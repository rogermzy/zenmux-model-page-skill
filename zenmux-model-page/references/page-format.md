# page.md — layout and writing rules

```markdown
---
template_id: zenmux-model-page
entity: DeepSeek V4 Pro
entity_type: text
url: /deepseek/deepseek-v4-pro
title: DeepSeek V4 Pro API (deepseek/deepseek-v4-pro, DeepSeek-V4-Pro-0813): Pricing & Providers on DeepSeek, Tencent Cloud, Baidu, … | ZenMux
meta_description: …
default_endpoint: deepseek
checked_date: 2026-10-19
facts: facts.json
---

<!-- module: M1 shown -->
# DeepSeek V4 Pro API
…

<!-- module: M2 shown -->
## DeepSeek V4 Pro Pricing & Providers
…

<!-- module: M5 hidden: no performance samples in facts.json -->

<!-- module: M6 hidden: no version-matched benchmark source -->
…
```

## Structure (enforced by `check_page.py`)

- Front matter keys: `template_id` (= spec), `entity`, `entity_type` (a key of
  `entity_variants`), `url`, `title`, `meta_description`, `default_endpoint` (an endpoint id in
  facts.json, or `auto` for automatic routing), `checked_date`, `facts`. Optional:
  `entity_aliases` (inline list, e.g. `[V4 Pro]`; each ≥ 3 characters): short names that count
  as the model name for the paragraph-opening rule.
- `title` matches `title_pattern` (`{Entity} API` first, `| ZenMux` last, variants in between);
  the only `#` H1 matches `h1_pattern` and sits in M1. Numbers in `title` and `meta_description`
  must be fact display strings, like any number on the page.
- One marker per spec module, in spec order: `<!-- module: Mx shown -->` or
  `<!-- module: Mx hidden: <reason> -->`. Required modules are always shown. A hidden module
  has no content before the next marker. A conditional module whose `show_if` selector matches
  no facts must be hidden.
- A shown module with an `h2` pattern starts with an `##` heading matching it.
- `default_endpoint` ≠ `auto`: every price shown in M1 belongs to a fact of that endpoint.
  `auto`: M1 states that version/price can vary by the endpoint hit.
