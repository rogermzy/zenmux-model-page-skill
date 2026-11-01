#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
site_fixes.py — turn every page's logged gaps into one list of site fix requests

Usage:
    python3 site_fixes.py <workspace> [--out site-fix-requests.md] [--site zenmux.ai] [--include-resolved]

Reads <workspace>/pages/*/facts.json gaps[] (schema: references/facts-ledger.md#gaps). Gaps with
owner "client" become fix requests to the client's site, grouped by the client page to fix and
sorted by priority; gaps that share a `key` across pages are merged into one request that lists
every affected page. Gaps with owner "external" go to a short FYI section (nothing to fix on the
client's site). Also writes the same data as <out>.json.

The request text is the writer's; this script only collects, merges and formats. It never sends
anything.

Exit code: 0 = written, 2 = usage / no pages found.  Stdlib only.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

KIND_LABEL = {
    "contradiction": "Contradiction on the site",
    "missing": "Not published on the site",
    "upstream_conflict": "Conflicts with the model developer's docs",
    "suspected_error": "Looks like an error",
    "not_in_html": "Only in JavaScript, not in the page HTML",
}
PRIO = {"high": 0, "medium": 1, "low": 2}


def log(m): print(f"[site_fixes] {m}", flush=True)


def collect(ws: Path, include_resolved: bool):
    merged, order = {}, []
    pages = sorted(ws.glob("pages/*/facts.json"))
    for fp in pages:
        slug = fp.parent.name
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except ValueError as e:
            log(f"skip {fp}: invalid JSON ({e})")
            continue
        for g in d.get("gaps") or []:
            if not isinstance(g, dict) or not g.get("id"):
                continue
            if g.get("status") == "resolved" and not include_resolved:
                continue
            k = g.get("key") or f"{slug}:{g['id']}"
            first = k not in merged
            if first:
                merged[k] = {**g, "key": k, "pages": [], "evidence": list(g.get("evidence") or []),
                             "searched": list(g.get("searched") or []), "client_urls": [], "parts": []}
                order.append(k)
            m = merged[k]
            m["pages"].append({"page": slug, "gap_id": g["id"], "entity": d.get("entity")})
            part = {"summary": g.get("summary"), "request": g.get("request"), "question": g.get("question"), "page": slug}
            if part not in m["parts"]:
                m["parts"].append(part)
            if g.get("client_url") and g["client_url"] not in m["client_urls"]:
                m["client_urls"].append(g["client_url"])
            if not first:
                for ev in g.get("evidence") or []:
                    if ev not in m["evidence"]:
                        m["evidence"].append(ev)
                for u in g.get("searched") or []:
                    if u not in m["searched"]:
                        m["searched"].append(u)
                if PRIO.get(g.get("priority"), 1) < PRIO.get(m.get("priority"), 1):
                    m["priority"] = g["priority"]
    return pages, [merged[k] for k in order]


def fmt_quote(ev):
    q = " ".join(str(ev.get("quote", "")).split())
    return f'> "{q}"  \n> — {ev.get("source_url")}'


