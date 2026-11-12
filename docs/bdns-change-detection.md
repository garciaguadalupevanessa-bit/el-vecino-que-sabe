# BDNS change and link tracking

`backend/app/bdns/change_detection.py` creates deterministic SHA-256 fingerprints from canonical JSON, field-path differences and stable source-link identities. `backend/app/db/database.py` uses those values during each idempotent import.

## Call changes and duplicate protection

- `bdns_calls` keeps one current row per BDNS code and its current payload fingerprint.
- `bdns_call_snapshots` stores the source JSON and mapped canonical record once per `(bdns_code, payload_sha256)`. Whitespace and JSON key-order differences do not produce a new fingerprint. The exact original HTTP byte formatting is not available from the decoded JSON client.
- `bdns_call_changes` records first discovery and later changes with previous/current hashes and changed JSON paths. It records field names, not old/new values.
- Re-importing the same source call does not add a snapshot or change event. A changed source payload adds an immutable snapshot/event and sets `bdns_calls.review_status` to `review_required`. A new call starts as `pending_review`; source review status is separate from reliability and eligibility.
- Existing task 2.3 rows are baselined on their next import. Their stored source payload is fingerprinted as the previous snapshot without falsely recording a change if the current API response is the same.
- Repeated search results are deduplicated by BDNS code before detail fetch. Database primary keys protect against duplicate calls and snapshots.
- Calls with different BDNS codes remain separate even when their titles or payloads match; a title match alone is not evidence of duplication.

## Link lifecycle

Each import synchronizes current URLs for the call detail, application portal, regulatory bases, state-aid regulation, documents and announcements into `bdns_links`. Links no longer present in the latest call detail remain in the table as `removed`; a new/reappearing URL begins as `unknown` until checked.

Run a bounded reachability check after importing a call:

```powershell
docker compose run --rm backend python -m app.bdns.link_checker --bdns-code 920758 --max-links 10
```

Checks use HTTPS on port 443 only, resolve to public IP addresses, do not send credentials, and validate every redirect target without following redirects automatically. The checker uses HEAD and falls back to a one-byte ranged GET when HEAD is unsupported. Requests are sequential and spaced by one second by default (`BDNS_LINK_CHECK_INTERVAL_SECONDS`). 4xx responses are recorded as `broken`; transient server errors, network failures, invalid/unsafe URLs and unresolved redirects are `unknown` rather than asserted broken. The maximum link count defaults to ten.

## Repeat-import validation

Run the bounded Aragón importer twice, then compare counts:

```powershell
docker compose run --rm backend python -m app.bdns.importer --regions 21 --terms "agricultura,ganadería" --max-pages 1 --page-size 10
docker compose run --rm backend python -m app.bdns.importer --regions 21 --terms "agricultura,ganadería" --max-pages 1 --page-size 10
docker compose exec -T db psql -U elvecino -d elvecinoquesabe -c "SELECT count(*) AS calls, count(DISTINCT bdns_code) AS unique_calls FROM bdns_calls; SELECT count(*) AS snapshots FROM bdns_call_snapshots; SELECT count(*) AS change_events FROM bdns_call_changes;"
```

On the first task 2.5 run, the existing Aragón calls are baselined. On an unchanged repeat, call, snapshot and change-event counts should stay fixed. A source update should increase snapshot and event counts for the affected BDNS code and mark it `review_required`.

**Live validation completed:** the user ran the bounded Aragón import twice. Postgres contained 11 calls, 11 snapshots and 0 change events after the repeat. The 32 BDNS client/importer/document/change-detection unit tests passed. The bounded link check for BDNS `920758` returned 4 reachable links (application portal, BDNS detail, document and regulatory bases), 0 broken and 0 unknown.

The Postgres regression case is in `backend/tests/test_db.py`; it runs only when `TEST_DATABASE_URL` is explicitly set and truncates tables. Point it only at a dedicated disposable test database, never the project database containing the Aragón import.
