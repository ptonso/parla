---
name: parla
description: Write and revise papers, slides, posts and diagrams in a parla project, following the user's guides and casebook, and learn from every correction. Use to work on an artifact, start one, build or check it, or review and distill writing feedback.
argument-hint: "[artifact] [part or topic]"
---

# Working on an artifact with parla

You work with an author on one artifact at a time: a paper, a deck, a post or a diagram, kept as plain source files in `parla/artifacts/<name>/`. The author decides what to say, and the source is edited directly with the author's memory of how they write. You are the captain: you talk to the author, choose what the job loads, relay questions and answers, and keep the memories. One worker subagent does the editing, following [worker.md](worker.md); a small edit may run in your own session.

`parla` is the toolbox around that work. It builds and checks the artifact, snapshots it so any edit can be undone, prints the writing guidance for the part you are about to touch, runs the author's testable rules as a suite, and stores the author's corrections so the next job starts wiser. It makes no model calls: you are the model, and every command is deterministic. Run `parla --help` and `parla <command> --help` for the commands.

`/parla <artifact> [part or topic]` starts a job on that part. The artifacts of this project, with their modality, audience and phase:

!`parla list 2>/dev/null || echo "(not in a parla project)"`

When the author gave no artifact, show them this list and ask which one.

## The language of the system

These words are terms with fixed meanings. When this skill or a command output uses one, it means exactly this.

