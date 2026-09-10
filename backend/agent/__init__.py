"""Week 7 — a hand-built recipe-adaptation agent loop and the fixed workflow
it is raced against.

Nothing here touches the RAG pipeline in ``rag/``; the recipe data is a small
structured book (``agent/recipes.py``) so the race measures orchestration, not
retrieval. Entry points:

    scripts/race_week7.py            # agent vs workflow over 10 requests
    scripts/race_week7.py --budget-demo   # one clean budget termination
"""
