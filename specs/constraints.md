# parla Constraints Spec

Related: **Read first** [architecture](architecture.md), [checks](checks.md). **See also** [guides](guides.md), [casebook](casebook.md), [jobs](jobs.md), [skill](skill.md), [cli](cli.md).

## Overview

A constraint is a rule of an artifact that can be tested, kept outside the prompt and run as part of `parla check` and `parla build`. The guides carry craft, which is a matter of degree. The constraints carry what a reviewer can answer yes or no, and the tool reports where the answer is no. The agent receives a located failure, as it would from a failing test, and it fixes the spot.

There are two kinds. A **regex constraint** holds a pattern, and the tool alone decides every hit. A **probe** holds a question and a locator: the tool finds every span the question applies to, such as each sentence with a citation, and the agent answers for each span by reading the source and recording a verdict with evidence. Structural checks that an engine computes from its own output, such as a slide that overflows, stay Python checks ([checks](checks.md)) and appear in the same report.

The constraints of the author live in a private store and learn from corrections. The package ships a small set of taste-neutral constraints, so a new project has a working suite on the first build.

Walk-through: the author corrects an em dash twice in a job. At the end the agent proposes a regex constraint `no-emdash` with a sentence that must match and one that must not, and the author accepts. In the next job the agent writes a paragraph with one em dash and runs `parla build`. The report lists `intro.tex:42 constraint/no-emdash`. The agent replaces the dash, rebuilds, and the line is gone. The same report also lists `cite-grounded` as a probe for the sentence with `\cite{goldstein2015}`. The agent reads the cited section with `parla tool source`, runs `parla check --resolve` with the sentence's key and a quoted line as evidence, and the suite turns green.

## Language

- **Constraint**: one entry of a store, a regex constraint or a probe.
- **Regex constraint**: a constraint with a pattern and example strings; every hit is a failure.
- **Probe**: a constraint with a question and a locator; each located span is open until the agent records a verdict.
- **Locator**: the named way a probe finds its spans: `citation`, `number`, `caption`, `paragraph` or `frame`.
- **Suite**: the constraint findings plus the engine's own checks in one report.
- **Green**: no failure and no open probe.
- **Verdict**: the agent's recorded answer to one finding: `pass` with evidence, or `na` with a reason.
- **Resolution key**: `<constraint id>#<hash>`, where the hash is taken over the text of the span (the line of a regex hit); it names one finding in a verdict.
- **Hint**: a flag that prints the description of a constraint in the guide view, for constraints the agent violates often.

## Map

`parla.constraints` owns the stores, the runner, the locators and the verdicts. `parla.router` appends its findings to the engine's findings ([checks](checks.md#runner)). The public store ships in `parla/guides/constraints.jsonl` and the private store lives next to the casebook.

## Contracts

### Stores

| Store | Location | Holds |
|---|---|---|
| public | `parla/guides/constraints.jsonl` in the package | taste-neutral constraints for any author of the modality |
| private | `<[guides].private>/constraints.jsonl` | the author's constraints |