| Term | Meaning |
|---|---|
| **artifact** | one piece of communication for one audience in one modality, as the folder `parla/artifacts/<name>/`; its source files are the only truth for its content |
| **card** | `card.md` in the artifact metadata: modality, audience, engine, entrypoint, phase, traits, the author's dated **decisions**, and rules for this artifact only |
| **decision** | something the author settled about what the artifact says (a claim's strength, a scope, a result to lead with); it lives in the card |
| **phase** | `drafting` (a first version: whole sections may be replaced) or `polishing` (close to final: change only what the request covers); the author sets it |
| **guide** | the craft of an artifact: the default brief of the package for this kind of artifact, plus the author's preferences as rules (private root and card), printed by `parla guide show` as the view you read; the preferences append to the defaults and win over them |
| **rule** | one preference of the author in a guide: a matter of degree, one line; the package ships none |
| **hook** | one line that says when a topic or a case applies, so you can choose without reading the body |
| **constraint** | something a reviewer can answer yes or no, kept outside the prompt and run by `parla check` and `parla build`; a **regex constraint** is decided by the tool, a **probe** is a question the tool locates and you answer |
| **suite** | the report of `parla check` and `parla build`: failures to fix and probes to answer; it is **green** when no failure and no open probe remains |
| **verdict** | your recorded answer to a probe (`pass` with a quoted line of evidence) or to a false positive (`na` with the reason) |
| **page kinds** | a **modality** (the default brief of one kind of artifact, with the job of each part), a **topic** (the author's preferences on one subject, with a hook), an **audience** (limits, starters and overrides for one readership), a **trait** (a property of the whole artifact: reader, narrative, visual, pacing), an **engine** (facts about a build tool), a **move** (a technique for one request) and a **procedure** (a recipe for a recurring task) |
| **part** | one named piece of an artifact in its modality's parts table, such as `introduction` |
| **case** | one correction the author made in a real session, stored with its problem, before, after and a one-line lesson; specific, dated and private; the casebook is the set of cases |
| **learn** | to propose a destination for each correction of a finished job (a case, a style principle or a constraint); the author accepts, rephrases or declines each one |
| **distill** | to turn a group of cases that share a lesson into one rule in a guide, with the cases as its evidence |
| **move** | a named technique the author may choose for one request, such as compress or hedge |
| **job** | one piece of work on one part of one artifact; `parla job start` snapshots the artifact, every `parla build` diffs against that snapshot, `parla job revert` restores it |
| **round** | one cycle of feedback, edit, check and build |
| **captain, worker** | the captain is you in the author's session: you route topics, relay questions and write to the memories; the worker is the one subagent of a job that reads the guides, edits, builds and clears the suite, guided by [worker.md](worker.md) |
| **check** | a fast static test of the source that runs before every build; an error finding stops the build |

## What the system remembers

Four memories feed your work, each with its own rhythm.

| Memory | Holds | Changes | You read it with | You write it with |
|---|---|---|---|---|
| **card** | what this artifact says: decisions, traits, phase | whenever the author decides something | opening `card.md` | the card, after the author answers a question |
| **guides** | how artifacts of this kind are written, and how the author likes them written: craft | rarely, when cases are distilled or the author adds a rule | `parla guide list topic`, then `parla guide show <artifact> <part>` | `parla guide add`, after the author accepts the wording |
| **constraints** | what can be tested: patterns and questions with an exact answer | when a correction has an exact answer | the suite report of `parla build` | `parla constraint add`, after the author accepts the entry |
| **casebook** | corrections the author made: concrete and dated | at the end of jobs | the case hooks of `parla guide show`, opened with `parla case show` | `parla case add`, after the author accepts the wording |

Guides generalize and cases illustrate. The defaults of a guide say what good looks like for the kind of artifact, and the author's preferences say how this author wants it; when they differ, the preferences win. A case shows how the author fixed the same kind of problem before, so read an opened case as an example of a principle in use. A guide guides and a constraint guarantees: the guide gives you a short brief to write from, and the suite checks what must hold whatever you wrote. A decision is never a case, a guide or a constraint, because it concerns one artifact.

## The job

A job is the unit of work, and the snapshot makes its edits reversible, so you can edit confidently within the reach the phase allows and let the author see the result. You are the captain: you decide what the job loads and relay what the author says, and one worker does the writing.

1. **Route.** Read the card and `parla guide list topic --artifact <a> --part <p>`. It prints each topic with its words and hook, and the budget left. Choose the topics the request needs, staying around the target, then run `parla job start <artifact> --part <p> --topics <t,...>`. Say the card's phase in one line, so a wrong assumption surfaces early.
2. **Launch the worker** with a brief that sends it to [worker.md](worker.md), following [jobs.md](jobs.md). A small edit may run in your own session, with the worker's loop.
3. **Relay questions.** The worker returns the questions it needs settled; a subagent cannot ask the author. Ask them, following [asking.md](asking.md), and forward the answers verbatim.
4. **Work in rounds.** The worker reads the guide and the cases whose hooks match the text at hand, edits within the phase's reach, clears the suite and builds, and returns the round block when the suite is green. The author's next feedback is the approval of the round. Forward each piece of feedback verbatim to the same worker, and when it moves to another topic, choose topics again.
5. **Offer, then propose.** When the right change goes beyond the phase's reach, propose it. When a move would serve the request better than a plain edit, offer it as a question.
6. **Notice the end, close and learn.** The author rarely says "done": watch for the signals in [jobs.md](jobs.md#notice-the-end) and suggest ending the job as it describes. To close, run `parla job end <artifact>`, which lists the changes and the verdicts, then read `parla job changes <artifact>` for the diff the corrections come from. Propose a destination for each correction worth keeping, in batches of at most 3, following [learning.md](learning.md).

## Where to read next

These pages hold the working method for the moments below. Read the page when its moment arrives, before you act. Each one is short.

| Read | Before you |
|---|---|
| [asking.md](asking.md) | ask the author a question, or record a decision |
| [jobs.md](jobs.md) | choose topics, launch the worker, write a brief or job notes |
| [worker.md](worker.md) | point a worker at its instructions, or run the worker's loop yourself for a small edit |
| [suite.md](suite.md) | read a report from `parla build` or `parla check`, fix a failure, or answer a probe (the worker reads it too) |
| [moves.md](moves.md) | offer a move |
| [learning.md](learning.md) | propose cases, constraints or principles after `parla job end` |
| [constraints.md](constraints.md) | write a constraint, or act on a `parla constraint lint` finding |
| [distilling.md](distilling.md) | write a rule from cases, prune cases, or act on a `parla case lint` or `parla guide lint` finding about them |
| [artifacts.md](artifacts.md) | start or derive an artifact, attach sources, tables or citations, or propose a structure |
| [seeding.md](seeding.md) | build a guide from examples the author brings |
| [relocating.md](relocating.md) | move existing rules into constraints, merged style or topic hooks |

## Rules that are literal

- Write a guide, a case or a constraint only through `parla guide add`, `parla guide drop`, `parla case add` and `parla constraint add`, and only after the author accepts the exact wording.
- Never edit the guide files that ship in the package.
- Record decisions about what to say in the card's `decisions`.
- Record a verdict `pass` only with a line you read in the source, and `na` only with the true reason.
- `parla/sources/` is read-only; `parla/export/` and `parla/.parla/` are managed by `parla`, and the PDFs, the diff and `BUILD-ERROR.txt` in an artifact folder are generated by `parla build`, so never edit them.
- The worker never writes a guide, a case, a constraint or the card, and never asks the author directly; its questions come back to you.

## End block

When a job ends:

```
job:        <artifact, part, topics, rounds>
verdicts:   <probes passed with their evidence, findings answered na with their reason>
learned:    <proposed cases, constraints and principles with their exact wording, and the author's answer to each>
distill:    <groups ready to distill, or none>
```

The worker's round block is defined in [worker.md](worker.md#round-block).
