---
template_id: zenmux-model-page
entity: DeepSeek V4 Pro
entity_type: text
url: /deepseek/deepseek-v4-pro
title: DeepSeek V4 Pro API (deepseek/deepseek-v4-pro, DeepSeek-V4-Pro-0813): Pricing & Providers on DeepSeek, Tencent Cloud, Baidu, Alibaba Cloud, Streamlake & SiliconFlow, Peak and Off-Peak Rates, Cache Pricing, 1M Context, 384K Max Output, Python, JavaScript & cURL Examples, Alternatives and FAQ | ZenMux
meta_description: DeepSeek V4 Pro (model ID deepseek/deepseek-v4-pro) is DeepSeek's open-weight Mixture-of-Experts text model with 1.6 trillion total parameters and 49 billion activated per token. On ZenMux it runs on DeepSeek, Tencent Cloud, Baidu, Alibaba Cloud, Streamlake and SiliconFlow: compare their input, output and cache-read prices with peak and off-peak conditions, check the 1M context window and 384K max output, see which revision each provider serves, read DeepSeek's V4 Pro phase-out notice, compare alternatives, and copy a Chat Completions example in Python, JavaScript or cURL.
default_endpoint: deepseek
checked_date: 2026-10-28
facts: facts.json
---

<!-- module: M1 shown -->
# DeepSeek V4 Pro API

DeepSeek V4 Pro is an open-weight Mixture-of-Experts text model with 1.6 trillion total parameters and 49 billion activated per token; ZenMux describes it as DeepSeek's flagship. On ZenMux you call it with one API key and choose between six providers.

| | |
| :- | :- |
| Model ID | `deepseek/deepseek-v4-pro` |
| Modalities | Text in, text out |
| Context window | 1M tokens |
| Max output | 384K tokens |
| Price on the DeepSeek endpoint | Input $0.66 off-peak / $1.32 peak; output $1.98 off-peak / $3.96 peak, per million tokens |
| First preview release | 2026-04-24 |

Different providers may serve different revisions. DeepSeek's pricing page lists DeepSeek-V4-Pro-0813 for its own API; the revision on the other providers is Not verified — see the pricing table below. <!-- gap: revision -->

**DeepSeek is phasing out V4 Pro.** From 04:00 UTC on Sept 14, 2026, DeepSeek routes deepseek-v4-pro requests on its own API to V4.1 Flash, billed at V4.1 Flash rates. DeepSeek says this lasts until V4.1 Pro launches. Whether this changes what the providers on ZenMux serve is Not verified. <!-- gap: phaseout -->

