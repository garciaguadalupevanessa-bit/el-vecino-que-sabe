import re
import unicodedata
from datetime import date

from app.data.loader import AIDS
from app.tools.labels import reliability_label_es


def _as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _matches(aid_values: list, profile_values: list) -> bool:
    """'all' matches any value; if the user did not give the data, the aid is not discarded."""
    if "all" in aid_values or not profile_values:
        return True
    return bool(set(aid_values) & set(profile_values))


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w{4,}", text.lower()))


def _normalize_location(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in value if not unicodedata.combining(char)).strip().casefold()


def _territory_matches(aid: dict, profile: dict) -> bool:
    territories = aid.get("territories") or []
    if not territories:
        scope = _normalize_location(aid.get("scope"))
        region = _normalize_location(profile.get("region"))
        return scope == "national" or (bool(region) and scope == region)

    profile_locations = {
        "autonomous_community": profile.get("region"),
        "province": profile.get("province"),
        "municipality": profile.get("municipality"),
    }
    for territory in territories:
        level = territory.get("level")
        if level == "national":
            return True
        candidate = _normalize_location(profile_locations.get(level))
        if candidate and candidate in {
            _normalize_location(territory.get("name")),
            _normalize_location(territory.get("code")),
        }:
            return True
    return False


def _deadline_has_expired(aid: dict, today: date | None = None) -> bool:
    """Return true only when a verified aid has an explicit, parseable past deadline."""
    if aid.get("reliability") != "verified" or not aid.get("deadline"):
        return False
    try:
        deadline = date.fromisoformat(str(aid["deadline"]))
    except ValueError:
        return False
    return deadline < (today or date.today())


def score(aid: dict, profile: dict, free_text: str = "") -> float:
    points = 1.0
    if profile.get("goal") and profile["goal"] in aid["goals"]:
        points += 2
    system = _as_list(profile.get("production_system"))
    if system and "all" not in aid["production_system"] and set(aid["production_system"]) & set(system):
        points += 1
    livestock = _as_list(profile.get("livestock_type"))
    if livestock and "all" not in aid["livestock_type"] and set(aid["livestock_type"]) & set(livestock):
        points += 1
    if free_text:
        points += len(_tokens(free_text) & _tokens(f'{aid["name"]} {aid["short_description"]}'))
    return points


def summary(aid: dict, fit: float | None = None) -> dict:
    reliability = aid["reliability"]
    source_is_verified = reliability == "verified"
    bdns_sources = [
        {
            "bdns_code": source["bdns_code"],
            "campaign_year": source.get("campaign_year"),
            "campaign_label": source.get("campaign_label"),
            "status": source.get("status", "discovered"),
            "documents": [
                {"title": document["title"], "source_url": str(document["source_url"])}
                for document in source.get("documents", [])
            ] if source_is_verified and source.get("status") == "verified" else [],
            "citations": source.get("citations", []) if source_is_verified else [],
        }
        for source in aid.get("bdns_calls", [])
    ]
    out = {
        "id": aid["id"], "name": aid["name"], "agency": aid["agency"], "scope": aid["scope"],
        "reliability": reliability,
        "reliability_label_es": reliability_label_es(aid),
        "verification_method": aid.get("verification_method", "human"),
        "source_url": aid["source_url"], "verified_on": aid["verified_on"],
        "last_checked_on": aid["verified_on"],
        "status": aid.get("status", "unknown"),
        "territories": aid.get("territories", []),
        "bdns_calls": bdns_sources,
        "campaigns": list(dict.fromkeys(
            str(item.get("campaign_label") or item.get("campaign_year"))
            for item in bdns_sources if item.get("campaign_label") or item.get("campaign_year")
        )),
    }
    if source_is_verified:
        out.update({
            "aid_type": aid["aid_type"], "short_description": aid["short_description"],
            "deadline": aid["deadline"], "open": aid["open"],
        })
    if fit is not None:
        out["preliminary_fit"] = round(fit, 1)
    return out


def search_aids(profile: dict, free_text: str = "", only_open: bool = False, max_results: int = 6) -> dict:
    max_results = max(1, min(int(max_results), 10))
    has_location = any(profile.get(key) for key in ("region", "province", "municipality"))

    candidates = []
    for aid in AIDS:
        if not _territory_matches(aid, profile):
            continue
        if only_open and (
            aid["open"] is False or aid.get("status") in {"closed", "withdrawn"}
            or _deadline_has_expired(aid)
        ):
            continue
        if not _matches(aid["livestock_type"], _as_list(profile.get("livestock_type"))):
            continue
        if not _matches(aid.get("farm_activities", ["all"]), _as_list(profile.get("farm_activities"))):
            continue
        candidates.append((score(aid, profile, free_text), aid))
    candidates.sort(key=lambda x: x[0], reverse=True)

    out = {"results": [summary(a, s) for s, a in candidates[:max_results]], "total_candidates": len(candidates)}
    territory_label = ", ".join(
        str(profile[key]).strip() for key in ("municipality", "province", "region") if profile.get(key)
    ) or "Ámbito nacional"
    out["coverage_territory"] = territory_label
    if not has_location:
        out["note"] = "No location given: only national aids were searched."
    if candidates:
        out["coverage_note"] = (
            f"Se muestran coincidencias del catálogo disponible para {territory_label}; "
            "esto no confirma que se haya recogido toda la oferta de ayudas de ese territorio."
        )
    if not candidates:
        out["note"] = "No matches in the aid base."
        missing = []
        if not has_location:
            missing.append("no se indicó ubicación y la búsqueda se limitó a ayudas nacionales")
        if not profile.get("farm_activities"):
            missing.append("no se indicó si la explotación es agrícola, ganadera o mixta")
        detail = f" Contexto: {'; '.join(missing)}." if missing else ""
        out["coverage_note"] = (
            f"No se encontraron coincidencias en el catálogo para {territory_label}. Esto no confirma que no existan ayudas; "
            "la cobertura del catálogo puede ser incompleta."
            + detail
        )
    return out
