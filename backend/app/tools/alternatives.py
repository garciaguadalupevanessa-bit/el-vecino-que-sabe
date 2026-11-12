from app.data.loader import AIDS_BY_ID, BLOCKS
from app.tools.check_eligibility import check_eligibility
from app.tools.requirements_engine import evaluate_requirement, expand_requirements
from app.tools.search_aids import search_aids, summary


def find_alternatives(profile: dict, aid_id: str | None = None, max_results: int = 3) -> dict:
    max_results = max(1, min(int(max_results), 5))
    excluded: set[str] = set()
    to_become_eligible: list[dict] = []
    candidate_ids: list[str] = []
    text = ""

    if aid_id:
        aid = AIDS_BY_ID.get(aid_id)
        if not aid:
            return {"error": f"Aid '{aid_id}' not found. Use an id returned by search_aids."}
        excluded.add(aid_id)
        if aid["reliability"] == "verified":
            for r in expand_requirements(aid, BLOCKS):
                ev = evaluate_requirement(r, profile)
                if ev["status"] == "not_met":
                    to_become_eligible.append({"requirement": ev["description"], "current_situation": ev["reason"]})
        candidate_ids = [i for i in aid["alternatives"] if i in AIDS_BY_ID]
        text = aid["name"]

    # Fill in with related aids found by search
    for r in search_aids(profile, free_text=text, max_results=10)["results"]:
        if r["id"] not in candidate_ids:
            candidate_ids.append(r["id"])

    alternatives = []
    for i in candidate_ids:
        if i in excluded:
            continue
        ev = check_eligibility(i, profile)
        alternatives.append({**summary(AIDS_BY_ID[i]), "overall_result": ev["overall_result"],
                             "missing_fields": ev["missing_fields"]})
        if len(alternatives) >= max_results:
            break

    return {
        "alternatives": alternatives,
        "to_become_eligible": to_become_eligible,
        "note": None if alternatives else "No alternatives found in the aid base.",
    }
