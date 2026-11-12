from app.tools import run_tool


def test_search_finds_national_aids_with_all():
    out = run_tool("search_aids", {"profile": {"region": "Aragón", "livestock_type": ["sheep"]}}, {})
    ids = {r["id"] for r in out["results"]}
    assert "cap_basic_income_support" in ids


def test_location_matching_supports_national_region_province_and_municipality(monkeypatch):
    import importlib

    search_module = importlib.import_module("app.tools.search_aids")
    base = {
        "agency": "Test agency", "aid_type": "other", "short_description": "Test",
        "farm_activities": ["all"], "livestock_type": ["all"], "production_system": ["all"],
        "goals": [], "requirements": [], "how_to_apply": [], "documents": [], "deadline": None,
        "open": None, "alternatives": [], "reliability": "verified", "source_url": "https://example.gov/aid",
        "verified_on": "2026-11-11", "verified_by": "Reviewer", "status": "active",
    }
    monkeypatch.setattr(search_module, "AIDS", [
        {**base, "id": "national", "name": "National", "scope": "national"},
        {**base, "id": "region", "name": "Region", "scope": "regional", "territories": [
            {"level": "autonomous_community", "name": "Aragón", "code": "ES24"}]},
        {**base, "id": "province", "name": "Province", "scope": "territorial", "territories": [
            {"level": "province", "name": "Teruel", "code": "ES242", "parent_code": "ES24"}]},
        {**base, "id": "municipality", "name": "Municipality", "scope": "territorial", "territories": [
            {"level": "municipality", "name": "Alcañiz", "code": "44013", "parent_code": "ES242"}]},
    ])

    all_ids = {item["id"] for item in search_module.search_aids(
        {"region": "Aragon", "province": "TERUEL", "municipality": "Alcañiz"}
    )["results"]}
    assert all_ids == {"national", "region", "province", "municipality"}
    province_ids = {item["id"] for item in search_module.search_aids({"province": "Teruel"})["results"]}
    assert province_ids == {"national", "province"}
    municipality_ids = {item["id"] for item in search_module.search_aids({"municipality": "ALCAÑIZ"})["results"]}
    assert municipality_ids == {"national", "municipality"}


def test_mixed_profile_keeps_both_farm_activities():
    from app.models.profile import FarmProfile

    profile = FarmProfile(farm_activities=["agriculture", "livestock"], crop_types=["olives"], livestock_type=["sheep"])
    assert set(profile.farm_activities) == {"agriculture", "livestock"}


def test_crop_livestock_and_mixed_profiles_match_relevant_aid_activities(monkeypatch):
    import importlib

    search_module = importlib.import_module("app.tools.search_aids")
    base = {
        "agency": "Test agency", "scope": "national", "aid_type": "other", "short_description": "Test",
        "livestock_type": ["all"], "production_system": ["all"], "goals": [], "requirements": [],
        "how_to_apply": [], "documents": [], "deadline": None, "open": None, "alternatives": [],
        "reliability": "verified", "source_url": "https://example.gov/aid", "verified_on": "2026-11-11",
        "verified_by": "Reviewer",
    }
    monkeypatch.setattr(search_module, "AIDS", [
        {**base, "id": "crops", "name": "Crops", "farm_activities": ["agriculture"]},
        {**base, "id": "livestock", "name": "Livestock", "farm_activities": ["livestock"]},
        {**base, "id": "general", "name": "General", "farm_activities": ["all"]},
    ])

    def ids(profile):
        return {item["id"] for item in search_module.search_aids(profile)["results"]}

    assert ids({"farm_activities": ["agriculture"], "crop_types": ["cereal"]}) == {"crops", "general"}
    assert ids({"farm_activities": ["livestock"], "livestock_type": ["sheep"]}) == {"livestock", "general"}
    assert ids({"farm_activities": ["agriculture", "livestock"], "crop_types": ["olives"],
                "livestock_type": ["sheep"]}) == {"crops", "livestock", "general"}


def test_crop_only_profile_finds_national_aids_without_livestock_fields():
    out = run_tool("search_aids", {"profile": {"farm_activities": ["agriculture"],
                                                "crop_types": ["cereal"],
                                                "agricultural_area_hectares": 24}}, {})
    ids = {r["id"] for r in out["results"]}
    assert "cap_basic_income_support" in ids


def test_search_without_location_warns():
    out = run_tool("search_aids", {"profile": {"livestock_type": ["sheep"]}}, {})
    assert "national" in out["note"]


