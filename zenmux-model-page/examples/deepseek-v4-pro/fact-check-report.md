# Fact-check report — DeepSeek V4 Pro (ZenMux model page)

Method: `references/fact-check.md` (Wendy Writes fact-check protocol). Three web-grounded agents ran in parallel (prices · specs/capabilities/routing · performance/claims/links). They worked from the 2026-10-28 snapshots in `../../sources/` and re-fetched every live source once on 2026-10-28/29 with a browser user agent. **No drift** between the snapshots and the live pages.

Verdicts per fact are in `facts.json` (`verdict`, plus `note` on the NUANCED facts). Totals: 72 VERIFIED, 5 NUANCED, 0 REFUTED, 0 UNVERIFIABLE.

## REFUTED in the draft, fixed in the page

| Claim in draft | Finding | Fix |
|---|---|---|
| M5: "P50 latency and throughput … over the last 24 hours" | The table cells are the **latest hourly** P50 values, e.g. the DeepSeek cell 1.04 s is the last hourly point (1044 ms). The medians of the hourly values differ (DeepSeek ≈ 1013 ms / 59.8 tok/s). | Relabelled the columns "Latest-hour P50 …" and rewrote the M5 intro. Fixed the `perf.*` labels and conditions. |

## NUANCED, page reworded

| Item | Finding | Page now says |
|---|---|---|
| DeepSeek endpoint "bills on the same two tiers" | The ZenMux peak bands (business minutes 60–240 and 360–600, weekdays 1–5) line up with DeepSeek's 01:00–04:00 / 06:00–10:00 UTC. ZenMux states no time zone and has no Chinese-public-holiday exception. | "line up with those hours"; the missing time zone and holiday rule are a gap (`time-schedule`), not page text |
| Tencent / Baidu / Alibaba "trigger Not published" | The embedded data shows time-of-day bands. Tencent's bands are DeepSeek's but apply every day; Baidu and Alibaba split at business minute 840. No time zone is given. | "Time-of-day rates; schedule and time zone Not published" |
| `version.deepseek` (0813) | DeepSeek's docs describe api.deepseek.com, not ZenMux's `deepseek` provider. ZenMux does title the model "0813". | Attributed: "DeepSeek documents DeepSeek-V4-Pro-0813 for its own API" |
| Tool calling "on all endpoints" (parameter list) | `tools` appears in all 18 provider × protocol lists. `tool_choice` and `parallel_tool_calls` are missing from some Responses and Messages lists. | Detail narrowed to what each protocol lists |
| `reasoning_effort` "listed for the DeepSeek endpoint" | It is listed on Chat Completions for 5 of the 6 providers (all except Alibaba Cloud). | All 5 named; Alibaba Cloud's alternative parameters noted |
| Structured output "on every ZenMux endpoint" | `response_format` is on Chat Completions for all 6 providers; Responses has it on 5/6 and Messages on 4/6. | Scoped to Chat Completions |
| Use cases ("whole-codebase review", "without switching models"), M7 "the lower-cost DeepSeek model", "the one to use for images", "flagship" as a reason | These go beyond the sources. | Rewritten to the sourced facts only; "flagship" attributed to ZenMux |
| Uptime "No data" | ZenMux charts uptime client-side; the values just weren't in the captured source. | Says exactly that |
| V4.1 Flash price | It is a ZenMux promotion (`pricing_discount` 0.5) with no end date. | Labelled as a promotional rate with no published end date |
| Links | All 8 URLs return 200. `https://zenmux.ai/models` is the full model list, not a DeepSeek page, and the in-page anchor was a guessed slug. | Anchor text "All models on ZenMux"; anchor link removed; Chat link now preselects the model (`?model=deepseek/deepseek-v4-pro`, the link ZenMux itself uses) |
| Source URL | `https://api-docs.deepseek.com/quick_start/pricing` without the trailing slash returns "Your First API Call". | All DeepSeek pricing facts cite `…/quick_start/pricing/`; the bad index entry was removed |

## Open items for ZenMux (not fixable from public sources)

1. **Revision conflict.** ZenMux's own model description says Tencent Cloud and Alibaba Cloud serve the "0731" revision and the other providers serve "0424". The page title says 0813, and DeepSeek's docs list only DeepSeek-V4-Pro-0813 (GA 2026-08-13). The page shows "Not verified" for the five non-DeepSeek providers until ZenMux confirms what each one serves.
2. **Time-of-day pricing.** ZenMux should publish the schedule and time zone for its tiered rates (DeepSeek, Tencent Cloud, Baidu, Alibaba Cloud) and say how Chinese public holidays are billed.
3. **Promotions.** End dates for SiliconFlow's 75% OFF (V4 Pro) and the V4.1 Flash discount.
4. **SiliconFlow cache-read list price.** Listed at $0.44: ten times the $0.044 that DeepSeek, Tencent Cloud, Baidu and Streamlake list, and over three times Alibaba Cloud's $0.127. Worth confirming it isn't a data-entry error.
5. **Performance data.** Uptime values and a 24-hour aggregate aren't in the server-rendered HTML; only the latest hour is. To meet the plan's M5 rule (state the window and sample conditions), ZenMux needs to expose these server-side.
6. **Benchmarks (M6, hidden).** The Artificial Analysis charts expose no version-matched scores in the page source.
7. **DeepSeek is phasing out V4 Pro (found 2026-10-29, after this fact-check).** DeepSeek's 2026/09/10 announcement (https://api-docs.deepseek.com/news/news260910/) says: "Starting at 04:00 UTC on Sept 14, 2026, all deepseek-v4-pro requests will route to V4.1-Flash at V4.1-Flash rates. This will continue until V4.1-Pro launches." It also says "We're phasing out V4-Pro." DeepSeek's pricing page still lists deepseek-v4-pro as DeepSeek-V4-Pro-0813 with its own rates, and ZenMux still lists V4 Pro at $0.66 / $1.32. The page's line "DeepSeek documents DeepSeek-V4-Pro-0813 for its own API" is accurate for the pricing page but leaves out the announcement. **Page updated 2026-10-29:** the hero (M1), M7 and two FAQ answers now carry the announcement, scoped to DeepSeek's own API, with its effect on ZenMux's providers marked Not verified. New facts `alt.deepseek.phaseout`, `alt.deepseek.route` and `alt.deepseek.route_start` are copied from the V4.1 Flash ledger, where the same snapshot was fact-checked. **Still open for ZenMux:** what the `deepseek` endpoint serves today, and whether ZenMux wants a stronger deprecation notice.

## Live API test

Skipped by the user's decision on 2026-10-30. The code example was written from ZenMux's docs and has not been run. The plan's acceptance check ("the example returns a real response") stays open for this page until ZenMux confirms or someone with an account runs it.
