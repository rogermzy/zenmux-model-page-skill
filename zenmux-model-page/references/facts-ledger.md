# facts.json — the fact ledger

Every number, version, date and capability state on a page traces to one entry here. The page
writer reads this file; it never adds a value to the page that isn't in it.

```json
{
  "entity": "DeepSeek V4 Pro",
  "entity_type": "text",
  "checked_date": "2026-10-19",
  "names": ["DeepSeek V4 Pro", "DeepSeek V3.2", "GPT-5"],
  "endpoints": [
    {"id": "deepseek", "provider": "DeepSeek", "served_version": "0813", "status": "active"},
    {"id": "novita",   "provider": "Novita",   "served_version": "Not verified", "status": "active"}
  ],
  "facts": [
    {
      "id": "price.deepseek.input",
      "category": "price",
      "endpoint": "deepseek",
      "label": "Input price",
      "value": 0.55,
      "unit": "USD / 1M tokens",
      "display": "$0.55",
      "condition": "cache miss",
      "source_url": "https://zenmux.ai/deepseek/deepseek-v4-pro",
      "quote": "exact text copied from the snapshot",
      "checked_at": "2026-10-19",
      "verdict": "UNCHECKED"
    }
  ],
  "gaps": [
    {
      "id": "rev-providers",
      "key": "acme.revision-per-provider",
      "kind": "contradiction",
      "owner": "client",
      "summary": "The site gives two different revisions for the same model",
      "client_url": "https://zenmux.ai/deepseek/deepseek-v4-pro",
      "location": "page title vs model description",
      "evidence": [
        {"source_url": "https://zenmux.ai/deepseek/deepseek-v4-pro", "quote": "exact text, side A"},
        {"source_url": "https://zenmux.ai/deepseek/deepseek-v4-pro", "quote": "exact text, side B"}
      ],
      "searched": [],
      "request": "Show one revision per provider in the provider table and remove the conflicting line.",
      "question": "Which revision does each provider serve today?",
      "priority": "high",
      "status": "open"
    }
  ]
}
```

(Values above are format illustrations, not real prices.)

## Rules

- `names` — every model/product/provider name the page mentions. The checker ignores digits
  inside these names (`V4`, `3.5`), so list names exactly as written on the page.
- `endpoints[].status` — `active` | `disabled`. Disabled endpoints never supply the lowest
  price or a "select" action.
- `endpoint` on a fact — the endpoint id it applies to, or `null` for model-level facts
  (context window as published by the developer, release date).
- `category` — free, but use consistently; `show_if: category:<x>` selectors read it.
  Common: `price`, `spec`, `capability`, `version`, `date`, `performance`, `benchmark`, `limit`.
- `display` — the exact string the page will show (`$0.55`, `128K`, `1,048,576`, `99.2%`,
  `2026-04-24`). Write the page using these strings verbatim. A number may appear in several
  display forms only if each form is its own fact or listed in `aliases: [...]`.
- Capability facts use `display` from the spec's `status_vocabulary`
  (`Supported` / `Not supported` / `Not verified` / `Varies by provider`).
- `source_url` must have a snapshot in `sources/index.json`; `quote` must be findable verbatim
  in that snapshot's text. No quote → the fact is `Not verified`, not a number.
- `verdict` — `UNCHECKED` until fact-check; then `VERIFIED` | `NUANCED` | `REFUTED` |
  `UNVERIFIABLE`. A page using a REFUTED fact fails `check_page.py`.
- Benchmarks: record `version`, `mode` (reasoning on/off), `source_url`, `date` in `condition`.
  No version-matched source → no fact → M6 hidden.
- Performance: record the window and sample condition in `condition`. No samples → no fact.

## gaps

A gap is anything the page writer needed and could not state as a fact: the client's site
doesn't publish it, says it two different ways, disagrees with the model developer's docs, shows
a value that looks wrong, or only draws it with JavaScript (invisible in the HTML search engines
read first). Each gap is logged once here; every page line that shows `Not verified` /
`Not published` / `No data` points to it with `<!-- gap: id -->` (see page-format.md).
`scripts/site_fixes.py` collects the client-owned gaps from all pages into
`site-fix-requests.md`: the change requests for the ZenMux site team.

| Field | Rule |
|---|---|
| `id` | Unique within this facts.json; used by page markers. |
| `key` | Optional. The same `key` on several pages merges them into one request (e.g. a site-wide pricing-schedule gap). |
| `kind` | `missing` · `contradiction` (the client's site disagrees with itself) · `upstream_conflict` (client vs the model developer's docs) · `suspected_error` (an outlier value worth confirming) · `not_in_html` (data only rendered client-side). |
| `owner` | `client`: the client's site should change or the client must answer. `external`: nobody publishes it (e.g. a task-quality comparison); listed as FYI, no request. |
| `summary` | One plain sentence a non-specialist understands. |
| `client_url` | Owner client: the client page that needs the change. |
| `location` | Where on that page (tab, table, section, embedded data). |
| `evidence` | `[{source_url, quote}]`, quotes verbatim from snapshots (checked like fact quotes). `contradiction` and `upstream_conflict` need both sides (≥ 2); `suspected_error` ≥ 1. |
| `searched` | Snapshotted URLs that were checked and don't have it. Required for `missing` and `not_in_html`. |
| `request` | The change we ask the client to make, as an instruction to their content/dev team. |
| `question` | What the client must tell us before the fix can be written. Owner client needs `request` and/or `question`. |
| `priority` | `high` (wrong or contradictory price/ID/version on a live page) · `medium` · `low`. |
| `status` | `open` → `sent` → `resolved`. On `resolved`, update the fact and the page, and drop the marker. |

Rules: never resolve a gap by picking a side. A contradiction stays `Not verified` on the page
until the client answers. A gap is not a fact: nothing in `gaps[]` may supply a number to the page.
