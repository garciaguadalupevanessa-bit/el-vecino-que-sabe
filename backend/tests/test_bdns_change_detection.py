import httpx

from app.bdns.change_detection import changed_paths, extract_source_links, payload_sha256
from app.bdns.link_checker import OfficialLinkChecker, check_and_record_links


def test_payload_hash_ignores_json_key_order_and_whitespace():
    assert payload_sha256({"b": 2, "a": 1}) == payload_sha256({"a": 1, "b": 2})


def test_changed_paths_report_changed_fields_without_values():
    old = {"descripcion": "Old", "fecha": "2026-01-01", "items": [1, 2]}
    new = {"descripcion": "New", "items": [1, 3], "extra": True}
    assert changed_paths(old, new) == ["descripcion", "extra", "fecha", "items"]


def test_extract_source_links_uses_stable_keys_and_keeps_http_sources_for_review():
    record = {
        "source_identity": {"bdns_code": "123", "detail_url": "https://example.gov/call/123"},
        "application": {"application_portal_url": "https://region.example/apply"},
        "call": {"state_aid": {"url": "http://example.gov/state-aid"}},
        "sources": {
            "regulatory_bases": {"url": "https://boe.example/rules"},
            "documents": [{"bdns_document_id": 7, "download_url": "https://example.gov/doc/7"}],
            "announcements": [{"id": 88, "urlExtracto": "https://gazette.example/88"}],
        },
    }
    links = extract_source_links(record)
    assert {(item["resource_type"], item["resource_key"]) for item in links} == {
        ("call_detail", "123"), ("application_portal", "application"),
        ("regulatory_bases", "bases"), ("state_aid", "regulation"),
        ("document", "7"), ("announcement", "88:urlExtracto"),
    }


def test_link_checker_follows_redirect_and_falls_back_to_range_get():
    requests = []

    def handler(request):
        requests.append((request.method, str(request.url)))
        if request.url.host == "origin.example":
            return httpx.Response(301, headers={"Location": "https://target.example/final"})
        if request.method == "HEAD":
            return httpx.Response(405)
        assert request.headers["Range"] == "bytes=0-0"
        return httpx.Response(206, headers={"Content-Range": "bytes 0-0/100"})

    http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    checker = OfficialLinkChecker(
        http_client=http,
        minimum_request_interval=0,
        resolver=lambda host, port: ["8.8.8.8"],
    )
    result = checker.check("https://origin.example/start")
    assert result == {"status": "reachable", "status_code": 206, "last_error": None}
    assert [method for method, _ in requests] == ["HEAD", "HEAD", "GET"]
    checker.close()
    http.close()


def test_link_checker_only_marks_definitive_missing_responses_broken():
    def handler(request):
        return httpx.Response({"/missing": 404, "/gone": 410, "/forbidden": 403,
                               "/bad-request": 400}.get(request.url.path, 503))

    http = httpx.Client(transport=httpx.MockTransport(handler))
    checker = OfficialLinkChecker(http_client=http, minimum_request_interval=0, resolver=lambda host, port: ["8.8.8.8"])
    assert checker.check("https://source.example/missing")["status"] == "broken"
    assert checker.check("https://source.example/gone")["status"] == "broken"
    assert checker.check("https://source.example/forbidden")["status"] == "unknown"
    assert checker.check("https://source.example/bad-request")["status"] == "unknown"
    assert checker.check("https://source.example/outage")["status"] == "unknown"
    checker.close()
    http.close()


def test_link_checker_retries_forbidden_head_with_bounded_range_get():
    requests = []

    def handler(request):
        requests.append(request.method)
        return httpx.Response(403 if request.method == "HEAD" else 206)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    checker = OfficialLinkChecker(
        http_client=http, minimum_request_interval=0,
        resolver=lambda host, port: ["8.8.8.8"],
    )
    result = checker.check("https://source.example/restricted-head")
    assert result == {"status": "reachable", "status_code": 206, "last_error": None}
    assert requests == ["HEAD", "GET"]
    checker.close()
    http.close()


def test_link_checker_blocks_insecure_or_private_redirect_targets():
    http = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"Location": "http://127.0.0.1/admin"})
    ))
    checker = OfficialLinkChecker(http_client=http, minimum_request_interval=0, resolver=lambda host, port: ["8.8.8.8"])
    result = checker.check("https://source.example/redirect")
    assert result["status"] == "unknown"
    assert "HTTPS" in result["last_error"]
    checker.close()
    http.close()


def test_check_and_record_persists_each_status_and_commits():
    class Checker:
        def check(self, url):
            return {"status": "reachable", "status_code": 200, "last_error": None}

    class Connection:
        def __init__(self):
            self.commits = 0

        def commit(self):
            self.commits += 1

    conn = Connection()
    recorded = []
    results = check_and_record_links(
        Checker(), conn, [{"bdns_code": "1", "resource_type": "bases", "resource_key": "bases", "url": "https://example.org"}],
        record_check=lambda db_conn, item: recorded.append(item),
    )
    assert results == recorded
    assert results[0]["status"] == "reachable"
    assert conn.commits == 1
