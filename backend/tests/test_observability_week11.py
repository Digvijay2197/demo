"""Week 11: per-request tracing + the dairy-free check that the eval and the log share."""
import json

from langchain_core.documents import Document

import rag.generation.answer_service as answer_service
from rag.observability import tracing
from rag.observability.dairy_check import answer_flags, dairy_free_violation

DOC = Document(
    page_content="Chicken Biryani\nOil or ghee - 3 tbsp\n1/2 cup yogurt",
    metadata={"chunk_id": "c-1", "source_file": "Chicken_Biryani_Recipe.pdf", "page": 1},
)


def _fake_retrieve(question, hybrid=None):
    return [(DOC, 0.8)]


def _fake_generate(question, results):
    from langchain_core.messages import AIMessage

    tracing.record_llm_usage(AIMessage(
        content="x", usage_metadata={"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100}))
    return "Use oil instead of ghee, which contains dairy. [source: Chicken_Biryani_Recipe.pdf p.1]"


def test_each_request_writes_one_trace_with_spans_cost_and_context_ids(tmp_path, monkeypatch):
    log = tmp_path / "traces.jsonl"
    monkeypatch.setenv("TRACE_LOG", "true")
    monkeypatch.setenv("TRACE_LOG_PATH", str(log))
    monkeypatch.setattr(answer_service, "retrieve", _fake_retrieve)
    monkeypatch.setattr(answer_service, "generate_grounded_answer", _fake_generate)

    answer_service.answer_question("I'm dairy-free - can I use ghee in the biryani", user_id="u_9")

    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert rec["trace_id"].startswith("tr_") and rec["user_id"] == "u_9"
    assert rec["prompt_version"] in ("v1", "v2", "v3") and rec["input_type"] == "dietary_restriction"
    assert [s["name"] for s in rec["spans"]] == ["retrieval", "generation", "tools"]
    assert all(s["latency_ms"] is not None for s in rec["spans"])
    gen = rec["spans"][1]
    assert (gen["tokens_in"], gen["tokens_out"]) == (1000, 100)
    assert gen["cost_usd"] > 0 and rec["cost_usd"] == gen["cost_usd"]
    assert rec["retrieved"][0]["chunk_id"] == "c-1"          # context ids are logged
    assert "ghee" in rec["answer"]                            # the OUTPUT is searchable
    assert rec["answer_flags"]["dairy_free_violation"] is False


def test_a_failing_request_is_still_logged(tmp_path, monkeypatch):
    log = tmp_path / "traces.jsonl"
    monkeypatch.setenv("TRACE_LOG", "true")
    monkeypatch.setenv("TRACE_LOG_PATH", str(log))
    monkeypatch.setattr(answer_service, "retrieve", _fake_retrieve)

    def boom(q, r):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(answer_service, "generate_grounded_answer", boom)
    try:
        answer_service.answer_question("anything")
    except RuntimeError:
        pass
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert "rate limited" in rec["error"]


def test_dairy_check_flags_endorsement_not_negation():
    assert dairy_free_violation("The recipe lists oil or ghee, so you can use either oil or ghee.")
    assert dairy_free_violation("Yes, the recipe already allows you to use ghee instead of oil.")
    assert not dairy_free_violation("Use oil (instead of ghee) for a dairy-free version.")
    assert not dairy_free_violation("It does not list a dairy-free substitute for the butter.")
    assert not dairy_free_violation("Ghee is made from butter and contains dairy; use oil.")


def test_restriction_detector_and_v3_reminder_only_for_restricted_questions():
    from rag.generation import groq_service
    from rag.generation.prompt import DIETARY_REMINDER
    from rag.observability.dairy_check import restriction_stated

    for q in ["I'm dairy-free - can I use ghee", "I'm allergic to milk, is ghee ok",
              "My daughter can't have any dairy", "I'm vegan, can I use butter", "lactose intolerant here"]:
        assert restriction_stated(q), q
    for q in ["can I use ghee instead of oil", "how much sugar is in the sourdough"]:
        assert not restriction_stated(q), q

    sent = {}

    class FakeLLM:
        def invoke(self, messages):
            from langchain_core.messages import AIMessage

            sent["user"] = messages[1].content
            return AIMessage(content="ok")

    orig = groq_service._get_llm
    groq_service._get_llm = lambda: FakeLLM()
    try:
        groq_service.PROMPT_VERSION, old = "v3", groq_service.PROMPT_VERSION
        groq_service.generate_grounded_answer("I'm dairy-free, ghee ok?", [(DOC, 0.9)])
        assert DIETARY_REMINDER in sent["user"]
        groq_service.generate_grounded_answer("can I use ghee instead of oil", [(DOC, 0.9)])
        assert DIETARY_REMINDER not in sent["user"]      # unrestricted questions: prompt untouched
        groq_service.PROMPT_VERSION = "v1"
        groq_service.generate_grounded_answer("I'm dairy-free, ghee ok?", [(DOC, 0.9)])
        assert DIETARY_REMINDER not in sent["user"]      # rollback to v1 really removes it
    finally:
        groq_service._get_llm = orig
        groq_service.PROMPT_VERSION = old


def test_answer_flags_only_fire_when_the_user_stated_a_restriction():
    bad = "You can use either oil or ghee."
    assert answer_flags("I'm dairy-free, can I use ghee", bad)["dairy_free_violation"]
    # same answer, no stated restriction -> a taste swap, not a violation
    assert not answer_flags("can I use ghee instead of oil", bad)["dairy_free_violation"]
