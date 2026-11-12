#!/usr/bin/env bash
# Golden regression for page-revamp scripts. Asserts exit code AND that the expected rule code
# appears in the output, so a check that silently stops firing fails the suite.
# Usage: bash tests/run_tests.sh      (no internet needed; snapshot fetch tests use 127.0.0.1)
set -u
PY="${PYTHON:-python3}"
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../scripts"
FX="$HERE/fixtures"
W="$(mktemp -d)"
PASS=0; FAIL=0
SRV=""
cleanup() { [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; rm -rf "$W"; }
trap cleanup EXIT

ok()  { PASS=$((PASS+1)); echo "  ok   $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL $1 -- $2"; }

# expect NAME EXIT CODE|- <command...>   (CODE "-" = no code assertion; "!CODE" = must be absent)
expect() {
  local name="$1" want="$2" code="$3"; shift 3
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  if [ "$rc" != "$want" ]; then bad "$name" "exit $rc, wanted $want"; echo "$out" | sed 's/^/       /'; return; fi
  case "$code" in
    -)  ok "$name" ;;
    !*) if echo "$out" | grep -q "${code#!}"; then bad "$name" "unexpected ${code#!}"; else ok "$name"; fi ;;
    *)  if echo "$out" | grep -q "$code"; then ok "$name"; else bad "$name" "code $code not in output"; echo "$out" | sed 's/^/       /'; fi ;;
  esac
}

# mutation helpers: fail loudly if the text to change is not there (no silent no-op tests)
mut() {  # mut FILE OLD NEW  (first occurrence)
  "$PY" - "$@" <<'PY' || { echo "  FAIL mutation target missing: $2" ; FAIL=$((FAIL+1)); }
import sys
f, old, new = sys.argv[1:4]
s = open(f, encoding="utf-8").read()
if old not in s: sys.exit(1)
open(f, "w", encoding="utf-8").write(s.replace(old, new, 1))
PY
}
jmut() {  # jmut FILE 'python statement on d'
  "$PY" - "$1" "$2" <<'PY'
import json, sys
f, stmt = sys.argv[1:3]
d = json.load(open(f, encoding="utf-8"))
exec(stmt)
json.dump(d, open(f, "w", encoding="utf-8"), indent=1)
PY
}
newpage() { mkdir -p "$W/$1"; cp "$FX/good/page.md" "$FX/good/facts.json" "$W/$1/"; }
newplan() { cp "$FX/plan.md" "$W/$1.md"; }
page() { "$PY" "$S/check_page.py" "$W/$1/page.md" --plan "${2:-$FX/plan.md}" --no-lint "${@:3}"; }   # lint is on by default: the contract tests opt out
pagel() { "$PY" "$S/check_page.py" "$W/$1/page.md" --plan "${2:-$FX/plan.md}" "${@:3}"; }          # lint on (default)
# mkaccept DIR FIXTURE  -> $W/DIR/acceptance.json with the current page.md hash substituted
mkaccept() { "$PY" - "$W/$1" "$FX/acceptance/$2.json" <<'PYA'
import hashlib, sys
d, f = sys.argv[1:3]
sha = hashlib.sha256(open(d + "/page.md", "rb").read()).hexdigest()
open(d + "/acceptance.json", "w", encoding="utf-8").write(open(f, encoding="utf-8").read().replace("@SHA@", sha))
PYA
}
# mkreview DIR FIXTURE  -> $W/DIR/review.json with the current page.md hash substituted
mkreview() { "$PY" - "$W/$1" "$FX/review/$2.json" <<'PYR'
import hashlib, sys
d, f = sys.argv[1:3]
sha = hashlib.sha256(open(d + "/page.md", "rb").read()).hexdigest()
open(d + "/review.json", "w", encoding="utf-8").write(open(f, encoding="utf-8").read().replace("@SHA@", sha))
PYR
}
plan() { "$PY" "$S/check_plan.py" "$W/$1.md" "${@:2}"; }

echo "== --help =="
for s in snapshot check_plan check_page site_fixes; do expect "$s --help" 0 usage "$PY" "$S/$s.py" --help; done

echo "== check_plan =="
expect "plan: valid (+sources, no warnings)" 0 "!WARN" "$PY" "$S/check_plan.py" "$FX/plan.md" --sources "$FX/sources/index.json"
expect "plan: draft plan is still a valid plan" 0 PASS "$PY" "$S/check_plan.py" "$FX/plan-draft.md"
"$PY" "$S/check_plan.py" "$FX/plan.md" --json "$W/plan.check.json" >/dev/null
"$PY" -c "import json;d=json.load(open('$W/plan.check.json'));assert d['modules']==['M1','M2','M3','M4','M5'] and d['errors']==[]" && ok "plan: --json report" || bad "plan: --json report" "bad json"

