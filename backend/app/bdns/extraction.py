"""Conservative, local extraction of aid facts from BDNS metadata and stored PDFs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from app.core import config
from app.db import database as db


EXTRACTOR_VERSION = "1.1"
MAX_PDF_PAGES = 300
MAX_FACTS_PER_FIELD = 30
MAX_QUOTE_LENGTH = 1200

FIELD_PATTERNS = {
    "purpose": re.compile(r"\b(objeto|finalidad|prop[oó]sito|actuaci[oó]n subvencionable)\b", re.I),
    "beneficiaries": re.compile(r"\b(personas beneficiarias|beneficiarios|beneficiarias|destinatarios)\b", re.I),
    "requirements": re.compile(r"\b(requisitos|condiciones|obligaciones|compromisos|criterios de elegibilidad)\b", re.I),
    "deadlines": re.compile(r"\b(plazo|plazos|fecha l[ií]mite|presentaci[oó]n de solicitudes|solicitud(?:es) hasta)\b", re.I),
    "documents": re.compile(r"\b(documentaci[oó]n|documentos que|documentos a presentar|junto con la solicitud|acompañar)\b", re.I),
    "application_route": re.compile(r"\b(presentaci[oó]n de solicitudes|sede electr[oó]nica|tramitaci[oó]n electr[oó]nica|presentar la solicitud|registro electr[oó]nico)\b", re.I),
}


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n.;")
    return value or None


def _fact(
    value: Any,
    source_url: str | None,
    *,
    source_type: str = "bdns_metadata",
    page: int | None = None,
    section: str | None = None,
    quote: str | None = None,
    **extra: Any,
) -> dict | None:
    cleaned = _clean(value)
    if not cleaned or not _is_citable_url(source_url) or (page is None and not section):
        return None
    citation = {
        "url": source_url,
        "page": page,
        "section": section,
        "quote": _clean(quote) if quote else cleaned,
    }
    return {"value": cleaned, "source_type": source_type, "citation": citation, **extra}


def _is_citable_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    from urllib.parse import urlsplit

    try:
        parsed = urlsplit(value.strip())
        return parsed.scheme.lower() in ("http", "https") and bool(parsed.hostname)
    except ValueError:
        return False


def _metadata_facts(record: dict[str, Any]) -> dict[str, list[dict]]:
    call = record.get("call", {})
    application = record.get("application", {})
    sources = record.get("sources", {})
    detail_url = record.get("source_identity", {}).get("detail_url")
    facts: dict[str, list[dict]] = {field: [] for field in FIELD_PATTERNS}

    purpose = call.get("purpose") or {}
    purpose_fact = _fact(
        purpose.get("label"), detail_url, section="call.purpose.label"
    )
    if purpose_fact:
        facts["purpose"].append(purpose_fact)
    for index, value in enumerate(call.get("objectives", [])):
        if isinstance(value, dict):
            value = value.get("descripcion") or value.get("description") or value.get("label")
        item = _fact(value, detail_url, section=f"call.objectives[{index}]")
        if item:
            facts["purpose"].append(item)
    for index, item in enumerate(call.get("beneficiary_categories", [])):
        value = item.get("label") if isinstance(item, dict) else item
        fact = _fact(value, detail_url, section=f"call.beneficiary_categories[{index}]")
        if fact:
            facts["beneficiaries"].append(fact)

    for key in ("start_date", "end_date", "start_text", "end_text", "open_ended"):
        value = application.get(key)
        if value is not None and value != "":
            fact = _fact(str(value), detail_url, section=f"application.{key}")
            if fact:
                facts["deadlines"].append(fact)

    for document in sources.get("documents", []):
        if isinstance(document, dict):
            label = document.get("description") or document.get("filename")
            url = document.get("download_url")
            parts = [str(value) for value in (label, url) if value]
            document_id = document.get("bdns_document_id")
            item = _fact(
                " — ".join(parts), detail_url,
                section=f"sources.documents[{document_id}]",
                document_id=document_id,
            )
            if item:
                facts["documents"].append(item)

    route = application.get("application_portal_url")
    if route:
        item = _fact(route, detail_url, section="application.application_portal_url")
        if item:
            facts["application_route"].append(item)

    return facts


def _extract_pdf_pages(
    content: bytes, document_id: int, source_url: str
) -> tuple[list[dict], str | None]:
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    return [], "encrypted_pdf"
            except Exception:
                return [], "encrypted_pdf"
        pages: list[dict] = []
        for page_number, page in enumerate(reader.pages[:MAX_PDF_PAGES], start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                continue
            text = re.sub(r"[ \t]+", " ", text)
            paragraphs = [re.sub(r"\s+", " ", chunk).strip() for chunk in re.split(r"\n\s*\n|\r", text)]
            # PDFs often use one line per visual row; join wrapped lines before matching.
            if len(paragraphs) > 1:
                paragraphs = [re.sub(r"\s+", " ", text).strip()]
            for paragraph in paragraphs:
                if paragraph:
                    pages.append({
                        "document_id": document_id,
                        "source_url": source_url,
                        "page": page_number,
                        "text": paragraph,
                    })
        return pages, None
    except Exception:
        return [], "unreadable_pdf"


def _pdf_facts(pages: list[dict]) -> dict[str, list[dict]]:
    facts: dict[str, list[dict]] = {field: [] for field in FIELD_PATTERNS}
    for page in pages:
        text = page["text"]
        for field, pattern in FIELD_PATTERNS.items():
            if len(facts[field]) >= MAX_FACTS_PER_FIELD:
                continue
            match = pattern.search(text)
            if not match:
                continue
            # Keep a bounded context around the first matching phrase. This is a review
            # candidate, not a claim that the whole paragraph is a normalized rule.
            start = max(0, match.start() - 220)
            end = min(len(text), max(match.end() + 700, start + 250))
            quote = text[start:end].strip()
            if len(quote) > MAX_QUOTE_LENGTH:
                quote = quote[:MAX_QUOTE_LENGTH].rsplit(" ", 1)[0]
            facts[field].append({
                "value": quote,
                "source_type": "pdf_text",
                "citation": {
                    "url": page["source_url"],
                    "page": page["page"],
                    "section": None,
                    "quote": quote,
                },
                "document_id": page["document_id"],
                "page": page["page"],
                "quote": quote,
            })
    return facts


def extract_call_facts(record: dict[str, Any], documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Build reviewable fact candidates; never mutates or promotes the source call."""
    facts = _metadata_facts(record)
    document_results = []
    all_pages = []
    for document in documents:
        source_url = document.get("source_url")
        if not _is_citable_url(source_url):
            document_results.append({
                "document_id": document["document_id"],
                "content_sha256": document["content_sha256"],
                "page_count_read": 0,
                "status": "missing_source_url",
            })
            continue
        pages, error = _extract_pdf_pages(document["content"], document["document_id"], source_url)
        all_pages.extend(pages)
        document_results.append({
            "document_id": document["document_id"],
            "content_sha256": document["content_sha256"],
            "page_count_read": len({page["page"] for page in pages}),
            "status": "text_extracted" if pages else (error or "no_text"),
        })

    pdf = _pdf_facts(all_pages)
    for field, candidates in pdf.items():
        seen = {item["value"] for item in facts[field]}
        for candidate in candidates:
            if candidate["value"] not in seen and len(facts[field]) < MAX_FACTS_PER_FIELD:
                facts[field].append(candidate)
                seen.add(candidate["value"])

    field_status = {
        field: ("found" if candidates else "not_found")
        for field, candidates in facts.items()
    }
    return {
        "schema_version": "1.0",
        "extractor_version": EXTRACTOR_VERSION,
        "bdns_code": record.get("source_identity", {}).get("bdns_code"),
        "source_payload_sha256": record.get("source_state", {}).get("payload_sha256"),
        "reliability": "extracted",
        "facts": facts,
        "field_status": field_status,
        "documents_processed": document_results,
        "limitations": [
            "Machine-extracted text is a candidate for human review, not an approved aid rule.",
            "Scanned pages without an embedded text layer are not OCR-processed.",
            "A missing extracted field means no matching text was found in the available sources; it does not prove the information is absent.",
        ],
    }


