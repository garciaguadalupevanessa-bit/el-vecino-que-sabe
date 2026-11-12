from fastapi.testclient import TestClient

from app.core import config
from app.main import app


client = TestClient(app)
TOKEN = "test-review-token"
PAYLOAD_HASH = "a" * 64


def test_review_api_is_disabled_without_a_configured_token(monkeypatch):
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", "")
    response = client.get("/api/admin/bdns/review")
    assert response.status_code == 404


def test_review_api_requires_the_bearer_token(monkeypatch):
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    assert client.get("/api/admin/bdns/review").status_code == 401
    assert client.get(
        "/api/admin/bdns/review", headers={"Authorization": "Bearer wrong"}
    ).status_code == 401


def test_authorized_reviewer_can_list_the_queue(monkeypatch):
    from app.main import db

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    item = {"bdns_code": "920758", "review_status": "pending_review"}
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(db, "connect", lambda url: Connection())
    monkeypatch.setattr(db, "read_bdns_review_queue", lambda conn, status, limit, offset: [item])
    monkeypatch.setattr(db, "count_bdns_review_queue", lambda conn, status: 1)
    response = client.get(
        "/api/admin/bdns/review?limit=20&offset=0",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 200
    assert response.json() == {"items": [item], "count": 1, "total": 1, "limit": 20, "offset": 0}


def test_review_decision_is_not_a_verification_and_stale_source_returns_conflict(monkeypatch):
    from app.main import db

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(db, "connect", lambda url: Connection())
    request = {
        "expected_payload_sha256": PAYLOAD_HASH,
        "reviewer": "Reviewer One",
        "decision": "accepted_for_extraction",
        "notes": "Reviewed the BDNS record and source links.",
    }
    monkeypatch.setattr(db, "review_bdns_call", lambda *args, **kwargs: "accepted_for_extraction")
    accepted = client.post(
        "/api/admin/bdns/review/920758", json=request,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["reliability"] == "metadata_only"
    assert accepted.json()["review_status"] == "accepted_for_extraction"

    monkeypatch.setattr(db, "review_bdns_call", lambda *args, **kwargs: "stale")
    stale = client.post(
        "/api/admin/bdns/review/920758", json=request,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert stale.status_code == 409


def test_review_decision_requires_a_reviewer_and_reason(monkeypatch):
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    for reviewer, notes in [("  ", "source reviewed"), ("Reviewer", "  ")]:
        response = client.post(
            "/api/admin/bdns/review/920758",
            json={"expected_payload_sha256": PAYLOAD_HASH, "reviewer": reviewer,
                  "decision": "out_of_scope", "notes": notes},
            headers=headers,
        )
        assert response.status_code == 422


def test_bdns_source_record_is_not_exposed_as_a_public_aid():
    assert client.get("/api/aids/920758").status_code == 404


def test_coverage_report_requires_reviewer_access_and_returns_index_gaps(monkeypatch):
    from app.main import db

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    report = {"indexed_call_count": 11, "gaps": {"unclassified_farm_activity_calls": 11}}
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(db, "connect", lambda url: Connection())
    monkeypatch.setattr(db, "read_bdns_coverage", lambda conn, run_limit: report)
    assert client.get("/api/admin/bdns/coverage").status_code == 401
    response = client.get(
        "/api/admin/bdns/coverage?run_limit=10",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 200
    assert response.json() == report


def test_extraction_endpoint_is_protected_and_returns_latest_candidates(monkeypatch):
    from app.main import db

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    extraction = {"bdns_code": "920758", "reliability": "extracted", "facts": {}}
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(db, "connect", lambda url: Connection())
    monkeypatch.setattr(db, "read_latest_bdns_extraction", lambda conn, code: extraction)
    assert client.get("/api/admin/bdns/extractions/920758").status_code == 401
    response = client.get(
        "/api/admin/bdns/extractions/920758", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert response.status_code == 200
    assert response.json() == extraction


def test_quality_check_endpoint_is_protected_and_returns_latest_report(monkeypatch):
    from app.main import db

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    report = {"bdns_code": "923754", "overall_status": "warning", "findings": []}
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(db, "connect", lambda url: Connection())
    monkeypatch.setattr(db, "read_latest_bdns_quality_check", lambda conn, code: report)
    assert client.get("/api/admin/bdns/quality/923754").status_code == 401
    response = client.get(
        "/api/admin/bdns/quality/923754", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert response.status_code == 200
    assert response.json() == report


def test_extraction_review_queue_is_protected_and_lists_tasks(monkeypatch):
    from app.main import db

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): return False

    item = {"task_id": 3, "bdns_code": "923754", "issue_type": "ambiguous_data"}
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(db, "connect", lambda url: Connection())
    monkeypatch.setattr(db, "read_bdns_extraction_review_queue", lambda *args, **kwargs: [item])
    monkeypatch.setattr(db, "count_bdns_extraction_review_queue", lambda *args, **kwargs: 1)
    assert client.get("/api/admin/bdns/extraction-review").status_code == 401
    response = client.get("/api/admin/bdns/extraction-review?status=open", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json()["items"] == [item]


def test_extraction_review_keeps_candidates_unverified_and_rejects_stale(monkeypatch):
    from app.main import db

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): return False

    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(db, "connect", lambda url: Connection())
    headers = {"Authorization": f"Bearer {TOKEN}"}
    request = {"expected_payload_sha256": PAYLOAD_HASH, "expected_extraction_fingerprint": "b" * 64,
               "reviewer": "Reviewer One", "decision": "reviewed_candidate", "notes": "Compared with the call PDF."}
    monkeypatch.setattr(db, "review_bdns_extraction_task", lambda *args, **kwargs: "reviewed_candidate")
    accepted = client.post("/api/admin/bdns/extraction-review/7", json=request, headers=headers)
    assert accepted.status_code == 200
    assert accepted.json()["reliability"] == "extracted"
    monkeypatch.setattr(db, "review_bdns_extraction_task", lambda *args, **kwargs: "stale")
    stale = client.post("/api/admin/bdns/extraction-review/7", json=request, headers=headers)
    assert stale.status_code == 409


def test_extraction_review_requires_reviewer_and_notes(monkeypatch):
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    response = client.post("/api/admin/bdns/extraction-review/7", headers={"Authorization": f"Bearer {TOKEN}"}, json={
        "expected_payload_sha256": PAYLOAD_HASH, "expected_extraction_fingerprint": "",
        "reviewer": " ", "decision": "needs_correction", "notes": " "
    })
    assert response.status_code == 422


def test_bdns_verification_state_and_promotion_are_protected_and_gated(monkeypatch):
    from app.main import db

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): return False

    state = {"bdns_code": "923754", "eligible_to_verify": True, "reliability": "metadata_only"}
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(db, "connect", lambda url: Connection())
    monkeypatch.setattr(db, "read_bdns_verification_state", lambda *args: state)
    assert client.get("/api/admin/bdns/verification/923754").status_code == 401
    response = client.get(
        "/api/admin/bdns/verification/923754",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 200
    assert response.json()["eligible_to_verify"] is True

    request = {
        "expected_payload_sha256": PAYLOAD_HASH,
        "expected_extraction_fingerprint": "b" * 64,
        "reviewer": "Reviewer One",
        "notes": "Compared the source document and current rules.",
        "approved_rules": [{
            "statement": "Approved rule copied from the official call document.",
            "source_url": "https://www.infosubvenciones.es/bdnstrans/api/convocatorias/documentos?idDocumento=1512984",
            "page": 7,
        }],
    }
    monkeypatch.setattr(db, "verify_bdns_call", lambda *args: "verified")
    promoted = client.post(
        "/api/admin/bdns/verification/923754", json=request,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["reliability"] == "verified"

    monkeypatch.setattr(db, "verify_bdns_call", lambda *args: "not_ready")
    blocked = client.post(
        "/api/admin/bdns/verification/923754", json=request,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert blocked.status_code == 409


def test_bdns_verification_requires_approved_rules_and_a_citation_locator(monkeypatch):
    monkeypatch.setattr(config, "BDNS_REVIEW_TOKEN", TOKEN)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    request = {
        "expected_payload_sha256": PAYLOAD_HASH,
        "expected_extraction_fingerprint": "b" * 64,
        "reviewer": "Reviewer One", "notes": "Source checked.", "approved_rules": [{
            "statement": "A rule without a source locator.",
            "source_url": "https://example.org/call",
        }],
    }
    response = client.post("/api/admin/bdns/verification/923754", headers=headers, json=request)
    assert response.status_code == 422
