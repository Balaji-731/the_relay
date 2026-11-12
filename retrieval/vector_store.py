"""
Vector Store module for The Relay.
Manages persistent ChromaDB collections for each retrieval chunk size configuration.
"""

import os
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions

from ingestion.pdf_loader import load_all_papers
from ingestion.chunker import chunk_pages


DB_DIR = "data/chroma_db"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Retrieval settings required for Table 3
CONFIGURATIONS = {
    "setting_a": {"chunk_size": 300, "overlap": 30, "collection_name": "relay_setting_300"},
    "setting_b": {"chunk_size": 500, "overlap": 50, "collection_name": "relay_setting_500"},
    "setting_c": {"chunk_size": 700, "overlap": 70, "collection_name": "relay_setting_700"},
}


def get_embedding_function():
    """Initializes local sentence-transformers embedding function."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME
    )


def get_chroma_client(db_dir: str = DB_DIR) -> chromadb.PersistentClient:
    """Returns a persistent ChromaDB client."""
    os.makedirs(db_dir, exist_ok=True)
    return chromadb.PersistentClient(path=db_dir)


def populate_collection(
    client: chromadb.PersistentClient,
    collection_name: str,
    chunks: List[Dict[str, Any]],
    embedding_fn
):
    """Inserts chunks and metadata into the specified collection in batches."""
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

    existing_count = collection.count()
    if existing_count >= len(chunks):
        print(f"Collection '{collection_name}' already populated ({existing_count} items). Skipping.")
        return collection

    print(f"Populating '{collection_name}' with {len(chunks)} chunks...")
    
    # ChromaDB accepts batches of ids, documents, and metadatas
    batch_size = 64
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        ids = [c["id"] for c in batch]
        documents = [c["text"] for c in batch]
        metadatas = [c["metadata"] for c in batch]

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

    print(f"Successfully populated '{collection_name}' with {collection.count()} chunks.")
    return collection


def build_all_vector_stores(papers_dir: str = "data/papers"):
    """Loads all papers and builds the 3 Chroma collections."""
    pages = load_all_papers(papers_dir)
    client = get_chroma_client()
    embedding_fn = get_embedding_function()

    for setting_name, cfg in CONFIGURATIONS.items():
        print(f"\n--- Preparing {setting_name} ({cfg['chunk_size']} words) ---")
        chunks = chunk_pages(pages, chunk_size=cfg["chunk_size"], overlap=cfg["overlap"])
        populate_collection(client, cfg["collection_name"], chunks, embedding_fn)

    print("\nAll 3 vector collections are ready in data/chroma_db!")


if __name__ == "__main__":
    build_all_vector_stores()