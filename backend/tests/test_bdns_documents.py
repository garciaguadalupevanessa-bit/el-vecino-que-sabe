import hashlib
from pathlib import Path

import pytest

from app.bdns.client import BDNSDocumentError
from app.bdns.documents import DocumentStorage, download_call_documents
from app.db.database import record_bdns_document


PDF = b"%PDF-1.7\nunit test document"


def test_storage_is_content_addressed_and_keeps_changed_versions(tmp_path):
    storage = DocumentStorage(tmp_path, max_bytes=1000)
    first_uri, first_hash = storage.save("920758", 17, PDF)
    second_uri, second_hash = storage.save("920758", 17, PDF + b" changed")
    repeated_uri, repeated_hash = storage.save("920758", 17, PDF)

    assert first_hash == hashlib.sha256(PDF).hexdigest()
    assert repeated_hash == first_hash and repeated_uri == first_uri
    assert second_hash != first_hash and second_uri != first_uri
    assert (Path(tmp_path) / first_uri).read_bytes() == PDF
    assert (Path(tmp_path) / second_uri).read_bytes() == PDF + b" changed"
    assert len(list(Path(tmp_path).rglob("*.pdf"))) == 2


def test_storage_rejects_non_pdf_and_oversized_content(tmp_path):
    storage = DocumentStorage(tmp_path, max_bytes=10)
    with pytest.raises(BDNSDocumentError, match="not a PDF"):
        storage.save("920758", 17, b"not a pdf")
    with pytest.raises(BDNSDocumentError, match="exceeds"):
        storage.save("920758", 17, b"%PDF-" + b"x" * 10)


def test_downloader_records_provenance_and_respects_document_bound(tmp_path):
    class FakeClient:
        requested = []

        def download_document(self, document_id, *, max_bytes):
            self.requested.append((document_id, max_bytes))
            return PDF, "application/pdf"

    class FakeConnection:
        commits = 0

        def commit(self):
            self.commits += 1

    records = [{
        "source_identity": {"bdns_code": "920758"},
        "sources": {"documents": [
            {"bdns_document_id": 17, "filename": "source.pdf", "download_url": "https://source.example/17"},
            {"bdns_document_id": 18, "filename": "next.pdf"},
        ]},
    }]
    client = FakeClient()
    conn = FakeConnection()
    inventory = []
    result = download_call_documents(
        client, conn, records, DocumentStorage(tmp_path), max_documents=1,
        record_document=lambda connection, item: inventory.append(item),
    )

    assert len(result) == 1
    assert client.requested == [(17, 25 * 1024 * 1024)]
    assert result[0]["status"] == "downloaded"
    assert result[0]["source_metadata"]["download_url"].endswith("/17")
    assert result[0]["content_sha256"] == hashlib.sha256(PDF).hexdigest()
    assert (Path(tmp_path) / result[0]["stored_object_uri"]).exists()
    assert inventory == result and conn.commits == 1


def test_downloader_records_rejected_document_without_saving(tmp_path):
    class FakeClient:
        def download_document(self, document_id, *, max_bytes):
            raise BDNSDocumentError("unsupported content")

    class FakeConnection:
        def commit(self):
            pass

    record = {
        "source_identity": {"bdns_code": "920758"},
        "sources": {"documents": [{"bdns_document_id": 17}]},
    }
    inventory = []
    result = download_call_documents(
        FakeClient(), FakeConnection(), [record], DocumentStorage(tmp_path),
        record_document=lambda connection, item: inventory.append(item),
    )
    assert result[0]["status"] == "rejected"
    assert result[0]["content_sha256"] is None
    assert inventory == result
    assert list(Path(tmp_path).rglob("*.pdf")) == []


def test_database_inventory_upserts_current_state_and_keeps_content_versions():
    class RecordingConnection:
        def __init__(self):
            self.statements = []

        def execute(self, statement, params):
            self.statements.append((statement, params))
            class EmptyResult:
                @staticmethod
                def fetchone():
                    return None
            return EmptyResult()

    conn = RecordingConnection()
    item = {
        "bdns_code": "920758",
        "bdns_document_id": 17,
        "source_metadata": {"filename": "source.pdf"},
        "status": "downloaded",
        "content_type": "application/pdf",
        "content_sha256": "a" * 64,
        "stored_object_uri": "abc/17/sha.pdf",
        "downloaded_size_bytes": len(PDF),
        "last_error": None,
    }
    record_bdns_document(conn, item)
    assert len(conn.statements) == 3
    assert conn.statements[0][0].lstrip().startswith("SELECT status, content_sha256")
    assert "ON CONFLICT (bdns_code, bdns_document_id) DO UPDATE" in conn.statements[1][0]
    assert "ON CONFLICT (bdns_code, bdns_document_id, content_sha256) DO NOTHING" in conn.statements[2][0]
    assert conn.statements[2][1][2] == "a" * 64
