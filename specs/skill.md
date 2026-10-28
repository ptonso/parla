# parla Skill Spec

Related: **Read first** [architecture](architecture.md), [guides](guides.md), [jobs](jobs.md), [casebook](casebook.md). **See also** [constraints](constraints.md), [cli](cli.md), [checks](checks.md).

## Overview

The `parla` skill is how a coding agent uses the tool. It holds no writing principle of its own: every principle reaches the agent through `parla guide show`, so the skill links to the author's guides and never hardcodes them. What the skill holds is the working method: how a job runs, which decisions belong to the author, when to propose a move, how to capture a case, and how to distill.

It follows the patterns of `create-skills`: a thin `SKILL.md` that opens with context and routes through one registry, supporting pages for each situation, a few strict rules in one place, fixed return blocks, and a design log the agent never reads.

The skill ships in the package at `parla/skills/parla/`. `parla init` links it into the project for Claude Code and opencode ([cli](cli.md#parla-init---force---local)).

Walk-through: the author types `/parla icra-paper results`. The skill is the captain: it reads the card, runs `parla guide list topic --artifact icra-paper --part results`, and picks `tables,figures,claims` from the hooks and sizes. It runs `job start --part results --topics tables,figures,claims` and launches one worker with a brief. The worker runs `guide show icra-paper results`, opens the case hooks that apply with `case show`, and returns two questions. The captain asks the author and forwards the answers. The worker edits the source, runs `build`, fixes the failures the suite lists, resolves each probe with evidence, and returns the round block when the suite is green. The author gives feedback, which goes to the same worker. When the author is done, the captain runs `job end`, proposes the cases and constraints that the corrections justify, and the author accepts or declines each.

## Language

- **Round**: one cycle of feedback, edit, build and suite.
- **Captain**: the skill agent in the author's session. It routes, relays questions and writes to the memories after the author accepts.
- **Worker**: the one subagent of a job. It reads the guides, edits, builds and clears the suite.
- **Suite, green, probe, verdict**: see [constraints](constraints.md#language).
- **Round block, end block**: the fixed return formats.
- **Registry**: the table in `SKILL.md`, "Where to read next", that routes each moment to the page the agent reads before acting.

## Map

```
skills/parla/
  SKILL.md        context, the glossary, the memories, the job, the registry, strict rules, the return blocks
  asking.md       which decisions are the author's, how to ask, recording answers in the card
  jobs.md         starting, running and ending a job; topic routing, the brief that sends the worker to worker.md, job notes
  worker.md       the worker's own page: the loop, the questions it returns, what it never does, the round block
  suite.md        reading the suite report, fixing a failure, verifying a probe, answering not applicable
  constraints.md  proposing a constraint from a correction, the regex and its examples, locators
  learning.md     proposing cases, constraints and style principles at the end of a job
  distilling.md   turning a group of cases into a principle, and pruning
  moves.md        when a move helps, and how to propose it
  artifacts.md    starting an artifact, writing its card, deriving one from another
  seeding.md      building a guide page from good examples
  relocating.md   moving existing rules to constraints, merged style and topic hooks, in batches
  logs/           design history, read only when revising the skill
```

## Contracts

### Frontmatter

```yaml
name: parla
description: Write and revise papers, slides, posts and diagrams in a parla project, following the user's guides and casebook, and learn from every correction. Use to work on an artifact, start one, build or check it, or review and distill writing feedback.
```

### Context

`SKILL.md` opens with what `parla` is and what the agent does with it: it works with an author on one artifact at a time, edits the source directly, and takes how to say things from the author's memory while the author decides what to say. It then gives the agent two orientation tables before any procedure.

- **The language of the system**: a glossary of the terms that look like ordinary words (artifact, card, decision, phase, guide, rule, the page kinds, part, case, learn, distill, move, job, round, captain, worker, check, constraint, probe, suite), each with one fixed meaning.
- **What the system remembers**: the card, the guides, the constraints and the casebook, each with what it holds, how fast it changes, how the agent reads it and how it writes it. It states that guides carry craft and constraints carry what can be tested, that cases illustrate, and that a decision is never a case, a guide or a constraint.

### The job loop

1. **Route.** Read the card. Run `parla guide list topic --artifact <a> --part <p>`, which prints each topic with its hook and its words, and the budget left. Choose the topics the job needs from the author's request, the hooks and the sizes, staying around the target. Run `parla job start <artifact> --part <p> --topics <t,...>`. When the session began with `/parla <artifact> <part>`, the author's words are the request.
2. **Launch the worker.** Write the brief and launch one worker for the job, following `jobs.md`. A small edit may run in the captain with `guide show --topics`; the suite is the same.
3. **Questions.** The worker returns questions it needs settled: a decision about what to say that the request, the text and the card do not settle, or a wording the guides leave open. The captain asks the author, following `asking.md`, and forwards the answers verbatim. A subagent cannot ask the author.
4. **Rounds.** For each piece of feedback, forward it verbatim to the same worker. The worker:
   - runs `guide show`, and `case show` for the hooks that match the text at hand;
   - edits within the reach the card's phase allows ([jobs](jobs.md#phase)), and proposes a larger change;
   - runs `parla build`, fixes every failure the suite lists, and resolves every probe, following `suite.md`;
   - returns the round block only when the suite is green.
   When the feedback moves to another topic, the captain reads the topic table again and sends the worker the new topics.
5. **Offer a move** when one would help, following `moves.md`, and load it on acceptance with `guide show --move`.
6. **Notice the end.** The author rarely says "done". The signs are an approval with no open question, a turn to another part, artifact or subject, a substantial amount of landed work with thinning feedback, and a request to commit or export. The captain acts by the author's message: when its own reply is probably the job's last, it closes the reply with one line suggesting the end; on a short message that moves on ("good, next"), it suggests the end before starting the next thing; on a substantial unrelated request, it asks before answering whether the request is part of the job, whether to end and review now, or whether to end now and hold the review. A held review waits until the new work settles, so a flow of ideas is never interrupted, and is then proposed in one line. When the job's context grows too large, propose writing job notes and continuing in a fresh worker, and ask.
7. **End.** On "done", or when the author accepts ending:
   - Run `parla job end <artifact>`, which lists the changed files and the verdicts, and `parla job changes <artifact>`, the diff the corrections are read from ([jobs](jobs.md#parla-job-changes-artifact)). A held review on an artifact whose next job starts first saves that diff to the job folder before `job start`.
   - Propose a destination for each correction worth keeping, following `learning.md`: a case, a style principle or a constraint. Batches of at most 3, triaged with a toggle list and then phrased one question per case.
   - When `parla case lint` or `parla constraint lint` reports a group, mention it once; distill when the author asks, following `distilling.md`.
   - Answer with the end block.

### Where to read next

A table of moments: it names the page the agent reads before acting at that moment, and states that the page is required reading for it.

| Before the agent | Page |
|---|---|
| asks the author a question or records a decision | `asking.md` |
| routes topics, launches the worker, writes a brief or notes, or edits in the `polishing` phase | `jobs.md` |
| reads a suite report, clears a failure, resolves a probe | `suite.md` |
| proposes cases, constraints or style principles after `job end` | `learning.md` |
| writes a constraint or acts on a `constraint-refine` finding | `constraints.md` |
| writes a rule from cases, prunes cases, or acts on a lint finding about them | `distilling.md` |
| offers a move | `moves.md` |
| starts or derives an artifact, attaches sources, tables or citations, or proposes a structure | `artifacts.md` |
| builds a guide from examples the author brings | `seeding.md` |
| moves existing rules to constraints or merges them into style | `relocating.md` |

### Strict rules

- Guides, cases and constraints are written only through `parla guide add`, `parla guide drop`, `parla case add` and `parla constraint add`, and only after the author accepts the exact wording.
- Package guide files are never edited.
- Decisions about what to say go to the card's `decisions`, never to a guide, a case or a constraint.
- A verdict `pass` quotes the evidence it read, and a verdict `na` gives its reason. Neither is given to clear a report.
- A failure is fixed with the smallest edit, and text the job did not change stays as it is.
- `sources/` is read-only.
- The worker never writes a guide, a case, a constraint or the card, and never asks the author directly.

### Return blocks

Round block, after each round that changed something:

```
changed:    <what, where, in a few lines>
asked:      <decisions requested, or none>
conflicts:  <rules that disagreed, quoted, and which one won>
opened:     <cases opened with case show, or none>
suite:      <the summary line, and each verdict na with its reason>
proposed:   <a move, a larger change, or ending the job, or none>
```

End block, when a job ends:

```
job:        <artifact, part, topics, rounds>
verdicts:   <probes passed with their evidence, findings answered na with their reason>
learned:    <proposed cases, constraints and principles with their exact wording, and the author's answer to each>
distill:    <groups ready to distill, or none>
```

### Supporting pages

| Page | Carries |
|---|---|
| `asking.md` | the decisions that belong to the author: a claim's strength, the scope of a part, what to include or leave out, which version of a result to use, how to position against a named paper, which result to lead with; wording, order within a paragraph and anything a principle settles need no question; one question at a time with the options the agent sees; recording each answer in the card with its date |
| `worker.md` | the worker's role as a subagent that cannot talk to the author; the loop (read the guide, open the cases that apply, read the text, return questions, edit, clear the suite, return the round block); what it never writes; the round block |
| `jobs.md` | reading the topic table and choosing topics around the target; the brief at `.parla/jobs/<id>/brief.md`, which opens with a line sending the worker to `worker.md` and `suite.md` and then holds the artifact, the part, the phase, the author's words verbatim, the chosen topics, what changed as pointers to files and never as summaries, decisions not yet in the card, the captain's suggestion labelled as such, what must not change; the questions protocol between worker and captain; forwarding each round verbatim to the same worker; changing topics mid-job; small edits in the captain; job notes at `.parla/jobs/<id>/notes.md` when the context grows too large |
| `suite.md` | reading the report; fixing a failure with the smallest edit; verifying a probe with the tool its finding names and quoting the line that proves it; when `na` is honest; never rewriting text the job did not change to silence a hit; returning only when the suite is green |
| `constraints.md` | when a correction is a constraint; writing the regex with a sentence it must match and one it must not; choosing a locator for a probe; the `hint` flag; acting on a `constraint-refine` finding |
| `learning.md` | what makes a correction worth keeping; reading the rounds and notes for corrections that recur or reverse; choosing the destination (a regex answers it, a reader answers yes or no, a matter of degree, an illustration) and whether a lesson adds a rule, revises one or merges several; phrasing a lesson as one line about the quality, never about the sentence; writing the hook as a situation recognizable in a draft; choosing topics; proposing before and after in batches of at most 3 through a triage toggle and a phrasing question per case; accepting a decline without argument |
| `distilling.md` | reading a group from `case lint`; writing the principle at the right level and on the right page, without "always" and "never" and with a structural limit instead of a count unless the author stated the number; reading rule ids with `guide show --unformatted`; proposing it with its evidence; marking cases distilled through `guide add --evidence`; keeping the guide within its caps by proposing dedups, generalizations, merges and rewrites with `guide edit`, `guide add` and `guide drop` whenever a page nears or passes its cap or a lesson refines an existing rule; dropping a promoted rule with `guide drop`; proposing pruning one case at a time |
| `moves.md` | the signals that suggest a move (a passage over budget, a claim stronger than its evidence, an explanation a newcomer cannot follow); phrasing the offer as a question with the move named |
| `artifacts.md` | `parla init artifact`; writing the card with the author: modality, audience, engine, phase, traits; deriving an artifact and setting `derived-from`; variants as copies; declaring `sources/` links, tables, formulas and finding citekeys; proposing a structure |
| `seeding.md` | reading examples, extracting candidate principles, proposing them one at a time, filing each under the right topic, audience or modality |
| `relocating.md` | taking the inventory of rules and cases; proposing in batches a move to a regex constraint, a probe, a merged style description or a topic hook; stating public or private for each item and defaulting to private; applying only accepted items and measuring the sizes again |

### Design log

`skills/parla/logs/` follows the `create-skills` design log: an index for the human and one note per working day holding why the skill is the way it is. Feedback on the skill itself goes there and into the skill as a generalized principle. Feedback on writing goes to the casebook, never to the skill.

## Constraints

- `SKILL.md` MUST carry no writing principle; every principle reaches the agent through `guide show`.
- The skill MUST NOT write a guide, a case, a constraint or the card without the author's accepted wording.
- The captain MUST run one worker per job except for a small edit, MUST relay the worker's questions to the author, and MUST propose ending or restarting a job and ask.
- A round MUST end with a green suite before the worker returns its block.
- Every supporting page MUST be reachable from the registry, and every term of the glossary MUST have one meaning across the skill and its pages.
- The skill folder MUST NOT hold the author's private guides or cases.

## History

- [Guides and casebook](logs/2026-10-14_guides-and-casebook.md): why the skill links to guides and does not hold them.
- [Jobs and the snapshot diff](logs/2026-10-14_jobs.md): the worker edits directly and the diff and revert are the safety.
- [Lean prompts and a constraint suite](logs/2026-10-18_lean-prompts.md): the captain, one worker per job, the suite loop and topic routing.
