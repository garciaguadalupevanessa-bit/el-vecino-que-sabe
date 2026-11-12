# National and territorial coverage matrix

This matrix is the working register for Phase 4. It separates the territory/activity/category/campaign dimensions from the imported call records and records evidence instead of implying nationwide completeness.

## Files and dimensions

- [`national-coverage-matrix.csv`](national-coverage-matrix.csv) contains 2,640 rows: 80 territorial units × 3 farm activities × 11 priority aid categories.
- The 80 units are Spain, all 17 autonomous communities, both autonomous cities, all 50 provinces, and ten official island-level BDNS subdivisions for Baleares and Canarias.
- BDNS assigns IDs to 77 of these units. It has no single province-level ID for Illes Balears, Las Palmas or Santa Cruz de Tenerife; those province rows remain without an ID and point to the corresponding island-level rows instead.
- Farm activity values are `agriculture`, `livestock` and `mixed`.
- Priority aid categories are `pac_direct`, `pac_coupled`, `young_farmer_startup`, `farm_modernisation`, `agro_environment_organic`, `agricultural_insurance`, `animal_health`, `extensive_livestock`, `native_breeds`, `investment` and `emergency_aid`.
- Campaign is initially `not_classified`. Add campaign-specific rows when the campaign is established from an official source; do not infer a campaign from the calendar year alone.
- Relevant province and municipality-level territories are added from official call evidence. The initial register does not enumerate every municipality in Spain.

## Status and evidence rules

Every initial row starts as `not_checked`. Blank territory IDs, dates, import-run IDs and indexed counts mean that evidence has not yet been recorded; they are not zeros. Use the public states `not_checked`, `indexed`, `details_extracted` and `verified` according to the evidence reached. Keep per-row `last_checked_at`, latest BDNS import-run ID, indexed-call count and a concise evidence note when updating the matrix.

**Current operating scope:** maintain and reconcile coverage for Aragón only. Other rows remain `not_checked`, including Spain-level rows. The persisted national discovery run is retained in `bdns_calls`, but its broad candidate results are not counted in this matrix until the user expands the coverage scope and the candidates are reviewed.

The territory IDs are reconciled against the full official BDNS region tree refreshed during import run 6. The CSV stores these IDs while retaining `not_checked` coverage states until matching query and category evidence exists. Run 6 searched region 21 (Aragón) for `agricultura`, capped at one page, and indexed 10 calls. Its run ID is noted on Aragón/agriculture rows, but aid category and campaign were not classified, so those category-specific rows correctly remain `not_checked`.

The current `/review` → **Cobertura** report tracks bounded queries by BDNS region and search term, and lists reviewer-confirmed category/activity/campaign assignments with citations. A territory/category row can be marked `indexed` only when recorded query and classification evidence support it. A limited query with no results remains a bounded observation, not proof that no aid exists. Do not aggregate `verified` coverage from call metadata alone; the source and approved rules must pass the verification workflow. The CSV remains a manually reconciled register; report counts do not silently rewrite it.

Use [`bdns-coverage.md`](bdns-coverage.md) for importer run behavior and the authenticated coverage report. The matrix is an initial coverage plan; its entries have not been seeded from live nationwide query results yet.

Use [`national-indexing-plan.md`](national-indexing-plan.md) for the Phase 4.2 bounded national, autonomous and local search batches and their review rules.

Use [`phase-4-validation.md`](phase-4-validation.md) for the runbook to confirm a cited Aragón classification, inspect the activity/category gap grid, and smoke-test other territories without changing their matrix status.
