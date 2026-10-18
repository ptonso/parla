# Lean prompts and a constraint suite

**Affects:** [guides](../guides.md), [casebook](../casebook.md), [constraints](../constraints.md), [checks](../checks.md), [jobs](../jobs.md), [skill](../skill.md), [cli](../cli.md), [config](../config.md).

## Situation

`guide show paper introduction` printed 2365 words on the author's real guides: about 360 public, 320 private general and modality, 800 for five topics and 890 for eight cases. The author's guides hold 255 rules on 39 pages, ported from texfy and refined over many debug sessions. A single load holds only 30 to 40 rules, so the density came from volume and from mixing two kinds of instruction in one list: craft guidance ("write natural, breathable prose") and checkable constraints ("no sentence over 25 words"). Research the author collected puts the range where an agent follows a prompt reliably at about 500 to 1000 words, and says a model struggles to write naturally while counting words.

The prompt also carried bookkeeping that helps a human and costs the model attention: rule ids, origin headings, a statistics header, and the cases in full. A fresh install had a second problem: the package shipped no topic page, so `case add` failed on its first call.

## Alternatives considered

- **Shrink the budget and trim by hand.** A cap alone deletes knowledge, and the rules are the product of long debugging.
- **Two prompts, drafting and verifying, with the model checking its own draft silently.** Silent self-review is the weakest form of checking, and the tool already knows how to point at a location.
- **Three phases with a reviewer subagent before the author sees the output.** It adds a second agent and a second context, and the reviewer cannot ask the author a question. The author preferred one agent per job with a test-suite loop.
- **Split every topic into a style part and a rules part.** The real topic pages mix both kinds, and a guarantee that depends on the captain having picked the topic fails silently when the captain forgets it.
- **A fixed cap on the number of topics.** Topics differ in size, so the budget counts words.

## Decision

Style, constraints and cases are three stores with three delivery paths ([guides](../guides.md), [constraints](../constraints.md), [casebook](../casebook.md)).

- Style is delivered by topic pages the captain routes through hooks, within a budget of about 1000 words. The view the model reads is XML without ids or origins.
- Constraints leave the prompt. They run as a test suite inside `check` and `build`, report what failed and where, and cover three kinds: regex, structural and probe. A probe finds every span that needs a reader's judgment and frames the question, and the agent records a verdict with evidence.
- Cases appear as one-line hooks and are opened on demand.
- One worker per job runs the loop and returns only when the suite is green. The captain relays questions to the author, because a subagent cannot ask them.
- The package ships a short prose topic page per topic and a small set of taste-neutral constraints, so a new user starts with a working routing table and a first suite.

## What tipped it

The measurements. Cases were 40% of a load, and a load held about 35 rules, so the instruction count was never the problem. Moving checkable rules out of the prompt shortens it and also enforces them more reliably, because a test report is a located failure the model can fix, which a rule read 2000 words earlier is not.

## Trade-offs accepted

- Probes ask the same agent that wrote the text to verify it. Each probe is narrow, a pass needs quoted evidence, and the end block lists every verdict. A fresh reviewer for grounding probes stays an option if evaluation shows misses.
- A routing mistake by the captain loses craft guidance for that round. Guarantees are unaffected.
- Rule ids disappear from the default view, so a conflict report quotes the rule text, and distillation reads ids with `--unformatted`.
- `max_words` is replaced by a target and a tolerance, a breaking change to the author's config.

## Addendum: rules stay atomic, and the loop tidies them

While relocating the author's guides, merging nine overlapping rules into one paragraph looked like the quickest cut. The author preferred atomic rules (an id and one instruction), since a paragraph is hard to edit later and blurs the rule format. They also pointed out that an append-only loop makes the guide grow back past its budget whenever a new lesson arrives.

Decision: `guide edit` rewrites a rule in place, `guide drop` and `guide edit` keep the previous wording in an append-only history, `guide add` and `guide edit` warn when a topic page passes its cap, and the skill makes dedup, generalization, merge and rewrite part of every learning proposal ([guides](../guides.md#parla-guide-edit-rule-id---text-text---evidence-case-ids), [skill](../skill.md#supporting-pages)).

## Addendum: topics are general, and some are limited to modalities

The relocation showed topics written for one artifact kind (a CV bullet, a deck frame, a diagram, a paper abstract). The author asked for topics to be general subjects usable in any artifact, and for modality-specific rules to stay out of other modalities' calls. Making them modality sections of the modality page would have loaded them with every call of that modality. Instead a topic page may list the modalities it fits in `applicable`: `guide list topic --artifact` shows only the topics that apply, and a topic picked for the wrong modality fails before anything prints ([guides](../guides.md#topic-page)). This keeps the captain's routing and prevents a nonsensical topic set without adding to any prompt.
