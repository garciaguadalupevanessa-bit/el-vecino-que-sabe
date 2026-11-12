"""Bounded, validated storage for official BDNS PDF documents."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from app.bdns import BDNSClient, BDNSClientError, BDNSDocumentError
from app.core import config
from app.db import database as db


MAX_DOCUMENTS_DEFAULT = 10


class DocumentStorage:
    """Write PDFs to immutable content-addressed paths below one storage root."""

    def __init__(self, root: str | Path, max_bytes: int = 25 * 1024 * 1024):
        self.root = Path(root).expanduser().resolve()
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive.")
        self.max_bytes = max_bytes

    def save(self, bdns_code: str, document_id: int, content: bytes) -> tuple[str, str]:
        if not bdns_code.strip():
            raise ValueError("bdns_code cannot be empty.")
        if isinstance(document_id, bool) or not isinstance(document_id, int) or document_id < 1:
            raise ValueError("document_id must be a positive integer.")
        if len(content) > self.max_bytes:
            raise BDNSDocumentError(f"Document exceeds the {self.max_bytes}-byte storage limit.")
        if not content.startswith(b"%PDF-"):
            raise BDNSDocumentError("Document content is not a PDF file.")

        digest = hashlib.sha256(content).hexdigest()
        call_key = hashlib.sha256(bdns_code.strip().encode("utf-8")).hexdigest()[:16]
        relative = Path(call_key) / str(document_id) / f"{digest}.pdf"
        destination = (self.root / relative).resolve()
        if not destination.is_relative_to(self.root):
            raise ValueError("Resolved document path escaped the configured storage root.")
        destination.parent.mkdir(parents=True, exist_ok=True)

        if not destination.exists() or self._file_sha256(destination) != digest:
            descriptor, temporary_name = tempfile.mkstemp(prefix=".bdns-", suffix=".tmp", dir=destination.parent)
            try:
                with os.fdopen(descriptor, "wb") as temporary:
                    temporary.write(content)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.replace(temporary_name, destination)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        return relative.as_posix(), digest

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


def download_call_documents(
    client: BDNSClient,
    conn: Any,
    records: list[dict[str, Any]],
    storage: DocumentStorage,
    *,
    max_documents: int = MAX_DOCUMENTS_DEFAULT,
    record_document: Callable[[Any, dict[str, Any]], None] = db.record_bdns_document,
) -> list[dict[str, Any]]:
    """Download at most the requested number of documents and persist provenance/status."""
    if max_documents < 1:
        raise ValueError("max_documents must be at least one.")
    results = []
    for record in records:
        identity = record.get("source_identity", {})
        code = str(identity.get("bdns_code", "")).strip()
        for document in record.get("sources", {}).get("documents", []):
            if len(results) >= max_documents:
                conn.commit()
                return results
            document_id = document.get("bdns_document_id")
            if isinstance(document_id, bool) or not isinstance(document_id, int) or document_id < 1:
                continue
            item = {
                "bdns_code": code,
                "bdns_document_id": document_id,
                "source_metadata": document,
                "status": "failed",
                "content_type": None,
                "content_sha256": None,
                "stored_object_uri": None,
                "downloaded_size_bytes": None,
                "last_error": None,
            }
            try:
                content, content_type = client.download_document(
                    document_id, max_bytes=storage.max_bytes
                )
                object_uri, digest = storage.save(code, document_id, content)
                item.update({
                    "status": "downloaded",
                    "content_type": content_type,
                    "content_sha256": digest,
                    "stored_object_uri": object_uri,
                    "downloaded_size_bytes": len(content),
                })
            except BDNSDocumentError as exc:
                item.update({"status": "rejected", "last_error": str(exc)[:1000]})
            except (BDNSClientError, OSError) as exc:
                item.update({"status": "failed", "last_error": str(exc)[:1000]})
            record_document(conn, item)
            results.append(item)
    conn.commit()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely download and inventory BDNS call PDFs.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--bdns-code", help="Import documents for one previously imported call.")
    scope.add_argument("--all", action="store_true", help="Use imported calls, bounded by --max-documents.")
    parser.add_argument("--max-documents", type=int, default=MAX_DOCUMENTS_DEFAULT)
    parser.add_argument("--url", default=config.DATABASE_URL, help="Database URL (defaults to DATABASE_URL).")
    args = parser.parse_args(argv)
    try:
        if not args.url:
            raise ValueError("DATABASE_URL is missing.")
        if args.max_documents < 1:
            raise ValueError("max-documents must be positive.")
        if args.bdns_code is not None and not args.bdns_code.strip():
            raise ValueError("bdns-code cannot be empty.")
        storage = DocumentStorage(config.BDNS_DOCUMENT_STORAGE_DIR, config.BDNS_DOCUMENT_MAX_BYTES)
        with BDNSClient.from_config() as client, db.connect(args.url) as conn:
            db.create_schema(conn)
            records = db.read_bdns_calls(conn, None if args.all else args.bdns_code.strip())
            if args.bdns_code is not None and not records:
                raise ValueError(f"BDNS call {args.bdns_code!r} is not in the imported call table.")
            results = download_call_documents(
                client, conn, records, storage, max_documents=args.max_documents
            )
        counts = {status: sum(item["status"] == status for item in results)
                  for status in ("downloaded", "rejected", "failed")}
        print(
            f"Processed {len(results)} BDNS documents: {counts['downloaded']} downloaded, "
            f"{counts['rejected']} rejected, {counts['failed']} failed. "
            f"Maximum size: {storage.max_bytes} bytes."
        )
        for item in results:
            print(
                f"{item['bdns_code']}/{item['bdns_document_id']}: {item['status']}"
                + (f" ({item['last_error']})" if item["last_error"] else "")
            )
        return 0 if counts["failed"] == 0 and counts["rejected"] == 0 else 1
    except (BDNSClientError, OSError, ValueError, RuntimeError) as exc:
        print(f"BDNS document download failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