c() { newplan "$1"; }
c p1; mut $W/p1.md 'status: approved ' 'status: maybe '; expect "plan: bad status" 1 PLAN_BAD_STATUS plan p1
c p2; mut $W/p2.md 'approved_by: Test Human' 'approved_by:'; expect "plan: approved w/o approved_by" 1 PLAN_APPROVAL_INCOMPLETE plan p2
c p3; tail -n +2 $W/p3.md > $W/p3b.md; mv $W/p3b.md $W/p3.md; expect "plan: no front matter" 1 PLAN_NO_FRONT_MATTER plan p3
c p4; mut $W/p4.md 'sample_url: https://example.test/acme/acme-model-7-5' ''; expect "plan: missing sample_url" 1 PLAN_MISSING_KEY plan p4
c p5; mut $W/p5.md '# 4. 开发实施与验收' '# 开发'; expect "plan: missing # 4. heading" 1 PLAN_MISSING_HEADING plan p5
c p6; mut $W/p6.md '```json page-template' '```json'; expect "plan: no json page-template block" 1 PLAN_NO_SPEC_BLOCK plan p6
c p7; mut $W/p7.md '"page_language": "en",' '"page_language": "en" "oops",'; expect "plan: spec JSON broken" 1 PLAN_SPEC_JSON plan p7
c p8; mut $W/p8.md '## **M3 能力：能做什么**' '## **能力：能做什么**'; expect "plan: part 3 missing M3 heading" 1 PLAN_PART3_MODULE_HEADING plan p8
c p9; mut $W/p9.md '## **M4–M5 性能与 FAQ**' '## **M4–M6 性能与 FAQ**'; expect "plan: part 3 mentions module not in spec" 1 PLAN_PART3_UNKNOWN_MODULE plan p9
c p10; mut $W/p10.md '"id": "M2", "name": "Pricing", "required": true, "h2": "{Entity} Pricing"' '"id": "M2", "name": "Pricing", "required": true, "h2": null'; expect "plan: h2 null on non-M1" 1 SPEC_H2_NULL plan p10
c p11; mut $W/p11.md '"h2": "{Entity} Pricing"' '"h2": ""'; expect "plan: h2 empty string" 1 SPEC_H2_VALUE plan p11
c p12; expect "plan: generic h2 without {Entity} is allowed (M5)" 0 "!SPEC_H2" plan p12
c p13; mut $W/p13.md '"template_id": "acme-model-page"' '"template_id": "other-page"'; expect "plan: template_id != plan_slug" 1 SPEC_TEMPLATE_ID_MISMATCH plan p13
c p14; mut $W/p14.md '"template_id": "acme-model-page"' '"template_id": "Acme_Page"'; expect "plan: template_id not kebab" 1 SPEC_TEMPLATE_ID plan p14
c p15; mut $W/p15.md '"h1_pattern": "{Entity} API"' '"h1_pattern": "API"'; expect "plan: h1 pattern lacks {Entity}" 1 SPEC_H1_PATTERN plan p15
c p16; mut $W/p16.md '"id": "M3"' '"id": "M7"'; expect "plan: module ids not consecutive" 1 SPEC_MODULE_ID plan p16
c p17; mut $W/p17.md '"show_if": "category:performance"' '"show_if": "whenever"'; expect "plan: bad show_if" 1 SPEC_SHOW_IF_FORMAT plan p17
c p18; mut $W/p18.md '"show_if": "category:performance"' '"show_if": null'; expect "plan: conditional without show_if" 1 SPEC_SHOW_IF_MISSING plan p18
c p19; mut $W/p19.md '"derived_from": ["M2", "M3"]' '"derived_from": ["M2", "M6"]'; expect "plan: derived_from unknown" 1 SPEC_DERIVED_FROM plan p19
c p20; mut $W/p20.md '"required": true, "h2": null' '"required": "yes", "h2": null'; expect "plan: required not boolean" 1 SPEC_REQUIRED_TYPE plan p20
c p21; mut $W/p21.md '"missing_value_labels": {"price": "Not published", "version": "Not verified", "metric": "No data"},' ''; expect "plan: missing_value_labels absent" 1 SPEC_MISSING_LABELS plan p21
c p22; mut $W/p22.md '"status_vocabulary": ["Supported", "Not supported", "Not verified", "Varies by provider"],' ''; expect "plan: status_vocabulary absent" 1 SPEC_STATUS_VOCAB plan p22
c p23; mut $W/p23.md '| [Rival B · Model](https://rival-b.example.test/models/y) | 能力状态表 | M3；不抄文案 |' ''; expect "plan: part 1 < 2 rows" 1 PLAN_PART1_ROWS plan p23
c p24; mut $W/p24.md '[Rival B · Model](https://rival-b.example.test/models/y)' 'Rival B'; expect "plan: part 1 row without URL" 1 PLAN_PART1_URL plan p24
c p25; mut $W/p25.md '| 能力只有图标 | 图标无文字 | M3 改为文字状态表 |' ''; expect "plan: part 2 no data row" 1 PLAN_PART2_TABLE plan p25
c p26; mut $W/p26.md 'https://rival-a.example.test/models/x' 'https://rival-a.example.test/other'; expect "plan: URL w/o snapshot warns" 0 WARN_NO_SNAPSHOT plan p26 --sources "$FX/sources/index.json"
c p27; mut $W/p27.md '⚡ MEDIUM' 'MEDIUM'; expect "plan: legend warns" 0 WARN_NO_PRIORITY_LEGEND plan p27
c p28; mut $W/p28.md 'checked_date: 2026-01-15' 'checked_date: Jan 15'; expect "plan: checked_date warns" 0 WARN_CHECKED_DATE plan p28

echo "== check_page =="
newpage g; expect "page: valid (UNCHECKED fact warns)" 0 WARN_UNCHECKED_FACTS page g
page g "$FX/plan.md" --json "$W/page.check.json" >/dev/null
"$PY" -c "import json;d=json.load(open('$W/page.check.json'));assert d['modules']=={'M1':'shown','M2':'shown','M3':'shown','M4':'hidden','M5':'shown'} and d['numbers_checked']>0 and d['entity']=='Acme Model 7.5'" && ok "page: --json report" || bad "page: --json report" "bad json"

