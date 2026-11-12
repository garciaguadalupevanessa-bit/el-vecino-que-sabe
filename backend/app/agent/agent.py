"""Agent loop over an OpenAI-compatible API (Groq by default):
LLM with function calling -> run tools -> final answer with sources."""
import json
import logging
import re
from datetime import date
from pathlib import Path

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from app.agent import single
from app.agent.tool_schemas import TOOLS_OPENAI
from app.core import config
from app.tools import run_tool

log = logging.getLogger("elvecinoquesabe.agent")

_PROMPT_TEMPLATE = (Path(__file__).with_name("system_prompt.md")).read_text(encoding="utf-8")
_client: OpenAI | None = None

# Messages in Spanish on purpose: they are shown to the end user.
MSG_NOT_CONFIGURED = "El servicio de IA no está configurado (falta LLM_API_KEY)."
MSG_BAD_KEY = "La clave del servicio de IA no es válida. Revisa LLM_API_KEY."
MSG_RATE_LIMIT = "Se ha alcanzado el límite de uso del servicio de IA. Espera un minuto e inténtalo de nuevo."
MSG_CONNECTION = "No se puede conectar con el servicio de IA. Inténtalo de nuevo en unos minutos."
MSG_GENERIC = "El asistente no ha podido procesar la consulta. Inténtalo de nuevo."
MSG_EMPTY_ANSWER = "No he podido generar una respuesta. ¿Puedes reformular la pregunta?"


class LLMError(Exception):
    """Error talking to the LLM provider (the message is safe to show to the user)."""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.LLM_API_KEY:
            raise LLMError(MSG_NOT_CONFIGURED)
        _client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
            timeout=config.LLM_TIMEOUT,
            max_retries=2,
        )
    return _client


def build_system_prompt(profile: dict) -> str:
    text = (_PROMPT_TEMPLATE
            .replace("{current_date}", date.today().isoformat())
            .replace("{app_name}", config.APP_NAME))
    if profile:
        text += (
            "\n\n# FORM PROFILE\n"
            "Data the user filled in on the form (treat it as true unless the user corrects it):\n"
            + json.dumps(profile, ensure_ascii=False)
        )
    return text


def _create(client, **kwargs):
    """Calls the LLM. Open models sometimes produce a malformed tool call
    (HTTP 400 'tool_use_failed' or 'Tool call validation failed'): in that case it retries."""
    last: Exception | None = None
    for _ in range(3):
        try:
            return client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            text = str(e)
            if ("tool_use_failed" in text or "Failed to call a function" in text
                    or "Tool call validation failed" in text):
                log.warning("Malformed tool call; retrying.")
                last = e
                continue
            raise
    raise last  # type: ignore[misc]


def _collect(obj, sources: dict, aids: dict, coverage_notes: dict | None = None, context: dict | None = None) -> None:
    """Collects candidate aid details and provenance for the response panels."""
    coverage_notes = coverage_notes if coverage_notes is not None else {}
    context = context or {}
    if isinstance(obj, dict):
        current = dict(context)
        for key in ("reliability", "verification_method", "verified_on", "last_checked_on"):
            if obj.get(key) is not None:
                current[key] = obj[key]
        current.setdefault("last_checked_on", current.get("verified_on"))
        territories = obj.get("territories")
        if isinstance(territories, list):
            labels = [item if isinstance(item, str) else item.get("name") or item.get("source_label")
                      for item in territories if isinstance(item, (str, dict))]
            labels = [label for label in labels if label]
            if labels:
                current["territories"] = labels
        listed_campaigns = obj.get("campaigns")
        if isinstance(listed_campaigns, list):
            current["campaigns"] = list(dict.fromkeys([
                *current.get("campaigns", []), *(str(item) for item in listed_campaigns if item)
            ]))
        year, label = obj.get("campaign_year"), obj.get("campaign_label")
        campaign = str(label or year) if label or year else None
        if campaign:
            current["campaigns"] = list(dict.fromkeys([*current.get("campaigns", []), campaign]))

        url = obj.get("source_url")
        if isinstance(url, str) and url.startswith("http"):
            source = sources.setdefault(url, {
                "url": url, "campaigns": [], "territories": [],
            })
            source["name"] = source.get("name") or obj.get("name") or obj.get("title")
            for key in ("reliability", "verification_method", "verified_on", "last_checked_on"):
                source[key] = current.get(key) or source.get(key)
            source["campaigns"] = list(dict.fromkeys([*source.get("campaigns", []), *current.get("campaigns", [])]))
            source["territories"] = list(dict.fromkeys([*source.get("territories", []), *current.get("territories", [])]))

        aid_id = obj.get("aid_id") or obj.get("id")
        if aid_id and obj.get("name") and (obj.get("reliability") or obj.get("overall_result")):
            aid = aids.setdefault(str(aid_id), {"id": str(aid_id), "campaigns": [], "territories": [], "requirements": []})
            for key in ("name", "overall_result", "reliability", "verification_method", "status", "source_url", "verified_on", "last_checked_on", "scope"):
                if obj.get(key) is not None:
                    aid[key] = obj[key]
            aid["campaigns"] = list(dict.fromkeys([*aid.get("campaigns", []), *current.get("campaigns", [])]))
            aid["territories"] = list(dict.fromkeys([*aid.get("territories", []), *current.get("territories", [])]))
            if isinstance(obj.get("requirements"), list) and obj["requirements"]:
                aid["requirements"] = obj["requirements"]

        note = obj.get("coverage_note")
        if isinstance(note, str) and note.strip():
            coverage_notes.setdefault(note, {
                "message": note,
                "territory": obj.get("coverage_territory") or ", ".join(current.get("territories", [])) or None,
            })
        for v in obj.values():
            _collect(v, sources, aids, coverage_notes, current)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, sources, aids, coverage_notes, context)


