import hashlib

from app.bdns.change_detection import payload_sha256
from app.bdns.quality import evaluate_call_quality


def make_record():
    payload = {"codigoBDNS": "123", "fechaRecepcion": "2026-01-01"}
    digest = payload_sha256(payload)
    return {
        "schema_version": "1.0",
        "source_identity": {
            "system": "BDNS", "bdns_code": "123",
            "detail_url": "https://bdns.example/call/123",
        },
        "source_state": {
            "retrieved_at": "2026-01-01T00:00:00Z",
            "payload_sha256": digest, "snapshot_id": digest,
        },
        "call": {
            "title": "Subvención agrícola",
            "received_date": "2026-01-01",
            "territories": [{"source_label": "ES24 - ARAGÓN", "code": "ES24"}],
        },
        "application": {
            "application_portal_url": "https://region.example/apply",
            "start_date": "2026-02-01", "end_date": "2026-03-01",
        },
        "sources": {"regulatory_bases": {}, "announcements": [], "documents": []},
        "quality": {"reliability": "metadata_only"},
        "source_payload": payload,
    }


def make_context(record):
    digest = record["source_state"]["payload_sha256"]
    return {
        "database_payload_sha256": digest,
        "snapshot_exists": True,
        "latest_change": {"event_type": "discovered", "current_sha256": digest,
                          "changed_paths": [], "detected_at": "2026-01-01T00:00:00+00:00"},
        "documents": [],
        "links": [],
        "known_territories": [{"nuts_code": "ES24", "description": "Aragón"}],
        "latest_extraction": None,
    }


def test_valid_record_passes_dates_territory_and_version_hash_checks(tmp_path):
    record = make_record()
    links = [
        {"resource_type": "call_detail", "resource_key": "123",
         "url": "https://bdns.example/call/123", "status": "reachable"},
        {"resource_type": "application_portal", "resource_key": "application",
         "url": "https://region.example/apply", "status": "reachable"},
    ]

    report = evaluate_call_quality(record, make_context(record), links, tmp_path)

    assert report["overall_status"] == "passed"
    assert report["checks"]["dates"]["status"] == "passed"
    assert report["checks"]["territories"]["status"] == "passed"
    assert report["checks"]["version_hash"]["status"] == "passed"


def test_invalid_date_territory_and_payload_hash_are_reported(tmp_path):
    record = make_record()
    record["application"]["start_date"] = "not-a-date"
    record["application"]["end_date"] = "2026-01-01"
    record["call"]["territories"][0]["code"] = "ES25"
    record["call"]["title"] = None
    record["source_payload"]["codigoBDNS"] = "changed"
    links = [
        {"resource_type": "call_detail", "resource_key": "123",
         "url": "https://bdns.example/call/123", "status": "reachable"},
        {"resource_type": "application_portal", "resource_key": "application",
         "url": "https://region.example/apply", "status": "broken", "status_code": 404},
    ]

    report = evaluate_call_quality(record, make_context(record), links, tmp_path)
    codes = {item["code"] for item in report["findings"]}

    assert report["overall_status"] == "failed"
    assert "invalid_date" in codes
    assert "territory_label_code_conflict" in codes
    assert "call_hash_mismatch" in codes
    assert "url_unreachable" in codes
    assert "required_field_missing" in codes


def test_missing_link_check_is_reported_as_unknown_not_passed(tmp_path):
    record = make_record()
    report = evaluate_call_quality(record, make_context(record), [], tmp_path)

    assert report["summaries"]["urls"]["not_checked"] == 2
    assert report["checks"]["urls"]["status"] == "warning"
    assert report["overall_status"] == "warning"


def test_stored_pdf_hash_mismatch_is_a_quality_error(tmp_path):
    content = b"%PDF-1.7 fake content"
    (tmp_path / "stored.pdf").write_bytes(content)
    record = make_record()
    record["sources"]["documents"] = [{
        "bdns_document_id": 7, "download_url": "https://bdns.example/doc/7",
    }]
    context = make_context(record)
    context["documents"] = [{
        "document_id": 7, "status": "downloaded", "content_sha256": "0" * 64,
        "stored_object_uri": "stored.pdf", "size_bytes": len(content), "version_recorded": True,
    }]

    report = evaluate_call_quality(record, context, [], tmp_path)

    assert report["checks"]["pdfs"]["status"] == "failed"
    assert any(item["code"] == "document_hash_mismatch" for item in report["findings"])


def test_no_text_pdf_is_warning_and_source_reliability_is_not_promoted(tmp_path, monkeypatch):
    import app.bdns.quality as quality

    content = b"%PDF-1.7 valid fixture"
    digest = hashlib.sha256(content).hexdigest()
    (tmp_path / "stored.pdf").write_bytes(content)

    class Page:
        def extract_text(self):
            return ""

    class Reader:
        is_encrypted = False
        pages = [Page(), Page()]

    monkeypatch.setattr(quality, "PdfReader", lambda *args, **kwargs: Reader())
    record = make_record()
    record["sources"]["documents"] = [{"bdns_document_id": 7}]
    context = make_context(record)
    context["documents"] = [{
        "document_id": 7, "status": "downloaded", "content_sha256": digest,
        "stored_object_uri": "stored.pdf", "size_bytes": len(content), "version_recorded": True,
    }]

    report = evaluate_call_quality(record, context, [], tmp_path)

    assert report["summaries"]["pdfs"]["checked"][0]["status"] == "no_text"
    assert report["checks"]["pdfs"]["status"] == "warning"
    assert record["quality"]["reliability"] == "metadata_only"


def test_changed_source_and_old_extraction_are_reported_as_warnings(tmp_path):
    record = make_record()
    context = make_context(record)
    context["latest_change"] = {
        "event_type": "changed", "current_sha256": record["source_state"]["payload_sha256"],
        "changed_paths": ["fechaFinSolicitud"], "detected_at": "2026-02-01T00:00:00+00:00",
    }
    context["latest_extraction"] = {
        "source_fingerprint": "a" * 64,
        "data": {
            "source_payload_sha256": record["source_state"]["payload_sha256"],
            "extractor_version": "0.9", "documents_processed": [],
        },
    }
    links = [
        {"resource_type": "call_detail", "resource_key": "123",
         "url": "https://bdns.example/call/123", "status": "reachable"},
        {"resource_type": "application_portal", "resource_key": "application",
         "url": "https://region.example/apply", "status": "reachable"},
    ]

    report = evaluate_call_quality(record, context, links, tmp_path)
    codes = {item["code"] for item in report["findings"]}

    assert report["overall_status"] == "warning"
    assert report["summaries"]["version_hash"]["latest_extraction_status"] == "stale"
    assert "source_changed" in codes
    assert "extraction_stale" in codes
