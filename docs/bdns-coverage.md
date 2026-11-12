# BDNS import coverage

Task 2.7 records bounded importer runs and reports the evidence available for territory, farm activity, source category and campaign coverage. It is an operational index report, not a claim that the aid base is complete.

## What is recorded

- The importer refreshes the official BDNS region tree (`GET /regiones`) and stores its identifiers, descriptions, NUTS codes and parent/child relationships.
- Each database-backed import records its start/end state, selected BDNS region IDs, search terms, page limit and page size. Per-query candidate counts are unique within each query; the run-level candidate total can include overlap across terms, while indexed-call counts are deduplicated by BDNS code.
- Searches run once per region and search term. Their candidate/indexed counts and whether the configured page budget was reached are saved separately.
- Each completed query also stores the BDNS codes found for its import run, search region and term. The internal Convocatorias queue uses this membership to filter by run and territory; title and BDNS code text search are applied to the same paginated queue.
- Dry runs remain read-only and do not create a coverage record.

The region tree comes from the public BDNS API; the search endpoint documents region IDs as an explicit filter and the catalogue endpoint returns a hierarchical region list. See the [official SNPSAP API specification](https://www.infosubvenciones.es/bdnstrans/doc/swagger).

## Reading the report

With `BDNS_REVIEW_TOKEN` configured, open `/review` and select **Cobertura**, or request `GET /api/admin/bdns/coverage` with the same bearer token. The report shows the latest import and its per-region/per-term results, all regions in the current BDNS catalogue, and the current indexed metadata counts.

- Territory state refers to the most recent recorded bounded query for that BDNS region. “Sin resultados en consulta limitada” means that query returned no candidates; it does not prove that no relevant aid exists.
- Activity query scope is inferred only from explicit words in the search term. Record activity counts come from `farm_activity_classification`; unclassified calls remain visible as a gap. Neither is a final relevance or eligibility decision.
- The report preserves source-provided purpose and economic-sector labels. Reviewers can separately confirm normalized activity/category/campaign assignments with citations; only current assignments on calls still accepted for extraction appear in the confirmed-classification table. Automated suggestions alone do not count.
- Campaign counts use `call.campaign`; because the current importer does not derive campaign years, missing years appear as unclassified.
- If the page budget was reached, more matching calls may exist beyond the scanned pages. Every run is explicitly described as bounded.
- The confirmed-classification table groups by the region used for the search, not a claim that the call is legally limited to that region. Calls may appear in multiple categories if reviewers support each assignment separately.
- The activity/category gap grid is generated for territories with recorded queries, using the 3 activities and 11 priority categories. “Pendiente de clasificación” means there is no current cited assignment; it never means “no aid.” Unqueried territory gaps remain listed separately.

The first run after this change establishes query history and refreshes the territory catalog. Earlier imported BDNS calls are included in index counts, but the project does not invent query history for them.

Runs created before candidate-to-run membership was added cannot be filtered exactly by run. Repeat a bounded import to create a new run with exact membership; the BDNS call upsert remains idempotent.

## Run and validate

Use the normal bounded importer from the project root. The default remains the Aragón validation slice:

```powershell
docker compose run --rm backend python -m app.bdns.importer --regions 21 --terms "agricultura,ganadería" --max-pages 1 --page-size 10
```

Pass additional region IDs and terms for other bounded runs. A run over multiple regions executes separate region/term searches and records each separately. Avoid an unbounded nationwide run until query terms and page limits have been reviewed.

Backend tests:

```powershell
cd backend
python -m pytest -q tests\test_bdns_client.py tests\test_bdns_importer.py tests\test_review_api.py
```

If other local containers already use ports 5432 or 8000, set different `POSTGRES_HOST_PORT` and `BACKEND_HOST_PORT` values in `.env` (for example `5433` and `8001`). The application still connects to Postgres over the internal Compose network on port 5432. To run tests without Compose attempting to start its database dependency, use `docker compose run --rm --no-deps --build backend pytest -q tests/test_bdns_client.py tests/test_bdns_importer.py tests/test_review_api.py`.

The PostgreSQL integration test in `tests/test_db.py` truncates tables. Run it only against a dedicated disposable test database configured with `TEST_DATABASE_URL`, never against the application's database.

See [`phase-4-validation.md`](phase-4-validation.md) for the bounded Aragón review check and small Navarra/La Rioja smoke sample. The latter is not a coverage expansion.
