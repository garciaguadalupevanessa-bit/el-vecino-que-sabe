# BDNS/SNPSAP API review

Reviewed against the official OpenAPI specification on 2026-11-10:

- Swagger: <https://www.infosubvenciones.es/bdnstrans/doc/swagger>
- OpenAPI JSON: <https://www.infosubvenciones.es/bdnstrans/estaticos/doc/snpsap-api.json>
- Production base URL listed by the specification: `https://www.infosubvenciones.es/bdnstrans/api`
- Reuse notice: <https://www.pap.hacienda.gob.es/bdnstrans/GE/es/avisolegal>
- API good-practice reference: <https://datos.gob.es/es/blog/limitaciones-la-consulta-de-una-api>

## What the specification confirms

### Search and pagination

`GET /convocatorias/busqueda` provides a paginated JSON search. Parameters include `page`, `pageSize`, `order`, `direccion`, title text (`descripcion` and `descripcionTipoBusqueda`), BDNS code (`numeroConvocatoria`), date-range fields (`fechaDesde`, `fechaHasta`; exact semantics need a live check), administration type (`tipoAdministracion`: State, Autonomous Community, Local, Other), granting-body IDs (`organos`), impact-region IDs (`regiones`), beneficiary type, aid instrument, expenditure purpose (`finalidad`) and State-aid reference.

The response includes `content`, `totalElements`, `totalPages`, paging metadata and a legal/dynamic-data warning. The specification does not declare an agricultural-sector filter on this search operation. It exposes date-range parameters, but their precise semantics need a live check. The detail record does contain economic sectors, beneficiary types, regions and purpose. For national coverage, use multiple discovery routes (purpose, title terms, administration/region and latest calls), then classify candidates using their detail records; measure false negatives during the live probe.

`GET /convocatorias/ultimas` is available for recent registered calls. A live page-0 request returned BDNS 941269 and reported 10,000 total records at page size 1; the retention window and change-polling behavior are not established. See [`bdns-live-probe.md`](bdns-live-probe.md).

### Details and source documents

- `GET /convocatorias?numConv=…` returns the detailed call record. The detail schema includes granting body, electronic application portal, BDNS code, eligible beneficiary types, economic sectors, impact regions, purpose, regulatory-bases title and URL, application start/end dates, literal date text, documents and official-gazette announcements.
- `GET /convocatorias/documentos?idDocumento=…` downloads an individual document as a binary file.
- `GET /convocatorias/zip?id=…&vpd=…` downloads the documents for a call in a ZIP archive.
- The detail response carries document IDs, names, descriptions and publication/modification dates, which can support version tracking.

The exact values, URL patterns and runtime reliability of these fields still need to be confirmed with live calls. The current specification describes the data as dynamic and subject to corrections, additions, modifications and deletions.

## Coverage approach implied by the API

Do not rely on one keyword search to claim nationwide coverage. A candidate discovery pass should combine administrative and territorial partitions with expenditure-purpose filters, title terms and recent-call polling. Fetch details for candidates and classify by sector, territory, beneficiaries and text. Maintain a list of queries and their last successful page/date so coverage can be audited. The missing sector filter is a specific recall risk to test before setting launch claims.

Do not query concessions or beneficiary datasets for the aid-discovery feature; they are not needed to find calls and can contain personal or sensitive information.

## Reuse terms and request pacing

The current SNPSAP legal notice permits reuse for commercial and non-commercial purposes. Reuse must preserve the meaning of the information, cite the source (the notice suggests “Origen de los datos: Intervención General de la Administración del Estado”), retain any supplied update-date and reuse-condition metadata, and must not imply IGAE sponsorship or endorsement. Where source records contain personal data, the notice limits reuse to public-management oversight or, for historical, statistical or scientific purposes, after prior disassociation. This product should therefore ingest public calls and their documents only, not concession/beneficiary data. The notice also says the supplying administration remains responsible for the information and disclaims guarantees of continuity and completeness.

The notice does not publish a numeric request-per-second or daily quota. It reserves the right to restrict API access for manifest abuse, security risks or fraudulent use, referring to open-data good practices. The linked datos.gob.es guidance explains why APIs can impose throughput, dynamic and data-volume controls, but it is general guidance and does not set an SNPSAP-specific quota. Do not encode an assumed numeric limit. Use a conservative configurable request interval, avoid parallel bulk downloads, cache responses, honor HTTP `Retry-After` and transient failure responses, and revisit the configuration if the API publishes explicit limits or begins returning throttling responses.

For product attribution, show the source and the last update date when the source provides one, and state that the service is independent and not endorsed by IGAE. Preserve relevant source metadata in stored records and displayed links.

## Runtime probe status

The official OpenAPI document was readable. The local project environment still cannot reach the host, with certificate checks left intact. The user ran the bounded probe from Windows PowerShell on the project copy with normal TLS validation; latest calls, paginated regional search, state-level search, a detailed Aragón call, document download and ZIP download all succeeded. Detailed requests and observed responses are recorded in [`bdns-live-probe.md`](bdns-live-probe.md), with search and detail JSON in `docs/samples/`.

The sample capture and bounded request-behavior checks are documented in [`bdns-live-probe.md`](bdns-live-probe.md). The importer should send multi-value region IDs as comma-separated values, as specified by the API; the live comparison returned the same results for the repeated form. Task 1.4's bounded first-page diagnostic is documented in [`bdns-search-recall-method.md`](bdns-search-recall-method.md), and Task 1.6's bounded latest-call/date/amendment/link probe is documented in [`bdns-lifecycle-validation.md`](bdns-lifecycle-validation.md). These probes do not establish complete nationwide coverage or immutable source history.

## Current conclusion

The API has the key capabilities needed for the proposed BDNS-first ingestion: national search, territorial filters, detailed call metadata, direct regulatory-bases URLs and call-document downloads. The bounded search audit shows that first-page capture is insufficient; the lifecycle probe confirms date matching, amendment records, no-extract records and example link reachability within the tested cases only.
