
from pathlib import Path
import re

import chromadb

BASE_DIR = Path(__file__).resolve().parents[2]
DOCUMENTS_DIR = BASE_DIR / "documents" / "podcasts"
VECTOR_DB_DIR = BASE_DIR / "backend" / "chroma_db"

client = chromadb.PersistentClient(
    path=str(VECTOR_DB_DIR)
)

collection = client.get_or_create_collection(
    name="lenny_transcripts",
    metadata={"hnsw:space": "cosine"},
)


def clean_text(text: str) -> str:
    # Remove YAML frontmatter when present.
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]

    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, size: int = 1000,
               overlap: int = 150) -> list[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(text):
            break

        start = end - overlap

    return chunks


def ingest_documents():
    files = list(DOCUMENTS_DIR.rglob("*.md"))

    if not files:
        raise FileNotFoundError(
            f"No Markdown transcripts found in {DOCUMENTS_DIR}"
        )

    ids = []
    documents = []
    metadatas = []

    for file_path in files:
        raw_text = file_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        text = clean_text(raw_text)

        for index, chunk in enumerate(chunk_text(text)):
            chunk_id = f"{file_path.stem}_{index}"

            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "source": str(file_path.relative_to(BASE_DIR)),
                "chunk_index": index,
            })

    # Upsert makes repeated ingestion safe for existing chunk IDs.
    for start in range(0, len(ids), 100):
        collection.upsert(
            ids=ids[start:start + 100],
            documents=documents[start:start + 100],
            metadatas=metadatas[start:start + 100],
        )

    print(f"Transcript files found: {len(files)}")
    print(f"Chunks processed: {len(ids)}")
    print(f"Chunks stored: {collection.count()}")
    print(f"Vector database: {VECTOR_DB_DIR}")


if __name__ == "__main__":
    ingest_documents()
