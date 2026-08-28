"""Embedding model, wrapped as a LangChain Embeddings object.

Local sentence-transformers model (all-MiniLM-L6-v2 by default): free, runs
offline, no API key. Loaded lazily and cached so the ~90MB model is read from
disk only once per process.
"""
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from rag.config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )
