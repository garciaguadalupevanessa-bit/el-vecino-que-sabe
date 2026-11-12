"""Single-call agent (AGENT_MODE=single): code plans and runs the tools, the LLM writes once.

Why: on Groq's free plan a model gets ~8000 tokens per minute, and the function-calling loop
needs 3-4 calls of ~6000 tokens per answer, so answers time out. Here the same deterministic
tools run first (search, eligibility, guide, alternatives), chosen by simple rules on the
question, and the LLM makes exactly one call to explain the results in Spanish. The response
shape (answer, aids, sources, trace, coverage_notes) is the same as the loop's.
"""
import json
import re
import unicodedata

from app.agent.profile_extract import extract_profile
from app.tools import run_tool

MAX_CHECKS = 3
_REQ_LIMIT = 8

GUIDE = re.compile(r"\bcomo\b.{0,20}\b(pido|pedir|pedirla|solicito|solicitar|solicitarla|tramito|tramitar|presento|presentar)\b"
                   r"|\b(solicitarla|pedirla|tramitarla)\b|\bdocumentacion\b|\bdocumentos\b|\bplazo\b|\bdonde\b.{0,15}\b(pido|presento|solicito)\b")
ALTERNATIVES = re.compile(r"alternativ|otras? ayudas?|no cumplo|no encaj|que mas (hay|puedo)")
EXPLAIN = re.compile(r"^(que es|que significa|explicamelo|explica|no entiendo)\b|\bque es (ser |el |la |un |una )")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def intent_of(question: str) -> str:
    q = _norm(question)
    if EXPLAIN.search(q) and not GUIDE.search(q):
        return "explain"
    if GUIDE.search(q):
        return "guide"
    if ALTERNATIVES.search(q):
        return "alternatives"
    return "search"


def _focus_aid(candidates: list[dict], messages: list[dict]) -> dict | None:
    """The aid the user is talking about: the candidate whose name words appear most in the recent conversation."""
    if not candidates:
        return None
    recent = _norm(" ".join(m.get("content", "") for m in messages[-4:]))
    words = set(re.findall(r"[a-z]{4,}", recent))

    def score(aid: dict) -> int:
        name = set(re.findall(r"[a-z]{4,}", _norm(aid.get("name", ""))))
        return len(name & words)

    best = max(candidates, key=score)
    return best if score(best) >= 2 else candidates[0]


def _compact_check(c: dict) -> dict:
    reqs = c.get("requirements") or []
    return {
        "aid_id": c.get("aid_id"), "name": c.get("name"), "overall_result": c.get("overall_result"),
        "recommendation_es": c.get("recommendation_es"), "reliability_label_es": c.get("reliability_label_es"),
        "source_url": c.get("source_url"), "verified_on": c.get("verified_on"),
        "missing_fields": c.get("missing_fields"),
        "requirements": [{"description": r.get("description"), "status": r.get("status"),
                          "explanation_es": r.get("explanation_es")} for r in reqs[:_REQ_LIMIT]],
        **({"note": c["note"]} if c.get("note") else {}),
    }


def _compact_search(s: dict) -> list[dict]:
    keep = ("id", "name", "agency", "scope", "short_description", "reliability_label_es", "source_url", "deadline", "open")
    return [{k: r.get(k) for k in keep if r.get(k) is not None} for r in (s.get("results") or [])]


def _compact_guide(g: dict) -> dict:
    keep = ("aid_id", "name", "agency", "deadline", "how_to_apply", "documents", "incomplete_data", "guide_available",
            "reliability_label_es", "source_url", "verified_on", "note", "error")
    return {k: g.get(k) for k in keep if g.get(k) is not None}


def _compact_alternatives(a: dict) -> dict:
    alts = [{k: x.get(k) for k in ("aid_id", "id", "name", "overall_result", "missing_fields", "reliability_label_es", "source_url")
             if x.get(k) is not None} for x in (a.get("alternatives") or [])]
    return {"alternatives": alts, **{k: a[k] for k in ("to_become_eligible", "note", "error") if a.get(k)}}


def plan_and_run(messages: list[dict], form_profile: dict) -> tuple[dict, list[tuple[str, dict, dict]]]:
    """Returns (profile used, [(tool, input, full output)]) for the last user question."""
    question = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    profile = {**extract_profile(messages), **(form_profile or {})}
    intent = intent_of(question)
    calls: list[tuple[str, dict, dict]] = []

    def call(tool: str, args: dict) -> dict:
        output = run_tool(tool, args, form_profile or {})
        calls.append((tool, args, output))
        return output

    if intent == "explain":
        return profile, calls

    search = call("search_aids", {"profile": profile, "max_results": 5})
    candidates = search.get("results") or []

    if intent == "search":
        for aid in candidates[:MAX_CHECKS]:
            call("check_eligibility", {"aid_id": aid["id"], "profile": profile})
        if not candidates:
            call("find_alternatives", {"profile": profile})
        return profile, calls

    focus = _focus_aid(candidates, messages)
    if intent == "guide" and focus:
        call("get_application_guide", {"aid_id": focus["id"]})
        call("check_eligibility", {"aid_id": focus["id"], "profile": profile})
    elif intent == "alternatives":
        if focus:
            call("check_eligibility", {"aid_id": focus["id"], "profile": profile})
        call("find_alternatives", {"profile": profile, **({"aid_id": focus["id"]} if focus else {})})
    return profile, calls


def results_message(intent: str, profile: dict, calls: list[tuple[str, dict, dict]]) -> str:
    """Compact tool results for the single LLM call (full outputs still go to the UI panels)."""
    compact = []
    for tool, args, output in calls:
        if tool == "search_aids":
            data = {"results": _compact_search(output), **({"coverage_note": output["coverage_note"]} if output.get("coverage_note") else {})}
        elif tool == "check_eligibility":
            data = _compact_check(output)
        elif tool == "get_application_guide":
            data = _compact_guide(output)
        else:
            data = _compact_alternatives(output)
        compact.append({"tool": tool, "result": data})
    return (
        "# TOOL RESULTS FOR THIS TURN\n"
        "The system has already run the tools for the user's last message. You cannot call tools now: "
        "answer only from these results, following all the rules above. "
        "If a result needs data the user has not given, ask for it (one question).\n"
        f"Question type: {intent}\n"
        f"Profile used: {json.dumps(profile, ensure_ascii=False)}\n"
        + json.dumps(compact, ensure_ascii=False, default=str)
    )
