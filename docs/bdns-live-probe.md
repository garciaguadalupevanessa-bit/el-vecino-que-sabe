# BDNS live probe — 2026-11-10

## Runtime and safety

The local project environment could not establish the API's TLS connection; certificate verification was left enabled. The user then ran the bounded checks from Windows PowerShell on the project copy at `C:\Users\Administrator\Desktop\ideal-octo-meme`. All API calls succeeded over HTTPS with normal certificate validation. The API JSON samples from that run are copied into this project's `docs/samples/` folder. The PDF and ZIP were saved to the user's temporary folder, not copied into the repository because the project sample guidance caps checked-in files at 100 KB.

All calls below are bounded to small search pages. The BDNS response itself warns that data can be corrected, inserted, modified or deleted after extraction.

## Successful checks

### Latest calls and pagination

Request: <https://www.infosubvenciones.es/bdnstrans/api/convocatorias/ultimas?page=0&pageSize=1&vpd=GE>

- HTTP/API response rendered successfully.
- Page 0 returned one call, `941269`, received 2026-11-10; the response reported page size 1, 10,000 total elements and 10,000 pages.
- A page size of 1 is accepted; this result is only a snapshot of the latest-call endpoint, not evidence that all 10,000 pages should be downloaded.

### Aragón regional search and pagination

Request (page 0): <https://www.infosubvenciones.es/bdnstrans/api/convocatorias/busqueda?page=0&pageSize=2&descripcion=agricultura&descripcionTipoBusqueda=2&regiones=21&vpd=GE>

Request (page 1): <https://www.infosubvenciones.es/bdnstrans/api/convocatorias/busqueda?page=1&pageSize=2&descripcion=agricultura&descripcionTipoBusqueda=2&regiones=21&vpd=GE>

- The API accepted a comma-style scalar region parameter (`regiones=21`). The regions catalog identifies `21` as Aragón and `22`, `23`, `24` as Huesca, Teruel and Zaragoza.
- Page 0 returned BDNS calls `920758` and `920752`; page 1 returned `919930` and `917459`. This confirms page numbering starts at zero and successive pages return different results for this query.
- The response reported 65 matches and 33 pages at page size 2.
- These title results include livestock-related subjects, but do not measure overall agricultural recall.

### State-level search

Request: <https://www.infosubvenciones.es/bdnstrans/api/convocatorias/busqueda?page=0&pageSize=2&tipoAdministracion=C&descripcion=agricultura&descripcionTipoBusqueda=2&vpd=GE>

- The API accepted `tipoAdministracion=C` for State Administration and returned records labelled `ESTADO`.
- The response reported 114 matches and 57 pages at page size 2. The first results included international agriculture calls, so the state filter alone does not mean a call benefits farms in Spain.

### Call detail

Request: <https://www.infosubvenciones.es/bdnstrans/api/convocatorias?numConv=920758&vpd=GE>

The detail response resolved call `920758` and included:

- Granting body: Aragón's Directorate-General for Quality and Food Safety.
- Sector: `AGRICULTURA, GANADERÍA, SILVICULTURA Y PESCA` (code `A`).
- Territory: `ES24 - ARAGON`.
- Purpose: Agriculture, Fisheries and Food.
- Stated budget: €200,000.
- Application window: “Sin plazo de solicitud”.
- Regulatory-bases URL: the consolidated Aragón Subsidies Act PDF on BOE.
- One associated PDF document, ID `1515086`, size 515,337 bytes, with publication/modification date 2026-09-01.

This is a livestock/food-safety instrumental grant to the University of Zaragoza, not a typical direct farm grant. It validates detail fields and document inventory, but must not be presented as an aid available to an ordinary farm.

## Checks blocked in this runtime

The following documented binary endpoints were first attempted in the browser, where the client blocked the binary responses. They then succeeded from the user's Windows PowerShell with TLS validation enabled, using the document ID and call number from the successful detail response:

- `GET /convocatorias/documentos?idDocumento=1515086`
- `GET /convocatorias/zip?id=920758&vpd=GE`

The PDF endpoint returned a 515,337-byte file; the ZIP endpoint returned a 471,526-byte file. Both were saved under `$env:TEMP` on the user's computer. The file contents have not been copied here or inspected, so only successful retrieval and reported sizes are verified.

## Current result

Search pagination, state/regional filters, call detail and both binary endpoints are verified live with normal TLS validation. Task 1.2 is complete. The multi-value parameter comparison is recorded below.

## Task 1.3 sample and limit record

- Saved the successful Aragón search and detail JSON as `docs/samples/aragon-search.json` and `docs/samples/aragon-detail.json`.
- The detail JSON records the associated PDF's ID, filename, size and source dates. Its live download succeeded at 515,337 bytes; the call ZIP succeeded at 471,526 bytes. The project sample policy caps individual samples at 100 KB, so the binaries were kept in the user's temporary folder and are not part of the working copy/archive.
- Search page sizes 1 and 2 succeeded. The latest-call endpoint reported 10,000 available pages at page size 1; this is a reported search window, not a recommendation to crawl the entire catalog.
- Requests were spaced by one second in the user's script. No API errors or throttling were reported during these bounded calls. This does not establish a server quota or general throughput allowance.
- The one-value regional query `regiones=21` succeeded. The OpenAPI parameter describes region IDs as comma-separated, while its array schema omits explicit `style`/`explode` settings. Both multi-value forms have since been tested (see below).
- Browser-client `ERR_BLOCKED_BY_CLIENT` and local-runtime connection failures occurred only in the initial probe environment; they were not API responses. The user's PowerShell requests succeeded with TLS validation enabled.
- The repeatable comparison script `scripts/probe-bdns-array-encoding.ps1` spaces its two requests by one second.

### Multi-value region parameter encoding

The user ran the comparison script from the project root using the same trusted PowerShell runtime. It tested:

- Comma-separated: `regiones=22,23`
- Repeated parameter: `regiones=22&regiones=23`

Both calls succeeded and returned 18 total matches, 2 records on the requested page, and the same first BDNS codes (`930573`, `923797`). Both responses are saved as `docs/samples/aragon-regions-comma.json` and `docs/samples/aragon-regions-repeated.json`. Use the comma-separated form in the importer because the official OpenAPI description explicitly documents comma-separated region IDs. This comparison confirms equivalent observed results for this filter/query, not every possible list parameter or query.
