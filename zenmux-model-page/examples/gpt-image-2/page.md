---
template_id: zenmux-model-page
entity: GPT Image 2
entity_type: image
url: /openai/gpt-image-2
title: GPT Image 2 API, Pricing & Providers | ZenMux
meta_description: GPT Image 2 on ZenMux: token-based image pricing on the OpenAI and Azure providers, image size and edit limits, and a copyable image-generation example for model ID openai/gpt-image-2.
default_endpoint: auto
checked_date: 2026-10-29
facts: facts.json
---

<!-- module: M1 shown -->
# GPT Image 2 API

GPT Image 2 is an image generation and editing model from OpenAI; ZenMux describes it as OpenAI's next-generation image generation model. It takes text and image input and returns an image. On ZenMux you call it with one API key through two providers, OpenAI and Azure.

| | |
| :- | :- |
| Model ID | `openai/gpt-image-2` (ZenMux also lists the alias `gpt-image-2`) <!-- gap: model-id --> |
| Modalities | Text and image in, image out |
| Context window | 10K tokens (ZenMux provider table) |
| Max output | Azure: 10,000 tokens; OpenAI: Not published <!-- gap: max-output-openai --> |
| Image pricing | $8 per million image input tokens; $30 per million image output tokens |
| Prompt pricing | $5 per million tokens (ZenMux fee item `prompt`) |
| Sizes | Examples in ZenMux's guide: `1024x1024`, `1536x1024`, `1024x1536`; other sizes within OpenAI's limits (see the capabilities section) |
| Reference images | Supported for edits; the maximum number of reference images is Not published <!-- gap: max-reference-images --> |
| Published on ZenMux | 2026-04-22 |

Both providers list the same prices. The revision each provider serves is Not verified, and default routing can send a request to either provider, so the served revision can vary by request. ZenMux lists the aliases `gpt-image-2` and `gpt-image-2-2026-04-21`; OpenAI lists the snapshot `gpt-image-2-2026-04-21`. See the pricing table below. <!-- gap: revision, model-id -->

[Get your API key](/docs/guide/quickstart.html) · [Read the Image Studio guide](/docs/guide/studio/studio-image.html)

<!-- module: M2 shown -->
## GPT Image 2 Pricing & Providers

GPT Image 2 is billed per token on ZenMux: $30 per million image output tokens and $8 per million image input tokens, at the same rates on both providers. ZenMux's `prompt` fee item is $5 per million tokens. ZenMux publishes no per-image price. <!-- gap: per-image-price -->

All prices are USD per million tokens. ZenMux's provider table shows Input, Output and Cache read; they correspond to the image input, image output and cached image input rates below. The `prompt` and `input_cache_read` rates appear only in ZenMux's page data.

| Billing item | Rate | What it covers |
| :- | :- | :- |
| Image output | $30 | Tokens of the generated image |
| Image input | $8 | Tokens of input images, such as reference images for an edit |
| Cached image input | $2 | Listed as "Cache read" in the provider table |
| Prompt | $5 | ZenMux fee item `prompt` |
| Other cache read | $1.25 | ZenMux fee item `input_cache_read`; ZenMux doesn't say which tokens it covers |

Cache write: Not published for either provider. OpenAI says that for GPT Image 2, cached input pricing applies only to the image generation tool in its Responses API, not to direct Images API requests. Whether ZenMux bills cache reads on its Images endpoints is Not verified. <!-- gap: cache-write, cache-read-images-api -->

| Provider | Served version | Image input | Image output | Cached image input | Context | Max output |
| :- | :- | :- | :- | :- | :- | :- |
| OpenAI (`openai`) | Not verified <!-- gap: revision --> | $8 | $30 | $2 | 10K | Not published <!-- gap: max-output-openai --> |
| Azure (`azure`) | Not verified <!-- gap: revision --> | $8 | $30 | $2 | 10K | 10,000 |

**Choosing a provider.** Without a provider suffix, ZenMux applies its default routing strategy: "Performance first: Sort by first token latency from low to high". It switches to another provider if the first is unavailable, so the provider and its revision can differ between requests.

