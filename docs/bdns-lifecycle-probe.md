# BDNS date, amendment and source-link probe

Captured: 2026-11-10T23:53:26Z

## Recent-call endpoint

The earlier live probe called `/convocatorias/ultimas` with `page=0&pageSize=1` and received BDNS 941269 (`fechaRecepcion=2026-11-10`). The endpoint reported 10,000 total elements/pages at that page size. It is useful for recent-call discovery, but the retention window is not documented; see [`bdns-live-probe.md`](bdns-live-probe.md).

## Date-window result

- BDNS 920758 has fechaRecepcion=2026-07-22 in the saved detail sample.
- Exact same-day range (22/07/2026) returned the call: True (total 1).
- Next-day-only range (23/07/2026) returned the call: False (total 0).
- This is a single-record semantics probe, not proof of every edge case. Keep both the original date text and parsed date; do not interpret it as an application deadline.

## Amendments and no-extract calls

- BDNS 811615 returned two official announcement records: the original extract dated 2025-01-31 and a modification published 2025-06-03. The modification text extends the application deadline to 2025-05-15 and links to DOE announcement 25062278.
- The no-bulletin probe found BDNS 938663 (agricultural/livestock/beekeeping emergency aid; one document and a bases URL) and BDNS 920758 (University food-safety grant; one document and a bases URL), both with sePublicaDiarioOficial=false and zero announcement records. Absence of an extract must not be represented as an open call.
- A direct source link is evidence to inspect the underlying text; it is not, by itself, proof of current availability or eligibility.

## Official source-link checks

| BDNS | Link type | Host | Absolute URL | HTTP HEAD | URL |
|---|---|---|---|---|---|
| 811615 | official_gazette_announcement | doe.juntaex.es | True | HEAD succeeded | https://doe.juntaex.es/pdfs/doe/2025/1050o/25062278.pdf |
| 811615 | official_gazette_announcement | doe.juntaex.es | True | HEAD succeeded | https://doe.juntaex.es/pdfs/doe/2025/210o/25060248.pdf |
| 938663 | regulatory_bases | doe.juntaex.es | True | HEAD succeeded | https://doe.juntaex.es/pdfs/doe/2026/1740o/26DE0005.pdf |
| 909993 | regulatory_bases | dogv.gva.es | True | HEAD succeeded | https://dogv.gva.es/datos/consolidacion/2024/2024_7802_20240808_es.pdf |
| 909993 | official_gazette_announcement | dogv.gva.es | True | HEAD succeeded | https://dogv.gva.es/va/resultat-dogv?signatura=2026/19470 |
| 811615 | regulatory_bases | www.boe.es | True | HEAD succeeded | https://www.boe.es/boe/dias/2022/12/29/pdfs/BOE-A-2022-23048.pdf |
| 920758 | regulatory_bases | www.boe.es | True | HEAD succeeded | https://www.boe.es/buscar/pdf/2023/BOE-A-2023-12919-consolidado.pdf |

All seven HEAD checks against the allowlisted official gazette hosts returned HTTP 200 on 2026-11-10. HEAD failures can reflect server policy; confirm a failing link in a browser or with a bounded GET before treating it as broken.
