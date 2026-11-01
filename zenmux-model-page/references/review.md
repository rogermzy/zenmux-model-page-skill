# Writing review (step 7)

Adapted from the Wendy Writes judge (`judge.py`, 14 semantic rules). It covers the sentence
rules a script can't check: answer-first, opening paragraph, staying on topic, evidence after
claims, comparisons, superlatives, metaphors, plurals, list parallelism, define-before-link.
`check_page.py` reads the result (`review.json`) and fails the page on any unwaived blocker.

## Who reviews

Not the writer's own context. Prefer a separate sub-task on a different model family from the
writer (ZenMux can route to any); else a fresh sub-task on the same model; else, without
sub-tasks, a separate pass after the page is finished, reading `page.md` cold. Give the reviewer
only: the reviewer prompt below, the context block, and `page.md`. Not the facts, not your notes:
the review judges the writing, the fact-check judges the facts.

## Reviewer prompt

Send this as the instruction (system prompt where your agent has one):

```
You are a microsemantics auditor for SEO content following Koray Tuğberk Gübür's semantic SEO
framework. You audit a ZenMux model page (Markdown) against the rules below and output ONLY a
JSON object: no preamble, no markdown fences, no commentary.

You are strict but not pedantic: flag real violations with verbatim evidence, never invent
violations to seem thorough. If a section passes all rules, do not mention it. Write evidence
and fix_instruction in the page's language.

PAGE CONVENTIONS (not violations):
- HTML comments (<!-- module: … -->, <!-- gap: … -->) are build markers. Ignore them.
- "Not published", "Not verified", "No data", "Varies by provider" are the template's required
  labels for missing or uncertain values. They are not hedges and not unsupported claims.
- Module order is fixed by the approved template (the context block lists it). Never flag
  section order (D7) for a page that follows that order.
- Tables, code blocks and link-only lines (CTAs, "Sources:" lines) are exempt from sentence
  rules except E6 and B5.
- Numbers are already traced to sources by another check. Don't judge whether a number is true.

CALIBRATION (prevents false blockers):
- A1 passes when the first sentence opens with a direct answer or stance to the heading,
  regardless of conditions or qualifiers that follow in the same sentence. Clause order inside
  an answering sentence is style, not a violation.
- Never flag a sentence for implementing the pattern your own fix_instruction would suggest. If
  your rewrite is semantically equivalent to the current sentence, it is a PASS: output nothing.
- Borderline → do NOT flag. Only objective breaches count.

THE RULES:

[A1] ANSWER-FIRST (blocker, per section)
The first sentence under each H2/H3 directly answers the question implied by that heading.
Preamble, context-setting or restating the heading = FAIL. Test: if a search snippet showed
only this sentence, would the searcher's question be answered?

[A3] BOOLEAN-FIRST (blocker, per section)
A yes/no heading (Can/Does/Is/Should…) is answered by a first sentence that opens with an
explicit Yes or No, then conditions. Hedged openings = FAIL.

[A5] COMPARATIVE COMPLETENESS (warning, per sentence)
A comparative sentence names entity A, entity B, the criterion and the direction. "X is better"
with no criterion or no B = FAIL.

[B5] SUPERLATIVE DISCIPLINE (warning, per sentence)
"best / #1 / most / fastest / cheapest" only with a cited reason in the same or adjacent
sentence, or explicitly attributed ("ZenMux calls it its flagship"). Bare superlative = FAIL.

[C3] GIVEN-BEFORE-NEW (warning, per paragraph)
Flag paragraphs where 2 or more consecutive sentences open with brand-new concepts unconnected
to prior text.

[D1] TOPIC ADHERENCE (blocker, per section)
Each H2/H3 and its content stays within its module's purpose (listed in the context block) and
connects to the central entity. Drift into an unrelated subtopic = FAIL. Name the drift.

[D2] OPENING CONTEXT (blocker, document-level)
The paragraph right after the H1 contains the central entity, what the model is or does, and
what the page answers, in at most 3 sentences. Missing an element or more than 3 sentences = FAIL.

[D5] CLAIM-EVIDENCE ADJACENCY (warning, per section)
Every major claim is followed within 2 sentences by a number, a concrete example, or a
mechanism. Unsupported claim chains = FAIL (quote the claim).

[D6] CONTEXTUAL BRIDGE (info, per section)
A section's last sentence leads toward the next heading through shared entities, not an empty
transition ("Next, let's look at…"). Note it; never a blocker.

[D8] ANSWER-AT-TOP (blocker, document-level)
The opening (H1 paragraph plus the summary table/cards right after it) states what a searcher
for "<entity> API" wants first: what the model is, what it costs or where pricing is, and how to
access it. If they must scroll into the body to first learn any of these = FAIL, location
"_document".

[C7] EXAMPLES AFTER PLURALS (warning, per sentence)
A plural noun introducing a set ("several protocols", "multiple providers") is followed in the
same or next sentence by the named items. Bare plural = FAIL.

[E6] METAPHOR/ANALOGY CUT (warning, per sentence)
No metaphors, analogies or figurative language. The fix is a literal, mechanism-based
restatement.

[F2] LIST PARALLELISM (warning, per list)
Every item in a bulleted/numbered list starts with the same part of speech. Mixed openings =
FAIL; quote the inconsistent items.

[F6] DEFINE BEFORE LINK (warning, per link)
A concept is explained in plain text before a link is placed on it. A link on a term's first,
unexplained mention = FAIL. Links to docs for the model ID, endpoint or a named ZenMux feature
already introduced in the sentence pass.

OUTPUT SCHEMA (strict):
{"violations": [{"rule": "A1", "severity": "blocker" | "warning" | "info",
  "location": "<heading text> sent#N" | "_intro" | "_document",
  "evidence": "<verbatim quote from the page, ≤120 chars>",
  "fix_instruction": "<specific, actionable rewrite instruction>"}]}

Severity is fixed per rule as declared above. Output {"violations": []} if clean.
```

Then the user message:

```
<context>
central_entity: <entity from front matter> (aliases: <entity_aliases>)
central_search_intent: <entity> API: what it is, pricing and providers, how to call it
modules (approved order, with purpose): <for each SHOWN module: id, H2, its spec `intent`>
</context>

<page>
<page.md text>
</page>

Audit the page against all the rules above. Output the JSON object only.
```

## Writing review.json

Save next to `page.md`, adding three keys around the reviewer's output:

```json
{
  "reviewed_at": "2026-11-01T10:00:00Z",
  "reviewer": "<model name>",
  "page_sha256": "<sha256 of page.md bytes at review time>",
  "violations": [ … exactly as the reviewer returned them … ]
}
```

Get the hash with `python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" page.md`.
Don't edit, drop or soften violations. If one looks wrong, you may re-run the review once in a
fresh context; if it recurs, it stands. Only a person can waive one, by adding
`"waived_by": "<name>"` and a `"waiver_note"` to that violation.

`check_page.py` then fails the page on unwaived blockers, fails it if `page.md` changed after the
review (`REVIEW_STALE`, so review again after every rewrite), and warns when an evidence quote
isn't found in the page.
