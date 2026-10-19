"""Shared RAG settings, used by both ingest.py (writing) and tool.py (searching).

Ingest and search MUST use the same embedding model and the same Chroma
folder, so they are defined once here.
"""

import os
from functools import cache
from pathlib import Path

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

# Server project root (…/MCPHybridRAG-Server).
PROJECT_DIR = Path(__file__).resolve().parents[2]

DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR", PROJECT_DIR / "documents"))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", PROJECT_DIR / "chroma_db"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen3-embedding:0.6b")
COLLECTION_NAME = "knowledge_base"
TOP_K = 3


@cache
def get_vectorstore() -> Chroma:
    """Open the local Chroma index (created once, then reused)."""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=OllamaEmbeddings(model=EMBEDDING_MODEL),
        persist_directory=str(CHROMA_DIR),
    )


def search(query: str, k: int = TOP_K) -> list:
    """Return the k chunks most similar to the query."""
    return get_vectorstore().similarity_search(query, k=k)
