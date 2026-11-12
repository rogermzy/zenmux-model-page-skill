---
name: zenmux-model-page
description: Write the content of a zenmux.ai model page (e.g. zenmux.ai/deepseek/deepseek-v4-pro) on demand, following ZenMux's approved model-page template (modules M1–M9). Every price, spec, version and date comes from a quoted, saved source; nothing is invented. Output is page.md plus its fact ledger, a fact-check report, and a list of fixes the ZenMux site itself needs. Use when asked to "write / rewrite / refresh the model page for <model>", "make a ZenMux page for <model>", "update <model>'s page", or to roll the template out to more models. Covers text, image, video and audio (speech) models; other model types have no template yet.
---

# ZenMux model page

You write one model page at a time from ZenMux's approved template. The template is
`references/plan.md` (Chinese; its appendix A JSON is the machine-readable contract). You do not
change the template: if a model doesn't fit it, stop and say what is missing.

Everything here is plain files plus Python 3.9+ scripts (standard library only). You need a
shell, outbound HTTPS, and ideally web search for finding developer docs. No other tools.

`SKILL_DIR` below means the folder this file is in.

## Hard rules

1. **You are never the source of a number.** Prices, context sizes, max output, versions, dates,
   benchmark scores, latency, uptime: each must be a fact in `facts.json` whose `quote` appears
   verbatim in a saved snapshot. No source → the template's missing label (`Not published`,
   `Not verified`, `No data`). Writing a remembered value and attaching a source is the same
   violation. Invented model names, aliases or version numbers too.
2. **Developer docs never override ZenMux's own data silently.** When ZenMux's page, ZenMux's
   docs and the model developer's docs disagree, the value's table cell shows the missing/`Not
   verified` label (or the value is left out) and a gap records both quotes. Don't pick a side,
   and don't explain the disagreement on the page (rule 8).
3. **Hidden beats empty.** Conditional modules show only when their `show_if` is met by facts in
   the ledger. Never show `$0`, `100%`, an empty chart or a generic leaderboard as filler.
4. **Never skip the checks.** `check_page.py` must PASS (facts, structure, writing lint and
   writing review) and the fact-check must be done before you call a page finished. A REFUTED
   fact or an unwaived writing blocker still on the page blocks delivery.
4a. **Rewrite only what was flagged.** When a check or the review flags sentences, rewrite those
   sentences and keep every other sentence as it is. At most 3 rewrite rounds per page; after
   that, stop and report the remaining violations as needing a person. Never waive a violation
   yourself.
5. **No secrets.** Code samples use `$ZENMUX_API_KEY`; never paste a real key into any file.
6. **Every gap is logged.** Anything the site doesn't publish, says two ways, states differently
   from the developer's docs, shows as an outlier, or only renders with JavaScript goes into
   `gaps[]` with quotes. These become the site-fix list for the ZenMux site team.
7. **Unsupported model types stop.** Transcription, embeddings, rerank and other types have no
   template. Say so and stop; don't improvise one.
