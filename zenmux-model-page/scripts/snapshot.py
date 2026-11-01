#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snapshot.py — fetch a page and record it as evidence (raw HTML + visible text + index entry)

Usage:
    python3 snapshot.py <url> --dir sources --role current
    python3 snapshot.py <url> --dir sources --role current-rendered --from-file rendered.txt
    python3 snapshot.py <url> --dir sources --role competitor|fact

Files:  <dir>/<host>__<path-slug>__<role>.html  (raw bytes, not written for --from-file)
        <dir>/<host>__<path-slug>__<role>.txt   (visible text: script/style/noscript dropped,
                                                 whitespace collapsed)
        <dir>/index.json  list of {url, role, html, txt, fetched_at, method, status, final_url}
        (html/txt are file names relative to <dir>). A trailing slash is significant: /a/b/ is
        saved as <path-slug>-slash. Re-snapshotting the same url+role replaces its entry. A failed fetch (HTTP/network error) exits 1 and records nothing.

Exit code: 0 = saved, 1 = failure.  Stdlib only.
"""

import argparse
try:
    import fcntl          # POSIX
except ImportError:       # Windows
    fcntl = None
    try:
        import msvcrt
    except ImportError:   # unknown platform: locking becomes a no-op (only matters for concurrent snapshots)
        msvcrt = None
import gzip
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ROLES = ("current", "current-rendered", "competitor", "fact", "data")
SKIP_TAGS = {"script", "style", "noscript"}
BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "header",
              "footer", "nav", "main", "aside", "h1", "h2", "h3", "h4", "h5", "h6", "pre",
              "blockquote", "form", "hr", "dd", "dt", "dl", "figure", "figcaption", "details",
              "summary", "title"}


def log(m): print(f"[snapshot] {m}", flush=True)


def fail(m):
    print(f"[snapshot] ERROR {m}", file=sys.stderr, flush=True)
    sys.exit(1)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def visible_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    p.close()
    lines = (re.sub(r"\s+", " ", ln).strip() for ln in "".join(p.parts).split("\n"))
    return "\n".join(ln for ln in lines if ln) + "\n"


def slug_for(url: str, role: str) -> str:
    u = urlsplit(url)
    host = re.sub(r"[^A-Za-z0-9.-]+", "-", u.netloc.lower()) or "unknown-host"
    path = re.sub(r"[^A-Za-z0-9._-]+", "-", u.path.strip("/")).strip("-") or "index"
    # /a/b and /a/b/ can serve different pages — keep them in different files
    if u.path.strip("/") and u.path.endswith("/"):
        path += "-slash"
    if u.query:
        path += "-q" + hashlib.md5(u.query.encode()).hexdigest()[:6]
    if len(path) > 100:
        path = path[:93] + "-" + hashlib.md5(path.encode()).hexdigest()[:6]
    return f"{host}__{path}__{role}"


def decode(raw: bytes, ctype: str) -> str:
    m = re.search(r"charset=([\w-]+)", ctype or "", re.I) or \
        re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", raw[:4096], re.I)
    enc = m.group(1) if m and isinstance(m.group(1), str) else (m.group(1).decode() if m else "utf-8")
    try:
        return raw.decode(enc, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def fetch(url: str):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
            return raw, r.headers.get("Content-Type", ""), r.status, r.geturl()
    except urllib.error.HTTPError as e:
        fail(f"HTTP {e.code} {e.reason} for {url}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        fail(f"could not fetch {url}: {getattr(e, 'reason', e)}")


def lock_file(f):
    """Exclusive lock held until the process exits (the handle is never closed explicitly)."""
    if fcntl is not None:
        fcntl.flock(f, fcntl.LOCK_EX)
    elif msvcrt is not None:
        while True:  # LK_LOCK gives up after ~10 s with OSError; keep waiting
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:
                continue
    # else: no locking available - parallel snapshot runs may race on index.json


def main():
    ap = argparse.ArgumentParser(description="Snapshot a page (raw HTML + visible text + index)")
    ap.add_argument("url")
    ap.add_argument("--dir", default="sources")
    ap.add_argument("--role", choices=ROLES, default="current")
    ap.add_argument("--from-file", help="don't fetch; use this text file as the .txt")
    args = ap.parse_args()

    if not re.match(r"^https?://", args.url):
        fail("url must start with http:// or https://")
    out = Path(args.dir)
    index_path = out / "index.json"
    out.mkdir(parents=True, exist_ok=True)
    # parallel runs (one agent per entity) share sources/: hold a lock across read-modify-write
    lock = open(out / ".index.lock", "w")
    lock_file(lock)
    index = []
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            assert isinstance(index, list)
        except Exception:
            fail(f"{index_path} is not a JSON list — fix or remove it first")

    stem = slug_for(args.url, args.role)
    if args.from_file:
        src = Path(args.from_file)
        if not src.is_file():
            fail(f"--from-file {src} not found")
        text = src.read_text(encoding="utf-8")
        html_name, status, final_url, method = None, None, args.url, "from-file"
        raw = None
    else:
        raw, ctype, status, final_url = fetch(args.url)
        text = visible_text(decode(raw, ctype))
        html_name, method = stem + ".html", "urllib"

    out.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        (out / html_name).write_bytes(raw)
    (out / (stem + ".txt")).write_text(text, encoding="utf-8")

    entry = {"url": args.url, "role": args.role, "html": html_name, "txt": stem + ".txt",
             "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "method": method, "status": status, "final_url": final_url}
    index = [e for e in index if not (e.get("url") == args.url and e.get("role") == args.role)]
    index.append(entry)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"saved {args.role}: {entry['txt']} ({len(text.split())} words, {method}, status={status})")


if __name__ == "__main__":
    main()
