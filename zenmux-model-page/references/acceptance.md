# Acceptance review (step 9)

The writing review (`review.md`) judges sentences and the fact-check (`fact-check.md`) judges
facts. This review answers what neither covers: does the finished page meet the acceptance rules
in `plan.md` Part 4 (开发实施与验收) for its model type, does it hold together, and is it on par
with the matching example page? The result is `acceptance.json`. `check_page.py` reads it and
fails the page on any failed blocker item.

## Who reviews

Someone other than the writer, in a fresh context: a separate sub-task, ideally on a different
model family from the writer; without sub-tasks, a separate pass after the writing review that
reads the files cold. It is a separate run from the writing review because it needs inputs the
writing reviewer must not see. Give the reviewer only:

1. the reviewer prompt below;
2. `plan.md` (Part 4 and appendix A are the rules; the reviewer reads the row for the page's type);
3. the page's `page.md`, `facts.json` and `fact-check-report.md`;
4. the matching example's `page.md`: `examples/deepseek-v4-pro/` for text, `examples/gpt-image-2/`
   for image. Video and audio have no example yet: use the text example for structure only, and
   answer G10 against the plan alone.

## Checklist

Every item for the page's `entity_type` must be answered (`ACCEPT_INCOMPLETE` otherwise). The
severity is fixed here and in `check_page.py` (`ACCEPT_ITEMS`); the reviewer doesn't set it.

### All model types

| ID | Severity | Requirement | Plan source |
|---|---|---|---|
| G1 | blocker | The H1 is exactly "{Entity} API". The title starts with "{Entity} API" and ends with "\| ZenMux". The title, meta description, H1 and opening paragraph name the same model, and the title and meta description list only things the page answers. | Google SEO 验收 1; title/meta rule |
| G2 | blocker | M1's input and output price come from one endpoint, which the page names (or states that auto-routing chooses it). That endpoint's prices are identical in M1, M2 and the FAQ. M3's model ID and M4's capabilities match that endpoint, or are scoped per provider or protocol. | M1 rules; 选择 provider 后价格一致 |
| G3 | blocker | When providers serve, or may serve, different revisions, the page never presents one revision as the version for all providers, and the per-provider revision sits in M2. | M1 rule; 版本提示 |
| G4 | blocker | No `$0`, `100%`, empty chart or generic leaderboard stands in for missing data. A value with no source shows the template's label in its table cell. A conditional module with no qualifying facts is hidden. | 缺失数据规则; hidden beats empty |
| G5 | blocker | Nothing on the page contradicts anything else on the page: a sentence, table, code sample or FAQ answer that a number or statement elsewhere on the page disproves fails. Quote both sides. | 同页信息一致 |
| G6 | blocker | Primary CTA is "Get API Key". Secondary CTA by type: text → Try Model / Chat; image → Try API / Create, never Chat; video → Create; audio → the task's own action, never Chat. | M1 rule; type table |
| G7 | blocker | M3's example uses the request shape for this model type (messages for text, the Images API for image, create task + query result for video, the audio API for audio), reads the key from `$ZENMUX_API_KEY`, contains no real key, and uses the model ID shown in M1 (or M3 explains the alias it uses). | 匿名可读可复制，无密钥泄露; type table |
| G8 | warning | Links are real URLs with accurate anchors (model names or topics, never "click here"). M9 picks models with the same output task first, then the same series, and links no model that the page's data marks Sunset or unavailable. | M9 rule; 内链 |
| G9 | warning | Each shown module answers its spec `intent` with information specific to this model; a paragraph that would fit any model unchanged fails. | Google SEO 验收 1 (信息价值) |
| G10 | warning | On par with the example: every question the example page answers (what the model is, price and its conditions, providers, how to call it, capabilities and limits, performance when data exists, alternatives, FAQ) is answered here too wherever `facts.json` holds the facts. List each unused fact id that would answer one. Never ask for content that has no fact. | 首期完成标准; "match their quality" |
| G11 | blocker | When no endpoint is active, the page shows Unavailable with alternatives and doesn't imply the model can be called now. `n/a` when an endpoint is active. | 没有有效 endpoint 的页面 |
| G12 | blocker | One call with the M3 example, in an authorised account, returned a real response of the model's output type (text, image, video, audio) and confirmed the model ID. `needs_person` unless `fact-check-report.md` records such a run with its result. | 验证至少一次成功调用; image rule ⑥ |

### Text (`entity_type: text`)

| ID | Severity | Requirement | Plan source |
|---|---|---|---|
| TXT-1 | blocker | Context window and max output are shown (per provider when they differ), billing is per token with the unit stated, and M3 sends a message. | 文本/推理/视觉理解 |
| TXT-2 | blocker | TTFT and throughput appear only with valid data, with the time window and sample conditions stated, and TTFT is never presented as total latency. | type table; M5 rule |

### Image (`entity_type: image`)

| ID | Severity | Requirement | Plan source |
|---|---|---|---|
| IMG-1 | blocker | Sizes or ratios, reference-image limits, image count and billing items are shown as the model actually supports them, with missing values as labels in their table cells. Context and token fields stay when billing is per token or output mixes text and image. | 图像生成/编辑 |
| IMG-2 | blocker | When providers' context or max output differ, or one is missing, M1 shows the value per provider. | image rule ① |
| IMG-3 | blocker | M2 has a billing-items table whose rows use the provider's own fee-item names (e.g. `prompt`, `input_cache_read`), never inferred labels such as "text input". No per-image price unless ZenMux publishes one; without one, the per-image cell shows `Not published` (page rule 8 replaces the plan's sentence "ZenMux publishes no per-image price" with that label). | image rule ② |
| IMG-4 | blocker | M4 scopes capabilities by protocol (Images API vs Responses / Chat). Where the provider's docs and ZenMux disagree, the status is Not verified. | image rule ③ |
| IMG-5 | blocker | A latency value counts as image completion time only when ZenMux states what it measures. No text TPS stands in for it. With nothing qualifying, M5 is hidden. | image rule ④ |
| IMG-6 | warning | When ZenMux's docs use a different model ID alias, M3 says so. | image rule ⑥ |

