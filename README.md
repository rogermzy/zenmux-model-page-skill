# zenmux-model-page：ZenMux 模型页写作 Skill

[English](README.en.md)

这是一个给 AI agent 用的 skill：告诉 agent「写 / 更新某个模型的 ZenMux 模型页」，它会按已批准的模型页模板（模块 M1–M9）产出页面内容。页面上的每个价格、规格、版本和日期都来自一个已保存、可逐字引用的来源，不靠模型记忆，也不编造。

## 每个模型会产出什么

| 文件 | 内容 |
| :- | :- |
| `page.md` | 页面正文，按模块顺序写，带模块标记，方便前端按模块搭建 |
| `facts.json` | 事实台账：页面上每个数字的来源 URL 和原文引文，以及发现的问题（gaps） |
| `fact-check-report.md` | 事实核查报告：哪些已核实、哪些改了措辞、哪些需要人来判断 |
| `review.json` | 写作评审结果：按 Wendy Writes 语义规则发现的问题 |
| `site-fix-requests.md` | 全部页面合并后的「官网修复清单」：官网缺失、自相矛盾或与模型厂商文档不一致的地方，附原文引文 |

页面正文是英文；模板（`references/plan.md`）是中文。

## 支持的模型类型

- 支持：文本（text）、图像（image）、视频（video）、语音合成（speech / audio）。
- 不支持：转写（transcription）、向量（embeddings）、重排（rerank）、decisions 等。这些类型模板里还没有规则，skill 会直接说明并停止，不会自行发挥。
- 2026-11-01 扫描时，公开模型 API 共 212 个模型：197 个可以生成，15 个属于暂不支持的类型。

## 环境要求

- 一个能读写文件、执行 shell 命令、访问网页的 agent；有网页搜索更好（用来找模型厂商的官方文档）。
- Python 3.9 或以上，只用标准库，无需安装任何依赖。macOS、Linux 已测试；Windows 的文件锁代码已写好，但未实测。
- **任何模型都能用**，不依赖 Claude。有子任务（sub-agent）能力时会并行做事实核查，没有也能按顺序完成。
- 写页面不需要 ZenMux API key。只有最后的「真实调用验收」需要（见下文）。

## 安装

skill 本体是 `zenmux-model-page/` 这个文件夹（里面有 `SKILL.md`）。把它复制到你的 agent 读取 skill 的位置：

| Agent | 位置 |
| :- | :- |
| Claude Code | `~/.claude/skills/zenmux-model-page/` 或 项目内 `.claude/skills/zenmux-model-page/` |
| Codex CLI | `~/.codex/skills/zenmux-model-page/` 或 项目内 `.agents/skills/zenmux-model-page/` |
| Claude Agent SDK / 其他支持 Agent Skills 格式的 agent | 对应的 skills 目录 |
| 不支持 skill 的 agent | 把 `SKILL.md` 的内容放进系统提示词，并告诉它这个文件夹的路径 |

## 使用

直接对 agent 说，例如：

> Write the ZenMux model page for Claude Opus 5.5.
> 帮我写 doubao-seedance-2.5 的模型页。
> Refresh the DeepSeek V4.1 Flash page.

所有页面共用一个工作目录（默认 `./zenmux-pages/`），ZenMux 的公共文档只抓一次，14 天内复用，过期自动重新抓取。

**注意：**「不要调用 API」这类要求只针对生成类调用（需要 `$ZENMUX_API_KEY`、会产生费用的请求）。公开的模型列表 `https://zenmux.ai/api/v1/models` 不需要 key，是普通网页抓取，skill 每次都要用它。

## 它是怎么工作的

1. **起步**：`scripts/new_page.py` 通过公开模型 API 找到模型，按输出类型选模板分支；抓取模型页，解码页面内嵌数据（Next.js flight data），提取各供应商的价格、计费项、上下文、最大输出、别名和状态，生成初始 `facts.json`。每条引文都已校验确实存在于快照中。
2. **补充厂商事实**：从模型厂商的官方文档、模型卡补充官方上下文、版本、发布日期、弃用公告等。
3. **记录问题**：官网没写、写了两种说法、与厂商文档不一致、疑似录入错误、只在 JavaScript 里显示的，统统记为 gap，附两边原文。
4. **决定模块显隐**：必选模块显示；条件模块只有在台账里有数据时才显示，否则隐藏并写明原因。
5. **写页面**：按页面规则和 19 条句子规则（来自 Wendy Writes 写作宪法：首句直答、不用模糊词、一句一事实、段首含模型名、FAQ 问题用 H3 等）写作。页面上出现的每个数字都必须是台账里某条事实的显示值。
6. **检查**：`scripts/check_page.py` 检查数字可追溯、引文存在、模块顺序、缺失值标签、密钥泄露，并运行 Wendy 的文风检查（lint）：阻断级问题（如段首用代词、模糊词、AI 套话、段首放链接、H1 和首句缺模型名）直接判失败。必须 PASS。
7. **事实核查**：另开一个上下文（最好用不同厂商的模型；ZenMux 正好可以路由到任意模型），重新抓取并逐条核对来源原文。
8. **写作评审**：同样在写作者之外的上下文里，按 Wendy 的语义规则（首句直答、开头段落、紧扣模块主题、断言后跟证据、比较完整、不用比喻等）评审全文，结果存为 `review.json`。未豁免的阻断项会让检查失败；页面一改，评审即过期，需要重新评审。
9. **终检**：对最终页面再跑一次检查，必须 PASS 且评审为最新。
10. **官网修复清单**：`scripts/site_fixes.py` 把所有页面的 gap 合并成 `site-fix-requests.md`。
11. **报告**：列出每页的显示 / 隐藏模块、核查结果、写作评审结果、未核实项和需要人处理的事。

