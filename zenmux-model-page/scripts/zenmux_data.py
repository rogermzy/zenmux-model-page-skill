#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zenmux_data.py — decode the Next.js flight data of a zenmux.ai model page

A ZenMux model page (https://zenmux.ai/<author>/<model>) is server-rendered by Next.js. The visible
HTML has only a rounded, flattened provider table. The exact per-provider data (fee items per
billing dimension, context, max output, supported parameters, the model's aliases) is only in the
flight data: <script>self.__next_f.push([1,"..."])</script> chunks.

Usage:
    python3 zenmux_data.py <snapshot.html> --url <page url> --out data.txt [--json summary.json]

  data.txt      readable text of VERBATIM fragments of the decoded flight data (nothing re-formatted),
                so a fact's quote can be an exact substring of it:
                  MODEL            the "initialModel":{...} block
                  PROVIDER <slug>  one provider object (up to, not including, the hourly
                                   cacheHite / Latency / Throughput series, which are noise)
                  FEE RECORDS ...  the provider's fee records (the decoded T-chunk that
                                   pricing_variable points at, or the inline JSON string)
                Snapshot it with: snapshot.py <page url> --dir sources --role data --from-file data.txt
  summary.json  the same data structured (model fields; per provider: slug, name, status, context,
                max output, protocols, fee items with code/name/rate/unit/conditions and the verbatim
                record text). Hourly latency/throughput series are dropped, not summarised.

Exit codes: 0 ok · 2 the page shape is not recognised (message says what was missing) · 1 bad usage.
A page that does not decode must stop the run: that is how a ZenMux page change gets noticed.

Flight format notes (checked against live pages):
  - rows are "<hex id>:<payload>\\n"; a text row is "<hex id>:T<hex byte length>,<text>" and the
    length counts UTF-8 BYTES (fee item names are Chinese), so the cut is made on bytes.
  - a provider's pricing_variable is either "$<id>" (a reference to such a T row) or, for some
    models, the fee-record JSON itself as an escaped string.
Stdlib only, Python 3.9+.
"""

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

NOISE_KEYS = ("cacheHite", "Latency", "Throughput")


class PageShapeError(Exception):
    """The page is not the shape this decoder knows. The message says what was missing."""


def fmt_decimal(x):
    """8 -> '8', 0.0000750000 -> '0.000075', 1.2000000000 -> '1.2' (never scientific notation)."""
    try:
        d = Decimal(str(x)).normalize()
    except InvalidOperation:
        return str(x)
    return format(d, "f")


# ── flight decoding ───────────────────────────────────────────────────────────────────────
def flight_text(html):
    parts = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    if not parts:
        raise PageShapeError("no self.__next_f.push([1,\"...\"]) script chunks in the HTML: this is not a Next.js "
                             "flight-data page (ZenMux may have changed its rendering, or the fetch returned an "
                             "error/blocked page)")
    try:
        return "".join(json.loads('"' + p + '"') for p in parts)
    except ValueError as e:
        raise PageShapeError(f"a flight-data chunk is not valid JSON-string text ({e})")


def t_chunk(flight_bytes, ref):
    """The text of flight row '<ref>:T<hexlen>,<text>'. hexlen counts UTF-8 bytes."""
    rid = re.escape(ref.encode())
    m = re.search(rb"(?:^|\n)" + rid + rb":T([0-9a-f]+),", flight_bytes) or \
        re.search(rb"(?<![0-9A-Za-z])" + rid + rb":T([0-9a-f]+),", flight_bytes)
    if not m:
        raise PageShapeError(f"pricing_variable points at flight row '{ref}' but no '{ref}:T<len>,' row exists")
    n = int(m.group(1), 16)
    raw = flight_bytes[m.end():m.end() + n]
    if len(raw) != n:
        raise PageShapeError(f"flight row '{ref}' announces {n} bytes but only {len(raw)} remain")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise PageShapeError(f"flight row '{ref}': the {n}-byte cut is not valid UTF-8 (length rule changed?)")


def raw_elements(text, start):
    """text[start] == '['. Returns ([(begin, end, obj)], end_of_array) for the array's elements."""
    dec = json.JSONDecoder()
    i, out = start + 1, []
    while True:
        while i < len(text) and text[i] in " \n\r\t,":
            i += 1
        if i >= len(text):
            raise PageShapeError("unterminated JSON array in flight data")
        if text[i] == "]":
            return out, i + 1
        obj, end = dec.raw_decode(text, i)
        out.append((i, end, obj))
        i = end


def _range(v):
    """'{"lowerLimit":"272","upperLimit":"1000000",...}' (string or dict) -> {'from','to','include_from','include_to'} or None."""
    try:
        v = json.loads(v) if isinstance(v, str) else v
        return {"from": int(float(v["lowerLimit"])), "to": int(float(v["upperLimit"])),
                "include_from": v.get("includeLowerLimit"), "include_to": v.get("includeUpperLimit")}
    except (ValueError, KeyError, TypeError):
        return None


def parse_conditions(comps):
    """Every component except chargeUnit is a pricing dimension: bizMinute / promptKToken / kTokens ... are
    ranges, bizDayOfWeek is a list, the rest (resolution, videoInput, quality, size, cacheType, imageGenModel)
    are plain values. Unknown codes are kept raw, never dropped."""
    cond = {}
    for code, val in comps.items():
        if code == "chargeUnit":
            continue
        if code == "bizDayOfWeek":
            try:
                v = json.loads(val) if isinstance(val, str) else val
                cond[code] = [int(d) for d in v]
            except (ValueError, TypeError):
                cond[code] = {"raw": val}
            continue
        rg = _range(val) if isinstance(val, (str, dict)) and "Limit" in str(val) else None
        cond[code] = rg if rg else val
    return cond


def parse_fee_records(text, who):
    """Fee-record JSON text -> list of items; each record carries raw text for quoting. Strict about shape."""
    try:
        recs, _ = raw_elements(text, text.index("["))
    except (ValueError, PageShapeError) as e:
        raise PageShapeError(f"{who}: fee records are not a JSON array ({e})")
    items = []
    for b, e, item in recs:
        if not isinstance(item, dict) or "feeItemCode" not in item or not isinstance(item.get("feeRecords"), list):
            raise PageShapeError(f"{who}: a fee item lacks feeItemCode / feeRecords "
                                 f"(keys: {sorted(item) if isinstance(item, dict) else type(item).__name__})")
        itext = text[b:e]
        rb = itext.index('"feeRecords":')
        relems, _ = raw_elements(itext, itext.index("[", rb))
        records = []
        for (rs, re_, rec) in relems:
            if not isinstance(rec, dict) or "feeRate" not in rec or not isinstance(rec.get("components"), list):
                raise PageShapeError(f"{who}: fee item '{item['feeItemCode']}' has a record without feeRate/components")
            comps = {}
            for c in rec["components"]:
                if not isinstance(c, dict) or "code" not in c or "value" not in c:
                    raise PageShapeError(f"{who}: fee item '{item['feeItemCode']}' has a component without code/value")
                comps[c["code"]] = c["value"]
            records.append({"rate": rec["feeRate"], "rate_text": fmt_decimal(rec["feeRate"]),
                            "unit": comps.get("chargeUnit"), "conditions": parse_conditions(comps),
                            "raw": itext[rs:re_]})
        # a single-record item is quoted whole (code + name + rate + conditions); multi-record items per record
        for r in records:
            r["quote"] = itext if len(records) == 1 else r["raw"]
        items.append({"code": item["feeItemCode"], "name": item.get("feeItemName"),
                      "selected_constraint": item.get("selectedConstraint"), "records": records})
    return items


# ── page extraction ───────────────────────────────────────────────────────────────────────
def extract(html, url=None):
    """Returns (data_text, summary dict). Raises PageShapeError."""
    fl = flight_text(html)
    fb = fl.encode("utf-8")
    markers = ('"initialModel":', '"initialProviders":', '"initialRelatedModels"')
    missing = [k for k in markers if k not in fl]
    if missing:
        raise PageShapeError(f"flight data has no {', '.join(missing)} marker: not a ZenMux model page of the known shape")
    im, ip, ir = (fl.index(k) for k in markers)
    if not im < ip < ir:
        raise PageShapeError("flight markers initialModel / initialProviders / initialRelatedModels are not in the known order")
    model_raw = fl[im:ip].rstrip().rstrip(",")
    try:
        model = json.loads(model_raw[len('"initialModel":'):])
    except ValueError as e:
        raise PageShapeError(f"the initialModel block is not a JSON object ({e})")
    for k in ("slug", "name", "output_modalities"):
        if k not in model:
            raise PageShapeError(f"initialModel has no '{k}' (keys: {sorted(model)})")
    if url:
        path = urlsplit(url).path.strip("/")
        if path and path != model["slug"]:
            raise PageShapeError(f"URL path '{path}' != model slug '{model['slug']}' in the page data (redirect or wrong file?)")

    try:
        pelems, _ = raw_elements(fl, fl.index("[", ip))
    except (PageShapeError, ValueError) as e:
        raise PageShapeError(f"initialProviders is not a JSON array ({e})")
    if not pelems:
        raise PageShapeError("initialProviders is empty: the page lists no providers")

    out = [f"ZenMux page data for {url or model['slug']} (decoded from the Next.js flight data)",
           "Verbatim JSON fragments. Hourly cacheHite / Latency / Throughput series are omitted; a provider "
           "fragment therefore stops before them.", "", "MODEL", model_raw, ""]
    providers = []
    for (b, e, p) in pelems:
        if not isinstance(p, dict) or not p.get("provider_slug"):
            raise PageShapeError("a provider object lacks provider_slug "
                                 f"(keys: {sorted(p) if isinstance(p, dict) else type(p).__name__})")
        slug = p["provider_slug"]
        ptxt = fl[b:e]
        cut = min([i for i in (ptxt.find(',"' + k + '":') for k in NOISE_KEYS) if i >= 0] or [len(ptxt)])
        frag = ptxt[:cut]
        pv = p.get("pricing_variable")
        who = f"provider '{slug}'"
        if isinstance(pv, str) and pv.startswith("$") and re.fullmatch(r"[0-9a-f]+", pv[1:]):
            fee_text, where = t_chunk(fb, pv[1:]), f"pricing_variable {pv} -> flight row {pv[1:]}"
        elif isinstance(pv, str) and pv.lstrip().startswith("["):
            fee_text, where = pv, "pricing_variable is inline JSON"
        else:
            raise PageShapeError(f"{who}: pricing_variable is {str(pv)[:40]!r}: neither a $<id> reference nor inline fee JSON")
        items = parse_fee_records(fee_text, who)
        out += [f"PROVIDER {slug}", frag, "", f"FEE RECORDS for provider {slug} ({where})", fee_text, ""]
        apis = {api: {"supported_parameters": d.get("supported_parameters", []), "supports_reasoning": d.get("supports_reasoning")}
                for api, d in (p.get("api_protocols") or {}).items()}
        providers.append({
            "slug": slug, "name": p.get("provider"), "visible": p.get("visible"),
            "status": "active" if p.get("visible") == 1 else "disabled",
            "status_basis": ("visible=1" if p.get("visible") == 1 else
                             f"visible={p.get('visible')!r}: for 2 the page shows a 'Sunset' badge next to the provider name; "
                             "treated as disabled until ZenMux says what Sunset means"),
            "context_length": p.get("context_length"), "max_completion_tokens": p.get("max_completion_tokens"),
            "supports_streaming": p.get("supports_streaming"), "pricing_discount": p.get("pricing_discount"),
            "suitable_api": [a for a in str(p.get("suitable_api") or "").split(",") if a],
            "api_protocols": apis, "pricing_variable": pv if where.startswith("pricing_variable $") else "(inline)",
            "fee_items": items, "fragment": frag,
        })

    def csv(v):
        return [x for x in str(v or "").split(",") if x]

    summary = {
        "url": url, "decoded_from": "Next.js flight data (self.__next_f.push)",
        "model": {"slug": model["slug"], "name": model["name"], "author": model.get("author"),
                  "author_name": model.get("authorName"), "description": model.get("description"),
                  "context_length": model.get("context_length"), "publish_time": model.get("publish_time"),
                  "input_modalities": csv(model.get("input_modalities")),
                  "output_modalities": csv(model.get("output_modalities")),
                  "aliases": model.get("aliases"), "pricing_discount": model.get("pricing_discount"),
                  "visible": model.get("visible"), "faq_count": len(model.get("faqs") or []), "raw": model_raw},
        "providers": providers,
        "dropped": list(NOISE_KEYS),
    }
    return "\n".join(out) + "\n", summary


def main():
    ap = argparse.ArgumentParser(description="Decode the Next.js flight data of a zenmux.ai model page")
    ap.add_argument("html", help="saved page HTML (snapshot.py writes it to sources/*.html)")
    ap.add_argument("--url", help="the page URL (checked against the model slug in the data)")
    ap.add_argument("--out", required=True, help="write the readable verbatim-fragment text here")
    ap.add_argument("--json", help="also write the structured summary here")
    args = ap.parse_args()
    src = Path(args.html)
    if not src.is_file():
        print(f"[zenmux_data] ERROR {src} not found", file=sys.stderr)
        sys.exit(1)
    try:
        text, summary = extract(src.read_bytes().decode("utf-8", errors="replace"), args.url)
    except PageShapeError as e:
        print(f"[zenmux_data] PAGE SHAPE NOT RECOGNISED: {e}", file=sys.stderr)
        print("[zenmux_data] The ZenMux model page may have changed; tell the site owner / fix this decoder. "
              "Nothing was written.", file=sys.stderr)
        sys.exit(2)
    Path(args.out).write_text(text, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = sum(len(i["records"]) for p in summary["providers"] for i in p["fee_items"])
    print(f"[zenmux_data] {summary['model']['slug']}: {len(summary['providers'])} providers, {n} fee records -> {args.out}")


if __name__ == "__main__":
    main()
