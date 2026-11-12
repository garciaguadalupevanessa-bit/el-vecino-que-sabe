# BDNS API client

The read-only BDNS/SNPSAP client lives in `backend/app/bdns/client.py`. It covers the call-search, latest-calls, call-detail and size-limited PDF-download endpoints. The source-call importer and separate document storage/inventory workflows are documented in [`bdns-importer.md`](bdns-importer.md) and [`bdns-documents.md`](bdns-documents.md).

## Safety and operational behavior

- HTTPS is required for the configured API base URL. `httpx` certificate verification stays enabled.
- Search pagination is explicit and bounded: callers must provide `max_pages` to `iter_search` or `iter_latest`. Page sizes are capped locally at 100 by default; this is an application safeguard, not a claim about an official BDNS limit.
- The client waits at least one second between physical requests by default, including retries. Repeated identical GETs are served from a five-minute in-memory TTL cache by default; cache results are copied before return.
- Timeouts, retries, backoff, page-size cap, request interval, cache TTL, base URL and portal identifier are configurable. Retry-After is honored up to a configured wait ceiling; larger values return a retryable client error instead of blocking for a long time.
- Search filters map the tested/documented API names, including comma-separated region, beneficiary-type and instrument lists, and repeated `organos` parameters. Search filters cannot establish that a call is relevant to agriculture; classification belongs to later ingestion and review.
- Errors are raised as typed client exceptions. Search and detail responses are checked for the JSON shape and requested BDNS identity expected by callers.

## Configuration

Set these environment variables for the backend; defaults are shown in `.env.example`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BDNS_API_BASE_URL` | `https://www.infosubvenciones.es/bdnstrans/api` | HTTPS API base |
| `BDNS_PORTAL_ID` | `GE` | BDNS portal identifier |
| `BDNS_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `BDNS_MIN_REQUEST_INTERVAL_SECONDS` | `1` | Minimum spacing between physical requests |
| `BDNS_CACHE_TTL_SECONDS` | `300` | In-memory response cache lifetime |
| `BDNS_MAX_RETRIES` | `2` | Retries after the initial attempt |
| `BDNS_MAX_PAGE_SIZE` | `100` | Local page-size ceiling |

The client accepts these values as constructor arguments. The environment settings are prepared for the importer to instantiate it in task 2.3; this task deliberately does not wire database ingestion or application routes.

## Example

```python
from datetime import date

from app.bdns import BDNSClient, BDNSFilters

with BDNSClient() as client:
    filters = BDNSFilters(
        title="agricultura",
        received_from=date(2026, 1, 1),
        received_to=date(2026, 12, 31),
        regions=(2, 21),
    )
    for call in client.iter_search(filters, max_pages=3, page_size=50):
        print(call)
```

## Validation status

Unit tests use `httpx.MockTransport`, so they do not depend on network availability or issue live requests. A live BDNS TLS and endpoint probe was already completed in phase 1 and is documented in [`bdns-live-probe.md`](bdns-live-probe.md). Re-run the client tests in the backend environment with `python -m pytest tests/test_bdns_client.py` before integrating it into the importer.
