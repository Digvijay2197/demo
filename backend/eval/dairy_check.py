"""Re-export: the eval assertion and the log-time flag share ONE implementation."""
from rag.observability.dairy_check import *  # noqa: F401,F403
from rag.observability.dairy_check import (  # noqa: F401
    DAIRY_TERMS,
    dairy_free_violation,
    endorsed_dairy_sentences,
    mentions_dairy_awareness,
)