Both are append-only JSON lines. A later line with the same `id` updates the fields it carries, so the current state of a constraint is its lines folded in order. Ids are unique across both stores. No command writes the public store. A project mutes a public constraint with `constraint/<id>` in `[checks].ignore` ([config](config.md#parlaparlatoml)).

### Entry

```json
{"id": "no-emdash", "kind": "regex", "description": "no em dash in the text",
 "applies": {"modality": ["paper"], "engine": ["latex"]},
 "regex": "\u2014", "flags": "", "severity": "error", "hint": true,
 "examples": {"match": ["the model \u2014 which"], "ok": ["the model, which"]},
 "evidence": ["c-0003"], "origin": "promoted from rule gen-no-emdash",
 "status": "active", "date": "2026-10-18"}
```

```json
{"id": "cite-grounded", "kind": "probe", "locator": "citation",
 "description": "the cited source supports the claim at the strength written",
 "applies": {"engine": ["latex"]}, "severity": "error", "hint": false,
 "evidence": [], "origin": "promoted from rule cite-keep",
 "status": "active", "date": "2026-10-18"}
```

- `kind` is `regex` or `probe`. A regex constraint has `regex`, `flags` (a subset of `i`, `m`, `s`) and `examples` with a `match` and an `ok` list, both non-empty. A probe has `locator`.
- `applies` holds optional lists `modality`, `engine`, `audience` and `files`. A missing list matches everything. `files` holds globs on the path within the artifact folder (`abstract/*.tex`), so a constraint can govern one part of the artifact.
- `severity` is `error` or `warning`. A warning never keeps the suite from green.
- `status` is `active` or `retired`.
- `evidence` lists case ids. `origin` is free text, such as the id of the rule a constraint was promoted from.

### Locators

| Locator | Spans | Extra context in the finding |
|---|---|---|
| `citation` | each sentence holding a `\cite` | the cite keys and `parla tool source <key>` |
| `number` | each sentence holding a digit | none |
| `caption` | the argument of each `\caption` | the float label |
| `paragraph` | each paragraph | none |
| `frame` | each beamer `frame` environment | the frame title |

A locator reads the same source files as the regex runner and uses the sentence and paragraph bounds of `parla tool claims` ([tools](tools.md#parla-tool-claims-artifact)). Engines without the structure a locator needs (`svg`, `none`) support only `paragraph`; a probe with another locator does not apply to them.

### Scope

A job narrows the suite to the lines changed against the active job's snapshot ([jobs](jobs.md#diff-baseline)). Without an active job, or with `--all`, the suite covers the whole artifact. A span belongs to the changed lines when any of its lines changed. Comments are masked with the engine's comment rule, so a pattern never matches commented text.

### Report

Each failure is a [finding](checks.md#finding) with id `constraint/<id>` and the line of the span. A probe finding has severity `probe` and a message that holds the question, the span text and the resolution key:

```
intro.tex:57: probe constraint/cite-grounded: the cited source supports the claim at the strength written
    span: "Sweeping one attribute of a single instance over its range is established..." [goldstein2015]
    verify: parla tool source goldstein2015
    key: cite-grounded#a41c9e
```

When a constraint finding is open, a line before the summary says how to answer one: `parla check <artifact> --resolve <key> --pass --evidence "<line>"` for a probe, or `--na --why "<reason>"` for a false positive. The report ends with one summary line: `suite: <n> fail, <m> probes open, <k> resolved`. Probes beyond `[guides].max_probes` are counted in the summary and listed on the next run, after the shown ones are resolved. A finding with a verdict in the active job prints with the severity `resolved`, and its message holds the verdict and the key.

### Verdicts

`parla check <artifact> --resolve <key> --pass --evidence "<quote>"` records that the span satisfies the question; the evidence is a quoted line of the source, required. `--resolve <key> --na --why "<reason>"` records that the finding does not apply, such as a false positive; the reason is required. Both append to `.parla/jobs/<id>/verdicts.jsonl`:

```json
{"key": "cite-grounded#a41c9e", "verdict": "pass", "evidence": "ICE plots show ... (sec. 2)", "file": "intro.tex", "line": 57, "date": "2026-10-18"}
```

- A regex hit accepts only `--na`.
- A verdict holds while the span text is unchanged. Editing the span changes the hash and reopens the finding.
- `--resolve` fails without an active job.
- `job end` prints the verdicts of the job ([jobs](jobs.md#parla-job-end-artifact)).

### `parla constraint add`

Reads one JSON object from standard input with the fields above and appends it to the private store. It assigns `date` and `status: active`. It fails fast on a missing field, a duplicate id, a regex that does not compile, a `match` example the regex misses, an `ok` example it hits, or an unknown locator.

### `parla constraint list [--kind <k>] [--status <s>]`

One line per constraint of both stores: id, kind, severity, status, origin store and description.

### `parla constraint edit <id>`

Reads one JSON object from standard input with the fields to change, such as `regex`, `examples`, `applies`, `severity` or `description`, and appends it to the private store. The merged entry is validated as `constraint add` validates it. `id`, `kind`, `status` and `date` cannot be edited, and a public constraint cannot be edited.

### `parla constraint mark <id> <status>`

Appends a status change to the private store. A public constraint cannot be marked; `[checks].ignore` mutes it.

### `parla constraint lint`

Prints findings in the [finding format](checks.md#finding):
- `constraint-example-failed`: a regex constraint whose examples no longer hold.
- `constraint-refine`: a constraint with `[guides].distill_min` or more `na` verdicts across all jobs. The agent proposes tightening the pattern or adding an example to the `ok` list.

### Starter set

The public store holds a few constraints that any author of the modality accepts: `fig-ref-form` and `tab-ref-form` (a reference written as `Figure~\ref{fig:<id>}`, with no file name), `cite-before-punct` (a citation placed before the punctuation of its clause), and the probes `cite-grounded`, `number-sourced` and `caption-describes`. It holds no taste: no banned words, no sentence lengths, no house terms.

### Learning

At the end of a job the agent proposes a destination for each correction ([skill](skill.md#supporting-pages)): a regex constraint when a pattern answers it, a probe when a reader answers yes or no, a style principle when it is a matter of degree, and a case when it is an illustration. A constraint cites the cases that motivated it in `evidence`, and the cases are marked `distilled`.

## Constraints

- A regex constraint MUST be added with examples, and `constraint add` MUST reject a pattern that fails them.
- A verdict MUST carry evidence (`pass`) or a reason (`na`).
- The runner MUST know no constraint by name.
- A constraint MUST NOT modify any file.
- Constraint ids MUST be unique across both stores, and no command MUST write the public store.
- The suite MUST report the same findings for the same source, job and stores.
- A resolved finding MUST reopen when its span text changes.
- A prompt MUST NOT carry a constraint that the suite checks, apart from the description of a `hint` constraint.

## History

- [Lean prompts and a constraint suite](logs/2026-10-18_lean-prompts.md): why checkable rules leave the prompt, why probes exist, and why one agent runs the suite.
