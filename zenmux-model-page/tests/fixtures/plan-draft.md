---
plan_slug: acme-model-page
status: draft
checked_date: 2026-01-15
sample_url: https://example.test/acme/acme-model-7-5
sample_entity: Acme Model 7.5
---

# AcmeHub Model page 改版方案
# **改版目标：先回答价格，再回答能力，再回答怎么调用。**
SEO 目标：model + API 词族。
核查日期：2026-01-15；示例页面：Acme Model 7.5。

# **1. 参考竞品以及具体借鉴方向**
| 竞品与页面 | 具体参考点 | AcmeHub 对应改动 |
| :- | :- | :- |
| [Rival A · Model](https://rival-a.example.test/models/x) | 价格表按供应商分行 | M2；不抄价格 |
| [Rival B · Model](https://rival-b.example.test/models/y) | 能力状态表 | M3；不抄文案 |

# **2. 当前页面不足，以及对应修改思路**
当前页面已有价格摘要。
[当前页面](https://example.test/acme/acme-model-7-5)
| 当前不足 | 具体观察 | 改版动作 |
| :- | :- | :- |
| 能力只有图标 | 图标无文字 | M3 改为文字状态表 |

优先级：
🔥 HIGH IMPACT 为 M2；
⚡ MEDIUM IMPACT 为 M3；
⚠️ LOW IMPACT 为 M5，不阻塞首期。

# 3. 改版后的 Template
| 对应模块 | 承接的搜索意图 | 内容要求 |
| :- | :- | :- |
| M1 首屏 | {entity} API | 概览 |

## **M1 首屏：这是什么模型**
  - 显示：概览、价格摘要
## **M2 价格与供应商：多少钱**
  - 规则：同一 endpoint 的输入输出价
## **M3 能力：能做什么**
  - 规则：状态词表
## **M4–M5 性能与 FAQ**
  - 条件模块与 FAQ

# 4. 开发实施与验收
## **SEO 与移动端**
一个 H1。

# 附录 A：Template spec
```json page-template
{
  "template_id": "acme-model-page",
  "page_language": "en",
  "url_pattern": "/{developer}/{model-slug}",
  "title_pattern": "{Entity} API, Pricing & Providers | AcmeHub",
  "h1_pattern": "{Entity} API",
  "meta_description_rule": "One sentence.",
  "default_endpoint_rule": "M1 prices come from default_endpoint.",
  "status_vocabulary": ["Supported", "Not supported", "Not verified", "Varies by provider"],
  "missing_value_labels": {"price": "Not published", "version": "Not verified", "metric": "No data"},
  "entity_variants": {"text": "context, pricing", "image": "sizes"},
  "modules": [
    {"id": "M1", "name": "Hero", "required": true, "h2": null, "intent": [], "fields": [], "rules": [], "show_if": null, "status_table": false},
    {"id": "M2", "name": "Pricing", "required": true, "h2": "{Entity} Pricing", "intent": [], "fields": [], "rules": [], "show_if": null, "status_table": false},
    {"id": "M3", "name": "Capabilities", "required": true, "h2": "{Entity} Capabilities", "intent": [], "fields": [], "rules": [], "show_if": null, "status_table": true},
    {"id": "M4", "name": "Performance", "required": false, "h2": "{Entity} Performance", "intent": [], "fields": [], "rules": [], "show_if": "category:performance", "status_table": false},
    {"id": "M5", "name": "FAQ", "required": true, "h2": "Frequently Asked Questions", "intent": [], "fields": [], "rules": [], "show_if": null, "status_table": false, "derived_from": ["M2", "M3"]}
  ]
}
```
