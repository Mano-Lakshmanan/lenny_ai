
from pathlib import Path

import chromadb

BASE_DIR = Path(__file__).resolve().parents[2]
VECTOR_DB_DIR = BASE_DIR / "backend" / "chroma_db"

client = chromadb.PersistentClient(
    path=str(VECTOR_DB_DIR)
)

collection = client.get_or_create_collection(
    name="lenny_transcripts",
    metadata={"hnsw:space": "cosine"},
)


def retrieve_context(question: str, top_k: int = 5) -> list[dict]:
    if not question.strip():
        return []

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[question],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    passages = []

    for i, text in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i]

        passages.append({
            "text": text,
            "source": metadata.get("source", "Unknown"),
            "chunk_index": metadata.get("chunk_index"),
            "distance": results["distances"][0][i],
        })

    return passages


if __name__ == "__main__":
    question = input("Ask a product/growth question: ")
    passages = retrieve_context(question)

    if not passages:
        print("No passages found. Check your ingestion and vector database.")
    else:
        for i, passage in enumerate(passages, start=1):
            print(f"\n--- Result {i} ---")
            print("Source:", passage["source"])
            print("Chunk:", passage["chunk_index"])
            print("Distance:", round(passage["distance"], 4))
            print("Text:", passage["text"][:800])
