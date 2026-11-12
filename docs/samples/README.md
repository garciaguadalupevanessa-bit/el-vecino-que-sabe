# BDNS probe samples

The corrected national crop/livestock discovery audit is `agricultural-search-audit.json`. Its positive comparison panel and computed first-page recovery report are `agricultural-recall-seed-panel.json` and `agricultural-recall-report.md`. Recompute the report from the project root with `scripts/measure-agricultural-search-recall.ps1`. See [`../bdns-search-recall-method.md`](../bdns-search-recall-method.md) for scope and limitations.

For Task 1.5, `bdns-lifecycle-probe.json` contains the live date, amendment, no-extract and source-link checks; its readable summary is [`../bdns-lifecycle-probe.md`](../bdns-lifecycle-probe.md). Repeat them with `scripts/probe-bdns-lifecycle.ps1` from the project root.

These UTF-8 JSON snapshots were retrieved from the official BDNS/SNPSAP API on 2026-11-10 using Windows PowerShell with standard TLS certificate validation:

- `aragon-search.json`: first page (`page=0`, `pageSize=2`) of an agriculture title search filtered to Aragón (`regiones=21`).
- `aragon-detail.json`: detail for BDNS call `920758`.
- `aragon-regions-comma.json`: multi-value regional query using `regiones=22,23`.
- `aragon-regions-repeated.json`: the same query using repeated `regiones` parameters. It returned the same total and first-page call codes as the comma-separated form in this probe.

The API's `advertencia` field is retained in each response. These are point-in-time public call records and may change at the source. The associated PDF (515,337 bytes) and call ZIP (471,526 bytes) downloaded successfully to the user's temporary folder; they are not included here because the source-sample guidance caps files at 100 KB. The live test outcomes are in [`../bdns-live-probe.md`](../bdns-live-probe.md).

The JSON files are valid UTF-8 and parse successfully. The associated binary endpoints were checked for successful retrieval and reported byte counts only; the downloaded files have not been reviewed for document contents or ZIP integrity.

To repeat the comparison between comma-separated array values and repeated query parameters, run `scripts/probe-bdns-array-encoding.ps1` from the project root in a PowerShell environment with normal TLS validation. It writes two small JSON responses here and prints their result counts and call codes. The project uses comma-separated values because that is what the official API description specifies.
