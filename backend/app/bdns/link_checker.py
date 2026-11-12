"""Conservative reachability checks for current official links in the BDNS catalog."""

from __future__ import annotations

import argparse
import ipaddress
import socket
import sys
import time
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit

import httpx

from app.core import config
from app.db import database as db


REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class OfficialLinkChecker:
    """Check HTTPS links without following unvalidated redirects or private IP targets."""

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        max_redirects: int = 3,
        minimum_request_interval: float = 1.0,
        http_client: httpx.Client | None = None,
        resolver: Callable[[str, int], list[str]] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if timeout_seconds <= 0 or max_redirects < 0 or minimum_request_interval < 0:
            raise ValueError("timeout_seconds must be positive; redirect count and request interval cannot be negative.")
        self.timeout_seconds = timeout_seconds
        self.max_redirects = max_redirects
        self.minimum_request_interval = minimum_request_interval
        self._http = http_client or httpx.Client(follow_redirects=False)
        self._owns_http_client = http_client is None
        self._resolver = resolver or self._resolve_public_addresses
        self._clock = clock
        self._sleep = sleeper
        self._last_request_at: float | None = None

    def close(self) -> None:
        if self._owns_http_client:
            self._http.close()

    def __enter__(self) -> OfficialLinkChecker:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _resolve_public_addresses(host: str, port: int) -> list[str]:
        return list({
            result[4][0]
            for result in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        })

    def _validate_target(self, url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("Only HTTPS links with a hostname can be checked.")
        if parsed.username or parsed.password:
            raise ValueError("Links containing credentials are not allowed.")
        port = parsed.port or 443
        if port != 443:
            raise ValueError("Only the standard HTTPS port is allowed.")
        try:
            addresses = [str(ipaddress.ip_address(parsed.hostname))]
        except ValueError:
            addresses = self._resolver(parsed.hostname, port)
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError("Link host did not resolve exclusively to public IP addresses.")

    def check(self, url: str) -> dict[str, Any]:
        current_url = url
        for redirect_count in range(self.max_redirects + 1):
            try:
                self._validate_target(current_url)
                response = self._request_head_or_range_get(current_url)
                status = response["status_code"]
                location = response.get("location")
                if status in REDIRECT_STATUSES:
                    if not location:
                        return {"status": "unknown", "status_code": status, "last_error": "Redirect response had no Location header."}
                    if redirect_count >= self.max_redirects:
                        return {"status": "unknown", "status_code": status, "last_error": "Redirect limit exceeded."}
                    current_url = urljoin(current_url, location)
                    continue
                if 200 <= status < 400:
                    return {"status": "reachable", "status_code": status, "last_error": None}
                if status in (404, 410):
                    return {"status": "broken", "status_code": status, "last_error": f"HTTP {status}"}
                if 400 <= status < 500:
                    return {
                        "status": "unknown", "status_code": status,
                        "last_error": f"HTTP {status}; the server did not confirm whether the resource is unavailable.",
                    }
                return {"status": "unknown", "status_code": status, "last_error": f"HTTP {status}"}
            except (httpx.RequestError, ValueError, OSError) as exc:
                return {"status": "unknown", "status_code": None, "last_error": str(exc)[:1000]}
        return {"status": "unknown", "status_code": None, "last_error": "Redirect limit exceeded."}

    def _request_head_or_range_get(self, url: str) -> dict[str, Any]:
        self._wait_for_request_slot()
        response = self._http.head(url, timeout=self.timeout_seconds)
        if response.status_code in (403, 405, 501):
            self._wait_for_request_slot()
            with self._http.stream(
                "GET", url, headers={"Range": "bytes=0-0"}, timeout=self.timeout_seconds
            ) as ranged:
                return {"status_code": ranged.status_code, "location": ranged.headers.get("Location")}
        return {"status_code": response.status_code, "location": response.headers.get("Location")}

    def _wait_for_request_slot(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            delay = self.minimum_request_interval - (now - self._last_request_at)
            if delay > 0:
                self._sleep(delay)
        self._last_request_at = self._clock()


def check_and_record_links(
    checker: OfficialLinkChecker,
    conn: Any,
    links: list[dict[str, str]],
    record_check: Callable[[Any, dict], None] = db.record_bdns_link_check,
) -> list[dict[str, Any]]:
    results = []
    for link in links:
        result = {**link, **checker.check(link["url"])}
        record_check(conn, result)
        results.append(result)
    conn.commit()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a bounded set of official BDNS source links.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--bdns-code", help="Check links for one imported call.")
    scope.add_argument("--all", action="store_true", help="Check current links across calls, bounded by --max-links.")
    parser.add_argument("--max-links", type=int, default=10)
    parser.add_argument("--url", default=config.DATABASE_URL)
    args = parser.parse_args(argv)
    try:
        if not args.url:
            raise ValueError("DATABASE_URL is missing.")
        if args.max_links < 1:
            raise ValueError("max-links must be positive.")
        if args.bdns_code is not None and not args.bdns_code.strip():
            raise ValueError("bdns-code cannot be empty.")
        with OfficialLinkChecker(
            minimum_request_interval=config.BDNS_LINK_CHECK_INTERVAL_SECONDS
        ) as checker, db.connect(args.url) as conn:
            db.create_schema(conn)
            links = db.read_bdns_links(
                conn, None if args.all else args.bdns_code.strip(), limit=args.max_links
            )
            results = check_and_record_links(checker, conn, links)
        counts = {status: sum(item["status"] == status for item in results)
                  for status in ("reachable", "broken", "unknown")}
        print(
            f"Checked {len(results)} links: {counts['reachable']} reachable, "
            f"{counts['broken']} broken, {counts['unknown']} unknown."
        )
        for item in results:
            print(f"{item['bdns_code']} {item['resource_type']}/{item['resource_key']}: {item['status']} {item['url']}")
        return 0 if counts["broken"] == 0 else 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"BDNS link check failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