newpage t1; mut $W/t1/page.md '| Other Cloud | $3.33 |' '| Other Cloud | $3.34 |'; expect "page: untraced number" 1 UNTRACED_NUMBER page t1
newpage t2; jmut $W/t2/facts.json 'd["names"]=[]'; expect "page: name digits flagged when not in names (proves name strip)" 1 UNTRACED_NUMBER page t2
expect "page: number inside model name not flagged" 0 '!UNTRACED_NUMBER' page g
newpage t3; jmut $W/t3/facts.json 'd["facts"][1]["verdict"]="REFUTED"'; expect "page: REFUTED fact used" 1 REFUTED_FACT_USED page t3
newpage t4; mut $W/t4/page.md '<!-- module: M3 shown -->' '<!-- module: M3 hidden: nope -->'; expect "page: required module hidden" 1 REQUIRED_HIDDEN page t4
newpage t5; mut $W/t5/page.md '<!-- module: M4 hidden: no performance samples in facts.json; gap: perf-none -->' $'<!-- module: M4 shown -->\n## Acme Model 7.5 Performance\n\nNothing here.'; expect "page: conditional shown without facts" 1 COND_SHOWN_NO_FACTS page t5
newpage t5b; mut $W/t5b/page.md '<!-- module: M4 hidden: no performance samples in facts.json; gap: perf-none -->' $'<!-- module: M4 shown -->\n## Acme Model 7.5 Performance\n\nTTFT is 12 ms.'
jmut $W/t5b/facts.json 'd["facts"].append({"id":"perf.ttft","category":"performance","endpoint":"acme","label":"TTFT","display":"12 ms","source_url":"https://example.test/acme/acme-model-7-5","quote":"TTFT 12 ms","checked_at":"2026-01-15","verdict":"VERIFIED"})'
expect "page: conditional shown WITH facts passes" 0 '!ERROR' page t5b
newpage t6; mut $W/t6/page.md 'module: M2 shown' 'module: MX shown'; mut $W/t6/page.md 'module: M3 shown' 'module: M2 shown'; mut $W/t6/page.md 'module: MX shown' 'module: M3 shown'; expect "page: module order wrong" 1 MODULE_ORDER page t6
newpage t7; mut $W/t7/page.md '<!-- module: M4 hidden: no performance samples in facts.json; gap: perf-none -->' $'<!-- module: M4 hidden: no performance samples in facts.json; gap: perf-none -->\n\nLeftover text.'; expect "page: hidden module with content" 1 HIDDEN_HAS_CONTENT page t7
newpage t7b; mut $W/t7b/page.md 'M4 hidden: no performance samples in facts.json; gap: perf-none' 'M4 hidden:'; expect "page: hidden without reason" 1 HIDDEN_NO_REASON page t7b
newpage t8; mut $W/t8/page.md 'Input costs $1.11' 'Input costs $3.33'; expect "page: M1 price from non-default endpoint" 1 M1_PRICE_ENDPOINT page t8
newpage t9; mut $W/t9/page.md 'Not published' '$0'; expect "page: \$0 on page" 1 ZERO_OR_FULL page t9
newpage t9b; mut $W/t9b/page.md 'Not published' '100%'; expect "page: 100% on page" 1 ZERO_OR_FULL page t9b
newpage t10; mut $W/t10/page.md 'Supported.' 'Supported. Use sk-abcdefghijklmnopqrstuvwx as the key.'; expect "page: secret key" 1 SECRET page t10
newpage t10b; mut $W/t10b/page.md 'Bearer $ACME_API_KEY' 'Bearer abcdefghijklmnopqrstuvwxyz012345'; expect "page: bearer token literal" 1 SECRET page t10b
expect "page: Bearer \$VAR is allowed" 0 '!SECRET' page g
newpage t11; mut $W/t11/page.md '| Streaming | Supported |' '| Streaming | Yes |'; expect "page: status_table bad value" 1 STATUS_TABLE_VALUE page t11
newpage t12; mut $W/t12/page.md '2. **Does it support streaming?** Supported.' '2. **Does it support streaming?** Supported, with 999K context.'; expect "page: derived_from violation" 1 DERIVED_FROM_VIOLATION page t12
expect "page: draft plan refused" 1 PLAN_NOT_APPROVED page g "$FX/plan-draft.md"
expect "page: --allow-draft-plan runs with loud warning" 0 WARN_DRAFT_PLAN page g "$FX/plan-draft.md" --allow-draft-plan
newpage t13; mut $W/t13/page.md '<!-- module: M1 shown -->' $'Stray intro.\n\n<!-- module: M1 shown -->'; expect "page: content before first marker" 1 CONTENT_BEFORE_MARKER page t13
newpage t14; mut $W/t14/page.md '<!-- module: M5 shown -->' '<!-- module: M9 shown -->'; expect "page: unknown module marker" 1 MARKER_UNKNOWN_MODULE page t14
expect "page: ...and the real M5 marker is then missing" 1 MARKER_MISSING page t14
newpage t15; mut $W/t15/page.md '# Acme Model 7.5 API' '# Acme Model 7.5 Review'; expect "page: H1 pattern" 1 H1_PATTERN page t15
newpage t16; mut $W/t16/page.md '## Acme Model 7.5 Capabilities' '## Capabilities'; expect "page: h2 pattern" 1 H2_PATTERN page t16
newpage t17; mut $W/t17/page.md '## Acme Model 7.5 Pricing' $'# Acme Model 7.5 API\n\n## Acme Model 7.5 Pricing'; expect "page: two H1s" 1 H1_COUNT page t17
newpage t18; mut $W/t18/page.md 'title: Acme Model 7.5 API, Pricing & Providers | AcmeHub' 'title: Acme Model 7.5 is great'; expect "page: title pattern" 1 TITLE_PATTERN page t18
newpage t18b; mut $W/t18b/page.md 'title: Acme Model 7.5 API, Pricing & Providers | AcmeHub' 'title: Acme Model 7.5 API: Pricing and Providers on Acme Cloud and Beta Host, Input and Output Token Rates, Cache Read Pricing, Context Window and Max Output, Streaming, Tool Calling, Structured Output, Chat Completions and Responses Protocols, Python, JavaScript and cURL Examples, Alternatives, Related Models and FAQ, Developer Docs and Provider Routing | AcmeHub'; expect "page: long title with variants -> PASS (no length limit)" 0 PASS page t18b
newpage t18c; mut $W/t18c/page.md 'title: Acme Model 7.5 API, Pricing & Providers | AcmeHub' 'title: Acme Model 7.5 API, Pricing & Providers'; expect "page: title without brand suffix" 1 TITLE_PATTERN page t18c
newpage t18d; python3 - "$W/t18d/page.md" <<'PY'
import re,sys
p=sys.argv[1]; s=open(p).read()
s=re.sub(r"(?m)^meta_description:.*$", "meta_description: Acme Model 7.5 is the text model from Acme. On AcmeHub it runs on Acme Cloud and Beta Host: compare their input, output and cache-read token prices and the conditions behind each rate, check the context window and max output on every provider, see which protocols and parameters each endpoint supports, including streaming, tool calling and structured output, compare alternatives and related models, read the FAQ, and copy a Chat Completions or Responses example in Python, JavaScript or cURL with your API key kept in an environment variable. Acme Model 7.5 is the text model from Acme. On AcmeHub it runs on Acme Cloud and Beta Host: compare their input, output and cache-read token prices and the conditions behind each rate, check the context window and max output on every provider, see which protocols and parameters each endpoint supports, including streaming, tool calling and structured output, compare alternatives and related models, read the FAQ, and copy a Chat Completions or Responses example in Python, JavaScript or cURL with your API key kept in an environment variable.", s, count=1)
open(p,"w").write(s)
PY
expect "page: long meta description -> PASS (no length limit)" 0 PASS page t18d
newpage t19; mut $W/t19/page.md 'default_endpoint: acme' 'default_endpoint: nowhere'; expect "page: default_endpoint unknown" 1 DEFAULT_ENDPOINT_UNKNOWN page t19
newpage t20; mut $W/t20/page.md 'meta_description:' 'meta_desc:'; expect "page: front matter key missing" 1 PAGE_MISSING_KEY page t20
newpage t21; jmut $W/t21/facts.json 'd["facts"][0]["source_url"]=""'; expect "page: fact without source_url" 1 FACT_NO_SOURCE page t21
newpage t22; jmut $W/t22/facts.json 'd["facts"][1]["id"]=d["facts"][0]["id"]'; expect "page: duplicate fact id" 1 FACT_DUP_ID page t22
newpage t23; jmut $W/t23/facts.json 'd["facts"][1]["verdict"]="MAYBE"'; expect "page: bad verdict" 1 FACT_BAD_VERDICT page t23
newpage t24; jmut $W/t24/facts.json 'd["facts"][1]["endpoint"]="ghost"'; expect "page: fact references unknown endpoint" 1 FACT_BAD_ENDPOINT page t24
newpage t25; jmut $W/t25/facts.json 'del d["facts"][1]["label"]'; expect "page: fact missing key" 1 FACT_MISSING_KEY page t25
newpage t26; mut $W/t26/page.md 'default_endpoint: acme' 'default_endpoint: auto'; expect "page: auto endpoint w/o 'vary' warns" 0 WARN_M1_AUTO_NO_VARY page t26
newpage t27; mut $W/t27/page.md 'See [pricing](/acme/pricing) for details.' 'Click [here](#) or see [pricing]() and [N] and [CITE].'; expect "page: placeholder link warns" 0 WARN_LINK_PLACEHOLDER page t27
expect "page: bad anchor warns" 0 WARN_LINK_ANCHOR page t27
expect "page: open placeholders warn" 0 WARN_OPEN_PLACEHOLDERS page t27
newpage t28; mut $W/t28/page.md 'on Acme Cloud, with' 'on Acme Cloud in 2025, with'; expect "page: bare year is an untraced number" 1 UNTRACED_NUMBER page t28
newpage t29; mut $W/t29/page.md 'with a 999K context' 'with a 999K context (updated 2026-01-15)'; expect "page: checked_date allowed" 0 '!UNTRACED_NUMBER' page t29
newpage t30; mut $W/t30/page.md 'with a 999K context' 'with a `128K` context and a link [docs](https://x.test/v2/2025/)'; expect "page: numbers in inline code / link URLs ignored" 0 '!UNTRACED_NUMBER' page t30
expect "page: lint runs by default (no WARN_LINT_FAILED)" 0 '!WARN_LINT_FAILED' pagel g "$FX/plan.md"
expect "page: --lint still accepted (no-op)" 0 '!WARN_LINT_FAILED' pagel g "$FX/plan.md" --lint
expect "page: --no-lint skips lint (no lint: findings)" 0 '!lint:' page g "$FX/plan.md"
expect "page: lint is entity-aware (C1 opening-entity warning fires on the good page)" 0 'lint:C1' pagel g "$FX/plan.md"
"$PY" - "$S" "$FX" <<'PY2' && ok "page: --lint produces lint: findings on cliche-heavy prose" || bad "page: --lint findings" "see above"
import sys; sys.path.insert(0, sys.argv[1]); import check_page as c
w = []
c.run_lint("It's important to note that, in today's fast-paced world, we delve into a rich tapestry. " * 3, "en", lambda code, msg, line=None: w.append(code))
assert "WARN_LINT_FAILED" not in w, w
assert any(x.startswith("lint:") for x in w), w
PY2
expect "page: lint warnings never error" 0 '!ERROR' pagel g "$FX/plan.md"
"$PY" - "$S" <<'PY' && ok "page: lint_prose drops markers, code fences, CTA rows; keeps prose" || bad "page: lint_prose" "see above"
import sys; sys.path.insert(0, sys.argv[1]); import check_page as c
out = c.lint_prose("<!-- module: M1 shown -->\nReal prose here.\n```bash\ncurl x \\\n  -d y\n```\n"
                   "[Get key](/a) · [Try it](https://b.test/c?m=1)\nSee [docs](/d) for more.\n")
