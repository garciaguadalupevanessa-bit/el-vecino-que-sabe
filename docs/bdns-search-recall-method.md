# Measuring agricultural search coverage

## What the API can and cannot measure directly

The documented BDNS call-search endpoint has no agricultural-sector parameter. It supports title text, region, administration and expenditure-purpose filters; a detail record contains sector and other classification fields. A search count or union of keyword results is therefore a candidate-discovery measure, not recall by itself.

## Bounded discovery audit

Run `scripts/probe-agricultural-search-coverage.ps1` from the project root in a trusted PowerShell environment with normal TLS certificate validation. It retrieves the official finality catalog, then makes 32 small, one-page searches: 31 nationwide title searches across crop and livestock terms plus a search using the catalog's agriculture purpose ID. It waits at least one second between requests, captures at most 10 records per search, records total matches/truncation, deduplicates the captured candidates and writes `docs/samples/agricultural-search-audit.json`.

The first-page capture is intentionally bounded and may truncate popular terms. Do not treat it as a complete national extract. The purpose filter is also only a discovery route; it may include fisheries, food, research or other calls that are not farm aid.

## Gold panel and recall calculation

Before calculating recall, reviewers must manually assemble a seed panel of known relevant calls from independent official paths, including official campaign pages, known call IDs and relevant BDNS records found through purpose/sector details. The panel should contain verified positive examples from crop-only, livestock and mixed farm aid, across national, autonomous-community and local administration levels. Exclude calls that only fund research bodies or sector organizations when measuring eligibility discovery for farm holdings.

For each positive seed call, check whether its BDNS code appears in the union of the search routes. Report recall as `positive seed calls recovered / all positive seed calls`, overall and separately for crop, livestock and mixed aid. Record false positives and which query recovered each call. Keep the seed panel fixed and versioned so later query changes can be compared fairly.

The initial Aragón probe already demonstrates why detail review matters: the agriculture keyword search surfaced an instrumental food-safety grant to the University of Zaragoza with a non-economic legal-entity beneficiary type. It is sector-related but not generally eligible to a farm. Keyword hit counts alone would overstate usable-aid coverage.

## Completed bounded diagnostic (2026-11-11)

The user ran the first bounded audit on 2026-11-10. The initial corrected audit has 32 active searches: 31 title terms and the catalog-derived agriculture-purpose filter, each with only page 0 and `pageSize=10`. It contains 270 deduplicated candidates. Most query result sets are truncated; `PAC` alone returned 32,280 matches. These are not complete result sets.

The audit originally used `finalidad=11`, which is CULTURA in the live catalog, and misspelled `frutícola` as `frutácola`. The official [finality catalog in the API specification](https://www.infosubvenciones.es/bdnstrans/estaticos/doc/snpsap-api.json) identifies “AGRICULTURA, PESCA Y ALIMENTACIÓN” as ID `12`. The saved audit now excludes the bad purpose results and includes `finalidad=12` and the corrected fruit term. A title-search false positive also showed `PAC` matching the substring in “AGRUPACION”.

An 8-record positive panel was selected from official BDNS detail pages after the initial audit, manually screened for direct farm-holding relevance, and stored in [`samples/agricultural-recall-seed-panel.json`](samples/agricultural-recall-seed-panel.json). The repeatable comparison script is `scripts/measure-agricultural-search-recall.ps1`; its output is [`samples/agricultural-recall-report.md`](samples/agricultural-recall-report.md).

| Holding type | Recovered in captured first pages | Panel size | Rate |
|---|---:|---:|---:|
| Crop-only | 1 | 2 | 50.0% |
| Livestock-only | 0 | 3 | 0.0% |
| Mixed | 2 | 3 | 66.7% |
| Overall | 3 | 8 | 37.5% |

This panel was assembled after the audit and intentionally includes both recovered and missed examples, so its recovery rate is selection-biased. It is diagnostic, not an independent blind benchmark or a statistically representative estimate. A missed ID was absent from the captured first-page union; it may appear on a later BDNS page. It is valid to conclude that first-page capture is insufficient, but not to claim that the underlying API search routes can never find the missed calls. Current application availability is tracked separately from discovery relevance. The official pages also show why title matches need beneficiary/source review: some apparent farm calls target non-economic organizations, and some calls have no published extract yet.

**Task 1.4 is complete at the bounded measurement scope.** A larger nationwide recall claim requires paginating or partitioning the collection and expanding the fixed panel across more territories, aid categories, administrations and campaigns. The API's lack of a direct sector filter is confirmed from its [official OpenAPI specification](https://www.infosubvenciones.es/bdnstrans/estaticos/doc/snpsap-api.json).
