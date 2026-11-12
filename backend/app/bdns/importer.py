"""Bounded BDNS discovery and idempotent source-record import."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from typing import Any, Callable

from pydantic import ValidationError

from app.bdns import BDNSClient, BDNSFilters
from app.bdns.change_detection import payload_sha256
from app.core import config
from app.db import database as db
from app.models.bdns import BDNSCanonicalRecord


class BDNSImportError(ValueError):
    """A BDNS source record is missing required identity or has an invalid shape."""


def map_call_record(payload: dict[str, Any], retrieved_at: datetime | None = None) -> dict[str, Any]:
    """Map a BDNS detail response to a conservative canonical source record.

    Source metadata is retained in ``source_payload``. Farm relevance is left
    unclassified, and eligibility is never inferred from sector labels.
    """
    code = payload.get("codigoBDNS")
    title = payload.get("descripcion")
    if code is None or not str(code).strip():
        raise BDNSImportError("BDNS detail is missing codigoBDNS.")
    if not isinstance(title, str) or not title.strip():
        raise BDNSImportError(f"BDNS call {code} is missing descripcion.")
    if isinstance(payload.get("id"), bool) or not isinstance(payload.get("id"), (int, type(None))):
        raise BDNSImportError(f"BDNS call {code} has a non-numeric internal id.")
    for field in ("fechaRecepcion", "fechaInicioSolicitud", "fechaFinSolicitud"):
        value = payload.get(field)
        if value is not None:
            if not isinstance(value, str):
                raise BDNSImportError(f"BDNS call {code} has an invalid {field} date.")
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise BDNSImportError(f"BDNS call {code} has an invalid {field} date.") from exc

    org = payload.get("organo") or {}
    if not isinstance(org, dict):
        raise BDNSImportError(f"BDNS call {code} has an invalid organo value.")
    retrieved = retrieved_at or datetime.now(timezone.utc)
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=timezone.utc)

    detail_url = (
        "https://www.infosubvenciones.es/bdnstrans/"
        f"{config.BDNS_PORTAL_ID}/es/convocatoria/{str(code).strip()}"
    )
    documents = []
    for item in _object_list(payload, "documentos", code):
        document_id = item.get("id")
        documents.append({
            "bdns_document_id": document_id,
            "filename": item.get("nombreFic"),
            "description": item.get("descripcion"),
            "size_bytes": item.get("long"),
            "published_at": item.get("datPublicacion"),
            "source_modified_at": item.get("datMod"),
            "download_url": (
                f"{config.BDNS_API_BASE_URL.rstrip('/')}/convocatorias/documentos"
                f"?idDocumento={document_id}"
            ) if document_id is not None else None,
            "content_sha256": None,
            "stored_object_uri": None,
        })

    regions = _object_list(payload, "regiones", code)
    territories = []
    for region in regions:
        label = region.get("descripcion")
        match = re.match(r"\s*([A-Z]{2}\d{2})\s*-", label) if isinstance(label, str) else None
        territories.append({
            "source_label": label,
            "code": match.group(1) if match else None,
            "level": "autonomous_community" if match and match.group(1)[:2] == "ES" else None,
        })

    instruments = [item.get("descripcion") for item in _object_list(payload, "instrumentos", code)]
    beneficiaries = [item.get("descripcion") for item in _object_list(payload, "tiposBeneficiarios", code)]
    sectors = [
        {"code": item.get("codigo"), "label": item.get("descripcion")}
        for item in _object_list(payload, "sectores", code)
    ]
    retrieved_iso = retrieved.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    source_hash = payload_sha256(payload)
    record = {
        "schema_version": "1.0",
        "source_identity": {
            "system": "BDNS",
            "bdns_code": str(code).strip(),
            "bdns_internal_id": payload.get("id"),
            "detail_url": detail_url,
        },
        "source_state": {
            "retrieved_at": retrieved_iso,
            "payload_sha256": source_hash,
            "snapshot_id": source_hash,
        },
        "call": {
            "title": title.strip(),
            "title_co_official": payload.get("descripcionLeng"),
            "received_date": payload.get("fechaRecepcion"),
            "call_type": payload.get("tipoConvocatoria"),
            "budget_eur": payload.get("presupuestoTotal"),
            "mrr": payload.get("mrr"),
            "purpose": {"code": None, "label": payload.get("descripcionFinalidad")},
            "instruments": instruments,
            "economic_sectors": sectors,
            "beneficiary_categories": [{"code": None, "label": label} for label in beneficiaries],
            "funds": _object_list(payload, "fondos", code),
            "state_aid": {
                "number": payload.get("ayudaEstado"),
                "url": payload.get("urlAyudaEstado"),
                "regulation": payload.get("reglamento"),
            },
            "product_sectors": _object_list(payload, "sectoresProductos", code),
            "objectives": _object_list(payload, "objetivos", code),
            "granting_body": {
                "administration_level": org.get("nivel1"),
                "level_1": org.get("nivel2"),
                "level_2": org.get("nivel3"),
                "level_3": None,
            },
            "territories": territories,
            "farm_activity_classification": {"activities": [], "status": "unclassified", "evidence": []},
            "campaign": {"year": None, "label": None, "evidence": None},
        },
        "application": {
            "application_portal_url": payload.get("sedeElectronica"),
            "start_date": payload.get("fechaInicioSolicitud"),
            "end_date": payload.get("fechaFinSolicitud"),
            "start_text": payload.get("textInicio"),
            "end_text": payload.get("textFin"),
            "open_ended": payload.get("abierto"),
            "status": "unknown",
            "status_evidence": None,
            "official_gazette_extract_expected": payload.get("sePublicaDiarioOficial"),
        },
        "sources": {
            "regulatory_bases": {
                "title": payload.get("descripcionBasesReguladoras"),
                "url": payload.get("urlBasesReguladoras"),
            },
            "announcements": _object_list(payload, "anuncios", code),
            "documents": documents,
        },
        "quality": {
            "reliability": "metadata_only",
            "eligibility_status": "not_assessed",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": None,
        },
        "source_payload": payload,
    }
    return record


def _object_list(payload: dict[str, Any], name: str, code: Any) -> list[dict[str, Any]]:
    value = payload.get(name)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise BDNSImportError(f"BDNS call {code} has an invalid {name} array.")
    return value


def flatten_region_catalog(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten the official BDNS region tree while preserving IDs and hierarchy."""
    flattened: list[dict[str, Any]] = []

    def visit(nodes: list[dict[str, Any]], parent_id: int | None, depth: int) -> None:
        for node in nodes:
            region_id = node.get("id")
            description = node.get("descripcion")
            children = node.get("children", [])
            if isinstance(region_id, bool) or not isinstance(region_id, int):
                raise BDNSImportError("BDNS region catalog contains a node without a numeric id.")
            if not isinstance(description, str) or not description.strip():
                raise BDNSImportError(f"BDNS region {region_id} is missing its description.")
            if not isinstance(children, list) or any(not isinstance(item, dict) for item in children):
                raise BDNSImportError(f"BDNS region {region_id} has invalid children.")
            code_match = re.match(r"\s*([A-Z]{2}\d{2,3})\s*-", description)
            flattened.append({
                "region_id": region_id,
                "description": description.strip(),
                "nuts_code": code_match.group(1) if code_match else None,
                "parent_region_id": parent_id,
                "depth": depth,
            })
            visit(children, region_id, depth + 1)

    visit(items, None, 0)
    return flattened