[Get your API key](/docs/guide/quickstart.html) · [Try it in Chat](https://zenmux.ai/platform/chat?model=deepseek/deepseek-v4-pro)

<!-- module: M2 shown -->
## DeepSeek V4 Pro Pricing & Providers

On the DeepSeek endpoint, DeepSeek V4 Pro costs $0.66 per million input tokens and $1.98 per million output tokens at the off-peak rate. The peak rate is $1.32 and $3.96.

DeepSeek publishes off-peak rates at half of peak, with peak hours 01:00–04:00 and 06:00–10:00 UTC, Monday through Friday, excluding Chinese public holidays. ZenMux lists the same two rates for the DeepSeek endpoint, with weekday peak bands that line up with those hours. ZenMux does not state the time zone, or whether Chinese public holidays bill at the off-peak rate. <!-- gap: time-schedule -->

All prices are USD per million tokens. Where a cell shows two prices, the first is the lower rate and the second the higher rate.

| Provider | Served version | Input | Output | Cache read | Context | Price condition |
| :- | :- | :- | :- | :- | :- | :- |
| DeepSeek (`deepseek`) | DeepSeek-V4-Pro-0813 (per DeepSeek docs) | $0.66 / $1.32 | $1.98 / $3.96 | $0.022 / $0.044 | 1M | Off-peak / peak; weekday peak bands match DeepSeek's UTC hours |
| Tencent Cloud (`tencent-cloud`) | Not verified | $0.66 / $1.32 | $1.98 / $3.96 | $0.022 / $0.044 | 1M | Time-of-day rates; schedule and time zone Not published <!-- gap: revision, time-schedule --> |
| Baidu (`baidu`) | Not verified | $0.66 / $1.32 | $1.98 / $3.96 | $0.022 / $0.044 | 1M | Time-of-day rates; schedule and time zone Not published <!-- gap: revision, time-schedule --> |
| Alibaba Cloud (`alibaba`) | Not verified | $0.636 / $1.272 | $1.908 / $3.816 | $0.064 / $0.127 | 1M | Time-of-day rates; schedule and time zone Not published <!-- gap: revision, time-schedule --> |
| Streamlake (`streamlake`) | Not verified | $1.32 | $3.96 | $0.044 | 1M | Single rate <!-- gap: revision --> |
| SiliconFlow (`siliconflow`) | Not verified | $0.33 (list $1.32) | $0.99 (list $3.96) | $0.11 (list $0.44, as listed) | 1M | 75% OFF promotion; end date Not published <!-- gap: revision, promo-siliconflow, sf-cache-read --> |

Cache write: Not published for any provider. Max output is 384K on every endpoint. <!-- gap: cache-write -->

**Choosing a provider.** Without a provider suffix, ZenMux routes each request "performance first": it sorts providers by first-token latency and switches if the original provider is unavailable. The provider, revision and price can therefore differ between requests. To pin a provider, append its slug to the model ID, for example `deepseek/deepseek-v4-pro:deepseek` ([provider routing docs](/docs/guide/advanced/provider-routing.html)).

<!-- module: M3 shown -->
## How to Use DeepSeek V4 Pro via API

Send a Chat Completions request to `https://zenmux.ai/api/v1` with the model ID `deepseek/deepseek-v4-pro` and your ZenMux API key. The same model also accepts the OpenAI Responses protocol at the same base URL and the Anthropic Messages protocol at `https://zenmux.ai/api/anthropic`.

```bash
curl https://zenmux.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $ZENMUX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek/deepseek-v4-pro",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

```python
import os
from openai import OpenAI

client = OpenAI(base_url="https://zenmux.ai/api/v1", api_key=os.environ["ZENMUX_API_KEY"])
response = client.chat.completions.create(
    model="deepseek/deepseek-v4-pro",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

```javascript
import OpenAI from "openai";

const client = new OpenAI({ baseURL: "https://zenmux.ai/api/v1", apiKey: process.env.ZENMUX_API_KEY });
const completion = await client.chat.completions.create({
  model: "deepseek/deepseek-v4-pro",
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(completion.choices[0].message.content);
```

To pin the DeepSeek endpoint, use `"model": "deepseek/deepseek-v4-pro:deepseek"`. Full setup: [ZenMux Quickstart](/docs/guide/quickstart.html).

<!-- module: M4 shown -->
## DeepSeek V4 Pro Capabilities & Use Cases

DeepSeek V4 Pro takes text and returns text. Tool calling and a thinking mode are available on every ZenMux provider, and structured output through `response_format` on Chat Completions. It does not accept image input.

| Capability | Status | Detail |
| :- | :- | :- |
| Text input and output | Supported | Context window 1M; max output 384K |
| Image input | Not supported | Text-only (DeepSeek docs; ZenMux lists text input) |
| Streaming | Supported | All providers |
| Tool calling | Supported | `tools` on all providers and protocols; `tool_choice` and `parallel_tool_calls` on Chat Completions for all providers |
| Structured output | Supported | `response_format` on Chat Completions for all providers |
| Reasoning (thinking mode) | Supported | All providers, all three protocols |
| `reasoning_effort` parameter | Varies by provider | On Chat Completions for DeepSeek, Streamlake, Baidu, SiliconFlow and Tencent Cloud; Alibaba Cloud lists `enable_thinking` and `thinking_budget` instead |
| Chat Completions, Responses, Anthropic Messages | Supported | All providers |

**Good fits**

- **Long inputs and long outputs.** The 1M-token context window and 384K max output let one request carry a very long input and return a long answer.
- **Agents.** ZenMux lists autonomous agents among the model's design targets, and tool calling and thinking mode are both available.
- **Jobs you can schedule.** On the DeepSeek endpoint, work run outside DeepSeek's published peak hours is billed at the off-peak rate, half of peak.

**Not ideal for**

- **Image or screenshot input.** DeepSeek V4 Pro is text-only; [DeepSeek V4.1 Flash](/deepseek/deepseek-v4.1-flash) accepts image input.

<!-- module: M5 shown -->
## DeepSeek V4 Pro Performance & Availability

ZenMux's provider table shows the P50 time to first token and P50 throughput for the most recent hour of live gateway traffic. Its charts plot the hourly values over 24 hours or a week.

These figures date from 2026-10-28. They change every hour. Time to first token is not total response time.

| Provider | Latest-hour P50 time to first token | Latest-hour P50 throughput |
| :- | :- | :- |
| DeepSeek | 1.04 s | 70.2 tok/s |
| SiliconFlow | 2.13 s | 28.2 tok/s |
| Baidu | 2.27 s | 46.1 tok/s |
| Streamlake | 2.85 s | 37.5 tok/s |
| Tencent Cloud | 4.14 s | 52.9 tok/s |
| Alibaba Cloud | 4.16 s | 33.1 tok/s |

The live ZenMux page charts uptime (request success rate). Its values were not in the page source we captured, so this page doesn't show them. <!-- gap: perf-uptime -->

<!-- module: M6 hidden: no version-matched benchmark source captured; ZenMux's Artificial Analysis charts did not expose scores in the page source; gap: benchmarks -->

<!-- module: M7 shown: sourced price and image-input trade-off vs DeepSeek V4.1 Flash -->
## Compare DeepSeek V4 Pro Alternatives

DeepSeek V4.1 Flash costs less than DeepSeek V4 Pro on the DeepSeek endpoint and accepts image input, which DeepSeek V4 Pro does not ([V4.1 Flash on ZenMux](/deepseek/deepseek-v4.1-flash)).

| Model | Input (DeepSeek endpoint) | Output (DeepSeek endpoint) | Image input | Choose it when |
| :- | :- | :- | :- | :- |
| DeepSeek V4 Pro | $0.66 / $1.32 | $1.98 / $3.96 | Not supported | You want the larger model (1.6 trillion total parameters) and text input is enough |
| DeepSeek V4.1 Flash | $0.075 / $0.15 (ZenMux promotional rate; list $0.15 / $0.3) | $0.3 / $0.6 (list $0.6 / $1.2) | Supported | Cost matters most, or the task includes images |

DeepSeek also says it is phasing out V4 Pro. From 04:00 UTC on Sept 14, 2026, deepseek-v4-pro requests on DeepSeek's own API route to V4.1 Flash at V4.1 Flash rates. This lasts until V4.1 Pro launches. How this applies to the providers on ZenMux is Not verified. <!-- gap: phaseout -->

Prices are USD per million tokens, lower rate / higher rate. The V4.1 Flash promotion has no published end date. <!-- gap: promo-flash --> A task-quality comparison between the two models is Not verified in the sources checked; test both on your own prompts. <!-- gap: quality -->

<!-- module: M8 shown -->
## DeepSeek V4 Pro FAQ

**How much does DeepSeek V4 Pro cost?**
On the DeepSeek endpoint: $0.66 input and $1.98 output per million tokens at the off-peak rate, $1.32 and $3.96 at the peak rate. Other providers' prices and conditions are in the pricing table above.

**What is the model ID?**
`deepseek/deepseek-v4-pro`. Add a provider suffix such as `:deepseek` to pin one provider.

**Which revision will I get?**
DeepSeek's pricing page lists DeepSeek-V4-Pro-0813 for its own API. DeepSeek has also announced that it routes deepseek-v4-pro requests on its own API to V4.1 Flash (see the note at the top of this page). Other providers' revisions are Not verified, and default routing can send requests to any of them. <!-- gap: revision, phaseout -->

**What is the context window?**
1M tokens, with a max output of 384K tokens.

**Does it support tool calling and structured output?**
Yes — tool calling is Supported on every provider, and structured output is Supported through `response_format` on Chat Completions.

**Which provider should I choose?**
Pin `deepseek` to use the DeepSeek endpoint, whose weekday rate bands line up with DeepSeek's published peak hours. Whether DeepSeek's announced routing of deepseek-v4-pro to V4.1 Flash affects this endpoint is Not verified. <!-- gap: phaseout --> Leave the suffix off to let ZenMux route by first-token latency.

<!-- module: M9 shown -->
## Related Models & Guides

- [All models on ZenMux](https://zenmux.ai/models)
- [DeepSeek V4.1 Flash](/deepseek/deepseek-v4.1-flash) — lower-cost DeepSeek model with image input
- [DeepSeek V3.2](/deepseek/deepseek-v3.2)
- [ZenMux Quickstart](/docs/guide/quickstart.html)
- [Provider routing](/docs/guide/advanced/provider-routing.html)
- [Tool calls](/docs/guide/advanced/tool-calls.html)
- [Reasoning models](/docs/guide/advanced/reasoning.html)

[Get your API key](/docs/guide/quickstart.html)
