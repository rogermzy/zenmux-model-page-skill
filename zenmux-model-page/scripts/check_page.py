#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_page.py — contract gate for a Mode B page.md against its approved plan + fact ledger

Usage:
    python3 check_page.py pages/<e>/page.md --plan plan.md
    python3 check_page.py pages/<e>/page.md --plan plan.md --facts pages/<e>/facts.json \
        [--sources sources/index.json] [--allow-draft-plan] [--no-lint] [--review review.json] \
        [--json page.check.json]

Enforces (references/page-format.md, facts-ledger.md, template-spec.md): front matter, title/H1
patterns, one marker per spec module in order, required/conditional/hidden rules, h2 patterns,
facts.json validity, gap logging (every Not verified / Not published / No data line carries a
<!-- gap: id --> marker that resolves to facts.json gaps[]), number provenance (every number token must be a fact's `display` or alias,
verbatim), fact source/quote traceability against snapshots (--sources; default
<plan dir>/sources/index.json), M1 price endpoint, status tables, derived_from, secrets, links, open placeholders.
The bundled Wendy linter (lint/lint.py) runs by default (--no-lint skips it; --lint is accepted as a no-op). It gets
a config built from the front matter (entities = entity + optional `entity_aliases`, central_entity, primary_keyword =
the H1, language), so the entity-aware rules (C1, F1, G1) run. Lint blockers are ERRORS `lint:<rule>`, warnings stay
warnings, info is dropped. Only prose is linted (no module markers, code blocks or link-only CTA lines); A4/E7 are
skipped for page copy.
--review merges an AI reviewer's findings (default: review.json next to page.md; schema in check_page.review_block):
missing -> WARN REVIEW_MISSING; invalid -> ERROR REVIEW_INVALID; page changed since the review -> ERROR REVIEW_STALE;
blocker -> ERROR review:<rule>; warning -> warning; a violation with a non-empty `waived_by` (a person's decision) is
only counted. The checker never waives anything itself.

Exit code: 0 = no ERROR, 1 = at least one ERROR, 2 = usage / file not found.  Stdlib only.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_plan import extract_spec, parse_front_matter, split_row, is_sep_row, tables  # noqa: E402

LINT_SCRIPT = Path(__file__).resolve().parent / "lint" / "lint.py"
PAGE_KEYS = ["template_id", "entity", "entity_type", "url", "title", "meta_description",
             "default_endpoint", "checked_date", "facts"]
FACT_KEYS = ["id", "category", "endpoint", "label", "display", "quote", "checked_at", "verdict"]
VERDICTS = {"UNCHECKED", "VERIFIED", "NUANCED", "REFUTED", "UNVERIFIABLE"}
ZERO_FORMS = {"$0", "$0.00", "100%"}
GAP_KINDS = {"missing", "contradiction", "upstream_conflict", "suspected_error", "not_in_html"}
GAP_OWNERS = {"client", "external"}
GAP_REF = re.compile(r"<!--\s*gap:\s*(.*?)\s*-->")
HIDDEN_GAP = re.compile(r"\bgap:\s*([A-Za-z0-9_.-]+(?:\s*,\s*[A-Za-z0-9_.-]+)*)")

MARKER = re.compile(r"^\s*<!--\s*module:\s*(\S+?)\s+(shown|hidden)\s*(?::\s*(.*?))?\s*-->\s*$")
TOKEN = re.compile(r"(?<![A-Za-z0-9_.])(\d{4}-\d{2}-\d{2}(?!\d)|\d{1,2}:\d{2}(?![\d:])|[$€¥£]?\d[\d,]*(?:\.\d+)?(?:\s?(?:%|[KMB]\b|k\b))?)")
LEAD = re.compile(r"^(?:\d{4}-\d{2}-\d{2}(?!\d)|\d{1,2}:\d{2}(?![\d:])|[$€¥£]?\d[\d,]*(?:\.\d+)?(?:\s?(?:%|[KMB]\b|k\b))?)")
DASHES = "-–—"
ZERO_RE = re.compile(r"(?<![\d.,])(?:\$0(?:\.00)?(?!\.?\d)|100%)")
SECRETS = [
    ("sk- style API key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}")),
    ("Bearer token", re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")),
    ("api_key literal", re.compile(r"api[_-]?key[\"'\s:=]+[A-Za-z0-9]{20,}", re.I)),
]


def log(m): print(f"[check_page] {m}", flush=True)


# ── text masking (all replacements keep length + newlines, so line numbers stay valid) ───────
def blank(text, rx, group=0, flags=0):
    def sub(m):
        s = m.group(group)
        return m.group(0).replace(s, re.sub(r"[^\n]", " ", s), 1) if group else re.sub(r"[^\n]", " ", s)
    return re.sub(rx, sub, text, flags=flags)


def tokenize(ln):
    """Numeric tokens of one (already masked) line → [(start, text)]. A hyphen/en/em dash right
    before a number is allowed only as a range separator, i.e. when the previous accepted token
    ends exactly at the dash ($1.11-$2.22, 1–3); gpt-4o / V4-0813 stay skipped."""
    out, prev_end = [], -1
    for m in TOKEN.finditer(ln):
        nxt = ln[m.end()] if m.end() < len(ln) else ""
        if nxt.isalpha() and nxt not in "KMBk":
            continue
        if m.start() > 0 and ln[m.start() - 1] in DASHES and prev_end != m.start() - 1:
            continue
        t = m.group(1).rstrip(",").strip()
        if t:
            out.append((m.start(), t))
            prev_end = m.start() + len(m.group(1).rstrip(","))
    return out


def pattern_re(pat: str, entity: str):
    out = []
    for part in re.split(r"(\{[^{}]*\})", pat):
        if part == "{Entity}":
            out.append(re.escape(entity))
        elif part.startswith("{") and part.endswith("}"):
            out.append(".+")
        else:
            out.append(re.escape(part))
    return re.compile("".join(out))


# ── facts ───────────────────────────────────────────────────────────────────────────────────
def validate_facts(facts, E):
    """facts-ledger.md rules. Returns True when the ledger is structurally usable."""
    if not isinstance(facts, dict):
        E("FACTS_INVALID", "facts.json top level must be an object")
        return False
    ok = True
    for k, t in (("entity", str), ("names", list), ("endpoints", list), ("facts", list)):
        if not isinstance(facts.get(k), t):
            E("FACTS_MISSING_KEY", f"facts.json: '{k}' missing or not a {t.__name__}")
            ok = False
    if not ok:
        return False
    eids = set()
    for i, ep in enumerate(facts["endpoints"]):
        if not isinstance(ep, dict) or not ep.get("id"):
            E("FACTS_MISSING_KEY", f"endpoints[{i}] needs an id")
            continue
        eids.add(ep["id"])
        if ep.get("status") not in ("active", "disabled"):
            E("ENDPOINT_BAD_STATUS", f"endpoint '{ep['id']}' status {ep.get('status')!r} must be active|disabled")
    seen = set()
    for i, f in enumerate(facts["facts"]):
        if not isinstance(f, dict):
            E("FACT_MISSING_KEY", f"facts[{i}] is not an object")
            continue
        fid = f.get("id", f"facts[{i}]")
        for k in FACT_KEYS:
            if k not in f:
                E("FACT_MISSING_KEY", f"fact '{fid}' lacks key '{k}'")
        if not f.get("source_url"):
            E("FACT_NO_SOURCE", f"fact '{fid}' has no source_url")
        if "display" in f and not isinstance(f["display"], str):
            E("FACT_BAD_TYPE", f"fact '{fid}' display must be a string")
        if "id" in f:
            if f["id"] in seen:
                E("FACT_DUP_ID", f"duplicate fact id '{f['id']}'")
            seen.add(f["id"])
        if "verdict" in f and f["verdict"] not in VERDICTS:
            E("FACT_BAD_VERDICT", f"fact '{fid}' verdict {f['verdict']!r} not in {sorted(VERDICTS)}")
        if f.get("endpoint") is not None and "endpoint" in f and f["endpoint"] not in eids:
            E("FACT_BAD_ENDPOINT", f"fact '{fid}' references unknown endpoint '{f['endpoint']}'")
    return True


# ── main check ──────────────────────────────────────────────────────────────────────────────
def validate_gaps(gaps, E):
    """facts.json gaps[]: one entry per thing the writer could not find or found contradicted.
    Returns the set of valid ids. Schema: references/facts-ledger.md#gaps."""
    ids = set()
    if not isinstance(gaps, list):
        E("GAP_INVALID", "facts.json 'gaps' must be a list")
        return ids
    for k, g in enumerate(gaps):
        if not isinstance(g, dict) or not g.get("id"):
            E("GAP_INVALID", f"gaps[{k}] needs an 'id'")
            continue
        gid = str(g["id"])
        if gid in ids:
            E("GAP_INVALID", f"duplicate gap id '{gid}'")
        ids.add(gid)
        for key in ("kind", "owner", "summary"):
            if not g.get(key):
                E("GAP_INVALID", f"gap '{gid}': '{key}' missing")
        kind, owner = g.get("kind"), g.get("owner")
        if kind and kind not in GAP_KINDS:
            E("GAP_INVALID", f"gap '{gid}': kind '{kind}' not in {sorted(GAP_KINDS)}")
        if owner and owner not in GAP_OWNERS:
            E("GAP_INVALID", f"gap '{gid}': owner '{owner}' not in {sorted(GAP_OWNERS)}")
        ev, se = g.get("evidence") or [], g.get("searched") or []
        if not isinstance(ev, list) or not isinstance(se, list):
            E("GAP_INVALID", f"gap '{gid}': 'evidence' and 'searched' must be lists")
            continue
        if any(not isinstance(e, dict) or not e.get("source_url") or not e.get("quote") for e in ev):
            E("GAP_INVALID", f"gap '{gid}': each evidence item needs source_url + quote")
        if kind in ("missing", "not_in_html") and not se:
            E("GAP_INVALID", f"gap '{gid}' ({kind}): list the snapshotted URLs you searched in 'searched'")
        if kind in ("contradiction", "upstream_conflict") and len(ev) < 2:
            E("GAP_INVALID", f"gap '{gid}' ({kind}): quote both sides — at least 2 evidence items")
        if kind == "suspected_error" and not ev:
            E("GAP_INVALID", f"gap '{gid}' (suspected_error): quote the suspect value in 'evidence'")
        if owner == "client":
            if not g.get("client_url"):
                E("GAP_INVALID", f"gap '{gid}': owner client needs 'client_url' (the page to fix)")
            if not (g.get("request") or g.get("question")):
                E("GAP_INVALID", f"gap '{gid}': owner client needs 'request' (the change we ask for) and/or 'question'")
        if g.get("priority") and g["priority"] not in ("high", "medium", "low"):
            E("GAP_INVALID", f"gap '{gid}': priority must be high | medium | low")
        if g.get("status") and g["status"] not in ("open", "sent", "resolved"):
            E("GAP_INVALID", f"gap '{gid}': status must be open | sent | resolved")
    return ids


def check(page_path: Path, plan_path: Path, facts_arg, allow_draft, do_lint, sources_arg=None, review_arg=None):
    errors, warnings = [], []

    def E(code, msg, line=None):
        errors.append({"code": code, "msg": msg, **({"line": line} if line else {})})

    def W(code, msg, line=None):
        warnings.append({"code": code, "msg": msg, **({"line": line} if line else {})})

    rep = {"file": str(page_path), "entity": None, "errors": errors, "warnings": warnings,
           "modules": {}, "numbers_checked": 0}

    # plan + spec
    plan_text = plan_path.read_text(encoding="utf-8")
    pfm, _ = parse_front_matter(plan_text)
    pfm = pfm or {}
    spec, err = extract_spec(plan_text)
    if err:
        E("PLAN_SPEC_INVALID", f"plan has no usable page-template spec ({err})")
        return rep
    if pfm.get("status") != "approved":
        if allow_draft:
            msg = (f"PLAN STATUS IS '{pfm.get('status')}', NOT approved — checking against a DRAFT plan "
                   "(--allow-draft-plan). Do not ship pages from this run.")
            W("WARN_DRAFT_PLAN", msg)
            print("\n" + "!" * 78 + f"\n!! {msg}\n" + "!" * 78 + "\n", file=sys.stderr, flush=True)
        else:
            E("PLAN_NOT_APPROVED", f"plan status is '{pfm.get('status')}', not approved — "
              "Mode B refuses a draft plan (use --allow-draft-plan for a dry run)")
            return rep
    smods = [m for m in spec.get("modules", []) if isinstance(m, dict) and m.get("id")]
    sids = [m["id"] for m in smods]
    sby = {m["id"]: m for m in smods}

    # page front matter
    text = page_path.read_text(encoding="utf-8")
    fm, body_start = parse_front_matter(text)
    if fm is None:
        E("PAGE_NO_FRONT_MATTER", "page.md must open with a closed --- front matter block")
        return rep
    for k in PAGE_KEYS:
        if not fm.get(k):
            E("PAGE_MISSING_KEY", f"front matter key '{k}' missing or empty")
    entity = fm.get("entity", "")
    rep["entity"] = entity or None
    aliases = parse_aliases(fm.get("entity_aliases", ""))
    for a in aliases:
        if len(a) < 3:
            E("FRONT_MATTER_INVALID", f"entity_aliases: {a!r} is shorter than 3 characters (it would match almost anything)")
    aliases = [a for a in aliases if len(a) >= 3]
    if fm.get("template_id") and fm["template_id"] != spec.get("template_id"):
        E("PAGE_TEMPLATE_MISMATCH", f"template_id '{fm['template_id']}' != spec '{spec.get('template_id')}'")
    variants = spec.get("entity_variants")
    if fm.get("entity_type") and isinstance(variants, dict) and fm["entity_type"] not in variants:
        E("PAGE_BAD_ENTITY_TYPE", f"entity_type '{fm['entity_type']}' not in spec entity_variants {sorted(variants)}")
    if entity and fm.get("title") and isinstance(spec.get("title_pattern"), str):
        if not pattern_re(spec["title_pattern"], entity).fullmatch(fm["title"].strip()):
            E("TITLE_PATTERN", f"title {fm['title']!r} does not match title_pattern {spec['title_pattern']!r}")

    # facts
    facts_path = Path(facts_arg) if facts_arg else (page_path.parent / fm["facts"] if fm.get("facts") else None)
    facts, facts_ok = None, False
    if not facts_path or not facts_path.is_file():
        E("FACTS_MISSING", f"facts file not found ({facts_path})")
    else:
        try:
            facts = json.loads(facts_path.read_text(encoding="utf-8"))
            facts_ok = validate_facts(facts, E)
        except ValueError as e:
            E("FACTS_INVALID", f"{facts_path} is not valid JSON: {e}")
    flist = facts["facts"] if facts_ok else []
    ep_ids = {e["id"] for e in facts["endpoints"] if isinstance(e, dict) and e.get("id")} if facts_ok else set()

    de = fm.get("default_endpoint", "")
    de_known = False
    if facts_ok and de:
        if de == "auto" or de in ep_ids:
            de_known = de != "auto"
        else:
            E("DEFAULT_ENDPOINT_UNKNOWN", f"default_endpoint '{de}' is not in facts.endpoints (and not 'auto')")

    # gaps ledger (what the writer could not find, or found contradicted)
    gap_ids = set()
    pseudo = []
    if facts_ok:
        gaps = facts.get("gaps", [])
        gap_ids = validate_gaps(gaps, E)
        for g in gaps if isinstance(gaps, list) else []:
            if not isinstance(g, dict) or not g.get("id"):
                continue
            for ev in g.get("evidence") or []:
                if isinstance(ev, dict):
                    pseudo.append({"id": f"gap:{g['id']}", "source_url": ev.get("source_url"), "quote": ev.get("quote")})
            for u in g.get("searched") or []:
                pseudo.append({"id": f"gap:{g['id']}", "source_url": u, "_no_quote": True})

    # source / quote traceability against snapshots (facts + gap evidence)
    if facts_ok:
        check_sources(flist + pseudo, sources_arg, plan_path, E, W)

    # structure: fences, markers, module of each line
    lines = text.split("\n")
    n = len(lines)
    fence_flag, fence = [False] * n, None
    for i in range(body_start, n):
        m = re.match(r"^\s{0,3}(`{3,}|~{3,})", lines[i])
        if fence is None:
            if m:
                fence, fence_flag[i] = (m.group(1)[0], len(m.group(1))), True
        else:
            fence_flag[i] = True
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and lines[i].strip() == m.group(1):
                fence = None
    markers = []  # (idx, id, state, reason)
    for i in range(body_start, n):
        if fence_flag[i]:
            continue
        if "<!--" in lines[i] and re.search(r"<!--\s*module:", lines[i]):
            m = MARKER.match(lines[i])
            if not m:
                E("MARKER_MALFORMED", f"unparseable module marker: {lines[i].strip()[:80]!r}", i + 1)
            else:
                markers.append((i, m.group(1), m.group(2), (m.group(3) or "").strip()))
    mod_of = [None] * n
    for k, (idx, mid, _s, _r) in enumerate(markers):
        end = markers[k + 1][0] if k + 1 < len(markers) else n
        for j in range(idx + 1, end):
            mod_of[j] = mid
    first_marker = markers[0][0] if markers else n
    pre = [j for j in range(body_start, first_marker) if lines[j].strip()]
    if pre:
        E("CONTENT_BEFORE_MARKER", "content before the first module marker", pre[0] + 1)

    state, seen_ids = {}, []
    for idx, mid, st, reason in markers:
        if mid not in sby:
            E("MARKER_UNKNOWN_MODULE", f"marker for '{mid}', which is not in the spec", idx + 1)
            continue
        if mid in state:
            E("MARKER_DUPLICATE", f"duplicate marker for {mid}", idx + 1)
            continue
        state[mid] = (st, reason, idx)
        seen_ids.append(mid)
    for mid in sids:
        if mid not in state:
            E("MARKER_MISSING", f"no marker for spec module {mid}")
    pos = [sids.index(m) for m in seen_ids]
    if pos != sorted(pos):
        E("MODULE_ORDER", f"module markers out of spec order: found {' '.join(seen_ids)}; expected {' '.join(m for m in sids if m in state)}")
    rep["modules"] = {m: state[m][0] for m in sids if m in state}

    # gap markers: every line showing a missing-value label must name the gap(s) behind it
    labels = sorted({v for v in (spec.get("missing_value_labels") or {}).values() if isinstance(v, str) and v}
                    | {"Not verified"}, key=len, reverse=True)
    referenced = set()

    def ref_gap(gid, line):
        referenced.add(gid)
        if facts_ok and gid not in gap_ids:
            E("GAP_UNKNOWN", f"gap marker '{gid}' is not an id in facts.json gaps[]", line)

    unlogged = 0
    for i in range(body_start, n):
        if fence_flag[i]:
            continue
        mk = MARKER.match(lines[i])
        if mk:
            if mk.group(2) == "hidden" and mk.group(1) in sby and sby[mk.group(1)].get("required") is not True:
                hg = HIDDEN_GAP.search(mk.group(3) or "")
                if hg:
                    for gid in (x.strip() for x in hg.group(1).split(",")):
                        ref_gap(gid, i + 1)
                else:
                    W("WARN_HIDDEN_NO_GAP", f"{mk.group(1)} is hidden; add 'gap: <id>' to the reason so the missing data reaches the fix list", i + 1)
            continue
        refs = [x.strip() for m in GAP_REF.finditer(lines[i]) for x in m.group(1).split(",") if x.strip()]
        for gid in refs:
            ref_gap(gid, i + 1)
        visible = re.sub(r"<!--.*?-->", "", lines[i])
        hit = next((lb for lb in labels if lb in visible), None)
        if hit and not refs:
            unlogged += 1
            E("UNLOGGED_GAP", f"{hit!r} with no <!-- gap: id --> marker on this line; log why in facts.json gaps[]", i + 1)
    for gid in sorted(gap_ids - referenced):
        W("WARN_GAP_UNUSED", f"gap '{gid}' is in facts.json but no page line or hidden marker refers to it")
    rep["gaps"] = {"logged": len(gap_ids), "referenced": len(referenced & gap_ids), "unlogged_lines": unlogged}

    for mid, (st, reason, idx) in state.items():
        spm = sby[mid]
        if st == "hidden":
            if spm.get("required") is True:
                E("REQUIRED_HIDDEN", f"{mid} is required but marked hidden", idx + 1)
            if not reason:
                E("HIDDEN_NO_REASON", f"{mid} hidden marker needs a non-empty reason", idx + 1)
            body = [j for j in range(body_start, n) if mod_of[j] == mid and lines[j].strip()]
            if body:
                E("HIDDEN_HAS_CONTENT", f"{mid} is hidden but has content (first at line {body[0] + 1})", body[0] + 1)
        else:
            si = spm.get("show_if")
            if isinstance(si, str) and facts_ok:
                kind, _, arg = si.partition(":")
                if kind == "category":
                    cnt = sum(1 for f in flist if isinstance(f, dict) and f.get("category") == arg)
                elif kind == "facts":
                    cnt = sum(1 for f in flist if isinstance(f, dict) and str(f.get("id", "")).startswith(arg))
                else:
                    cnt = None
                    if not reason:
                        W("WARN_MANUAL_NO_REASON", f"{mid} is shown under show_if '{si}'; template-spec says the marker should state the reason", idx + 1)
                if cnt == 0:
                    E("COND_SHOWN_NO_FACTS", f"{mid} show_if '{si}' matches no facts but the module is shown", idx + 1)
            h2 = spm.get("h2")
            if isinstance(h2, str) and entity:
                head = next((j for j in range(idx + 1, n) if mod_of[j] == mid and not fence_flag[j]
                             and re.match(r"^#{1,6}\s", lines[j])), None)
                if head is None:
                    E("H2_MISSING", f"{mid} has no heading; expected '## ' matching {h2!r}", idx + 1)
                else:
                    mm = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", lines[head])
                    if len(mm.group(1)) != 2 or not pattern_re(h2, entity).fullmatch(mm.group(2)):
                        E("H2_PATTERN", f"{mid} first heading {lines[head].strip()!r} must be '## ' matching {h2!r}", head + 1)

    # H1
    h1s = [j for j in range(body_start, n) if not fence_flag[j] and re.match(r"^# +\S", lines[j])]
    if len(h1s) != 1:
        E("H1_COUNT", f"expected exactly one '# ' H1, found {len(h1s)}", h1s[1] + 1 if len(h1s) > 1 else None)
    if h1s:
        j = h1s[0]
        if mod_of[j] != "M1":
            E("H1_NOT_IN_M1", f"H1 sits in {mod_of[j] or 'no module'}, not M1", j + 1)
        txt = re.sub(r"\s*#*\s*$", "", lines[j][1:].strip())
        if entity and isinstance(spec.get("h1_pattern"), str) and not pattern_re(spec["h1_pattern"], entity).fullmatch(txt):
            E("H1_PATTERN", f"H1 {txt!r} does not match h1_pattern {spec['h1_pattern']!r}", j + 1)

    # status tables
    vocab = spec.get("status_vocabulary") or []
    for mid, (st, reason, idx) in state.items():
        if st != "shown" or sby[mid].get("status_table") is not True:
            continue
        seg = [lines[j] for j in range(idx + 1, n) if mod_of[j] == mid and not fence_flag[j]]
        tbs = tables(seg)
        if not tbs:
            E("STATUS_TABLE_MISSING", f"{mid} has status_table but no markdown table", idx + 1)
            continue
        for r in tbs[0]["rows"]:
            cell = r[1].lstrip("*_` ") if len(r) > 1 else ""
            if not any(cell.startswith(v) for v in vocab):
                E("STATUS_TABLE_VALUE", f"{mid} status table row {r[0]!r}: column 2 {cell[:30]!r} does not start with one of {vocab}", idx + 1 + tbs[0]["start"] + 2)

    # secrets (whole file, code blocks included)
    for label, rx in SECRETS:
        for m in rx.finditer(text):
            E("SECRET", f"possible {label} ({m.group(0)[:6]}…) at line {text.count(chr(10), 0, m.start()) + 1}; use an env var",
              text.count("\n", 0, m.start()) + 1)

    # masked views
    stage = [("" if (i < body_start or fence_flag[i]) else lines[i]) for i in range(n)]
    nocode = "\n".join(stage)
    nocode = blank(nocode, r"<!--.*?-->", flags=re.S)
    nocode = blank(nocode, r"`[^`\n]+`")
    # links
    for m in re.finditer(r"\[([^\]\n]*)\]\(([^)\n]*)\)", nocode):
        anchor, url = m.group(1).strip(), m.group(2).strip()
        ln = nocode.count("\n", 0, m.start()) + 1
        if url in ("", "#") or url.startswith("# "):
            W("WARN_LINK_PLACEHOLDER", f"link [{anchor}]({url}) has no real target", ln)
        if anchor.lower() in ("click here", "here", "点击这里"):
            W("WARN_LINK_ANCHOR", f"link anchor {anchor!r} is not descriptive", ln)
    ph = {}
    for m in re.finditer(r"\[(N|CITE)\](?!\()", nocode):
        ph.setdefault(m.group(1), []).append(nocode.count("\n", 0, m.start()) + 1)
    if ph:
        W("WARN_OPEN_PLACEHOLDERS", "open placeholders: " + "; ".join(
            f"[{k}] x{len(v)} (lines {', '.join(map(str, v[:8]))})" for k, v in ph.items()))

    masked = nocode
    masked = blank(masked, r"\]\(((?:[^()\n]|\([^()\n]*\))*)\)", group=1)
    masked = blank(masked, r"<https?://[^>\n]+>")
    masked = blank(masked, r"https?://[^\s)>\]]+")
    masked = blank(masked, r"^(\s*)(\d+)([.)]\s)", group=2, flags=re.M)
    masked = blank(masked, r"\[(?:N|CITE)\]")
    names = sorted({s for s in (facts["names"] if facts_ok else []) if isinstance(s, str) and s}, key=len, reverse=True)
    if names:
        masked = blank(masked, "|".join(re.escape(s) for s in names))
    mlines = masked.split("\n")

    # $0 / 100%
    by_display, nonref_display = {}, set()
    for f in flist:
        if isinstance(f, dict) and isinstance(f.get("display"), str):
            keys = [f["display"].strip()] + [a.strip() for a in f.get("aliases", []) if isinstance(a, str)]
            for k0 in list(keys):   # unit-bearing display ("12 ms", "$0.55 / 1M tokens") also accepts its leading number
                lm = LEAD.match(k0)
                if lm and lm.group(0).rstrip(",") != k0:
                    keys.append(lm.group(0).rstrip(","))
            for k in keys:
                by_display.setdefault(k, []).append(f)
                if f.get("verdict") != "REFUTED":
                    nonref_display.add(k)
    for i, ln in enumerate(mlines):
        for m in ZERO_RE.finditer(ln):
            if m.group(0) not in nonref_display:
                E("ZERO_OR_FULL", f"{m.group(0)!r} on the page without a (non-REFUTED) fact — never fill $0 / 100%", i + 1)

    # tokens
    tokens = []  # (line_idx, text, module)
    for i, ln in enumerate(mlines):
        if i < body_start:
            continue
        for _pos, t in tokenize(ln):
            tokens.append((i, t, mod_of[i]))
    # front-matter title / meta_description are page text too
    for key in ("title", "meta_description"):
        li = next((j for j in range(1, body_start) if re.match(rf"^{key}\s*:", lines[j])), 0)
        val = fm.get(key, "")
        if names:
            val = blank(val, "|".join(re.escape(s) for s in names))
        for m in ZERO_RE.finditer(val):
            if m.group(0) not in nonref_display:
                E("ZERO_OR_FULL", f"{m.group(0)!r} in front matter {key} without a (non-REFUTED) fact", li + 1)
        for _pos, t in tokenize(val):
            tokens.append((li, t, None))
    allowed = {fm.get("checked_date", "").strip()} - {""}
    used = {}
    checked = 0
    for i, t, mid in tokens:
        if t in ZERO_FORMS:
            continue
        checked += 1
        ms = by_display.get(t)
        if ms:
            for f in ms:
                used[f.get("id")] = f
            if all(f.get("verdict") == "REFUTED" for f in ms):
                E("REFUTED_FACT_USED", f"{t!r} is the display of REFUTED fact(s) only: {', '.join(str(f.get('id')) for f in ms)}", i + 1)
        elif t not in allowed:
            if facts_ok:
                E("UNTRACED_NUMBER", f"untraced number {t!r} — not any fact's display/alias", i + 1)
            else:
                E("UNTRACED_NUMBER", f"untraced number {t!r} (no usable facts.json)", i + 1)
    rep["numbers_checked"] = checked

    # non-numeric displays count as used when they occur on the page
    body_masked = "\n".join(mlines)
    for k, fs in by_display.items():
        if not re.search(r"\d", k) and k and k in body_masked:
            for f in fs:
                used.setdefault(f.get("id"), f)
    unchecked = sorted(str(i) for i, f in used.items() if f.get("verdict") == "UNCHECKED")
    if unchecked:
        W("WARN_UNCHECKED_FACTS", f"{len(unchecked)} fact(s) used on the page are not fact-checked yet: {', '.join(unchecked[:6])}{' …' if len(unchecked) > 6 else ''}")

    # M1 price / endpoint
    m1_tokens = [(i, t) for i, t, mid in tokens if mid == "M1"]
    if state.get("M1", ("",))[0] == "shown":
        if de_known:
            for i, t in m1_tokens:
                if t.startswith("$") and t not in ZERO_FORMS:
                    if not any(f.get("endpoint") == de for f in by_display.get(t, [])):
                        E("M1_PRICE_ENDPOINT", f"M1 price {t!r} is not a fact of default_endpoint '{de}'", i + 1)
        elif de == "auto":
            m1txt = "\n".join(lines[j] for j in range(n) if mod_of[j] == "M1" and not fence_flag[j])
            if not re.search(r"vary|varies", m1txt, re.I):
                W("WARN_M1_AUTO_NO_VARY", "default_endpoint is auto: M1 should say version/price vary by the endpoint hit")

    # derived_from
    toks_by_mod = {}
    for i, t, mid in tokens:
        toks_by_mod.setdefault(mid, []).append((i, t))
    for mid, (st, _r, _i) in state.items():
        df = sby[mid].get("derived_from")
        if st != "shown" or not isinstance(df, list):
            continue
        pool = {t for d in df for _, t in toks_by_mod.get(d, [])}
        done = set()
        for i, t in toks_by_mod.get(mid, []):
            if t not in pool and t not in done and t not in ZERO_FORMS:
                done.add(t)
                E("DERIVED_FROM_VIOLATION", f"{mid} number {t!r} does not appear in {'/'.join(df)}", i + 1)

    body = "\n".join(lines[body_start:])
    if do_lint:
        cfg = lint_config(body, entity, aliases, fm.get("language") or spec.get("page_language") or "en")
        run_lint(body, cfg["language"], W, E, cfg)
    review_block(page_path, text, review_arg, rep, E, W)
    return rep


def _norm(u):
    # Fragment dropped, scheme/host case-folded. A trailing slash is significant (/a/b and /a/b/
    # can be different pages); only the bare-host root "https://x.com/" equals "https://x.com".
    u = str(u).strip().split("#")[0]
    m = re.match(r"^([A-Za-z][\w+.-]*://[^/?]+)(.*)$", u)
    if not m:
        return u
    base, rest = m.group(1).lower(), m.group(2)
    return base + ("" if rest == "/" else rest)


def check_sources(flist, sources_arg, plan_path, E, W):
    idx_path = Path(sources_arg) if sources_arg else plan_path.parent / "sources" / "index.json"
    index = None
    if idx_path.is_file():
        try:
            index = json.loads(idx_path.read_text(encoding="utf-8"))
            assert isinstance(index, list)
        except Exception as e:
            W("SOURCES_UNCHECKED", f"could not read {idx_path} ({str(e)[:60]}): fact sources/quotes not verified")
            return
    if index is None:
        W("SOURCES_UNCHECKED", f"no snapshot index ({idx_path}): fact source_url/quote not verified against snapshots")
        return
    by_url = {}
    for e in index:
        for k in ("url", "final_url"):
            if isinstance(e, dict) and e.get(k):
                by_url.setdefault(_norm(e[k]), []).append(e)
    cache = {}

    def text_of(e):
        if not e.get("txt"):
            return ""
        p = idx_path.parent / e["txt"]
        if p not in cache:
            try:
                cache[p] = re.sub(r"\s+", " ", p.read_text(encoding="utf-8")).strip()
            except OSError:
                cache[p] = ""
        return cache[p]

    for f in flist:
        if not isinstance(f, dict) or f.get("verdict") == "UNVERIFIABLE" or not f.get("source_url"):
            continue
        fid, ents = f.get("id"), by_url.get(_norm(f["source_url"]))
        if not ents:
            E("SOURCE_NOT_SNAPSHOTTED", f"fact '{fid}': source_url {f['source_url']} has no snapshot in {idx_path.name}")
            continue
        if f.get("_no_quote"):
            continue
        q = re.sub(r"\s+", " ", str(f.get("quote") or "")).strip()
        if not q or not any(q in text_of(e) for e in ents):
            E("QUOTE_NOT_FOUND", f"fact '{fid}': quote {q[:50]!r} not found in the snapshot text of {f['source_url']}")


# Article rules that don't fit page copy: A4 wants a count sentence above every list (page lists
# are nav/fit lists), E7 wants inline [CITE] markers (numbers are traced through facts.json here).
LINT_SKIP_RULES = {"A4", "E7"}
_CTA_ROW = re.compile(r"^\s*(\[[^\]]+\]\([^)]+\)\s*[·|•,]?\s*)+$")


def lint_prose(body):
    """Keep only prose for lint: drop HTML comments (module markers), fenced code and CTA/link-only lines."""
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"^\s*(```|~~~).*?^\s*\1[^\n]*$", "", body, flags=re.S | re.M)
    return "\n".join(l for l in body.split("\n") if not _CTA_ROW.match(l))


