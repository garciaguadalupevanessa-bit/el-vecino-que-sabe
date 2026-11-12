"""Repeatable quality checks for imported BDNS calls and extraction artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pypdf import PdfReader

from app.bdns.change_detection import extract_source_links, payload_sha256
from app.bdns.extraction import EXTRACTOR_VERSION
from app.bdns.link_checker import OfficialLinkChecker, check_and_record_links
from app.core import config
from app.db import database as db


MAX_PDF_PAGES = 300
MAX_URL_FIELDS = 100
MAX_DOCUMENTS = 25
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
NUTS_PATTERN = re.compile(r"^\s*([A-Z]{2}\d{2})\s*[-–]")


def _url_values(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            is_url_field = (
                key.lower().startswith("url") or key.lower().endswith("_url")
                or key.lower() == "detail_url"
            )
            if is_url_field and child is not None and child != "":
                found.append((path, child.strip() if isinstance(child, str) else child))
            else:
                found.extend(_url_values(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_url_values(child, f"{prefix}[{index}]"))
    return found


def _source_fields(record: dict[str, Any], add) -> dict[str, Any]:
    identity = record.get("source_identity")
    source_state = record.get("source_state")
    call = record.get("call")
    application = record.get("application")
    sources = record.get("sources")
    quality = record.get("quality")
    required = {
        "schema_version": record.get("schema_version"),
        "source_identity.system": identity.get("system") if isinstance(identity, dict) else None,
        "source_identity.bdns_code": identity.get("bdns_code") if isinstance(identity, dict) else None,
        "source_identity.detail_url": identity.get("detail_url") if isinstance(identity, dict) else None,
        "source_state.retrieved_at": source_state.get("retrieved_at") if isinstance(source_state, dict) else None,
        "source_state.payload_sha256": source_state.get("payload_sha256") if isinstance(source_state, dict) else None,
        "source_state.snapshot_id": source_state.get("snapshot_id") if isinstance(source_state, dict) else None,
        "call.title": call.get("title") if isinstance(call, dict) else None,
        "call.territories": call.get("territories") if isinstance(call, dict) else None,
        "application": application,
        "sources": sources,
        "quality.reliability": quality.get("reliability") if isinstance(quality, dict) else None,
        "source_payload": record.get("source_payload"),
    }
    for path, value in required.items():
        missing = value is None or value == "" or (
            path.endswith(".territories") and not isinstance(value, list)
        )
        if missing:
            add("required_fields", "error", "required_field_missing", f"Required field is missing or has the wrong type: {path}.", {"field": path})
    for path, value in (("source_identity", identity), ("source_state", source_state),
                        ("call", call), ("application", application),
                        ("sources", sources), ("quality", quality)):
        if value is not None and not isinstance(value, dict):
            add("required_fields", "error", "invalid_group_shape", f"{path} must be an object.", {"field": path})
    if isinstance(sources, dict) and not isinstance(sources.get("documents", []), list):
        add("required_fields", "error", "invalid_documents_shape", "sources.documents must be an array.", {"field": "sources.documents"})
    for path in ("source_state.payload_sha256", "source_state.snapshot_id"):
        value = required[path]
        if value is not None and (not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value)):
            add("required_fields", "error", "invalid_hash_format", f"{path} must be a lowercase SHA-256 hex digest.", {"field": path})
    title = required["call.title"]
    if title is not None and not isinstance(title, str):
        add("required_fields", "error", "invalid_title_type", "Call title must be text.", {"field": "call.title"})
    if not isinstance(identity, dict) or identity.get("system") != "BDNS":
        add("required_fields", "error", "invalid_source_system", "Source system must be BDNS.")
    if quality is not None and (
        not isinstance(quality, dict)
        or quality.get("reliability") not in {"metadata_only", "extracted", "verified"}
    ):
        add("required_fields", "error", "invalid_reliability", "Reliability value is not supported.")
    return {"required_fields": list(required)}


def _check_dates(record: dict[str, Any], add) -> dict[str, Any]:
    call = record.get("call") if isinstance(record.get("call"), dict) else {}
    application = record.get("application") if isinstance(record.get("application"), dict) else {}
    values = {
        "call.received_date": call.get("received_date"),
        "application.start_date": application.get("start_date"),
        "application.end_date": application.get("end_date"),
    }
    parsed: dict[str, date] = {}
    for path, value in values.items():
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            add("dates", "error", "invalid_date_type", f"{path} must be an ISO date string.", {"field": path})
            continue
        try:
            parsed[path] = date.fromisoformat(value)
        except ValueError:
            add("dates", "error", "invalid_date", f"{path} is not a valid ISO date.", {"field": path, "value": value})
    start = parsed.get("application.start_date")
    end = parsed.get("application.end_date")
    if start and end and end < start:
        add("dates", "error", "date_order_conflict", "Application end date is earlier than its start date.", {
            "start_date": start.isoformat(), "end_date": end.isoformat(),
        })
    source_state = record.get("source_state") if isinstance(record.get("source_state"), dict) else {}
    retrieved_at = source_state.get("retrieved_at")
    if retrieved_at:
        try:
            if not isinstance(retrieved_at, str):
                raise ValueError
            datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        except ValueError:
            add("dates", "error", "invalid_retrieved_at", "source_state.retrieved_at is not a valid ISO datetime.", {"field": "source_state.retrieved_at"})
    return {"parsed_fields": sorted(parsed)}


def _check_territories(record: dict[str, Any], known: list[dict], add) -> dict[str, Any]:
    call = record.get("call") if isinstance(record.get("call"), dict) else {}
    territories = call.get("territories")
    if not isinstance(territories, list):
        return {"checked": 0, "known_catalog_codes": len(known)}
    known_codes = {item.get("nuts_code", "").upper() for item in known if item.get("nuts_code")}
    checked = 0
    if not territories:
        add("territories", "warning", "territory_unspecified", "BDNS record has no explicit territory; scope remains unknown.")
    elif not known_codes:
        add("territories", "warning", "territory_catalog_unavailable", "The official BDNS territory catalog is empty; territory codes cannot be cross-checked.")
    for index, item in enumerate(territories):
        if not isinstance(item, dict):
            add("territories", "error", "invalid_territory_shape", f"Territory at index {index} is not an object.")
            continue
        checked += 1
        label = item.get("source_label")
        code = item.get("code")
        label_match = NUTS_PATTERN.match(label) if isinstance(label, str) else None
        label_code = label_match.group(1) if label_match else None
        if code and label_code and str(code).upper() != label_code:
            add("territories", "error", "territory_label_code_conflict", f"Territory code disagrees with its source label at index {index}.", {
                "code": code, "label_code": label_code, "source_label": label,
            })
        normalized_code = str(code).upper() if code else None
        if not normalized_code and label_code:
            add("territories", "warning", "territory_code_missing", f"A territory code could be read from the source label but is absent in the mapped record at index {index}.", {"label_code": label_code})
        elif not normalized_code:
            add("territories", "warning", "territory_code_missing", f"Territory at index {index} has no normalized code for catalog consistency checking.", {"territory_index": index})
        elif normalized_code and known_codes and normalized_code not in known_codes:
            add("territories", "warning", "territory_not_in_current_catalog", f"Territory code is absent from the currently stored official BDNS region catalog: {normalized_code}.", {"territory_index": index})
    return {"checked": checked, "known_catalog_codes": len(known_codes)}


def _check_urls(record: dict[str, Any], link_results: list[dict], add) -> dict[str, Any]:
    url_record = {
        "source_identity": record.get("source_identity"),
        "call": {"state_aid": (record.get("call") or {}).get("state_aid")}
                if isinstance(record.get("call"), dict) else {},
        "application": record.get("application"),
        "sources": record.get("sources"),
    }
    raw_urls = _url_values(url_record)
    if len(raw_urls) > MAX_URL_FIELDS:
        add("urls", "warning", "url_check_bound_reached", f"Only the first {MAX_URL_FIELDS} URL fields are inspected.")
        raw_urls = raw_urls[:MAX_URL_FIELDS]
    invalid = []
    for path, url in raw_urls:
        try:
            if not isinstance(url, str):
                raise ValueError("URL must be text.")
            parsed = urlsplit(url)
            valid = parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname) and not parsed.username and not parsed.password
            if parsed.port and parsed.port not in {80, 443}:
                valid = False
        except ValueError:
            valid = False
        if not valid:
            invalid.append({"field": path})
            add("urls", "error", "invalid_url", f"Source URL is malformed or uses a disallowed scheme: {path}.", {"field": path})

    try:
        expected = extract_source_links(record)
    except (AttributeError, TypeError, ValueError):
        expected = []
        add("urls", "error", "invalid_source_shape", "Source URL groups have an invalid shape and cannot be checked.")
    current_results = {
        (item.get("resource_type"), item.get("resource_key"), item.get("url")): item
        for item in link_results
    }
    counts = {"reachable": 0, "broken": 0, "unknown": 0, "not_checked": 0}
    url_statuses = []
    for link in expected:
        key = (link["resource_type"], link["resource_key"], link["url"])
        result = current_results.get(key)
        status = result.get("status") if result else "not_checked"
        counts[status if status in counts else "unknown"] += 1
        url_statuses.append({
            "resource_type": link["resource_type"], "resource_key": link["resource_key"],
            "url": link["url"], "status": status,
            "status_code": result.get("status_code") if result else None,
            "last_error": result.get("last_error") if result else None,
        })
        if status == "broken":
            add("urls", "error", "url_unreachable", f"Official source returned a definitive broken-link response: {link['resource_type']}/{link['resource_key']}.", {"url": link["url"], "status_code": result.get("status_code")})
        elif status in {"unknown", "not_checked"}:
            add("urls", "warning", "url_reachability_unknown", f"Reachability is not confirmed for {link['resource_type']}/{link['resource_key']}.", {
                "url": link["url"], "status": status,
                "status_code": result.get("status_code") if result else None,
                "last_error": result.get("last_error") if result else None,
            })
    return {"source_url_fields": len(raw_urls), "invalid": invalid, **counts, "links": url_statuses}


def _check_documents(
    record: dict[str, Any], inventory: list[dict], storage_root: str | Path,
    max_documents: int, add,
) -> dict[str, Any]:
    root = Path(storage_root).expanduser().resolve()
    sources = record.get("sources") if isinstance(record.get("sources"), dict) else {}
    listed = sources.get("documents", [])
    listed = listed if isinstance(listed, list) else []
    inventory_by_id = {item.get("document_id"): item for item in inventory}
    checked = []
    for source in listed[:max_documents]:
        if not isinstance(source, dict):
            add("pdfs", "error", "invalid_document_metadata", "A listed source document is not an object.")
            continue
        document_id = source.get("bdns_document_id")
        if isinstance(document_id, bool) or not isinstance(document_id, int):
            add("pdfs", "warning", "document_id_missing", "A source document has no numeric BDNS document ID.")
            continue
        current = inventory_by_id.get(document_id)
        result = {"document_id": document_id, "status": "not_downloaded", "page_count": 0, "text_pages": 0}
        if current is None:
            add("pdfs", "warning", "document_not_downloaded", f"BDNS document {document_id} has not been downloaded into the local store.")
            checked.append(result)
            continue
        result["status"] = current["status"]
        if current["status"] != "downloaded":
            add("pdfs", "warning", "document_unavailable", f"BDNS document {document_id} is recorded as {current['status']}.", {"document_id": document_id})
            checked.append(result)
            continue
        try:
            path = (root / current["stored_object_uri"]).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Stored document path escaped its storage root.")
            content = path.read_bytes()
        except (OSError, ValueError, TypeError) as exc:
            result["status"] = "storage_error"
            add("pdfs", "error", "document_storage_error", f"Cannot safely read BDNS document {document_id} from storage.", {"document_id": document_id, "error": str(exc)[:250]})
            checked.append(result)
            continue
        digest = hashlib.sha256(content).hexdigest()
        result["actual_sha256"] = digest
        if digest != current.get("content_sha256"):
            result["status"] = "hash_mismatch"
            add("pdfs", "error", "document_hash_mismatch", f"Stored BDNS document {document_id} does not match its recorded content hash.", {"document_id": document_id, "expected_sha256": current.get("content_sha256"), "actual_sha256": digest})
            checked.append(result)
            continue
        if current.get("size_bytes") is not None and len(content) != current["size_bytes"]:
            add("pdfs", "error", "document_size_mismatch", f"Stored BDNS document {document_id} does not match its recorded size.", {"document_id": document_id})
        if not content.startswith(b"%PDF-"):
            result["status"] = "invalid_pdf_signature"
            add("pdfs", "error", "invalid_pdf_signature", f"Stored BDNS document {document_id} lacks a PDF signature.", {"document_id": document_id})
            checked.append(result)
            continue
        try:
            from io import BytesIO

            reader = PdfReader(BytesIO(content), strict=False)
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError("PDF is encrypted and has no empty-password access.")
            page_count = len(reader.pages)
            result["page_count"] = page_count
            if page_count == 0:
                raise ValueError("PDF has no pages.")
            text_pages = 0
            for page in reader.pages[:MAX_PDF_PAGES]:
                try:
                    if (page.extract_text() or "").strip():
                        text_pages += 1
                except Exception:
                    continue
            result["text_pages"] = text_pages
            result["status"] = "text_readable" if text_pages else "no_text"
            if not text_pages:
                add("pdfs", "warning", "pdf_has_no_text", f"BDNS document {document_id} parses as a PDF but no embedded text was extracted.", {"document_id": document_id, "page_count": page_count})
            if page_count > MAX_PDF_PAGES:
                add("pdfs", "warning", "pdf_page_limit_reached", f"Only the first {MAX_PDF_PAGES} pages of BDNS document {document_id} were checked.", {"document_id": document_id, "page_count": page_count})
            if not current.get("version_recorded"):
                add("version_hash", "warning", "document_version_missing", f"No immutable document-version row matches the current hash for document {document_id}.", {"document_id": document_id})
        except Exception as exc:
            result["status"] = "unreadable_pdf"
            add("pdfs", "error", "pdf_unreadable", f"BDNS document {document_id} cannot be parsed as a readable PDF.", {"document_id": document_id, "error": str(exc)[:250]})
        checked.append(result)
    if len(listed) > max_documents:
        add("pdfs", "warning", "document_check_bound_reached", f"Only {max_documents} of {len(listed)} listed PDFs were checked.")
    return {"listed": len(listed), "checked": checked}


def _check_versions(record: dict[str, Any], context: dict[str, Any], inventory: list[dict], add) -> dict[str, Any]:
    source_state = record.get("source_state") if isinstance(record.get("source_state"), dict) else {}
    payload_hash = source_state.get("payload_sha256")
    payload = record.get("source_payload")
    try:
        computed_hash = payload_sha256(payload) if isinstance(payload, dict) else None
    except (TypeError, ValueError):
        computed_hash = None
    database_hash = context.get("database_payload_sha256")
    snapshot_exists = context.get("snapshot_exists", False)
    hash_matches = bool(payload_hash and payload_hash == computed_hash == database_hash)
    if not hash_matches:
        add("version_hash", "error", "call_hash_mismatch", "The canonical call payload, BDNS call row and its stored hash do not agree.", {
            "record_sha256": payload_hash, "computed_sha256": computed_hash, "database_sha256": database_hash,
        })
    if payload_hash and not snapshot_exists:
        add("version_hash", "error", "current_snapshot_missing", "No immutable call snapshot matches the current BDNS payload hash.", {"payload_sha256": payload_hash})
    latest_change = context.get("latest_change")
    if latest_change and latest_change.get("event_type") == "changed":
        add("version_hash", "warning", "source_changed", "The latest import detected a source change; prior extracted facts may need review.", {
            "current_sha256": latest_change.get("current_sha256"),
            "changed_paths": latest_change.get("changed_paths", []),
            "detected_at": latest_change.get("detected_at"),
        })
    extraction = context.get("latest_extraction")
    extraction_status = "not_run"
    if extraction:
        data = extraction.get("data", {})
        current_docs = sorted(
            (item.get("document_id"), item.get("content_sha256"))
            for item in inventory if item.get("status") == "downloaded" and item.get("content_sha256")
        )
        extracted_docs = sorted(
            (item.get("document_id"), item.get("content_sha256"))
            for item in data.get("documents_processed", [])
        )
        extraction_stale = (
            data.get("source_payload_sha256") != payload_hash
            or current_docs != extracted_docs
            or data.get("extractor_version") != EXTRACTOR_VERSION
        )
        extraction_status = "stale" if extraction_stale else "current"
        if extraction_stale:
            add("version_hash", "warning", "extraction_stale", "The latest stored extraction does not match the current call, document hashes or extractor version.", {
                "extraction_fingerprint": extraction.get("source_fingerprint"),
                "extraction_version": data.get("extractor_version"),
                "current_extractor_version": EXTRACTOR_VERSION,
            })
    return {
        "record_sha256": payload_hash,
        "computed_sha256": computed_hash,
        "database_sha256": database_hash,
        "hashes_match": hash_matches,
        "current_snapshot_exists": snapshot_exists,
        "latest_change": latest_change,
        "latest_extraction_status": extraction_status,
    }


def evaluate_call_quality(
    record: dict[str, Any], context: dict[str, Any], link_results: list[dict],
    storage_root: str | Path, *, max_documents: int = MAX_DOCUMENTS,
) -> dict[str, Any]:
    """Assess one current call without changing source reliability or review state."""
    if max_documents < 1:
        raise ValueError("max_documents must be positive.")
    findings: list[dict[str, Any]] = []

    def add(check: str, severity: str, code: str, message: str, details: dict | None = None) -> None:
        finding = {"check": check, "severity": severity, "code": code, "message": message}
        if details:
            finding["details"] = details
        findings.append(finding)

    _source_fields(record, add)
    date_summary = _check_dates(record, add)
    territory_summary = _check_territories(
        record, context.get("known_territories", []), add
    )
    url_summary = _check_urls(record, link_results, add)
    inventory = context.get("documents", [])
    document_summary = _check_documents(
        record, inventory, storage_root, max_documents, add
    )
    version_summary = _check_versions(record, context, inventory, add)

    check_names = ("required_fields", "dates", "territories", "urls", "pdfs", "version_hash")
    checks = {}
    for name in check_names:
        relevant = [finding for finding in findings if finding["check"] == name]
        checks[name] = {
            "status": "failed" if any(item["severity"] == "error" for item in relevant)
                      else "warning" if relevant else "passed",
            "finding_count": len(relevant),
        }
    if any(item["severity"] == "error" for item in findings):
        overall_status = "failed"
    elif findings:
        overall_status = "warning"
    else:
        overall_status = "passed"
    return {
        "schema_version": "1.0",
        "bdns_code": record.get("source_identity", {}).get("bdns_code"),
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload_sha256": record.get("source_state", {}).get("payload_sha256"),
        "overall_status": overall_status,
        "checks": checks,
        "summaries": {
            "dates": date_summary,
            "territories": territory_summary,
            "urls": url_summary,
            "pdfs": document_summary,
            "version_hash": version_summary,
        },
        "findings": findings,
        "interpretation": "Quality checks flag source and extraction issues; a passed result is not source verification or an eligibility decision.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded quality checks for one imported BDNS call.")
    parser.add_argument("--bdns-code", required=True, help="BDNS call code already in the source index.")
    parser.add_argument("--max-links", type=int, default=10, help="Maximum official links checked per run.")
    parser.add_argument("--max-documents", type=int, default=MAX_DOCUMENTS, help="Maximum PDFs inspected per run.")
    parser.add_argument("--url", default=config.DATABASE_URL, help="Database URL (defaults to DATABASE_URL).")
    args = parser.parse_args(argv)
    try:
        if not args.url:
            raise ValueError("DATABASE_URL is missing.")
        if not args.bdns_code.strip():
            raise ValueError("bdns-code cannot be empty.")
        if args.max_links < 1 or args.max_links > 100:
            raise ValueError("max-links must be between 1 and 100.")
        if args.max_documents < 1 or args.max_documents > MAX_DOCUMENTS:
            raise ValueError(f"max-documents must be between 1 and {MAX_DOCUMENTS}.")
        with OfficialLinkChecker(
            minimum_request_interval=config.BDNS_LINK_CHECK_INTERVAL_SECONDS
        ) as checker, db.connect(args.url) as conn:
            db.create_schema(conn)
            records = db.read_bdns_calls(conn, args.bdns_code.strip())
            if not records:
                raise ValueError(f"BDNS call {args.bdns_code!r} was not found.")
            links = db.read_bdns_links(conn, args.bdns_code.strip(), limit=args.max_links)
            link_results = check_and_record_links(checker, conn, links) if links else []
            context = db.read_bdns_quality_context(conn, args.bdns_code.strip())
            report = evaluate_call_quality(
                records[0], context, link_results, config.BDNS_DOCUMENT_STORAGE_DIR,
                max_documents=args.max_documents,
            )
            check_id = db.record_bdns_quality_check(
                conn, args.bdns_code.strip(), report.get("payload_sha256"), report
            )
        counts = {severity: sum(item["severity"] == severity for item in report["findings"])
                  for severity in ("error", "warning")}
        print(
            f"Quality check {check_id} for BDNS {args.bdns_code.strip()}: "
            f"{report['overall_status']} ({counts['error']} errors, {counts['warning']} warnings)."
        )
        print(json.dumps({"checks": report["checks"], "summaries": report["summaries"],
                          "findings": report["findings"]}, ensure_ascii=False, indent=2))
        return 1 if report["overall_status"] == "failed" else 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"BDNS quality check failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
