"""Tool registry and safe runner. Tools always return dicts; errors go back as {"error": ...}."""
import logging

from pydantic import ValidationError

from app.models.profile import FarmProfile
from app.tools.alternatives import find_alternatives
from app.tools.application_guide import get_application_guide
from app.tools.check_eligibility import check_eligibility
from app.tools.search_aids import search_aids

log = logging.getLogger("elvecinoquesabe.tools")

TOOLS = {
    "search_aids": search_aids,
    "check_eligibility": check_eligibility,
    "get_application_guide": get_application_guide,
    "find_alternatives": find_alternatives,
}


def run_tool(name: str, args: dict, base_profile: dict) -> dict:
    """Validates the profile proposed by the LLM and merges it with the form one (the form wins)."""
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    # A null argument means "not given": let the tool use its default.
    args = {k: v for k, v in dict(args).items() if v is not None}
    try:
        if "profile" in args:
            from_llm = FarmProfile(**(args.get("profile") or {})).model_dump(exclude_none=True)
            args["profile"] = {**from_llm, **base_profile}
        return fn(**args)
    except ValidationError as e:
        detail = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
        return {"error": f"Invalid profile values: {detail}"}
    except TypeError as e:
        return {"error": f"Invalid parameters: {e}"}
    except Exception as e:  # noqa: BLE001
        log.exception("Tool %s failed", name)
        return {"error": f"Internal tool failure: {type(e).__name__}"}
