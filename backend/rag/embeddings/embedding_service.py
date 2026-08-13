import os
from typing import List

# Embedding model kept identical across both chunking experiments so that
# chunking strategy is the only intentional variable (see results.md).
# Free/open-source local model, no API key required.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return [e.tolist() for e in embeddings]


def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]
