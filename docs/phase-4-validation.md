# Phase 4 validation runbook

This runbook validates the review/classification and coverage-report flow with Aragón first. Navarra and La Rioja are small technical smoke samples only; they do not expand the active coverage matrix, which remains Aragón-only by user decision.

## 1. Apply the classification workflow

Rebuild the API and review UI so the append-only classification table is created:

```powershell
docker compose up -d --build backend frontend
```

In `/review` → **Convocatorias**, select **Todas**, run 10 and Aragón. On one call that is **Apta para extracción**, confirm the preselected category/activity suggestions, cite the official source, enter a short note and save. A call marked **Fuera de alcance** should not accept an in-scope classification. A changed source should require a fresh classification.

## 2. Check coverage and gaps

Open `/review` → **Cobertura** and refresh. Confirm the saved classification appears in **Clasificaciones confirmadas por revisión** and the matching activity/category row changes to **Clasificación confirmada**. Confirm the other rows remain **Pendiente de clasificación**. These rows mean no current cited assignment exists; they do not mean that no aid exists. In the grid, **Campaña sin clasificar** should decrease only when an explicit campaign citation was saved. The separate source-metadata campaign count may remain unclassified because review classifications are stored separately from the original BDNS record.

The matrix CSV is not rewritten by this report. Keep non-Aragón rows `not_checked`; do not promote calls to `verified` from classification alone.

## 3. Smoke-test other autonomous territories

First preview a tiny batch for Navarra and La Rioja (four searches, at most five summaries per query):

```powershell
docker compose exec backend python -m app.bdns.importer --regions 17,19 --administration-types A --terms "agricultura,ganadería" --max-pages 1 --page-size 5 --dry-run
```

If the preview completes, persist the same bounded sample:

```powershell
docker compose exec backend python -m app.bdns.importer --regions 17,19 --administration-types A --terms "agricultura,ganadería" --max-pages 1 --page-size 5
```

Record the new run ID. In **Cobertura**, confirm both region IDs have four query observations. In **Convocatorias**, filter by that run and one of the territories, then open a candidate and verify its official BDNS link and metadata. This is a collection/review smoke test, not category reconciliation or a claim of Navarra/La Rioja coverage; leave those matrix rows `not_checked`.

On 2026-11-11, the user persisted this sample as run 11. The importer completed four region/term observations and upserted 13 unique calls. The printed examples included both agricultural-sector organization support and titles for young-farmer or farm-investment calls; this is a candidate smoke sample only and does not establish relevance or regional coverage.

## Completion evidence to report

To close Phase 4, report: the BDNS code of one saved Aragón classification and its category/activity/campaign; the matching coverage counts; the Navarra/La Rioja smoke-run ID and query status; and any errors or unexpected statuses. If a smoke query returns no calls, note it as a bounded empty result, not absence of aid.
