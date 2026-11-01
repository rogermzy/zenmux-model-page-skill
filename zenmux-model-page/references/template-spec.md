# Appendix A — template spec (JSON)

Lives in `plan.md` inside a fenced block whose info string is exactly `json page-template`.
It is the contract the page writer and `check_page.py` read.

```json
{
  "template_id": "zenmux-model-page",
  "page_language": "en",
  "url_pattern": "/{developer}/{model-slug}",
  "title_pattern": "{Entity} API, Pricing & Providers | ZenMux",
  "h1_pattern": "{Entity} API",
  "meta_description_rule": "One sentence: what the model is + where pricing/providers/API example are. No superlatives.",
  "default_endpoint_rule": "M1 prices, M3 code and M4 capabilities describe the same endpoint (front matter default_endpoint).",
  "status_vocabulary": ["Supported", "Not supported", "Not verified", "Varies by provider"],
  "missing_value_labels": {"price": "Not published", "version": "Not verified", "metric": "No data"},
  "entity_variants": {
    "text":  "context/max output, per-token pricing, chat message example; TTFT/TPS only with valid data",
    "image": "sizes/ratios, reference-image limits, billing items as published; example returns an image",
    "video": "duration/resolution, input modes, real billing unit; create-task + poll example; CTA Create",
    "audio": "voices/languages/duration limits and billing unit as the API defines them"
  },
  "modules": [
    {
      "id": "M1",
      "name": "Hero",
      "required": true,
      "h2": null,
      "intent": ["{entity}", "{entity} API"],
      "fields": ["overview", "model_id", "modalities", "context_window", "max_output", "price_summary", "primary_cta"],
      "rules": [
        "Input and output price come from the same available endpoint (default_endpoint).",
        "No valid price -> link 'View provider pricing', never $0."
      ],
      "show_if": null,
      "status_table": false
    },
    {
      "id": "M5",
      "name": "Performance & Availability",
      "required": false,
      "h2": "{Entity} Performance & Availability",
      "intent": [],
      "fields": ["ttft", "throughput", "success_rate", "window", "updated_at"],
      "rules": ["TTFT != total latency; request success rate != time-based uptime."],
      "show_if": "category:performance",
      "status_table": false
    }
  ]
}
```

## Field rules (enforced by `check_plan.py`)

| Field | Rule |
|---|---|
| `template_id` | kebab-case; matches `plan_slug` in front matter |
| `title_pattern`, `h1_pattern` | contain `{Entity}` |
| `modules[].id` | `M1`, `M2`, … unique, consecutive, in page order |
| `modules[].required` | boolean |
| `modules[].h2` | non-empty string pattern (usually contains `{Entity}`; a generic heading such as "Related Models & Guides" is allowed), or `null` (only allowed for M1 — the H1 module) |
| `modules[].show_if` | `null` when required; when conditional, a selector `check_page.py` can evaluate: `category:<name>` (≥1 fact with that category), `facts:<id-prefix>` (≥1 fact whose id starts with the prefix), or `manual:<free-text reason>` (writer decides; the reason must be stated in the marker) |
| `modules[].status_table` | `true` → the first table in the module has capability values in column 2 drawn from `status_vocabulary` |
| `modules[].derived_from` | optional list of module ids (e.g. FAQ `["M2","M4"]`): numbers in this module must also appear in those modules |

Placeholders: `{Entity}` = entity display name. Other `{…}` tokens in patterns are free
(filled from facts / front matter); the checker treats any `{…}` as "one or more characters".
