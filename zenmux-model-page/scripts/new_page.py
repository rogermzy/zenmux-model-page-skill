#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new_page.py — start a ZenMux model page: resolve the model, snapshot every source, write the facts starter

Usage:
    python3 new_page.py <workspace> "<model name | id like deepseek/deepseek-v4-pro | zenmux.ai URL>"
                        [--date YYYY-MM-DD] [--max-age-days 14] [--force]
                        [--api-json FILE] [--skip-docs] [--site-config FILE]

What it does (nothing is written before steps 1-2 succeed):
  1. Resolve the query to a model id with the public API (https://zenmux.ai/api/v1/models): match on id, on
     display name with or without the "Developer: " prefix, on the id's model part; case/space-insensitive.
  2. Map output_modalities to a page type: text, image, video, speech->audio. Anything else
     (transcription, embeddings, rerank, decisions, unknown) has no template: exit 3, nothing written.
  3. Snapshot (via snapshot.py, into <workspace>/sources/): the model page (role fact), its decoded flight
     data (role data, via zenmux_data.py), the model's public-API record (role data).
  4. Re-snapshot the shared ZenMux docs listed in zenmux-site.json (plus the per-type extras) when they are
     missing or older than --max-age-days.
  5. Write <workspace>/pages/<slug>/facts.json (starter) and gap-candidates.json. Every fact quote is
     asserted to be a whitespace-normalised substring of its source's snapshot text. Verdicts are UNCHECKED.
     0 / empty / missing values get NO fact: they go to gap-candidates.json for review (gaps[] stays []).

Exit codes: 0 ok · 1 usage / a required fetch failed · 2 model not found or ambiguous ·
            3 model type has no page template · 4 facts.json exists (use --force) · 5 page shape not recognised
Stdlib only, Python 3.9+. Needs snapshot.py next to this file.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import zenmux_data  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
DEFAULT_SITE = {
    "base_url": "https://zenmux.ai", "models_api": "https://zenmux.ai/api/v1/models",
    "page_url_template": "https://zenmux.ai/{id}",
    "output_modality_to_entity_type": {"text": "text", "image": "image", "video": "video", "speech": "audio"},
    "entity_type_priority": ["video", "image", "audio", "text"], "shared_docs": [], "type_docs": {},
}
UNIT_PHRASE = {"millionTokens": ("USD / 1M tokens", "per 1M tokens"), "seconds": ("USD / second", "per second"),
               "counts": ("USD / count", "per count")}


def die(code, msg):
    print(f"[new_page] {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def log(msg):
    print(f"[new_page] {msg}", flush=True)


def norm_ws(s):
    return " ".join(str(s).split())


def read_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die(1, f"cannot read {what} {path}: {e}")


# ── 1. resolve ────────────────────────────────────────────────────────────────────────────
def load_models(site, api_json):
    if api_json:
        raw = read_json(api_json, "--api-json")
    else:
        req = urllib.request.Request(site["models_api"], headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            die(1, f"could not fetch {site['models_api']}: {getattr(e, 'reason', e)}")
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, list) or not data or not all(isinstance(m, dict) and "id" in m for m in data):
        die(1, "the models API did not return {data:[{id,...}]}: its shape changed? (stop and tell the site owner)")
    return data


def key(s):
    return re.sub(r"[^a-z0-9.]+", "", str(s).lower())


def strip_dev(name):
    return name.split(": ", 1)[1] if ": " in name else name


def resolve(models, query, site):
    q = query.strip()
    m = re.match(r"^https?://(?:www\.)?zenmux\.ai/([^?#]+)", q)
    if m:
        q = m.group(1).strip("/")
    qk = key(q)
    levels = [
        ("id", lambda m: key(m["id"]) == qk),
        ("display name", lambda m: key(m.get("display_name", "")) == qk),
        ("display name without developer prefix", lambda m: key(strip_dev(m.get("display_name", ""))) == qk),
        ("model part of the id", lambda m: key(m["id"].split("/", 1)[-1]) == qk),
    ]
    for how, test in levels:
        hits = [m for m in models if test(m)]
        if len(hits) == 1:
            return hits[0], how
        if len(hits) > 1:
            print(f"[new_page] '{query}' is ambiguous (matches {how} of {len(hits)} models). Pass the full id:", file=sys.stderr)
            for h in hits:
                print(f"    {h['id']}    {h.get('display_name')}    output={h.get('output_modalities')}", file=sys.stderr)
            sys.exit(2)
    near = [m for m in models if qk and (qk in key(m["id"]) or qk in key(m.get("display_name", "")))][:12]
    print(f"[new_page] no model matches '{query}' exactly.", file=sys.stderr)
    if near:
        print("[new_page] partial matches (re-run with the full id):", file=sys.stderr)
        for h in near:
            print(f"    {h['id']}    {h.get('display_name')}", file=sys.stderr)
    sys.exit(2)


def entity_type(rec, site):
    outs = rec.get("output_modalities")
    outs = [outs] if isinstance(outs, str) else list(outs or [])
    mapping = site["output_modality_to_entity_type"]
    supported = [mapping[o] for o in outs if o in mapping]
    unsupported = [o for o in outs if o not in mapping]
    if not outs or unsupported:
        die(3, f"no page template for model type {','.join(unsupported) if unsupported else 'unknown (no output_modalities)'}; "
               "the approved plan covers text, image, video, audio")
    for t in site["entity_type_priority"]:
        if t in supported:
            return t, outs
    die(3, f"no page template for model type {','.join(outs)}; the approved plan covers text, image, video, audio")


# ── snapshots ─────────────────────────────────────────────────────────────────────────────
def run_snapshot(url, sources, role, from_file=None):
    cmd = [sys.executable, str(HERE / "snapshot.py"), url, "--dir", str(sources), "--role", role]
    if from_file:
        cmd += ["--from-file", str(from_file)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def index_entry(sources, url, role):
    """The sources/index.json entry for url+role. snapshot.py rewrites the index under a lock but readers get
    none, so with parallel runs (one agent per entity) a read can catch a half-written file: retry."""
    for _ in range(40):
        try:
            idx = json.loads((sources / "index.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.1)
            continue
        for e in idx:
            if isinstance(e, dict) and e.get("url") == url and e.get("role") == role:
                return e
        return None
    return None


def is_fresh(sources, url, max_age_days):
    e = index_entry(sources, url, "fact")
    if not e or not (sources / e.get("txt", "\0")).is_file():
        return False
    try:
        t = datetime.strptime(e["fetched_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return False
    return (datetime.now(timezone.utc) - t).days < max_age_days


def api_record_text(rec):
    """One JSON key per line, so a quote can be one line of it."""
    lines = ["{"]
    items = list(rec.items())
    for i, (k, v) in enumerate(items):
        lines.append(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" + ("," if i < len(items) - 1 else ""))
    lines.append("}")
    return "\n".join(lines) + "\n"


# ── facts ─────────────────────────────────────────────────────────────────────────────────
def fmt_count(n):
    """Token counts the way the ZenMux table shows them: 8192 -> 8.19K, 12800 -> 12.8K, 1000000 -> 1M."""
    n = int(n)
    if n < 1000:
        return str(n)
    for div, suf in ((1000, "K"), (1000000, "M"), (1000000000, "B")):
        s = f"{n / div:.3g}"
        if "e" not in s and float(s) < 1000:
            return s + suf
    return str(n)


def comma(n):
    return f"{int(n):,}"


class Builder:
    def __init__(self, hay, date_s):
        self.hay, self.date, self.facts, self.cands, self._ids = hay, date_s, [], [], set()

    def has(self, url, quote):
        return norm_ws(quote) in norm_ws(self.hay[url])

    def fact(self, id, cat, endpoint, label, display, url, quote, value=None, unit=None, condition=None,
             aliases=None, **extra):
        if not self.has(url, quote):
            raise AssertionError(f"fact {id}: quote not found in the snapshot text of {url}: {quote[:80]!r}")
        base, n = id, 1
        while id in self._ids:
            n += 1
            id = f"{base}.{n}"
        self._ids.add(id)
        f = {"id": id, "category": cat, "endpoint": endpoint, "label": label}
        if value is not None:
            f["value"] = value
        if unit:
            f["unit"] = unit
        f.update({"display": display, "source_url": url, "quote": quote, "checked_at": self.date, "verdict": "UNCHECKED"})
        if condition:
            f["condition"] = condition
        if aliases:
            f["aliases"] = aliases
        f.update(extra)
        self.facts.append(f)
        return f

    def cand(self, field, endpoint, found, evidence, note, kind):
        for e in evidence:
            if not self.has(e[0], e[1]):
                raise AssertionError(f"gap candidate {field}: quote not found in {e[0]}: {e[1][:80]!r}")
        self.cands.append({"field": field, "endpoint": endpoint, "found": found,
                           "quote": evidence[0][1], "source_url": evidence[0][0],
                           "evidence": [{"source_url": u, "quote": q} for u, q in evidence],
                           "suggested_kind": kind, "note": note})


def cond_phrase(r):
    parts = [UNIT_PHRASE.get(r["unit"], (None, f"chargeUnit {r['unit']}"))[1]]
    for k, v in sorted(r["conditions"].items()):
        if isinstance(v, dict) and "from" in v:
            note = {"bizMinute": " (minutes of the day as coded; time zone not stated)"}.get(k, " (range as coded)")
            parts.append(f"{k} {v['from']}-{v['to']}{note}")
        elif k == "bizDayOfWeek" and isinstance(v, list):
            parts.append("bizDayOfWeek " + ",".join(str(d) for d in v) + " (as coded; day numbering not stated)")
        else:
            parts.append(f"{k} {v}")
    return "; ".join(parts)


def cond_suffix(r):
    bits = []
    for k, v in sorted(r["conditions"].items()):
        if isinstance(v, dict) and "from" in v:
            bits.append(("m" if k == "bizMinute" else re.sub(r"[^A-Za-z0-9]+", "", k) + "-") + f"{v['from']}-{v['to']}")
        elif k == "bizDayOfWeek" and isinstance(v, list):
            bits.append("d" + (f"{v[0]}-{v[-1]}" if len(v) > 3 and v == list(range(v[0], v[-1] + 1)) else "".join(map(str, v))))
        else:
            bits.append(re.sub(r"[^A-Za-z0-9.]+", "", str(v)))
    return ".".join(bits)


def build(rec, etype, summ, api_text, page_url, api_url, hay, date_s, discount_visible_ok):
    B = Builder(hay, date_s)
    model, provs = summ["model"], summ["providers"]
    mraw = model["raw"]
    PD = page_url

    def mq(pattern):
        m = re.search(pattern, mraw)
        return m.group(0) if m else None

    # model-level facts from the page data
    q = mq(r'"name":"[^"]*"')
    if q:
        B.fact("name.zenmux", "spec", None, "ZenMux model name (page title field)", model["name"], PD, q)
    for fld, label in (("input_modalities", "Input modalities (ZenMux page data)"), ("output_modalities", "Output modalities (ZenMux page data)")):
        q = mq(rf'"{fld}":"[^"]*"')
        if q and model[fld]:
            B.fact(f"spec.{fld.split('_')[0]}", "spec", None, label, ", ".join(model[fld]), PD, q)
        else:
            B.cand(fld, None, "empty", [(PD, mraw[:60])], f"{fld} is empty in the page data", "missing")
    q = mq(r'"publish_time":"[^"]*"')
    if q and model.get("publish_time"):
        B.fact("date.publish", "date", None, "ZenMux publish time", model["publish_time"], PD, q, value=model["publish_time"])
    else:
        B.cand("publish_time", None, "empty", [(PD, mraw[:60])], "no publish_time in the page data", "missing")
    q = mq(r'"aliases":\[[^\]]*\]')
    if q and model.get("aliases"):
        B.fact("spec.aliases", "spec", None, "Model aliases (ZenMux page data)", ", ".join(model["aliases"]), PD, q, value=model["aliases"])
    else:
        B.cand("aliases", None, "[]", [(PD, q or mraw[:60])], "the page data lists no aliases (informational: not every model has one)", "missing")
    disc = str(model.get("pricing_discount") or "1")
    if not 0 < Decimal(disc) <= 1:
        B.cand("pricing_discount", None, disc, [(PD, mq(r'"pricing_discount":"[^"]*"') or mraw[:60])],
               f"pricing_discount is {disc}: not a usable multiplier (0 shows no badge on the page); no discount handled", "suspected_error")
        disc = "1"
    if Decimal(disc) != 1:
        q = mq(r'"pricing_discount":"[^"]*"')
        pct = fmt_pct(Decimal(disc))
        B.fact("discount.zenmux", "price", None, "ZenMux pricing_discount on the model (price multiplier)",
               pct if discount_visible_ok.get(pct) else disc, PD, q, value=float(disc),
               condition="fee-record rates are list prices; the multiplier is applied by ZenMux; end date not published",
               aliases=[disc])
    if model.get("context_length"):
        B.fact("spec.context.model", "spec", None, "Context length (ZenMux model block)", fmt_count(model["context_length"]), PD,
               mq(r'"context_length":\d+'), value=model["context_length"], unit="tokens",
               aliases=[comma(model["context_length"]), str(model["context_length"])])
    else:
        B.cand("context_length", None, str(model.get("context_length")), [(PD, mq(r'"context_length":[^,}]*') or mraw[:60])],
               "model-level context_length is 0 or missing", "missing")

    # endpoints and per-provider facts
    endpoints = []
    api_prices = (rec.get("pricings") or {})
    for p in provs:
        s = p["slug"]
        ep = {"id": s, "provider": p["name"], "served_version": "Not verified", "status": p["status"]}
        if p["status"] != "active":
            sun = f"{p['name']}Sunset" in norm_ws(hay["__visible__"]).replace(" ", "")
            ep["note"] = (f"page data visible={p['visible']!r}; " + ("the provider table shows a 'Sunset' badge on this provider" if sun
                                                                    else "no 'Sunset' badge found in the page text") +
                          "; treated as disabled")
            B.cand("provider status", s, f"visible={p['visible']}", [(PD, re.search(r'"visible":\d+', p["fragment"]).group(0))],
                   f"{p['name']} is flagged visible={p['visible']} ({'Sunset badge on the page' if sun else 'no badge found'}); "
                   "the page data has no explanation, so confirm with ZenMux whether this endpoint still serves requests and at the listed price",
                   "missing")
        endpoints.append(ep)
        frag = p["fragment"]
        pq = lambda pat: (re.search(pat, frag).group(0) if re.search(pat, frag) else None)  # noqa: E731
        for fld, fid, label in (("context_length", "context", "Context length"), ("max_completion_tokens", "maxout", "Max output (max_completion_tokens)")):
            v, quote = p.get(fld), pq(rf'"{fld}":\s*[^,}}]+')
            if v and quote:
                B.fact(f"spec.{s}.{fid}", "spec", s, f"{label} ({p['name']})", fmt_count(v), PD, quote, value=v, unit="tokens",
                       aliases=[comma(v), str(v)])
            else:
                B.cand(f"{fld}", s, "0" if v == 0 else "missing", [(PD, quote or frag[:60])],
                       f"{p['name']}: {fld} is {'0' if v == 0 else 'absent'} in the page data; the page must show Not published/Not verified, not 0",
                       "missing")
        if p["suitable_api"]:
            q = pq(r'"suitable_api":"[^"]*"')
            B.fact(f"spec.{s}.protocols", "spec", s, f"API protocols served ({p['name']}, suitable_api)", ", ".join(p["suitable_api"]),
                   PD, q, value=p["suitable_api"])
        if not p["fee_items"]:
            B.cand("fee_items", s, "none", [(PD, pq(r'"pricing_variable":"[^"]*"') or frag[:60])],
                   f"{p['name']}: the fee records are empty", "missing")
        pdisc = str(p.get("pricing_discount") or "1")
        if not 0 < Decimal(pdisc) <= 1:
            pdisc = "1"
        vis = hay["__visible__"]
        undisc, zero = [], {}
        for it in p["fee_items"]:
            recs = it["records"]
            seg = None
            if Decimal(pdisc) != 1:
                lists = sorted({Decimal(fmt_decimal(r["rate"])) for r in recs if r["rate"]})
                if lists:
                    discs = [l * Decimal(pdisc) for l in lists]
                    rng = lambda xs: "-".join(fmt_decimal(x) for x in ((xs[0], xs[-1]) if len(xs) > 1 else (xs[0],)))  # noqa: E731
                    seg = re.search(rf"(?<![\d.])\$?{re.escape(rng(lists))}\$?{re.escape(rng(discs))}(?![\d.])", norm_ws(vis))
                    if not seg:
                        undisc.append(it["code"])
            for r in recs:
                suffix = cond_suffix(r) if len(recs) > 1 else ""
                sfx = f".{suffix}" if suffix else ""
                if not r["rate"]:
                    zero.setdefault(it["code"], []).append(r)
                    continue
                unit_label = UNIT_PHRASE.get(r["unit"], (f"USD / {r['unit']}", None))[0]
                cnote = cond_phrase(r)
                if Decimal(pdisc) != 1:
                    cnote += (f"; list price before ZenMux pricing_discount {pdisc}" if seg else
                              f"; provider pricing_discount {pdisc} (whether it applies to this fee item is not stated on the page)")
                B.fact(f"price.{s}.{it['code']}{sfx}", "price", s, f"Fee item {it['code']} ({p['name']})", "$" + r["rate_text"], PD, r["quote"],
                       value=r["rate"], unit=unit_label, condition=cnote, fee_item_code=it["code"], fee_item_name=it["name"])
                if seg:
                    dv = Decimal(fmt_decimal(r["rate"])) * Decimal(pdisc)
                    B.fact(f"price.{s}.{it['code']}.discounted{sfx}", "price", s,
                           f"Fee item {it['code']} after ZenMux discount ({p['name']})", "$" + fmt_decimal(dv), PD, seg.group(0),
                           value=float(dv), unit=unit_label,
                           condition=cond_phrase(r) + f"; list price x pricing_discount {pdisc}, as shown next to the list price in the page's provider table; end date not published",
                           fee_item_code=it["code"], fee_item_name=it["name"])
        for code, zr in zero.items():
            total = sum(len(i["records"]) for i in p["fee_items"] if i["code"] == code)
            B.cand(f"fee {code}", s, "0", [(PD, zr[0]["quote"])],
                   f"{p['name']}: fee item {code} has rate 0 in {len(zr)} of {total} record(s), e.g. ({cond_phrase(zr[0])}); "
                   "is it free or unpublished? The page must not show $0 unless ZenMux says free", "suspected_error")
        if undisc:
            B.cand("discounted price", s, "not located", [(PD, pq(r'"pricing_discount":"[^"]*"') or frag[:60])],
                   f"{p['name']}: pricing_discount is {pdisc} but the discounted rate for fee item(s) {', '.join(undisc)} "
                   "was not found next to the list rate in the page text (the table may not show those items); no discounted-price fact written for them",
                   "not_in_html")

    # public API record
    aq = lambda k: next((ln.strip().rstrip(",") for ln in api_text.splitlines() if ln.lstrip().startswith(f'"{k}":')), None)  # noqa: E731
    if rec.get("max_tokens"):
        B.fact("spec.maxout.api", "spec", None, "Max output (ZenMux public API max_tokens)", fmt_count(rec["max_tokens"]), api_url, aq("max_tokens"),
               value=rec["max_tokens"], unit="tokens", aliases=[comma(rec["max_tokens"]), str(rec["max_tokens"])])
    else:
        B.cand("max_tokens", None, "absent" if "max_tokens" not in rec else "0", [(api_url, aq("id"))],
               "the public API record has no max_tokens (informational; the provider rows may still give max_completion_tokens)", "missing")
    if rec.get("context_length"):
        B.fact("spec.context.api", "spec", None, "Context length (ZenMux public API)", fmt_count(rec["context_length"]), api_url, aq("context_length"),
               value=rec["context_length"], unit="tokens", aliases=[comma(rec["context_length"]), str(rec["context_length"])])
    # cross-source checks -> candidates (never auto-gaps)
    pctx = {p["context_length"] for p in provs if p.get("context_length")}
    if rec.get("context_length") and pctx and rec["context_length"] not in pctx:
        B.cand("context_length", None, f"API {rec['context_length']} vs providers {sorted(pctx)}",
               [(api_url, aq("context_length")), (PD, mq(r'"context_length":\d+'))],
               "the public API context_length equals no provider's context_length", "contradiction")
    if model.get("context_length") and pctx and model["context_length"] not in pctx:
        B.cand("context_length", None, f"model block {model['context_length']} vs providers {sorted(pctx)}",
               [(PD, mq(r'"context_length":\d+'))] + [(PD, re.search(r'"context_length":\d+', p["fragment"]).group(0)) for p in provs[:1] if re.search(r'"context_length":\d+', p["fragment"])],
               "the model-level context_length equals no provider's context_length; M1 must not show one number as if it held for all providers",
               "contradiction")
    if rec.get("publish_time") and model.get("publish_time") and rec["publish_time"] != model["publish_time"]:
        B.cand("publish_time", None, f"API {rec['publish_time']} vs page {model['publish_time']}",
               [(api_url, aq("publish_time")), (PD, mq(r'"publish_time":"[^"]*"'))], "publish_time differs between the API and the page data", "contradiction")
    page_list = {}
    page_disc = {}
    for p in provs:
        for it in p["fee_items"]:
            for r in it["records"]:
                lv = Decimal(zenmux_data.fmt_decimal(r["rate"]))
                page_list.setdefault(it["code"], set()).add(lv)
                page_disc.setdefault(it["code"], set()).add(lv * Decimal(str(p.get("pricing_discount") or 1)))
    api_vals = {c: {Decimal(zenmux_data.fmt_decimal(e["value"])) for e in v if isinstance(e, dict) and "value" in e} for c, v in api_prices.items()}
    pricing_line = (aq("pricings") or "")[:100]
    first_quote = {}
    for p in provs:
        for it in p["fee_items"]:
            first_quote.setdefault(it["code"], it["records"][0]["quote"])
    for c in sorted(set(page_list) - set(api_vals)):
        if pricing_line:
            B.cand(f"fee item {c}", None, "on the page, not in the public API", [(PD, first_quote[c]), (api_url, pricing_line)],
                   f"fee item '{c}' is billed per the page data but the public API pricings has no such key (API incomplete?)", "suspected_error")
    for c in sorted(set(api_vals) - set(page_list)):
        B.cand(f"fee item {c}", None, "in the public API, not on the page", [(api_url, pricing_line)] if pricing_line else [(api_url, aq("id"))],
               f"public API prices '{c}' but the page data has no such fee item", "suspected_error")
    for c in sorted(set(api_vals) & set(page_list)):
        allowed = page_list[c] | page_disc[c]
        if api_vals[c] and not api_vals[c] <= allowed:
            B.cand(f"fee item {c}", None, f"API {sorted(map(str, api_vals[c]))} vs page list {sorted(map(str, page_list[c]))} / discounted {sorted(map(str, page_disc[c]))}",
                   [(PD, first_quote[c]), (api_url, pricing_line)] if pricing_line else [(PD, first_quote[c])],
                   f"fee item '{c}': the public API has value(s) that match no page list price and no discounted price", "contradiction")
    return B, endpoints


def fmt_pct(disc):
    """pricing_discount 0.5 -> '50% OFF' (the badge the site shows)."""
    return f"{zenmux_data.fmt_decimal((1 - disc) * 100)}% OFF"


def fmt_decimal(x):
    return zenmux_data.fmt_decimal(x)


def main():
    ap = argparse.ArgumentParser(description="Start a ZenMux model page: resolve, snapshot, write the facts starter",
                                 epilog="exit: 0 ok, 1 usage/fetch, 2 not found/ambiguous, 3 no template for the type, "
                                        "4 facts.json exists, 5 page shape not recognised")
    ap.add_argument("workspace")
    ap.add_argument("model", help='model name, id (deepseek/deepseek-v4-pro) or page URL')
    ap.add_argument("--date", default=None, help="checked_date (default: today)")
    ap.add_argument("--max-age-days", type=int, default=14, help="re-snapshot shared docs older than this")
    ap.add_argument("--force", action="store_true", help="overwrite an existing facts.json")
    ap.add_argument("--api-json", help="use this saved /api/v1/models response instead of fetching it")
    ap.add_argument("--skip-docs", action="store_true", help="do not (re-)snapshot the shared docs")
    ap.add_argument("--site-config", default=str(HERE.parent / "zenmux-site.json"))
    args = ap.parse_args()

    date_s = args.date or date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_s):
        die(1, "--date must be YYYY-MM-DD")
    site = dict(DEFAULT_SITE)
    if Path(args.site_config).is_file():
        site.update(read_json(args.site_config, "site config"))

    models = load_models(site, args.api_json)
    rec, how = resolve(models, args.model, site)
    etype, outs = entity_type(rec, site)
    mid = rec["id"]
    slug = mid.split("/", 1)[-1]
    ws = Path(args.workspace)
    facts_path = ws / "pages" / slug / "facts.json"
    if facts_path.exists() and not args.force:
        die(4, f"{facts_path} already exists; refusing to overwrite (use --force). Nothing was changed.")
    page_url = site["page_url_template"].format(id=mid)
    api_url = f"{site['models_api']}?id={mid}"
    log(f"resolved '{args.model}' -> {mid} ({rec.get('display_name')}) by {how}; output {outs} -> page type {etype}")

    sources = ws / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    refreshed, failed = [], []

    ok, msg = run_snapshot(page_url, sources, "fact")
    if not ok:
        die(1, f"could not snapshot the model page {page_url}:\n{msg}")
    refreshed.append(page_url)
    pe = index_entry(sources, page_url, "fact")
    if not pe:
        die(1, f"snapshot.py reported success but {sources / 'index.json'} has no entry for {page_url}")
    try:
        html = (sources / pe["html"]).read_bytes().decode("utf-8", errors="replace")
        data_text, summ = zenmux_data.extract(html, page_url)
    except zenmux_data.PageShapeError as e:
        die(5, f"PAGE SHAPE NOT RECOGNISED for {page_url}: {e}\n[new_page] The page snapshot was saved; nothing else was written. "
               "ZenMux may have changed the page: report it, do not hand-patch numbers.")
    with tempfile.TemporaryDirectory() as td:
        f1 = Path(td) / "data.txt"
        f1.write_text(data_text, encoding="utf-8")
        ok, msg = run_snapshot(page_url, sources, "data", f1)
        if not ok:
            die(1, f"could not save the data snapshot:\n{msg}")
        api_text = api_record_text(rec)
        f2 = Path(td) / "api.txt"
        f2.write_text(api_text, encoding="utf-8")
        ok, msg = run_snapshot(api_url, sources, "data", f2)
        if not ok:
            die(1, f"could not save the API-record snapshot:\n{msg}")
    refreshed += [page_url + " (data)", api_url + " (data)"]

    if not args.skip_docs:
        docs = list(dict.fromkeys(site.get("shared_docs", []) + site.get("type_docs", {}).get(etype, [])))
        for u in docs:
            if is_fresh(sources, u, args.max_age_days):
                continue
            ok, msg = run_snapshot(u, sources, "fact")
            (refreshed if ok else failed).append(u if ok else f"{u}  ({msg.splitlines()[-1] if msg else 'failed'})")
        log(f"docs: {len(docs)} listed, {len([r for r in refreshed if r.startswith('https://zenmux.ai/docs') or r.startswith('https://docs.')])} (re-)snapshotted, {len(failed)} failed")

    # texts to quote from
    ptxt = (sources / pe["txt"]).read_text(encoding="utf-8")
    ae = index_entry(sources, api_url, "data")
    if not ae:
        die(1, f"snapshot.py reported success but {sources / 'index.json'} has no entry for {api_url}")
    hay = {page_url: data_text + "\n" + ptxt, api_url: (sources / ae["txt"]).read_text(encoding="utf-8"), "__visible__": ptxt}
    vis_ok = {}
    pdisc = str(summ["model"].get("pricing_discount") or "1")
    if Decimal(pdisc) != 1:
        pct = fmt_pct(Decimal(pdisc))
        vis_ok[pct] = pct in ptxt
    try:
        B, endpoints = build(rec, etype, summ, api_text, page_url, api_url, hay, date_s, vis_ok)
    except AssertionError as e:
        die(1, f"internal check failed (no files written): {e}")

    entity = strip_dev(rec.get("display_name") or summ["model"]["name"])
    names = [entity]
    for n in [summ["model"]["name"], rec.get("display_name"), slug, mid] + list(summ["model"].get("aliases") or []) + [p["name"] for p in summ["providers"] if p.get("name")]:
        if n and n not in names:
            names.append(n)
    out = {"entity": entity, "entity_type": etype, "checked_date": date_s, "names": names,
           "endpoints": endpoints, "facts": B.facts, "gaps": []}
    pdir = ws / "pages" / slug
    pdir.mkdir(parents=True, exist_ok=True)
    facts_path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (pdir / "gap-candidates.json").write_text(json.dumps(B.cands, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (pdir / "zenmux-data.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    cats = {}
    for f in B.facts:
        cats[f["category"]] = cats.get(f["category"], 0) + 1
    print()
    print(f"entity        {entity}  ({mid})")
    print(f"type          {etype}   (API output_modalities {outs})")
    print("providers     " + ", ".join(f"{e['id']} [{e['status']}]" for e in endpoints))
    print(f"facts written {len(B.facts)}  " + " ".join(f"{k}={v}" for k, v in sorted(cats.items())) + f"   -> {facts_path}")
    print(f"gap candidates {len(B.cands)}  -> {pdir / 'gap-candidates.json'}  (review; gaps[] left empty)")
    print(f"snapshots     {len(refreshed)} refreshed" + (f", {len(failed)} FAILED" if failed else ""))
    for f in failed:
        print(f"  WARNING doc snapshot failed: {f}")
    print(f"structured    {pdir / 'zenmux-data.json'}")
    print("next          write the developer-doc facts (served version, specs, limits, examples), then page.md")


if __name__ == "__main__":
    main()