def classify_search_activity(term: str) -> str:
    """Describe query intent from explicit activity words; never classify aid records."""
    normalized = unicodedata.normalize("NFD", term.casefold())
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    agriculture = any(word in normalized for word in (
        "agricultur", "agricola", "agrari", "cultiv", "cereal", "regadio", "olivar", "vin", "frutal",
        "horticol", "invernader",
    ))
    livestock = any(word in normalized for word in (
        "ganader", "vacun", "bovin", "ovin", "caprin", "porcin", "avicol", "apicol", "leche",
        "pastos", "extensiva", "raza", "sanidad", "bienestar",
    ))
    if agriculture and livestock:
        return "mixed"
    if agriculture:
        return "agriculture"
    if livestock:
        return "livestock"
    return "unknown"


def import_calls(
    client: BDNSClient,
    conn: Any | None,
    *,
    regions: tuple[int, ...],
    search_terms: tuple[str, ...],
    max_pages: int,
    administration_types: tuple[str, ...] = (),
    page_size: int = 50,
    upsert: Callable[[Any, list[dict[str, Any]]], None] = db.upsert_bdns_calls,
    query_observations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Discover a bounded slice, fetch details, validate, and optionally upsert it."""
    if not regions:
        raise ValueError("At least one BDNS region is required for a bounded import.")
    if max_pages < 1:
        raise ValueError("max_pages must be at least one.")
    if not search_terms or any(not term.strip() for term in search_terms):
        raise ValueError("Provide at least one non-empty search term.")
    regions = tuple(dict.fromkeys(regions))
    search_terms = tuple(dict.fromkeys(term.strip() for term in search_terms))
    administration_types = tuple(dict.fromkeys(value.upper() for value in administration_types))
    if any(value not in {"C", "A", "L", "O"} for value in administration_types):
        raise ValueError("Administration types must be C, A, L or O.")
    admin_filters: tuple[str | None, ...] = administration_types or (None,)
    codes: dict[str, None] = {}
    observations: list[dict[str, Any]] = []
    observation_offset = len(query_observations) if query_observations is not None else 0
    for region_id in regions:
        for term in search_terms:
            if term.lower().startswith("finalidad="):
                try:
                    purpose_id = int(term.split("=", 1)[1])
                except (IndexError, ValueError) as exc:
                    raise ValueError(f"Invalid purpose search route {term!r}; use finalidad=<numeric ID>.") from exc
                if purpose_id < 1:
                    raise ValueError("Purpose IDs must be positive.")
            else:
                purpose_id = None
            for administration_type in admin_filters:
                if purpose_id is not None:
                    filters = BDNSFilters(
                        purpose_id=purpose_id, regions=(region_id,),
                        administration_type=administration_type,
                    )
                else:
                    filters = BDNSFilters(
                        title=term, title_search_mode=2, regions=(region_id,),
                        administration_type=administration_type,
                    )
                query_codes: set[str] = set()
                for summary in client.iter_search(filters, max_pages=max_pages, page_size=page_size):
                    code = summary.get("numeroConvocatoria") or summary.get("codigoBDNS")
                    if code is not None and str(code).strip():
                        normalized_code = str(code).strip()
                        codes.setdefault(normalized_code, None)
                        query_codes.add(normalized_code)
                query_label = (
                    term if administration_type is None
                    else f"admin={administration_type}|{term}"
                )
                observation = {
                    "region_id": region_id,
                    "search_term": query_label,
                    "activity_scope": classify_search_activity(term),
                    "candidate_count": len(query_codes),
                    "_candidate_codes": query_codes,
                    "page_limit_reached": len(query_codes) >= max_pages * page_size,
                }
                observations.append(observation)
                if query_observations is not None:
                    query_observations.append({
                        key: value for key, value in observation.items() if key != "_candidate_codes"
                    } | {"candidate_codes": sorted(query_codes), "indexed_call_count": 0})

    records = []
    for code in codes:
        record = map_call_record(client.get_call(code))
        try:
            BDNSCanonicalRecord.model_validate(record)
        except ValidationError as exc:
            raise BDNSImportError(f"BDNS call {code} failed canonical record validation: {exc}") from exc
        records.append(record)
    mapped_codes = {record["source_identity"]["bdns_code"] for record in records}
    if records and conn is not None:
        upsert(conn, records)
        conn.commit()
    if query_observations is not None and conn is not None:
        for index, observation in enumerate(observations):
            indexed_codes = observation["_candidate_codes"] & mapped_codes
            query_observations[observation_offset + index]["candidate_codes"] = sorted(indexed_codes)
            query_observations[observation_offset + index]["indexed_call_count"] = len(indexed_codes)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a bounded BDNS call slice into the source-record table.")
    parser.add_argument("--regions", default="21", help="Comma-separated BDNS region IDs (default: Aragón, 21).")
    parser.add_argument("--terms", default="agricultura,ganadería", help="Comma-separated title searches.")
    parser.add_argument(
        "--administration-types", default="",
        help="Optional comma-separated BDNS administration filters: C, A, L or O.",
    )
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum pages per search term.")
    parser.add_argument("--page-size", type=int, default=10, help="Results per page (bounded by client configuration).")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and map records without writing to Postgres.")
    parser.add_argument("--url", default=config.DATABASE_URL, help="Database URL (not required with --dry-run).")
    args = parser.parse_args(argv)
    try:
        region_ids = tuple(int(value.strip()) for value in args.regions.split(",") if value.strip())
        terms = tuple(value.strip() for value in args.terms.split(",") if value.strip())
        administration_types = tuple(
            value.strip().upper() for value in args.administration_types.split(",") if value.strip()
        )
        if any(value not in {"C", "A", "L", "O"} for value in administration_types):
            raise ValueError("Administration types must be C, A, L or O.")
        if args.max_pages < 1 or args.page_size < 1:
            raise ValueError("max-pages and page-size must be positive.")
        if any(region < 0 for region in region_ids):
            raise ValueError("Region IDs must be non-negative.")
        if not args.dry_run and not args.url:
            raise ValueError("DATABASE_URL is missing. Set it or pass --dry-run.")
        with BDNSClient.from_config() as client:
            observations: list[dict[str, Any]] = []
            if args.dry_run:
                records = import_calls(
                    client, None, regions=region_ids, search_terms=terms,
                    max_pages=args.max_pages, page_size=args.page_size,
                    administration_types=administration_types,
                    query_observations=observations,
                )
            else:
                with db.connect(args.url) as conn:
                    db.create_schema(conn)
                    normalized_regions = tuple(dict.fromkeys(region_ids))
                    normalized_terms = tuple(dict.fromkeys(terms))
                    run_id = db.start_bdns_import_run(
                        conn, normalized_regions, normalized_terms, args.max_pages, args.page_size
                    )
                    try:
                        db.upsert_bdns_regions(conn, flatten_region_catalog(client.get_regions()))
                        records = import_calls(
                            client, conn, regions=normalized_regions, search_terms=normalized_terms,
                            max_pages=args.max_pages, page_size=args.page_size,
                            administration_types=administration_types,
                            query_observations=observations,
                        )
                        db.finish_bdns_import_run(
                            conn, run_id, status="completed",
                            candidate_count=sum(item["candidate_count"] for item in observations),
                            indexed_call_count=len(records), observations=observations,
                        )
                    except Exception as exc:
                        conn.rollback()
                        db.finish_bdns_import_run(
                            conn, run_id, status="failed",
                            candidate_count=sum(item["candidate_count"] for item in observations),
                            observations=observations, error_summary=str(exc)[:500]
                        )
                        raise
        print(f"Mapped {len(records)} unique BDNS calls; {'dry run, no database writes' if args.dry_run else 'upsert completed'}.")
        if args.dry_run:
            print(f"Dry run coverage preview: {len(observations)} bounded region/term queries; not saved to the database.")
        else:
            print(f"Coverage recorded for import run {run_id}: {len(observations)} region/term queries.")
        for record in records[:10]:
            identity = record["source_identity"]
            print(f"{identity['bdns_code']} — {record['call']['title'][:120]}")
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f"BDNS import failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
