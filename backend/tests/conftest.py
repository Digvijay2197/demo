import os
import sys
import tempfile

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)

# Point the pipeline at throwaway temp folders BEFORE rag.config is imported,
# so tests never touch the real ./data/pdfs or ./data/chroma.
_TMP = tempfile.mkdtemp(prefix="recipe_rag_test_")
os.environ.setdefault("PDF_DIR", os.path.join(_TMP, "pdfs"))
os.environ.setdefault("CHROMA_DIR", os.path.join(_TMP, "chroma"))
os.environ.setdefault("CHROMA_COLLECTION", "recipes_test")
os.environ.setdefault("GROQ_API_KEY", "test-key-not-used")
os.makedirs(os.environ["PDF_DIR"], exist_ok=True)