def render(items, site, n_pages):
    client = [i for i in items if i.get("owner") == "client"]
    external = [i for i in items if i.get("owner") == "external"]
    client.sort(key=lambda i: (PRIO.get(i.get("priority"), 1), str(i.get("client_url")), str(i.get("summary"))))
    out = [f"# Site fix requests{' — ' + site if site else ''}", "",
           f"Generated {date.today().isoformat()} from {n_pages} page(s) in this workspace. "
           f"{len(client)} request(s) for the site, {len(external)} external gap(s) for information.", "",
           "Each request comes from a gap the page writer logged: something the site doesn't publish, says two "
           "different ways, or states differently from the model developer's docs. Until a request is resolved, "
           "the new page shows \"Not verified\" or \"Not published\" in the place listed under *Affects*.", ""]
    counts = {}
    for i in client:
        counts[i.get("kind")] = counts.get(i.get("kind"), 0) + 1
    if counts:
        out += ["| Kind | Requests |", "| :- | -: |"]
        out += [f"| {KIND_LABEL.get(k, k)} | {v} |" for k, v in sorted(counts.items(), key=lambda x: -x[1])]
        out.append("")
    out += ["## Requests for the site", ""]
    if not client:
        out += ["None.", ""]
    for n, i in enumerate(client, 1):
        i["request_no"] = f"R{n}"
        pp = {}
        for p in i.get("parts") or []:
            pp[p["page"]] = pp.get(p["page"], 0) + 1
        extra = len(i.get("parts") or []) - 1 if max(pp.values(), default=0) > 1 else 0
        out.append(f"### R{n}. {i.get('summary')}" + (f" (+{extra} related)" if extra else ""))
        out.append("")
        meta = [f"**Priority:** {i.get('priority') or 'medium'}", f"**Kind:** {KIND_LABEL.get(i.get('kind'), i.get('kind'))}",
                f"**Status:** {i.get('status') or 'open'}"]
        out.append(" · ".join(meta) + "  ")
        urls = i.get("client_urls") or [i.get("client_url")]
        label = "Page to fix" if len(urls) == 1 else "Pages to fix"
        out.append(f"**{label}:** {', '.join(map(str, urls))}" + (f" ({i['location']})" if i.get("location") else ""))
        out.append("")
        if i.get("evidence"):
            out.append("**What we found:**")
            out.append("")
            for ev in i["evidence"]:
                out += [fmt_quote(ev), ""]
        if i.get("searched"):
            out.append("**Checked and not found on:** " + ", ".join(i["searched"]))
            out.append("")
        parts = i.get("parts") or []
        # The same key on different pages = one issue described twice: keep the first wording.
        # Several gaps under one key on the SAME page = distinct issues grouped: list them all.
        per_page = {}
        for p in parts:
            per_page[p["page"]] = per_page.get(p["page"], 0) + 1
        if max(per_page.values(), default=0) > 1:
            # several distinct gaps share this key: keep every summary, change and question
            out += ["**Requested changes:**", ""]
            for p in parts:
                line = f"- **{p['summary']}**"
                if p.get("request"):
                    line += f" {p['request']}"
                if p.get("question"):
                    line += f" *Needs an answer first:* {p['question']}"
                out.append(line)
            out.append("")
        else:
            if i.get("request"):
                out += [f"**Requested change:** {i['request']}", ""]
            q = next((p["question"] for p in parts if p.get("question")), i.get("question"))
            if q:
                out += [f"**Needs an answer first:** {q}", ""]
        aff = ", ".join(f"{p['entity'] or p['page']} (`{p['page']}`, gap `{p['gap_id']}`)" for p in i["pages"])
        out += [f"**Affects:** {aff}", ""]
    if external:
        out += ["## External gaps (for information; nothing to fix on the site)", "",
                "Nobody we checked publishes these, so the pages say so instead of guessing.", ""]
        for i in external:
            aff = ", ".join(p["page"] for p in i["pages"])
            out.append(f"- **{i.get('summary')}** (pages: {aff})")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Collect logged gaps into one list of site fix requests (usage: site_fixes.py <workspace>)")
    ap.add_argument("workspace")
    ap.add_argument("--out", default="site-fix-requests.md", help="output path, relative to the workspace (default site-fix-requests.md)")
    ap.add_argument("--site", default="", help="site name for the heading, e.g. zenmux.ai")
    ap.add_argument("--include-resolved", action="store_true", help="also list gaps marked resolved")
    a = ap.parse_args()
    ws = Path(a.workspace)
    pages, items = collect(ws, a.include_resolved)
    if not pages:
        print(f"[site_fixes] ERROR no pages/*/facts.json under {ws}", file=sys.stderr)
        sys.exit(2)
    md = render(items, a.site, len(pages))
    out = Path(a.out) if Path(a.out).is_absolute() else ws / a.out
    out.write_text(md + "\n", encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    nc = sum(1 for i in items if i.get("owner") == "client")
    log(f"{nc} request(s), {len(items) - nc} external gap(s) from {len(pages)} page(s) -> {out}")


if __name__ == "__main__":
    main()
