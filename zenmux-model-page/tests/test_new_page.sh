#!/usr/bin/env bash
# Tests for scripts/zenmux_data.py and scripts/new_page.py. No internet: the pages are saved/synthetic
# fixtures (tests/fixtures/zenmux-site, regenerate with mk_fixtures.py) served from 127.0.0.1.
# Usage: bash tests/test_new_page.sh
set -u
PY="${PYTHON:-python3}"
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../scripts"
FX="$HERE/fixtures/zenmux-site"
W="$(mktemp -d)"
PASS=0; FAIL=0
SRV=""
cleanup() { [ -n "$SRV" ] && { kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; }; rm -rf "$W"; }
trap cleanup EXIT

ok()  { PASS=$((PASS+1)); echo "  ok   $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL $1 -- $2"; }

# expect NAME EXIT PATTERN|- <command...>
expect() {
  local name="$1" want="$2" pat="$3"; shift 3
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" != "$want" ]; then bad "$name" "exit $rc, wanted $want"; echo "$out" | sed 's/^/       /'; return; fi
  if [ "$pat" != "-" ] && ! echo "$out" | grep -q -- "$pat"; then bad "$name" "pattern '$pat' not in output"; echo "$out" | sed 's/^/       /'; return; fi
  ok "$name"
}
# pyt NAME <<'PY' ... PY   (python assertions; env: W FX S; exit 0 = pass)
pyt() {
  local name="$1" out
  out="$(W="$W" FX="$FX" S="$S" "$PY" - 2>&1)" && ok "$name" || { bad "$name" "assertion failed"; echo "$out" | sed 's/^/       /'; }
}

echo "zenmux_data.py"
D="$W/d"; mkdir -p "$D"
expect "decode text page (tiers, CJK chunk, inline-JSON provider)" 0 "2 providers, 9 fee records" \
  "$PY" "$S/zenmux_data.py" "$FX/www/acme/tiered-text" --url https://zenmux.ai/acme/tiered-text --out "$D/t.txt" --json "$D/t.json"
expect "decode video page (per-second items)" 0 "1 providers, 3 fee records" \
  "$PY" "$S/zenmux_data.py" "$FX/www/acme/clip-2" --url https://zenmux.ai/acme/clip-2 --out "$D/v.txt" --json "$D/v.json"

D="$D" pyt "data.txt is verbatim, noise-free, CJK intact" <<'PY'
import os
t = open(os.environ["D"] + "/t.txt", encoding="utf-8").read()
assert "FEE RECORDS for provider alpha (pricing_variable $2f -> flight row 2f)" in t, "T-chunk ref not resolved"
assert "输入提示词的处理费用(prompt)" in t, "CJK text lost (UTF-8 byte-length cut)"
assert "pricing_variable is inline JSON" in t, "inline pricing_variable not handled"
assert "Latency" not in t.replace("cacheHite / Latency / Throughput", "") and "biz_hour" not in t, "hourly series leaked"
assert '"initialModel":{"name":"Acme: Tiered Text 1.0"' in t
# the last fee item of the $ref chunk must be complete (a char-count cut would truncate it)
assert '"value":"counts"}]}]}]' in t, "chunk cut short"
PY
D="$D" pyt "summary: status, units, conditions, tiers" <<'PY'
import json, os
s = json.load(open(os.environ["D"] + "/t.json", encoding="utf-8"))
v = json.load(open(os.environ["D"] + "/v.json", encoding="utf-8"))
P = {p["slug"]: p for p in s["providers"]}
assert P["alpha"]["status"] == "active" and P["beta"]["status"] == "disabled", "visible=2 must not be active"
assert P["alpha"]["context_length"] == 1000000 and P["alpha"]["max_completion_tokens"] == 384000
item = {i["code"]: i for i in P["alpha"]["fee_items"]}
assert [r["rate_text"] for r in item["prompt"]["records"]] == ["0.2", "0.4"]
assert item["prompt"]["records"][1]["conditions"]["bizMinute"]["from"] == 840
assert item["web_search"]["records"][0]["unit"] == "counts"
assert "feeRate" in item["prompt"]["records"][0]["raw"]
beta = {i["code"]: i for i in P["beta"]["fee_items"]}
assert beta["completion"]["records"][1]["conditions"]["promptKToken"]["from"] == 272, beta
assert s["model"]["aliases"] == ["tiered-text", "acme-tt"] and s["model"]["output_modalities"] == ["text"]
r = v["providers"][0]["fee_items"][0]["records"]
assert r[0]["unit"] == "seconds" and r[0]["conditions"] == {"resolution": "720p"} and r[0]["rate_text"] == "0.084", r
PY

