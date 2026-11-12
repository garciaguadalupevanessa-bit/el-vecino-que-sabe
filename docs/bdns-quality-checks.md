# BDNS task 3.3 — Automated quality checks

The quality checker assesses one imported BDNS call and appends a report to `bdns_quality_checks`. It reuses the existing safe HTTPS reachability checker and the current source, PDF, version and extraction stores. It does not change the call's reliability, review decision, or user-facing aid catalog. A `passed` report means only that these automated checks found no issue; it is not legal/source verification or an eligibility decision.

## Checks

- **Required fields:** canonical identity, retrieval/hash/snapshot state, title, territory list, source groups, reliability and preserved BDNS payload.
- **Dates:** ISO parsing for receipt, application start/end and retrieval timestamp; flag an end date before a start date.
- **Territory consistency:** compare a territory NUTS code to any code parsed from its source label and the currently stored official BDNS region catalog. An empty territory remains unknown and is reported as a warning.
- **URL reachability:** check up to `--max-links` current official URLs using the existing SSRF-conscious HTTPS checker. A HEAD 403 triggers one bounded range-GET retry; 403/401 and other non-404/410 client denials remain unknown warnings because they do not establish that a link is absent. 404/410 are recorded as broken at check time. Untested, transient, insecure-HTTP, or otherwise unknown links remain warnings.
- **PDF readability and integrity:** inspect up to `--max-documents` listed PDFs in storage, verify safe paths, PDF signature, byte size and SHA-256, parse page count, test embedded text, and verify the immutable document hash version exists. A parsed PDF with no embedded text is a warning; OCR is not performed.
- **Version/hash changes:** compare canonical payload, database and immutable snapshot hashes; report the latest source change and detect whether saved extraction results are stale against the current payload, current PDF hashes or extractor version.

Reports contain `passed`, `warning` or `failed` status per check, machine-readable findings and bounded details. Unknown or untested results are never counted as passes. Every run is retained append-only.

## Run one call

From the project root:

```powershell
docker compose run --rm --build backend python -m app.bdns.quality --bdns-code 923754 --max-links 10 --max-documents 10
```

The command stores its report in Postgres and prints the status and findings. Exit code `0` means passed or warning; exit code `1` means one or more quality errors; exit code `2` means the check could not run. Link checks are live and bounded; reports may include warnings for rate limits, temporary outages, or links beyond the bound.

Retrieve the most recent report from the private review API:

```text
GET /api/admin/bdns/quality/923754
Authorization: Bearer <BDNS_REVIEW_TOKEN>
```

The report can also be inspected in Postgres:

```sql
SELECT check_id, created_at, report->>'overall_status' AS status,
       report->'checks' AS checks, report->'findings' AS findings
FROM bdns_quality_checks
WHERE bdns_code = '923754'
ORDER BY created_at DESC, check_id DESC
LIMIT 1;
```

**Live validation completed:** the user ran the focused change-detection, quality and reviewer API suites (23 passed, one non-blocking pytest cache warning). Quality check `2` for BDNS `923754` passed all six check groups with zero errors or warnings: five official URLs were reachable, the 42-page PDF had readable text on all pages and matching content hash/version, source/snapshot hashes matched, and the latest extraction was current. Source reliability remained `metadata_only`.

## Tests

From `backend`:

```powershell
python -m pytest -q tests\test_bdns_quality.py tests\test_review_api.py
```
