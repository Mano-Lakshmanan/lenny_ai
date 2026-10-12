import os
import re
import time

import ollama
from dotenv import load_dotenv
from openai import OpenAI

from services.rag import retrieve_context

load_dotenv()


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip()

MAX_CONTEXT_CHARS = 4500
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))
TOP_K = 3

MAX_HISTORY_MESSAGES = 4
MAX_HISTORY_CHARS = 2000

OLLAMA_CONTEXT_WINDOW = int(os.getenv("OLLAMA_CONTEXT_WINDOW", "8192"))
OLLAMA_TEMPERATURE = 0.1


# ---------------------------------------------------------
# System prompt
# ---------------------------------------------------------

SYSTEM_PROMPT = """
You are Lenny's Growth Assistant, an assistant specializing in product
management, startups, and growth.

Answer the user's current question using the supplied Lenny's Podcast
transcript passages as your primary evidence.

Rules:
- Return only the finished answer for the user.
- Start directly with the answer; do not restate the question.
- Never include internal reasoning, analysis, planning, or draft notes.
- Use clear, natural language, with headings or bullets when useful.
- Explain transcript findings in your own words.
- Cite relevant transcript filenames naturally.
- Never invent facts, quotations, filenames, chunk numbers, or sources.
- Distinguish transcript-supported findings from your own recommendations.
- If the supplied evidence is insufficient, explicitly say so.
- Use conversation history only to understand follow-up questions.
- Finish every response with a complete sentence.
"""


# ---------------------------------------------------------
# Response cleanup
# ---------------------------------------------------------

def clean_answer(answer: str) -> str:
    """Remove explicit model thinking tags without guessing at prose."""

    answer = (answer or "").strip()
    if not answer:
        return ""

    # If the model explicitly emitted a closing think tag, discard everything
    # before it. This is safer than guessing where reasoning ends.
    closing_tags = list(re.finditer(r"</think\s*>", answer, flags=re.IGNORECASE))
    if closing_tags:
        answer = answer[closing_tags[-1].end():].strip()

    # Remove any remaining complete think blocks and stray tags.
    answer = re.sub(
        r"<think\b[^>]*>.*?</think\s*>",
        "",
        answer,
        flags=re.IGNORECASE | re.DOTALL,
    )
    answer = re.sub(r"</?think\b[^>]*>", "", answer, flags=re.IGNORECASE)

    return answer.strip()


def _error(message: str, model_name: str, sources=None) -> dict:
    return {
        "answer": message,
        "sources": sources or [],
        "model": model_name,
    }


# ---------------------------------------------------------
# Main answer generation function
# ---------------------------------------------------------