expect "page without flight data is refused loudly" 2 "PAGE SHAPE NOT RECOGNISED" \
  "$PY" "$S/zenmux_data.py" "$FX/www/acme/no-flight" --out "$W/x.txt"
expect "renamed marker is refused and named" 2 "initialProviders" \
  "$PY" "$S/zenmux_data.py" "$FX/www/acme/renamed-markers" --out "$W/x.txt"
expect "URL that disagrees with the page's model slug is refused" 2 "!= model slug" \
  "$PY" "$S/zenmux_data.py" "$FX/www/acme/clip-2" --url https://zenmux.ai/acme/other --out "$W/x.txt"
[ ! -e "$W/x.txt" ] && ok "nothing written on a refused page" || bad "nothing written on a refused page" "x.txt exists"

echo "new_page.py: resolve + type gate (no network, nothing written)"
NP() { "$PY" "$S/new_page.py" "$@" --api-json "$FX/models-api.json" --skip-docs; }
for q in "acme/listen-1|transcription" "Acme: Embed 1|embeddings" "acme/mystery|unknown"; do
  expect "type gate: ${q%%|*}" 3 "no page template for model type ${q##*|}.*; the approved plan covers text, image, video, audio" NP "$W/ws-gate" "${q%%|*}"
done
[ ! -e "$W/ws-gate" ] && ok "type gate wrote nothing" || bad "type gate wrote nothing" "workspace created"
expect "ambiguous name lists candidates" 2 "other/twin" NP "$W/ws-gate" "twin"
expect "unknown model" 2 "no model matches" NP "$W/ws-gate" "no such model"

echo "new_page.py: full run against the fixture site"
PORT="$("$PY" -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')"
"$PY" -m http.server "$PORT" --bind 127.0.0.1 --directory "$FX/www" >/dev/null 2>&1 &
SRV=$!
for _ in $(seq 1 50); do curl -s -o /dev/null "http://127.0.0.1:$PORT/acme/clip-2" && break; sleep 0.1; done
cat > "$W/site.json" <<JSON
{"models_api": "http://127.0.0.1:$PORT/api/v1/models", "page_url_template": "http://127.0.0.1:$PORT/{id}",
 "sitemap": "http://127.0.0.1:$PORT/sitemap-models.xml"}
JSON
WS="$W/ws"
expect "text page (display name, case/space-insensitive)" 0 "type          text" NP "$WS" "ACME:  tiered text 1.0" --site-config "$W/site.json" --date 2026-11-01
expect "video page by URL" 0 "type          video" NP "$WS" "https://zenmux.ai/acme/clip-2" --site-config "$W/site.json" --date 2026-11-01
expect "refuses to overwrite facts.json" 4 "already exists" NP "$WS" acme/clip-2 --site-config "$W/site.json"
expect "--force overwrites" 0 "facts written" NP "$WS" acme/clip-2 --site-config "$W/site.json" --force

WS="$WS" S="$S" pyt "starter validates against check_page and every quote is in its snapshot" <<'PY'
import json, os, re, sys
sys.path.insert(0, os.environ["S"])
import check_page
ws = os.environ["WS"]
idx = json.load(open(ws + "/sources/index.json", encoding="utf-8"))
norm = lambda s: " ".join(s.split())
def text_of(url):
    return norm(" ".join(open(ws + "/sources/" + e["txt"], encoding="utf-8").read() for e in idx if e["url"] == url))
for slug in ("tiered-text", "clip-2"):
    d = json.load(open(f"{ws}/pages/{slug}/facts.json", encoding="utf-8"))
    errs = []
    E = lambda code, msg, line=None: errs.append((code, msg))
    assert check_page.validate_facts(d, E), errs
    check_page.validate_gaps(d["gaps"], E)
    assert not errs, errs
    assert d["gaps"] == [], "gaps[] must stay empty"
    assert all(f["verdict"] == "UNCHECKED" for f in d["facts"])
    for f in d["facts"]:
        assert norm(f["quote"]) in text_of(f["source_url"]), (f["id"], f["quote"][:60])
    cands = json.load(open(f"{ws}/pages/{slug}/gap-candidates.json", encoding="utf-8"))
    for c in cands:
        assert all(norm(e["quote"]) in text_of(e["source_url"]) for e in c["evidence"]), c["field"]
    assert not any(f.get("value") == 0 for f in d["facts"]), "a zero value became a fact"
    globals()[slug.replace("-", "_")] = (d, cands)

