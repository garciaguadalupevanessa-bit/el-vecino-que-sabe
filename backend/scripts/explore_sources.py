"""Probes data-source URLs (BDNS, FEGA, BOE, datos.gob.es...) and saves a small sample of each.

It helps fill docs/data_sources.md with facts (status, format, size) instead of assumptions.
It only uses the standard library, so it can run outside Docker with python3.

Usage:
    python3 backend/scripts/explore_sources.py URL [URL ...] [--output docs/samples]

Rules: at most 1 request per second, samples up to 100 KB, a User-Agent that identifies the project, and
robots.txt is respected: a URL that the site disallows for automated access is NOT fetched (look for an
official API or download instead, or browse it manually). Before using any source, read its legal notice
and reuse conditions.
"""
import argparse
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

USER_AGENT = "elvecinoquesabe-exploration/0.1 (educational project; contact: project team)"
MAX_BYTES = 100_000
MIN_WAIT = 1.0  # seconds between requests


_ROBOTS: dict[str, urllib.robotparser.RobotFileParser] = {}


def allowed_by_robots(url: str) -> bool:
    """True if the site's robots.txt lets our user agent fetch the URL. Unreachable robots.txt means allowed."""
    p = urlparse(url)
    root = f"{p.scheme}://{p.netloc}"
    if root not in _ROBOTS:
        parser = urllib.robotparser.RobotFileParser(f"{root}/robots.txt")
        try:
            parser.read()
        except Exception:  # noqa: BLE001 - if robots.txt cannot be read, behave like "no rules"
            parser.parse([])
        _ROBOTS[root] = parser
    return _ROBOTS[root].can_fetch(USER_AGENT, url)


def probe_url(url: str, timeout: float = 20, max_bytes: int = MAX_BYTES) -> dict:
    """Does a GET and returns a summary. Never raises on network or HTTP errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/*;q=0.8, */*;q=0.5"})
    summary = {"url": url, "status": None, "content_type": "", "bytes": 0, "truncated": False, "error": None, "body": b"",
               "blocked": False}
    if not allowed_by_robots(url):
        summary["blocked"] = True
        summary["error"] = "blocked by robots.txt (not fetched)"
        return summary
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            summary["status"] = resp.status
            summary["content_type"] = resp.headers.get("Content-Type", "")
            body = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        summary["status"] = e.code
        summary["content_type"] = e.headers.get("Content-Type", "") if e.headers else ""
        body = e.read(max_bytes + 1)
    except Exception as e:  # noqa: BLE001 - the reason is reported
        summary["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        return summary
    summary["truncated"] = len(body) > max_bytes
    summary["body"] = body[:max_bytes]
    summary["bytes"] = len(summary["body"])
    return summary


def extension(content_type: str) -> str:
    ct = content_type.lower()
    for key, ext in (("json", ".json"), ("xml", ".xml"), ("csv", ".csv"), ("html", ".html"), ("text/plain", ".txt")):
        if key in ct:
            return ext
    return ".bin"


def sample_name(url: str, content_type: str, n: int) -> str:
    p = urlparse(url)
    base = re.sub(r"[^a-zA-Z0-9]+", "_", f"{p.netloc}{p.path}").strip("_")[:60] or "sample"
    return f"{n:02d}_{base}{extension(content_type)}"


def save_sample(summary: dict, folder: Path, n: int) -> Path | None:
    if not summary["body"]:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / sample_name(summary["url"], summary["content_type"], n)
    path.write_bytes(summary["body"])
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--output", default="docs/samples", help="folder where samples are saved")
    ap.add_argument("--wait", type=float, default=MIN_WAIT, help="seconds between requests (minimum 1)")
    args = ap.parse_args(argv)
    wait = max(MIN_WAIT, args.wait)

    print("| URL | Status | Type | Bytes | Sample |\n|---|---|---|---|---|")
    had_error = False
    for n, url in enumerate(args.urls, start=1):
        if n > 1:
            time.sleep(wait)
        r = probe_url(url)
        if r["blocked"]:
            print(f"| {url} | SKIPPED: {r['error']} | | | |")
            continue
        if r["error"]:
            had_error = True
            print(f"| {url} | ERROR: {r['error']} | | | |")
            continue
        path = save_sample(r, Path(args.output), n)
        mark = " (truncated)" if r["truncated"] else ""
        print(f"| {url} | {r['status']} | {r['content_type'].split(';')[0]} | {r['bytes']}{mark} | {path or '-'} |")
        preview = r["body"][:300].decode("utf-8", errors="replace").replace("\n", " ")
        print(f"|   ↳ start: {preview!r} | | | | |")
    print("\nPaste the table into docs/data_sources.md and fill in format, filters, limits and legal notice by hand.")
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
