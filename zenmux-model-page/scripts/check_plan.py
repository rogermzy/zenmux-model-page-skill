#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_plan.py — contract gate for a page-revamp plan.md (Mode A output)

Usage:
    python3 check_plan.py plan.md
    python3 check_plan.py plan.md --sources sources/index.json --json plan.check.json

Checks front matter, the four top-level parts, the `json page-template` appendix against the
field rules in references/template-spec.md, and that Part 3 documents every module.
ERROR = blocks (exit 1); WARN = advisory. Report JSON: {file, errors, warnings, modules}.
Stdlib only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_KEYS = ["plan_slug", "status", "checked_date", "sample_url"]
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MODULE_ID = re.compile(r"^M([1-9]\d*)$")
SHOW_IF = re.compile(r"^(?:category:\S+|facts:\S+|manual:\S.*)$")
URL_RE = re.compile(r"https?://[^\s)\]>|]+")


def log(m): print(f"[check_plan] {m}", flush=True)


# ── shared helpers (also imported by check_page.py) ──────────────────────────────────────────
def parse_front_matter(text: str):
    """Hand-parsed `key: value` front matter → (dict|None, index of first body line).
    Returns (None, 0) when the file doesn't open with a closed --- block."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, 0
    fm = {}
    for i in range(1, len(lines)):
        ln = lines[i]
        if ln.strip() == "---":
            return fm, i + 1
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", ln)
        if m:
            val = re.sub(r"\s+#.*$", "", m.group(2)).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            fm[m.group(1)] = val
    return None, 0


def extract_spec(text: str):
    """→ (spec, None) | (detail, error_code)."""
    m = re.search(r"^```json page-template[^\n]*\n(.*?)^```", text, re.M | re.S)
    if not m:
        return None, "PLAN_NO_SPEC_BLOCK"
    try:
        spec = json.loads(m.group(1))
    except ValueError as e:
        return str(e), "PLAN_SPEC_JSON"
    if not isinstance(spec, dict):
        return "top level is not an object", "PLAN_SPEC_JSON"
    return spec, None


def norm_url(u: str) -> str:
    u = u.strip().rstrip(".,;")
    return re.sub(r"/+$", "", u.split("#")[0])


def split_row(row: str):
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", row)]


def is_sep_row(cells):
    return bool(cells) and all(re.fullmatch(r":?-+:?", c) for c in cells if c) and any(cells)


def tables(lines):
    """Markdown tables in `lines` → list of {start, header, rows}; rows = data rows (cell lists),
    header and separator excluded. `start` = index of the first line of the table."""
    out, cur, start = [], [], 0
    for i, ln in enumerate(lines + [""]):
        if ln.lstrip().startswith("|"):
            if not cur:
                start = i
            cur.append(ln)
        elif cur:
            rows = [split_row(r) for r in cur]
            out.append({"start": start, "header": rows[0],
                        "rows": [r for r in rows[1:] if not is_sep_row(r)]})
            cur = []
    return out


def ids_in(s: str):
    """Module ids mentioned in s; ranges like M5–M7 / M5-M7 expand."""
    out = set()
    for m in re.finditer(r"(?<![A-Za-z0-9])M(\d+)\s*[–—~～\-]\s*M?(\d+)(?![A-Za-z0-9])", s):
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b and b - a < 100:
            out |= {f"M{k}" for k in range(a, b + 1)}
    for m in re.finditer(r"(?<![A-Za-z0-9])M(\d+)(?![A-Za-z0-9])", s):
        out.add(f"M{m.group(1)}")
    return out


# ── checks ──────────────────────────────────────────────────────────────────────────────────
def check(text: str, path: str, sources: str = None):
    errors, warnings = [], []
    E = lambda code, msg: errors.append({"code": code, "msg": msg})
    W = lambda code, msg: warnings.append({"code": code, "msg": msg})

    fm, _ = parse_front_matter(text)
    if fm is None:
        E("PLAN_NO_FRONT_MATTER", "plan.md must open with a closed --- front matter block")
        fm = {}
    else:
        for k in REQUIRED_KEYS:
            if not fm.get(k):
                E("PLAN_MISSING_KEY", f"front matter key '{k}' missing or empty")
        st = fm.get("status")
        if st and st not in ("draft", "approved"):
            E("PLAN_BAD_STATUS", f"status '{st}' is not draft|approved")
        if st == "approved" and not (fm.get("approved_by") and fm.get("approved_at")):
            E("PLAN_APPROVAL_INCOMPLETE", "status approved requires approved_by and approved_at")
        cd = fm.get("checked_date")
        if cd and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cd):
            W("WARN_CHECKED_DATE", f"checked_date '{cd}' is not YYYY-MM-DD")

    # top-level parts (outside code fences)
    lines = text.split("\n")
    heads, other, fence = {}, [], False
    for i, ln in enumerate(lines):
        if re.match(r"^\s{0,3}(```|~~~)", ln):
            fence = not fence
            continue
        if fence or not re.match(r"^#(?!#)", ln):
            continue
        m = re.match(r"^#(?!#)\s*\**\s*([1-4])\.", ln)
        if m:
            heads.setdefault(int(m.group(1)), i)
        else:
            other.append(i)
    for n in (1, 2, 3, 4):
        if n not in heads:
            E("PLAN_MISSING_HEADING", f"missing top-level heading '# {n}.'")

    def part(n):
        if n not in heads:
            return []
        ends = [i for i in list(heads.values()) + other if i > heads[n]]
        return lines[heads[n] + 1:(min(ends) if ends else len(lines))]

    p1, p2, p3 = part(1), part(2), part(3)

    spec, err = extract_spec(text)
    mods = []
    if err == "PLAN_NO_SPEC_BLOCK":
        E(err, "no ```json page-template fenced block found")
        spec = None
    elif err:
        E(err, f"page-template JSON does not parse: {spec}")
        spec = None
    if spec is not None:
        mods = check_spec(spec, fm, E)

    urls = set()
    if 1 in heads:
        rows = [r for t in tables(p1) for r in t["rows"]]
        if len(rows) < 2:
            E("PLAN_PART1_ROWS", f"part 1 needs a table with >= 2 competitor rows (found {len(rows)})")
        for r in rows:
            found = URL_RE.findall(" | ".join(r))
            if not found:
                E("PLAN_PART1_URL", f"part 1 row has no URL: {r[0][:60]!r}")
            urls.update(found)
    if 2 in heads:
        rows = [r for t in tables(p2) for r in t["rows"]]
        if not rows:
            E("PLAN_PART2_TABLE", "part 2 needs a table with >= 1 data row")
        for r in rows:
            urls.update(URL_RE.findall(" | ".join(r)))
        ptxt = "\n".join(p2)
        missing = [k for k in ("🔥", "⚡", "⚠") if k not in ptxt]
        if missing:
            W("WARN_NO_PRIORITY_LEGEND",
              f"part 2 priority legend incomplete (missing {' '.join(missing)}; expected 🔥 / ⚡ / ⚠️)")

    if 3 in heads and mods:
        covered = set()
        for ln in p3:
            if re.match(r"^#{2,}\s", ln):
                covered |= ids_in(ln)
        for mid in mods:
            if mid not in covered:
                E("PLAN_PART3_MODULE_HEADING", f"part 3 has no '##' heading mentioning {mid}")
        for mid in sorted(ids_in("\n".join(p3)) - set(mods), key=lambda s: int(s[1:])):
            E("PLAN_PART3_UNKNOWN_MODULE", f"part 3 mentions {mid}, which is not in the spec")

    if sources:
        known = None
        try:
            known = set()
            for e in json.loads(Path(sources).read_text(encoding="utf-8")):
                for k in ("url", "final_url"):
                    if e.get(k):
                        known.add(norm_url(e[k]))
        except Exception as e:
            known = None
            W("WARN_SOURCES_UNREADABLE", f"could not read {sources}: {e}")
        if known is not None:
            if fm.get("sample_url"):
                urls.add(fm["sample_url"])
            for u in sorted(urls):
                if norm_url(u) not in known:
                    W("WARN_NO_SNAPSHOT", f"no snapshot in {sources} for {u}")

    return {"file": path, "errors": errors, "warnings": warnings, "modules": mods}


def check_spec(spec, fm, E):
    """Field rules of references/template-spec.md. Returns the list of module ids."""
    tid = spec.get("template_id")
    if not isinstance(tid, str) or not KEBAB.match(tid):
        E("SPEC_TEMPLATE_ID", f"template_id {tid!r} must be kebab-case")
    elif fm.get("plan_slug") and tid != fm["plan_slug"]:
        E("SPEC_TEMPLATE_ID_MISMATCH", f"template_id '{tid}' != plan_slug '{fm['plan_slug']}'")
    for k, code in (("title_pattern", "SPEC_TITLE_PATTERN"), ("h1_pattern", "SPEC_H1_PATTERN")):
        v = spec.get(k)
        if not isinstance(v, str) or "{Entity}" not in v:
            E(code, f"{k} must be a string containing {{Entity}}")
    if not isinstance(spec.get("missing_value_labels"), dict) or not spec.get("missing_value_labels"):
        E("SPEC_MISSING_LABELS", "missing_value_labels must be a non-empty object")
    sv = spec.get("status_vocabulary")
    if not isinstance(sv, list) or not sv or not all(isinstance(x, str) and x for x in sv):
        E("SPEC_STATUS_VOCAB", "status_vocabulary must be a non-empty list of strings")

    modules = spec.get("modules")
    if not isinstance(modules, list) or not modules:
        E("SPEC_MODULES_EMPTY", "spec.modules must be a non-empty list")
        return []
    ids = []
    for i, m in enumerate(modules):
        if not isinstance(m, dict):
            E("SPEC_MODULE_ID", f"modules[{i}] is not an object")
            ids.append(None)
            continue
        mid = m.get("id")
        ids.append(mid if isinstance(mid, str) else None)
        want = f"M{i + 1}"
        if not isinstance(mid, str) or not MODULE_ID.match(mid):
            E("SPEC_MODULE_ID", f"modules[{i}].id {mid!r} must look like M1, M2, …")
        elif mid != want:
            E("SPEC_MODULE_ID", f"modules[{i}].id is {mid}; ids must be unique and consecutive in page order (expected {want})")
        tag = mid if isinstance(mid, str) else f"modules[{i}]"
        req = m.get("required")
        if not isinstance(req, bool):
            E("SPEC_REQUIRED_TYPE", f"{tag}.required must be boolean")
        h2 = m.get("h2")
        if h2 is None:
            if i != 0:
                E("SPEC_H2_NULL", f"{tag}.h2 is null — only M1 (the H1 module) may have a null h2")
        elif not isinstance(h2, str) or not h2.strip():
            E("SPEC_H2_VALUE", f"{tag}.h2 must be a non-empty string pattern (or null for M1)")
        si = m.get("show_if")
        if req is True and si is not None:
            E("SPEC_SHOW_IF_REQUIRED", f"{tag} is required, so show_if must be null")
        elif req is False:
            if si is None:
                E("SPEC_SHOW_IF_MISSING", f"{tag} is conditional, so show_if must be set")
            elif not isinstance(si, str) or not SHOW_IF.match(si):
                E("SPEC_SHOW_IF_FORMAT", f"{tag}.show_if {si!r} must be category:x | facts:x | manual:<reason>")
        if "status_table" in m and not isinstance(m["status_table"], bool):
            E("SPEC_STATUS_TABLE_TYPE", f"{tag}.status_table must be boolean")
        if "derived_from" in m:
            df = m["derived_from"]
            if not isinstance(df, list):
                E("SPEC_DERIVED_FROM", f"{tag}.derived_from must be a list of module ids")
            else:
                for d in df:
                    if d is None or d not in ids[:i]:
                        E("SPEC_DERIVED_FROM", f"{tag}.derived_from '{d}' must be an existing, earlier module id")
    clean = [x for x in ids if x]
    if len(set(clean)) != len(clean):
        E("SPEC_MODULE_ID", "duplicate module ids")
    return clean


def main():
    ap = argparse.ArgumentParser(description="Contract gate for a page-revamp plan.md")
    ap.add_argument("plan")
    ap.add_argument("--sources", help="sources/index.json from snapshot.py (enables URL-snapshot warnings)")
    ap.add_argument("--json", help="write report JSON here")
    args = ap.parse_args()
    p = Path(args.plan)
    if not p.is_file():
        print(f"[check_plan] ERROR {p} not found", file=sys.stderr)
        sys.exit(2)
    rep = check(p.read_text(encoding="utf-8"), str(p), args.sources)
    for e in rep["errors"]:
        log(f"ERROR {e['code']}: {e['msg']}")
    for w in rep["warnings"]:
        log(f"WARN  {w['code']}: {w['msg']}")
    log(f"{len(rep['errors'])} error(s), {len(rep['warnings'])} warning(s), modules: {', '.join(rep['modules']) or '-'}")
    log("FAIL" if rep["errors"] else "PASS")
    if args.json:
        Path(args.json).write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.exit(1 if rep["errors"] else 0)


if __name__ == "__main__":
    main()
