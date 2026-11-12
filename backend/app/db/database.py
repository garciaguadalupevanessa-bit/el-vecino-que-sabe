"""Postgres access with psycopg 3. Aids are stored as JSONB validated with Pydantic."""
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.bdns.change_detection import changed_paths, extract_source_links, payload_sha256

SCHEMA = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def connect(url: str, attempts: int = 15, wait: float = 2.0) -> psycopg.Connection:
    """Connects with retries: in Docker the database may take a few seconds to accept connections."""
    for i in range(attempts):
        try:
            return psycopg.connect(url)
        except psycopg.OperationalError:
            if i == attempts - 1:
                raise
            time.sleep(wait)
    raise RuntimeError("unreachable")


def create_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version TEXT PRIMARY KEY,
               applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
           )"""
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if migration.name in applied:
            continue
        conn.execute(migration.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration.name,))
    conn.commit()


def count_aids(conn: psycopg.Connection) -> int:
    return conn.execute("SELECT count(*) FROM aids").fetchone()[0]


def upsert_aids(conn: psycopg.Connection, aids: list[dict]) -> None:
    for a in aids:
        conn.execute(
            """INSERT INTO aids (id, scope, reliability, data)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE
               SET scope = EXCLUDED.scope, reliability = EXCLUDED.reliability,
                   data = EXCLUDED.data, updated_at = now()""",
            (a["id"], a["scope"], a["reliability"], Jsonb(a)),
        )
        conn.execute("DELETE FROM aid_territories WHERE aid_id = %s", (a["id"],))
        conn.execute("DELETE FROM aid_bdns_calls WHERE aid_id = %s", (a["id"],))
        for territory in a.get("territories", []):
            conn.execute(
                """INSERT INTO aid_territories (
                       aid_id, territory_level, territory_code, territory_name, parent_code
                   ) VALUES (%s, %s, %s, %s, %s)""",
                (a["id"], territory["level"], territory.get("code"), territory["name"],
                 territory.get("parent_code")),
            )
        for source in a.get("bdns_calls", []):
            conn.execute(
                """INSERT INTO aid_bdns_calls (
                       aid_id, bdns_code, campaign_year, campaign_label, status
                   ) VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (aid_id, bdns_code) DO UPDATE SET
                       campaign_year = EXCLUDED.campaign_year,
                       campaign_label = EXCLUDED.campaign_label,
                       status = EXCLUDED.status""",
                (a["id"], source["bdns_code"], source.get("campaign_year"),
                 source.get("campaign_label"), source.get("status", "discovered")),
            )
            for event in source.get("review_history", []):
                event_fingerprint = payload_sha256({
                    "bdns_code": source["bdns_code"], "reviewer": event["reviewer"],
                    "status": event["status"], "reviewed_at": event["reviewed_at"],
                    "notes": event.get("notes", ""), "citations": event.get("citations", []),
                })
                conn.execute(
                    """INSERT INTO aid_review_events (
                           aid_id, bdns_code, event_fingerprint, reviewer, status, notes, citations, created_at
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (aid_id, event_fingerprint) DO NOTHING""",
                    (a["id"], source["bdns_code"], event_fingerprint, event["reviewer"],
                     event["status"], event.get("notes", ""), Jsonb(event.get("citations", [])),
                     datetime.fromisoformat(event["reviewed_at"].replace("Z", "+00:00"))),
                )


def _upsert_extraction_review_task(
    conn: psycopg.Connection, *, bdns_code: str, payload_sha256: str,
    extraction_fingerprint: str, issue_key: str, issue_type: str,
    field: str | None, summary: str, details: dict,
) -> int:
    row = conn.execute(
        """INSERT INTO bdns_extraction_review_tasks (
               bdns_code, payload_sha256, extraction_fingerprint, issue_key,
               issue_type, field, summary, details, status
           ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open')
           ON CONFLICT (bdns_code, payload_sha256, extraction_fingerprint, issue_key)
           DO UPDATE SET issue_type = EXCLUDED.issue_type, field = EXCLUDED.field,
                         summary = EXCLUDED.summary, details = EXCLUDED.details,
                         status = CASE
                           WHEN bdns_extraction_review_tasks.status IN ('reviewed_candidate', 'needs_correction')
                           THEN bdns_extraction_review_tasks.status ELSE 'open' END,
                         updated_at = now()
           RETURNING task_id""",
        (bdns_code, payload_sha256, extraction_fingerprint or "", issue_key,
         issue_type, field, summary, Jsonb(details)),
    ).fetchone()
    return row[0]


def _record_extraction_review_event(
    conn: psycopg.Connection, task_id: int, reviewer: str, decision: str, notes: str
) -> None:
    conn.execute(
        """INSERT INTO bdns_extraction_review_events (task_id, reviewer, decision, notes)
           VALUES (%s, %s, %s, %s)""",
        (task_id, reviewer, decision, notes),
    )


def _stale_extraction_review_tasks(
    conn: psycopg.Connection, bdns_code: str, payload_sha256: str,
    extraction_fingerprint: str, *, reason: str = "superseded",
) -> int:
    rows = conn.execute(
        """UPDATE bdns_extraction_review_tasks
           SET status = 'stale', updated_at = now()
           WHERE bdns_code = %s AND status IN ('open', 'needs_correction')
             AND (payload_sha256 <> %s OR extraction_fingerprint <> %s)
           RETURNING task_id""",
        (bdns_code, payload_sha256, extraction_fingerprint or ""),
    ).fetchall()
    for (task_id,) in rows:
        _record_extraction_review_event(
            conn, task_id, "system", reason,
            "Task closed because its source or extraction fingerprint changed.",
        )
    return len(rows)


def _enqueue_extraction_candidate_tasks(
    conn: psycopg.Connection, bdns_code: str, payload_sha256: str,
    extraction_fingerprint: str, extraction: dict,
) -> None:
    facts = extraction.get("facts", {})
    statuses = extraction.get("field_status", {})
    for field, candidates in facts.items():
        candidates = candidates if isinstance(candidates, list) else []
        unique = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            value = candidate.get("value")
            if isinstance(value, str) and value.strip():
                unique.setdefault(" ".join(value.split()).casefold(), candidate)
        if not unique:
            if statuses.get(field) == "not_found" or not candidates:
                _upsert_extraction_review_task(
                    conn, bdns_code=bdns_code, payload_sha256=payload_sha256,
                    extraction_fingerprint=extraction_fingerprint,
                    issue_key=f"missing_data:{field}", issue_type="missing_data",
                    field=field,
                    summary=f"No se encontró un dato para revisar en «{field}».",
                    details={"field_status": statuses.get(field, "not_found"), "candidates": []},
                )
            continue
        if len(unique) > 1:
            _upsert_extraction_review_task(
                conn, bdns_code=bdns_code, payload_sha256=payload_sha256,
                extraction_fingerprint=extraction_fingerprint,
                issue_key=f"ambiguous_data:{field}", issue_type="ambiguous_data",
                field=field,
                summary=f"Hay {len(unique)} textos candidatos distintos para revisar en «{field}».",
                details={"field_status": statuses.get(field, "found"),
                         "candidate_count": len(unique), "candidates": list(unique.values())[:8],
                         "truncated": len(unique) > 8},
            )


def _sync_quality_review_tasks(
    conn: psycopg.Connection, bdns_code: str, payload_sha256: str,
    extraction_fingerprint: str, report: dict,
) -> None:
    active_keys = set()
    for finding in report.get("findings", []):
        if not isinstance(finding, dict):
            continue
        code = str(finding.get("code") or "unknown")
        details = finding.get("details") if isinstance(finding.get("details"), dict) else {}
        field = details.get("field") or finding.get("check")
        discriminator = details.get("document_id") or details.get("field") or details.get("territory_index") or finding.get("check")
        issue_key = f"quality:{code}:{discriminator}"
        active_keys.add(issue_key)
        if code in {"source_changed", "extraction_stale"}:
            issue_type = "source_changed"
        elif code in {"date_order_conflict", "call_hash_mismatch", "territory_label_code_conflict", "document_hash_mismatch"}:
            issue_type = "conflicting_data"
        elif code in {"required_field_missing", "document_not_downloaded", "territory_unspecified"}:
            issue_type = "missing_data"
        else:
            issue_type = "quality_finding"
        translated = {
            "source_changed": "La convocatoria cambió desde la extracción.",
            "extraction_stale": "La extracción no coincide con la versión actual de la fuente.",
            "url_unreachable": "Un enlace oficial requiere revisión de accesibilidad.",
            "url_reachability_unknown": "No se pudo confirmar la accesibilidad de un enlace oficial.",
            "pdf_has_no_text": "El PDF no contiene texto extraíble y requiere revisión.",
            "date_order_conflict": "Las fechas de inicio y fin no son coherentes.",
            "call_hash_mismatch": "La huella de la convocatoria no coincide con la fuente guardada.",
            "territory_label_code_conflict": "El código territorial no coincide con la etiqueta de origen.",
            "document_hash_mismatch": "El contenido del PDF no coincide con su huella guardada.",
        }.get(code, "Un control automático detectó un dato que requiere revisión humana.")
        _upsert_extraction_review_task(
            conn, bdns_code=bdns_code, payload_sha256=payload_sha256,
            extraction_fingerprint=extraction_fingerprint,
            issue_key=issue_key, issue_type=issue_type, field=field,
            summary=translated, details={"finding": finding},
        )

    previous = conn.execute(
        """UPDATE bdns_extraction_review_tasks SET status = 'stale', updated_at = now()
           WHERE bdns_code = %s AND payload_sha256 = %s AND extraction_fingerprint = %s
             AND left(issue_key, 8) = 'quality:' AND status IN ('open', 'needs_correction')
             AND NOT (issue_key = ANY(%s))
           RETURNING task_id""",
        (bdns_code, payload_sha256, extraction_fingerprint or "", sorted(active_keys)),
    ).fetchall()
    for (task_id,) in previous:
        _record_extraction_review_event(
            conn, task_id, "system", "quality_issue_cleared",
            "A newer quality check no longer reports this finding.",
        )


def upsert_bdns_calls(conn: psycopg.Connection, records: list[dict]) -> None:
    """Upsert current calls, preserve unique source snapshots and flag changed calls for review."""
    for record in records:
        identity = record["source_identity"]
        code = identity["bdns_code"]
        payload = record.get("source_payload", {})
        fingerprint = record.get("source_state", {}).get("payload_sha256") or payload_sha256(payload)
        record.setdefault("source_state", {})["payload_sha256"] = fingerprint
        record["source_state"]["snapshot_id"] = fingerprint
        existing = conn.execute(
            "SELECT data, payload_sha256, reliability FROM bdns_calls WHERE bdns_code = %s FOR UPDATE",
            (code,),
        ).fetchone()
        previous_data = existing[0] if existing else None
        previous_hash = existing[1] if existing else None
        previous_reliability = existing[2] if existing else None

        # Existing task 2.3 rows predate fingerprints; baseline them without a false change event.
        if existing and previous_hash is None:
            old_payload = previous_data.get("source_payload", {})
            if old_payload:
                previous_hash = payload_sha256(old_payload)
                previous_data.setdefault("source_state", {})["payload_sha256"] = previous_hash
                previous_data["source_state"]["snapshot_id"] = previous_hash
                conn.execute(
                    """INSERT INTO bdns_call_snapshots
                       (bdns_code, payload_sha256, source_payload, canonical_record)
                       VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                    (code, previous_hash, Jsonb(old_payload), Jsonb(previous_data)),
                )
                conn.execute(
                    "UPDATE bdns_calls SET payload_sha256 = %s WHERE bdns_code = %s",
                    (previous_hash, code),
                )

        if existing and previous_hash and previous_hash != fingerprint:
            _invalidate_bdns_verification(
                conn, code, "La ficha BDNS cambió; se reabrió la verificación de la fuente."
            )
            latest = conn.execute(
                "SELECT source_fingerprint FROM bdns_extractions WHERE bdns_code = %s ORDER BY created_at DESC LIMIT 1",
                (code,),
            ).fetchone()
            _stale_extraction_review_tasks(
                conn, code, fingerprint, latest[0] if latest else "", reason="source_changed"
            )
            _upsert_extraction_review_task(
                conn, bdns_code=code, payload_sha256=fingerprint,
                extraction_fingerprint=latest[0] if latest else "",
                issue_key="source_changed", issue_type="source_changed", field=None,
                summary="La convocatoria cambió desde la última extracción; hay que revisar la nueva versión.",
                details={"previous_payload_sha256": previous_hash,
                         "current_payload_sha256": fingerprint,
                         "changed_paths": changed_paths(previous_data.get("source_payload", {}), payload)},
            )

        verified_unchanged = bool(
            existing and previous_reliability == "verified" and previous_hash == fingerprint
        )
        if verified_unchanged:
            previous_quality = previous_data.get("quality", {})
            record.setdefault("quality", {}).update({
                "reliability": "verified",
                "reviewed_by": previous_quality.get("reviewed_by"),
                "reviewed_at": previous_quality.get("reviewed_at"),
                "review_notes": previous_quality.get("review_notes"),
            })

        conn.execute(
            """INSERT INTO bdns_calls (bdns_code, bdns_id, reliability, data, payload_sha256)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (bdns_code) DO UPDATE
               SET bdns_id = EXCLUDED.bdns_id,
                   reliability = EXCLUDED.reliability,
                   data = EXCLUDED.data,
                   payload_sha256 = EXCLUDED.payload_sha256,
                   review_status = CASE
                       WHEN bdns_calls.payload_sha256 IS DISTINCT FROM EXCLUDED.payload_sha256 THEN 'review_required'
                       ELSE bdns_calls.review_status END,
                   last_seen_at = now(), updated_at = now()""",
            (
                code,
                identity.get("bdns_internal_id"),
                "verified" if verified_unchanged else record["quality"]["reliability"],
                Jsonb(record),
                fingerprint,
            ),
        )
        conn.execute(
            """INSERT INTO bdns_call_snapshots
               (bdns_code, payload_sha256, source_payload, canonical_record)
               VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
            (code, fingerprint, Jsonb(payload), Jsonb(record)),
        )
        if not existing or previous_hash != fingerprint:
            paths = changed_paths(
                previous_data.get("source_payload", {}) if previous_data else {}, payload
            ) if existing else []
            conn.execute(
                """INSERT INTO bdns_call_changes
                   (bdns_code, event_type, previous_sha256, current_sha256, changed_paths)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    code,
                    "changed" if existing else "discovered",
                    previous_hash,
                    fingerprint,
                    Jsonb(paths),
                ),
            )
        _sync_bdns_links(conn, code, extract_source_links(record))
        current_document_ids = [
            item["bdns_document_id"]
            for item in record.get("sources", {}).get("documents", [])
            if isinstance(item.get("bdns_document_id"), int)
            and not isinstance(item.get("bdns_document_id"), bool)
        ]
        conn.execute(
            """UPDATE bdns_documents SET status = 'removed',
                      last_error = 'No longer listed in the current BDNS call detail.', updated_at = now()
               WHERE bdns_code = %s AND status <> 'removed'
                 AND NOT (bdns_document_id = ANY(%s))""",
            (code, current_document_ids),
        )


