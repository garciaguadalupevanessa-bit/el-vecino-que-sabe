# BDNS rule approval and verification

Task 3.5 adds a protected source-verification API. Manual promotion remains available. The AI finalization endpoint can also verify a call and publish a user-facing aid when current-source, extraction, quality, citation and rule-mapping gates all pass; unresolved cases remain for human review.

## Promotion gates

`GET /api/admin/bdns/verification/{bdns_code}` reports whether the call is eligible and returns the current call hash, extraction fingerprint, document manifest, quality state and latest verification event. The endpoint is protected by the existing reviewer bearer token.

This task exposes the controlled action through the protected API; it does not add a reviewer-screen form. Use the API documentation at `/docs` with the same bearer token while the backend is running.

The POST endpoint rejects promotion unless all of these are true:

- The source call was accepted for extraction.
- The latest extraction matches the current call hash and all currently downloaded document hashes.
- No extraction-review tasks for the current call version remain open or marked for correction.
- The latest quality report is `passed`, matches the current call hash and predates no current document update.
- The reviewer supplies a name, source-review notes, and one or more approved rule statements.
- Every rule has a page or section locator and cites a URL listed on the official call record.

## Automatic verification and publication

For an accepted call, open its card in `/review` and use **Verificar reglas y publicar con agente**. The agent receives only the current extraction's requirement candidates and source metadata. It must account for every extracted requirement evidence item, map each rule to a supported `FarmProfile` field/operator/value, and cite an exact current official extraction citation. The backend independently validates the citation URL, locator, payload hash and value type, then reruns the existing freshness, quality and pending-task gates before promotion.

If all gates pass, the same transaction appends an AI finalization audit event, records the verified rules, and publishes `bdns_<code>` to the database-backed aid catalog. The public response labels the source as verified automatically by the agent. New chat requests refresh the catalog from PostgreSQL; no backend restart is needed. The generated aid does not invent an open/closed status, deadline, amount or application steps; missing details remain unknown. A source or document change reopens verification and downgrades an agent-published aid to extracted until it is processed again.

If requirements are incomplete, ambiguous, unsupported by the current profile fields, missing citations, or if source/extraction/quality gates are stale, the endpoint records `needs_human_review` and publishes nothing. The agent never guarantees that the administration will grant the aid.

Example request to `POST /api/admin/bdns/verification/923754`:

```json
{
  "expected_payload_sha256": "<hash returned by the GET endpoint>",
  "expected_extraction_fingerprint": "<fingerprint returned by the GET endpoint>",
  "reviewer": "Reviewer Name",
  "notes": "Compared the approved rule with the current official bases and call document.",
  "approved_rules": [
    {
      "statement": "Approved rule text, transcribed and checked by the reviewer.",
      "source_url": "https://www.infosubvenciones.es/bdnstrans/api/convocatorias/documentos?idDocumento=1512984",
      "page": 7,
      "section": "Eligibility requirements"
    }
  ]
}
```

The document ID must belong to the specified BDNS call. A stale call or extraction returns HTTP 409; an incomplete quality/review state also returns HTTP 409; an unrelated citation returns HTTP 422. Decisions are recorded in the append-only `bdns_call_verification_events` table. Verification applies to the indexed BDNS source call and does not create or publish a user-facing aid rule; the public aid catalog remains separate.

## Reopening after changes

When an import changes the BDNS call payload, or a document download changes its status or content hash, the workflow appends a `reopened` event and resets source reliability to `metadata_only`. It adds a source-change task to the extraction inbox. The prior approval and approved rules remain in the audit history; a fresh extraction, quality check and reviewer approval are required for promotion again.

## Validation

Run API/database lifecycle checks in Docker with a dedicated disposable PostgreSQL database configured as `TEST_DATABASE_URL`. Do not point integration tests at the application database. Validate successful promotion gates, rejected stale hashes and citations, immutable audit events, and reopening after call or document changes.
