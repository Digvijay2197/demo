"""Week 11: run real questions through the traced pipeline and save the traces.

    python scripts/w11_capture_pool.py            # -> logs/real_pool.jsonl

These are genuine model answers (prompt v1) with genuine per-span latency,
tokens and cost. w11_seed_logs.py resamples them into a week of background
traffic for the support drill.
"""
import os
import sys
import time

sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv

load_dotenv(os.path.join(os.getcwd(), ".env"))
os.environ["TRACE_LOG_PATH"] = os.path.abspath("logs/real_pool.jsonl")

from rag.generation.answer_service import answer_question
from scripts.eval_week6 import CASES

EXTRA = [
    "I'm dairy-free - can I use the ghee in the chicken biryani",
    "I'm allergic to milk, can the chicken biryani be made with ghee",
    "I'm dairy-free, what can I use instead of buttermilk in the Classic Carrot Cake",
    "I need a dairy-free swap for the yogurt in the chicken biryani",
    "is the chicken biryani dairy-free? suggest a dairy free substitute for anything that isn't",
    "dairy-free substitute for the butter in the Pecan Fingers",
    "which fat should I use in the chicken biryani if I am dairy-free",
    "I can't eat dairy. Which of the biryani fats is OK, oil or ghee?",
    "dairy-free here: can I keep the yogurt in the chicken biryani",
    "dairy-free diet: is the butter in the Pecan Fingers okay to use",
    "I'm vegan, can I use the ghee in the biryani",
    "I'm dairy free, is it fine to use the buttermilk in the Classic Carrot Cake",
    "lactose intolerant - can I use the whole milk in the yogurt recipe",
    "can I replace the milk in the yogurt recipe with a dairy-free option",
    "how do I make the sourdough with a gluten-free flour",
    "I'm nut-free - can I make the Pecan Fingers",
]

if __name__ == "__main__":
    answer_question("warm up the embedding model", user_id="capture")  # exclude cold start
    open("logs/real_pool.jsonl", "w").close()
    qs = [c[1] for c in CASES] + EXTRA
    for i, q in enumerate(qs, 1):
        try:
            answer_question(q, user_id="capture")
            print(f"[{i}/{len(qs)}] ok  {q[:60]}")
        except Exception as exc:  # noqa: BLE001
            print(f"[{i}/{len(qs)}] ERR {exc!r:.80}  {q[:50]}")
        time.sleep(7)
