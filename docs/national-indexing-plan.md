# National BDNS indexing plan

This plan starts the Phase 4.2 discovery workflow. It records bounded search observations in the existing import-run coverage report and stores matching calls in `bdns_calls`. A match is only a candidate: the BDNS search endpoint has no agricultural-sector filter, title searches have incomplete recall, and imported records remain unclassified and `metadata_only` until reviewed.

## Query model

- Use the official BDNS region ID to scope geography and `tipoAdministracion` to separate Central (`C`), Autonomous (`A`), Local (`L`) and Other (`O`) granting bodies.
- Use short, high-signal title terms. The importer also accepts `finalidad=<ID>` as a purpose-filter route, but purpose 12 is broad and should not be treated as an agriculture filter.
- Each `(region, term, administration type)` query is bounded by `--max-pages` and `--page-size`. Coverage observations preserve administration type in `search_term`, for example `admin=C|PAC`.
- Search overlaps are deduplicated by BDNS code before detail mapping/upsert. Query-level candidate counts are independent and must not be summed as unique calls.
- A query with no results, or a query whose page cap is reached, does not establish that a territory or category has no aid. `page_limit_reached` indicates likely truncation when the cap is filled.
- The matrix stays `not_checked` until evidence is manually mapped to a supported category/activity/campaign. Indexing alone never means an aid is relevant or verified.

## First bounded collection

Run from the repository root in PowerShell. This first pass checks one national region and one administration type with one page of ten results per title term (at most 100 summaries before overlap; detail calls are deduplicated). It is intended to exercise collection and produce reviewable candidates, not to complete the national index.

Dry run, without database writes:

```powershell
docker compose exec backend python -m app.bdns.importer --regions 1 --administration-types C --terms "PAC,pago básico,agricultura,ganadería,joven agricultor,modernización,seguro agrario,sanidad animal,razas autóctonas,sequía" --max-pages 1 --page-size 10 --dry-run
```

Then persist the same bounded run:

```powershell
docker compose exec backend python -m app.bdns.importer --regions 1 --administration-types C --terms "PAC,pago básico,agricultura,ganadería,joven agricultor,modernización,seguro agrario,sanidad animal,razas autóctonas,sequía" --max-pages 1 --page-size 10
```

The national pass for autonomous administrations uses official CCAA and autonomous-city region IDs from `national-coverage-matrix.csv` (for example Galicia `3`, Aragón `21`, Madrid `26`, Ceuta `74`, Melilla `76`):

```powershell
docker compose exec backend python -m app.bdns.importer --regions 3,8,10,13,17,19,21,26,29,39,45,49,54,58,63,72,74,76,79 --administration-types A --terms "agricultura,ganadería,joven agricultor,modernización,agroambiental,ecológico,seguro agrario,sanidad animal,extensivo,razas autóctonas,sequía" --max-pages 1 --page-size 10
```

This is 209 bounded queries and can take several minutes because the client paces requests. Run it only after reviewing the first run's volume and failures. For local administrations, start with the same regional ID list and `--administration-types L`, then expand province/island searches for territories with gaps. To keep each execution small, split `--regions` into groups of three to five and retain the same query cap. The 77 mapped region IDs and 10 island subdivisions are listed in the matrix.

## Review and reconciliation

After each persisted batch:

1. In `/review` → **Cobertura**, record the run ID, bounded region/term observations, candidate and indexed counts, and any capped queries.
2. Inspect candidate titles, granting bodies, territories, dates, official source links and documents. Keep unrelated recipients and ambiguous titles as unclassified candidates.
3. Assign activity, priority category and campaign only from explicit source evidence. Update only matrix rows supported by the evidence; leave other rows `not_checked`.
4. Send relevant uncertain records through extraction/review. Mark a call `verified` only after the Task 3.5 source and rule gates pass.
5. Repeat with additional title synonyms and later pages for high-priority territories. Log terms and bounds so recall limitations remain visible.

## Current limitation

The initial recall audit recovered only 3 of 8 manually reviewed positive calls from a union of first-page searches. This is a diagnostic sample, not a national recall estimate. Better coverage requires iterative synonyms, additional pages, official-purpose/administration filters, source review and targeted checks of known programs. The search API does not expose a reliable agricultural-sector-only filter, so no single automated pass can certify completeness.

## First national dry-run result

On 2026-11-11, the user ran the first bounded dry run for national region 1 and Central administration (`C`), with ten title terms, one page and ten results per query. The importer mapped 86 unique calls from ten bounded searches and made no database writes. The displayed sample included an agricultural test-space grant as well as calls for FEMP and ICEX, confirming that broad terms return unrelated candidates. This validates the dry-run path and candidate collection only; it does not validate persisted coverage, relevance, completeness or matrix status.

The same batch was subsequently persisted successfully and mapped/upserted 86 unique BDNS calls. Per the user's scope decision, this national run is retained as discovery data but is not reconciled into the coverage matrix. Active coverage work remains limited to Aragón for now; other territories stay `not_checked` until the scope is expanded and their records are reviewed.

On 2026-11-11, the user also ran a dry run for Aragón (region 21), Autonomous administration (`A`), with eleven title terms and one page of ten results per query. The importer mapped 62 unique calls from eleven bounded searches without database writes. The displayed titles included direct grants to the University of Zaragoza and a foundation, so a matching agricultural title or granting body alone is insufficient to classify a call as farm support. The dry run validates candidate discovery only; no matrix status was changed.

The user then persisted the same Aragón batch successfully as import run 9. It recorded eleven bounded region/term query observations and upserted 62 unique calls. These remain discovery candidates until recipient and activity relevance are reviewed; no category, activity or campaign coverage has been inferred from the import.

After adding exact run/territory membership for the review filters, the user rebuilt the backend and frontend and repeated the bounded Aragón batch. Import run 10 completed with the same 62 unique calls and eleven query observations. This run can be filtered exactly in the review queue; run 9 remains a historical run without per-call membership.