def _sync_bdns_links(conn: psycopg.Connection, code: str, links: list[dict]) -> None:
    incoming = {
        (link["resource_type"], link["resource_key"], link["url"])
        for link in links
    }
    existing = conn.execute(
        """SELECT resource_type, resource_key, url FROM bdns_links
           WHERE bdns_code = %s AND is_current = TRUE""",
        (code,),
    ).fetchall()
    for resource_type, resource_key, url in existing:
        if (resource_type, resource_key, url) not in incoming:
            conn.execute(
                """UPDATE bdns_links SET is_current = FALSE, status = 'removed', updated_at = now()
                   WHERE bdns_code = %s AND resource_type = %s AND resource_key = %s AND url = %s""",
                (code, resource_type, resource_key, url),
            )
    for link in links:
        conn.execute(
            """INSERT INTO bdns_links
               (bdns_code, resource_type, resource_key, url, status, is_current)
               VALUES (%s, %s, %s, %s, 'unknown', TRUE)
               ON CONFLICT (bdns_code, resource_type, resource_key, url) DO UPDATE SET
                   status = CASE WHEN bdns_links.is_current THEN bdns_links.status ELSE 'unknown' END,
                   is_current = TRUE,
                   status_code = CASE WHEN bdns_links.is_current THEN bdns_links.status_code ELSE NULL END,
                   last_error = CASE WHEN bdns_links.is_current THEN bdns_links.last_error ELSE NULL END,
                   checked_at = CASE WHEN bdns_links.is_current THEN bdns_links.checked_at ELSE NULL END,
                   updated_at = now()""",
            (code, link["resource_type"], link["resource_key"], link["url"]),
        )