## 硬规则（脚本会强制检查大部分）

- **模型永远不是数字的来源。** 没有来源就显示模板规定的标签：`Not published`、`Not verified` 或 `No data`。
- **ZenMux 与厂商文档冲突时不替任何一方做决定**：页面显示 `Not verified`，问题进入修复清单。
- **宁可隐藏，不要空填**：不显示 `$0`、`100%`、空图表或通用排行榜。
- **不跳过检查、事实核查和写作评审**；页面若还在用被核查判定为错误（REFUTED）的事实，或有未豁免的写作阻断项，检查会失败。
- **只改被标记的句子**：其余句子保持不变；每页最多 3 轮修改，之后把剩余问题交给人处理。agent 不能自行豁免任何问题，只有人可以在 `review.json` 中标注 `waived_by`。
- **不写入任何密钥**；示例代码只用 `$ZENMUX_API_KEY`。

## 需要人来决定的事

- 页面是否发布。skill 不会在还有未决事项时宣布页面完成。
- 核查结果为 UNVERIFIABLE 的事实（页面上显示 `Not verified`）。
- 图像、视频模型的验收：用真实 key 跑一次调用，拿到真实图片 / 视频，确认示例代码里的模型 ID 可用。
- `site-fix-requests.md` 交给谁处理。

## 官网数据问题（2026-11-01 扫描全站模型时发现）

这些问题会在每个受影响的模型页里自动记为 gap，并进入修复清单。集中修掉，生成的页面会少很多 `Not verified`：

1. **公开模型 API 缺少页面上实际收费的计费项。** 例如 `image_input`（35 个模型）、`image_output`（33 个）、`image_input_cache`（29 个）等。gpt-image-2 的 API 只列出 `prompt` 和 `input_cache_read`，模型页却列了 5 个计费项。另外，API 里的价格没有标明属于哪个供应商。
2. **模型级上下文长度与所有供应商都对不上，共 26 处。** 例如 doubao-seedance-2.5：模型级 100000，供应商和 API 都是 12800；kling-3.0：100000 对 20000。
3. **缺失或为 0 的数值。** 22 个供应商的 `max_completion_tokens` 为 0；API 中 30 个模型没有 `max_tokens`；29 个模型的别名为空；少数计费记录的费率为 0。
4. **`pricing_discount` 为 `"0"` 的模型有 4 个。** 不可能是真实的折扣倍数，skill 按「无折扣」处理并记录。
5. **27 个供应商带「Sunset」标记，但站内任何地方都没有解释。** skill 暂按「已停用」处理：不显示选择按钮，不参与最低价计算。如果 Sunset 的含义不同（例如仍可调用），改 `scripts/new_page.py` 中的状态映射即可。
6. **页面内嵌数据是唯一包含「按供应商的价格」的地方。** 页面结构一旦改版，`new_page.py` 会报错退出（退出码 5），而不是猜数字。建议提供一个带供应商维度的公开接口（或给 agent 内部接口），这样 skill 就不必依赖页面结构。

## 测试情况

- 用这套模板手工流程写过 3 个页面：DeepSeek V4 Pro、DeepSeek V4.1 Flash、GPT Image 2。新的起步脚本与这 3 个页面的手工台账逐项比对，价格、上下文、最大输出全部一致（V4.1 Flash 48 个价格、GPT Image 2 的 10 个计费项）。
- 解码脚本在全部 212 个线上模型页上运行，无一失败。
- 在 Codex（OpenAI gpt-6.1-sol）里端到端跑了两个从未测试过的类型，检查全部 PASS，0 条被判错误：
  - doubao-seedance-2.5（视频）：40 条核实，11 条收窄措辞，记录 17 个问题。
  - gemini-3.8-flash-tts（语音）：37 条核实，7 条收窄措辞，记录 15 个问题。
- 自动化测试：`cd zenmux-model-page && bash tests/run_tests.sh && bash tests/test_new_page.sh`（共 156 项，不需要联网）。

## 修改模板

模板在 `zenmux-model-page/references/plan.md`，附录 A 的 JSON 是脚本强制执行的规则（模块顺序、字段、显示条件、各类型变体、缺失值标签）。修改时文字部分和 JSON 要一起改；只有经过审批的版本才能保留 `status: approved`，`check_page.py` 会拒绝草稿模板。新增模型类型（如 transcription）需要先在模板里加对应的变体规则，并在 `zenmux-site.json` 的类型映射里登记。

## 目录结构

```
zenmux-model-page/
  SKILL.md              agent 读的操作说明
  zenmux-site.json      ZenMux 站点配置：API、sitemap、类型映射、公共文档列表
  references/           模板（plan.md）、台账格式、页面格式、事实核查方法
  examples/             已完成的示例页（文本：deepseek-v4-pro；图像：gpt-image-2）
  scripts/              起步、快照、检查、修复清单脚本；lint/ 为内置文风检查
  tests/                自动化测试
```

## 来源

以下内容来自 Wendy Writes 写作引擎：写作宪法（`references/page-format.md` 中的句子规则）、文风检查（`scripts/lint/`）、写作评审（`references/review.md`）和事实核查方法（`references/fact-check.md`），均已按模型页改编。
