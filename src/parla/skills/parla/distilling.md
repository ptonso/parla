# Distilling cases into principles

To distill is to turn a group of cases that share a lesson into one rule in a guide. Cases are specific, dated and private. When several share a lesson, a principle for the guides says it once and the cases become its evidence.

## Read the group

`parla case lint` reports groups of active cases that share a topic and an audience. Read them with `parla case list --topic <t>`, and judge whether they share a lesson. Mention a group to the author once, and distill when they ask.

## Write the principle

First ask whether a pattern or a yes-or-no reading decides the lesson. If so, propose a constraint instead ([constraints.md](constraints.md)): the suite enforces it, and the guide stays short.

Otherwise put the principle on the page it belongs to: a topic page when the lesson holds generally, an audience page when the cases share an audience, a modality section when they share a modality. Use the rule format of the guides: a one-line rule, with its origin. State the quality the cases teach, in the author's terms, as a tendency the writer can apply with judgment. Prefer a structural limit (one main clause and one dependent clause) to a count of words, and use a number only when the author stated it. Avoid "always" and "never" in style rules, since guarantees belong to constraints. Give a rule one instruction.

The default view of `parla guide show` hides rule ids. Read them with `parla guide show <artifact> <part> --unformatted`, or `--topic <t> --unformatted`, when a rule has to name an id (`--overrides`) or be dropped.

Propose the principle with its evidence: the case ids and the lesson each one carries. Write it only after the author accepts the exact wording, with `parla guide add <page> <rule-id> --text ... --evidence <case-ids>`, which records the ids in the rule's origin and marks the cases distilled. They stay retrievable as examples.

## Ported rules that a case contradicts

`parla guide lint` reports a rule copied from texfy that an active case contradicts. Propose rewriting it or dropping it, and apply the author's choice with `parla guide add` (a replacement carrying `--overrides`) or by asking them to edit the page.

## Keep the guide inside its budget

Rules are atomic: an id and one instruction. A guide stays useful only while it fits its caps, so every proposal that adds to a topic is also a chance to tidy it. When you propose a new rule, a case group, or a constraint, read the topic page with `parla guide show --topic <t> --unformatted` and ask four questions:

- **Dedup.** Does another rule, the public topic note, a constraint or an engine check already say it? Propose dropping the redundant one.
- **Generalize.** Does the lesson refine a rule that exists? Propose rewriting that rule with `parla guide edit <id> --text ... --evidence <case-ids>`, showing the old and new wording side by side, instead of adding a sibling.
- **Merge.** Do several rules say one thing in pieces? Propose one rule that carries all of them. Add it with `--origin "merged from <ids>"`, then drop each rule it replaces.
- **Orchestrate.** Is a rule in the wrong place (a topic rule that belongs to an audience or a modality, a craft rule that a pattern could decide)? Propose moving it with `parla guide move`, or promoting it to a constraint.

`parla guide add` and `parla guide edit` warn when a topic page passes `[guides].max_page_words`. Treat the warning as a request to run these four questions on that page before adding more. Keep one theme per rule, in atomic form, so a later lesson edits one rule. The old wording is kept in the history file, so a proposal never costs the author anything. The author accepts each change, and you write it with the exact wording shown.

## Promoting and merging

When a rule becomes a constraint, or several rules merge into one rule, `parla guide drop <rule-id>` removes the old rule after the author accepts the move, and its text goes to the history. Add the new home first and drop second, so no knowledge is ever lost between the two steps.

## Pruning

Propose pruning stale cases one at a time, and mark accepted ones with `parla case mark <id> pruned`. A case the author reverses is marked `contradicted`.