assert "module" not in out and "curl" not in out and "Get key" not in out, out
assert "Real prose here." in out and "See [docs](/d) for more." in out, out
assert {"A4", "E7"} <= c.LINT_SKIP_RULES
PY

echo "== check_page: sources / ranges / units / front-matter numbers =="
newpage s1; jmut $W/s1/facts.json 'd["facts"][0]["source_url"]="https://example.test/not-snapshotted"'; expect "page: source_url without snapshot" 1 SOURCE_NOT_SNAPSHOTTED page s1
newpage s2; jmut $W/s2/facts.json 'd["facts"][0]["quote"]="Input $9.99"'; expect "page: quote not in snapshot" 1 QUOTE_NOT_FOUND page s2
newpage s3; jmut $W/s3/facts.json 'd["facts"][0]["quote"]="input $1.11"'; expect "page: quote match is case-sensitive" 1 QUOTE_NOT_FOUND page s3
newpage s4; jmut $W/s4/facts.json 'd["facts"][0]["quote"]="Input   $1.11\n Output $2.22"'
expect "page: quote whitespace-collapsed" 0 '!QUOTE_NOT_FOUND\|SOURCE_NOT_SNAPSHOTTED' page s4
newpage s4b; jmut $W/s4b/facts.json 'd["facts"][0]["source_url"]+="/"'
expect "page: trailing slash is significant (/a/b/ != snapshot of /a/b)" 1 SOURCE_NOT_SNAPSHOTTED page s4b
newpage s4c; jmut $W/s4c/facts.json 'd["facts"][0]["source_url"]=d["facts"][0]["source_url"].replace("https://example.test","HTTPS://Example.TEST")'
expect "page: scheme/host case ignored when matching snapshot" 0 '!SOURCE_NOT_SNAPSHOTTED' page s4c
newpage s5; jmut $W/s5/facts.json 'd["facts"][5]["quote"]="nothing like it"; d["facts"][5]["source_url"]="https://example.test/gone"; d["facts"][5]["verdict"]="UNVERIFIABLE"'
expect "page: UNVERIFIABLE facts skip source/quote checks" 0 '!QUOTE_NOT_FOUND\|SOURCE_NOT_SNAPSHOTTED' page s5
newpage s6; jmut $W/s6/facts.json 'd["facts"][0]["source_url"]="https://example.test/acme/acme-model-7-5#frag"'
expect "page: fragment ignored when matching snapshot" 0 '!SOURCE_NOT_SNAPSHOTTED' page s6
mkdir -p $W/noidx; cp $FX/plan.md $W/noidx/plan.md
expect "page: no sources index -> SOURCES_UNCHECKED warning only" 0 SOURCES_UNCHECKED page g $W/noidx/plan.md
expect "page: --sources explicit path (bad quote caught)" 1 QUOTE_NOT_FOUND page s2 $W/noidx/plan.md --sources $FX/sources/index.json
expect "page: --sources missing file -> SOURCES_UNCHECKED" 0 SOURCES_UNCHECKED page g $FX/plan.md --sources $W/none.json
expect "page: default sources present -> no SOURCES_UNCHECKED" 0 '!SOURCES_UNCHECKED' page g

