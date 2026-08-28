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
# gpt-oss / qwen on Groq are reasoning models - "low" keeps hidden reasoning
# tokens (and cost / rate-limit pressure) down. Ignored by non-reasoning models.
GROQ_REASONING_EFFORT = os.environ.get("GROQ_REASONING_EFFORT", "low")
# Hard cap on how much retrieved context is sent to the LLM per question.
# Keeps a big multi-recipe PDF from blowing the Groq free-tier 8k tokens/min
# limit (~4 chars/token, so 4000 chars ≈ 1k tokens of context).
MAX_CONTEXT_CHARS = int(os.environ.get("MAX_CONTEXT_CHARS", "4000"))

# --- Embeddings ---
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# --- Vector store ---
CHROMA_DIR = _abs(os.environ.get("CHROMA_DIR", "./data/chroma"))
CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "recipes")

# --- Source documents ---
PDF_DIR = _abs(os.environ.get("PDF_DIR", "./data/pdfs"))


def _flag(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


# Index new/changed PDFs automatically: once when the API starts, and then
# whenever a file in PDF_DIR changes while it runs. Set either to false to
# require an explicit `python scripts/ingest.py` / POST /ingest instead.
AUTO_INGEST_ON_STARTUP = _flag("AUTO_INGEST_ON_STARTUP")
WATCH_PDF_DIR = _flag("WATCH_PDF_DIR")

# --- Chunking ---
# Small chunks: in a multi-recipe PDF this lands roughly one recipe per chunk,
# which both sharpens retrieval and keeps the context sent to the LLM small.
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "550"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "80"))

# --- Retrieval ---
TOP_K = int(os.environ.get("TOP_K", "4"))
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.22"))

# --- API ---
PORT = int(os.environ.get("PORT", "8000"))
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:3006")
