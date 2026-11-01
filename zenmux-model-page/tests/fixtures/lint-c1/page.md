---
template_id: acme-model-page
entity: Acme Model 7.5
entity_type: text
url: /acme/acme-model-7-5
title: Acme Model 7.5 API, Pricing & Providers | AcmeHub
meta_description: Acme Model 7.5 is a fictional text model; this page lists pricing, capabilities and answers.
default_endpoint: acme
checked_date: 2026-01-15
facts: facts.json
---

<!-- module: M1 shown -->
# Acme Model 7.5 API

Acme Model 7.5 is a fictional text model. Input costs $1.11 and output costs $2.22 per million tokens on Acme Cloud, with a 999K context window. See [pricing](/acme/pricing) for details.

<!-- module: M2 shown -->
## Acme Model 7.5 Pricing

It is the cheapest listed endpoint on Acme Cloud.

| Provider | Input | Output |
| :- | :- | :- |
| Acme Cloud | $1.11 | $2.22 |
| Other Cloud | $3.33 | Not published <!-- gap: other-output --> |

<!-- module: M3 shown -->
## Acme Model 7.5 Capabilities

| Capability | Status |
| :- | :- |
| Streaming | Supported |
| Vision | Not supported |

<!-- module: M4 hidden: no performance samples in facts.json; gap: perf-none -->

<!-- module: M5 shown -->
## Frequently Asked Questions

1. **How much does it cost?** Input is $1.11 and output is $2.22 on Acme Cloud.
2. **Does it support streaming?** Supported.

```bash
curl -H "Authorization: Bearer $ACME_API_KEY" https://api.example.test/v1/chat
```
