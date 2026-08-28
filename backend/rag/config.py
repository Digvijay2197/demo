"""Central configuration, read once from the environment.

Every tunable in the RAG pipeline lives here so the rest of the code never
touches os.environ directly.
"""
import os

# Quiet third-party noise unless the environment already asked otherwise.
# Safe defaults; override in .env.
for _k, _v in {
    "ANONYMIZED_TELEMETRY": "False",     # ChromaDB usage telemetry
    "TOKENIZERS_PARALLELISM": "false",   # HuggingFace fork-after-parallelism warning
    "HF_HUB_DISABLE_TELEMETRY": "1",     # HuggingFace Hub telemetry
}.items():
    os.environ.setdefault(_k, _v)


def _abs(path: str) -> str:
    """Resolve a possibly-relative path against the backend/ working directory."""
    return path if os.path.isabs(path) else os.path.abspath(os.path.join(os.getcwd(), path))


# --- LLM ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

# --- Embeddings ---
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# --- Vector store ---
CHROMA_DIR = _abs(os.environ.get("CHROMA_DIR", "./data/chroma"))
CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "recipes")

# --- Source documents ---
PDF_DIR = _abs(os.environ.get("PDF_DIR", "./data/pdfs"))

# --- Chunking ---
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "150"))

# --- Retrieval ---
TOP_K = int(os.environ.get("TOP_K", "5"))
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.22"))

# --- API ---
PORT = int(os.environ.get("PORT", "8000"))
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:3006")
