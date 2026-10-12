
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from models import ChatSession, Message
from services.llm import generate_answer

router = APIRouter(prefix="/api/chats", tags=["Messages"])


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    provider: Literal["ollama", "openrouter"] = "ollama"


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatReply(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    sources: list[dict]
    model: str


@router.post("/{chat_id}/messages", response_model=ChatReply)
def send_message(
    chat_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
):
    chat = db.get(ChatSession, chat_id)

    if chat is None:
        raise HTTPException(
            status_code=404,
            detail="Chat not found",
        )

    question = payload.content.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Message cannot be empty",
        )

    # Load only this chat's earlier messages.
    previous_messages = (
        db.query(Message)
        .filter(Message.session_id == chat_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(10)
        .all()
    )

    # The query returns newest first; the model needs oldest first.
    previous_messages.reverse()

    conversation_history = [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in previous_messages
        if message.role in ("user", "assistant")
    ]

    # Save the new user message.
    user_message = Message(
        session_id=chat_id,
        role="user",
        content=question,
    )

    try:
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save the user message",
        )

    # Generate an answer using the selected model and chat history.
    result = generate_answer(
        question,
        provider=payload.provider,
        conversation_history=conversation_history,
    )

    assistant_message = Message(
        session_id=chat_id,
        role="assistant",
        content=result["answer"],
    )

    try:
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save the assistant message",
        )

    return ChatReply(
        user_message=user_message,
        assistant_message=assistant_message,
        sources=result.get("sources", []),
        model=result.get("model", payload.provider),
    )


@router.get(
    "/{chat_id}/messages",
    response_model=list[MessageResponse],
)
def get_messages(
    chat_id: int,
    db: Session = Depends(get_db),
):
    chat = db.get(ChatSession, chat_id)

    if chat is None:
        raise HTTPException(
            status_code=404,
            detail="Chat not found",
        )

    return (
        db.query(Message)
        .filter(Message.session_id == chat_id)
        .order_by(Message.created_at, Message.id)
        .all()
    )