newpage r1; mut $W/r1/page.md 'Acme Cloud is the cheapest listed endpoint.' 'Prices run $1.11-$2.22 or $1.11–$2.22 here; compare gpt-4o and V4-0813.'
expect "page: price ranges (hyphen/en dash) of traced values pass; model names skipped" 0 '!UNTRACED_NUMBER' page r1
newpage r2; mut $W/r2/page.md 'Acme Cloud is the cheapest listed endpoint.' 'Prices run $1.11-$9.99 here.'; expect "page: second number of a hyphen range is checked" 1 UNTRACED_NUMBER page r2
newpage r3; mut $W/r3/page.md 'Acme Cloud is the cheapest listed endpoint.' 'Prices run $1.11–$9.98 here.'; expect "page: second number of an en-dash range is checked" 1 UNTRACED_NUMBER page r3
newpage r4; mut $W/r4/page.md 'Acme Cloud is the cheapest listed endpoint.' 'Pick 1–3 options.'; expect "page: bare range 1–3 yields both tokens" 1 "untraced number '3'" page r4
expect "page: ...and the first token too" 1 "untraced number '1'" page r4
newpage r5; mut $W/r5/page.md 'Acme Cloud is the cheapest listed endpoint.' 'Not a range: gpt-4o and V4-0813 and x-5.'; expect "page: letter-adjacent / non-range dashes stay skipped" 0 '!UNTRACED_NUMBER' page r5

newpage u1; jmut $W/u1/facts.json 'd["facts"][0]["display"]="$1.11 / 1M tokens"'; expect "page: unit-bearing display accepts its leading number" 0 '!UNTRACED_NUMBER' page u1
newpage u2; jmut $W/u2/facts.json 'd["facts"][0]["display"]="$1.11 / 1M tokens"'; mut $W/u2/page.md 'per million tokens' 'per 1M tokens'; expect "page: unit-bearing display does not loosen other tokens (1M)" 1 "untraced number '1M'" page u2

newpage h1t; mut $W/h1t/page.md 'Acme Cloud is the cheapest listed endpoint.' 'Peak hours start at 01:00 UTC.'; expect "page: HH:MM is one token (untraced)" 1 "untraced number '01:00'" page h1t
newpage h2t; mut $W/h2t/page.md 'Acme Cloud is the cheapest listed endpoint.' 'Peak hours start at 01:00 UTC.'; jmut $W/h2t/facts.json 'd["facts"][0]["aliases"]=["01:00"]'; expect "page: HH:MM traced via a fact display/alias" 0 '!UNTRACED_NUMBER' page h2t

newpage f1; mut $W/f1/page.md 'fictional text model; this page' 'fictional text model with 4242 tokens; this page'; expect "page: untraced number in meta_description" 1 UNTRACED_NUMBER page f1
newpage f2; mut $W/f2/page.md '| AcmeHub' '| AcmeHub 2025'; expect "page: untraced number in title" 1 UNTRACED_NUMBER page f2
newpage f3; mut $W/f3/page.md 'fictional text model; this page' 'fictional text model from $1.11; this page'; expect "page: traced number in meta_description passes" 0 '!UNTRACED_NUMBER' page f3
newpage f4; mut $W/f4/page.md 'fictional text model; this page' 'fictional text model, always $0; this page'; expect "page: \$0 in meta_description" 1 ZERO_OR_FULL page f4

echo "== check_page: lint blockers, entity_aliases =="
mkdir -p $W/c1; cp $FX/lint-c1/page.md $FX/good/facts.json $W/c1/
expect "page: pronoun-start paragraph -> lint:C1 blocker is an ERROR" 1 'ERROR lint:C1' pagel c1
expect "page: ...--no-lint ignores it" 0 '!lint:C1' page c1
newpage al1; mut $W/al1/page.md 'entity_type: text' $'entity_type: text\nentity_aliases: [Model 7.5, Acme-7.5]'
expect "page: entity_aliases inline list accepted" 0 '!FRONT_MATTER_INVALID' pagel al1
newpage al2; mut $W/al2/page.md 'entity_type: text' $'entity_type: text\nentity_aliases: Model 7.5, "Acme-7.5"'
expect "page: entity_aliases comma string accepted" 0 '!FRONT_MATTER_INVALID' pagel al2
newpage al3; mut $W/al3/page.md 'entity_type: text' $'entity_type: text\nentity_aliases: [Model 7.5, A7]'
expect "page: 2-char alias rejected" 1 FRONT_MATTER_INVALID pagel al3

