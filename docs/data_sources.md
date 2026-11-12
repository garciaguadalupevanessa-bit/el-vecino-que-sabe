# Data sources

Result of the exploration (F0-08). Fill it in with verified facts: if you have not verified something, write "unverified".

Downloaded samples: `docs/samples/` (100 KB maximum each; do not commit large files to Git).

To probe URLs and generate the status table:

```bash
python3 backend/scripts/explore_sources.py URL1 URL2 --output docs/samples
```

## Summary per source

| Source | Data or API URL | API or download? | Format | Filters | Limits | Legal notice and licence | Sample | Conclusion |
|---|---|---|---|---|---|---|---|---|
| BDNS / SNPSAP | https://www.infosubvenciones.es/bdnstrans/doc/swagger | Official REST API (JSON) and open CSV, PDF and XLSX downloads | Public aid and call records, including associated documents | Nationwide discovery; documented filters include administration, region, purpose, beneficiaries and title. No direct sector filter is declared on the call-search endpoint. Multi-value regions should be sent comma-separated per the API docs; the tested repeated form returned the same results for one query. | No numeric quota published in the notice or API docs reviewed; access may be restricted for abuse, security risks or fraudulent use. Apply conservative configurable pacing; bounded probe succeeded. | Reuse permitted for commercial and non-commercial purposes subject to source attribution, preserving meaning and metadata, no implied IGAE endorsement, and personal-data restrictions. See the [legal notice](https://www.pap.hacienda.gob.es/bdnstrans/GE/es/avisolegal). | Live pagination, state/regional filters, detail, PDF and ZIP succeeded in user's PowerShell with TLS validation. Search/detail/array JSON samples saved under `docs/samples/`. | Primary discovery and ingestion source; measure agricultural recall and verify extracted rules against linked call documents |
| Regional administrations | Links surfaced by BDNS for each call | Official aid index and procedure pages | Aid summaries, campaign status and links to procedures | All autonomous communities and cities; consult only where needed | Campaign pages and dates change | Check each administration’s site terms | Countrywide list of agency links to be assembled | Fallback for missing documents, changes or unclear application steps |
| Official gazettes (BOE, regional and provincial) | Linked from BDNS call records where applicable | Official gazettes | Binding orders, call extracts, amendments and corrections | Match the BDNS identifier, call title and dates | Must check amendments and extensions | Official gazette reuse terms | Exact call-by-call links to be captured | Preserve as the legal-publication reference for each call |
| FEGA / MAPA | https://www.fega.gob.es/ ; https://www.mapa.gob.es/ | Official national ministry and paying-agency pages | National CAP rules and state aid programmes | Nationwide | Campaign-specific | Check each site’s notice | Official sources located; selected aid verification pending | Cross-check national guidance when linked call text needs campaign context |
| datos.gob.es (catalogue) | unverified | unverified | unverified | unverified | unverified | | | |

## Notes

- The official API specification is published at `https://www.infosubvenciones.es/bdnstrans/doc/swagger` and links to its OpenAPI document. Do not use third-party endpoint guesses when the official specification is available.
- The SNPSAP notice links to [datos.gob.es guidance on API request limitations](https://datos.gob.es/es/blog/limitaciones-la-consulta-de-una-api). It describes general rate and volume controls, but gives no SNPSAP-specific numeric quota. Do not assume one; use conservative configurable pacing and observe server responses.
- The call-search endpoint has no sector filter. The first bounded audit and its 8-call positive panel measure recovery only in captured first pages; see [`bdns-search-recall-method.md`](bdns-search-recall-method.md).
- Attribute reused data to the Intervención General de la Administración del Estado, retain supplied update/reuse metadata, avoid implying endorsement, and exclude concessions/beneficiary datasets from the aid-discovery pipeline.
- `explore_sources.py` respects `robots.txt`: a URL that the site disallows for automated access is reported as SKIPPED and not fetched. In that case browse the page manually and look for an official API or download instead.
- The BDNS includes data about individuals in its grant awards. This project does not need to store them: do not download or publish them.

## Product coverage decision

The product is intended to cover **all of Spain**: national calls, calls from all 17 autonomous communities and the two autonomous cities, and local calls when relevant to agricultural holdings. Use BDNS/SNPSAP as the nationwide discovery and ingestion source, then follow each record to the official call text and responsible agency page when needed. Validate the end-to-end workflow with Aragón first, but do not make Aragón the geographic limit. Do not label coverage complete for a territory until its source records and aid categories have been measured.

For the first nationwide coverage pass, prioritize: (1) PAC direct payments and crop/livestock coupled support; (2) young farmer establishment and farm modernization; (3) agro-environmental and organic production measures; (4) agricultural insurance; (5) livestock health, extensive systems and native breeds; and (6) relevant emergency or investment calls. Track results by autonomous community and province where the call is territorial. Include only calls with a clear farm-beneficiary scope.

The official API specification, reuse notice, linked general API guidance and bounded endpoint probe have been reviewed in [`bdns-api-review.md`](bdns-api-review.md) and [`bdns-live-probe.md`](bdns-live-probe.md). Calls from the user's Windows PowerShell with normal TLS validation verified paginated searches, state/regional filters, an Aragón detail, PDF and ZIP downloads. The corrected nationwide first-page search audit was compared against an eight-call manually reviewed positive panel and recovered 3/8 examples (37.5%); this is a diagnostic of the bounded first-page capture, not a representative nationwide recall estimate. A bounded read-only client, Aragón source-call importer and source change/link tracking are implemented; see [`bdns-client.md`](bdns-client.md), [`bdns-importer.md`](bdns-importer.md) and [`bdns-change-detection.md`](bdns-change-detection.md). Safe PDF preservation passed the 32-test BDNS unit suite and was live-validated with an Aragón source document; see [`bdns-documents.md`](bdns-documents.md).

## Conclusion after the initial probe

- Which source will we use for the demo aids? BDNS nationwide for discovery, with linked official call documents as the first verification target. Live search/detail, bounded Aragón import and one source PDF download succeeded with TLS validation enabled; see the probe report, JSON samples and task guides.
- Live queries or a stored sample? Build and validate the importer against the captured local JSON samples first; live search and document retrieval succeeded from a trusted PowerShell runtime. Keep runtime use conservative and configurable.
- Which limits affect us? Reuse conditions and the API's abuse/security restriction are documented. No SNPSAP-specific numeric request quota was found in the notice, API documentation or linked general guidance; no throttling occurred in the small probe. Keep pacing configurable.
