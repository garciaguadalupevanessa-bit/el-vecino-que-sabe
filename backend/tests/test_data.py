from app.data.loader import AIDS, BLOCKS


def test_every_aid_has_source_and_date():
    for a in AIDS:
        assert a["source_url"].startswith("http")
        assert a["verified_on"]


def test_verified_aids_have_a_reviewer():
    for a in AIDS:
        if a["reliability"] == "verified":
            assert a["verified_by"]


def test_blocks_are_not_empty():
    assert all(BLOCKS[k] for k in BLOCKS)


def test_aid_model_round_trips_campaign_source_evidence_and_document_versions():
    from copy import deepcopy

    from app.models.aid import Aid

    citation = {
        "source_url": "https://example.gov/rules.pdf", "title": "Official rules",
        "locator": "Page 4, section 2", "quote": "Eligible farms may apply.",
        "payload_sha256": "a" * 64,
    }
    raw = deepcopy(AIDS[0])
    raw["territories"] = [{
        "level": "municipality", "name": "Alcañiz", "code": "44013", "parent_code": "ES242",
    }]
    raw["bdns_calls"] = [{
        "bdns_code": "999020", "campaign_year": 2026, "campaign_label": "2026",
        "status": "verified", "citations": [citation],
        "documents": [{
            "bdns_document_id": 100, "title": "Bases reguladoras", "source_url": "https://example.gov/rules.pdf",
            "content_sha256": "b" * 64,
            "versions": [{"content_sha256": "b" * 64, "retrieved_at": "2026-11-11T10:00:00Z"}],
        }],
        "review_history": [{
            "reviewer": "Reviewer One", "status": "verified", "reviewed_at": "2026-11-11T10:00:00Z",
            "notes": "Checked against the official rules.", "citations": [citation],
        }],
    }]

    aid = Aid(**raw).model_dump(mode="json")
    assert aid["territories"][0]["level"] == "municipality"
    assert aid["bdns_calls"][0]["campaign_year"] == 2026
    assert aid["bdns_calls"][0]["documents"][0]["versions"][0]["content_sha256"] == "b" * 64
    assert aid["bdns_calls"][0]["review_history"][0]["citations"][0]["locator"] == "Page 4, section 2"


def test_verified_evaluable_rule_requires_a_citation():
    from copy import deepcopy

    import pytest
    from pydantic import ValidationError

    from app.models.aid import Aid

    raw = deepcopy(AIDS[0])
    raw.update({"reliability": "verified", "verified_by": "Reviewer One", "requirements": [{
        "description": "Age limit", "field": "holder_age", "operator": "<=", "value": 40,
    }]})
    with pytest.raises(ValidationError, match="official citation"):
        Aid(**raw)