echo "== check_page: no disclaimers / third-party voice / production notes (rule 20) =="
S1='Acme Model 7.5 is a fictional text model.'
expect "page: labels in table cells pass (good page has no NOTE_)" 0 '!NOTE_' pagel g "$FX/plan.md"
newpage n1; mut $W/n1/page.md "$S1" "$S1 The served revision cannot be determined."
expect "page: 'cannot be determined' -> NOTE_DISCLAIMER" 1 'ERROR NOTE_DISCLAIMER' pagel n1
expect "page: ...--no-lint skips NOTE_ checks" 0 '!NOTE_' page n1
newpage n2; mut $W/n2/page.md "$S1" "$S1 Acme Cloud is not the same as Other Cloud."
expect "page: 'not the same as' -> NOTE_DISCLAIMER" 1 'ERROR NOTE_DISCLAIMER' pagel n2
newpage n3; mut $W/n3/page.md "$S1" "$S1 Acme Model 7.5 is widely regarded as reliable, according to users."
expect "page: hearsay / reviewer voice -> NOTE_THIRD_PARTY" 1 'ERROR NOTE_THIRD_PARTY' pagel n3
newpage n4; mut $W/n4/page.md "$S1" "$S1 建议这样表述：Acme Model 7.5 is a text model."
expect "page: '建议这样表述' production note -> NOTE_EDITORIAL" 1 'ERROR NOTE_EDITORIAL' pagel n4
newpage n5; mut $W/n5/page.md "$S1" "$S1 Acme Model 7.5 尚未核实，仅供参考。"
expect "page: '尚未核实' / '仅供参考' -> NOTE_DISCLAIMER" 1 'ERROR NOTE_DISCLAIMER' pagel n5
newpage n6; mut $W/n6/page.md "$S1" "$S1 The served revision is Not verified. <!-- gap: other-output -->"
expect "page: missing-value label in a prose sentence -> NOTE_LABEL_IN_PROSE" 1 'ERROR NOTE_LABEL_IN_PROSE' pagel n6
newpage n7; mut $W/n7/page.md 'fictional text model; this page' 'fictional text model; output price Not published; this page'
expect "page: missing-value label in meta_description -> NOTE_LABEL_IN_PROSE" 1 'ERROR NOTE_LABEL_IN_PROSE' pagel n7
newpage n8; mut $W/n8/page.md '| Other Cloud | $3.33 |' '| Other Cloud (as listed) | $3.33 |'
expect "page: disclaimer inside a table cell -> NOTE_DISCLAIMER" 1 'ERROR NOTE_DISCLAIMER' pagel n8
newpage n9; mut $W/n9/page.md "$S1" "Acme Model 7.5, also known as Acme Seven, is a fictional text model. Acme documents its rates."
expect "page: plain attribution and 'also known as' are not notes" 0 '!NOTE_' pagel n9
"$PY" - "$S" <<'PY' && ok "page: lint config = entity+aliases, central_entity, H1 as primary_keyword" || bad "page: lint_config" "see above"
import sys; sys.path.insert(0, sys.argv[1]); import check_page as c
cfg = c.lint_config("<!-- module: M1 shown -->\n```\n# not me\n```\n# Acme Model 7.5 API\n\ntext\n", "Acme Model 7.5", ["Acme-7.5"], "en")
assert cfg == {"language": "en", "entities": ["Acme Model 7.5", "Acme-7.5"],
               "term_lists": {"central_entity": "Acme Model 7.5", "primary_keyword": "Acme Model 7.5 API"}}, cfg
assert c.parse_aliases("[V4 Pro, 'DeepSeek-V4-Pro']") == ["V4 Pro", "DeepSeek-V4-Pro"] and c.parse_aliases("") == []
PY

echo "== check_page: review.json merge =="
newpage rv0
expect "review: missing -> REVIEW_MISSING warning only" 0 REVIEW_MISSING page rv0
newpage rv1; mkreview rv1 warning; mut $W/rv1/page.md 'Other Cloud' 'Other Cloud X'
expect "review: stale hash -> REVIEW_STALE error" 1 REVIEW_STALE page rv1
newpage rv2; mkreview rv2 blocker
expect "review: blocker -> ERROR review:R1, FAIL" 1 'ERROR review:R1' page rv2
newpage rv3; mkreview rv3 waived
expect "review: waived blocker -> PASS" 0 PASS page rv3
expect "review: ...and not an error" 0 '!ERROR' page rv3
expect "review: ...summary counts 1 waived" 0 '1 waived' page rv3
newpage rv4; mkreview rv4 warning
expect "review: warning (whitespace-normalised evidence) -> PASS with warning" 0 'WARN  review:R2' page rv4
expect "review: ...info is dropped" 0 '!review:R3' page rv4
expect "review: ...evidence found" 0 '!REVIEW_EVIDENCE_NOT_FOUND' page rv4
newpage rv5; mkreview rv5 badevidence
expect "review: evidence not on page -> warning, violation still counted" 0 REVIEW_EVIDENCE_NOT_FOUND page rv5
expect "review: ...still counted" 0 '1 warning(s), 0 waived' page rv5
newpage rv6; mkreview rv6 badseverity
expect "review: bad severity -> REVIEW_INVALID" 1 REVIEW_INVALID page rv6
newpage rv7; echo '{not json' > $W/rv7/review.json
expect "review: invalid JSON -> REVIEW_INVALID" 1 REVIEW_INVALID page rv7
newpage rv8; echo '{"violations": []}' > $W/rv8/review.json
expect "review: missing keys -> REVIEW_INVALID" 1 REVIEW_INVALID page rv8
newpage rv9; mkreview rv9 blocker; mv $W/rv9/review.json $W/rv9/other.json
expect "review: --review explicit path" 1 'ERROR review:R1' page rv9 "$FX/plan.md" --review $W/rv9/other.json
newpage rv10; mkreview rv10 waived
page rv10 "$FX/plan.md" --json $W/rv10.json >/dev/null 2>&1
"$PY" -c "import json;r=json.load(open('$W/rv10.json'))['review'];assert r=={'present':True,'reviewer':'test-reviewer','blockers':0,'warnings':0,'waived':1,'stale':False},r" && ok "review: --json report block" || bad "review: --json block" "bad json"

