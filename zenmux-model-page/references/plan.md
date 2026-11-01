---
plan_slug: zenmux-model-page
status: approved
approved_by: rogermzy
approved_at: 2026-10-28
amended: 2026-10-30 — image-model variant (6 rules from the GPT Image 2 page), approved by rogermzy; 2026-11-01 — Title and meta description have no length limit and should carry the model's name variants and related entities, set by rogermzy
checked_date: 2026-10-19
sample_url: https://zenmux.ai/deepseek/deepseek-v4-pro
sample_entity: DeepSeek V4 Pro
---

# ZenMux Model 页改版方案

# **改版目标：让访问网站的用户依次看懂“这是什么模型 → 选哪个供应商、多少钱 → 如何接入”，并让同一套组件适用于全站模型。保留现有供应商和运行数据，不重做已有能力。**

SEO 目标：让模型页承接模型名及 API、价格、接入示例、能力和限制等相关搜索，以模型专属信息帮助用户完成选型。SEO 与用户体验共用同一套正文，不另建重复的“SEO 页面”，也不靠堆字数或关键词。

核查日期：2026-10-19；示例页面：DeepSeek V4 Pro。

# 1. 参考竞品以及具体借鉴方向

| 竞品与页面 | 具体参考点 | ZenMux 对应改动 |
| :- | :- | :- |
| [OpenRouter · DeepSeek V4 Pro](https://openrouter.ai/deepseek/deepseek-v4-pro) | Providers 供应商比较、价格/性能信息、分区锚点导航；性能区解释 TTFT、吞吐和可用性的含义。 | 参考其“先选供应商、再看运行表现”的组织方式，改造 M2 价格表和 M5 性能区；保留现有数据，增加实际版本和统计条件。 |
| [AI/ML API · DeepSeek V4 Pro](https://aimlapi.com/models/deepseek-v4-pro) | 首屏用卡片展示模态、上下文、输入/输出价格；正文很快进入 Quickstart；另有模型对比与 FAQ。 | 参考首屏卡片、正文代码和选型内容，形成 M1、M3、M7、M8；不把长介绍放在价格之前。 |
| [DeepInfra · DeepSeek V3](https://deepinfra.com/deepseek-ai/DeepSeek-V3)[该模型 API 页](https://deepinfra.com/deepseek-ai/DeepSeek-V3/api) | 紧凑的价格与规格标签；API 页提供代码、streaming 和输入/输出参数说明。它是相邻的推理服务竞品，并非同构的多供应商市场。 | 参考“规格与接入信息靠近”的方式，形成 M3 接入示例和 M4 能力/限制表；不复制长篇训练和本地部署说明。 |

# 2. 当前页面不足，以及对应修改思路

当前页已经有供应商、Uptime、Throughput、Latency、Activity、Benchmarks、Apps、Related Models，也有 API Request 弹窗。以下针对现有结构补强，不将已存在的功能列为“缺失”。

[当前 ZenMux DeepSeek V4 Pro 页面](https://zenmux.ai/deepseek/deepseek-v4-pro)

| 当前不足 | 具体观察 | 改版动作 |
| :- | :- | :- |
| 首屏不便快速选型 | 长介绍占据较大空间，尤其移动端；价格在供应商表中，缺少简洁摘要。 | M1 用 1–2 句概述 + 关键事实卡替代长首屏介绍，价格和主 CTA 前置。 |
| 版本信息混杂 | H1 写 0813，介绍又写部分 provider 为 0731、其他为 0424；Publish time 的日期语义不清。 | 主标题用稳定模型名；版本差异放提示条，并在 M2 每个供应商 endpoint 行展示实际版本。分开模型发布与平台上架日期。 |
| 价格区间和优惠条件不清 | 部分供应商显示价格区间，首屏还有 75% OFF，但适用条件不够自解释。 | M2 解释区间触发条件、优惠对应 provider/版本/期限；首屏价格必须对应一个实际可用的报价组合。 |
| 接入代码只在快捷弹窗内 | API Request 已能匿名展示带 model ID 的代码和协议选项，但正文没有直接可读的最小接入示例。 | 保留弹窗，新增 M3 正文 Quickstart；不用登录或点击弹窗也能看懂如何调用。 |
| 缺少集中展示的能力、限制和选型理由 | 模态用图标表示，信息分散于介绍和供应商数据；缺少清楚的能力/限制及适用任务说明。 | M4 用文字和简表说明支持什么、不支持什么，以及适合哪些任务；按 endpoint 区分差异。 |
| 辅助模块和不同模型类型缺少取舍 | 图像/视频样本也出现 token TPS、TTFT 的通用模块；空数据时无法帮助用户。 | M5/M6 有相关数据才显示；图像/视频换成生成耗时、正确计费单位和对应示例。Apps、Activity 置于次级区域，无数据隐藏。 |

优先级：

🔥 HIGH IMPACT 为首屏、版本/报价解释、正文接入和能力说明；

⚡ MEDIUM IMPACT 为性能口径与有证据的选型比较；

⚠️ LOW IMPACT 为装饰性图表、空榜单和额外 schema，不阻塞首期。

# 3. 改版后的 Template：开发按这个顺序搭建

编号 M1–M9 即组件顺序。标记“必备”的模块用于所有可调用模型；标记“条件”的模块只有数据有效时才展示，隐藏后导航也同步隐藏。页面采用单页锚点导航，不拆成大量 tab URL。

模块对应的 Google 搜索意图如下。查询示例用于指导内容组织，尚未代表经过实测的搜索量或关键词优先级；相同模型的相近意图优先由同一个 model 页承接。

| 对应模块 | 承接的搜索意图 | 内容要求 |
| :- | :- | :- |
| M1 首屏 | {model} / {model} API | 自然模型名、API 身份与简明定义；Title、描述、H1 对应该模型，不套用无差别宣传。 |
| M2 价格/供应商 | {model} pricing / API cost | 直接解释真实价格、缓存、阶梯和供应商条件，不只给一个未注明条件的最低价。 |
| M3 接入代码 | {model} API example / Python | 提供准确的模型 ID、endpoint 和可复制示例；完整教程由相关文档承接。 |
| M4 能力 + M8 FAQ | {model} context window / tool calling / reasoning | 用文字直接回答本模型实际能力与限制；可核实的数据进入正文，不能只存在图标或弹窗中。 |
| M7 对比 | {model A} vs {model B} / alternatives | 有依据时给同任务取舍；独立比较页仅在有实质内容和独立意图时建立，不批量拆薄页。 |

```text
Models > {Developer} > {Model}
┌ M1 首屏：H1 + 简介 + 事实卡 + 主 CTA ┐
├ 锚点导航：Pricing / API / Capabilities / …
├ M2 Pricing & Providers                  必备
├ M3 API Quickstart                       必备
├ M4 Capabilities, Limits & Use Cases      必备
├ M5 Performance & Availability           条件
├ M6 Benchmarks                           条件
├ M7 Compare Alternative Models           条件
├ M8 FAQ                                  必备
└ M9 Related Models & Guides + CTA         必备
```

## **M1 首屏：模型是什么、多少钱、如何开始**

参考 AI/ML API 的事实卡布局。保留现有模型名、slug、状态、Compare/API Request/试用能力；将长介绍下移或缩短。

- 显示：H1“{Model Name} API”、1–2 句概述、可复制 model ID、模态文字、上下文/输出限制（适用时）、对应供应商的价格摘要、主 CTA。
- 交互：主 CTA“Get API Key”；次 CTA 随任务显示 Try Model / Create / Try API。现有 API Request 弹窗继续可用。
- 版本：若供应商版本不同，在事实卡下显示“Different providers may serve different revisions”，链接 M2；不把一个版本号当成全部供应商的统一版本。
- 规则：首屏输入/输出价来自同一个可用 endpoint；不能拼接两家各自最低价。无有效报价时显示 View provider pricing，不填 $0。

## **M2 Pricing & Providers：选服务商并看懂报价**

参考 OpenRouter 的供应商比较。复用现有表格和接口，增加解释字段，不另做一套手工价格表。英文 H2：{Model Name} Pricing & Providers。

默认列：Provider｜Served version｜Input price｜Output price｜Cache read（适用时）｜Context/任务限制｜选择入口。TTFT、TPS 等已有列可保留在性能展开区。价格统一显示币种和计费单位；区间、折扣、缓存写入、额外费用放在对应行的详情中。 计费维度独立于模型类型配置：可能包含文本输入/输出、图像输入/输出、缓存、搜索或视频输出等项目，不能把所有图像改成按张、视频改成按秒；单独列出适用项目及条件，不从其他平台复制价格。

- 选择某 endpoint 后，M1 价格、M3 代码和 M4 能力说明同步更新；默认显示当前路由策略，不能让界面选择与实际请求不一致。
- 未知版本写 Not verified；未知价格写 Not published；不支持与未知分别处理。
- 单供应商模型使用计费卡或单行表，不渲染复杂比较器。停用 endpoint 不参与最低价，不提供选用按钮。

## **M3 API Quickstart：正文即可复制调用**

参考 AI/ML API 的前置 Quickstart 和 DeepInfra 的模型级代码。复用现有 API Request 的代码生成器并增加正文组件，但必须先校验任务语义：文字示例返回文字，图像示例配置并读取图像，视频示例创建任务、查询状态并取得结果；不能只替换 model ID。英文 H2：How to Use {Model Name} via API。

- 显示：默认协议、endpoint、模型 ID、cURL/Python/JavaScript 代码切换、复制按钮、获取 API key 和完整文档链接。
- 代码随 M2 选择的供应商更新。只有该模型/endpoint 确认支持的协议才出现可选项，不把平台级协议支持推定为每个模型均支持。
- 未登录可阅读和复制；获取密钥/实际试用按现有登录流程。示例只引用环境变量，不写入真实密钥。

DeepSeek V4 Pro 的默认路由示例（结构来自 ZenMux 现有弹窗和官方 Quickstart；不是付费调用测试结果）：

```bash
curl https://zenmux.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $ZENMUX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek/deepseek-v4-pro",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

固定供应商时，使用 ZenMux 文档支持的 model_slug:provider_slug 或 routing 配置；不能套用其他平台的参数。

## **M4 Capabilities, Limits & Use Cases：是否适合我的任务**

参考 DeepInfra 的紧凑规格与参数说明，并补充模型特定的任务选择信息。英文 H2：{Model Name} Capabilities & Use Cases。

模型页独特内容要求：每页至少提供实际适用的版本/供应商差异、计费条件、能力限制或任务取舍，而不是只替换模型名和重写上游介绍。M4 的场景需结合该模型证据撰写；规格与价格同步引用事实数据，避免同页冲突。重要事实附对应版本的官方来源或核验时间，不为表现“新鲜”每天改发布日期。

- 规格表：输入/输出模态、上下文与最大输出、streaming、tool calling、structured output、reasoning；按模型类型选择字段。
- 能力状态必须区分 Supported / Not supported / Not verified / Varies by provider；选择 provider 后对应变化。
- 内容提供 2–3 个有依据的具体场景，以及简短 Not ideal for；每项说明任务和限制，不只写“coding、reasoning”等标签。没有依据就少写，不机械凑字数。

## **M5–M7 条件模块：有证据才展示**

| 模块与参考 | 显示内容 | 开发规则 |
| :- | :- | :- |
| M5 Performance & Availability；参考 OpenRouter，复用 ZenMux 现有图表 | TTFT、吞吐、请求成功率/可用性，以及时间窗口、更新时间和统计条件。 | 明确 TTFT ≠ 总耗时、请求成功率 ≠ 按时间算的 uptime。无有效样本时隐藏图表或显示 No data，不填 100%。图像/视频用生成耗时，不用文字 TPS。 |
| M6 Benchmarks；参考 OpenRouter | 少量与任务相关的成绩、来源链接、模型版本、推理模式和日期。 | 不同版本或设置不混算排名；没有能对应版本的来源就隐藏。不要为每个模型复制通用 leaderboard。 |
| M7 Compare Alternative Models；参考 AI/ML API | 2–3 个同任务替代模型；比较价格、关键限制及选择理由。 | 替代项由内容配置提供，不自动把同厂商模型当作所有替代项；无可靠取舍依据则隐藏。价格复用各模型的同一数据源。 |

## **M8–M9 FAQ、相关内容与结尾 CTA**

M8 参考 AI/ML API 的 FAQ。围绕本模型的价格、实际版本、模型 ID、上下文、工具调用和供应商选择提供简短答案；价格和规格从 M2/M4 同一数据生成，不在 FAQ 手填第二份。FAQ 目的是答疑，不以 Google FAQ 富结果为交付目标。

M9 展示开发者 hub、同系列/同任务模型、相关 Quickstart 或教程，全部链接真实页面；结尾重复主 CTA。保留现有 Related Models 能力并优化筛选，不堆全站链接。Apps 与 Activity 不是首期必备模块：真实数据存在时放在性能区之后的次级内容，无数据时整体隐藏。 相关模型优先按相同输出任务和使用目的筛选，再补同系列；不能因为同属 Google 就把 TTS 当作图像模型的主要替代项。

# 4. 开发实施与验收

## **组件与数据：只补必要字段**

优先复用现有页面接口、供应商表、运行图表、代码生成器和登录流程。以下是前端需要的数据含义，不要求新增同名 API 或重建后台；开发先映射现有字段，仅补缺失项。

| 数据组 | 前端必须能拿到什么 |
| :- | :- |
| 模型信息 | 自然名、slug、开发者、任务类型、模态、描述、可用状态；模型发布时间与平台上架时间分开。 |
| 供应商 endpoint | provider slug、实际服务版本、报价/币种/单位/条件、协议、能力和限制、可用状态、最后核验时间。 |
| 辅助数据 | 性能统计及窗口/样本条件；benchmark 来源与版本；按需配置场景、替代模型和 FAQ。缺失时按条件规则隐藏。 |

全页共用一个“当前选定 endpoint”状态：M2 选用 → M1 摘要、M3 代码、M4 能力同步。自动路由是独立状态，需标明版本/报价可能随命中 endpoint 变化，不把某一 provider 的能力无条件承诺为全局能力。

## **不同模型类型：同骨架，替换字段和代码**

| 类型 | 必须适配的展示 |
| :- | :- |
| 文本/推理/视觉理解 | 显示 context/max output、按 token 计费及消息示例；TTFT/TPS 只在有有效数据时出现。 |
| 图像生成/编辑 | 按实际能力显示尺寸/比例、参考图限制、数量和计费项目，示例需取得真实图像响应；支持文本与图像混合输出、context 或 token 计费的模型保留对应字段，不将它们误删为“图像不适用”。文字 TPS 不能代替图像完成耗时。另按以下 6 条执行（2026-10-30 增补）：① M1：各供应商 context/max output 不同或有缺失时，按供应商分别显示（如“Azure: 10,000 tokens; OpenAI: Not published”）；② M2：增加计费项目表，行名使用供应商自己的计费项名称（如 `prompt`、`input_cache_read`），不写推断出的“文字输入”等标签；未公布单张价格时写明“ZenMux publishes no per-image price”；③ M4：能力按协议区分（Images API 与 Responses/Chat）；供应商文档与 ZenMux 列表不一致时两者都写，状态标 Not verified；④ M5：只有 ZenMux 说明了延迟指标的含义，才可作为图像完成耗时；否则注明“metric not stated”，不当作完成耗时，无其他合格数据时隐藏 M5；⑤ 图像模型不放 Chat CTA，次 CTA 用 Try API / Create；⑥ M3：ZenMux 文档使用不同的 model ID 别名时在 M3 说明；验收要求一次返回真实图像的调用并确认 model ID。 |
| 视频 | 显示时长/分辨率、输入模式、真实计费单位，使用创建任务/查询结果示例；CTA 用 Create，性能看生成耗时。 |
| 音频及其他已提供类型 | 按实际 API 展示音色/语言/时长或相应任务限制和计费单位；不把所有模型都做成 Chat。 |

## **SEO 与移动端：作为开发验收项**

- 保留现有 /{developer}/{model-slug} URL 与自引用 canonical；provider、代码语言和图表筛选不新增可索引页面。
- 只有一个页面 H1；各正文模块使用 H2。
- Title 与 meta description 不设字数上限（2026-11-01 增补）：越长、包含的名称变体和相关实体越多越好。Title 以「{模型名} API」开头、以「| ZenMux」结尾，中间写入 model ID、别名与修订版本、开发者、各供应商名、计费方式、上下文与最大输出、主要能力、示例语言、对比与 FAQ 等本页确实回答的内容；meta description 用完整句子写出同样的名称变体与相关实体。所有数字必须来自事实台账，不写本页没有的内容，不写最高级或宣传语。DeepSeek 示例 Title：DeepSeek V4 Pro API (deepseek/deepseek-v4-pro, DeepSeek-V4-Pro-0813): Pricing & Providers on DeepSeek, Tencent Cloud, Baidu, Alibaba Cloud, Streamlake & SiliconFlow, Peak and Off-Peak Rates, Cache Pricing, 1M Context, 384K Max Output, Python, JavaScript & cURL Examples, Alternatives and FAQ | ZenMux。
- 首屏事实、报价、默认代码、能力和 FAQ 在服务端 HTML 中可读，且与渲染后正文一致；导航和相关链接使用真实 href。
- 390px 移动端先显示短摘要、关键规格/价格和 CTA；供应商表改为卡片或局部横滚，页面本身不能横向溢出；长图表延后加载。

## **内链入口与索引规则**

- 🔥 HIGH IMPACT：补齐指向模型页的入口。模型目录、开发者聚合页、相关教程应以真实链接指向对应模型页；分页中的模型也应可发现，不能只靠站内搜索或无限滚动。锚文本使用准确模型名或相关主题，不统一写“点击这里”。
- 保留目录 → 开发者 hub → model 页的层级；模型开发者与服务供应商分开。M9 负责相关模型/文档出口，教程和 hub 同时提供模型页入口，避免只出不进。
- ⚡ MEDIUM IMPACT：Sitemap 仅提交希望索引、状态有效的 canonical URL；参数/筛选不产生重复索引页，实质不同的模型版本不一概合并。
- 暂不可用但仍有实用资料的模型页可保留 200，说明状态并给替代选择；永久移除且无等价替代时返回 404/410。同一实体改名且有等价目标时才重定向，不把所有旧模型跳到目录，也不批量保留只有 Unavailable 的空页。

## **Google SEO 验收**

- 逐页检查自然模型名、Title、meta description、H1 与正文一致，核心答案位于对应模块；不只检查有没有标签，也检查是否对本模型有信息价值。
- 抽查未登录、未选 provider、未打开弹窗的默认页面：原始 HTML 与渲染后均有准确身份、默认报价条件、代码和能力答案；使用 GSC URL Inspection 等检查 Google 实际可读取的版本，不仅凭浏览器截图判断。
- 检查模型目录、hub、教程和分页链接能到达 model 页；有效页面状态码、robots/noindex、canonical 和 Sitemap 一致。若存在阻断抓取或索引的问题，升级为最高优先级。
- 上线前保存 GSC 的模型页曝光、点击和查询基线；上线后按相同 URL 与意图簇比较，再结合首次成功调用判断流量质量。30/60/90 天可作观察窗口，不作为排名增长承诺。

⚠️ LOW IMPACT：额外 schema、泛化 FAQ、长篇通用介绍和全量榜单不作为首期 SEO 交付目标；不设关键词密度或最低字数指标。

## **首期完成标准**

- 🔥 HIGH IMPACT：先用 DeepSeek V4 Pro 实现 M1–M4、M8–M9，复用已有能力；版本提示与报价条件必须同步完成。
- ⚡ MEDIUM IMPACT：M5–M7 根据真实数据启用，不因没有 benchmark 或替代项而阻塞必备模块。
- 验收覆盖：一个多供应商文本页、一个单供应商页、图像页、视频/音频页；确认单位、CTA、代码和缺失数据规则不同但布局骨架一致。
- 选择 provider 后，首屏/表格/FAQ 的价格一致，代码和能力对应所选 endpoint；匿名可读可复制，无密钥泄露。
- 在有授权的测试账户中验证至少一次成功调用；没有有效 endpoint 的页面显示 Unavailable 并给替代项，不继续暗示可以立即调用。
- 同页信息一致、来源可追溯、真实链接有效；本方案不要求重建计费系统、开发成本估算器或新增全量榜单。

# 附录 A：Template spec

```json page-template
{
  "template_id": "zenmux-model-page",
  "page_language": "en",
  "url_pattern": "/{developer}/{model-slug}",
  "title_pattern": "{Entity} API{Variants} | ZenMux",
  "title_rule": "No length limit; longer is better. After '{Entity} API', add the variants and related entities this page really answers: model ID, aliases and revision names, developer, provider names, billing type, context and max output, main capabilities, example languages, alternatives, FAQ. Numbers only as fact display strings; nothing the page does not cover; no superlatives.",
  "h1_pattern": "{Entity} API",
  "meta_description_rule": "No length limit; longer is better. Full sentences that name this specific model and its variants (model ID, aliases, revision), the developer, modalities, the providers, the billing items and conditions, context and max output, and what the page offers (pricing table, capabilities, API example languages, alternatives). Title, description and H1 correspond to this model; numbers only as fact display strings; no undifferentiated promotion.",
  "default_endpoint_rule": "One shared 'currently selected endpoint' state: choosing an endpoint in M2 updates the M1 summary, M3 code and M4 capabilities.",
  "status_vocabulary": ["Supported", "Not supported", "Not verified", "Varies by provider"],
  "missing_value_labels": {"price": "Not published", "version": "Not verified", "metric": "No data"},
  "entity_variants": {
    "text": "context/max output, per-token billing and a message example; TTFT/TPS only when valid data exists",
    "image": "sizes/ratios, reference-image limits, count and billing items per actual capability; example must obtain a real image response; keep context/token-billing fields for models with mixed text+image output; text TPS cannot replace image completion time. Amended 2026-10-30: (1) M1: when providers' context/max output differ or one is missing, show the value per provider; (2) M2: add a billing-items table whose rows use the provider's own fee-item names (e.g. prompt, input_cache_read), never inferred labels such as 'text input'; state 'ZenMux publishes no per-image price' when none is published; (3) M4: scope capabilities by protocol (Images API vs Responses/Chat); when the provider's docs and ZenMux disagree, show both and mark Not verified; (4) M5: a latency value counts as image completion time only when ZenMux states what it measures; otherwise label it 'metric not stated', do not treat it as completion time, and hide M5 if nothing else qualifies; (5) no Chat CTA for image models; the secondary CTA is Try API or Create; (6) M3: when ZenMux's docs use a different model ID alias, say so in M3; acceptance requires one call that returns a real image with the model ID confirmed",
    "video": "duration/resolution, input modes, real billing unit; create-task + query-result example; CTA Create; performance is generation time",
    "audio": "voices/languages/duration or the task limits and billing unit per the actual API; do not turn every model into Chat"
  },
  "modules": [
    {
      "id": "M1",
      "name": "Hero",
      "required": true,
      "h2": null,
      "intent": ["{entity}", "{entity} API"],
      "fields": ["overview", "model_id", "modalities", "context_window", "max_output", "price_summary", "version_note", "primary_cta", "secondary_cta"],
      "rules": [
        "H1 is '{Model Name} API' with a 1-2 sentence overview; long introduction is shortened or moved below price.",
        "Input and output price come from the same available endpoint; never splice each provider's lowest price.",
        "No valid price -> show 'View provider pricing', never $0.",
        "If providers serve different versions, show 'Different providers may serve different revisions' under the fact card, linking to M2; do not present one version as the version for all providers.",
        "Primary CTA 'Get API Key'; secondary CTA is Try Model / Create / Try API by task; the existing API Request dialog stays available."
      ],
      "show_if": null,
      "status_table": false
    },
    {
      "id": "M2",
      "name": "Pricing & Providers",
      "required": true,
      "h2": "{Entity} Pricing & Providers",
      "intent": ["{entity} pricing", "{entity} API cost"],
      "fields": ["provider", "served_version", "input_price", "output_price", "cache_read", "context_limits", "select_action", "currency", "billing_unit"],
      "rules": [
        "Explain real price, cache, tiers and provider conditions; do not give only a lowest price without conditions.",
        "Show currency and billing unit; ranges, discounts, cache write and extra fees go in the row details.",
        "Billing dimensions are configured independently of model type; list applicable items and conditions, never copy prices from other platforms.",
        "Selecting an endpoint updates M1 price, M3 code and M4 capabilities; the default shows the current routing strategy and the UI selection must match the actual request.",
        "Unknown version -> Not verified; unknown price -> Not published; unsupported and unknown are handled separately.",
        "Single-provider models use a billing card or single-row table, not a comparator; deactivated endpoints do not count toward the lowest price and get no select button."
      ],
      "show_if": null,
      "status_table": false
    },
    {
      "id": "M3",
      "name": "API Quickstart",
      "required": true,
      "h2": "How to Use {Entity} via API",
      "intent": ["{entity} API example", "{entity} Python"],
      "fields": ["default_protocol", "endpoint", "model_id", "code_tabs", "copy_button", "api_key_link", "docs_link"],
      "rules": [
        "Provide exact model ID, endpoint and a copyable example; the full tutorial is left to the docs.",
        "Example must match the task semantics: text returns text, image configures and reads an image, video creates a task, polls status and gets the result; do not just swap the model ID.",
        "Code tabs cURL/Python/JavaScript with a copy button; code follows the provider selected in M2.",
        "Only protocols confirmed for that model/endpoint appear as options; do not infer platform-level protocol support for every model.",
        "Readable and copyable without login; example references an environment variable only, never a real key.",
        "To pin a provider use the ZenMux-documented model_slug:provider_slug or routing config; do not reuse other platforms' parameters."
      ],
      "show_if": null,
      "status_table": false
    },
    {
      "id": "M4",
      "name": "Capabilities, Limits & Use Cases",
      "required": true,
      "h2": "{Entity} Capabilities & Use Cases",
      "intent": ["{entity} context window", "{entity} tool calling", "{entity} reasoning"],
      "fields": ["input_modalities", "output_modalities", "context_window", "max_output", "streaming", "tool_calling", "structured_output", "reasoning", "use_cases", "not_ideal_for", "source_or_verified_at"],
      "rules": [
        "Answer the model's real capabilities and limits in text; verifiable data goes in the body, not only in icons or dialogs.",
        "Each page gives at least one of: version/provider differences, billing conditions, capability limits, task trade-offs; do not just swap the model name and rewrite the upstream intro.",
        "Spec table: input/output modalities, context and max output, streaming, tool calling, structured output, reasoning; fields chosen by model type.",
        "Capability status must distinguish Supported / Not supported / Not verified / Varies by provider, and changes with the selected provider.",
        "2-3 evidence-based concrete scenarios plus a short 'Not ideal for'; each states the task and limit, not bare labels like coding or reasoning; with no evidence write less.",
        "Specs and prices cite the same fact data; important facts carry the official source for that version or a verified-at time; do not change the publish date daily to look fresh."
      ],
      "show_if": null,
      "status_table": true
    },
    {
      "id": "M5",
      "name": "Performance & Availability",
      "required": false,
      "h2": "{Entity} Performance & Availability",
      "intent": [],
      "fields": ["ttft", "throughput", "success_rate", "window", "updated_at", "sample_conditions"],
      "rules": [
        "Show TTFT, throughput, request success rate/availability with time window, update time and statistics conditions.",
        "TTFT != total latency; request success rate != time-based uptime.",
        "With no valid samples hide the chart or show 'No data'; never fill 100%.",
        "Image/video use generation time, not text TPS."
      ],
      "show_if": "category:performance",
      "status_table": false
    },
    {
      "id": "M6",
      "name": "Benchmarks",
      "required": false,
      "h2": "{Entity} Benchmarks",
      "intent": [],
      "fields": ["benchmark_name", "score", "source_url", "model_version", "reasoning_mode", "date"],
      "rules": [
        "A few task-relevant results with source link, model version, reasoning mode and date.",
        "Do not mix rankings across versions or settings; hide when there is no source matching the version.",
        "Do not copy a generic leaderboard onto every model."
      ],
      "show_if": "category:benchmark",
      "status_table": false
    },
    {
      "id": "M7",
      "name": "Compare Alternative Models",
      "required": false,
      "h2": "Compare {Entity} Alternatives",
      "intent": ["{model A} vs {model B}", "{entity} alternatives"],
      "fields": ["alternatives", "price", "key_limits", "selection_reason"],
      "rules": [
        "2-3 same-task alternative models; compare price, key limits and selection reason.",
        "Alternatives come from content configuration; do not automatically treat same-developer models as every alternative; hide when there is no reliable trade-off basis.",
        "Prices reuse each model's same data source.",
        "A standalone comparison page is built only with substantive content and independent intent; do not split thin pages in bulk."
      ],
      "show_if": "manual:alternatives with a sourced trade-off are configured",
      "status_table": false
    },
    {
      "id": "M8",
      "name": "FAQ",
      "required": true,
      "h2": "{Entity} FAQ",
      "intent": ["{entity} context window", "{entity} tool calling", "{entity} reasoning"],
      "fields": ["price", "served_version", "model_id", "context_window", "tool_calling", "provider_choice"],
      "rules": [
        "Short answers about this model's price, actual version, model ID, context, tool calling and provider choice.",
        "Price and specs are generated from the same data as M2/M4; do not hand-write a second copy in the FAQ.",
        "The FAQ's purpose is answering questions, not earning Google FAQ rich results."
      ],
      "show_if": null,
      "status_table": false,
      "derived_from": ["M2", "M4"]
    },
    {
      "id": "M9",
      "name": "Related Models & Guides",
      "required": true,
      "h2": "Related Models & Guides",
      "intent": [],
      "fields": ["developer_hub", "related_models", "related_guides", "closing_cta"],
      "rules": [
        "Show developer hub, same-series/same-task models and related Quickstart or tutorials; all link to real pages; do not pile on site-wide links.",
        "Related models are filtered first by the same output task and purpose, then topped up by same series.",
        "Repeat the primary CTA at the end.",
        "Apps and Activity are not required in the first release: show them as secondary content after the performance area only when real data exists, otherwise hide as a whole."
      ],
      "show_if": null,
      "status_table": false
    }
  ]
}
```
