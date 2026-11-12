"""Postgres integration tests. Skipped when TEST_DATABASE_URL is not set.
These tests truncate application and BDNS source tables in the selected database;
use a dedicated disposable test database only.
Locally: TEST_DATABASE_URL=postgresql://.../dedicated_test_db pytest tests/test_db.py"""
import os

import pytest

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Set TEST_DATABASE_URL to run the Postgres tests")

from app.data.sources import load_from_db, load_from_json, read_json  # noqa: E402
from app.db import database as db  # noqa: E402


@pytest.fixture
def empty_db():
    with db.connect(URL) as conn:
        db.create_schema(conn)
        conn.execute(
            """TRUNCATE aid_review_events, aid_bdns_calls, aid_territories,
               bdns_extraction_review_events, bdns_extraction_review_tasks,
               bdns_call_verification_events, bdns_quality_checks, bdns_extractions,
               bdns_import_run_calls, bdns_import_run_queries, bdns_import_runs, bdns_regions,
               bdns_ai_finalization_events, bdns_ai_review_decisions, bdns_ai_review_suggestions,
               bdns_call_classification_events,
               bdns_call_reviews, bdns_links,
               bdns_document_versions, bdns_documents,
               bdns_call_changes, bdns_call_snapshots, bdns_calls, aids, blocks
               RESTART IDENTITY"""
        )
        conn.commit()


def test_seeding_gives_data_equivalent_to_the_json(empty_db):
    from_db = load_from_db(URL, seed=True)
    from_json = load_from_json()
    assert from_db[1] == from_json[1]      # same aids by id
    assert from_db[2] == from_json[2]      # same blocks


def test_without_seeding_an_empty_db_loads_no_data(empty_db):
    aids, _, _ = load_from_db(URL, seed=False)
    assert aids == []


def test_upsert_updates_without_duplicating(empty_db):
    raw, blocks = read_json()
    with db.connect(URL) as conn:
        db.upsert_blocks(conn, blocks)
        db.upsert_aids(conn, raw)
        raw[0]["name"] = "Modified name"
        db.upsert_aids(conn, raw)
        conn.commit()
        stored = db.read_aids(conn)
    assert len(stored) == len(raw)
    assert any(a["name"] == "Modified name" for a in stored)


def test_aid_links_persist_territories_campaign_and_append_only_review(empty_db):
    from app.bdns.change_detection import payload_sha256

    payload = {"codigoBDNS": "999020", "descripcion": "Linked source call"}
    fingerprint = payload_sha256(payload)
    source_call = {
        "source_identity": {"bdns_code": "999020", "bdns_internal_id": 999020,
                            "detail_url": "https://example.gov/call/999020"},
        "source_state": {"payload_sha256": fingerprint}, "source_payload": payload,
        "call": {"title": "Linked source call", "territories": []}, "application": {},
        "sources": {"regulatory_bases": {}, "documents": [], "announcements": []},
        "quality": {"reliability": "metadata_only"},
    }
    aid = {
        "id": "linked-aid", "scope": "national", "reliability": "verified", "name": "Linked aid",
        "territories": [{"level": "province", "name": "Teruel", "code": "ES242", "parent_code": "ES24"}],
        "bdns_calls": [{"bdns_code": "999020", "campaign_year": 2026, "campaign_label": "2026",
                        "status": "verified", "review_history": [{
                            "reviewer": "Reviewer One", "status": "verified",
                            "reviewed_at": "2026-11-11T10:00:00Z", "notes": "Checked against official rules.",
                            "citations": [{"source_url": "https://example.gov/rules", "locator": "Section 2",
                                           "quote": "Farmers may apply."}],
                        }]}],
    }
    with db.connect(URL) as conn:
        db.upsert_bdns_calls(conn, [source_call])
        db.upsert_aids(conn, [aid])
        conn.commit()
        assert conn.execute(
            "SELECT territory_level, territory_name FROM aid_territories WHERE aid_id = 'linked-aid'"
        ).fetchone() == ("province", "Teruel")
        assert conn.execute(
            "SELECT bdns_code, campaign_year, status FROM aid_bdns_calls WHERE aid_id = 'linked-aid'"
        ).fetchone() == ("999020", 2026, "verified")
        assert conn.execute(
            "SELECT reviewer, status FROM aid_review_events WHERE aid_id = 'linked-aid'"
        ).fetchone() == ("Reviewer One", "verified")