ZenMux's provider routing guide documents pinning a provider with `model_slug:provider_slug`. That guide shows the syntax on a chat model, and nobody has verified it on the image endpoints ([provider routing docs](/docs/guide/advanced/provider-routing.html)). <!-- gap: provider-pin-image -->

<!-- module: M3 shown -->
## How to Use GPT Image 2 via API

Send a request to `https://zenmux.ai/api/v1/images/generations` with the model ID `openai/gpt-image-2` and your ZenMux API key. GPT Image models return the image as base64 in `data[0].b64_json`; decode it and save it as a file. This is the OpenAI Images protocol, so the OpenAI SDK works with the base URL pointed at ZenMux. The examples use the model-page slug; ZenMux's Images guide uses the alias `gpt-image-2` in its generation examples. <!-- gap: model-id -->

```bash
curl https://zenmux.ai/api/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ZENMUX_API_KEY" \
  -d '{
    "model": "openai/gpt-image-2",
    "prompt": "A cute baby sea otter",
    "n": 1,
    "size": "1024x1024"
  }' | jq -r '.data[0].b64_json' | base64 --decode > output.png
```

```python
import base64
import os
from openai import OpenAI

client = OpenAI(base_url="https://zenmux.ai/api/v1", api_key=os.environ["ZENMUX_API_KEY"])
img = client.images.generate(
    model="openai/gpt-image-2",
    prompt="A cute baby sea otter",
    n=1,
    size="1024x1024",
)
with open("output.png", "wb") as f:
    f.write(base64.b64decode(img.data[0].b64_json))
```

```javascript
import OpenAI from "openai";
import { writeFile } from "fs/promises";

const client = new OpenAI({ baseURL: "https://zenmux.ai/api/v1", apiKey: process.env.ZENMUX_API_KEY });
const img = await client.images.generate({
  model: "openai/gpt-image-2",
  prompt: "A cute baby sea otter",
  n: 1,
  size: "1024x1024",
});
await writeFile("output.png", Buffer.from(img.data[0].b64_json, "base64"));
```

For edits, post one or more reference images to `https://zenmux.ai/api/v1/images/edits` (add a mask for a local edit). GPT Image 2 can also be called through the Google Gemini (Vertex AI) protocol with `generate_images`. Both providers list the `images` and `imagen` APIs. Full guides: [OpenAI Images protocol](/docs/guide/advanced/openai-image-generation.html), [Google Gemini protocol](/docs/guide/advanced/image-generation.html) and the [ZenMux Quickstart](/docs/guide/quickstart.html).

<!-- module: M4 shown -->
## GPT Image 2 Capabilities & Use Cases

GPT Image 2 takes text and images and returns an image; it does not return text. ZenMux lists streaming parameters for both providers. Its Images guide documents reference-image and mask edits on this protocol, without a per-provider breakdown. OpenAI's model page lists function calling and structured outputs as Not supported.

| Capability | Status | Detail |
| :- | :- | :- |
| Image output | Supported | Output modality is image |
| Image input | Supported | ZenMux lists text and image input |
| Text-to-image, OpenAI Images protocol | Supported | `/images/generations`; listed for both providers |
| Reference-image generation and edits, OpenAI Images protocol | Supported | `images.edit` takes one or more reference images; the maximum count is Not published. OpenAI's guide, in its section on newer GPT Image models, says the image to edit and the mask must be under 50MB; ZenMux states no limit <!-- gap: max-reference-images --> |
| Mask edits | Supported | The image and mask should use the same format and dimensions; ZenMux recommends an alpha channel for a PNG mask |
| Streaming partial images | Not verified | ZenMux lists `stream` and `partial_images` for both providers; `partial_images` set to 0 returns only the final image, 1 to 3 returns partial images. OpenAI's model page lists Streaming as Not supported <!-- gap: streaming --> |
| Google Gemini (Vertex AI) protocol | Supported | `generate_images`; images per request 1-10 on this protocol |
| Reference images on the Gemini protocol | Varies by provider | `referenceImages` is listed for OpenAI; Azure lists `sampleCount` and `outputOptions` only, so Azure is Not verified <!-- gap: azure-gemini-ref-images --> |
| Transparent background | Not verified | `background` is listed on the Images protocol, but ZenMux says exact support depends on the model; ZenMux's Gemini-protocol table marks `background` as not supported <!-- gap: transparent-background --> |
| Function calling, structured outputs | Not supported | Per OpenAI's model page |
| Reasoning | Not supported | ZenMux marks reasoning as unsupported on both protocols |

