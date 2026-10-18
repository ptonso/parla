# parla Casebook Spec

Related: **Read first** [architecture](architecture.md), [guides](guides.md). **See also** [constraints](constraints.md), [jobs](jobs.md), [cli](cli.md), [config](config.md).

## Overview

The casebook is the volatile memory: concrete corrections the author made in real sessions, each with the problem, the fix, a before and after, and the lesson. Cases are specific, dated and private. `guide show` lists the ones that concern what is being loaded as one-line hooks, and the agent opens the ones that apply with `case show`, so it sees how the author fixed the same kind of problem before without carrying every case in its prompt. When several cases share a lesson, the agent proposes a principle for the guides and the cases become evidence for it.

Nothing is captured silently. At the end of a job the agent proposes cases in batches of at most 3, and the author triages each batch with a toggle list and then picks or rephrases the lesson of each kept case. Decisions about what to say never enter the casebook; they go to the card.

Walk-through: in a job on the introduction, the author twice rewrites a contribution from "a tool that aggregates rules" to "lets an analyst inspect a fitted ensemble". At job end the agent proposes one case with that before and after and the lesson "a contribution states what the reader can now do". The author accepts, and `case add` appends it. Months later three active cases on `contributions` for the same audience exist; `case lint` reports the group, and the agent proposes a rule for `topic/contributions`, or a [constraint](constraints.md) when a pattern or a reader's yes or no answers the lesson.

## Language

- **Case**: one entry of the casebook.
- **Lesson**: one line about the quality, never about the sentence.
- **Active, distilled, contradicted, pruned**: the case statuses.
- **Distill**: write a principle from a group of cases.
- **Retrieval**: listing the hooks of the cases that concern a `guide show`.
- **Hook**: one line that says in which situation a case applies, written as something recognizable in a draft, such as "a table caption that carries definitions". The lesson states the rule, and the hook states when to open the case.

## Map

`parla.casebook` owns the store, retrieval and lint. It is read by `parla.guides` for `guide show` and written by `guide add --evidence`. The usage log is written when a case is opened, not when it is listed.

## Contracts

### Store

Two append-only files under `[guides].private`:
- `cases.jsonl`: one JSON object per line. A later line with the same `id` updates the fields it carries, so the current state of a case is its lines folded in order.
- `cases.use.jsonl`: one line per retrieval, `{"case": "c-0412", "date": "...", "artifact": "..."}`.

### Entry

```json
{"id": "c-0412", "date": "2026-10-14", "artifact": "icra-paper", "part": "introduction",
 "topics": ["contributions"], "modality": "paper", "audience": "icra",
 "hook": "a contribution that restates the method",
 "problem": "contributions restated the method instead of what it enables",
 "before": "We propose AcmeTrees, a tool that aggregates rules...",
 "after": "AcmeTrees lets an analyst inspect a fitted ensemble without a surrogate...",
 "lesson": "a contribution states what the reader can now do",
 "contradicts": [],
 "status": "active"}
```

- `contradicts` is an optional list of rule ids the case argues against.
- `status` is `active`; `distilled` (its lesson lives in a principle that names it as evidence); `contradicted` (a later case reversed it); or `pruned`.
- `modality` and `audience` are copied from the card at capture.

### `parla case add`

Reads one JSON object from standard input with `artifact`, `part`, `topics`, `hook`, `problem`, `before`, `after` and `lesson` (and optionally `contradicts`). It assigns `id` (`c-` and the next number), `date`, `modality`, `audience` and `status: active`, appends the entry and prints the id. Fails on a missing field, an unknown artifact, or a topic with no page in either root of the guides. A hook of more than one line fails.

### `parla case show <id>[,<id>...] [--artifact <a>]`

Prints each case in full, in the form the model reads, and appends one line per case to `cases.use.jsonl`, naming the artifact when `--artifact` is given. Fails on an unknown id.

```
<case id="c-0009">
<problem>parallel sentences repeated the same verb</problem>
<after>... and fidelity scores how well this holds...</after>
<lesson>parallel sentences avoid repeating one verb</lesson>
</case>
```

### `parla case list [--topic <t>] [--status <s>]`

Prints one line per case: id, status, topics, audience, hook and lesson.

### `parla case edit <id>`

Reads one JSON object from standard input with any of `hook`, `lesson`, `problem` and `topics`, and appends it as an update line. The `before` and `after` cannot change. A hook or lesson of more than one line fails, and so does an unknown topic. The agent uses it to add a hook to a case that lacks one and to sharpen a lesson.

### `parla case mark <id> <status>`

Appends a status change. `distilled` is also set by `guide add --evidence`.

### Capture

At the end of a job, the agent reads the job's corrections and proposes cases in batches of at most 3, in two steps: triage, then phrasing. A case carries a hook, the problem, a one-line lesson, the topics, and the before and after. Each correction gets a proposed destination: a case, a style principle, or a [constraint](constraints.md), and a case that becomes a constraint or a principle is marked `distilled`. Collecting them at the end shows which corrections recurred and which were reversed within the job. The author accepts, rephrases or declines, and only accepted cases are written.

### Retrieval

`guide show` lists each retrieved case as `id: hook` and does not print the case body. It retrieves every active or distilled case that concerns the load: one of the case's topics is among the loaded topics, and its audience and modality match the card or are absent. Over `[guides].max_cases`, cases are kept in this order: same artifact, same audience, same modality, most recent. Contradicted and pruned cases are never retrieved. Listing a hook does not log a use; opening the case with `case show` does, so `case lint` measures the cases the agent read.

### `parla case lint`

Prints findings in the [finding format](checks.md#finding). It reports:
- **ready to distill**: `[guides].distill_min` or more active cases (default 3) that share a topic and an audience. The agent judges whether they share a lesson.
- **stale**: active cases not opened for `[guides].stale_days`. With `stale_days` unset, no stale report is made.

### Distillation

For a group the agent proposes a principle for the right page: a topic page when the lesson holds generally, an audience page when the cases share an audience, a modality section when they share a modality. On acceptance it runs `guide add --evidence <ids>`, which records the ids in the rule's origin and marks the cases `distilled`. They stay retrievable as examples of the principle.

### Pruning

The agent proposes pruning stale cases one at a time, and marks accepted ones `pruned`. A case the author reverses is marked `contradicted`.

### Ported principles learn too

Rules ported from texfy carry `origin: texfy ...`. When an active case lists a ported rule in `contradicts`, `guide lint` reports it, and the agent proposes rewriting or dropping the rule.

## Constraints

- `cases.jsonl` MUST be append-only; no command rewrites or deletes a line.
- A case MUST NOT be written without the author's acceptance. The skill enforces this.
- A case MUST carry a one-line lesson.
- Retrieval MUST NOT return contradicted or pruned cases.
- A case MUST carry a one-line hook.
- `guide show` MUST NOT write the usage log; only `case show` does.
- Decisions about what to say MUST NOT be stored as cases.
- Case ids MUST be unique and never reused.

## History

- [Guides and casebook](logs/2026-10-14_guides-and-casebook.md): why corrections live in a casebook and become principles only through distillation.
- [Lean prompts and a constraint suite](logs/2026-10-18_lean-prompts.md): why cases appear as hooks and open on demand.