def test_open_search_excludes_verified_calls_with_expired_iso_deadlines(monkeypatch):
    import importlib
    from datetime import date

    search_module = importlib.import_module("app.tools.search_aids")
    template = {
        "agency": "Test agency", "scope": "national", "aid_type": "other",
        "short_description": "Test", "farm_activities": ["all"], "livestock_type": ["all"],
        "production_system": ["all"], "goals": [], "requirements": [], "how_to_apply": [],
        "documents": [], "open": True, "alternatives": [], "reliability": "verified",
        "source_url": "https://example.gov/aid", "verified_on": date.today().isoformat(),
        "verified_by": "Reviewer", "status": "active",
    }
    monkeypatch.setattr(search_module, "AIDS", [
        {**template, "id": "expired", "name": "Expired", "deadline": "2020-01-01"},
        {**template, "id": "current", "name": "Current", "deadline": "2999-01-01"},
        {**template, "id": "unknown", "name": "Unknown", "deadline": None},
    ])

    results = search_module.search_aids({}, only_open=True)["results"]
    assert {item["id"] for item in results} == {"current", "unknown"}


def test_check_eligibility_unknown_id():
    out = run_tool("check_eligibility", {"aid_id": "does_not_exist", "profile": {}}, {})
    assert "error" in out


def test_check_eligibility_is_unknown_when_data_is_missing():
    out = run_tool("check_eligibility", {"aid_id": "cap_basic_income_support", "profile": {}}, {})
    assert out["overall_result"] == "unknown"
    assert out["missing_fields"] == []


def test_extracted_aid_with_unverified_requirement_is_unknown():
    out = run_tool("check_eligibility", {"aid_id": "cap_basic_income_support", "profile": {
        "active_farmer": True, "conditionality_compliant": True,
    }}, {})
    assert out["overall_result"] == "unknown"
    assert any(r["needs_verification"] and r["status"] == "unknown" for r in out["requirements"])


def test_metadata_only_aid_does_not_claim_requirement_results():
    out = run_tool("check_eligibility", {"aid_id": "cap_complementary_redistributive_support", "profile": {
        "active_farmer": False, "conditionality_compliant": False,
    }}, {})
    assert out["overall_result"] == "unknown"
    assert out["requirements"]
    assert all(r["status"] == "unknown" for r in out["requirements"])
    assert out["missing_fields"] == []


def test_metadata_only_search_result_shows_identity_and_source_only():
    out = run_tool("search_aids", {"profile": {"region": "Aragón"}}, {})
    result = next(r for r in out["results"] if r["id"] == "cap_complementary_redistributive_support")
    assert result["reliability"] == "metadata_only" and result["source_url"].startswith("https://")
    assert "deadline" not in result and "short_description" not in result and "open" not in result


def test_form_profile_wins_over_llm_profile():
    base_profile = {"active_farmer": False}
    out = run_tool("check_eligibility",
                   {"aid_id": "cap_basic_income_support", "profile": {"active_farmer": True}}, base_profile)
    assert out["overall_result"] == "unknown"
    active_farmer = next(r for r in out["requirements"] if r["description"].startswith("Ser agricultor activo"))
    assert active_farmer["status"] == "unknown"
    assert active_farmer["missing_field"] is None


def test_invalid_profile_value_returns_error():
    out = run_tool("search_aids", {"profile": {"production_system": "martian"}}, {})
    assert "error" in out


def test_unknown_tool():
    assert "error" in run_tool("hack", {}, {})


def test_guide_flags_incomplete_documents():
    out = run_tool("get_application_guide", {"aid_id": "cap_basic_income_support"}, {})
    assert out["incomplete_data"] is True and out["documents"] == []


def test_unverified_guide_withholds_provisional_steps_and_deadlines():
    out = run_tool("get_application_guide", {"aid_id": "cap_basic_income_support"}, {})
    assert out["guide_available"] is False
    assert out["deadline"] is None and out["how_to_apply"] == [] and out["documents"] == []
    assert out["source_url"].startswith("https://")


def test_alternatives_do_not_infer_changes_from_unverified_rules():
    out = run_tool("find_alternatives", {"profile": {"active_farmer": False},
                                         "aid_id": "cap_basic_income_support"}, {})
    assert out["to_become_eligible"] == []


def test_alternatives_exclude_the_original_aid():
    out = run_tool("find_alternatives", {"profile": {"region": "Aragón"}, "aid_id": "cap_basic_income_support"}, {})
    assert all(a["id"] != "cap_basic_income_support" for a in out["alternatives"])


def test_reliability_labels_are_ready_to_show_in_spanish():
    from app.tools.labels import reliability_label_es
    assert "no revisada por una persona" in reliability_label_es(
        {"reliability": "verified", "verification_method": "agent", "verified_on": "2026-11-12"})
    assert "12/11/2026" in reliability_label_es({"reliability": "verified", "verified_on": "2026-11-12"})
    assert "metadata" not in reliability_label_es({"reliability": "metadata_only", "verified_on": "2026-11-06"})


def test_not_met_aid_tells_the_agent_not_to_recommend_applying():
    from app.tools.check_eligibility import check_eligibility
    r = check_eligibility("cap_coupled_sheep_goat_meat",
                          {"livestock_type": ["sheep"], "head_count": 20, "active_farmer": True})
    assert r["overall_result"] == "not_met"
    assert "No recomiendes solicitarla" in r["recommendation_es"]
    assert "automáticamente" in r["reliability_label_es"]