def parse_aliases(raw):
    """`entity_aliases` front matter value → list of names. Accepts `[V4 Pro, DeepSeek-V4-Pro]` or `V4 Pro, DeepSeek-V4-Pro`
    (the shared front-matter parser keeps the value as one string)."""
    raw = str(raw or "").strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    out = []
    for a in raw.split(","):
        a = a.strip()
        if len(a) >= 2 and a[0] == a[-1] and a[0] in "\"'":
            a = a[1:-1].strip()
        if a and a not in out:
            out.append(a)
    return out


def page_h1(body):
    """Text of the first `# ` heading outside fenced code ('' if none)."""
    fence = False
    for l in body.split("\n"):
        if re.match(r"^\s*(```|~~~)", l):
            fence = not fence
        elif not fence:
            m = re.match(r"^#\s+(.+?)\s*#*\s*$", l)
            if m:
                return m.group(1).strip()
    return ""


def lint_config(body, entity, aliases, lang):
    ents = [e for e in [entity] + list(aliases) if e]
    return {"language": lang, "entities": ents,
            "term_lists": {"central_entity": entity or "", "primary_keyword": page_h1(body) or entity or ""}}


def run_lint(body, lang, W, E=None, cfg=None):
    """Lint the page prose (front matter stripped, see lint_prose) with the bundled lint/lint.py and an entity-aware
    config. Findings (minus LINT_SKIP_RULES): blocker → error `lint:<rule>` (warning when no E given), warning →
    warning, info → dropped."""
    body = lint_prose(body)
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    md, cfgp = tmp.name + ".md", tmp.name + ".cfg.json"
    try:
        Path(md).write_text(body, encoding="utf-8")
        cmd = [sys.executable, str(LINT_SCRIPT), md, "--lang", lang, "--json", tmp.name]
        if cfg:
            Path(cfgp).write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
            cmd += ["--config", cfgp]
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")  # linter prints non-ASCII; keep Windows consoles from choking
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=env)
        rpt = json.loads(Path(tmp.name).read_text(encoding="utf-8"))
        for sec in rpt.get("sections", []):
            for v in sec.get("violations", []):
                rule, sev = str(v.get("rule")), v.get("severity")
                if rule in LINT_SKIP_RULES or sev not in ("blocker", "warning"):
                    continue
                msg = f"{sev} @ {v.get('location')}: {str(v.get('evidence'))[:100]} — {v.get('fix_instruction', '')[:100]}"
                (E if sev == "blocker" and E else W)("lint:" + rule, msg)
    except Exception as e:
        W("WARN_LINT_FAILED", f"lint could not run ({type(e).__name__}: {str(e)[:100]}); continuing without it")
    finally:
        for f in (tmp.name, md, cfgp):
            try:
                os.unlink(f)
            except OSError:
                pass


