# BDNS source-document preservation

The document downloader is `backend/app/bdns/documents.py`, with bounded binary transfer in `backend/app/bdns/client.py`. It reads previously imported source records and stores each supported call PDF separately from the call metadata and user-facing aid catalog.

## Initial safety limits

- Only PDF is accepted. The response media type must be `application/pdf`, `application/octet-stream`, or absent, and the bytes must begin with the PDF signature `%PDF-`. HTML error pages, ZIP bundles and other formats are rejected; no archive is extracted.
- A document is limited to 25 MiB by default. Both `Content-Length` and streamed bytes are checked, so an absent or false length cannot bypass the cap.
- Downloads are sequential, use the client's HTTPS/TLS verification, timeout, retry and pacing settings, and are additionally limited to ten documents per command by default.
- The source filename is metadata only and is never used to build a local path. Storage paths use a hash of the BDNS code, numeric document ID and SHA-256 of the bytes.
- Writes are atomic. Re-downloading identical content is idempotent; changed content is stored at a new content-hash path. Postgres keeps a current inventory/status row and append-only content-version rows with source metadata, source URL, hash, MIME type, byte count and storage URI.
- Rejected/failed downloads are recorded without publishing a storage URI. They do not change the call's `metadata_only` reliability or farm classification.

Limits are configurable with `BDNS_DOCUMENT_MAX_BYTES` and `BDNS_DOCUMENT_STORAGE_DIR`. Docker Compose mounts the storage directory on the persistent `bdns_documents` volume.

## Validate on the Aragón record

The imported BDNS `920758` sample has document ID `1515086`. From `backend`, run the PDF client and storage tests:

```powershell
python -m pytest -q tests/test_bdns_client.py tests/test_bdns_importer.py tests/test_bdns_documents.py
```

Then return to the project root, rebuild the backend image so the persistent volume is writable by its non-root service user, and download one live document:

```powershell
cd ..
docker compose build backend
docker compose run --rm backend python -m app.bdns.documents --bdns-code 920758 --max-documents 5
```

The command requires the call to exist in `bdns_calls` and Postgres to be available. It reports per-document status. For a downloaded document, query provenance with:

```powershell
docker compose exec -T db psql -U elvecino -d elvecinoquesabe -c "SELECT bdns_code, bdns_document_id, status, content_type, downloaded_size_bytes, content_sha256, stored_object_uri FROM bdns_documents WHERE bdns_code = '920758';"
```

The BDNS source inventory lists `515337` bytes for document `1515086`; the stored length and SHA-256 returned by this implementation are measured from the actual response. This initial pipeline preserves PDFs only and does not parse their content or decide that the call is relevant to farms.

**Live validation completed:** the client reported `1 downloaded, 0 rejected, 0 failed`. BDNS served the PDF as `application/octet-stream`; the `%PDF-` signature check passed. Postgres recorded 515337 bytes, SHA-256 `b40931489954f6fe851867bf25e192e19c64cc36bea6ec0f0b914eb0dc6b5222`, and storage URI `b4f11e62c83bc326/1515086/b40931489954f6fe851867bf25e192e19c64cc36bea6ec0f0b914eb0dc6b5222.pdf`. Repeated inventory queries returned the same current metadata. The 25 BDNS client/importer/document tests passed before the live download.