8. **No disclaimers, third-party voice or production notes on the page.** The page states facts
   and stops. Rewrite or remove every:
   - vague disclaimer or uncertainty note: "cannot be determined", "not yet verified", "is not
     the same as", "may vary", "subject to change", "in the sources checked", "X does not
     publish Y", "check before relying on it" (Chinese pages: 无法确定, 尚未核实, 不等同于,
     仅供参考, 以…为准);
   - third-party or reviewer voice: "ZenMux says / claims / describes", "according to users",
     "is widely regarded as", "a solid choice", "in our tests";
   - production note meant for the writer or editor: "suggested wording", "建议这样表述",
     TODO, "to be confirmed", "Note:";
   - sentence after a statement that explains how reliable or complete its data is, or
     disclaims it ("The figures are estimates and leave out…", "Prices can change; verify with
     the provider").

   Missing-value labels (`Not verified`, `Not published`, `No data`) appear only as values in
   table cells, never inside a prose sentence. If a sentence's only content is that something is
   unknown, unverified or unpublished, delete it. The gap stays in `facts.json`, and the gap
   marker moves to the table cell or line where the value would be. Attribution stays
   ("DeepSeek documents …", "ZenMux lists …"): naming a fact's source is not a disclaimer.

## Read before working

| File | When |
|---|---|
| `references/plan.md` | Always. Appendix A (JSON) = module order, fields, rules, `show_if`, `entity_variants`, missing labels. Part 4 = per-type rules and acceptance. |
| `references/facts-ledger.md` | Before touching `facts.json` (schema for facts and gaps). |
| `references/page-format.md` | Before writing `page.md` (front matter, module markers, page rules, and the 20 sentence rules: 19 from the Wendy Writes writing constitution plus rule 20, no disclaimers or production notes). |
| `references/fact-check.md` | At the fact-check step. |
| `references/review.md` | At the writing-review step (the reviewer prompt and `review.json`). |
| `examples/deepseek-v4-pro/`, `examples/gpt-image-2/` | Finished pages (text, image) with their ledgers and reports. Match their quality, not their facts. |

## Workspace

One folder holds all pages so ZenMux's shared docs are fetched once and reused:

```
<workspace>/                 default: ./zenmux-pages
  plan.md                    copy of references/plan.md (scripts read it from here)
  sources/                   snapshots + index.json (snapshot.py writes these)
  pages/<model-slug>/
    facts.json               fact ledger (facts[] + gaps[])
    gap-candidates.json      values new_page.py found empty or zero (you review them)
    page.md                  ← the page
    page.check.json          check result
    review.json              writing review (reviewer's violations + page hash)
    fact-check-report.md
  site-fix-requests.md       ← fixes for the ZenMux site (all pages, merged)
```

First run only: `mkdir -p <workspace> && cp $SKILL_DIR/references/plan.md <workspace>/plan.md`.

## Steps

### 1. Start the page

```bash
python3 $SKILL_DIR/scripts/new_page.py <workspace> "<model name, id or URL>"
```

Never skip this step or rebuild it by hand. If you were told not to make API calls, add
`--no-api`: the model is then resolved from the sitemap and the model page's own data, with no
request to any API. Without the flag it also reads ZenMux's keyless public models list
(`https://zenmux.ai/api/v1/models`) for extra cross-checks, and falls back to no-API mode by
itself if that list can't be fetched. No API key is ever needed here.

It resolves the model through ZenMux's public models API, picks the template variant from the
model's output type, snapshots the model page, decodes the page's embedded data (per-provider
prices, fee items, context, max output, aliases, status), re-fetches shared ZenMux docs older
than 14 days, and writes a starter `facts.json` whose every quote is already verified.

- Exit 2: name not found or ambiguous: it prints candidates; ask the user which one.
- Exit 3: no template for this model type: report that and stop (rule 7).
- Exit 4: `facts.json` already exists: see "Refreshing an existing page".
- Exit 5: the page shape is not recognized, which means ZenMux's page changed. Report it; don't
  hand-copy numbers from the browser instead.

It also writes `zenmux-data.json` (the decoded page data, including supported parameters per
protocol: use it to find capability facts, then quote them from the data snapshot) and
`gap-candidates.json`. Two things to check by hand:
- `entity` is the API display name, which can carry a revision ("DeepSeek V4.1 Flash 1017").
  Set it to the name the page should use in its H1 and title; keep the revision as a fact.
- Providers ZenMux marks "Sunset" start as `status: disabled` (no select button, not counted for
  the lowest price) with a gap candidate, because ZenMux doesn't say what Sunset means.

### 2. Add developer facts

Find the model developer's own pages for this model (model card / docs / pricing / release
notes), in this priority: developer docs → official model card or paper. Snapshot each before
quoting it:

```bash
python3 $SKILL_DIR/scripts/snapshot.py <url> --dir <workspace>/sources --role fact
```

Add facts to `facts.json` per `references/facts-ledger.md`: `quote` copied exactly from the
snapshot text in `sources/`, `verdict: "UNCHECKED"`. Typical: official context/max output,
modalities, snapshot/version names, release date, the developer's own list price (as the
developer's price, never as ZenMux's), deprecations. If a value lives only in a page's
embedded JSON, extract it to a text file and add it with `--role data --from-file <txt>`.

### 3. Review gap candidates and log gaps

Open `gap-candidates.json`. For each: decide whether it is a real gap (not published,
contradiction, conflicts with developer docs, suspected error, JS-only) and record it in
`gaps[]` with both quotes and where you looked. A value that is legitimately not applicable
(e.g. no cache pricing for an image-only provider) is not a gap; note why and drop it.
App routes such as `/platform/...` or `/settings/...` load in the browser after sign-in, so a
plain fetch returning the homepage HTML is expected and is not a gap. Check them against
ZenMux's docs instead.
Compare ZenMux's values with the developer's as you go; every disagreement is a gap.

### 4. Decide which modules show

For each module in appendix A, in order: required → shown; conditional → shown only if its
`show_if` is satisfied by facts in the ledger, else hidden with the reason (naming the gap if
one explains it). Apply the `entity_variants` rules for the model's type: they override the
generic module rules (e.g. image: billing-items table, no Chat CTA; video: create-task + query
example, generation time; audio: voices/languages/limits, not Chat).