REVIEW_SEVERITIES = ("blocker", "warning", "info")


def _wsnorm(t):
    return re.sub(r"\s+", " ", str(t)).strip()


def review_block(page_path, page_text, review_arg, rep, E, W):
    """Merge the AI reviewer's review.json. Schema: {"reviewed_at": ISO8601, "reviewer": model name, "page_sha256":
    sha256 hex of page.md bytes at review time, "violations": [{"rule","severity","location","evidence",
    "fix_instruction", optional "waived_by", "waiver_note"}]}. A violation with a non-empty `waived_by` is only
    counted: a person waived it, the checker never decides."""
    blk = {"present": False, "reviewer": None, "blockers": 0, "warnings": 0, "waived": 0, "stale": False}
    rep["review"] = blk
    rp = Path(review_arg) if review_arg else page_path.parent / "review.json"
    if not rp.is_file():
        W("REVIEW_MISSING", f"no review file ({rp}); run the AI review after this pass and save it there")
        return
    blk["present"] = True
    try:
        rv = json.loads(rp.read_text(encoding="utf-8"))
        if not isinstance(rv, dict):
            raise ValueError("top level must be an object")
        for k, t in (("reviewed_at", str), ("reviewer", str), ("page_sha256", str), ("violations", list)):
            if not isinstance(rv.get(k), t):
                raise ValueError(f"'{k}' missing or not a {t.__name__}")
        for i, v in enumerate(rv["violations"]):
            if not isinstance(v, dict):
                raise ValueError(f"violations[{i}] is not an object")
            for k in ("rule", "severity", "location", "evidence", "fix_instruction"):
                if not isinstance(v.get(k), str):
                    raise ValueError(f"violations[{i}]: '{k}' missing or not a string")
            if v["severity"] not in REVIEW_SEVERITIES:
                raise ValueError(f"violations[{i}]: severity {v['severity']!r} not in {list(REVIEW_SEVERITIES)}")
            if v.get("waived_by") is not None and not isinstance(v["waived_by"], str):
                raise ValueError(f"violations[{i}]: 'waived_by' must be a string")
    except (ValueError, OSError) as e:
        E("REVIEW_INVALID", f"{rp.name}: {str(e)[:160]}")
        return
    blk["reviewer"] = rv["reviewer"]
    if rv["page_sha256"].strip().lower() != hashlib.sha256(page_path.read_bytes()).hexdigest():
        blk["stale"] = True
        E("REVIEW_STALE", "page changed since the review; re-run the review (its findings are not applied)")
        return
    page_norm = _wsnorm(page_text)
    for v in rv["violations"]:
        sev = v["severity"]
        if sev == "info":
            continue
        if (v.get("waived_by") or "").strip():
            blk["waived"] += 1
            continue
        ev = _wsnorm(v["evidence"])
        if not ev or ev not in page_norm:
            W("REVIEW_EVIDENCE_NOT_FOUND", f"review:{v['rule']}: evidence {ev[:60]!r} is not in page.md (paraphrased or invented?)")
        msg = f"{sev} @ {v['location']}: {ev[:100]} — {v['fix_instruction'][:100]}"
        if sev == "blocker":
            blk["blockers"] += 1
            E("review:" + v["rule"], msg)
        else:
            blk["warnings"] += 1
            W("review:" + v["rule"], msg)