echo "== check_page: acceptance.json merge =="
newpage ac0
expect "accept: missing -> ACCEPT_MISSING warning only" 0 ACCEPT_MISSING page ac0
newpage ac1; mkaccept ac1 pass
expect "accept: all pass, live call needs a person -> PASS" 0 PASS page ac1
expect "accept: ...needs_person is a warning" 0 'WARN  ACCEPT_NEEDS_PERSON' page ac1
expect "accept: ...summary" 0 '0 failed blocker(s), 0 failed warning(s), 1 need a person, 0 waived' page ac1
newpage ac2; mkaccept ac2 pass; mut $W/ac2/page.md 'Other Cloud' 'Other Cloud X'
expect "accept: page edited after review -> ACCEPT_STALE" 1 ACCEPT_STALE page ac2
newpage ac3; mkaccept ac3 pass
jmut $W/ac3/acceptance.json 'it=[x for x in d["items"] if x["id"]=="G5"][0]; it.update(result="fail", location="M2", evidence="Acme Cloud is the cheapest listed endpoint.", fix_instruction="Match the table.")'
expect "accept: failed blocker item -> ERROR accept:G5" 1 'ERROR accept:G5' page ac3
expect "accept: ...evidence found" 1 '!ACCEPT_EVIDENCE_NOT_FOUND' page ac3
newpage ac4; mkaccept ac4 pass
jmut $W/ac4/acceptance.json 'it=[x for x in d["items"] if x["id"]=="G10"][0]; it.update(result="fail", location="M4", evidence="not on the page at all", fix_instruction="Add the fact.")'
expect "accept: failed warning item -> warning, PASS" 0 'WARN  accept:G10' page ac4
expect "accept: ...evidence not on page -> warning" 0 ACCEPT_EVIDENCE_NOT_FOUND page ac4
newpage ac5; mkaccept ac5 pass
jmut $W/ac5/acceptance.json 'it=[x for x in d["items"] if x["id"]=="G5"][0]; it.update(result="fail", location="M2", evidence="Acme Cloud is the cheapest listed endpoint.", fix_instruction="Match the table.", waived_by="Roger", waiver_note="Checked.")'
expect "accept: waived failed blocker -> PASS" 0 '1 waived' page ac5
newpage ac6; mkaccept ac6 pass; jmut $W/ac6/acceptance.json 'd["items"]=[x for x in d["items"] if x["id"]!="TXT-2"]'
expect "accept: unanswered item -> ACCEPT_INCOMPLETE" 1 'ACCEPT_INCOMPLETE.*TXT-2' page ac6
newpage ac7; mkaccept ac7 pass; jmut $W/ac7/acceptance.json 'd["items"][0]["result"]="ok"'
expect "accept: bad result -> ACCEPT_INVALID" 1 ACCEPT_INVALID page ac7
newpage ac8; mkaccept ac8 pass; jmut $W/ac8/acceptance.json 'd["items"][0].update(result="fail", evidence="x")'
expect "accept: fail without fix_instruction -> ACCEPT_INVALID" 1 ACCEPT_INVALID page ac8
newpage ac9; mkaccept ac9 pass; jmut $W/ac9/acceptance.json 'd["items"][-1]["result"]="n/a"'
expect "accept: n/a without note -> ACCEPT_INVALID" 1 ACCEPT_INVALID page ac9
newpage ac10; mkaccept ac10 pass; jmut $W/ac10/acceptance.json 'd["items"].append(dict(d["items"][0]))'
expect "accept: item answered twice -> ACCEPT_INVALID" 1 ACCEPT_INVALID page ac10
newpage ac11; mkaccept ac11 pass; jmut $W/ac11/acceptance.json 'd["entity_type"]="image"'
expect "accept: checked as another entity_type -> ACCEPT_WRONG_TYPE" 1 ACCEPT_WRONG_TYPE page ac11
newpage ac12; mkaccept ac12 pass; jmut $W/ac12/acceptance.json 'd["items"].append({"id": "IMG-1", "result": "pass"})'
expect "accept: item for another type -> ACCEPT_UNKNOWN_ITEM warning" 0 ACCEPT_UNKNOWN_ITEM page ac12
newpage ac13; mkaccept ac13 pass; mv $W/ac13/acceptance.json $W/ac13/other.json
expect "accept: --acceptance explicit path" 0 'test-acceptor' page ac13 "$FX/plan.md" --acceptance $W/ac13/other.json
newpage ac14; mkaccept ac14 pass
page ac14 "$FX/plan.md" --json $W/ac14.json >/dev/null 2>&1
"$PY" -c "import json;a=json.load(open('$W/ac14.json'))['acceptance'];assert a=={'present':True,'reviewer':'test-acceptor','blockers':0,'warnings':0,'needs_person':['G12'],'waived':0,'stale':False},a" && ok "accept: --json report block" || bad "accept: --json block" "bad json"
"$PY" - "$S" "$HERE/../references/acceptance.md" <<'PYC' && ok "accept: every checklist id is documented in acceptance.md" || bad "accept: ids vs acceptance.md" "see above"
import re, sys; sys.path.insert(0, sys.argv[1]); import check_page as c
doc = open(sys.argv[2], encoding="utf-8").read()
ids = set(re.findall(r"^\| `?([A-Z]+-?\d+)`? \| (blocker|warning) \|", doc, re.M))
assert ids == {(i, sev) for i, (_, sev) in c.ACCEPT_ITEMS.items()}, ids ^ {(i, sev) for i, (_, sev) in c.ACCEPT_ITEMS.items()}
PYC

echo "== gaps =="
newpage g0; expect "gaps: good page logs its gaps" 0 '!UNLOGGED_GAP' page g0
newpage g1; mut $W/g1/page.md 'Not published <!-- gap: other-output -->' 'Not published'; expect "gaps: label without marker" 1 UNLOGGED_GAP page g1
newpage g2; mut $W/g2/page.md '<!-- gap: other-output -->' '<!-- gap: nope -->'; expect "gaps: marker names unknown gap" 1 GAP_UNKNOWN page g2
newpage g3; mut $W/g3/page.md 'Not published <!-- gap: other-output -->' 'Not verified <!-- gap: other-output, perf-none -->'; expect "gaps: Not verified + multi-id marker" 0 '!UNLOGGED_GAP' page g3
newpage g4; jmut $W/g4/facts.json 'd["gaps"][0]["kind"]="contradiction"'; expect "gaps: contradiction needs both sides" 1 GAP_INVALID page g4
newpage g5; jmut $W/g5/facts.json 'd["gaps"][0]["searched"]=[]'; expect "gaps: missing needs searched" 1 GAP_INVALID page g5
newpage g6; jmut $W/g6/facts.json 'd["gaps"][0].pop("request")'; expect "gaps: client gap needs request/question" 1 GAP_INVALID page g6
newpage g7; jmut $W/g7/facts.json 'd["gaps"][0]["evidence"]=[{"source_url":"https://example.test/acme/acme-model-7-5","quote":"not in snapshot"}]'; expect "gaps: evidence quote verified" 1 QUOTE_NOT_FOUND page g7 "$FX/plan.md" --sources "$FX/sources/index.json"
newpage g8; jmut $W/g8/facts.json 'd["gaps"][0]["searched"]=["https://nowhere.example.test/x"]'; expect "gaps: searched url must be snapshotted" 1 SOURCE_NOT_SNAPSHOTTED page g8 "$FX/plan.md" --sources "$FX/sources/index.json"
newpage g9; mut $W/g9/page.md '; gap: perf-none -->' ' -->'; expect "gaps: hidden module without gap warns" 0 WARN_HIDDEN_NO_GAP page g9
newpage ga; jmut $W/ga/facts.json 'd["gaps"].append({"id":"spare","kind":"missing","owner":"external","summary":"x","searched":["https://example.test/acme/acme-model-7-5"]})'; expect "gaps: unreferenced gap warns" 0 WARN_GAP_UNUSED page ga