**Sizes and ratios.** ZenMux's Images guide gives `1024x1024`, `1536x1024` and `1024x1536` as examples "or other sizes supported by the model". ZenMux's Gemini-protocol guide says it forwards `imageSize` and `quality` to the underlying API without validation.

OpenAI's guide, in its Earlier GPT Image models section, says gpt-image-2 accepts any size that meets four rules. The longest edge is at most 3840 px. Both edges are multiples of 16 px, and the long-to-short ratio is at most 3:1. Total pixels fall between 655,360 and 8,294,400. It lists `2048x2048` (2K square) and `3840x2160` (4K landscape) among popular sizes, and `auto` is the default.

ZenMux's Gemini-protocol guide applies the same limits to custom sizes, which it supports for openai/gpt-image-2 only. It adds that larger sizes cost more and that sizes above 2560x1440 are experimental and may produce inconsistent results.

**Quality and format.** ZenMux lists quality values low, medium, high and auto; OpenAI lists low, medium and high for gpt-image-2, with auto as the default. ZenMux's examples of output formats are png, jpeg and webp, and compression runs from 0 to 100 for jpeg and webp.

**Images per request.** The Images protocol lists the `n` parameter, and the maximum is Not published there. The Gemini protocol guide gives a range of 1-10. <!-- gap: max-n -->

**Completion time.** ZenMux's provider table shows a Latency of 99.5 s for Azure, its most recent hourly value, and no figure for OpenAI. ZenMux doesn't say whether that cell is time to first token or whole response time, so this page doesn't treat it as image completion time. OpenAI's guide, in its section on newer GPT Image models, says complex prompts may take up to 2 minutes to process. <!-- gap: azure-latency -->

**Context.** ZenMux's provider table lists a context of 10K tokens for both providers. Billing is per token, as in the pricing section, so the context field and the token rates still apply to this image model.

OpenAI's guide is written around its newer GPT Image 2.5 models; the gpt-image-2 size and quality details above come from its Earlier GPT Image models section. Checked on 2026-10-29 against ZenMux's model page and docs and OpenAI's model page and image guide.

**Good fits**

- **Text prompt to image.** `images.generate` returns a base64 image from a prompt alone.
- **Combining reference images.** ZenMux's guide shows several product photos combined into one image, a gift basket.
- **Local edits.** With a mask, ZenMux's guide edits one region of a photo, for example adding a flamingo to a pool.
- **Showing progress.** ZenMux lists partial-image streaming for a more real-time generation experience. OpenAI's model page lists streaming as Not supported for this model, so test it first. <!-- gap: streaming -->

**Not ideal for**

- **Text, tool calls or structured output in the response.** The output is an image, and OpenAI lists function calling and structured outputs as Not supported.
- **Exact text placement or strict layouts.** OpenAI's guide, in its section on newer GPT Image models, says GPT Image models can still struggle with precise text placement and clarity, and with placing elements precisely in layout-sensitive compositions.
- **Transparent-background assets.** Support for this model is Not verified. <!-- gap: transparent-background -->

<!-- module: M5 hidden: no image completion time for this model; ZenMux's table has a Latency and a TPS cell for Azure only, and does not say whether that Latency is first-token or whole-response time; gap: azure-latency, perf-charts-not-in-html -->

<!-- module: M6 hidden: no version-matched benchmark source captured; ZenMux's Artificial Analysis charts expose no scores in the page source; gap: benchmarks-no-scores -->

<!-- module: M7 shown: sourced price comparison with GPT Image 1.5, whose ZenMux page is snapshotted -->
## Compare GPT Image 2 Alternatives