- **Gap markers.** Every line that shows a missing-value label (`Not verified`, `Not published`,
  `No data`, or any other value in the spec's `missing_value_labels`) carries an invisible
  `<!-- gap: <id> -->` (several: `<!-- gap: a, b -->`) naming entries in facts.json `gaps[]`.
  In a table, put it inside the cell, before the closing `|`. A hidden conditional module names
  its gap in the reason: `<!-- module: M5 hidden: uptime only charted client-side; gap: perf-uptime -->`.
  Unmarked label → `UNLOGGED_GAP` (error); unknown id → `GAP_UNKNOWN`; logged but never
  referenced → `WARN_GAP_UNUSED`.

## Writing rules

Two layers: the page rules below (what goes on a model page) and the sentence rules after them
(how every sentence is written, from the Wendy Writes writing constitution). On a conflict
between a sentence rule and a page rule, the page rule wins only where it says so explicitly
(missing-value labels, display strings); otherwise both apply.

### Page rules

- **Title and meta description: no length limit, longer is better.** Never shorten either to
  fit a character count. After `{Entity} API`, the title lists the name variants and related
  entities the page really answers: model ID, aliases and revision names, developer, provider
  names, billing type and conditions (peak/off-peak, cache, per image), context and max output,
  main capabilities, example languages, alternatives, FAQ. The meta description says the same in
  full sentences. Only what the page covers, numbers only from facts, no superlatives. Example:
  `DeepSeek V4 Pro API (deepseek/deepseek-v4-pro, DeepSeek-V4-Pro-0813): Pricing & Providers on
  DeepSeek, Tencent Cloud, Baidu, Alibaba Cloud, Streamlake & SiliconFlow, Peak and Off-Peak
  Rates, Cache Pricing, 1M Context, 384K Max Output, Python, JavaScript & cURL Examples,
  Alternatives and FAQ | ZenMux`.
- **Answer first.** Each module's first sentence answers the module's question (what it is /
  what it costs and under which condition / how to call it / whether it fits my task).
- **Numbers = fact `display` strings, verbatim.** No rounding, no "about", no new units.
  Unknown → spec's `missing_value_labels`, plus a gap marker and a `gaps[]` entry saying why.
  `[N]` only as a last resort; it is reported as open.
- **Conditions stay with the number.** A price range, discount, cache price or tier is shown
  with its trigger and the provider/version it applies to — in the same row or detail.
- **Capability states** use the four-value vocabulary; never an icon-only or blank cell.
  Per-endpoint differences → `Varies by provider` + the per-endpoint detail.
- **Use cases:** 2–3, each tied to evidence in the ledger (a capability, a limit, a price
  condition), plus a short "Not ideal for". Fewer is fine; don't pad.
- **Code (M3 or equivalent):** the task semantics must match the entity type — text returns text,
  image config reads an image, video creates a task then polls. Model ID and endpoint come from
  facts. Keys only as env vars. Only protocols confirmed for this endpoint.
- **FAQ:** short answers that restate M2/M4 facts (same display strings). No FAQ-only numbers.
- **Alternatives (compare module):** only with a stated, sourced reason per alternative; prices
  come from the alternative's own facts. Same developer ≠ same task.
- **Links:** real paths only (hub, related models, docs). No `#`, no "click here" anchors.
- No superlatives without a source; no marketing claims the facts don't carry.
- **Voice:** neutral and third person ("ZenMux lists…", "DeepSeek documents…"). No "we/our".

### Sentence rules (Wendy Writes constitution, adapted for model pages)

`lint` = checked by `check_page.py` (blockers fail the check); `review` = checked by the
review step (`references/review.md`); `—` = writer discipline only.

| # | Rule | On a model page | Checked by |
|---|---|---|---|
| 1 | **Answer first** | The first sentence under every H2/H3 answers that heading. No preamble, no restating the heading. A yes/no heading (FAQ "Does it support…?") opens with Yes or No. | review (A1, A3) |
| 2 | **Certainty** | No hedges: might, maybe, perhaps, possibly, probably. Uncertainty is expressed with the missing-value labels and attribution ("DeepSeek documents…"), never with a hedge word. Keep "can/may/could" under 10% of sentences. | lint (B1, B3) |
| 3 | **Exact numbers** | No "many / several / various / a lot" before something countable. Use the fact's number, or name the items. No number in the ledger → a missing label, not a vague word. | lint (B2) |
| 4 | **Literal, domain-precise** | No metaphors or analogies. No "however / moreover / additionally" sentence openers. Precise verbs (route, bill, cache, stream, poll, deploy) instead of make/do/get. | lint (E5, C6), review (E6) |
| 5 | **One fact per sentence** | Short sentences, one fact each; ≤ 30 words. Vary the length (a few short sentences between longer ones); paragraphs ≤ 4 sentences / 90 words. Active voice (passive ≤ 15%). | lint (C4, C5, C7, E3) |
| 6 | **Declaration before condition** | Never open a sentence with If/When-clauses: "Pin the `deepseek` endpoint if you need DeepSeek's own rates", not "If you need…". | lint (A7) |
| 7 | **Bold the answer** | Bold only a specific value or fact (a price, a limit, Yes/No), never the model name or the heading text. Sub-labels are H3s, not bold lines. | lint (F1) |
| 8 | **Link discipline** | Never link the first word of a paragraph. Define a term in plain text before linking it. Anchor text ≈ the target page's title. Same anchor → same page at most 3 times. | lint (F3, F5), review (F6) |
| 9 | **Plurals need examples** | A plural set ("several protocols", "three providers") is followed in the same or next sentence by the named items. | review (C7) |
| 10 | **No invented numbers** | Covered by the page rules and `facts.json`; stricter than Wendy's `[CITE]` rule. | check_page (UNTRACED_NUMBER, QUOTE_NOT_FOUND) |
| 11 | **Entity-initial paragraphs** | Every paragraph's first sentence contains the model name or one of its `entity_aliases` (front matter, e.g. `[V4 Pro]`). Never open a paragraph with It/This/These/They. Tables, code and list items are exempt; an FAQ answer paragraph is not. | lint (C1: pronoun start = blocker, missing name = warning) |
| 12 | **Lists** | Announce the exact count before a content list ("ZenMux lists 3 billing items:"). Every item starts with the same part of speech. Navigation/link lists are exempt from the count. | review (F2) |
| 13 | **Given before new** | Start sentences with something already introduced; put the new information at the end. | review (C3) |
| 14 | **Stay in the module** | Each module covers only its own intent (spec `intent`). Don't repeat another module's content, except FAQ answers restating facts. | review (D1) |
| 15 | **Real tables** | Tables are real Markdown tables (header row, delimiter row, one row per line), never collapsed or bracketed. | — |
| 16 | **Items and questions are H3** | Each FAQ question is an H3 (`### What is the model ID?`) with the answer in the paragraph below; its first sentence ≤ 40 words. Sub-groups inside a module ("Good fits", "Not ideal for", each alternative) are H3s, not bold lines. | — |
| 17 | **Opening paragraph** | The paragraph under the H1 names the model, says what it does and what the page answers (pricing and providers, API usage), in ≤ 3 sentences; its first sentence contains the model name. | lint (G1a: name in H1 and first sentence), review (D2, D8) |
| 18 | **Comparisons are complete** | A comparison names both models, the criterion and the direction ("V4.1 Flash lists a lower input price than V4 Pro on the DeepSeek endpoint"). No bare "better". | review (A5) |
| 19 | **Claims carry evidence** | A claim is followed within 2 sentences by a fact, an example or the mechanism. Superlatives only with a sourced reason. | review (D5, B5) |

Banned phrases (lint E2) include "in today's fast-paced world", "delve", "unlock",
"navigate the landscape", "it's important to note". Write plainly.