echo "== site_fixes =="
SF="$W/sf"; SF2="$W/sf2"; mkdir -p "$SF/pages"; cp -r "$W/g0" "$SF/pages/p1"; cp -r "$W/g0" "$SF/pages/p2"
expect "site_fixes: writes report" 0 "1 request(s), 2 external" "$PY" "$S/site_fixes.py" "$SF" --site example.test
"$PY" - "$SF" <<'PY' && ok "site_fixes: shared key merges pages, external listed" || bad "site_fixes: merge" "see above"
import json, sys
d = sys.argv[1]
items = json.load(open(d + "/site-fix-requests.json"))
c = [i for i in items if i["owner"] == "client"]
assert len(c) == 1 and [p["page"] for p in c[0]["pages"]] == ["p1", "p2"], c
md = open(d + "/site-fix-requests.md").read()
assert "### R1. Other Cloud's output price" in md and "Add Other Cloud's output price" in md, md
assert "External gaps" in md and "No performance samples published" in md, md
PY
mkdir -p "$SF2/pages"; cp -r "$W/g0" "$SF2/pages/p1"
jmut "$SF2/pages/p1/facts.json" 'd["gaps"].append(dict(d["gaps"][0], id="other-input", summary="Other Cloud input is unclear", request="Label the input price."))'
"$PY" "$S/site_fixes.py" "$SF2" >/dev/null
grep -q "(+1 related)" "$SF2/site-fix-requests.md" && grep -q "Label the input price." "$SF2/site-fix-requests.md" && ok "site_fixes: same-page gaps under one key all listed" || bad "site_fixes: grouped gaps" "missing part"
jmut "$SF/pages/p1/facts.json" 'd["gaps"][0]["status"]="resolved"'; jmut "$SF/pages/p2/facts.json" 'd["gaps"][0]["status"]="resolved"'
expect "site_fixes: resolved gaps dropped" 0 "0 request(s)" "$PY" "$S/site_fixes.py" "$SF"
expect "site_fixes: no pages" 2 "no pages" "$PY" "$S/site_fixes.py" "$W/empty-ws"

echo "== snapshot =="
SN="$W/sn"; mkdir -p "$SN"; printf 'rendered text 1.11\n' > "$SN/r.txt"
expect "snapshot: --from-file" 0 saved "$PY" "$S/snapshot.py" https://example.test/a/b --dir "$SN/sources" --role current-rendered --from-file "$SN/r.txt"
"$PY" - "$SN/sources" <<'PY' && ok "snapshot: index.json entry shape" || bad "snapshot: index.json entry shape" "see above"
import json, sys, os
d = sys.argv[1]
idx = json.load(open(d + "/index.json"))
assert len(idx) == 1, idx
e = idx[0]
assert e["url"] == "https://example.test/a/b" and e["role"] == "current-rendered", e
assert e["html"] is None and e["method"] == "from-file" and e["final_url"] == e["url"], e
assert e["fetched_at"].endswith("Z") and os.path.isfile(d + "/" + e["txt"]), e
assert open(d + "/" + e["txt"]).read() == "rendered text 1.11\n"
assert e["txt"] == "example.test__a-b__current-rendered.txt", e["txt"]
PY
"$PY" "$S/snapshot.py" https://example.test/a/b --dir "$SN/sources" --role current-rendered --from-file "$SN/r.txt" >/dev/null
"$PY" "$S/snapshot.py" https://example.test/a/b --dir "$SN/sources" --role fact --from-file "$SN/r.txt" >/dev/null
"$PY" -c "import json;i=json.load(open('$SN/sources/index.json'));assert len(i)==2,i" && ok "snapshot: re-snapshot same url+role replaces, other role adds" || bad "snapshot: replace" "index length"
"$PY" "$S/snapshot.py" https://example.test/a/b/ --dir "$SN/sources" --role fact --from-file "$SN/r.txt" >/dev/null
"$PY" - "$SN/sources" <<'PY' && ok "snapshot: /a/b/ and /a/b kept in separate files" || bad "snapshot: trailing slash" "see above"
import json, sys
i = json.load(open(sys.argv[1] + "/index.json"))
f = {e["url"]: e["txt"] for e in i if e["role"] == "fact"}
assert f == {"https://example.test/a/b": "example.test__a-b__fact.txt",
             "https://example.test/a/b/": "example.test__a-b-slash__fact.txt"}, f
PY
"$PY" "$S/snapshot.py" "https://example.test/$(printf 'x%.0s' $(seq 1 120))" --dir "$SN/long" --role fact --from-file "$SN/r.txt" >/dev/null
"$PY" "$S/snapshot.py" "https://example.test/$(printf 'x%.0s' $(seq 1 121))" --dir "$SN/long" --role fact --from-file "$SN/r.txt" >/dev/null
[ "$(ls "$SN/long" | grep -c '__fact.txt$')" = 2 ] && ok "snapshot: long paths sharing a prefix don't collide" || bad "snapshot: long paths" "$(ls "$SN/long")"
expect "snapshot: --from-file missing file" 1 "not found" "$PY" "$S/snapshot.py" https://example.test/a --dir "$SN/sources" --from-file "$SN/none.txt"

PORT=$((20000 + RANDOM % 20000))
"$PY" -m http.server "$PORT" --bind 127.0.0.1 --directory "$FX/www" >/dev/null 2>&1 & SRV=$!
sleep 1
expect "snapshot: urllib fetch (local server)" 0 saved "$PY" "$S/snapshot.py" "http://127.0.0.1:$PORT/" --dir "$SN/net" --role competitor
"$PY" - "$SN/net" <<'PY' && ok "snapshot: html saved, text stripped of script/style/noscript" || bad "snapshot: text extraction" "see above"
import json, sys
d = sys.argv[1]
e = json.load(open(d + "/index.json"))[0]
assert e["method"] == "urllib" and e["status"] == 200 and e["html"].endswith(".html"), e
assert "<script>" in open(d + "/" + e["html"]).read()
t = open(d + "/" + e["txt"]).read()
assert "Hello Fake" in t and "Price is $1.11" in t, t
assert "secret" not in t and "color:red" not in t and "enable js" not in t, t
PY
expect "snapshot: HTTP 404 exits non-zero" 1 "HTTP 404" "$PY" "$S/snapshot.py" "http://127.0.0.1:$PORT/missing" --dir "$SN/net"
"$PY" -c "import json;assert len(json.load(open('$SN/net/index.json')))==1" && ok "snapshot: failure records nothing" || bad "snapshot: failure recorded" "index grew"
expect "snapshot: connection refused exits non-zero" 1 "could not fetch" "$PY" "$S/snapshot.py" "http://127.0.0.1:9/" --dir "$SN/net2"
[ ! -e "$SN/net2/index.json" ] && ok "snapshot: no index on failed first fetch" || bad "snapshot: net2 index" "created"

echo
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" = 0 ]