GPT Image 1.5 is another OpenAI image model on ZenMux, and the cost gap depends on size and quality ([GPT Image 1.5 on ZenMux](/openai/gpt-image-1.5)). On ZenMux its image output rate is $32 per million tokens against $30 for GPT Image 2, with the same image input rate.

| Model | ZenMux image input / output | OpenAI per-image estimate at 1024x1024 (low / medium / high) | OpenAI per-image estimate at 1536x1024 (low / medium / high) | Context |
| :- | :- | :- | :- | :- |
| GPT Image 2 | $8 / $30 | $0.006 / $0.053 / $0.211 | $0.005 / $0.041 / $0.165 | 10K |
| GPT Image 1.5 | $8 / $32 | $0.009 / $0.034 / $0.133 | $0.013 / $0.05 / $0.2 | 10K |

Prices are USD, and ZenMux rates are per million tokens. The per-image figures are OpenAI's own estimates from its image generation guide. They use OpenAI's rates and leave out text and image input tokens and streamed partial images. They are not ZenMux prices, and a ZenMux per-image price is Not published. <!-- gap: per-image-price -->

**Choose GPT Image 1.5 when** you generate at 1024x1024 in medium or high quality. OpenAI's estimates are lower there. **Choose GPT Image 2 when** you generate at low quality or at 1536x1024. Its estimates are lower in the other four combinations listed, and OpenAI documents arbitrary sizes within its limits for it.

ZenMux's Gemini-protocol guide lists custom sizes for openai/gpt-image-2 only; the size range for GPT Image 1.5 is Not verified in the sources checked. A quality comparison between the two models is also Not verified, so test both on your own prompts. <!-- gap: gpt15-size-range, quality-comparison -->

<!-- module: M8 shown -->
## GPT Image 2 FAQ

**How much does GPT Image 2 cost?**
$30 per million image output tokens and $8 per million image input tokens on both providers. ZenMux's `prompt` fee item adds $5 per million tokens. ZenMux publishes no per-image price. <!-- gap: per-image-price -->

**What is the model ID?**
`openai/gpt-image-2`; ZenMux also lists the alias `gpt-image-2`. <!-- gap: model-id -->

**Which revision will I get?**
Not verified for either provider. Default routing can send requests to either one, so the revision can vary. <!-- gap: revision -->

**What image sizes can I request?**
`1024x1024`, `1536x1024` and `1024x1536` are the examples in ZenMux's guide. OpenAI documents any size with edges up to 3840 px, both edges multiples of 16 px, a ratio up to 3:1 and total pixels between 655,360 and 8,294,400. ZenMux calls sizes above 2560x1440 experimental.

**Can I edit images or use reference images?**
Yes, through `images.edit` on the OpenAI Images protocol, with an optional mask. The maximum number of reference images is Not published. OpenAI's guide, in its section on newer GPT Image models, says the image to edit and the mask must be under 50MB; ZenMux states no limit. <!-- gap: max-reference-images -->

**What is the context window?**
10K tokens in ZenMux's provider table, for both providers.

**Does it support function calling or structured output?**
No. OpenAI's model page lists both as Not supported.

**Which provider should I choose?**
Prices are the same on both. Leave the suffix off to use ZenMux's default routing, or see the pricing section for pinning.

<!-- module: M9 shown -->
## Related Models & Guides

- [All models on ZenMux](https://zenmux.ai/models)
- [GPT Image 1.5](/openai/gpt-image-1.5), compared above
- [Qwen Image 2.0](/qwen/qwen-image-2.0), which ZenMux's Gemini-protocol guide lists for `generate_images`
- [OpenAI Images protocol guide](/docs/guide/advanced/openai-image-generation.html)
- [Google Gemini protocol guide](/docs/guide/advanced/image-generation.html)
- [Studio guide for images](/docs/guide/studio/studio-image.html)
- [Provider routing](/docs/guide/advanced/provider-routing.html)
- [ZenMux Quickstart](/docs/guide/quickstart.html)

[Get your API key](/docs/guide/quickstart.html)