d, cands = tiered_text
F = {f["id"]: f for f in d["facts"]}
assert d["entity"] == "Tiered Text 1.0" and d["entity_type"] == "text" and d["checked_date"] == "2026-11-01"
assert {e["id"]: e["status"] for e in d["endpoints"]} == {"alpha": "active", "beta": "disabled"}
assert F["price.alpha.web_search"]["display"] == "$0.01" and F["price.alpha.web_search"]["unit"] == "USD / count"
assert F["price.alpha.prompt.m0-840"]["display"] == "$0.2" and "Fee item prompt" in F["price.alpha.prompt.m0-840"]["label"]
assert F["price.alpha.prompt.discounted.m0-840"]["display"] == "$0.1", "discounted price from the page text"
assert F["price.alpha.completion.discounted"]["display"] == "$0.4"
assert F["price.alpha.input_cache_read.discounted.m840-1440"]["display"] == "$0.02"
assert "price.alpha.web_search.discounted" not in F, "web_search discount is not in the page text: no fact"
assert F["discount.zenmux"]["display"] == "50% OFF"
assert F["spec.alpha.context"]["display"] == "1M" and "1,000,000" in F["spec.alpha.context"]["aliases"]
assert F["spec.beta.context"]["display"] == "128K"
assert "spec.beta.maxout" not in F, "max output 0 must not become a fact"
fields = {(c["field"], c["endpoint"]) for c in cands}
assert ("max_completion_tokens", "beta") in fields and ("provider status", "beta") in fields, fields
assert any(c["field"] == "fee completion" and c["endpoint"] == "beta" and c["found"] == "0" for c in cands), "zero-rate tier"
assert any(c["field"] == "discounted price" and c["endpoint"] == "alpha" for c in cands)

d, cands = clip_2
F = {f["id"]: f for f in d["facts"]}
assert d["entity_type"] == "video"
assert F["price.acme-video.video.720p"]["display"] == "$0.084" and F["price.acme-video.video.720p"]["unit"] == "USD / second"
assert "resolution 1080p" in F["price.acme-video.video.1080p"]["condition"]
assert not any(".discounted" in i for i in F) and "discount.zenmux" not in F
assert any(c["field"] == "max_completion_tokens" for c in cands) and any(c["field"] == "aliases" for c in cands)
PY

WS="$WS" pyt "snapshots recorded: page (fact), flight data (data), API record (data)" <<'PY'
import json, os
idx = json.load(open(os.environ["WS"] + "/sources/index.json", encoding="utf-8"))
roles = {(e["url"].split("/", 3)[-1], e["role"]) for e in idx}
assert ("acme/tiered-text", "fact") in roles and ("acme/tiered-text", "data") in roles, roles
assert any(e["role"] == "data" and "api/v1/models?id=acme/clip-2" in e["url"] for e in idx), roles
PY

echo "new_page.py: --no-api (sitemap + page data) and the automatic fallback"
NA() { "$PY" "$S/new_page.py" "$@" --site-config "$W/site.json" --skip-docs --date 2026-11-01; }
expect "--no-api, by name (slug, case/space/punctuation-insensitive)" 0 "resolved via: sitemap + page data (no API)" NA "$W/ws-na" "TIERED  text" --no-api
expect "--no-api, by developer-prefixed name" 0 "type          video" NA "$W/ws-na" "Acme: Clip 2" --no-api
expect "--no-api, by id" 0 "type          video" NA "$W/ws-na" acme/clip-2 --no-api --force
expect "--no-api, by URL" 0 "type          video" NA "$W/ws-na" https://zenmux.ai/acme/clip-2 --no-api --force
expect "--no-api: facts.json exists is still exit 4" 4 "already exists" NA "$W/ws-na" acme/clip-2 --no-api
expect "--no-api names the skipped API checks" 0 "API vs page price cross-check" NA "$W/ws-na" acme/clip-2 --no-api --force
expect "--no-api, ambiguous name lists candidates" 2 "other/twin" NA "$W/ws-na2" twin --no-api
expect "--no-api, no sitemap match" 2 "no model URL in the sitemap matches" NA "$W/ws-na2" "no such model" --no-api
expect "--no-api, provider page is not a model (sitemap skips /provider/)" 2 "no model URL in the sitemap matches" NA "$W/ws-na2" "acme" --no-api
expect "--no-api, provider URL refused" 2 "not a model page URL" NA "$W/ws-na2" https://zenmux.ai/provider/acme --no-api
expect "--no-api, unsupported type from the page data" 3 "no page template for model type transcription.*approved plan covers" NA "$W/ws-na2" acme/listen-1 --no-api
expect "--no-api and --api-json together" 1 "contradict" NA "$W/ws-na2" acme/clip-2 --no-api --api-json "$FX/models-api.json"
[ ! -e "$W/ws-na2/pages" ] && ok "refused --no-api runs wrote no pages/" || bad "refused --no-api runs wrote no pages/" "pages/ exists"