### Video (`entity_type: video`)

| ID | Severity | Requirement | Plan source |
|---|---|---|---|
| VID-1 | blocker | Duration, resolution, input modes and the real billing unit are shown. | 视频 |
| VID-2 | blocker | M3 shows a create-task request and a query-result request. | 视频 |
| VID-3 | blocker | Performance, when shown, is generation time; no text TPS or TTFT stands in for it. | 视频 |

### Audio (`entity_type: audio`)

| ID | Severity | Requirement | Plan source |
|---|---|---|---|
| AUD-1 | blocker | Voices, languages, duration or the task's own limits, and the billing unit, are shown as the API defines them. | 音频及其他 |
| AUD-2 | blocker | The page presents the model through its audio API, not as a chat model (no Chat framing in M1, M3 or the FAQ). | 音频及其他 |

### Site acceptance (not in `acceptance.json`)

Part 4 also has rules that only ZenMux's site can meet, and that no file in the workspace can
show: the page facts readable in server-rendered HTML, 390px mobile layout without horizontal
overflow, canonical / sitemap / robots / status codes, links from the model directory and
developer hubs into the page, provider selection updating M1, M3 and M4 in the UI, and the GSC
baseline before launch. List them in the step 12 report as owned by ZenMux's developers; don't
mark them passed.

## Reviewer prompt

Send this as the instruction (system prompt where your agent has one):

```
You are the acceptance reviewer for a ZenMux model page. You check the finished page against the
approved template's acceptance rules and the checklist below, and output ONLY a JSON object: no
preamble, no markdown fences, no commentary.

Inputs: plan.md (the approved template; Part 4 "开发实施与验收" and appendix A are the rules),
page.md (the page), facts.json (the fact ledger; facts[] and gaps[]), fact-check-report.md, and
an example page.md of a finished page of the same type.

Rules for judging:
- Judge the page as published content. HTML comments (<!-- module: … -->, <!-- gap: … -->) are
  build markers: read them only to see which modules are shown or hidden and why.
- Missing-value labels (Not published, Not verified, No data) in table cells are correct, not
  failures. The page bans disclaimers and production notes, so never ask for a sentence that
  explains a missing value.
- Don't re-check whether a number is true; the fact-check did that. Do check that the page agrees
  with itself (G5) and with its ledger (G10).
- G10: compare coverage with the example, not its facts or wording. A missing answer counts only
  when facts.json holds a fact for it; name the fact ids. Never ask for padding.
- G12 is needs_person unless fact-check-report.md records a live call and its result.
- Use n/a only when the requirement can't apply to this page, and say why in "note".
- Borderline → pass. Fail only what you can quote.

Checklist: <paste the checklist tables for "All model types" and for the page's entity_type>

OUTPUT SCHEMA (strict):
{"items": [{"id": "G1", "result": "pass" | "fail" | "needs_person" | "n/a",
  "location": "<module id or heading>",
  "evidence": "<fail only: verbatim quote from page.md, ≤160 chars; for G5 quote one side here and the other in fix_instruction>",
  "fix_instruction": "<fail only: the specific change, using facts from facts.json>",
  "note": "<needs_person / n/a: why; optional otherwise>"}]}

Answer every checklist item exactly once, in checklist order.
```

Then the user message:

```
<entity_type>image</entity_type>
<plan>…plan.md…</plan>
<facts>…facts.json…</facts>
<fact_check_report>…fact-check-report.md…</fact_check_report>
<example>…examples/<matching>/page.md…</example>
<page>…page.md…</page>

Check the page against every checklist item for its entity_type. Output the JSON object only.
```

## Writing acceptance.json

Save next to `page.md`, adding four keys around the reviewer's output:

```json
{
  "reviewed_at": "2026-11-12T10:00:00Z",
  "reviewer": "<model name>",
  "page_sha256": "<sha256 of page.md bytes at review time>",
  "entity_type": "image",
  "example": "examples/gpt-image-2",
  "items": [ … exactly as the reviewer returned them … ]
}
```

Same hash command as `review.md`. Don't edit, drop or soften items. If one looks wrong, you may
re-run the review once in a fresh context; if it recurs, it stands. Only a person can waive a
failed item, by adding `"waived_by": "<name>"` and a `"waiver_note"` to it.

`check_page.py` then:
- fails the page on a failed blocker item (`accept:<id>`), an unanswered item
  (`ACCEPT_INCOMPLETE`), a review of a different `entity_type` (`ACCEPT_WRONG_TYPE`) or a page
  changed after the review (`ACCEPT_STALE`);
- warns on a failed warning item, on each `needs_person` item (`ACCEPT_NEEDS_PERSON`), and when a
  quote isn't found in the page.

Fixing a failed item means editing `page.md`, which makes both `review.json` and
`acceptance.json` stale: re-run the writing review and this review after each rewrite round. The
3-round limit (SKILL.md rule 4a) covers both reviews together.