def test_bdns_snapshots_changes_and_removed_links_are_idempotent(empty_db):
    from app.bdns.change_detection import payload_sha256

    def source_call(title, bases_url):
        payload = {"codigoBDNS": "999001", "descripcion": title, "urlBasesReguladoras": bases_url}
        fingerprint = payload_sha256(payload)
        return {
            "source_identity": {
                "system": "BDNS", "bdns_code": "999001", "bdns_internal_id": 999001,
                "detail_url": "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/999001",
            },
            "source_state": {"payload_sha256": fingerprint, "snapshot_id": fingerprint},
            "source_payload": payload,
            "application": {"application_portal_url": "https://aragon.example/apply"},
            "call": {"state_aid": {"url": None}},
            "sources": {
                "regulatory_bases": {"url": bases_url}, "documents": [], "announcements": [],
            },
            "quality": {"reliability": "metadata_only"},
        }

    first = source_call("Call title v1", "https://aragon.example/rules-v1")
    with db.connect(URL) as conn:
        db.upsert_bdns_calls(conn, [first])
        conn.commit()
        db.record_bdns_link_check(conn, {
            "bdns_code": "999001", "resource_type": "regulatory_bases",
            "resource_key": "bases", "url": "https://aragon.example/rules-v1",
            "status": "reachable", "status_code": 200, "last_error": None,
        })
        conn.commit()
        db.upsert_bdns_calls(conn, [first])
        conn.commit()
        assert conn.execute(
            "SELECT count(*) FROM bdns_call_snapshots WHERE bdns_code = '999001'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT count(*) FROM bdns_call_changes WHERE bdns_code = '999001'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT review_status FROM bdns_calls WHERE bdns_code = '999001'"
        ).fetchone()[0] == "pending_review"
        assert conn.execute(
            "SELECT status FROM bdns_links WHERE bdns_code = '999001' "
            "AND resource_type = 'regulatory_bases'"
        ).fetchone()[0] == "reachable"

        changed = source_call("Call title v2", "https://aragon.example/rules-v2")
        db.upsert_bdns_calls(conn, [changed])
        conn.commit()
        assert conn.execute(
            "SELECT count(*) FROM bdns_call_snapshots WHERE bdns_code = '999001'"
        ).fetchone()[0] == 2
        event = conn.execute(
            "SELECT event_type, changed_paths FROM bdns_call_changes "
            "WHERE bdns_code = '999001' ORDER BY change_id DESC LIMIT 1"
        ).fetchone()
        assert event[0] == "changed"
        assert "descripcion" in event[1] and "urlBasesReguladoras" in event[1]
        assert conn.execute(
            "SELECT review_status FROM bdns_calls WHERE bdns_code = '999001'"
        ).fetchone()[0] == "review_required"
        links = conn.execute(
            "SELECT url, status, is_current FROM bdns_links "
            "WHERE bdns_code = '999001' AND resource_type = 'regulatory_bases' ORDER BY url"
        ).fetchall()
    assert links == [
        ("https://aragon.example/rules-v1", "removed", False),
        ("https://aragon.example/rules-v2", "unknown", True),
    ]


