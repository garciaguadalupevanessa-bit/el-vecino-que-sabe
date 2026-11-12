# BDNS task 3.1 — Extract reviewable aid facts

The local extraction step reads canonical BDNS metadata and already-downloaded PDFs for a call that a reviewer explicitly accepted for extraction. It stores candidate facts separately from `bdns_calls` and the public `aids` catalog. The source call remains `metadata_only`; extracted output is marked `extracted` and is never an eligibility decision.

## Extracted fields

- Purpose: BDNS purpose/objective metadata and PDF passages around object or purpose headings.
- Beneficiaries: BDNS beneficiary categories and passages naming eligible beneficiaries.
- Requirements: passages around requirements, conditions, obligations and eligibility criteria.
- Deadlines: source date/text fields and PDF passages around application periods.
- Documents: the BDNS document inventory and passages describing documents to submit.
- Application route: the BDNS electronic-office URL and PDF passages about submission or electronic processing.

Each candidate retains its origin. PDF candidates include BDNS document ID, page number and a bounded source-text excerpt. The structured page/section citation and formal source validation are handled in task 3.2.

The extractor is deterministic and runs locally; it does not send source documents to an LLM or infer missing values. It reads embedded PDF text only; scanned pages without a text layer are reported as not readable by this step and require later handling. A missing field means no candidate was found in the available sources, not that the call has no such rule. Extracted passages are candidates for human review and may include irrelevant surrounding text.

## Run for one reviewed call

First download its PDFs if they are not already in the persistent BDNS document store:

```powershell
docker compose run --rm backend python -m app.bdns.documents --bdns-code 920758 --max-documents 10
```

The source call must already have the `accepted_for_extraction` decision in `/review`. Then run:

```powershell
docker compose run --rm --build backend python -m app.bdns.extraction --bdns-code 920758
```

The command prints counts and per-field status. Results are stored append-only by BDNS source fingerprint and extractor version, so re-running the same source is idempotent and a changed source or PDF creates a separate extraction. Stored PDFs are re-hashed before parsing; escaped paths and hash mismatches are rejected.

To read the latest output, use the token-protected endpoint:

```text
GET /api/admin/bdns/extractions/920758
Authorization: Bearer <BDNS_REVIEW_TOKEN>
```

The response contains `facts`, `field_status`, processed-document outcomes, a source fingerprint and explicit limitations. The original source record reliability and public aid catalog are unchanged.

## Initial live smoke check

The first Docker run downloaded BDNS document `107774` for call `359141` and stored an extraction result. Metadata candidates were found for purpose, beneficiaries, deadlines and documents; none were found for requirements or application route. The PDF parser returned `no_text`, so this run did not validate extracting facts from a text-readable PDF. The call title is a 2017–2019 research-support grant and is not a representative farm-aid example; treat this only as a technical smoke check, not evidence of agricultural eligibility coverage.

A second live run used call `923754`, a 2026–2027 subsidy for investments in transformation and marketing of agricultural products. BDNS document `1512984` downloaded successfully; its 42 pages yielded text. The extractor stored candidates for all six fields: 24 purpose, 10 beneficiary, 22 requirement, 19 deadline, 15 document and 10 application-route candidates. The source call remained `metadata_only`. This validates the technical extraction path on a text-readable official PDF; the call is aimed at agri-food processing businesses, so it does not establish coverage of direct farm-level aid.

## Automated checks

From `backend`:

```powershell
python -m pytest -q tests\test_bdns_extraction.py tests\test_review_api.py
```

The focused extraction/reviewer suite was run in Docker: 11 passed. Pytest emitted one cache-permission warning inside the non-root container; it did not affect the result.
