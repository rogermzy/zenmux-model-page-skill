# page.md — layout and writing rules

```markdown
---
template_id: zenmux-model-page
entity: DeepSeek V4 Pro
entity_type: text
url: /deepseek/deepseek-v4-pro
title: DeepSeek V4 Pro API, Pricing & Providers | ZenMux
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
  facts.json, or `auto` for automatic routing), `checked_date`, `facts`.
- `title` matches `title_pattern`; the only `#` H1 matches `h1_pattern` and sits in M1.
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
