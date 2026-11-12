"""Stable source-payload fingerprints, field-level diffs, and link extraction."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlsplit


def canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
    """Serialize JSON deterministically so whitespace and object key order do not count as changes."""
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def changed_paths(previous: Any, current: Any, prefix: str = "") -> list[str]:
    """Return stable JSON paths whose source values changed, without storing source values."""
    if isinstance(previous, dict) and isinstance(current, dict):
        result = []
        for key in sorted(set(previous) | set(current)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in previous or key not in current:
                result.append(path)
            else:
                result.extend(changed_paths(previous[key], current[key], path))
        return result
    if previous != current:
        return [prefix or "$"]
    return []


def extract_source_links(record: dict[str, Any]) -> list[dict[str, str]]:
    """Extract stable references to the call, bases, application page and documents."""
    identity = record.get("source_identity", {})
    code = str(identity.get("bdns_code", "")).strip()
    links: dict[tuple[str, str, str], dict[str, str]] = {}

    def add(resource_type: str, resource_key: str, url: Any) -> None:
        if not isinstance(url, str):
            return
        candidate = url.strip()
        try:
            parsed = urlsplit(candidate)
        except ValueError:
            return
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return
        key = (resource_type, resource_key, candidate)
        links[key] = {
            "bdns_code": code,
            "resource_type": resource_type,
            "resource_key": resource_key,
            "url": candidate,
        }

    add("call_detail", code, identity.get("detail_url"))
    call = record.get("call", {})
    sources = record.get("sources", {})
    add("application_portal", "application", record.get("application", {}).get("application_portal_url"))
    bases = sources.get("regulatory_bases", {})
    add("regulatory_bases", "bases", bases.get("url") if isinstance(bases, dict) else None)
    state_aid = call.get("state_aid", {})
    add("state_aid", "regulation", state_aid.get("url") if isinstance(state_aid, dict) else None)
    for document in sources.get("documents", []):
        if isinstance(document, dict):
            document_id = document.get("bdns_document_id")
            add("document", str(document_id) if document_id is not None else "unknown", document.get("download_url"))
    for index, announcement in enumerate(sources.get("announcements", [])):
        if not isinstance(announcement, dict):
            continue
        announcement_id = announcement.get("id") or announcement.get("cve") or index
        for name, value in announcement.items():
            if isinstance(value, str) and name.lower().startswith("url"):
                add("announcement", f"{announcement_id}:{name}", value)
    return [links[key] for key in sorted(links)]