def generate_answer(
    question,
    passages=None,
    provider=None,
    conversation_history=None,
):
    started_at = time.perf_counter()
    question = (question or "").strip()
    conversation_history = conversation_history or []

    if not question:
        return _error("Please enter a question.", "none")

    selected_provider = (provider or LLM_PROVIDER).strip().lower()
    if selected_provider not in ("ollama", "openrouter"):
        return _error("Unsupported model provider.", selected_provider)

    model_name = (
        OLLAMA_MODEL if selected_provider == "ollama" else OPENROUTER_MODEL
    )

    greetings = {
        "hello", "hi", "hey", "hello there",
        "good morning", "good afternoon", "good evening",
    }
    if question.lower().strip("!.,? ") in greetings:
        return _error(
            "Hello! I'm Lenny's Growth Assistant. Ask me about product "
            "management, startups, or growth strategies discussed in "
            "Lenny's Podcast.",
            model_name,
        )

    sources = []

    try:
        # 1. Validate and bound conversation history.
        history = []
        for item in conversation_history[-MAX_HISTORY_MESSAGES:]:
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content") or ""
            if role not in ("user", "assistant") or not isinstance(content, str):
                continue

            content = content.strip()
            if content:
                history.append({"role": role, "content": content})

        history_parts = []
        remaining_history_chars = MAX_HISTORY_CHARS
        for item in reversed(history):
            if remaining_history_chars <= 0:
                break
            content = item["content"][:remaining_history_chars]
            history_parts.insert(0, f'{item["role"].title()}: {content}')
            remaining_history_chars -= len(content)

        history_text = "\n".join(history_parts) if history_parts else "No earlier messages."

        # 2. Retrieve transcript passages.
        previous_questions = [
            item["content"] for item in history if item["role"] == "user"
        ]
        retrieval_query = question
        if previous_questions:
            retrieval_query = (
                f"Previous question: {previous_questions[-1]}\n"
                f"Current question: {question}"
            )

        retrieval_started = time.perf_counter()
        if passages is None:
            passages = retrieve_context(retrieval_query, top_k=TOP_K)
        print(f"RAG retrieval: {time.perf_counter() - retrieval_started:.2f}s")

        if not passages:
            return _error(
                "I couldn't find sufficient supporting evidence in the "
                "available Lenny's Podcast transcripts to answer this "
                "question reliably.",
                model_name,
            )

        # 3. Build evidence context and source metadata.
        context_parts = []
        seen_sources = set()
        remaining_chars = MAX_CONTEXT_CHARS

        for passage in passages:
            if not isinstance(passage, dict):
                continue

            text = passage.get("text") or ""
            source = passage.get("source") or "Unknown"
            chunk_index = passage.get("chunk_index")

            if not isinstance(text, str):
                continue

            text = text.strip()
            if not text or remaining_chars <= 0:
                continue

            text = text[:remaining_chars]
            remaining_chars -= len(text)
            context_parts.append(
                f"Source: {source}\n"
                f"Chunk: {chunk_index}\n"
                f"Passage:\n{text}"
            )

            source_key = (source, chunk_index)
            if source_key not in seen_sources:
                sources.append({"source": source, "chunk_index": chunk_index})
                seen_sources.add(source_key)

        if not context_parts:
            return _error("No usable transcript passages were found.", model_name)

        context = "\n\n---\n\n".join(context_parts)

        # 4. Build the prompt.
        user_prompt = (
            "Answer directly. Return only the finished answer for the user. "
            "Do not reveal internal reasoning, analysis, planning, or draft notes.\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Current user question:\n{question}\n\n"
            f"Retrieved podcast transcript evidence:\n{context}\n\n"
            "Instructions:\n"
            "- Answer the current question directly using the evidence.\n"
            "- Use history only to understand follow-up questions.\n"
            "- Explain relevant findings in your own words.\n"
            "- Cite relevant transcript filenames naturally.\n"
            "- Acknowledge when evidence is insufficient.\n"
            "- Do not invent sources or unsupported claims.\n"
            "- Return only the completed answer, not reasoning or a plan.\n"
        )

        model_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 5. Generate using the selected provider.
        generation_started = time.perf_counter()

        if selected_provider == "ollama":
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=model_messages,
                think=True,
                keep_alive="10m",
                options={
                    "num_predict": MAX_OUTPUT_TOKENS,
                    "num_ctx": OLLAMA_CONTEXT_WINDOW,
                    "temperature": OLLAMA_TEMPERATURE,
                },
            )

            message = response.message
            thinking = getattr(message, "thinking", None) or ""
            answer = (getattr(message, "content", None) or "").strip()
            done_reason = getattr(response, "done_reason", None)

            print("Ollama thinking length:", len(thinking))
            print("Ollama answer length:", len(answer))
            print("Ollama done reason:", done_reason)

            eval_count = getattr(response, "eval_count", 0) or 0
            eval_duration = getattr(response, "eval_duration", 0) or 0
            if eval_count and eval_duration:
                print(
                    "Generation speed: "
                    f"{eval_count / (eval_duration / 1e9):.2f} tokens/s"
                )

            # Never display a response known to be token-truncated.
            if done_reason == "length":
                print(
                    f"Warning: Model reached output limit ({MAX_OUTPUT_TOKENS} tokens). "
                    f"Thinking length: {len(thinking)}, Answer length: {len(answer)}"
                )
                return _error(
                    "The model stopped before completing its answer because "
                    "it reached the output limit. Please try again.",
                    model_name,
                    sources,
                )

        else:
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise RuntimeError("OPENROUTER_API_KEY is missing from backend/.env")

            client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=60.0,
                max_retries=1,
            )
            response = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=model_messages,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.3,
            )
            choice = response.choices[0]
            answer = choice.message.content or ""
            print("OpenRouter finish reason:", choice.finish_reason)

            if choice.finish_reason == "length":
                return _error(
                    "The model stopped before completing its answer because "
                    "it reached the output limit. Please try again.",
                    model_name,
                    sources,
                )

        print(f"Model generation: {time.perf_counter() - generation_started:.2f}s")
        print(f"Total LLM request: {time.perf_counter() - started_at:.2f}s")

        answer = clean_answer(answer)
        if not answer:
            answer = (
                "The selected model did not return a usable answer. "
                "Please try again or switch models."
            )

        return {
            "answer": answer,
            "sources": sources,
            "model": model_name,
        }

    except Exception as exc:
        print(
            f"LLM request failed. Provider={selected_provider}; "
            f"Error={type(exc).__name__}: {exc}"
        )
        return _error(
            f"I couldn't generate an answer using {selected_provider}. "
            "Check the backend terminal for diagnostic details, then try "
            "again or switch models.",
            selected_provider,
            sources,
        )