def read_bdns_links(
    conn: psycopg.Connection, bdns_code: str | None = None, limit: int = 10
) -> list[dict]:
    if limit < 1:
        raise ValueError("limit must be positive.")
    if bdns_code is None:
        rows = conn.execute(
            """SELECT bdns_code, resource_type, resource_key, url FROM bdns_links
               WHERE is_current = TRUE ORDER BY bdns_code, resource_type, resource_key LIMIT %s""",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT bdns_code, resource_type, resource_key, url FROM bdns_links
               WHERE bdns_code = %s AND is_current = TRUE
               ORDER BY resource_type, resource_key LIMIT %s""",
            (bdns_code, limit),
        ).fetchall()
    return [
        {"bdns_code": row[0], "resource_type": row[1], "resource_key": row[2], "url": row[3]}
        for row in rows
    ]


def record_bdns_link_check(conn: psycopg.Connection, item: dict) -> None:
    conn.execute(
        """UPDATE bdns_links SET status = %s, status_code = %s, last_error = %s,
                  checked_at = now(), updated_at = now()
           WHERE bdns_code = %s AND resource_type = %s AND resource_key = %s AND url = %s
             AND is_current = TRUE""",
        (
            item["status"], item.get("status_code"), item.get("last_error"), item["bdns_code"],
            item["resource_type"], item["resource_key"], item["url"],
        ),
    )


def read_bdns_quality_context(conn: psycopg.Connection, bdns_code: str) -> dict:
    """Read current link, document, territory, snapshot and extraction state for QA."""
    call_row = conn.execute(
        "SELECT payload_sha256 FROM bdns_calls WHERE bdns_code = %s", (bdns_code,)
    ).fetchone()
    if call_row is None:
        return {}
    payload_sha256 = call_row[0]
    snapshot_exists = False
    if payload_sha256:
        snapshot_exists = conn.execute(
            """SELECT EXISTS(SELECT 1 FROM bdns_call_snapshots
               WHERE bdns_code = %s AND payload_sha256 = %s)""",
            (bdns_code, payload_sha256),
        ).fetchone()[0]
    change = conn.execute(
        """SELECT event_type, previous_sha256, current_sha256, changed_paths, detected_at
           FROM bdns_call_changes WHERE bdns_code = %s
           ORDER BY detected_at DESC, change_id DESC LIMIT 1""",
        (bdns_code,),
    ).fetchone()
    documents = conn.execute(
        """SELECT d.bdns_document_id, d.status, d.content_sha256, d.stored_object_uri,
                  d.downloaded_size_bytes,
                  EXISTS(SELECT 1 FROM bdns_document_versions v
                         WHERE v.bdns_code = d.bdns_code
                           AND v.bdns_document_id = d.bdns_document_id
                           AND v.content_sha256 = d.content_sha256) AS version_recorded
           FROM bdns_documents d WHERE d.bdns_code = %s ORDER BY d.bdns_document_id""",
        (bdns_code,),
    ).fetchall()
    links = conn.execute(
        """SELECT resource_type, resource_key, url, status, status_code, last_error, checked_at
           FROM bdns_links WHERE bdns_code = %s AND is_current = TRUE
           ORDER BY resource_type, resource_key, url""",
        (bdns_code,),
    ).fetchall()
    territories = conn.execute(
        "SELECT nuts_code, description FROM bdns_regions WHERE nuts_code IS NOT NULL"
    ).fetchall()
    extraction = conn.execute(
        """SELECT data, source_fingerprint, created_at FROM bdns_extractions
           WHERE bdns_code = %s ORDER BY created_at DESC, source_fingerprint DESC LIMIT 1""",
        (bdns_code,),
    ).fetchone()
    return {
        "database_payload_sha256": payload_sha256,
        "snapshot_exists": snapshot_exists,
        "latest_change": ({
            "event_type": change[0], "previous_sha256": change[1],
            "current_sha256": change[2], "changed_paths": change[3],
            "detected_at": change[4].isoformat(),
        } if change else None),
        "documents": [{
            "document_id": row[0], "status": row[1], "content_sha256": row[2],
            "stored_object_uri": row[3], "size_bytes": row[4], "version_recorded": row[5],
        } for row in documents],
        "links": [{
            "resource_type": row[0], "resource_key": row[1], "url": row[2],
            "status": row[3], "status_code": row[4], "last_error": row[5],
            "checked_at": row[6].isoformat() if row[6] else None,
        } for row in links],
        "known_territories": [
            {"nuts_code": row[0], "description": row[1]} for row in territories
        ],
        "latest_extraction": ({
            "data": extraction[0], "source_fingerprint": extraction[1],
            "created_at": extraction[2].isoformat(),
        } if extraction else None),
    }


def record_bdns_quality_check(
    conn: psycopg.Connection, bdns_code: str, payload_sha256: str | None, report: dict
) -> int:
    row = conn.execute(
        """INSERT INTO bdns_quality_checks (bdns_code, payload_sha256, report)
           VALUES (%s, %s, %s) RETURNING check_id""",
        (bdns_code, payload_sha256, Jsonb(report)),
    ).fetchone()
    current = conn.execute(
        "SELECT payload_sha256 FROM bdns_calls WHERE bdns_code = %s", (bdns_code,)
    ).fetchone()
    extraction = conn.execute(
        "SELECT source_fingerprint FROM bdns_extractions WHERE bdns_code = %s ORDER BY created_at DESC LIMIT 1",
        (bdns_code,),
    ).fetchone()
    if current and payload_sha256 == current[0]:
        _sync_quality_review_tasks(
            conn, bdns_code, current[0], extraction[0] if extraction else "", report
        )
    conn.commit()
    return row[0]


def read_latest_bdns_quality_check(conn: psycopg.Connection, bdns_code: str) -> dict | None:
    row = conn.execute(
        """SELECT check_id, report, created_at FROM bdns_quality_checks
           WHERE bdns_code = %s ORDER BY created_at DESC, check_id DESC LIMIT 1""",
        (bdns_code,),
    ).fetchone()
    if not row:
        return None
    return {**row[1], "check_id": row[0], "created_at": row[2].isoformat()}


def _verification_document_manifest(conn: psycopg.Connection, bdns_code: str, data: dict) -> list[dict]:
    inventory = {
        row[0]: {"status": row[1], "content_sha256": row[2]}
        for row in conn.execute(
            "SELECT bdns_document_id, status, content_sha256 FROM bdns_documents WHERE bdns_code = %s",
            (bdns_code,),
        ).fetchall()
    }
    manifest = []
    documents = data.get("sources", {}).get("documents", [])
    if not isinstance(documents, list):
        documents = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        document_id = document.get("bdns_document_id")
        stored = inventory.get(document_id, {})
        manifest.append({
            "document_id": document_id,
            "url": document.get("download_url"),
            "status": stored.get("status", "not_downloaded"),
            "content_sha256": stored.get("content_sha256"),
        })
    return sorted(manifest, key=lambda item: str(item["document_id"]))


def _verification_context(conn: psycopg.Connection, bdns_code: str) -> dict | None:
    call = conn.execute(
        "SELECT data, payload_sha256, reliability, review_status FROM bdns_calls WHERE bdns_code = %s",
        (bdns_code,),
    ).fetchone()
    if not call:
        return None
    data, payload_hash, reliability, review_status = call
    extraction = conn.execute(
        """SELECT data, source_fingerprint FROM bdns_extractions WHERE bdns_code = %s
           ORDER BY created_at DESC, source_fingerprint DESC LIMIT 1""",
        (bdns_code,),
    ).fetchone()
    quality = conn.execute(
        """SELECT payload_sha256, report, created_at FROM bdns_quality_checks
           WHERE bdns_code = %s ORDER BY created_at DESC, check_id DESC LIMIT 1""",
        (bdns_code,),
    ).fetchone()
    documents = _verification_document_manifest(conn, bdns_code, data)
    extraction_data = extraction[0] if extraction else None
    extraction_fingerprint = extraction[1] if extraction else ""
    extraction_documents = sorted(
        ({"document_id": item.get("document_id"), "content_sha256": item.get("content_sha256")}
         for item in (extraction_data or {}).get("documents_processed", [])
         if isinstance(item, dict)),
        key=lambda item: str(item["document_id"]),
    )
    current_downloads = sorted(
        ({"document_id": item["document_id"], "content_sha256": item["content_sha256"]}
         for item in documents if item["status"] == "downloaded" and item["content_sha256"]),
        key=lambda item: str(item["document_id"]),
    )
    extraction_current = bool(
        extraction_data
        and extraction_data.get("source_payload_sha256") == payload_hash
        and extraction_documents == current_downloads
    )
    pending_count = conn.execute(
        """SELECT count(*) FROM bdns_extraction_review_tasks
           WHERE bdns_code = %s AND payload_sha256 = %s AND status IN ('open', 'needs_correction')""",
        (bdns_code, payload_hash),
    ).fetchone()[0]
    quality_current = bool(
        quality
        and quality[0] == payload_hash
        and quality[1].get("overall_status") == "passed"
        and conn.execute(
            """SELECT NOT EXISTS(
                 SELECT 1 FROM bdns_documents WHERE bdns_code = %s AND updated_at > %s
               )""",
            (bdns_code, quality[2]),
        ).fetchone()[0]
    )
    latest_event = conn.execute(
        """SELECT event_type, reviewer, notes, created_at, approved_rules
           FROM bdns_call_verification_events WHERE bdns_code = %s
           ORDER BY created_at DESC, verification_event_id DESC LIMIT 1""",
        (bdns_code,),
    ).fetchone()
    return {
        "bdns_code": bdns_code,
        "reliability": reliability,
        "review_status": review_status,
        "payload_sha256": payload_hash,
        "document_manifest": documents,
        "document_fingerprint": payload_sha256({"documents": documents}),
        "extraction_fingerprint": extraction_fingerprint,
        "extraction_current": extraction_current,
        "pending_extraction_tasks": pending_count,
        "latest_quality_status": quality[1].get("overall_status") if quality else "not_run",
        "quality_current": quality_current,
        "latest_verification": ({
            "status": latest_event[0], "reviewer": latest_event[1], "notes": latest_event[2],
            "created_at": latest_event[3].isoformat(), "approved_rules": latest_event[4],
        } if latest_event else None),
        "eligible_to_verify": bool(
            review_status == "accepted_for_extraction" and extraction_current
            and pending_count == 0 and quality_current
        ),
    }


def read_bdns_verification_state(conn: psycopg.Connection, bdns_code: str) -> dict | None:
    return _verification_context(conn, bdns_code)


def verify_bdns_call(
    conn: psycopg.Connection, bdns_code: str, expected_payload_sha256: str,
    expected_extraction_fingerprint: str, reviewer: str, notes: str,
    approved_rules: list[dict],
) -> str:
    reviewer, notes = reviewer.strip(), notes.strip()
    if len(reviewer) < 2 or len(reviewer) > 120 or not notes or len(notes) > 2000:
        raise ValueError("Reviewer identity and source-review notes are required.")
    if not approved_rules or len(approved_rules) > 50:
        raise ValueError("At least one approved, cited rule is required.")
    locked = conn.execute(
        "SELECT bdns_code FROM bdns_calls WHERE bdns_code = %s FOR UPDATE", (bdns_code,)
    ).fetchone()
    if not locked:
        return "not_found"
    context = _verification_context(conn, bdns_code)
    assert context is not None
    if (context["payload_sha256"] != expected_payload_sha256
            or context["extraction_fingerprint"] != expected_extraction_fingerprint):
        return "stale"
    if not context["eligible_to_verify"]:
        return "not_ready"

    call = conn.execute("SELECT data FROM bdns_calls WHERE bdns_code = %s", (bdns_code,)).fetchone()[0]
    official_urls = {call.get("source_identity", {}).get("detail_url")}
    sources = call.get("sources", {})
    for document in sources.get("documents", []):
        if isinstance(document, dict) and document.get("download_url"):
            official_urls.add(document["download_url"])
    bases = sources.get("regulatory_bases", {})
    if isinstance(bases, dict) and bases.get("url"):
        official_urls.add(bases["url"])
    for announcement in sources.get("announcements", []):
        if isinstance(announcement, dict) and announcement.get("url"):
            official_urls.add(announcement["url"])
    portal = call.get("application", {}).get("application_portal_url")
    if portal:
        official_urls.add(portal)
    for rule in approved_rules:
        if str(rule.get("source_url", "")).rstrip("/") not in {
            str(url).rstrip("/") for url in official_urls if url
        }:
            return "invalid_citation"
    conn.execute(
        """INSERT INTO bdns_call_verification_events
           (bdns_code, event_type, payload_sha256, document_fingerprint,
            extraction_fingerprint, reviewer, notes, approved_rules)
           VALUES (%s, 'verified', %s, %s, %s, %s, %s, %s)""",
        (bdns_code, expected_payload_sha256, context["document_fingerprint"],
         expected_extraction_fingerprint, reviewer, notes, Jsonb(approved_rules)),
    )
    conn.execute(
        """UPDATE bdns_calls SET reliability = 'verified',
             data = jsonb_set(jsonb_set(jsonb_set(jsonb_set(data,
               '{quality,reliability}', '"verified"'::jsonb, true),
               '{quality,reviewed_by}', to_jsonb(%s::text), true),
               '{quality,reviewed_at}', to_jsonb(now()::text), true),
               '{quality,review_notes}', to_jsonb(%s::text), true), updated_at = now()
           WHERE bdns_code = %s""",
        (reviewer, notes, bdns_code),
    )
    return "verified"


def _invalidate_bdns_verification(conn: psycopg.Connection, bdns_code: str, reason: str) -> None:
    row = conn.execute(
        "SELECT data, payload_sha256, reliability FROM bdns_calls WHERE bdns_code = %s FOR UPDATE",
        (bdns_code,),
    ).fetchone()
    if not row or row[2] != "verified":
        return
    data, payload_hash, _ = row
    manifest = _verification_document_manifest(conn, bdns_code, data)
    doc_fingerprint = payload_sha256({"documents": manifest})
    latest = conn.execute(
        """SELECT extraction_fingerprint FROM bdns_call_verification_events
           WHERE bdns_code = %s AND event_type = 'verified'
           ORDER BY created_at DESC, verification_event_id DESC LIMIT 1""",
        (bdns_code,),
    ).fetchone()
    extraction_fingerprint = latest[0] if latest else ""
    conn.execute(
        """INSERT INTO bdns_call_verification_events
           (bdns_code, event_type, payload_sha256, document_fingerprint,
            extraction_fingerprint, reviewer, notes, approved_rules)
           VALUES (%s, 'reopened', %s, %s, %s, 'system', %s, '[]'::jsonb)""",
        (bdns_code, payload_hash or "", doc_fingerprint, extraction_fingerprint, reason[:2000]),
    )
    conn.execute(
        """UPDATE bdns_calls SET reliability = 'metadata_only',
             data = jsonb_set(jsonb_set(jsonb_set(jsonb_set(data,
               '{quality,reliability}', '"metadata_only"'::jsonb, true),
               '{quality,reviewed_by}', 'null'::jsonb, true),
               '{quality,reviewed_at}', 'null'::jsonb, true),
               '{quality,review_notes}', 'null'::jsonb, true), updated_at = now()
           WHERE bdns_code = %s""",
        (bdns_code,),
    )
    _invalidate_agent_published_aids(conn, bdns_code, reason)
    if payload_hash:
        extraction = conn.execute(
            """SELECT source_fingerprint FROM bdns_extractions WHERE bdns_code = %s
               ORDER BY created_at DESC, source_fingerprint DESC LIMIT 1""",
            (bdns_code,),
        ).fetchone()
        _upsert_extraction_review_task(
            conn, bdns_code=bdns_code, payload_sha256=payload_hash,
            extraction_fingerprint=extraction[0] if extraction else "",
            issue_key=f"verification_reopened:{doc_fingerprint}", issue_type="source_changed", field="sources",
            summary="Cambió una fuente después de verificarla; hay que extraer y revisar la versión actual.",
            details={"reason": reason, "previous_verified_extraction_fingerprint": extraction_fingerprint},
        )


def _invalidate_agent_published_aids(conn: psycopg.Connection, bdns_code: str, reason: str) -> None:
    """Withdraw automatic verification when its BDNS source or documents change."""
    rows = conn.execute(
        """SELECT a.data FROM aids a JOIN aid_bdns_calls link ON link.aid_id = a.id
           WHERE link.bdns_code = %s AND a.data->>'verification_method' = 'agent'""",
        (bdns_code,),
    ).fetchall()
    for (aid,) in rows:
        if aid.get("reliability") != "verified":
            continue
        aid["reliability"] = "extracted"
        aid["verified_by"] = None
        aid["notes"] = f"{aid.get('notes') or ''} Verificación automática reabierta: {reason}"[:2000]
        for source in aid.get("bdns_calls", []):
            if source.get("bdns_code") != bdns_code:
                continue
            source["status"] = "extracted"
            source.setdefault("review_history", []).append({
                "reviewer": "system", "status": "reopened",
                "reviewed_at": datetime.now().astimezone().isoformat(),
                "notes": reason[:2000], "citations": source.get("citations", []),
            })
        upsert_aids(conn, [aid])


def read_bdns_calls(conn: psycopg.Connection, bdns_code: str | None = None) -> list[dict]:
    if bdns_code is not None:
        row = conn.execute("SELECT data FROM bdns_calls WHERE bdns_code = %s", (bdns_code,)).fetchone()
        return [row[0]] if row else []
    return [row[0] for row in conn.execute("SELECT data FROM bdns_calls ORDER BY bdns_code").fetchall()]


def read_bdns_call_status(conn: psycopg.Connection, bdns_code: str) -> str | None:
    row = conn.execute("SELECT review_status FROM bdns_calls WHERE bdns_code = %s", (bdns_code,)).fetchone()
    return row[0] if row else None


def read_downloaded_bdns_documents(conn: psycopg.Connection, bdns_code: str) -> list[dict]:
    rows = conn.execute(
        """SELECT bdns_document_id, content_sha256, stored_object_uri
           FROM bdns_documents WHERE bdns_code = %s AND status = 'downloaded'
           AND content_sha256 IS NOT NULL AND stored_object_uri IS NOT NULL
           ORDER BY bdns_document_id""",
        (bdns_code,),
    ).fetchall()
    return [{"document_id": row[0], "content_sha256": row[1], "stored_object_uri": row[2]} for row in rows]


def record_bdns_extraction(
    conn: psycopg.Connection, bdns_code: str, source_fingerprint: str, extraction: dict
) -> None:
    conn.execute(
        """INSERT INTO bdns_extractions (bdns_code, source_fingerprint, reliability, data)
           VALUES (%s, %s, 'extracted', %s) ON CONFLICT (bdns_code, source_fingerprint) DO NOTHING""",
        (bdns_code, source_fingerprint, Jsonb(extraction)),
    )
    current = conn.execute(
        "SELECT payload_sha256 FROM bdns_calls WHERE bdns_code = %s", (bdns_code,)
    ).fetchone()
    if current:
        _stale_extraction_review_tasks(conn, bdns_code, current[0], source_fingerprint)
        if extraction.get("source_payload_sha256") == current[0]:
            _enqueue_extraction_candidate_tasks(conn, bdns_code, current[0], source_fingerprint, extraction)
        else:
            _upsert_extraction_review_task(
                conn, bdns_code=bdns_code, payload_sha256=current[0],
                extraction_fingerprint=source_fingerprint, issue_key="source_changed",
                issue_type="source_changed", field=None,
                summary="La extracción corresponde a una versión anterior de la convocatoria.",
                details={"extraction_payload_sha256": extraction.get("source_payload_sha256"),
                         "extraction_fingerprint": source_fingerprint,
                         "current_payload_sha256": current[0]},
            )
    conn.commit()


def read_latest_bdns_extraction(conn: psycopg.Connection, bdns_code: str) -> dict | None:
    row = conn.execute(
        """SELECT data, source_fingerprint, reliability, created_at
           FROM bdns_extractions WHERE bdns_code = %s
           ORDER BY created_at DESC, source_fingerprint DESC LIMIT 1""",
        (bdns_code,),
    ).fetchone()
    if not row:
        return None
    return {**row[0], "source_fingerprint": row[1], "reliability": row[2], "created_at": row[3].isoformat()}


REVIEW_STATUSES = {
    "pending_review", "review_required", "reviewed",
    "accepted_for_extraction", "out_of_scope",
}
REVIEW_DECISIONS = {"accepted_for_extraction", "out_of_scope"}


def _review_item(
    data: dict, review_status: str, fingerprint: str | None, last_seen_at: Any,
    classification_event: dict | None = None, ai_suggestion: dict | None = None,
) -> dict:
    from app.bdns.triage import suggest_bdns_triage

    identity = data.get("source_identity", {})
    call = data.get("call", {})
    sources = data.get("sources", {})
    bases = sources.get("regulatory_bases", {})
    classification = None
    if classification_event:
        classification = {
            **classification_event,
            "is_current": classification_event.get("payload_sha256") == fingerprint,
            "is_active": (
                classification_event.get("payload_sha256") == fingerprint
                and review_status == "accepted_for_extraction"
            ),
        }
    return {
        "bdns_code": identity.get("bdns_code"),
        "title": call.get("title"),
        "detail_url": identity.get("detail_url"),
        "last_seen_at": last_seen_at.isoformat() if hasattr(last_seen_at, "isoformat") else last_seen_at,
        "payload_sha256": fingerprint,
        "review_status": review_status,
        "reliability": data.get("quality", {}).get("reliability", "metadata_only"),
        "verified_by": data.get("quality", {}).get("reviewed_by"),
        "call": call,
        "automated_triage": suggest_bdns_triage(data),
        "ai_pre_review": ai_suggestion,
        "confirmed_classification": classification,
        "application": data.get("application", {}),
        "sources": {
            "regulatory_bases": bases,
            "announcements": sources.get("announcements", []),
            "documents": sources.get("documents", []),
        },
    }


def read_bdns_review_queue(
    conn: psycopg.Connection, status: str | None = None, limit: int = 50, offset: int = 0,
    *, run_id: int | None = None, region_id: int | None = None, query: str | None = None,
    ai_unreviewed_only: bool = False,
) -> list[dict]:
    if limit < 1 or limit > 100:
        raise ValueError("Review queue limit must be between 1 and 100.")
    if offset < 0:
        raise ValueError("Review queue offset cannot be negative.")
    if status is not None and status not in REVIEW_STATUSES | {"all"}:
        raise ValueError(f"Unsupported BDNS review status: {status}.")
    conditions, params = _bdns_review_queue_filters(status, run_id, region_id, query)
    if ai_unreviewed_only:
        conditions += " AND NOT EXISTS (SELECT 1 FROM bdns_ai_review_suggestions seen WHERE seen.bdns_code = c.bdns_code AND seen.payload_sha256 = c.payload_sha256 AND seen.suggestion->>'automatic_review_policy_version' = '2')"
    rows = conn.execute(
        f"""SELECT c.data, c.review_status, c.payload_sha256, c.last_seen_at
                   ,latest.classification, ai.suggestion
            FROM bdns_calls c
            LEFT JOIN LATERAL (
                SELECT jsonb_build_object(
                    'event_id', e.classification_event_id,
                    'payload_sha256', e.payload_sha256,
                    'reviewer', e.reviewer,
                    'activities', e.activities,
                    'categories', e.categories,
                    'campaign_year', e.campaign_year,
                    'campaign_label', e.campaign_label,
                    'evidence', e.evidence,
                    'notes', e.notes,
                    'created_at', e.created_at
                ) AS classification
                FROM bdns_call_classification_events e
                WHERE e.bdns_code = c.bdns_code
                ORDER BY e.created_at DESC, e.classification_event_id DESC LIMIT 1
            ) latest ON TRUE
            LEFT JOIN LATERAL (
                SELECT jsonb_build_object(
                    'suggestion_id', s.suggestion_id,
                    'payload_sha256', s.payload_sha256,
                    'model', s.model,
                    'created_at', s.created_at,
                    'applied_decision', (SELECT d.decision FROM bdns_ai_review_decisions d
                                         WHERE d.suggestion_id = s.suggestion_id LIMIT 1),
                    'decision_reason', (SELECT d.reason FROM bdns_ai_review_decisions d
                                        WHERE d.suggestion_id = s.suggestion_id LIMIT 1),
                    'result', s.suggestion
                ) AS suggestion
                FROM bdns_ai_review_suggestions s
                WHERE s.bdns_code = c.bdns_code AND s.payload_sha256 = c.payload_sha256
                ORDER BY s.created_at DESC, s.suggestion_id DESC LIMIT 1
            ) ai ON TRUE
            WHERE {conditions}
            ORDER BY CASE c.review_status WHEN 'review_required' THEN 0 ELSE 1 END,
                     c.last_seen_at DESC, c.bdns_code LIMIT %s OFFSET %s""",
        (*params, limit, offset),
    ).fetchall()
    return [_review_item(*row) for row in rows]


def _bdns_review_queue_filters(
    status: str | None, run_id: int | None, region_id: int | None, query: str | None,
) -> tuple[str, list[Any]]:
    if status is not None and status not in REVIEW_STATUSES | {"all"}:
        raise ValueError(f"Unsupported BDNS review status: {status}.")
    conditions: list[str] = []
    params: list[Any] = []
    if status is None:
        conditions.append("c.review_status IN ('pending_review', 'review_required')")
    elif status != "all":
        conditions.append("c.review_status = %s")
        params.append(status)
    if run_id is not None or region_id is not None:
        membership = ["rc.bdns_code = c.bdns_code"]
        if run_id is not None:
            membership.append("rc.run_id = %s")
            params.append(run_id)
        if region_id is not None:
            membership.append("rc.region_id = %s")
            params.append(region_id)
        conditions.append(
            f"EXISTS (SELECT 1 FROM bdns_import_run_calls rc WHERE {' AND '.join(membership)})"
        )
    normalized_query = (query or "").strip()
    if normalized_query:
        conditions.append("(c.bdns_code ILIKE %s OR c.data #>> '{call,title}' ILIKE %s)")
        pattern = f"%{normalized_query}%"
        params.extend([pattern, pattern])
    return (" AND ".join(conditions) if conditions else "TRUE"), params


def count_bdns_review_queue(
    conn: psycopg.Connection, status: str | None = None, *, run_id: int | None = None,
    region_id: int | None = None, query: str | None = None,
) -> int:
    conditions, params = _bdns_review_queue_filters(status, run_id, region_id, query)
    row = conn.execute(f"SELECT count(*) FROM bdns_calls c WHERE {conditions}", params).fetchone()
    return row[0]


def record_bdns_ai_review_suggestion(
    conn: psycopg.Connection, bdns_code: str, expected_payload_sha256: str,
    model: str, suggestion: dict,
) -> dict | str:
    """Append an AI review draft only if it still matches the current source fingerprint."""
    row = conn.execute(
        "SELECT payload_sha256, review_status FROM bdns_calls WHERE bdns_code = %s FOR UPDATE",
        (bdns_code,),
    ).fetchone()
    if row is None:
        return "not_found"
    if row[0] != expected_payload_sha256:
        return "stale"
    saved = conn.execute(
        """INSERT INTO bdns_ai_review_suggestions
           (bdns_code, payload_sha256, model, suggestion)
           VALUES (%s, %s, %s, %s) RETURNING suggestion_id, created_at""",
        (bdns_code, expected_payload_sha256, model, Jsonb(suggestion)),
    ).fetchone()
    decision = suggestion.get("auto_decision")
    applied_decision = None
    if decision in {"accepted_for_extraction", "out_of_scope"} and row[1] in {"pending_review", "review_required"}:
        conn.execute(
            "UPDATE bdns_calls SET review_status = %s, updated_at = now() WHERE bdns_code = %s AND payload_sha256 = %s",
            (decision, bdns_code, expected_payload_sha256),
        )
        conn.execute(
            """INSERT INTO bdns_ai_review_decisions
               (bdns_code, payload_sha256, suggestion_id, decision, reason)
               VALUES (%s, %s, %s, %s, %s)""",
            (bdns_code, expected_payload_sha256, saved[0], decision,
             suggestion.get("auto_decision_reason", "Criterios automáticos de revisión superados.")),
        )
        applied_decision = decision
        if decision == "accepted_for_extraction":
            extraction = conn.execute(
                "SELECT source_fingerprint FROM bdns_extractions WHERE bdns_code = %s ORDER BY created_at DESC LIMIT 1",
                (bdns_code,),
            ).fetchone()
            if not extraction:
                _upsert_extraction_review_task(
                    conn, bdns_code=bdns_code, payload_sha256=expected_payload_sha256,
                    extraction_fingerprint="", issue_key="missing_extraction", issue_type="missing_data",
                    field="extraction", summary="El agente aceptó la convocatoria para extracción; todavía no hay datos extraídos.",
                    details={"next_step": "Run the BDNS document and extraction jobs."},
                )
    conn.commit()
    return {"suggestion_id": saved[0], "created_at": saved[1].isoformat(), "applied_decision": applied_decision}


def record_bdns_ai_finalization_event(
    conn: psycopg.Connection, *, bdns_code: str, payload_sha256: str,
    extraction_fingerprint: str, model: str, outcome: str, details: dict,
) -> int:
    if outcome not in {"published", "needs_human_review", "failed"}:
        raise ValueError("Unsupported AI finalization outcome.")
    row = conn.execute(
        """INSERT INTO bdns_ai_finalization_events
           (bdns_code, payload_sha256, extraction_fingerprint, model, outcome, details)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING event_id""",
        (bdns_code, payload_sha256, extraction_fingerprint, model, outcome, Jsonb(details)),
    ).fetchone()
    return row[0]


def read_bdns_ai_finalization_history(conn: psycopg.Connection, bdns_code: str, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        """SELECT event_id, payload_sha256, extraction_fingerprint, model, outcome, details, created_at
           FROM bdns_ai_finalization_events WHERE bdns_code = %s
           ORDER BY created_at DESC, event_id DESC LIMIT %s""",
        (bdns_code, limit),
    ).fetchall()
    return [{
        "event_id": row[0], "payload_sha256": row[1], "extraction_fingerprint": row[2],
        "model": row[3], "outcome": row[4], "details": row[5], "created_at": row[6].isoformat(),
    } for row in rows]


def read_bdns_review_filter_options(conn: psycopg.Connection) -> dict:
    runs = conn.execute(
        """SELECT r.run_id, r.started_at, count(DISTINCT rc.bdns_code)
           FROM bdns_import_runs r LEFT JOIN bdns_import_run_calls rc USING (run_id)
           GROUP BY r.run_id ORDER BY r.started_at DESC, r.run_id DESC LIMIT 100"""
    ).fetchall()
    regions = conn.execute(
        """SELECT DISTINCT br.region_id, br.description FROM bdns_regions br
           JOIN bdns_import_run_calls rc USING (region_id)
           ORDER BY br.description"""
    ).fetchall()
    return {
        "runs": [{"run_id": row[0], "started_at": row[1].isoformat(), "record_count": row[2]} for row in runs],
        "regions": [{"region_id": row[0], "territory": row[1]} for row in regions],
    }


def record_bdns_classification(
    conn: psycopg.Connection, *, bdns_code: str, expected_payload_sha256: str,
    reviewer: str, categories: list[str], activities: list[str], campaign_year: int | None,
    campaign_label: str | None, evidence: list[dict], notes: str,
) -> str:
    current = conn.execute(
        "SELECT payload_sha256, review_status FROM bdns_calls WHERE bdns_code = %s FOR UPDATE",
        (bdns_code,),
    ).fetchone()
    if current is None:
        return "not_found"
    if current[0] != expected_payload_sha256:
        return "stale"
    if current[1] != "accepted_for_extraction":
        return "invalid_state"
    conn.execute(
        """INSERT INTO bdns_call_classification_events (
               bdns_code, payload_sha256, reviewer, activities, categories,
               campaign_year, campaign_label, evidence, notes
           ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (bdns_code, expected_payload_sha256, reviewer, Jsonb(activities), Jsonb(categories),
         campaign_year, campaign_label, Jsonb(evidence), notes),
    )
    conn.commit()
    return "saved"


EXTRACTION_TASK_STATUSES = {"open", "needs_correction", "reviewed_candidate", "stale", "all"}
EXTRACTION_TASK_DECISIONS = {"reviewed_candidate", "needs_correction"}


def read_bdns_extraction_review_queue(
    conn: psycopg.Connection, status: str | None = None, limit: int = 50, offset: int = 0
) -> list[dict]:
    if limit < 1 or limit > 100 or offset < 0:
        raise ValueError("Invalid extraction review queue page.")
    if status is not None and status not in EXTRACTION_TASK_STATUSES:
        raise ValueError("Unsupported extraction review status.")
    where = "" if status in (None, "all") else "WHERE t.status = %s"
    params = (limit, offset) if not where else (status, limit, offset)
    rows = conn.execute(
        f"""SELECT t.task_id, t.bdns_code, t.payload_sha256, t.extraction_fingerprint,
                   t.issue_key, t.issue_type, t.field, t.summary, t.details, t.status,
                   t.created_at, c.data, EXISTS (
                     SELECT 1 FROM bdns_extractions e WHERE e.bdns_code = t.bdns_code
                       AND e.data->>'source_payload_sha256' = c.payload_sha256
                   )
            FROM bdns_extraction_review_tasks t JOIN bdns_calls c USING (bdns_code)
            {where} ORDER BY CASE t.status WHEN 'open' THEN 0 WHEN 'needs_correction' THEN 1 ELSE 2 END,
                      t.updated_at DESC, t.task_id LIMIT %s OFFSET %s""", params
    ).fetchall()
    items = []
    for row in rows:
        data = row[11] or {}
        items.append({
            "task_id": row[0], "bdns_code": row[1], "payload_sha256": row[2],
            "extraction_fingerprint": row[3], "issue_key": row[4], "issue_type": row[5],
            "field": row[6], "summary": row[7], "details": row[8], "status": row[9],
            "created_at": row[10].isoformat(), "title": data.get("call", {}).get("title"),
            "detail_url": data.get("source_identity", {}).get("detail_url"),
            "reliability": "extracted" if row[12] else "metadata_only",
        })
    return items


def count_bdns_extraction_review_queue(conn: psycopg.Connection, status: str | None = None) -> int:
    if status is not None and status not in EXTRACTION_TASK_STATUSES:
        raise ValueError("Unsupported extraction review status.")
    if status in (None, "all"):
        return conn.execute("SELECT count(*) FROM bdns_extraction_review_tasks").fetchone()[0]
    return conn.execute(
        "SELECT count(*) FROM bdns_extraction_review_tasks WHERE status = %s", (status,)
    ).fetchone()[0]


def review_bdns_extraction_task(
    conn: psycopg.Connection, task_id: int, expected_payload_sha256: str,
    expected_extraction_fingerprint: str, reviewer: str, decision: str, notes: str,
) -> str:
    reviewer, notes = reviewer.strip(), notes.strip()
    if len(reviewer) < 2 or len(reviewer) > 120 or not notes or len(notes) > 2000:
        raise ValueError("Reviewer identity and a reason of at most 2000 characters are required.")
    if decision not in EXTRACTION_TASK_DECISIONS:
        raise ValueError("Unsupported extraction review decision.")
    row = conn.execute(
        """SELECT t.bdns_code, t.payload_sha256, t.extraction_fingerprint, t.status,
                  c.payload_sha256, t.issue_type, EXISTS (
                    SELECT 1 FROM bdns_extractions e WHERE e.bdns_code = t.bdns_code
                      AND e.data->>'source_payload_sha256' = c.payload_sha256
                  ) FROM bdns_extraction_review_tasks t
           JOIN bdns_calls c USING (bdns_code) WHERE t.task_id = %s FOR UPDATE OF t, c""",
        (task_id,),
    ).fetchone()
    if not row:
        return "not_found"
    code, task_hash, task_extraction, status, current_hash, issue_type, has_current_extraction = row
    if task_hash != expected_payload_sha256 or task_extraction != (expected_extraction_fingerprint or ""):
        return "stale"
    if task_hash != current_hash or status == "stale":
        return "stale"
    if issue_type == "source_changed" and not has_current_extraction and decision == "reviewed_candidate":
        return "invalid_state"
    if status not in ("open", "needs_correction"):
        return "invalid_state"
    conn.execute(
        "UPDATE bdns_extraction_review_tasks SET status = %s, updated_at = now() WHERE task_id = %s",
        (decision, task_id),
    )
    _record_extraction_review_event(conn, task_id, reviewer, decision, notes)
    conn.commit()
    return decision


def review_bdns_call(
    conn: psycopg.Connection,
    bdns_code: str,
    expected_payload_sha256: str,
    reviewer: str,
    decision: str,
    notes: str,
) -> str:
    """Record a human source decision without changing aid reliability or catalog data."""
    reviewer = reviewer.strip()
    notes = notes.strip()
    if len(reviewer) < 2 or len(reviewer) > 120 or not notes or len(notes) > 2000:
        raise ValueError("Reviewer identity and a reason of at most 2000 characters are required.")
    if decision not in REVIEW_DECISIONS:
        raise ValueError("Review decisions may only accept for extraction or mark out of scope.")
    row = conn.execute(
        "SELECT payload_sha256 FROM bdns_calls WHERE bdns_code = %s FOR UPDATE",
        (bdns_code,),
    ).fetchone()
    if row is None:
        return "not_found"
    current_hash = row[0]
    if current_hash != expected_payload_sha256:
        return "stale"
    conn.execute(
        """UPDATE bdns_calls SET review_status = %s, updated_at = now()
           WHERE bdns_code = %s AND payload_sha256 = %s""",
        (decision, bdns_code, expected_payload_sha256),
    )
    conn.execute(
        """INSERT INTO bdns_call_reviews
           (bdns_code, payload_sha256, reviewer, decision, notes)
           VALUES (%s, %s, %s, %s, %s)""",
        (bdns_code, expected_payload_sha256, reviewer, decision, notes),
    )
    if decision == "accepted_for_extraction":
        extraction = conn.execute(
            """SELECT source_fingerprint FROM bdns_extractions WHERE bdns_code = %s
               ORDER BY created_at DESC LIMIT 1""", (bdns_code,)
        ).fetchone()
        if not extraction:
            _upsert_extraction_review_task(
                conn, bdns_code=bdns_code, payload_sha256=expected_payload_sha256,
                extraction_fingerprint="", issue_key="missing_extraction", issue_type="missing_data",
                field="extraction", summary="Convocatoria aprobada para extracción; todavía no hay datos extraídos.",
                details={"next_step": "Run the BDNS document and extraction jobs."},
            )
    conn.commit()
    return decision


def read_bdns_call_reviews(conn: psycopg.Connection, bdns_code: str, limit: int = 50) -> list[dict]:
    if limit < 1 or limit > 100:
        raise ValueError("Review history limit must be between 1 and 100.")
    rows = conn.execute(
        """SELECT reviewer, decision, notes, payload_sha256, created_at
           FROM bdns_call_reviews WHERE bdns_code = %s
           ORDER BY created_at DESC, review_id DESC LIMIT %s""",
        (bdns_code, limit),
    ).fetchall()
    return [
        {"reviewer": row[0], "decision": row[1], "notes": row[2],
         "payload_sha256": row[3], "created_at": row[4].isoformat()}
        for row in rows
    ]


def upsert_bdns_regions(conn: psycopg.Connection, regions: list[dict]) -> None:
    """Refresh the current official region tree while preserving BDNS identifiers."""
    current_ids = [region["region_id"] for region in regions]
    for region in regions:
        conn.execute(
            """INSERT INTO bdns_regions (region_id, description, nuts_code, parent_region_id, depth)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (region_id) DO UPDATE SET
                   description = EXCLUDED.description, nuts_code = EXCLUDED.nuts_code,
                   parent_region_id = EXCLUDED.parent_region_id, depth = EXCLUDED.depth,
                   updated_at = now()""",
            (region["region_id"], region["description"], region.get("nuts_code"),
             region.get("parent_region_id"), region["depth"]),
        )
    if current_ids:
        conn.execute("DELETE FROM bdns_regions WHERE NOT (region_id = ANY(%s))", (current_ids,))
    conn.commit()


def start_bdns_import_run(
    conn: psycopg.Connection,
    regions: tuple[int, ...],
    search_terms: tuple[str, ...],
    max_pages: int,
    page_size: int,
) -> int:
    row = conn.execute(
        """INSERT INTO bdns_import_runs
           (status, region_ids, search_terms, max_pages, page_size)
           VALUES ('running', %s, %s, %s, %s) RETURNING run_id""",
        (Jsonb(list(regions)), Jsonb(list(search_terms)), max_pages, page_size),
    ).fetchone()
    conn.commit()
    return row[0]


def finish_bdns_import_run(
    conn: psycopg.Connection,
    run_id: int,
    *,
    status: str,
    candidate_count: int = 0,
    indexed_call_count: int = 0,
    observations: list[dict] | None = None,
    error_summary: str | None = None,
) -> None:
    if status not in {"completed", "failed"}:
        raise ValueError("An import run can only finish as completed or failed.")
    for item in observations or []:
        conn.execute(
            """INSERT INTO bdns_import_run_queries
               (run_id, region_id, search_term, activity_scope, candidate_count,
                indexed_call_count, page_limit_reached)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (run_id, region_id, search_term) DO UPDATE SET
                   activity_scope = EXCLUDED.activity_scope,
                   candidate_count = EXCLUDED.candidate_count,
                   indexed_call_count = EXCLUDED.indexed_call_count,
                   page_limit_reached = EXCLUDED.page_limit_reached,
                   queried_at = now()""",
            (run_id, item["region_id"], item["search_term"], item["activity_scope"],
             item["candidate_count"], item["indexed_call_count"], item["page_limit_reached"]),
        )
        if status == "completed":
            for bdns_code in item.get("candidate_codes", []):
                conn.execute(
                    """INSERT INTO bdns_import_run_calls (run_id, bdns_code, region_id, search_term)
                       VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                    (run_id, bdns_code, item["region_id"], item["search_term"]),
                )
    conn.execute(
        """UPDATE bdns_import_runs SET status = %s, completed_at = now(),
                  candidate_count = %s, indexed_call_count = %s, error_summary = %s
           WHERE run_id = %s""",
        (status, candidate_count, indexed_call_count, error_summary, run_id),
    )
    conn.commit()


def read_bdns_coverage(conn: psycopg.Connection, run_limit: int = 20) -> dict:
    """Report observed index/query coverage and explicitly retain unmeasured gaps."""
    if run_limit < 1 or run_limit > 100:
        raise ValueError("Coverage run_limit must be between 1 and 100.")
    indexed_call_count = conn.execute("SELECT count(*) FROM bdns_calls").fetchone()[0]
    runs = conn.execute(
        """SELECT run_id, started_at, completed_at, status, region_ids, search_terms,
                  max_pages, page_size, candidate_count, indexed_call_count, error_summary
           FROM bdns_import_runs ORDER BY started_at DESC, run_id DESC LIMIT %s""",
        (run_limit,),
    ).fetchall()
    run_items = []
    for row in runs:
        queries = conn.execute(
            """SELECT q.region_id, r.description, q.search_term, q.activity_scope,
                      q.candidate_count, q.indexed_call_count, q.page_limit_reached, q.queried_at
               FROM bdns_import_run_queries q LEFT JOIN bdns_regions r ON r.region_id = q.region_id
               WHERE q.run_id = %s ORDER BY q.region_id, q.search_term""",
            (row[0],),
        ).fetchall()
        run_items.append({
            "run_id": row[0],
            "started_at": row[1].isoformat(),
            "completed_at": row[2].isoformat() if row[2] else None,
            "status": row[3],
            "region_ids": row[4],
            "search_terms": row[5],
            "max_pages": row[6],
            "page_size": row[7],
            "candidate_count": row[8],
            "indexed_call_count": row[9],
            "error_summary": row[10],
            "queries": [{
                "region_id": query[0], "territory": query[1] or f"BDNS region {query[0]}",
                "search_term": query[2], "activity_scope": query[3],
                "candidate_count": query[4], "indexed_call_count": query[5],
                "page_limit_reached": query[6], "queried_at": query[7].isoformat(),
            } for query in queries],
        })

    latest_queries = conn.execute(
        """SELECT DISTINCT ON (q.region_id) q.region_id, q.run_id, q.queried_at
           FROM bdns_import_run_queries q ORDER BY q.region_id, q.queried_at DESC, q.run_id DESC"""
    ).fetchall()
    regions = conn.execute(
        "SELECT region_id, description, nuts_code, parent_region_id, depth FROM bdns_regions ORDER BY depth, description"
    ).fetchall()
    latest_by_region = {row[0]: row[1] for row in latest_queries}
    region_items = []
    for region in regions:
        last_run_id = latest_by_region.get(region[0])
        query_totals = conn.execute(
            """SELECT COALESCE(sum(candidate_count), 0), COALESCE(sum(indexed_call_count), 0),
                      count(*), bool_or(page_limit_reached)
               FROM bdns_import_run_queries WHERE region_id = %s AND run_id = %s""",
            (region[0], last_run_id),
        ).fetchone() if last_run_id is not None else (0, 0, 0, False)
        if not query_totals[2]:
            coverage_status = "not_checked"
        elif query_totals[1] > 0:
            coverage_status = "indexed_in_bounded_query"
        elif query_totals[0] > 0:
            coverage_status = "candidates_not_indexed"
        else:
            coverage_status = "no_candidates_in_bounded_query"
        region_items.append({
            "region_id": region[0], "territory": region[1], "nuts_code": region[2],
            "parent_region_id": region[3], "depth": region[4], "last_run_id": last_run_id,
            "last_candidate_count": query_totals[0], "last_indexed_call_count": query_totals[1],
            "last_query_count": query_totals[2], "page_limit_reached": bool(query_totals[3]),
            "status": coverage_status,
        })

    activity_rows = conn.execute(
        """SELECT COALESCE(data #>> '{call,farm_activity_classification,status}', 'unclassified'),
                  data #> '{call,farm_activity_classification,activities}', count(*)
           FROM bdns_calls GROUP BY 1, 2"""
    ).fetchall()
    activity_counts = {"agriculture": 0, "livestock": 0, "mixed": 0, "unclassified": 0}
    for status, activities, count in activity_rows:
        actual_activities = activities if isinstance(activities, list) else []
        if actual_activities:
            for activity in actual_activities:
                if activity in activity_counts:
                    activity_counts[activity] += count
        else:
            activity_counts["unclassified"] += count

    purpose_rows = conn.execute(
        """SELECT data #>> '{call,purpose,label}', count(*) FROM bdns_calls
           WHERE NULLIF(data #>> '{call,purpose,label}', '') IS NOT NULL
           GROUP BY 1 ORDER BY 2 DESC, 1"""
    ).fetchall()
    sector_rows = conn.execute(
        """SELECT item->>'label', count(DISTINCT c.bdns_code)
           FROM bdns_calls c CROSS JOIN LATERAL jsonb_array_elements(
             CASE WHEN jsonb_typeof(c.data #> '{call,economic_sectors}') = 'array'
                  THEN c.data #> '{call,economic_sectors}' ELSE '[]'::jsonb END
           ) AS sectors(item) WHERE NULLIF(item->>'label', '') IS NOT NULL
           GROUP BY 1 ORDER BY 2 DESC, 1"""
    ).fetchall()
    beneficiary_rows = conn.execute(
        """SELECT item->>'label', count(DISTINCT c.bdns_code)
           FROM bdns_calls c CROSS JOIN LATERAL jsonb_array_elements(
             CASE WHEN jsonb_typeof(c.data #> '{call,beneficiary_categories}') = 'array'
                  THEN c.data #> '{call,beneficiary_categories}' ELSE '[]'::jsonb END
           ) AS categories(item) WHERE NULLIF(item->>'label', '') IS NOT NULL
           GROUP BY 1 ORDER BY 2 DESC, 1"""
    ).fetchall()
    product_sector_rows = conn.execute(
        """SELECT item->>'descripcion', count(DISTINCT c.bdns_code)
           FROM bdns_calls c CROSS JOIN LATERAL jsonb_array_elements(
             CASE WHEN jsonb_typeof(c.data #> '{call,product_sectors}') = 'array'
                  THEN c.data #> '{call,product_sectors}' ELSE '[]'::jsonb END
           ) AS sectors(item) WHERE NULLIF(item->>'descripcion', '') IS NOT NULL
           GROUP BY 1 ORDER BY 2 DESC, 1"""
    ).fetchall()
    campaign_rows = conn.execute(
        """SELECT COALESCE(data #>> '{call,campaign,year}', 'unclassified'),
                  data #>> '{call,campaign,label}', count(*)
           FROM bdns_calls GROUP BY 1, 2 ORDER BY 1"""
    ).fetchall()
    activity_queries = conn.execute(
        """SELECT activity_scope, count(*), COALESCE(sum(candidate_count), 0),
                  COALESCE(sum(indexed_call_count), 0), max(queried_at)
           FROM bdns_import_run_queries GROUP BY activity_scope ORDER BY activity_scope"""
    ).fetchall()
    activity_query_items = [{
        "activity": row[0], "query_count": row[1], "candidate_count": row[2],
        "indexed_call_count": row[3], "last_queried_at": row[4].isoformat(),
    } for row in activity_queries]

    confirmed_classification_rows = conn.execute(
        """WITH latest AS (
               SELECT DISTINCT ON (e.bdns_code)
                      e.bdns_code, e.categories, e.activities, e.campaign_year, e.campaign_label
               FROM bdns_call_classification_events e
               JOIN bdns_calls c ON c.bdns_code = e.bdns_code
                                AND c.payload_sha256 = e.payload_sha256
                                AND c.review_status = 'accepted_for_extraction'
               ORDER BY e.bdns_code, e.created_at DESC, e.classification_event_id DESC
           )
           SELECT rc.region_id, COALESCE(r.description, 'BDNS ' || rc.region_id::text),
                  activity.value, category.value, latest.campaign_year,
                  latest.campaign_label, count(DISTINCT latest.bdns_code)
           FROM latest
           JOIN bdns_import_run_calls rc ON rc.bdns_code = latest.bdns_code
           LEFT JOIN bdns_regions r ON r.region_id = rc.region_id
           CROSS JOIN LATERAL jsonb_array_elements_text(latest.activities) AS activity(value)
           CROSS JOIN LATERAL jsonb_array_elements_text(latest.categories) AS category(value)
           GROUP BY rc.region_id, r.description, activity.value, category.value,
                    latest.campaign_year, latest.campaign_label
           ORDER BY r.description, category.value, activity.value, latest.campaign_year"""
    ).fetchall()
    confirmed_classifications = [{
        "region_id": row[0], "territory": row[1], "activity": row[2], "category": row[3],
        "campaign_year": row[4], "campaign_label": row[5], "call_count": row[6],
    } for row in confirmed_classification_rows]
    from app.bdns.triage import CATEGORY_RULES

    classification_cell_counts: dict[tuple[int, str, str], dict[str, int]] = {}
    for item in confirmed_classifications:
        cell = classification_cell_counts.setdefault(
            (item["region_id"], item["activity"], item["category"]),
            {"call_count": 0, "campaign_unclassified_count": 0},
        )
        cell["call_count"] += item["call_count"]
        if item["campaign_year"] is None:
            cell["campaign_unclassified_count"] += item["call_count"]
    classification_gaps = []
    for region in region_items:
        if not region["last_query_count"]:
            continue
        for activity in ("agriculture", "livestock", "mixed"):
            for category, _priority, _terms in CATEGORY_RULES:
                cell = classification_cell_counts.get(
                    (region["region_id"], activity, category),
                    {"call_count": 0, "campaign_unclassified_count": 0},
                )
                classification_gaps.append({
                    "region_id": region["region_id"],
                    "territory": region["territory"],
                    "last_run_id": region["last_run_id"],
                    "activity": activity,
                    "category": category,
                    "classified_call_count": cell["call_count"],
                    "campaign_unclassified_count": cell["campaign_unclassified_count"],
                    "status": "classified" if cell["call_count"] else "not_classified_yet",
                })
    accepted_candidate_count = conn.execute(
        "SELECT count(*) FROM bdns_calls WHERE review_status = 'accepted_for_extraction'"
    ).fetchone()[0]
    current_classified_candidate_count = conn.execute(
        """SELECT count(*) FROM (
               SELECT DISTINCT ON (e.bdns_code) e.bdns_code
               FROM bdns_call_classification_events e
               JOIN bdns_calls c ON c.bdns_code = e.bdns_code
                                AND c.payload_sha256 = e.payload_sha256
                                AND c.review_status = 'accepted_for_extraction'
               ORDER BY e.bdns_code, e.created_at DESC, e.classification_event_id DESC
           ) classified"""
    ).fetchone()[0]

    gaps = {
        "territories_not_checked": [item["territory"] for item in region_items if item["status"] == "not_checked"],
        "territories_without_candidates_in_latest_bounded_query": [
            item["territory"] for item in region_items if item["status"] == "no_candidates_in_bounded_query"
        ],
        "unclassified_farm_activity_calls": activity_counts["unclassified"],
        "unclassified_campaign_calls": sum(row[2] for row in campaign_rows if row[0] == "unclassified"),
        "accepted_candidates_without_current_classification": max(
            0, accepted_candidate_count - current_classified_candidate_count
        ),
        "controlled_aid_category_mapping": "not_implemented",
    }
    return {
        "coverage_claim": "bounded_queries_and_human_confirmed_classifications",
        "generated_at": conn.execute("SELECT now()::text").fetchone()[0],
        "indexed_call_count": indexed_call_count,
        "last_import_run": run_items[0] if run_items else None,
        "recent_runs": run_items,
        "territories": region_items,
        "activities": [
            {"activity": name, "indexed_call_count": activity_counts[name],
             "search_queries": next((item for item in activity_query_items if item["activity"] == name), None)}
            for name in ("agriculture", "livestock", "mixed", "unclassified")
        ],
        "source_categories": {
            "purposes": [{"label": row[0], "indexed_call_count": row[1]} for row in purpose_rows],
            "economic_sectors": [{"label": row[0], "indexed_call_count": row[1]} for row in sector_rows],
            "beneficiary_categories": [{"label": row[0], "indexed_call_count": row[1]} for row in beneficiary_rows],
            "product_sectors": [{"label": row[0], "indexed_call_count": row[1]} for row in product_sector_rows],
        },
        "campaigns": [{"year": row[0], "label": row[1], "indexed_call_count": row[2]} for row in campaign_rows],
        "confirmed_classifications": confirmed_classifications,
        "classification_gaps": classification_gaps,
        "gaps": gaps,
        "interpretation": "A bounded query with no candidates does not prove that no relevant aid exists. Imported records are source metadata, and absent activity, category or campaign classifications remain unknown.",
    }


def record_bdns_document(conn: psycopg.Connection, item: dict) -> None:
    """Upsert current source document state and retain each downloaded content hash."""
    previous = conn.execute(
        """SELECT status, content_sha256 FROM bdns_documents
           WHERE bdns_code = %s AND bdns_document_id = %s""",
        (item["bdns_code"], item["bdns_document_id"]),
    ).fetchone()
    if previous and (previous[0], previous[1]) != (item["status"], item.get("content_sha256")):
        _invalidate_bdns_verification(
            conn, item["bdns_code"],
            f"Cambió el estado o el contenido del documento BDNS {item['bdns_document_id']}; se reabrió la verificación.",
        )
    conn.execute(
        """INSERT INTO bdns_documents (
               bdns_code, bdns_document_id, source_metadata, status, content_type,
               content_sha256, stored_object_uri, downloaded_size_bytes, last_error
           ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (bdns_code, bdns_document_id) DO UPDATE SET
               source_metadata = EXCLUDED.source_metadata,
               status = EXCLUDED.status,
               content_type = EXCLUDED.content_type,
               content_sha256 = EXCLUDED.content_sha256,
               stored_object_uri = EXCLUDED.stored_object_uri,
               downloaded_size_bytes = EXCLUDED.downloaded_size_bytes,
               last_error = EXCLUDED.last_error,
               updated_at = now()""",
        (
            item["bdns_code"], item["bdns_document_id"], Jsonb(item["source_metadata"]),
            item["status"], item.get("content_type"), item.get("content_sha256"),
            item.get("stored_object_uri"), item.get("downloaded_size_bytes"), item.get("last_error"),
        ),
    )
    if item["status"] == "downloaded":
        conn.execute(
            """INSERT INTO bdns_document_versions (
                   bdns_code, bdns_document_id, content_sha256, content_type,
                   stored_object_uri, size_bytes
               ) VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (bdns_code, bdns_document_id, content_sha256) DO NOTHING""",
            (
                item["bdns_code"], item["bdns_document_id"], item["content_sha256"],
                item["content_type"], item["stored_object_uri"], item["downloaded_size_bytes"],
            ),
        )


def upsert_blocks(conn: psycopg.Connection, blocks: dict) -> None:
    for name, reqs in blocks.items():
        conn.execute(
            """INSERT INTO blocks (name, requirements) VALUES (%s, %s)
               ON CONFLICT (name) DO UPDATE
               SET requirements = EXCLUDED.requirements, updated_at = now()""",
            (name, Jsonb(reqs)),
        )


def read_aids(conn: psycopg.Connection) -> list[dict]:
    return [row[0] for row in conn.execute("SELECT data FROM aids ORDER BY id").fetchall()]


def read_blocks(conn: psycopg.Connection) -> dict:
    return {n: r for n, r in conn.execute("SELECT name, requirements FROM blocks").fetchall()}
