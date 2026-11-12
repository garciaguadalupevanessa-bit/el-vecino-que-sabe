from app.data.loader import AIDS_BY_ID, BLOCKS
from app.tools.requirements_engine import evaluate_requirement, expand_requirements


def check_eligibility(aid_id: str, profile: dict) -> dict:
    aid = AIDS_BY_ID.get(aid_id)
    if not aid:
        return {"error": f"Aid '{aid_id}' not found. Use an id returned by search_aids."}

    expanded = expand_requirements(aid, BLOCKS)
    if aid["reliability"] != "verified":
        reqs = [{
            "description": r.get("description"),
            "missing_field": None,
            "needs_verification": True,
            "status": "unknown",
            "explanation_es": (
                "La ficha solo contiene datos básicos; sus requisitos no se han comprobado."
                if aid["reliability"] == "metadata_only"
                else "Los requisitos extraídos aún no se han aprobado contra la fuente oficial."
            ),
            "reason": (
                "This aid has metadata only; its requirements have not been checked."
                if aid["reliability"] == "metadata_only"
                else "These extracted requirements have not been approved against the official source."
            ),
        } for r in expanded]
        overall = "unknown"
    else:
        reqs = [evaluate_requirement(r, profile) for r in expanded]
        statuses = {r["status"] for r in reqs}
        if "not_met" in statuses:
            overall = "not_met"
        elif not statuses or "unknown" in statuses:
            overall = "unknown"
        else:
            overall = "met"

    return {
        "aid_id": aid_id,
        "name": aid["name"],
        "overall_result": overall,
        "eligibility_status": overall,
        "requirements": reqs,
        "missing_fields": sorted({r["missing_field"] for r in reqs if r["missing_field"]}),
        "reliability": aid["reliability"],
        "verification_method": aid.get("verification_method", "human"),
        "source_url": aid["source_url"],
        "verified_on": aid["verified_on"],
        "last_checked_on": aid["verified_on"],
    }
