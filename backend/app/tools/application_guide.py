from app.data.loader import AIDS_BY_ID
from app.tools.labels import reliability_label_es

PLACEHOLDER = "TO_BE_COMPLETED"  # marks documents the team has not filled in yet


def get_application_guide(aid_id: str) -> dict:
    aid = AIDS_BY_ID.get(aid_id)
    if not aid:
        return {"error": f"Aid '{aid_id}' not found. Use an id returned by search_aids."}
    incomplete = any(PLACEHOLDER in d for d in aid["documents"]) or not (aid.get("how_to_apply") or aid.get("documents"))
    verified = aid["reliability"] == "verified"
    campaigns = list(dict.fromkeys(
        str(item.get("campaign_label") or item.get("campaign_year"))
        for item in aid.get("bdns_calls", [])
        if item.get("campaign_label") or item.get("campaign_year")
    ))
    territories = [item.get("name") for item in aid.get("territories", []) if item.get("name")]
    source_documents = [
        {"title": document["title"], "source_url": str(document["source_url"])}
        for source in aid.get("bdns_calls", []) if source.get("status") == "verified"
        for document in source.get("documents", [])
    ] if verified else []
    if not verified:
        return {
            "aid_id": aid["id"], "name": aid["name"], "agency": aid["agency"],
            "deadline": None, "how_to_apply": [], "documents": [],
            "source_documents": [], "campaigns": campaigns, "territories": territories,
            "incomplete_data": True, "guide_available": False,
            "note": "Application details have not been verified against the official rules.",
            "reliability": aid["reliability"], "reliability_label_es": reliability_label_es(aid),
            "source_url": aid["source_url"],
            "verification_method": aid.get("verification_method", "human"),
            "verified_on": aid["verified_on"],
            "last_checked_on": aid["verified_on"],
            "status": aid.get("status", "unknown"),
        }
    return {
        "aid_id": aid["id"],
        "name": aid["name"],
        "agency": aid["agency"],
        "deadline": aid["deadline"],
        "how_to_apply": aid["how_to_apply"],
        "documents": [] if incomplete else aid["documents"],
        "source_documents": source_documents,
        "campaigns": campaigns,
        "territories": territories,
        "incomplete_data": incomplete,
        "guide_available": not incomplete,
        "reliability": aid["reliability"],
        "reliability_label_es": reliability_label_es(aid),
        "verification_method": aid.get("verification_method", "human"),
        "source_url": aid["source_url"],
        "verified_on": aid["verified_on"],
        "last_checked_on": aid["verified_on"],
        "status": aid.get("status", "unknown"),
    }
