"""The single entry point: ask(question) -> answer.

Wires together everything built in Weeks 3-11 behind one function:

  question
    -> deterministic allergen parse (domain.extract_avoid)       [independent of the LLM]
    -> hand-built agent loop (Week 7 shape: budgeted lap loop, no framework agent)
         -> tools DISCOVERED over MCP from capstone/mcp_server.py   (Week 9)
              search_recipes -> Week 3-4 hybrid RAG (Chroma + BM25 + RRF)
              check_allergens / scale_recipe / lookup_substitution / ... -> exact-match domain logic
    -> post-answer guards (guards.apply_guards)                  [version, allergen, temp, swap]
    -> trace (obs): ONE trace id across the loop and the MCP server, cost + latency per span (Week 11)
"""
from __future__ import annotations

import json
import time
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent.budget import Budget, BudgetExceeded
from agent.llm import Usage, _base_llm, usage_of
from capstone import config, domain, guards, obs
from capstone.mcp_conn import McpConnection

PROMPT_VERSION = "cap-v1"

SYSTEM_PROMPT = """You are the Pantry-to-Plate assistant for a recipe publisher. Answer ONLY from the \
tools; never from memory.
1. Find recipes with search_recipes. If no hit is the dish asked for, say it is not in the library. Never invent a recipe.
2. Cite every recipe you rely on exactly as the tool gives it, e.g. [R-101@reformulated-2025] (id AND version).
3. For any allergy/dietary-safety statement call check_allergens with the SAME version you cite and report its verdict. \
Never infer allergens from ingredient text. may_contain means NOT safe. cannot_verify means say you cannot verify - never guess. \
Never guarantee safety.
4. Scale only with scale_recipe; cook time is not multiplied by the scale factor.
5. For meat, fish or egg dishes state the internal_temp_c from the recipe.
6. For substitutions call lookup_substitution with the user's allergens; if check_substituted_recipe exists, \
call it on the recipe AS SUBSTITUTED before suggesting any swap to someone with an allergy.
Be brief."""

_conn: Optional[McpConnection] = None


def connection() -> McpConnection:
    global _conn
    if _conn is None:
        _conn = McpConnection()
    return _conn


def reset_connection() -> None:
    """Drop the MCP session (the server subprocess reads its config at start-up)."""
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


def _llm(conn: McpConnection):
    return _base_llm().bind_tools(conn.model_tools())


def ask(question: str, user_id: str = "", budget: Optional[Budget] = None,
        conn: Optional[McpConnection] = None, verbose: bool = False) -> dict:
    conn = conn or connection()
    budget = budget or Budget(max_iterations=8, max_tokens=30_000, max_cost_usd=0.03, wall_clock_s=120)
    avoid, unsupported = domain.extract_avoid(question)
    tr = obs.start_trace(question, avoid, unsupported, user_id, extra={"prompt_version": PROMPT_VERSION})
    tid = tr.trace_id
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=question)]
    llm = _llm(conn)
    usage = Usage()
    started = time.monotonic()
    tool_calls: list[dict] = []
    raw, terminated, error, lap = "", "", None, 0

    try:
        with obs.span("discovery", "mcp_list", tools=conn.tool_names):
            pass
        while True:
            try:
                budget.check(iteration=lap, tokens=usage.total_tokens, cost_usd=usage.cost_usd, started_at=started)
            except BudgetExceeded as be:
                terminated = be.which
                break
            with obs.span(f"llm_lap_{lap + 1}", "llm") as sp:
                try:
                    resp: AIMessage = llm.invoke(messages)
                except Exception as exc:  # noqa: BLE001
                    text = str(exc)
                    if "tool_use_failed" in text or "Tool call validation failed" in text:
                        lap += 1
                        sp["malformed_tool_call"] = True
                        messages.append(HumanMessage(content="Your last tool call was malformed: "
                                                    f"{text[-200:]}\nRe-issue it with valid arguments."))
                        continue
                    raise
                u = usage_of(resp)
                usage = usage + u
                sp.update(tokens_in=u.prompt_tokens, tokens_out=u.completion_tokens, cost_usd=u.cost_usd)
            lap += 1
            messages.append(resp)
            if not resp.tool_calls:
                raw = guards.norm(resp.content or "")
                break
            for tc in resp.tool_calls:
                name, args = tc["name"], tc.get("args") or {}
                with obs.span(f"mcp:{name}", "mcp_call", tool=name, args=args, trace_id_sent=tid) as sp:
                    result = conn.call(name, args, tid)
                    sp["result_chars"] = len(json.dumps(result))
                    sp["error"] = result.get("error") if isinstance(result, dict) else None
                tool_calls.append({"tool": name, "args": args, "result": result, "lap": lap})
                messages.append(ToolMessage(content=json.dumps(result, separators=(",", ":")),
                                            tool_call_id=tc["id"]))
                if verbose:
                    print(f"  lap {lap}: {name}({json.dumps(args)[:90]})")
    except Exception as exc:  # noqa: BLE001
        error = repr(exc)[:300]

    guards_fired: list[str] = []
    final = raw
    assessment: dict = {}
    if raw and not error:
        with obs.span("guards", "guard") as sp:
            if config.guards_on():
                final, guards_fired, assessment = guards.apply_guards(question, raw, tool_calls)
            else:
                assessment = guards.assess(question, raw, tool_calls)
            sp["fired"] = guards_fired
    refused = bool(raw) and guards.says_refusal(final) and not guards.citations(final)
    rec = obs.finish_trace(answer=final, raw_answer=raw, refused=refused, guards_fired=guards_fired,
                           error=error or (f"budget:{terminated}" if terminated else None),
                           tools_called=[t["tool"] for t in tool_calls], laps=lap)
    return {"trace_id": tid, "answer": final, "raw_answer": raw, "refused": refused,
            "guards_fired": guards_fired, "assessment": assessment, "tool_calls": tool_calls,
            "citations": [{"recipe_id": r, "version": v, "url": domain.citation_url(domain.get_record(r, v))}
                          for r, v in guards.citations(final) if guards._exists(r, v)],
            "laps": lap, "tokens": usage.total_tokens, "cost_usd": round(usage.cost_usd, 6),
            "latency_ms": (rec or {}).get("latency_ms"), "error": error, "terminated_by": terminated,
            "tools_discovered": conn.tool_names}
