"""Tests for the Phase 0 helper scripts (no external network, no API key)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace as NS

import pytest

from scripts import explore_sources as es
from scripts import probe_groq as pg


# ---------- probe_groq ----------
def _resp(name="search_aids", args=None, tool=True):
    args = {"region": "Aragón", "livestock_type": "sheep"} if args is None else args
    calls = [NS(function=NS(name=name, arguments=args if isinstance(args, str) else json.dumps(args)))] if tool else None
    return NS(choices=[NS(message=NS(tool_calls=calls))])


class Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.chat = NS(completions=NS(create=self._create))
        self.models = NS(list=lambda: NS(data=[NS(id="model-b"), NS(id="model-a")]))

    def _create(self, **kw):
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_list_models_is_sorted():
    assert pg.list_models(Client([])) == ["model-a", "model-b"]


def test_tool_calling_correct():
    r = pg.probe_tool_calling(Client([_resp(), _resp()]), "m", attempts=2, pause=0)
    assert r == {"attempts": 2, "correct": 2, "failures": []}


def test_tool_calling_detects_each_kind_of_failure():
    client = Client([
        _resp(tool=False),
        _resp(args="{not json"),
        _resp(args={"region": "Aragón", "livestock_type": "cattle"}),
        RuntimeError("rate limit"),
    ])
    r = pg.probe_tool_calling(client, "m", attempts=4, pause=0)
    assert r["correct"] == 0 and len(r["failures"]) == 4
    assert "without calling" in r["failures"][0] and "JSON" in r["failures"][1]
    assert "unexpected" in r["failures"][2] and "RuntimeError" in r["failures"][3]


def test_main_without_key_returns_2(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert pg.main([]) == 2


# ---------- explore_sources ----------
class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/json":
            body, ctype, code = b'{"ok": true}', "application/json; charset=utf-8", 200
        elif self.path == "/robots.txt":
            body, ctype, code = b"User-agent: *\nDisallow: /private\n", "text/plain", 200
        elif self.path == "/private/data":
            body, ctype, code = b"secret", "text/plain", 200
        elif self.path == "/big":
            body, ctype, code = b"x" * 150_000, "text/plain", 200
        else:
            body, ctype, code = b"not found", "text/html", 404
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_probe_json(server):
    r = es.probe_url(f"{server}/json")
    assert r["status"] == 200 and "json" in r["content_type"] and r["body"] == b'{"ok": true}' and not r["truncated"]


def test_probe_truncates_big_responses(server):
    r = es.probe_url(f"{server}/big")
    assert r["truncated"] and r["bytes"] == es.MAX_BYTES


def test_probe_404_does_not_raise(server):
    r = es.probe_url(f"{server}/missing")
    assert r["status"] == 404 and r["error"] is None


def test_probe_connection_error_does_not_raise():
    r = es.probe_url("http://127.0.0.1:1/", timeout=2)
    assert r["error"] and r["status"] is None


def test_save_sample_and_name(tmp_path, server):
    r = es.probe_url(f"{server}/json")
    path = es.save_sample(r, tmp_path / "samples", 1)
    assert path.suffix == ".json" and path.read_bytes() == b'{"ok": true}'
    assert es.sample_name("https://www.example.es/a/b?x=1", "text/csv", 3).startswith("03_www_example_es_a_b")
    assert es.save_sample({"body": b""}, tmp_path, 1) is None


def test_probe_respects_robots_txt(server):
    es._ROBOTS.clear()
    blocked = es.probe_url(f"{server}/private/data")
    assert blocked["blocked"] and blocked["status"] is None and blocked["body"] == b""
    allowed = es.probe_url(f"{server}/json")
    assert not allowed["blocked"] and allowed["status"] == 200
