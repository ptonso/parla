# parla Jobs Spec

Related: **Read first** [architecture](architecture.md), [template](template.md). **See also** [constraints](constraints.md), [cli](cli.md), [latex engine](latex-engine.md), [guides](guides.md), [casebook](casebook.md).

## Overview

A job is one piece of work on one part of one artifact, over as many rounds of feedback as it takes. `parla` supports a job with three things: a snapshot of the artifact taken at the start, a folder for the job's brief and notes, and the rule that every build in the job diffs against the snapshot.

The snapshot gives the author two views the agent cannot fake: the diff PDF, which shows everything the job changed so far, and `job revert`, which undoes the whole job. The brief and notes let a job continue in a clean subagent or a fresh context without losing the author's steering.

Walk-through: the agent runs `job start icra-paper --part results`, which copies `artifacts/icra-paper/` to `.parla/jobs/20261014T153000Z/snapshot/`. It edits and runs `build` over several rounds; each build publishes `icra-paper_diff.pdf` against the snapshot. The author is happy and the agent runs `job end icra-paper`. A week later the author wants none of it: `job revert icra-paper` restores the artifact from the snapshot.

## Language

- **Job id**: the UTC start time as `yyyymmddThhmmssZ`, such as `20261014T153000Z`.
- **Snapshot**: the copy of the artifact folder taken by `job start`.
- **Active job**: the newest job of an artifact that has not ended.
- **Brief**: `brief.md`, the message a subagent starts from.
- **Notes**: `notes.md`, what a continuing context needs: decisions, steering so far, open threads.
- **Reach**: how far an edit may go, set by the card's `phase`.
- **Topics**: the style topics the captain chose for the job; `guide show` prints them.
- **Verdicts**: the agent's recorded answers to open probes and false positives of the suite ([constraints](constraints.md#verdicts)).

## Map

`parla.jobs` owns the job folder, the snapshot and the revert. `engines.latex.build` asks it for the active job's snapshot.

## Contracts

### Job folder

```
parla/.parla/jobs/<id>/
  job.toml        artifact, part, topics, started, ended
  snapshot/
    artifacts/<artifact>/...
  brief.md
  notes.md
  verdicts.jsonl
```

`job.toml` is written by `parla`. `brief.md` and `notes.md` are written by the agent; `parla` never reads them. `verdicts.jsonl` is appended by `parla check --resolve`. The snapshot mirrors the project layout, so it is a valid [diff baseline](latex-engine.md#diff).

### `parla job start <artifact> [--part <part>] [--topics <t,...>]`

Creates the job folder and the snapshot.
- Fails when the artifact has an active job.
- `--topics` names topics of the guides ([guides](guides.md#topic-page)) and is stored in `job.toml`. It fails on an unknown topic, on a topic that does not apply to the artifact's modality ([guides](guides.md#topic-page)), and warns when the system part and the topics together exceed the target times the tolerance of `[guides]`, listing the words of each topic ([guides](guides.md#budget)).
- The snapshot copies the artifact folder, including `table/` and the translation folders, and dereferences symlinks, so the snapshot holds content and not links. The build outputs (`<slug>.pdf`, `<slug>_diff.pdf`, `<slug>.png`, `<slug>_diff.png`, where the slug is the artifact name or `<artifact>-<code>`, `BUILD-ERROR.txt` and the generated `references.bib`) are generated files and stay out of it, out of the change list, and survive a revert.
- It removes the snapshot of the artifact's previous job. Only the last snapshot of an artifact is kept. Briefs and notes of earlier jobs stay.
- It prints the job id.

### `parla job end <artifact>`

Writes `ended` into `job.toml` and prints the source files changed since the snapshot (never the build outputs), one per line, with `added`, `changed` or `removed`, then the verdicts of the job, one per line, with the key, the verdict and the evidence or reason, and the summary line of the suite over the lines the job changed. The snapshot stays until the artifact's next job starts. Fails when the artifact has no active job.

### `parla job changes <artifact>`

Prints a unified diff of every source file changed since the snapshot of the artifact's newest job, active or ended: `--- snapshot/<path>` against `+++ <path>`, relative to `parla/`. A file that is not UTF-8 text prints one line, `<status> <path> (binary)`. Build outputs stay out, as in `job end`. The captain reads the job's corrections from it at learning time, together with its memory of the author's feedback ([skill](skill.md#the-job-loop)). Fails when the artifact has no job or its snapshot is missing.

### `parla job revert <artifact>`

Restores the artifact folder from the snapshot of the artifact's newest job, active or ended. Files in the snapshot are restored, and files created since are removed, except the build outputs, which stay. It prints the files it restored or removed. Fails when the artifact has no job.

### Diff baseline

`build <artifact>` diffs against the snapshot of the artifact's active job. With no active job and no `--diff-from`, it builds without a diff ([latex engine](latex-engine.md#build)).

### Captain and worker

The skill agent is the captain: it holds the author's request and the topic choice, and relays questions to the author. One worker per job runs the loop of writing, building and resolving the suite, and is resumed for every round ([skill](skill.md#the-job-loop)). A small edit may run in the captain. A job is finished when the suite is green: no failure and no open probe ([constraints](constraints.md#report)).

### Phase

The card's `phase` sets the reach of an edit. The worker keeps every edit within it, and the author sees the whole job in the diff.

| Phase | The text is | An edit may |
|---|---|---|
| drafting | a first version | replace whole sections, reorder, merge or split them |
| polishing | close to final | change only what the request covers and leave every other line byte-identical; anything larger is proposed |

The author moves the phase forward, or back when new results reopen the structure.

## Constraints

- An artifact MUST have at most one active job.
- `job start` MUST fail when the artifact has no card.
- A job id MUST be unique; a clash at the same second fails.
- A snapshot MUST NOT contain symlinks.
- `job revert` MUST leave the artifact folder identical to the snapshot, apart from the build outputs.
- `parla` MUST NOT read `brief.md` or `notes.md`.
- `check --resolve` MUST fail without an active job.
- `job start --topics` MUST fail on an unknown topic, and MUST warn without failing over the tolerance.
- Only the last snapshot of an artifact MUST remain on disk.

## History

- [Jobs and the snapshot diff](logs/2026-10-14_jobs.md): why a job owns the diff baseline, and why the subagent edits directly.
- [Lean prompts and a constraint suite](logs/2026-10-18_lean-prompts.md): topics in the job, verdicts, and one worker per job.
- [Translations of one artifact](logs/2026-10-16_translations.md): per-language outputs, snapshot and measure.
- [Ending jobs and a soft guide cap](logs/2026-10-28_ending-jobs-and-soft-cap.md): the signs of a job's end, `job changes`, and the warning cap.