def test_bdns_review_is_audited_without_promoting_reliability(empty_db):
    from app.bdns.change_detection import payload_sha256

    payload = {"codigoBDNS": "999002", "descripcion": "Test call"}
    fingerprint = payload_sha256(payload)
    record = {
        "source_identity": {"bdns_code": "999002", "bdns_internal_id": 999002,
                            "detail_url": "https://example.gov/call/999002"},
        "source_state": {"payload_sha256": fingerprint},
        "source_payload": payload,
        "call": {"title": "Test call", "territories": [], "farm_activity_classification": {"status": "unclassified"}},
        "application": {},
        "sources": {"regulatory_bases": {}, "documents": [], "announcements": []},
        "quality": {"reliability": "metadata_only"},
    }
    with db.connect(URL) as conn:
        db.upsert_bdns_calls(conn, [record])
        conn.commit()
        decision = db.review_bdns_call(
            conn, "999002", fingerprint, "Reviewer One", "accepted_for_extraction", "Official sources reviewed."
        )
        assert decision == "accepted_for_extraction"
        assert db.review_bdns_call(
            conn, "999002", "0" * 64, "Reviewer One", "out_of_scope", "Stale source."
        ) == "stale"
        state = conn.execute(
            "SELECT reliability, review_status FROM bdns_calls WHERE bdns_code = '999002'"
        ).fetchone()
        history = db.read_bdns_call_reviews(conn, "999002")
        import psycopg

        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute("UPDATE bdns_call_reviews SET notes = 'edited' WHERE bdns_code = '999002'")
        conn.rollback()
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute("DELETE FROM bdns_call_reviews WHERE bdns_code = '999002'")
        conn.rollback()
    assert state == ("metadata_only", "accepted_for_extraction")
    assert len(history) == 1
    assert history[0]["reviewer"] == "Reviewer One"


def test_bdns_import_coverage_reports_queries_indexing_and_unmeasured_dimensions(empty_db):
    from app.bdns.change_detection import payload_sha256

    payload = {"codigoBDNS": "999003", "descripcion": "Coverage test call"}
    fingerprint = payload_sha256(payload)
    record = {
        "source_identity": {"bdns_code": "999003", "bdns_internal_id": 999003,
                            "detail_url": "https://example.gov/call/999003"},
        "source_state": {"payload_sha256": fingerprint},
        "source_payload": payload,
        "call": {
            "title": "Coverage test call", "territories": [{"code": "ES24", "source_label": "ES24 - Aragón"}],
            "farm_activity_classification": {"status": "unclassified", "activities": []},
            "purpose": {"label": "Agriculture"}, "economic_sectors": [],
            "campaign": {"year": None, "label": None},
        },
        "application": {},
        "sources": {"regulatory_bases": {}, "documents": [], "announcements": []},
        "quality": {"reliability": "metadata_only"},
    }
    with db.connect(URL) as conn:
        db.upsert_bdns_regions(conn, [{
            "region_id": 21, "description": "ES24 - Aragón", "nuts_code": "ES24",
            "parent_region_id": None, "depth": 0,
        }])
        run_id = db.start_bdns_import_run(conn, (21,), ("agricultura",), 1, 10)
        db.upsert_bdns_calls(conn, [record])
        conn.commit()
        db.finish_bdns_import_run(
            conn, run_id, status="completed", candidate_count=1, indexed_call_count=1,
            observations=[{
                "region_id": 21, "search_term": "agricultura", "activity_scope": "agriculture",
                "candidate_count": 1, "indexed_call_count": 1, "page_limit_reached": False,
            }],
        )
        report = db.read_bdns_coverage(conn)
    assert report["indexed_call_count"] == 1
    assert report["last_import_run"]["queries"][0]["territory"] == "ES24 - Aragón"
    assert report["territories"][0]["status"] == "indexed_in_bounded_query"
    assert report["gaps"]["unclassified_farm_activity_calls"] == 1
    assert report["gaps"]["unclassified_campaign_calls"] == 1
    assert report["gaps"]["controlled_aid_category_mapping"] == "not_implemented"