def _source_fingerprint(record: dict[str, Any], documents: list[dict[str, Any]]) -> str:
    source_state = record.get("source_state", {}).get("payload_sha256", "")
    parts = [EXTRACTOR_VERSION, source_state]
    parts.extend(f"{item['document_id']}:{item['content_sha256']}" for item in documents)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def extract_and_store(conn: Any, bdns_code: str, storage_root: str | Path) -> dict[str, Any]:
    calls = db.read_bdns_calls(conn, bdns_code)
    if not calls:
        raise ValueError(f"BDNS call {bdns_code!r} was not found.")
    review_status = db.read_bdns_call_status(conn, bdns_code)
    if review_status != "accepted_for_extraction":
        raise ValueError("The call must be accepted in the internal review queue before extraction.")
    root = Path(storage_root).expanduser().resolve()
    documents = []
    for item in db.read_downloaded_bdns_documents(conn, bdns_code):
        path = (root / item["stored_object_uri"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError("A stored PDF path escaped the configured document directory.")
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != item["content_sha256"]:
            raise ValueError(f"Stored PDF hash mismatch for document {item['bdns_document_id']}.")
        metadata = next(
            (source for source in calls[0].get("sources", {}).get("documents", [])
             if source.get("bdns_document_id") == item["document_id"]),
            {},
        )
        documents.append({**item, "source_url": metadata.get("download_url"), "content": content})
    result = extract_call_facts(calls[0], documents)
    fingerprint = _source_fingerprint(calls[0], documents)
    result["source_fingerprint"] = fingerprint
    db.record_bdns_extraction(conn, bdns_code, fingerprint, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract reviewable aid facts from an accepted BDNS call.")
    parser.add_argument("--bdns-code", required=True, help="BDNS call code already accepted for extraction.")
    parser.add_argument("--url", default=config.DATABASE_URL, help="Database URL (defaults to DATABASE_URL).")
    args = parser.parse_args(argv)
    try:
        if not args.url:
            raise ValueError("DATABASE_URL is missing.")
        with db.connect(args.url) as conn:
            db.create_schema(conn)
            result = extract_and_store(conn, args.bdns_code.strip(), config.BDNS_DOCUMENT_STORAGE_DIR)
        counts = {field: len(items) for field, items in result["facts"].items()}
        print(f"Stored extracted candidates for BDNS {result['bdns_code']} ({result['source_fingerprint'][:12]}…); source reliability remains metadata_only.")
        print(json.dumps({"field_status": result["field_status"], "candidate_counts": counts,
                          "documents_processed": result["documents_processed"]}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"BDNS extraction failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
