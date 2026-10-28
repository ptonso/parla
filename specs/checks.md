# parla Checks Spec

Related: **Read first** [architecture](architecture.md). **See also** [constraints](constraints.md), [cli](cli.md), [config](config.md), [engines](engines.md), [latex engine](latex-engine.md), [svg engine](svg-engine.md), [none engine](none-engine.md).

## Overview

A check is a fast, static test of an artifact's source. It runs before the engine compiles, so the author, human or agent, hears about a missing figure or an unresolved citation in a line, and not in a long engine log.

Each engine owns a check set ([engines](engines.md#the-engine)). `parla check <artifact>` calls `check` on the engine the card names, and `build` calls the same method as its first phase. A check reports and never rewrites the source.

The checks an engine computes from its own source or log, and the [constraints](constraints.md) of the author, form one suite. `build` reports the suite after it compiles, so the agent sees one list of what to fix, as it would after a failing test run.

Walk-through: the agent edits a section and runs `build`. The check phase scans the artifact's `\input` tree, finds an `\includegraphics` whose file does not exist, and prints one finding with the file and line. The build stops with exit code 1. The agent fixes the path and runs `build` again; the checks pass and the compile runs.

## Language

- **Finding**: one reported problem, with a location, a severity, a check id and a message.
- **Severity**: `error` stops the build when an engine check raises it; `warning` prints and the build continues. A constraint finding never stops the build. `probe` marks a question still open.
- **Suite**: the engine's findings and the constraint findings in one report; green when it holds no error and no open probe.
- **Check id**: the stable kebab-case name of a check, such as `cite-unresolved`.
- **Check set**: the checks one engine runs.

## Map

`parla.checks` holds the finding type, the runner and the checks every engine shares. Each engine package holds its own checks and returns them from its `check` method. The router reads `[checks].ignore` ([config](config.md#parlaparlatoml)) and drops the findings of ignored ids.

## Contracts

### Finding

One finding is one line:

```
<file>:<line>: <severity> <id>: <message>
```

`<file>` is relative to `parla/`. The message names what is wrong and, when one fix is clear, the fix. A finding about a whole file, with no line, uses line `1`. The compile phase prints a failed compile's first error in the same format, with id `compile-error`, followed by its source context and the path of the full log.

### Runner

`Engine.check(root, artifact)` runs the shared checks and then the engine's own, and returns the findings in file and line order. The router appends the constraint findings ([constraints](constraints.md#report)), drops the findings of ids in `[checks].ignore` and the findings with a verdict in the active job. It reads only the artifact's folder, `sources/` and the user library. It needs no Docker and no network.

`build` runs the engine checks first; an error stops it. After a successful compile it reads the engine's build log for the post-build findings below, appends them to the suite and prints the report. A suite that is not green leaves the published output in place and exits with code 4 ([cli](cli.md#exit-codes)).

`check` and `build` print the findings, then one summary line: `suite: <n> fail, <m> probes open, <k> resolved`. The `--all` flag widens the scope of the constraints from the lines changed in the job to the whole artifact.

### Ids

Shared by every engine:

| Id | Severity | Reports |
|---|---|---|
| `card-invalid` | error | a missing or invalid card key ([config](config.md#the-card)) |
| `source-missing` | error | a path under `sources/` that an artifact text file names and that does not exist; build outputs such as `BUILD-ERROR.txt` are not scanned |

### LaTeX engine

The check set scans the entrypoint and every file its `\input` and `\include` reach inside the artifact folder. Commented-out text is ignored.

| Id | Severity | Reports |
|---|---|---|
| `cite-unresolved` | error | a `\cite` key found in neither the library nor `sources/bib/*.bib`, resolved as the [overlay](latex-engine.md#bibliography-overlay) resolves it |
| `figure-missing` | error | a figure, table or diagram path that does not exist |
| `bib-name-syntax` | error | a BibTeX `author` or `editor` name using BibLaTeX-only syntax |
| `unescaped-char` | error | an unescaped `_` or `%` outside a protected command |
| `brace-unbalanced` | error | unbalanced braces |
| `translation-parity` | error | a translation does not reach a file that the artifact's own entrypoint reaches, or reaches an extra one, or a file holds different `\section`, `\cventry`, `\cvline`, `\item` or `\input` commands in a different order |
| `macro-missing` | error | a slide macro such as `\SplashSlide` used when the preamble does not load it |
| `ref-dangling` | warning | a `\ref` or `\eqref` whose label is not defined |
| `float-unreferenced` | warning | a float that no text references |
| `float-order` | warning | a float whose first reference comes after the float |
| `figure-duplicate` | warning | the same figure included twice |
| `abbreviation-repeated` | warning | an abbreviation defined more than once |
| `cite-style` | warning | a stray backslash or thin space before a `\ref` or `\cite`, or a mangled `Figure \ref`; the tie in `Figure~\ref` is correct |
| `todo-marker` | warning | a leftover `%TODO` marker |
| `appendix-structure` | warning | an appendix section that does not start at `\section`, or a stray `\appendix` |

Post-build findings, read from the engine's log after the compile:

| Id | Severity | Reports |
|---|---|---|
| `frame-overflow` | error | a beamer frame whose content overflows the page, with the frame title and the source line |
| `overfull-line` | warning | a line that overfills its box by more than 5pt |

The list of path-taking commands that `figure-missing` and `unescaped-char` read is the one `export` traces ([latex engine](latex-engine.md#export)).

### SVG engine

| Id | Severity | Reports |
|---|---|---|
| `svg-overflow` | error | text that overflows its box |
| `svg-collision` | error | a label touching content or another label |
| `svg-arrow-crossing` | error | an arrow crossing content outside its endpoints |
| `svg-glyph-missing` | error | a glyph the font does not have |
| `svg-href-missing` | error | an `href` that does not resolve |
| `svg-malformed` | error | an SVG that is not well-formed XML |
| `svg-math-in-text` | error | a literal `$` in a `<text>`; math is a rendered formula |
| `svg-unsupported` | warning | an element or transform the checks do not understand, so it is not checked |

### Constraints

Findings of the author's and the package's [constraints](constraints.md) have the id `constraint/<id>`. A regex constraint takes its severity from its entry. A probe has the severity `probe` until the agent records a verdict. `[checks].ignore` accepts `constraint/<id>` for a constraint that exists in either store.

### Guides, casebook and constraints

`guide lint`, `case lint` and `constraint lint` ([guides](guides.md#parla-guide-lint), [casebook](casebook.md#parla-case-lint), [constraints](constraints.md#parla-constraint-lint)) print findings with these ids. A file is `public:<page>.md` or `private:<page>.md` for a guide page, an artifact's `card.md` path, or `cases.jsonl`.

| Id | Severity | Reports |
|---|---|---|
| `rule-malformed` | error | a rule heading without exactly one blockquote line |
| `rule-origin-missing` | error | a rule with no `(origin: ...)` |
| `rule-duplicate` | error | a rule id defined twice in a file, or on two different pages |
| `rule-overrides-missing` | error | an `overrides` that names no rule |
| `public-rule` | error | a rule inside a public guide page |
| `brief-missing` | error | a public modality page without a brief, or a part row without a job |
| `link-broken` | error | a Markdown link whose target does not exist, or a page a load needs that is missing |
| `guide-over-budget` | warning | the system part, or a part with all its topics, over `[guides].target_words` times `[guides].tolerance` |
| `guide-page-over-cap` | warning | a topic page over `[guides].max_page_words` |
| `hook-missing` | error | a topic with no `hook` in either root |
| `topic-applicable-unknown` | error | a topic limited to a modality that has no page |
| `rule-contradicted` | warning | a ported rule that an active case contradicts |
| `case-distill` | warning | active cases on one topic and audience at or over `[guides].distill_min` |
| `case-stale` | warning | an active case not opened for `[guides].stale_days` |
| `constraint-example-failed` | error | a regex constraint whose `match` or `ok` example no longer holds |
| `constraint-refine` | warning | a constraint with `[guides].distill_min` or more `na` verdicts across jobs |

### Text engine

The `none` engine ([none engine](none-engine.md)) runs only the shared checks.

## Constraints

- A check MUST NOT modify any file.
- A check MUST NOT start Docker or touch the network.
- A finding MUST carry a file, a line, a severity, an id and a message.
- Check ids MUST be unique and stable. Renaming one is a breaking change, because projects list ids in `[checks].ignore`.
- The router MUST drop findings whose id is in `[checks].ignore`, and MUST fail on an ignored id no check defines.
- Findings MUST be printed in file and line order, errors, warnings and probes together.
- A constraint finding MUST NOT stop the build.
- A post-build finding MUST come from the engine's own log and MUST NOT start a second compile.
- The summary line MUST be the last line of `check` and `build` output.

## History

- [Translations of one artifact](logs/2026-10-16_translations.md): the `translation-parity` check.
- [Two-phase build](logs/2026-10-14_two-phase-build.md): why checks run before the compile, and the ignore list.
- [Lean prompts and a constraint suite](logs/2026-10-18_lean-prompts.md): the suite, probes and post-build findings.
- [Agent-first rewrite](logs/2026-10-14_agent-first-rewrite.md): the post-processing that enforced these silently becomes checks the agent runs.