def test_extraction_review_tasks_are_versioned_and_never_verify_sources(empty_db):
    from app.bdns.change_detection import payload_sha256

    first_payload = {"codigoBDNS": "999004", "descripcion": "First call version"}
    first_hash = payload_sha256(first_payload)
    record = {
        "source_identity": {"bdns_code": "999004", "bdns_internal_id": 999004,
                            "detail_url": "https://example.gov/call/999004"},
        "source_state": {"payload_sha256": first_hash}, "source_payload": first_payload,
        "call": {"title": "Review test call"}, "application": {},
        "sources": {"regulatory_bases": {}, "documents": [], "announcements": []},
        "quality": {"reliability": "metadata_only"},
    }
    with db.connect(URL) as conn:
        db.upsert_bdns_calls(conn, [record])
        conn.commit()
        assert db.review_bdns_call(conn, "999004", first_hash, "Reviewer One",
                                   "accepted_for_extraction", "Ready for extraction.") == "accepted_for_extraction"
        missing = conn.execute(
            "SELECT task_id, status FROM bdns_extraction_review_tasks WHERE bdns_code = '999004' AND issue_key = 'missing_extraction'"
        ).fetchone()
        assert missing[1] == "open"
        extraction_fingerprint = "c" * 64
        db.record_bdns_extraction(conn, "999004", extraction_fingerprint, {
            "source_payload_sha256": first_hash,
            "field_status": {"purpose": "found", "requirements": "not_found"},
            "facts": {
                "purpose": [
                    {"value": "Crop grant", "citation": {"url": "https://example.gov/doc", "page": 1}},
                    {"value": "Farm investment", "citation": {"url": "https://example.gov/doc", "page": 2}},
                ],
                "requirements": [],
            },
        })
        tasks = conn.execute(
            "SELECT issue_key, status FROM bdns_extraction_review_tasks WHERE bdns_code = '999004' ORDER BY issue_key"
        ).fetchall()
        assert ("missing_extraction", "stale") in tasks
        assert ("ambiguous_data:purpose", "open") in tasks
        assert ("missing_data:requirements", "open") in tasks
        task_id = conn.execute(
            "SELECT task_id FROM bdns_extraction_review_tasks WHERE bdns_code = '999004' AND issue_key = 'ambiguous_data:purpose'"
        ).fetchone()[0]
        assert db.review_bdns_extraction_task(
            conn, task_id, first_hash, extraction_fingerprint, "Reviewer One",
            "reviewed_candidate", "Compared both excerpts with the official PDF.",
        ) == "reviewed_candidate"
        assert conn.execute("SELECT reliability FROM bdns_calls WHERE bdns_code = '999004'").fetchone()[0] == "metadata_only"
        assert conn.execute("SELECT reliability FROM bdns_extractions WHERE bdns_code = '999004'").fetchone()[0] == "extracted"
        changed_payload = {"codigoBDNS": "999004", "descripcion": "Changed call version"}
        changed_record = {**record, "source_payload": changed_payload,
                          "source_state": {"payload_sha256": payload_sha256(changed_payload),
                                           "snapshot_id": payload_sha256(changed_payload)}}
        db.upsert_bdns_calls(conn, [changed_record])
        conn.commit()
        source_task = conn.execute(
            "SELECT status, details->>'previous_payload_sha256', details->>'current_payload_sha256' "
            "FROM bdns_extraction_review_tasks WHERE bdns_code = '999004' AND issue_key = 'source_changed'"
        ).fetchone()
        assert source_task == ("open", first_hash, payload_sha256(changed_payload))


