# BDNS call dates, amendments and source links

## Confirmed from the official API specification

The call search accepts `fechaDesde` and `fechaHasta` in `dd/MM/yyyy` form. Their descriptions say they bound the period used for the search, but do not identify the underlying date field or explicitly state whether the bounds are inclusive. The search result and detail schemas expose `fechaRecepcion` as the date BDNS received the call. Detail records separately expose `fechaInicioSolicitud`, `fechaFinSolicitud`, `textInicio` and `textFin`; these must not be treated as interchangeable. A live controlled check is prepared in `scripts/probe-bdns-lifecycle.ps1`.

The detail schema exposes an `anuncios` array for official extracts. Each entry can include the gazette name, publication date, URL and CVE. The `documentos` array separately lists files and may include `datPublicacion` and `datMod`. The API does not define a version number, a structured amendment type, or a parent-child link for amendments. Its response warning explicitly says records can be corrected, inserted, modified or deleted after extraction. Therefore, preserve the original payload and retrieval timestamp, compare later detail snapshots and document inventories, and retain every announcement instead of replacing older material with the latest one.

Relevant detail fields for recognizing records without an extract are `sePublicaDiarioOficial`, `anuncios`, `urlBasesReguladoras`, `documentos` and `sedeElectronica`. A missing announcement is not proof that a call is currently open or that its rules have been verified. Review the official call text and application portal before showing an application path.

## Existing record evidence

The earlier live probe also queried `GET /convocatorias/ultimas?page=0&pageSize=1&vpd=GE`. On 2026-11-10 it returned BDNS `941269`, received that day, and reported 10,000 total elements/pages at a page size of one. This confirms the latest-calls route and its pagination, but does not establish how far back the 10,000-record window extends or guarantee that it exposes every later amendment to an older call. Use it for incremental discovery with overlap and deduplication, then refresh individual detail records and their announcement/document inventories.

The saved Aragón detail sample, BDNS `920758`, has `fechaRecepcion=2026-07-22`, `sePublicaDiarioOficial=false`, no announcement in its response, a regulatory-bases URL and one downloadable call document. This demonstrates that a record can provide source material without a gazette extract. It is an instrumental University of Zaragoza food-safety grant, not direct farm aid, so it is a schema example only.

The live detail endpoint for BDNS `811615` returned two announcement records: the original PAC extract dated 2025-01-31 and a modification dated 2025-06-03. The modification text says the application deadline was extended to 2025-05-15 and links to the DOE. The detail also lists a call document with publication and modification dates of 2025-05-29. This confirms that `anuncios` preserves the original and later extract records in this example; the API still exposes no general version chain or amendment relationship.

The live detail records for BDNS `938663` and `920758` both say `sePublicaDiarioOficial=false` and return zero announcement records, while each still has one document and a regulatory-bases URL. BDNS `938663` is an agricultural/livestock/beekeeping emergency-aid example but has no application period in the record; absence of an extract must not be treated as an open call.

## Source hierarchy and link checks

Use the BDNS detail page as the discovery record, then preserve and inspect:

1. `anuncios[].url` and `anuncios[].cve` for the official gazette extract, amendment or correction.
2. `documentos[].id` via `/convocatorias/documentos` for the call's attached bases, order and application forms.
3. `urlBasesReguladoras` for the cited regulatory bases; check that it points to the actual rules rather than assuming it is the call notice.
4. `sedeElectronica` for the application portal, after confirming the current call is open and the portal link matches the official documents.

Validate URL syntax and redirects/reachability, but do not treat an HTTP success or an official-looking domain as proof that a deadline or rule is current. Keep the source URL, retrieval time, final URL/status, document ID and source dates. Recheck changed or failed links and preserve prior snapshots.

## Live probe result (2026-11-10)

The controlled query for BDNS `920758` returned one record when `fechaDesde` and `fechaHasta` were both `22/07/2026`, matching its `fechaRecepcion=2026-07-22`; a `23/07/2026`-only query returned zero. This supports interpreting the filter as the BDNS receipt/registration date for this record. It does not test every date boundary or every record class.

The probe checked seven linked bases/official-gazette URLs with HTTP HEAD; all returned HTTP 200. This verifies reachability at that time for these URLs only. A HEAD success does not validate the text, currentness, eligibility, or future availability of a link.

The JSON and readable run output are saved as [`samples/bdns-lifecycle-probe.json`](samples/bdns-lifecycle-probe.json) and `bdns-lifecycle-probe.md`. The probe is repeatable with `scripts/probe-bdns-lifecycle.ps1`.

**Task 1.6 is complete for the bounded examples tested.** Date semantics on other records, complete amendment/version history, the retention window of `/ultimas`, and nationwide link availability remain unproven; preserve snapshots and verify authoritative documents before presenting rules or deadlines.
