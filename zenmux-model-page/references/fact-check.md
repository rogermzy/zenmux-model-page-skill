# Fact-check (step 7)

Adapted from the Wendy Writes fact-check protocol (stage 5.5) for model pages.

**Core rule: a verdict comes only from source text the checker has fetched and read. Judging
from model memory means one model that can hallucinate is reviewing another. That is not
allowed.** Memory goes stale: model names, prices and "current best" lists change monthly. It
also mixes things up: a model described with another model's features.

## Why this step exists when check_page.py already passes

`check_page.py` proves every number on the page traces to a fact, and every fact's quote exists
in a snapshot. It cannot tell whether:
- the quote actually supports the value, label and condition written on the page (a correct
  quote can still sit under the wrong label: "24-hour median" when the source is the latest hour);
- the source is the right one (a URL without its trailing slash that serves a different page);
- the snapshot is still current;
- the prose around the numbers says more than the sources do ("flagship", "best for codebases").

## Who checks

The checker must not be the writer's own context. In order of preference:
1. A separate sub-task on a **different model family** from the writer. ZenMux can route to any
   of them, so pick a different developer's model.
2. A separate sub-task on the same model, with a fresh context.
3. If your agent has no sub-tasks: finish the page, then do this step as a separate pass.
   Re-read each source from disk or the web for every fact. Don't rely on what you remember
   from writing.

Split the work into domains and run them in parallel when you can:

| Domain | Covers | Preferred sources |
|---|---|---|
| Prices | Every `price.*` fact, fee items, units, conditions, discounts, time-of-day bands | ZenMux page data snapshot; ZenMux pricing docs; developer pricing page (for developer prices only) |
| Specs & capabilities | Context, max output, modalities, versions/aliases, parameters, protocol support, routing | ZenMux page data; ZenMux docs; developer model card / docs |
| Performance, claims & links | Latency/throughput/uptime labels and windows, benchmark claims, every prose claim that isn't a fact, every link, code samples | ZenMux page; developer docs; the links themselves |
| Currency | Is the model still offered, deprecated, renamed or re-routed? Is any alternative named on the page still current? | Developer release notes / news, deprecation pages |

Give each checker: the list of facts it owns (id, label, display, condition, source_url,
quote), the page.md text for its modules, and this output format, one block per item:

```
CLAIM:   <fact id or quoted page sentence>
VERDICT: VERIFIED | REFUTED | NUANCED | UNVERIFIABLE
VALUE:   <what the source actually says>
SOURCE:  <exact URL>
QUOTE:   <short verbatim quote from the fetched text>
NOTE:    <for REFUTED/NUANCED: how the page and fact should change>
```

"Could not find it" is a valid answer (UNVERIFIABLE). Guessing is not.

## Getting the source text

Finding a URL and getting its text are different steps:

- **Finding:** web search, or any AI search tool, may be used only to locate candidate URLs. Its
  answers are never evidence; AI search citations are not guaranteed to appear in the page.
- **Getting the text,** in this order:
  1. `python3 $SKILL_DIR/scripts/snapshot.py <url> --dir <workspace>/sources --role fact`
     (browser user agent; many sites refuse default clients), then read the saved `.txt`.
  2. A real browser, if your agent has one, for content drawn by JavaScript. Save the visible
     text and add it with `--role fact --from-file <txt>`. Note in the report that it is rendered
     content. If ZenMux's page needs JavaScript to show a value, that is also a gap.
  3. The Wayback Machine, only when the live page refuses every fetch. Give the capture date.
- Avoid fetch tools that summarize pages through another model. Their "quotes" can be
  paraphrases.

**Drift:** re-fetch each live source once. If the live text no longer contains a fact's quote,
the snapshot is stale: snapshot again, update the fact (and page) from the new text, and say so
in the report.

## What each verdict does

| Verdict | Action |
|---|---|
| VERIFIED | Set `verdict: "VERIFIED"`. Nothing else. |
| REFUTED | Fix the fact (value, label, condition or source) to what the source supports, fix every place the page uses it, set the verdict on the corrected fact, then re-run `check_page.py`. A page that still uses a REFUTED fact fails the check. |
| NUANCED | Narrow the wording to the source: attribute it ("DeepSeek documents …"), scope it ("on Chat Completions"), or add the condition. Never narrow it with a disclaimer ("may vary", "not the same as", "in the sources checked"). Put the reason in the fact's `note`. |
| UNVERIFIABLE | Set the verdict. The page shows `Not verified` in that value's table cell, or deletes the sentence that stated it (no "could not be verified" prose: page-format rule 20), and it goes on the report's list for a person to decide. Never upgrade it yourself. |

Problems that point at ZenMux's own site go into `gaps[]` too, not only into the report. Examples:
an inconsistency between two ZenMux pages, a value the checker couldn't confirm anywhere, or a
price that looks like a typo.

## fact-check-report.md

```markdown
# Fact-check report — <Entity> (ZenMux model page)

Method: references/fact-check.md. <Who checked: model(s), how many parallel checks, domains.>
Snapshots dated <date> in ../../sources/; live sources re-fetched <date>. Drift: <none | list>.

Totals: <n> VERIFIED, <n> NUANCED, <n> REFUTED, <n> UNVERIFIABLE (<n> facts).

## REFUTED in the draft, fixed in the page
| Claim in draft | Finding | Fix |

## NUANCED, page reworded
| Item | Finding | Page now says |

## Open items for ZenMux
1. <What the site should publish or correct, and the gap id.>

## Needs a person
- <UNVERIFIABLE facts; acceptance items such as a live API call that returns an image or video.>
```

See `examples/*/fact-check-report.md` for finished reports.