### 5. Write page.md

Follow `references/page-format.md`, module by module in template order, in English, applying
both the page rules and the 20 sentence rules as you write (it is cheaper than fixing them
later). Every number you type must already be a fact's `display` value (or one of its
`aliases`). Missing value → the template's label plus `<!-- gap: <id> -->` on the same line
(inside the table cell for tables). FAQ answers restate facts already on the page; never a
second hand-typed copy. Set `entity_aliases` in the front matter to the short names the page
really uses for the model (e.g. `[V4 Pro]`), so paragraph openers using them count.
Write each statement once and stop: no disclaimer, hedge, data-reliability caveat or note to
the editor after it, and no missing-value label in a sentence (rule 8). An unknown value goes in
its table cell as the label; prose about it is deleted, not softened.
Write the `title` and `meta_description` long: there is no character limit, and more name
variants and related entities (model ID, aliases, revision, developer, providers, billing
conditions, context, capabilities, example languages) are better. Never trim them to a length.

### 6. Check

```bash
python3 $SKILL_DIR/scripts/check_page.py <workspace>/pages/<slug>/page.md \
  --plan <workspace>/plan.md --sources <workspace>/sources/index.json \
  --json <workspace>/pages/<slug>/page.check.json
```

Fix every ERROR and run it again until it prints PASS (rule 4a: flagged sentences only).
Common errors: a number with no fact (`UNTRACED_NUMBER`), a quote not found in its snapshot
(`QUOTE_NOT_FOUND`), a missing label with no gap behind it (`UNLOGGED_GAP`), a module out of
order or missing its marker, and `lint:<rule>` blockers from the writing lint (a paragraph
opening with It/This, a hedge word, a banned phrase, a link on a paragraph's first word, the
model name missing from the H1 or the first sentence), and rule 8 errors: `NOTE_DISCLAIMER`,
`NOTE_THIRD_PARTY`, `NOTE_EDITORIAL` (a disclaimer, reviewer voice or production note) and
`NOTE_LABEL_IN_PROSE` (a missing-value label inside a sentence). Fix those by rewriting the
sentence as a plain attributed fact or deleting it, never by finding a synonym that slips past the
pattern. `lint:<rule>` warnings (passive voice,
generic verbs, uniform sentence length, long paragraphs, paragraphs not opening with the model
name) are the same rules at lower severity: fix them unless the fix makes a sentence worse.
`REVIEW_MISSING` is expected until step 8.

### 7. Fact-check

Follow `references/fact-check.md`. The checker re-reads every source and sets each fact's
`verdict`; you write `fact-check-report.md`, fix REFUTED facts and the page, turn site
problems it finds into gaps, then re-run step 6.

### 8. Writing review

Follow `references/review.md`: a reviewer outside your own context audits `page.md` against the
semantic writing rules and you save its output as `review.json`. Then re-run step 6. Unwaived
review blockers (`review:<rule>`) fail the check: rewrite the flagged sentences, re-run step 6,
and review again, because any edit to `page.md` makes the review stale (`REVIEW_STALE`).
Stop after 3 rewrite rounds (rule 4a).

### 9. Final check

Run step 6 one last time on the finished page. It must PASS with a current review.

### 10. Site fixes

```bash
python3 $SKILL_DIR/scripts/site_fixes.py <workspace> --site zenmux.ai
```

Writes `site-fix-requests.md` (+ `.json`): one request per site-owned gap, merged across all
pages in the workspace, with quotes, the requested change, any question to answer first, and
which pages it unblocks. You write the list; a person decides who acts on it.

### 11. Report

For each page: its path; shown and hidden modules (with reasons); the fact-check totals;
facts left UNVERIFIABLE; writing-review result (reviewer model, blockers fixed, warnings left,
rewrite rounds used); gaps logged; and the path to `site-fix-requests.md`. Say plainly what
still needs a person, for example a live API call to confirm an image or video model ID (the
template's acceptance rule for those types). Don't call a page ready while any of that is open.

## Refreshing an existing page

Run `new_page.py` with `--force` only after moving the old `facts.json` aside, then compare old
and new ledgers: changed prices, providers added or deactivated, new aliases. Update the page
from the new ledger and re-run steps 6–10. Sources older than 14 days are re-fetched
automatically; pass `--max-age-days 0` to force it.

## Running steps in parallel

If your agent can run sub-tasks, three things benefit: several models at once (one sub-task per
model, each given this file and the references; review each `page.check.json` yourself), the
fact-check (see `references/fact-check.md`), and the writing review (`references/review.md`). If it can't, do everything in sequence; the
result is the same, only slower.