def _review_summary(r):
    if not r:
        return "n/a"
    if not r["present"]:
        return "missing"
    return (f"{r['reviewer'] or '?'}{' STALE' if r['stale'] else ''} "
            f"{r['blockers']} blocker(s), {r['warnings']} warning(s), {r['waived']} waived")


def main():
    ap = argparse.ArgumentParser(description="Contract gate for a Mode B page.md")
    ap.add_argument("page")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--facts", help="facts.json (default: front matter `facts`, relative to page.md)")
    ap.add_argument("--sources", help="sources/index.json from snapshot.py (default: <plan dir>/sources/index.json)")
    ap.add_argument("--allow-draft-plan", action="store_true", help="dry run against a draft plan (loud warning)")
    ap.add_argument("--lint", action="store_true", help="no-op (lint is on by default; kept for backward compatibility)")
    ap.add_argument("--no-lint", action="store_true", help="skip the bundled Wendy linter, scripts/lint/lint.py")
    ap.add_argument("--review", help="AI reviewer's review.json (default: review.json next to page.md)")
    ap.add_argument("--json", help="write report JSON here")
    args = ap.parse_args()
    page, plan = Path(args.page), Path(args.plan)
    for p in (page, plan):
        if not p.is_file():
            print(f"[check_page] ERROR {p} not found", file=sys.stderr)
            sys.exit(2)
    rep = check(page, plan, args.facts, args.allow_draft_plan, not args.no_lint, args.sources, args.review)
    for e in rep["errors"]:
        log(f"ERROR {e['code']}{' (line %d)' % e['line'] if e.get('line') else ''}: {e['msg']}")
    for w in rep["warnings"]:
        log(f"WARN  {w['code']}{' (line %d)' % w['line'] if w.get('line') else ''}: {w['msg']}")
    shown = [m for m, s in rep["modules"].items() if s == "shown"]
    hidden = [m for m, s in rep["modules"].items() if s == "hidden"]
    log(f"{len(rep['errors'])} error(s), {len(rep['warnings'])} warning(s); shown: {' '.join(shown) or '-'}; "
        f"hidden: {' '.join(hidden) or '-'}; numbers checked: {rep['numbers_checked']}"
        + (f"; gaps logged: {rep['gaps']['logged']}" if rep.get("gaps") else "")
        + "; review: " + _review_summary(rep.get("review")))
    log("FAIL" if rep["errors"] else "PASS")
    if args.json:
        Path(args.json).write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.exit(1 if rep["errors"] else 0)


if __name__ == "__main__":
    main()
