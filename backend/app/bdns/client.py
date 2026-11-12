"""Small, bounded, TLS-verified client for BDNS/SNPSAP call endpoints."""

from __future__ import annotations

import copy
import email.utils
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx


DEFAULT_BASE_URL = "https://www.infosubvenciones.es/bdnstrans/api"
DEFAULT_PORTAL_ID = "GE"
DEFAULT_PAGE_SIZE = 50
DEFAULT_MAX_PAGE_SIZE = 100
SEARCH_ORDER_FIELDS = {
    "numeroConvocatoria",
    "mrr",
    "nivel1",
    "nivel2",
    "nivel3",
    "fechaRecepcion",
    "descripcion",
    "descripcionLeng",
}


class BDNSClientError(RuntimeError):
    """Base class for BDNS client errors."""


class BDNSHTTPError(BDNSClientError):
    """A non-success HTTP response from the BDNS API."""

    def __init__(self, status_code: int, message: str, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class BDNSNetworkError(BDNSClientError):
    """A connection, timeout, or other transport error."""


class BDNSResponseError(BDNSClientError):
    """A successful HTTP response that does not match the expected JSON shape."""


class BDNSDocumentError(BDNSResponseError):
    """A source document failed configured size or PDF validation limits."""


@dataclass(frozen=True)
class BDNSFilters:
    """Documented call-search filters. No sector filter exists in this endpoint."""

    title: str | None = None
    title_search_mode: Literal[0, 1, 2] | None = None
    bdns_code: str | None = None
    received_from: date | None = None
    received_to: date | None = None
    administration_type: Literal["C", "A", "L", "O"] | None = None
    bodies: tuple[str, ...] = ()
    regions: tuple[int, ...] = ()
    beneficiary_types: tuple[int, ...] = ()
    instruments: tuple[int, ...] = ()
    purpose_id: int | None = None
    state_aid_number: str | None = None
    mrr: bool | None = None
    international_contribution: bool | None = None
    order: str | None = None
    direction: Literal["asc", "desc"] | None = None

    def __post_init__(self) -> None:
        if self.title_search_mode is not None and self.title is None:
            raise ValueError("title_search_mode requires a title.")
        if self.title_search_mode is not None and self.title_search_mode not in (0, 1, 2):
            raise ValueError("title_search_mode must be 0, 1, or 2.")
        if self.received_from and self.received_to and self.received_from > self.received_to:
            raise ValueError("received_from must be on or before received_to.")
        if self.order is not None and self.order not in SEARCH_ORDER_FIELDS:
            raise ValueError(f"Unsupported order field: {self.order}.")
        for name, values in (
            ("regions", self.regions),
            ("beneficiary_types", self.beneficiary_types),
            ("instruments", self.instruments),
        ):
            if any(value < 0 for value in values):
                raise ValueError(f"{name} values must be non-negative.")
        if self.purpose_id is not None and self.purpose_id < 0:
            raise ValueError("purpose_id must be non-negative.")

    def to_query_params(self) -> dict[str, str | list[str]]:
        """Map internal names to BDNS names and documented array encodings."""
        params: dict[str, str | list[str]] = {}
        scalar_values: tuple[tuple[str, Any], ...] = (
            ("descripcion", self.title),
            ("descripcionTipoBusqueda", self.title_search_mode),
            ("numeroConvocatoria", self.bdns_code),
            ("fechaDesde", self.received_from.strftime("%d/%m/%Y") if self.received_from else None),
            ("fechaHasta", self.received_to.strftime("%d/%m/%Y") if self.received_to else None),
            ("tipoAdministracion", self.administration_type),
            ("finalidad", self.purpose_id),
            ("ayudaEstado", self.state_aid_number),
            ("mrr", self.mrr),
            ("contribucion", self.international_contribution),
            ("order", self.order),
            ("direccion", self.direction),
        )
        for name, value in scalar_values:
            if value is not None:
                params[name] = str(value).lower() if isinstance(value, bool) else str(value)

        # The specification says these identifiers are comma-separated.
        for name, values in (
            ("regiones", self.regions),
            ("tiposBeneficiario", self.beneficiary_types),
            ("instrumentos", self.instruments),
        ):
            if values:
                params[name] = ",".join(str(value) for value in values)

        # OpenAPI's default array serialization is form/explode=true for organos.
        if self.bodies:
            params["organos"] = list(self.bodies)
        return params


class BDNSClient:
    """Synchronous read-only BDNS client with in-memory TTL cache and pacing.

    TLS verification is always left to httpx's secure default. Large result sets
    require an explicit page bound through ``iter_search``/``iter_latest``.
    """

    TRANSIENT_STATUSES = {429, 500, 502, 503, 504}

    @classmethod
    def from_config(cls) -> BDNSClient:
        """Create a client using the backend's BDNS environment configuration."""
        from app.core import config

        return cls(
            base_url=config.BDNS_API_BASE_URL,
            portal_id=config.BDNS_PORTAL_ID,
            timeout_seconds=config.BDNS_TIMEOUT_SECONDS,
            minimum_request_interval=config.BDNS_MIN_REQUEST_INTERVAL_SECONDS,
            cache_ttl_seconds=config.BDNS_CACHE_TTL_SECONDS,
            max_retries=config.BDNS_MAX_RETRIES,
            max_page_size=config.BDNS_MAX_PAGE_SIZE,
        )

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        portal_id: str = DEFAULT_PORTAL_ID,
        timeout_seconds: float = 30.0,
        minimum_request_interval: float = 1.0,
        cache_ttl_seconds: float = 300.0,
        max_retries: int = 2,
        max_page_size: int = DEFAULT_MAX_PAGE_SIZE,
        retry_backoff_seconds: float = 1.0,
        max_retry_after_seconds: float = 120.0,
        http_client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        parsed_base = urlsplit(base_url)
        if parsed_base.scheme.lower() != "https" or not parsed_base.netloc:
            raise ValueError("The BDNS base URL must use HTTPS.")
        if not portal_id.strip():
            raise ValueError("portal_id cannot be empty.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if minimum_request_interval < 0 or cache_ttl_seconds < 0:
            raise ValueError("request interval and cache TTL cannot be negative.")
        if max_retries < 0 or max_page_size < 1:
            raise ValueError("max_retries must be non-negative and max_page_size positive.")
        if retry_backoff_seconds < 0 or max_retry_after_seconds < 0:
            raise ValueError("retry delays cannot be negative.")

        self.base_url = base_url.rstrip("/")
        self.portal_id = portal_id
        self.timeout_seconds = timeout_seconds
        self.minimum_request_interval = minimum_request_interval
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_retries = max_retries
        self.max_page_size = max_page_size
        self.retry_backoff_seconds = retry_backoff_seconds
        self.max_retry_after_seconds = max_retry_after_seconds
        self._clock = clock
        self._sleep = sleeper
        self._http = http_client or httpx.Client(timeout=timeout_seconds)
        self._owns_http_client = http_client is None
        self._cache: dict[tuple[str, tuple[tuple[str, str], ...]], tuple[float, Any]] = {}
        self._last_request_at: float | None = None
        self._request_lock = threading.Lock()

    def close(self) -> None:
        if self._owns_http_client:
            self._http.close()

    def __enter__(self) -> BDNSClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def search_calls(
        self,
        filters: BDNSFilters | None = None,
        *,
        page: int = 0,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        self._validate_page(page, page_size)
        params: dict[str, str | list[str]] = {
            "page": str(page),
            "pageSize": str(page_size),
            "vpd": self.portal_id,
        }
        if filters:
            params.update(filters.to_query_params())
        return self._get_search_page("/convocatorias/busqueda", params)

    def latest_calls(
        self,
        *,
        page: int = 0,
        page_size: int = DEFAULT_PAGE_SIZE,
        order: str | None = None,
        direction: Literal["asc", "desc"] | None = None,
    ) -> dict[str, Any]:
        self._validate_page(page, page_size)
        if order is not None and order not in SEARCH_ORDER_FIELDS:
            raise ValueError(f"Unsupported order field: {order}.")
        params: dict[str, str] = {
            "page": str(page),
            "pageSize": str(page_size),
            "vpd": self.portal_id,
        }
        if order is not None:
            params["order"] = order
        if direction is not None:
            params["direccion"] = direction
        return self._get_search_page("/convocatorias/ultimas", params)

    def get_call(self, bdns_code: str) -> dict[str, Any]:
        code = bdns_code.strip()
        if not code:
            raise ValueError("bdns_code cannot be empty.")
        params = {"numConv": code, "vpd": self.portal_id}
        result = self._request_json("/convocatorias", params)
        if not isinstance(result, dict):
            raise BDNSResponseError("BDNS call detail response must be a JSON object.")
        returned_code = result.get("codigoBDNS")
        if returned_code is not None and str(returned_code) != code:
            raise BDNSResponseError(
                f"BDNS returned call {returned_code!s} for requested code {code!r}."
            )
        return result

    def get_regions(self) -> list[dict[str, Any]]:
        """Return BDNS's official region hierarchy used by the search filters."""
        result = self._request_json("/regiones", {"vpd": self.portal_id})
        if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
            raise BDNSResponseError("BDNS region catalog must be an array of objects.")
        return result

    def download_document(
        self, document_id: int, *, max_bytes: int = 25 * 1024 * 1024
    ) -> tuple[bytes, str]:
        """Download one bounded PDF document, validating media type and file signature."""
        if isinstance(document_id, bool) or not isinstance(document_id, int) or document_id < 1:
            raise ValueError("document_id must be a positive integer.")
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive.")
        endpoint = "/convocatorias/documentos"
        params = {"idDocumento": str(document_id)}
        url = f"{self.base_url}{endpoint}"

        with self._request_lock:
            for attempt in range(self.max_retries + 1):
                self._wait_for_request_slot()
                try:
                    with self._http.stream(
                        "GET", url, params=params, timeout=self.timeout_seconds
                    ) as response:
                        if response.status_code in self.TRANSIENT_STATUSES:
                            retry_after = self._retry_after_seconds(response.headers.get("Retry-After"))
                            if attempt >= self.max_retries:
                                raise BDNSHTTPError(
                                    response.status_code,
                                    f"BDNS document request returned HTTP {response.status_code} after {attempt + 1} attempts.",
                                    retry_after_seconds=retry_after,
                                )
                            delay = retry_after if retry_after is not None else self._backoff(attempt)
                            if retry_after is not None and delay > self.max_retry_after_seconds:
                                raise BDNSHTTPError(
                                    response.status_code,
                                    "BDNS Retry-After exceeds the configured in-process wait limit; retry later.",
                                    retry_after_seconds=retry_after,
                                )
                            self._sleep(delay)
                            continue
                        if response.is_error:
                            raise BDNSHTTPError(
                                response.status_code,
                                f"BDNS document request returned HTTP {response.status_code}.",
                            )

                        media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                        if media_type not in ("", "application/pdf", "application/octet-stream"):
                            raise BDNSDocumentError(
                                f"BDNS document has unsupported media type {media_type!r}; only PDF is accepted."
                            )
                        length = response.headers.get("Content-Length")
                        if length is not None:
                            try:
                                if int(length) > max_bytes:
                                    raise BDNSDocumentError(
                                        f"BDNS document exceeds the {max_bytes}-byte limit."
                                    )
                            except ValueError as exc:
                                raise BDNSDocumentError("BDNS document has an invalid Content-Length.") from exc

                        chunks = []
                        total = 0
                        for chunk in response.iter_bytes(64 * 1024):
                            total += len(chunk)
                            if total > max_bytes:
                                raise BDNSDocumentError(
                                    f"BDNS document exceeds the {max_bytes}-byte limit."
                                )
                            chunks.append(chunk)
                        content = b"".join(chunks)
                        if not content.startswith(b"%PDF-"):
                            raise BDNSDocumentError("BDNS document content is not a PDF file.")
                        return content, media_type or "application/pdf"
                except httpx.TransportError as exc:
                    if attempt >= self.max_retries:
                        raise BDNSNetworkError(f"BDNS document download failed: {exc}") from exc
                    self._sleep(self._backoff(attempt))
        raise BDNSClientError("BDNS document request ended without a response.")

    def iter_search(
        self,
        filters: BDNSFilters | None = None,
        *,
        max_pages: int,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[dict[str, Any]]:
        yield from self._iter_pages(
            lambda page: self.search_calls(filters, page=page, page_size=page_size),
            max_pages=max_pages,
            page_size=page_size,
        )

    def iter_latest(
        self,
        *,
        max_pages: int,
        page_size: int = DEFAULT_PAGE_SIZE,
        order: str | None = None,
        direction: Literal["asc", "desc"] | None = None,
    ) -> Iterator[dict[str, Any]]:
        yield from self._iter_pages(
            lambda page: self.latest_calls(
                page=page, page_size=page_size, order=order, direction=direction
            ),
            max_pages=max_pages,
            page_size=page_size,
        )

    def _iter_pages(
        self,
        fetch: Callable[[int], dict[str, Any]],
        *,
        max_pages: int,
        page_size: int,
    ) -> Iterator[dict[str, Any]]:
        if max_pages < 1:
            raise ValueError("max_pages must be at least one; pagination must be explicitly bounded.")
        self._validate_page(0, page_size)
        seen_codes: set[str] = set()
        for page in range(max_pages):
            response = fetch(page)
            for item in response["content"]:
                code = item.get("numeroConvocatoria") or item.get("codigoBDNS") or item.get("id")
                key = str(code) if code is not None else None
                if key is not None and key in seen_codes:
                    continue
                if key is not None:
                    seen_codes.add(key)
                yield item
            total_pages = response.get("totalPages")
            if response.get("last") is True or not response["content"]:
                break
            if isinstance(total_pages, int) and page + 1 >= total_pages:
                break

    def _validate_page(self, page: int, page_size: int) -> None:
        if page < 0:
            raise ValueError("page must be non-negative.")
        if page_size < 1 or page_size > self.max_page_size:
            raise ValueError(f"page_size must be between 1 and {self.max_page_size}.")

    def _get_search_page(
        self, endpoint: str, params: Mapping[str, str | list[str]]
    ) -> dict[str, Any]:
        result = self._request_json(endpoint, params)
        if not isinstance(result, dict) or not isinstance(result.get("content"), list):
            raise BDNSResponseError("BDNS search response must contain a content array.")
        if any(not isinstance(item, dict) for item in result["content"]):
            raise BDNSResponseError("BDNS search content must contain JSON objects.")
        return result

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = email.utils.parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None

    def _request_json(
        self, endpoint: str, params: Mapping[str, str | list[str]]
    ) -> Any:
        cache_params = tuple(sorted((key, tuple(value) if isinstance(value, list) else str(value)) for key, value in params.items()))
        cache_key = (endpoint, tuple((key, ",".join(value) if isinstance(value, tuple) else value) for key, value in cache_params))
        now = self._clock()
        cached = self._cache.get(cache_key)
        if cached and self.cache_ttl_seconds > 0 and now - cached[0] < self.cache_ttl_seconds:
            return copy.deepcopy(cached[1])

        with self._request_lock:
            # Recheck after acquiring the lock so simultaneous identical reads share one request.
            now = self._clock()
            cached = self._cache.get(cache_key)
            if cached and self.cache_ttl_seconds > 0 and now - cached[0] < self.cache_ttl_seconds:
                return copy.deepcopy(cached[1])
            url = f"{self.base_url}{endpoint}"
            for attempt in range(self.max_retries + 1):
                self._wait_for_request_slot()
                try:
                    response = self._http.get(url, params=params, timeout=self.timeout_seconds)
                except httpx.TransportError as exc:
                    if attempt >= self.max_retries:
                        raise BDNSNetworkError(f"BDNS request failed: {exc}") from exc
                    self._sleep(self._backoff(attempt))
                    continue

                if response.status_code in self.TRANSIENT_STATUSES:
                    retry_after = self._retry_after_seconds(response.headers.get("Retry-After"))
                    if attempt >= self.max_retries:
                        raise BDNSHTTPError(
                            response.status_code,
                            f"BDNS returned HTTP {response.status_code} after {attempt + 1} attempts.",
                            retry_after_seconds=retry_after,
                        )
                    delay = retry_after if retry_after is not None else self._backoff(attempt)
                    if retry_after is not None and delay > self.max_retry_after_seconds:
                        raise BDNSHTTPError(
                            response.status_code,
                            "BDNS Retry-After exceeds the configured in-process wait limit; retry later.",
                            retry_after_seconds=retry_after,
                        )
                    self._sleep(delay)
                    continue
                if response.is_error:
                    body = response.text[:500]
                    raise BDNSHTTPError(
                        response.status_code,
                        f"BDNS returned HTTP {response.status_code}: {body}",
                    )
                try:
                    data = response.json()
                except ValueError as exc:
                    raise BDNSResponseError("BDNS returned invalid JSON.") from exc
                if self.cache_ttl_seconds > 0:
                    self._cache[cache_key] = (self._clock(), copy.deepcopy(data))
                return data
        raise BDNSClientError("BDNS request ended without a response.")

    def _wait_for_request_slot(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            wait_seconds = self.minimum_request_interval - (now - self._last_request_at)
            if wait_seconds > 0:
                self._sleep(wait_seconds)
        self._last_request_at = self._clock()

    def _backoff(self, attempt: int) -> float:
        return min(self.retry_backoff_seconds * (2**attempt), 30.0)
