import json
import os
import sys

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from evaluation.questions import KNOWN_ANSWER_QUESTIONS, GROUNDED_QUESTION_IDS, OUT_OF_CORPUS_QUESTIONS
from rag.generation.answer_service import answer_question


def main():
    grounded = []
    for qid in GROUNDED_QUESTION_IDS:
        q = next(k for k in KNOWN_ANSWER_QUESTIONS if k.id == qid)
        response = answer_question(q.question)
        grounded.append({"id": q.id, "question": q.question, "expected_answer": q.expected_answer, **response})
        print(f"\n[{q.id}] {q.question}\n-> {response['answer']}\ncitations: {json.dumps(response['citations'])}")

    refusals = []
    for question in OUT_OF_CORPUS_QUESTIONS:
        response = answer_question(question)
        refusals.append({"question": question, **response})
        print(f"\n[refusal check] {question}\n-> {response['answer']}\nrefused: {response['refused']}")

    with open(os.path.join(os.getcwd(), "evaluation", "grounded_answers.json"), "w", encoding="utf-8") as f:
        json.dump(grounded, f, indent=2)
    with open(os.path.join(os.getcwd(), "evaluation", "refusals.json"), "w", encoding="utf-8") as f:
        json.dump(refusals, f, indent=2)


if __name__ == "__main__":
    main()