def test_bdns_verification_requires_current_evidence_and_reopens_on_document_change(empty_db):
    from app.bdns.change_detection import payload_sha256

    code = "999005"
    doc_url = "https://www.infosubvenciones.es/bdnstrans/api/convocatorias/documentos?idDocumento=1999005"
    payload = {"codigoBDNS": code, "descripcion": "Verification test call"}
    fingerprint = payload_sha256(payload)
    record = {
        "source_identity": {
            "bdns_code": code, "bdns_internal_id": 999005,
            "detail_url": f"https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/{code}",
        },
        "source_state": {"payload_sha256": fingerprint, "snapshot_id": fingerprint},
        "source_payload": payload,
        "call": {"title": "Verification test call"}, "application": {},
        "sources": {"regulatory_bases": {}, "documents": [{
            "bdns_document_id": 1999005, "download_url": doc_url, "filename": "rules.pdf",
        }], "announcements": []},
        "quality": {"reliability": "metadata_only", "reviewed_by": None,
                    "reviewed_at": None, "review_notes": None},
    }
    with db.connect(URL) as conn:
        db.upsert_bdns_calls(conn, [record])
        conn.commit()
        assert db.review_bdns_call(
            conn, code, fingerprint, "Reviewer One", "accepted_for_extraction", "Call checked."
        ) == "accepted_for_extraction"
        db.record_bdns_document(conn, {
            "bdns_code": code, "bdns_document_id": 1999005,
            "source_metadata": record["sources"]["documents"][0], "status": "downloaded",
            "content_type": "application/pdf", "content_sha256": "d" * 64,
            "stored_object_uri": "test/1999005/d.pdf", "downloaded_size_bytes": 100,
        })
        conn.commit()
        assert db.verify_bdns_call(
            conn, code, fingerprint, "", "Reviewer One", "checked source", [{
                "statement": "A rule checked against the official source document.",
                "source_url": doc_url, "page": 1,
            }]
        ) == "not_ready"
        db.record_bdns_extraction(conn, code, "e" * 64, {
            "source_payload_sha256": fingerprint,
            "documents_processed": [{"document_id": 1999005, "content_sha256": "d" * 64}],
            "facts": {}, "field_status": {},
        })
        db.record_bdns_quality_check(conn, code, fingerprint, {
            "bdns_code": code, "overall_status": "passed", "findings": [],
        })
        state = db.read_bdns_verification_state(conn, code)
        assert state["eligible_to_verify"] is True
        approved_rules = [{
            "statement": "The reviewer-approved rule from the official call document.",
            "source_url": doc_url, "page": 1, "section": "Eligibility",
        }]
        assert db.verify_bdns_call(
            conn, code, "0" * 64, "e" * 64, "Reviewer One", "checked source", approved_rules
        ) == "stale"
        assert db.verify_bdns_call(
            conn, code, fingerprint, "e" * 64, "Reviewer One", "checked source",
            [{**approved_rules[0], "source_url": "https://unrelated.example/rules.pdf"}],
        ) == "invalid_citation"
        assert db.verify_bdns_call(
            conn, code, fingerprint, "e" * 64, "Reviewer One",
            "Compared the official call and its source document.", approved_rules,
        ) == "verified"
        assert conn.execute(
            "SELECT reliability, data #>> '{quality,reviewed_by}' FROM bdns_calls WHERE bdns_code = %s",
            (code,),
        ).fetchone() == ("verified", "Reviewer One")

        repeated = {**record, "quality": {"reliability": "metadata_only"}}
        db.upsert_bdns_calls(conn, [repeated])
        conn.commit()
        assert conn.execute(
            "SELECT reliability FROM bdns_calls WHERE bdns_code = %s", (code,)
        ).fetchone()[0] == "verified"

        db.record_bdns_document(conn, {
            "bdns_code": code, "bdns_document_id": 1999005,
            "source_metadata": record["sources"]["documents"][0], "status": "downloaded",
            "content_type": "application/pdf", "content_sha256": "f" * 64,
            "stored_object_uri": "test/1999005/f.pdf", "downloaded_size_bytes": 101,
        })
        conn.commit()
        assert conn.execute(
            "SELECT reliability, data #>> '{quality,reliability}' FROM bdns_calls WHERE bdns_code = %s",
            (code,),
        ).fetchone() == ("metadata_only", "metadata_only")
        assert conn.execute(
            "SELECT event_type FROM bdns_call_verification_events WHERE bdns_code = %s "
            "ORDER BY verification_event_id DESC LIMIT 1", (code,),
        ).fetchone()[0] == "reopened"
        assert conn.execute(
            "SELECT status FROM bdns_extraction_review_tasks WHERE bdns_code = %s "
                "AND issue_key LIKE 'verification_reopened:%%'", (code,),
        ).fetchone()[0] == "open"
        import psycopg

        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute(
                "UPDATE bdns_call_verification_events SET notes = 'edited' WHERE bdns_code = %s",
                (code,),
            )
        conn.rollback()
