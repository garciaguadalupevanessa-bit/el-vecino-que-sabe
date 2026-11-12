# BDNS extraction review

Task 3.4 adds an internal queue for uncertain machine-extracted data. It is available at `/review` → **Extracciones** and uses the existing bearer-token access.

## Queue rules

- A call accepted for extraction gets a task until a current-source extraction is stored.
- Fields with no candidates are queued as missing data. Fields with several distinct candidate texts are queued as ambiguous.
- Findings from the quality checker are queued, including missing values, conflicts, unreachable or unreadable sources, and stale extractions.
- When the BDNS source payload changes, unresolved tasks for the old version become stale and a source-change task is added for the new version. A new extraction tied to the current payload supersedes that task.
- Every task is tied to the source payload hash and extraction fingerprint shown when the reviewer opened it. A decision is rejected if either version has changed.
- Review decisions require reviewer identity and notes and are stored in append-only event history.
- **Revisar automáticamente las tareas claras** closes only tasks with exactly one candidate and a complete citation to a current official URL. Missing, multiple, conflicting, stale or quality-finding tasks remain open for a person.

## Reliability boundary

The queue is an internal working tool. Marking a candidate as reviewed only records that a person or the agent inspected it. The extraction stays at `extracted`; closing a simple task does not promote the BDNS call or a public aid to `verified`, verify legal requirements, or determine eligibility. The separate gated source-verification workflow is documented in [`bdns-verification-workflow.md`](bdns-verification-workflow.md).

## Validation

Backend API regression coverage is in `backend/tests/test_review_api.py`. Database lifecycle changes should also be exercised against a disposable PostgreSQL database. Frontend unit tests are run with `npm test` in `frontend`; production bundle validation requires installed frontend dependencies.
