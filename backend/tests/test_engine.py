from app.tools.requirements_engine import evaluate_requirement


def test_missing_data_is_unknown():
    r = evaluate_requirement({"description": "x", "field": "holder_age", "operator": "<=", "value": 40}, {})
    assert r["status"] == "unknown" and r["missing_field"] == "holder_age"


def test_age_above_limit_is_not_met():
    req = {"description": "x", "field": "holder_age", "operator": "<=", "value": 40}
    assert evaluate_requirement(req, {"holder_age": 41})["status"] == "not_met"
    assert evaluate_requirement(req, {"holder_age": 29})["status"] == "met"


def test_requirement_without_field_is_not_evaluable():
    assert evaluate_requirement({"description": "x", "field": None}, {"holder_age": 30})["status"] == "unknown"


def test_in_operator_with_list():
    req = {"description": "x", "field": "livestock_type", "operator": "in", "value": ["sheep", "goat"]}
    assert evaluate_requirement(req, {"livestock_type": ["sheep"]})["status"] == "met"
    assert evaluate_requirement(req, {"livestock_type": ["pig"]})["status"] == "not_met"


def test_provisional_requirement_is_never_marked_met_or_not_met():
    req = {"description": "x", "field": "holder_age", "operator": "<=", "value": 40,
           "needs_verification": True}
    assert evaluate_requirement(req, {"holder_age": 29})["status"] == "unknown"
    assert evaluate_requirement(req, {"holder_age": 45})["status"] == "unknown"


def test_agricultural_and_mixed_profiles_validate_without_livestock_details():
    from app.models.profile import FarmProfile

    crop_only = FarmProfile(farm_activities=["agriculture"], crop_types=["cereal"], agricultural_area_hectares=18)
    mixed = FarmProfile(farm_activities=["agriculture", "livestock"], crop_types=["olives"],
                        livestock_type=["sheep"], irrigated_hectares=2.5)
    assert crop_only.livestock_type is None and crop_only.agricultural_area_hectares == 18
    assert mixed.farm_activities == ["agriculture", "livestock"]


def test_only_verified_rules_can_return_definitive_eligibility(monkeypatch):
    import importlib

    checker = importlib.import_module("app.tools.check_eligibility")

    aid = {
        "id": "verified-test", "name": "Test aid", "reliability": "verified",
        "source_url": "https://example.gov/aid", "verified_on": "2026-11-11",
        "requirements": [{"description": "Age limit", "field": "holder_age", "operator": "<=", "value": 40,
                           "citation": {"source_url": "https://example.gov/rules", "locator": "Section 2",
                                        "quote": "Applicants must be at most 40 years old."}}],
    }
    monkeypatch.setitem(checker.AIDS_BY_ID, aid["id"], aid)
    monkeypatch.setattr(checker, "BLOCKS", {})

    assert checker.check_eligibility(aid["id"], {"holder_age": 30})["overall_result"] == "met"
    assert checker.check_eligibility(aid["id"], {"holder_age": 45})["overall_result"] == "not_met"
    missing = checker.check_eligibility(aid["id"], {})
    assert missing["overall_result"] == "unknown"
    assert missing["requirements"][0]["status"] == "unknown"

    aid["reliability"] = "extracted"
    provisional = checker.check_eligibility(aid["id"], {"holder_age": 30})
    assert provisional["overall_result"] == "unknown"
    assert provisional["requirements"][0]["status"] == "unknown"


def test_verified_aid_without_rules_stays_unknown(monkeypatch):
    import importlib

    checker = importlib.import_module("app.tools.check_eligibility")

    aid = {"id": "empty-rules", "name": "Test aid", "reliability": "verified",
           "source_url": "https://example.gov/aid", "verified_on": "2026-11-11", "requirements": []}
    monkeypatch.setitem(checker.AIDS_BY_ID, aid["id"], aid)
    monkeypatch.setattr(checker, "BLOCKS", {})
    assert checker.check_eligibility(aid["id"], {})["overall_result"] == "unknown"
