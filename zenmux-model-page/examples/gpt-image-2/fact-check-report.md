# Fact-check report — GPT Image 2 (ZenMux model page)

Method: `references/fact-check.md` (Wendy Writes fact-check protocol). Three independent agents (prices/billing · specs/API/protocols · claims/hidden modules/image-variant/links) worked from the 2026-10-29 snapshots in `../../sources/`. Each re-fetched every live source once. None of them wrote the page. Their raw results are in `fc-prices.json`, `fc-specs.json` and `fc-claims.json`.

**Drift:** none. The ZenMux fee records, ZenMux docs, OpenAI's model page, image guide and pricing page match the snapshots.

**Verdicts in `facts.json`:** 79 VERIFIED, 11 NUANCED, 0 REFUTED, 0 UNVERIFIABLE (90 facts; 4 were added after the check — see below). Each NUANCED fact carries a `note`, and the page wording now matches it.

## The OpenAI price question
OpenAI's pricing page lists gpt-image-2 only under Batch ($4 / $15 / $1 cached image; $2.50 / $0.625 text). Its Standard tab lists only the GPT Image 2.5 models ($8 / $30 / $2; $5 / $1.25). Batch is exactly 50% of Standard on every item. ZenMux's gpt-image-2 rates equal 2.5 Standard, and OpenAI's guide says GPT Image 2 and 2.5 share the output-token price. The page uses ZenMux's rates and makes no claim about OpenAI's Standard tab, so no change was needed.

## Resolved

| Finding | Resolution |
|---|---|
| "Text prompt" and "Cached text input": ZenMux names the fee items only `prompt` and `input_cache_read`, so "text" was inferred | Rows renamed to the ZenMux fee items; "Other cache read" says ZenMux doesn't state which tokens it covers |
| Cached rates presented without OpenAI's caveat | Added OpenAI's statement that GPT Image 2 cached input pricing applies only in the Responses API image tool, not to direct Images API requests; ZenMux's behaviour is Not verified (new fact `price.openai.cache_scope`) |
| "A per-image price is Not published": true for ZenMux only (OpenAI publishes estimates) | "ZenMux publishes no per-image price" (M2, M8) |
| Streaming status "Supported" while OpenAI's model page says Not supported | Status is now Not verified, with both sources stated; the "Showing progress" bullet says to test it first |
| "Edits and masks listed for both providers": provider parameter lists show only streaming for both | Edits are now attributed to ZenMux's Images guide, without a per-provider breakdown |
| 50MB limit, "up to 2 minutes", and the text-placement and layout limits sit in OpenAI's GPT Image 2.5 section | Each is attributed to "OpenAI's guide, in its section on newer GPT Image models"; the page says ZenMux states no file-size limit |
| Sizes: the page omitted ZenMux's experimental caveat | Added: custom sizes are for openai/gpt-image-2 only, larger sizes cost more, and sizes above 2560x1440 are experimental (new facts `size.zenmux.experimental`, `size.zenmux.custom_only`) |
| "Output formats are png, jpeg and webp" presented as exhaustive | "ZenMux's examples of output formats are…" |
| "ZenMux publishes no image completion time": the table shows an Azure Latency of 99.5 s | The page reports the cell (the most recent hourly point, 99,528 ms) and says ZenMux doesn't state whether it is first-token or whole-response time, so it isn't treated as completion time. M5 stays hidden with a corrected reason (new fact `perf.azure.latency`). |
| M3: ZenMux's generation examples use the alias `gpt-image-2` | M3 says so; the examples keep the model-page slug |
| M7: "closest same-task alternative" is unsourced | "another OpenAI image model on ZenMux" |
| M7: per-image estimates also exclude streamed partial images | Added |
| M7: GPT Image 1.5's size range | The page notes that ZenMux lists custom sizes for gpt-image-2 only |
| M9 linked `/google/gemini-3-pro-image-preview`, which is badged Sunset | Link removed |

**Image-variant compliance (claims checker):** sizes and ratios — met. No text TPS standing in for image time — met. Partly met:
- **Reference-image limit:** Not published.
- **Billing items:** caveats added.
- **Token fields:** context and max output are kept because billing is per token, though output is image-only.
- **Real-response example:** not run.

**Links:** 8 of 9 were fine; the sunset link was removed.

## Open items

1. **The plan's acceptance rule for images** requires an example that returns a real image. Nobody has run it, so it's unknown whether `openai/gpt-image-2` or the alias `gpt-image-2` works on `/images/generations`. An unauthenticated POST returned 403, so the route exists. The user chose to skip the live test (2026-10-30), so this rests on ZenMux's answer to questions 8 and 10 in `../../zenmux-questions.md`.
2. **For ZenMux:**
   - which revision each provider serves;
   - the maximum `n` and the maximum number of reference images on the Images protocol;
   - whether `:provider` pinning works on image endpoints;
   - transparent-background support;
   - what the Azure Latency cell measures;
   - whether cache-read rates apply to Images API calls.
3. **OpenAI vs ZenMux on streaming:** the page shows both statements until a test settles it.

## Live API test

Skipped by the user's decision on 2026-10-30. The code example was written from ZenMux's docs and has not been run. The plan's acceptance check ("the example returns a real response") stays open for this page until ZenMux confirms or someone with an account runs it.
