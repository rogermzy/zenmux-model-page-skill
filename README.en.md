# zenmux-model-page skill

An agent skill that writes the content of a zenmux.ai model page on demand, following ZenMux's
approved model-page template (modules M1–M9). Every price, spec, version and date on the page
comes from a quoted, saved source. The skill produces, per model:

- `page.md`: the page content, module by module, with module markers for the build;
- `facts.json`: the fact ledger behind every number, plus the gaps found;
- `fact-check-report.md`: what was verified, reworded or left for a person;
- `review.json`: the writing review against Wendy Writes' semantic rules;
- `acceptance.json`: the acceptance review, a fixed checklist per model type taken from the
  template's Part 4 acceptance rules;
- `site-fix-requests.md` (shared across pages): what the ZenMux site itself should publish or
  correct, with quotes.

Supported model types: text, image, video, audio (speech). Other types (transcription,
embeddings, rerank) have no template yet; the skill says so and stops.

## Requirements

- An agent that can read files, run shell commands and fetch URLs. Web search helps for finding
  developer docs.
- Python 3.9 or newer. Standard library only; nothing to install.
- Works with any model. Sub-agents are optional (used for parallel fact-checking when
  available).

## Install

The skill is the `zenmux-model-page/` folder (it contains `SKILL.md`). Copy or link it where
your agent loads skills:

| Agent | Location |
|---|---|
| Claude Code | `~/.claude/skills/zenmux-model-page/` or `<repo>/.claude/skills/zenmux-model-page/` |
| Codex CLI | `~/.codex/skills/zenmux-model-page/` or `<repo>/.agents/skills/zenmux-model-page/` |
| Claude Agent SDK / other Agent Skills hosts | the host's skills directory |
| An agent without skill support | put the contents of `SKILL.md` in its system prompt and give it the folder path |

## Use

Ask the agent, for example:

> Write the ZenMux model page for Claude Opus 5.5.
> Refresh the DeepSeek V4.1 Flash page.
> Make model pages for doubao-seedance-2.5 and gemini-3.8-flash-tts.

All pages share one workspace (default `./zenmux-pages/`), so ZenMux's shared docs are fetched
once and reused for 14 days.

Titles and meta descriptions have no length limit: longer is better, with more name variants
and related entities (model ID, aliases and revision, developer, providers, billing conditions,
context, capabilities, example languages). A title starts with `{Model} API` and ends with
`| ZenMux`; any number in it must come from the fact ledger, like every number on the page.

The writing review runs outside the writer's context, ideally on a different model family. With
Codex CLI as the reviewer, end the command with `< /dev/null`
(`codex exec -s read-only --skip-git-repo-check -o out.txt "<prompt>" < /dev/null`): without it,
`codex exec` waits for stdin and never finishes in the background.

## Acceptance review

After the writing review, a second reviewer outside the writer's context checks the finished
page against the template's Part 4 acceptance rules, as a fixed checklist in
`references/acceptance.md`: the model named the same way in title, H1 and opening; one default
endpoint across M1, M2, M3, M4 and the FAQ; revisions; missing data; the page never
contradicting itself; CTAs and code for the model type; links; model-specific content; coverage
on par with the matching example page; the live call; and the type's own rules (for images:
per-provider context, a billing-items table, capabilities by protocol, completion time). It
saves `acceptance.json`. `check_page.py` fails the page on a failed blocker item or an
unanswered item, and any edit to the page makes the review stale. Acceptance items only ZenMux's
site can meet (server-rendered HTML, mobile layout, canonical and sitemap, links into the page,
the GSC baseline) are listed in the report for ZenMux's developers.

## No disclaimers or production notes

Pages state facts and stop. Vague disclaimers ("cannot be determined", "not yet verified",
"is not the same as", "may vary", "for reference only"), third-party or reviewer voice
("ZenMux says…", "users report…", "a solid choice"), production notes ("suggested wording",
TODO, "to be confirmed") and sentences that follow a statement to caveat its data are rewritten
as plain attributed facts or removed. Missing-value labels (`Not verified`, `Not published`,
`No data`) appear only in table cells. `check_page.py` blocks these as `NOTE_*` errors and the
writing review checks them as rule N1.

## What a person still decides

- Whether to publish a page; the skill never marks one as ready while items are open.
- Facts the fact-check left UNVERIFIABLE (shown on the page as `Not verified`).
- The live call (acceptance item G12): one call with the code sample that returns a real result
  of the model's output type, to confirm the model ID (needs a ZenMux API key in
  `$ZENMUX_API_KEY`). It matters most for image and video models.
- Who acts on `site-fix-requests.md`.

## Changing the template

The template is `zenmux-model-page/references/plan.md`; its appendix A JSON is what the scripts
enforce. Change the prose and the JSON together, and keep `status: approved` only for a version
someone has approved. `scripts/check_page.py` refuses a draft template.

## Tests

```bash
cd zenmux-model-page && bash tests/run_tests.sh && bash tests/test_new_page.sh
```

## Credits

From the Wendy Writes engine, adapted for model pages: the writing constitution (sentence rules in
`references/page-format.md`), the style linter (`scripts/lint/`, vendored; its blockers fail the
check), the writing review (`references/review.md`, from Wendy's judge) and the fact-check
protocol (`references/fact-check.md`).
