from datetime import date

import httpx
import pytest

from app.bdns import (
    BDNSClient,
    BDNSDocumentError,
    BDNSFilters,
    BDNSHTTPError,
    BDNSResponseError,
)


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    return BDNSClient(
        http_client=httpx.Client(transport=transport),
        minimum_request_interval=0,
        **kwargs,
    )


def test_filters_encode_documented_query_parameters():
    filters = BDNSFilters(
        title="agricultura",
        title_search_mode=2,
        received_from=date(2026, 1, 2),
        received_to=date(2026, 2, 3),
        regions=(2, 21),
        beneficiary_types=(1, 4),
        instruments=(2, 5),
        bodies=("ministerio", "comunidad"),
        purpose_id=12,
        mrr=False,
    )
    params = filters.to_query_params()
    assert params["descripcion"] == "agricultura"
    assert params["descripcionTipoBusqueda"] == "2"
    assert params["fechaDesde"] == "02/01/2026"
    assert params["fechaHasta"] == "03/02/2026"
    assert params["regiones"] == "2,21"
    assert params["tiposBeneficiario"] == "1,4"
    assert params["instrumentos"] == "2,5"
    assert params["organos"] == ["ministerio", "comunidad"]
    assert params["finalidad"] == "12"
    assert params["mrr"] == "false"


def test_search_paginates_with_explicit_bound_and_deduplicates():
    requested = []

    def handler(request):
        requested.append(request.url.params["page"])
        page = int(request.url.params["page"])
        rows = ([{"numeroConvocatoria": "1"}, {"numeroConvocatoria": "2"}]
                if page == 0 else [{"numeroConvocatoria": "2"}, {"numeroConvocatoria": "3"}])
        return httpx.Response(200, json={"content": rows, "totalPages": 4, "last": False})

    client = make_client(handler)
    rows = list(client.iter_search(max_pages=2, page_size=2))
    assert [row["numeroConvocatoria"] for row in rows] == ["1", "2", "3"]
    assert requested == ["0", "1"]
    client.close()


def test_latest_calls_uses_latest_endpoint():
    def handler(request):
        assert request.url.path.endswith("/convocatorias/ultimas")
        assert request.url.params["vpd"] == "GE"
        return httpx.Response(200, json={"content": [], "last": True})

    client = make_client(handler)
    assert client.latest_calls()["content"] == []
    client.close()


def test_region_catalog_returns_the_official_hierarchy():
    expected = [{"id": 21, "descripcion": "ES24 - ARAGÓN", "children": []}]

    def handler(request):
        assert request.url.path.endswith("/regiones")
        assert request.url.params["vpd"] == "GE"
        return httpx.Response(200, json=expected)

    client = make_client(handler)
    assert client.get_regions() == expected
    client.close()


def test_cache_returns_defensive_copies():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"content": [{"value": 1}]})

    client = make_client(handler)
    first = client.search_calls()
    first["content"][0]["value"] = 99
    second = client.search_calls()
    assert calls == 1
    assert second["content"][0]["value"] == 1
    client.close()


def test_transient_status_retries_and_honors_retry_after():
    calls = 0
    delays = []

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"content": []})

    client = make_client(handler, sleeper=delays.append, max_retries=1)
    assert client.search_calls()["content"] == []
    assert calls == 2
    assert delays == [2.0]
    client.close()


def test_retry_after_over_limit_is_reported_without_long_wait():
    def handler(request):
        return httpx.Response(429, headers={"Retry-After": "999"})

    client = make_client(handler, sleeper=lambda _: pytest.fail("must not sleep"))
    with pytest.raises(BDNSHTTPError, match="exceeds"):
        client.search_calls()
    client.close()


def test_non_transient_http_error_is_not_retried():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(404, text="missing")

    client = make_client(handler, max_retries=3)
    with pytest.raises(BDNSHTTPError) as error:
        client.get_call("123")
    assert error.value.status_code == 404
    assert calls == 1
    client.close()


def test_malformed_search_and_detail_shapes_are_rejected():
    client = make_client(lambda request: httpx.Response(200, json=[]))
    with pytest.raises(BDNSResponseError):
        client.search_calls()
    with pytest.raises(BDNSResponseError):
        client.get_call("123")
    client.close()


def test_bad_detail_identity_is_rejected():
    client = make_client(lambda request: httpx.Response(200, json={"codigoBDNS": "999"}))
    with pytest.raises(BDNSResponseError, match="requested code"):
        client.get_call("123")
    client.close()


def test_unsafe_urls_and_unbounded_pagination_are_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        BDNSClient(base_url="http://localhost/api")
    client = make_client(lambda request: httpx.Response(200, json={"content": []}))
    with pytest.raises(ValueError, match="explicitly bounded"):
        list(client.iter_search(max_pages=0))
    with pytest.raises(ValueError, match="page_size"):
        client.search_calls(page_size=101)
    client.close()


def test_pdf_download_checks_media_signature_and_size():
    pdf = b"%PDF-1.7\nfixture"
    client = make_client(lambda request: httpx.Response(
        200, content=pdf, headers={"Content-Type": "application/pdf"}
    ))
    content, content_type = client.download_document(42, max_bytes=100)
    assert content == pdf
    assert content_type == "application/pdf"
    client.close()

    oversized = make_client(lambda request: httpx.Response(
        200, content=pdf, headers={"Content-Type": "application/pdf", "Content-Length": "500"}
    ))
    with pytest.raises(BDNSDocumentError, match="exceeds"):
        oversized.download_document(42, max_bytes=100)
    oversized.close()


def test_pdf_download_rejects_html_and_streamed_oversize():
    html = make_client(lambda request: httpx.Response(
        200, content=b"<html>not a pdf</html>", headers={"Content-Type": "text/html"}
    ))
    with pytest.raises(BDNSDocumentError, match="media type"):
        html.download_document(42)
    html.close()

    streamed = make_client(lambda request: httpx.Response(
        200, stream=httpx.ByteStream(b"%PDF-" + b"x" * 100),
        headers={"Content-Type": "application/pdf"},
    ))
    with pytest.raises(BDNSDocumentError, match="exceeds"):
        streamed.download_document(42, max_bytes=20)
    streamed.close()


def test_pdf_download_rejects_invalid_document_ids():
    client = make_client(lambda request: httpx.Response(200, content=b"%PDF-1.7"))
    with pytest.raises(ValueError, match="positive integer"):
        client.download_document(0)
    client.close()
