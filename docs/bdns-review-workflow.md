# BDNS source staging and review

Task 2.6 adds a private review queue for the BDNS source records imported in task 2.3. It is a human triage step before the extraction work planned for phase 3. It does not verify an aid, calculate eligibility or publish anything to the user-facing aid catalog.

## Access

The internal page is served at `http://localhost:3000/review`. Its API is disabled unless `BDNS_REVIEW_TOKEN` is set in the project-root `.env` file. Use a long random secret, keep it out of source control and do not paste it into chat. The example environment file leaves this value blank by design.

For a local PowerShell secret, run `python -c "import secrets; print(secrets.token_urlsafe(32))"` and copy the result directly into `.env` as `BDNS_REVIEW_TOKEN=<generated-secret>`. Rebuild/restart the backend and frontend with `docker compose up -d --build backend frontend`, then open `/review` and enter the secret. The browser keeps it in page memory; closing the review session clears it.

The current implementation uses a shared bearer secret and a reviewer name entered with each decision. It is suitable for a local development workflow; before a public deployment, replace the shared secret with individual accounts and role-based access, and protect the page/API behind the deployment's authentication layer.

## Decisions

- **Apta para extracción** (`accepted_for_extraction`): the source looks relevant enough to enter a later extraction step. This is not a verified classification or eligibility decision.
- **Marcar fuera de alcance** (`out_of_scope`): retain the BDNS source record but exclude it from the planned extraction queue. Nothing is deleted.

Each decision requires the reviewer name and a reason. The append-only audit stores the BDNS code, source fingerprint, reviewer, decision, notes and timestamp. Database triggers reject edits/deletions to audit rows. A source fingerprint mismatch returns a conflict; reload the queue and review the changed source. Re-importing an unchanged source preserves its decision; a changed source is set back to `review_required`.

## Finding records to review

The **Convocatorias** view can filter by import run, BDNS search territory, and text matching the title or BDNS code. Filters combine with the existing review-status selector and apply to pagination. **Actualizar** reloads both the queue and the available run/territory options after a new import. Territory means the region used by the importer query; it does not claim the call is legally limited to that territory.

The importer now stores each query's candidate BDNS codes against its run and region. This association is exact for imports performed with the updated version. Older runs have no saved candidate-code membership; they appear disabled in the run selector with a re-import hint. To review the prior Aragón batch, rebuild the backend/frontend, then rerun the same bounded Aragón import. The new run will be selectable and can be filtered to region 21. Upserts remain idempotent by BDNS code, while the new run records its own query membership.

## Confirming activity, category and campaign

For a call marked **Apta para extracción**, the review card offers suggested activity/category values and an optional campaign year. The suggestions are preselected; a reviewer can change them and save a classification with notes. Matched official BDNS fields are attached as evidence automatically for unchanged suggestions. A manual category/activity/campaign correction requires an official URL, locator (BDNS field, section or page) and quoted evidence. Campaign years require a citation that explicitly identifies the campaign/year.

Each save appends an immutable, source-fingerprint-bound classification event. A changed BDNS source makes the old classification stale; it no longer contributes to the current coverage report. Classifications do not change `reliability`, extraction status, eligibility, or user-facing aid records. Calls marked **Fuera de alcance** cannot receive an in-scope classification. `/review` → **Cobertura** groups current cited classifications by queried territory, activity, category and campaign; one call can count in multiple categories when separately supported.

These decisions leave `reliability` at `metadata_only`. The records remain in `bdns_calls`, separate from `aids`; the public aid endpoint and eligibility tools do not read the review queue.

## AI review agent

The review card includes **Analizar con agente**. This makes an on-demand call to the configured LLM using a bounded selection of BDNS metadata and extracted fact candidates that cite official URLs/fields/pages. The complete raw BDNS payload and PDF binary are not sent in this request. The agent can suggest farm relevance, activity, category and an explicitly evidenced campaign year, and it lists questions and the exact evidence IDs it used.

The result is stored as an append-only suggestion tied to the current source payload hash and model name. If the BDNS source changes, the old suggestion is not shown as current. **Procesar hasta 10 con agente** analyses up to ten pending calls in the current filters for each automatic-review policy version. A case moves to **Apta para extracción** when deterministic official metadata supports an agricultural purpose and the agent supplies cited activities and categories. If beneficiaries are unclear, the bases can be examined during extraction rather than stopping the candidate at source triage. A case moves to **Fuera de alcance** only when official beneficiary metadata explicitly names a university, local/public body or research center, there is no farm-beneficiary or agricultural signal, and the agent also reports low relevance. These transitions are recorded in an append-only AI decision log. Cases without enough agricultural evidence, cited labels or with conflicting signals remain pending for a human; model confidence alone never opens the automatic gate. A single-record **Analizar con agente** action uses the same rules.

Automatic source triage does not create a human-confirmed activity/category/campaign classification or change its coverage counts. It never changes source reliability, verifies legal eligibility/rules, or publishes a call into the user-facing aid catalog. Calls accepted for extraction enter the existing extraction queue. The model's confidence label is not a calibrated probability.

On accepted calls, **Extracciones** can automatically close only single-candidate tasks with a current official citation. Missing, ambiguous, conflicting, stale and quality tasks stay open. Once the extracted candidates and quality report are current and no tasks remain, the card offers **Verificar reglas y publicar con agente**. That step validates every normalized rule against the profile schema and its source citation, then verifies and publishes the aid in one database transaction. It exposes the method as automatic in the catalog, refreshes the live catalog, and reopens/downgrades that aid if its BDNS source changes. Detailed gates and the human review path are in [`bdns-verification-workflow.md`](bdns-verification-workflow.md).

The pre-review request requires the configured LLM key and the existing reviewer token. If no current official evidence is available, it refuses to run rather than inventing a citation. Treat AI text as an aid to triage only; the official source remains authoritative.

## Validation

From `backend` with the project's Python environment active:

```powershell
python -m pytest -q tests\test_review_api.py tests\test_bdns_change_detection.py tests\test_bdns_importer.py
```

The PostgreSQL integration test in `tests/test_db.py` checks review audit persistence and immutability. Run it only with `TEST_DATABASE_URL` pointed at a dedicated disposable test database: that fixture truncates its tables. Do not point it at the application's working database.

Manual smoke check: with the token unset, `/api/admin/bdns/review` returns 404; with the token set, `/review` should accept the key, list pending BDNS records and permit a decision only after a reviewer and notes are entered. Confirm the result still says `metadata_only` and the BDNS code is not returned by `/api/aids/{code}`.

For AI source triage, follow [`ai-pre-review-validation.md`](ai-pre-review-validation.md). For downstream rule verification and automatic catalog publication, follow [`ai-finalization-validation.md`](ai-finalization-validation.md). Uncertain cases remain pending, and source changes reopen automatic verification.