# Last safety net: fixes wording the model sometimes gets wrong, before the user sees it.
_POLISH = [
    (re.compile(r"\bde la FEGA\b"), "del FEGA"),
    (re.compile(r"\ba la FEGA\b"), "al FEGA"),
    (re.compile(r"\bla FEGA\b"), "el FEGA"),
    (re.compile(r"\bLa FEGA\b"), "El FEGA"),
    (re.compile(r"`?metadata[ _]only`?", re.IGNORECASE), "solo datos básicos, sin verificar"),
    (re.compile(r"\b[Rr]eliability\s*:"), "Fiabilidad:"),
    (re.compile(r"`(unknown|not_met|met|extracted|verified)`"), lambda m: {
        "unknown": "sin confirmar", "not_met": "no cumple", "met": "cumple",
        "extracted": "sin verificar", "verified": "verificada"}[m.group(1)]),
]


def polish_answer(text: str) -> str:
    for pattern, repl in _POLISH:
        text = pattern.sub(repl, text)
    return text


def _result(msg, trace, sources, aids, coverage_notes) -> dict:
    text = polish_answer((msg.content or "").strip()) or MSG_EMPTY_ANSWER
    return {
        "answer": text, "aids": list(aids.values()), "sources": list(sources.values()),
        "trace": trace, "coverage_notes": list(coverage_notes.values()),
    }


def _execute_call(tc, profile: dict) -> tuple[dict, dict]:
    """Runs one tool_call from the model. Returns (arguments, output)."""
    try:
        args = json.loads(tc.function.arguments or "{}")
    except json.JSONDecodeError:
        return {}, {"error": "The arguments are not valid JSON."}
    if not isinstance(args, dict):
        return {}, {"error": "The arguments must be a JSON object."}
    return args, run_tool(tc.function.name, args, profile)


def run_agent(messages: list[dict], profile: dict) -> dict:
    if config.AGENT_MODE == "single":
        return run_single(messages, profile)
    return run_loop(messages, profile)


def run_single(messages: list[dict], profile: dict) -> dict:
    """AGENT_MODE=single: deterministic tool plan, then one LLM call (see app/agent/single.py)."""
    client = _get_client()
    question = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    intent = single.intent_of(question)
    used_profile, calls = single.plan_and_run(messages, profile)

    trace: list[dict] = []
    sources: dict = {}
    aids: dict = {}
    coverage_notes: dict = {}
    for tool, args, output in calls:
        shown = {k: v for k, v in args.items() if k != "profile"}
        trace.append({"tool": tool, "input": {**shown, **({"profile": used_profile} if "profile" in args else {})},
                      "ok": "error" not in output})
        _collect(output, sources, aids, coverage_notes)

    convo = [{"role": "system", "content": build_system_prompt(profile)}]
    convo += [dict(m) for m in messages]
    convo.append({"role": "system", "content": single.results_message(intent, used_profile, calls)})
    try:
        msg = client.chat.completions.create(
            model=config.LLM_MODEL, max_tokens=config.LLM_MAX_TOKENS,
            temperature=config.LLM_TEMPERATURE, messages=convo,
        ).choices[0].message
        return _result(msg, trace, sources, aids, coverage_notes)
    except AuthenticationError as e:
        raise LLMError(MSG_BAD_KEY) from e
    except RateLimitError as e:
        raise LLMError(MSG_RATE_LIMIT) from e
    except APIConnectionError as e:
        raise LLMError(MSG_CONNECTION) from e
    except APIStatusError as e:
        log.exception("LLM API error")
        raise LLMError(MSG_GENERIC) from e


def run_loop(messages: list[dict], profile: dict) -> dict:
    client = _get_client()
    convo: list[dict] = [{"role": "system", "content": build_system_prompt(profile)}]
    convo += [dict(m) for m in messages]
    trace: list[dict] = []
    sources: dict = {}
    aids: dict = {}
    coverage_notes: dict = {}
    base = dict(model=config.LLM_MODEL, max_tokens=config.LLM_MAX_TOKENS,
                temperature=config.LLM_TEMPERATURE, tools=TOOLS_OPENAI)

    try:
        for _ in range(config.MAX_AGENT_ITERATIONS):
            msg = _create(client, messages=convo, tool_choice="auto", **base).choices[0].message
            if not msg.tool_calls:
                return _result(msg, trace, sources, aids, coverage_notes)

            convo.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                args, output = _execute_call(tc, profile)
                trace.append({"tool": tc.function.name, "input": args, "ok": "error" not in output})
                _collect(output, sources, aids, coverage_notes)
                convo.append({"role": "tool", "tool_call_id": tc.id,
                              "content": json.dumps(output, ensure_ascii=False, default=str)})

        # Iteration limit reached: force a final answer with no more tool calls
        msg = _create(client, messages=convo, tool_choice="none", **base).choices[0].message
        return _result(msg, trace, sources, aids, coverage_notes)

    except AuthenticationError as e:
        raise LLMError(MSG_BAD_KEY) from e
    except RateLimitError as e:
        raise LLMError(MSG_RATE_LIMIT) from e
    except APIConnectionError as e:
        raise LLMError(MSG_CONNECTION) from e
    except APIStatusError as e:
        log.exception("LLM API error")
        raise LLMError(MSG_GENERIC) from e
