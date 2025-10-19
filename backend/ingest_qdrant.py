import os
import pickle
from typing import List, Dict
from dotenv import load_dotenv
from tqdm import tqdm

from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from config import config


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int = 384) -> None:
    """Create collection and payload index if they do not exist."""
    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if collection_name not in names:
        print(f"Creating collection '{collection_name}' with size={vector_size} and COSINE distance...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        try:
            # Index the podcast_tag field for faster filtering if needed
            client.create_payload_index(
                collection_name=collection_name,
                field_name="podcast_tag",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            print(f"Warning: create_payload_index failed: {e}")
    else:
        print(f"Collection '{collection_name}' already exists.")


def locate_chunks_pkl() -> str:
    """Find the chunks.pkl path in common locations."""
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "qdrant_data", "chunks.pkl"),
        os.path.join(os.getcwd(), "..", "qdrant_data", "chunks.pkl"),
        os.path.join("/app", "qdrant_data", "chunks.pkl"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("chunks.pkl not found; ensure qdrant_data/chunks.pkl exists.")


def load_chunks(path: str) -> List[Dict]:
    with open(path, "rb") as f:
        chunks = pickle.load(f)
    print(f"Loaded {len(chunks)} chunks from {path}")
    return chunks


def upsert_chunks(client: QdrantClient, model: SentenceTransformer, chunks: List[Dict], collection_name: str) -> None:
    print("Encoding and upserting chunks into Qdrant...")
    for chunk in tqdm(chunks, desc="Upserting"):
        vector = model.encode(chunk.get("content", "")).tolist()
        client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=chunk.get("id"),
                    vector=vector,
                    payload={
                        "podcast_title": chunk.get("podcast_title", ""),
                        "podcast_tag": chunk.get("podcast_tag", ""),
                        "content": chunk.get("content", ""),
                    },
                )
            ],
        )


def main():
    load_dotenv()

    # Connect to Qdrant and load model
    client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
    print(f"Connected to Qdrant at {config.QDRANT_HOST}:{config.QDRANT_PORT}")

    # Wait for Qdrant readiness
    import time
    start = time.time()
    while True:
        try:
            client.get_collections()
            print("Qdrant is ready.")
            break
        except Exception as e:
            if time.time() - start > 60:
                raise RuntimeError("Qdrant did not become ready in time") from e
            time.sleep(2)

    model = SentenceTransformer(config.EMBEDDING_MODEL)
    print(f"Loaded embedding model: {config.EMBEDDING_MODEL}")

    # Ensure collection exists
    ensure_collection(client, config.COLLECTION_NAME, vector_size=384)

    # Load chunks and upsert
    chunks_path = locate_chunks_pkl()
    chunks = load_chunks(chunks_path)
    upsert_chunks(client, model, chunks, config.COLLECTION_NAME)

    print(f"Ingestion completed: {len(chunks)} chunks upserted into '{config.COLLECTION_NAME}'.")


if __name__ == "__main__":
    main()