DEADPORT="$("$PY" -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')"   # bound then released: nothing listens
cat > "$W/site-dead.json" <<JSON
{"models_api": "http://127.0.0.1:$DEADPORT/api/v1/models", "page_url_template": "http://127.0.0.1:$PORT/{id}",
 "sitemap": "http://127.0.0.1:$PORT/sitemap-models.xml"}
JSON
expect "API unreachable -> automatic fallback, says so" 0 "NOTICE the models API is unavailable.*WITHOUT it" \
  "$PY" "$S/new_page.py" "$W/ws-fb" "Tiered Text" --site-config "$W/site-dead.json" --skip-docs --date 2026-11-01
expect "fallback summary states the mode" 0 "resolved via: sitemap + page data (no API)" \
  "$PY" "$S/new_page.py" "$W/ws-fb" "Tiered Text" --site-config "$W/site-dead.json" --skip-docs --date 2026-11-01 --force
expect "API answers but does not know the model -> exit 2, no fallback" 2 "no model matches" \
  "$PY" "$S/new_page.py" "$W/ws-live" "no such model" --site-config "$W/site.json" --skip-docs
[ ! -e "$W/ws-live" ] && ok "API not-found wrote nothing" || bad "API not-found wrote nothing" "workspace created"
expect "live (served) API still used when it works" 0 "resolved via: models API" \
  "$PY" "$S/new_page.py" "$W/ws-live" "Acme: Clip 2" --site-config "$W/site.json" --skip-docs --date 2026-11-01

W="$W" S="$S" pyt "no-API facts.json: quotes verified, equal to the API run, API-only facts absent" <<'PY'
import json, os, sys
sys.path.insert(0, os.environ["S"])
import check_page
W = os.environ["W"]
norm = lambda s: " ".join(s.split())
def load(ws, slug):
    idx = json.load(open(f"{ws}/sources/index.json", encoding="utf-8"))
    def text_of(url):
        return norm(" ".join(open(f"{ws}/sources/" + e["txt"], encoding="utf-8").read() for e in idx if e["url"] == url))
    d = json.load(open(f"{ws}/pages/{slug}/facts.json", encoding="utf-8"))
    errs = []
    E = lambda code, msg, line=None: errs.append((code, msg))
    assert check_page.validate_facts(d, E) and not errs, errs
    for f in d["facts"]:
        assert norm(f["quote"]) in text_of(f["source_url"]), (ws, f["id"], f["quote"][:60])
    return d, idx
for slug, ws_na, ws_api in (("tiered-text", "ws-na", "ws"), ("clip-2", "ws-na", "ws")):
    na, idx = load(f"{W}/{ws_na}", slug)
    api, _ = load(f"{W}/{ws_api}", slug)
    assert na["gaps"] == [] and all(f["verdict"] == "UNCHECKED" for f in na["facts"])
    A = {f["id"]: f for f in api["facts"]}; N = {f["id"]: f for f in na["facts"]}
    assert not [i for i in N if i.endswith(".api")], "API-derived fact in no-API mode"
    assert set(N) == {i for i in A if not i.endswith(".api")}, sorted(set(N) ^ set(A))
    for i in N:
        assert N[i]["display"] == A[i]["display"] and N[i]["source_url"].split("/", 3)[-1] == A[i]["source_url"].split("/", 3)[-1], i
    assert na["entity"] == api["entity"] and na["entity_type"] == api["entity_type"]
    assert not any("api/v1/models" in e["url"] for e in idx), "an API snapshot was written in no-API mode"
roles = {(e["url"].rsplit("/", 1)[-1], e["role"]) for e in idx}
assert ("sitemap-models.xml", "data") in roles, roles   # the resolution is auditable
fb, _ = load(f"{W}/ws-fb", "tiered-text")
assert fb["entity"] == "Tiered Text 1.0" and fb["entity_type"] == "text"
PY

echo
echo "passed $PASS, failed $FAIL"
[ "$FAIL" = 0 ]
