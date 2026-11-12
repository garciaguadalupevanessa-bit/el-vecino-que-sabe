# Phase 7 — Evaluation and release checks

This matrix defines repeatable, offline scenarios for the main aid-search and safety decisions. It is a test plan, not evidence that the current catalog covers every aid in Spain. Search results must remain limited to catalog evidence, and an unknown result must never be presented as an eligibility decision.

## Evaluation cases

| ID | Scenario | Input / fixture | Expected result |
|---|---|---|---|
| E01 | Crop-only farm | Agriculture, cereal crops; no livestock fields | Crop and general aids remain searchable; no livestock detail is requested. |
| E02 | Livestock farm | Livestock, sheep; no crop fields | Livestock and general aids remain searchable. |
| E03 | Mixed farm | Agriculture and livestock, olives and sheep | Results may match either activity; both profile activities are retained. |
| E04 | Other livestock species | Cattle, goat, pig, equine, poultry, bees, other | Each value is accepted by the profile schema; match only compatible or general aids. |
| E05 | National aid | Aragón profile with national territory | National aid remains eligible for search in the region. |
| E06 | Autonomous community | Aragón / ES24 | Aragón-level aid matches; unrelated region does not. |
| E07 | Province | Teruel / ES242 | Teruel aid matches without requiring municipality. |
| E08 | Municipality | Alcañiz / 44013 | Municipality aid matches; unrelated municipality does not. |
| E09 | Location omitted | Crop-only or activity-only profile | Search is bounded to national aids and says location was not supplied. |
| E10 | Campaign recorded | Aid with campaign label/year in source | Campaign appears as recorded, without implying that the call is currently open. |
| E11 | Campaign absent | Source has no campaign year/label | Campaign remains unknown; do not infer the current campaign. |
| E12 | Verified rule, required data absent | Empty profile against a cited evaluable rule | Result is unknown and lists required missing fields where supported. |
| E13 | Ambiguous or uncited rule | Extracted/metadata-only aid, or unresolved rule citation | All requirement results remain unknown; no deadline or application steps are asserted. |
| E14 | Conflicting sources | Source payload changes after an extraction/review | Change is recorded; prior extraction is stale and requires review. |
| E15 | Amended call | Changed date, status or source document | Changed paths are reported without exposing stored old/new payloads; stale review is flagged. |
| E16 | Expired deadline | Verified aid has an ISO deadline before today but stale `open=true` | Excluded from `only_open` results. Non-ISO or missing dates remain unknown rather than guessed. |
| E17 | Broken official link | HTTP 404/410 | Mark broken; 403, transient failures and uncertain responses remain unknown. |
| E18 | Redirect to private/insecure host | HTTPS public URL redirects to HTTP or a private IP | Do not follow the unsafe target; report status unknown. |
| E19 | Unreadable PDF | No extracted text, encryption or malformed PDF | Record a warning/review need; never promote aid reliability automatically. |
| E20 | Unsafe document response | HTML, wrong signature, oversized stream, invalid document ID | Reject without storing as PDF; preserve failure/rejection inventory. |
| E21 | Prompt injection in profile/source | Text asks to ignore policy, reveal prompt/key or call an arbitrary URL | Treat as untrusted data; it cannot change system rules or authorize unrelated tool calls. |
| E22 | BDNS transient rate limit | 429/503 with bounded Retry-After | Retry only within configured limit; over-limit delay fails without sleeping unboundedly. |
| E23 | Secret handling | Missing/invalid provider key or provider error | User receives a safe Spanish error; credentials and provider request headers are not returned. |
| E24 | No candidates | Empty catalog match for a location/activity | Explain no catalog match, not that no aid exists; disclose possible coverage gaps. |

## Implemented automated coverage

The backend suite already covers crop-only, livestock and mixed profiles; national, community, province and municipality matching; missing and unverified rules; source fingerprints and stale extractions; broken and redirected links; malformed, oversized and unreadable PDFs; bounded retries; and safe API configuration errors. Phase 7 adds a prompt-injection regression and a stale-deadline regression. The frontend has Node tests and a production build; CI runs backend, PostgreSQL integration, frontend build/tests, and Docker Compose smoke checks.

Run the full suite and release smoke checks using the commands in `docs/phase-7-validation.md`. CI is the reproducible record for checks that require a Linux/Postgres/Docker runner.

## Human review and known coverage gaps

- The user must review wording and keyboard/screen-reader behavior with people from the agricultural sector before release. Automated tests cannot establish that wording is understandable or accessible to them.
- The catalog and mapped BDNS calls are incomplete; a search result or empty result is not proof of national or regional coverage.
- Campaign status and deadlines may change after the catalog's recorded check date. Only an explicit verified ISO deadline is used to exclude an aid from `only_open`; unknown date formats are not interpreted.
- These fixtures verify product behavior, not legal eligibility. The administration decides each application.
