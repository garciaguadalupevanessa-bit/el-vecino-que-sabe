# BDNS source-record importer

The importer discovers a bounded selection of calls, fetches each call's detail, maps source metadata to the canonical record in [`bdns-call-record-schema.md`](bdns-call-record-schema.md), validates required fields, and upserts the result by BDNS code into the separate `bdns_calls` table. It never writes to `aids` and never creates a user-facing eligibility rule. Each record starts at `metadata_only`; activity classification and application status remain unknown until separately reviewed.

## Start with the Aragón slice

From `backend`, run a dry run first to fetch and map at most one page per search term without database writes:

```powershell
python -m app.bdns.importer --regions 21 --terms "agricultura,ganadería" --max-pages 1 --page-size 10 --dry-run
```

After setting `DATABASE_URL` and starting Postgres, run the same bounded slice without `--dry-run` to save it. The importer creates the idempotent schema if needed and upserts one batch in a transaction:

```powershell
python -m app.bdns.importer --regions 21 --terms "agricultura,ganadería" --max-pages 1 --page-size 10
```

The parameters `21` (Aragón) and one page of ten results per term are an initial validation slice, not a coverage claim. Increase the page bound deliberately when preparing a broader collection. Repeat runs update the record with current source metadata and advance `last_seen_at`, while keeping the original `first_seen_at`.

For broader discovery, `--administration-types` accepts a comma-separated subset of `C`, `A`, `L` and `O` (Central, Autonomous, Local and Other). The importer records each administration filter in the query observation so coverage can distinguish otherwise identical region/term searches. A term written as `finalidad=<positive ID>` uses the BDNS purpose filter instead of title matching; this is a query route, not an activity classification. See [`national-indexing-plan.md`](national-indexing-plan.md) for bounded batch examples and reconciliation guidance.

The first live dry run found 11 unique calls across the two searches. The sample includes grants to public bodies and research institutions, so those results are discovery candidates, not proof of aid for a farm. The importer intentionally leaves every record `unclassified` and `metadata_only` until a separate relevance and source review.

The bounded Aragón import was then run twice against the project's Postgres database. Both runs mapped 11 unique calls; after the repeat run, `bdns_calls` contained 11 rows and 11 distinct BDNS codes. The importer tests passed (17 client and importer tests). This validates idempotency for this bounded slice; it does not establish nationwide recall or farm relevance of every imported call.

## Tests

The importer and mapper are covered with fixture BDNS data and mock clients; those tests do not make live calls or need a database. Run from `backend`:

```powershell
python -m pytest -q tests/test_bdns_client.py tests/test_bdns_importer.py
```

Postgres persistence can additionally be integration-tested when a dedicated test database is configured. Never point destructive integration tests at a database with application data.
