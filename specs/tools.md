# parla Tools Spec

Related: **Read first** [architecture](architecture.md), [checks](checks.md). **See also** [cli](cli.md), [latex engine](latex-engine.md), [config](config.md).

## Overview

Tools are deterministic helpers the agent calls for work that is mechanical and easy to get wrong by hand: counting words and pages, fitting and rendering a table, reading a cited paper's text, finding the sentences that carry citations, and rendering a formula as an image. Each takes explicit inputs, prints a result and exits. None calls a model.

They descend from texfy-ai's summarize, compress, length and ground code, without the model calls. The judgment those modules asked a model for (which rows of a table to drop, whether a paper supports a claim) is now the agent's, and the tool supplies the facts.

Walk-through: the agent is asked to fit the paper in 8 pages. It runs `parla tool measure icra-paper` and sees 9 body pages and the words per section. It cuts text, rebuilds and measures again. For a results table it runs `parla tool table icra-paper sources/results/metrics.csv --id metrics`; the tool prints the fit plan and writes `artifacts/icra-paper/table/metrics.tex`.

## Commands

Tools are deterministic helpers under one command, `parla tool <name>`.

| Command | Does |
|---|---|
| `parla tool measure <artifact>` | words per file and body pages, per language |
| `parla tool table <artifact> <source>` | parse, fit and render a table |
| `parla tool formula <artifact> <tex>` | render a formula as a PNG |
| `parla tool source <citekey>` | text of a cited PDF, by section |
| `parla tool claims <artifact>` | each citation with its sentence and paragraph |

## Language

- **Body pages**: pages up to and including the one holding the body-end anchor, so the reference list and appendix are excluded.
- **Body-end anchor**: `\label{parla:body-end}`, an invisible label the paper starter places after the last body line ([template](template.md#stock-templates)).
- **Grid**: the canonical rows and columns every table source is read into.
- **Fit plan**: the cheapest way to make a grid fit: type size, citation legend, resize.
- **Citation instance**: one `\cite` occurrence with its sentence and paragraph.

## Map

- `parla.tools.measure` holds the word count and the page measurement.
- `parla.tools.table` holds the parser, the fit planner and the renderer.
- `parla.tools.source` holds the PDF text extraction and its cache.
- `parla.tools.claims` holds the citation-instance extraction.
- `parla.tools.formula` renders a formula to a PNG.

## Contracts

### `parla tool measure <artifact> [--words] [--pages] [--language <code>]`

With neither flag, both. Words and pages are independent. An artifact with translations ([config](config.md#the-card)) is measured once per language, the artifact's own first, each total labelled `[<code>]`; `--language` measures one translation.
- **Words.** Prints the words of the entrypoint and of each file its `\input` tree reaches inside the artifact folder, and the total. A word counts prose only: LaTeX comments, commands, braces and `$` are dropped, and a Markdown link keeps its label.
- **Pages.** Reads the published PDF. Prints the total pages and the body pages. The body page is read from the `\newlabel{parla:body-end}` entry of the document's `.aux` in `.parla/build/<slug>/`. Fails when the PDF is missing, naming `build`. For an engine with no pages, `--pages` fails naming the engine. Fails when the anchor is missing, naming the starter.

Pages come from the artifact's engine ([engines](engines.md#the-engine)); an engine whose `pages` returns nothing supports `--words` only.

### `parla tool table <artifact> <source> [--id <id>] [--max-width <n>] [--max-rows <n>] [--font-step <step>]`

Reads `<source>` (`.csv`, `.tsv`, `.md`, `.json` or `.tex`) into a grid, plans the fit and writes `artifacts/<artifact>/table/<id>.tex`. `<id>` defaults to the kebab-case stem of the source file.
- The plan escalates from the base type size to smaller sizes, then a citation legend, then `\resizebox`, never below the floor type size.
- A cell with `<bib:key>` or a Markdown link into `bib/<key>.md` renders as a citation.
- The output is booktabs LaTeX with `\providecommand` fallbacks, so it compiles with or without `booktabs`.
- It prints the plan: type size, strategy, width and rows.
- When the grid does not fit even at the floor, it writes nothing and fails with the measured width and rows. Condensing the source is the agent's job ([guides](guides.md) procedure `condense-table`).

### `parla tool source <citekey> [--section <label>] [--pages <a-b>]`

Prints the text of the PDF the library lists for `<citekey>` (`library_json` and the entry's `file` field), by section, each tagged with its pages, with the references section dropped. `--section` and `--pages` narrow it. Fails when the key has no entry, or the entry has no readable PDF.
- The normalized text is cached under `$XDG_CACHE_HOME/parla/source/<citekey>.json` (default `~/.cache/parla/source`), valid while the PDF's fingerprint is unchanged.
- It requires the `pdf` extra and fails naming it when missing.

### `parla tool claims <artifact>`

Prints each citation instance in the artifact's `\input` tree as a block:

```
<file>:<line> [<key>, <key>]
sentence: <the sentence>
focus:    <the part of the sentence the key supports>
paragraph: <the paragraph>
```

Blocks are separated by a blank line, in file and line order. It reports facts; whether a source supports a claim is the agent's judgment, using `tool source`.

### `parla tool formula <artifact> <tex> [--display]`

Typesets `<tex>` as an inline or display formula in the container, rasterizes it at 300 dpi and writes `artifacts/<artifact>/formula/<hash>.png`, where `<hash>` is a content hash. It prints the path and the pixel size. An identical formula is not re-rendered. A formula that fails to typeset is a failure with the engine's message.

## Constraints

- A tool MUST NOT call a model or the network.
- `measure` MUST count the same words for the same text on every run.
- `table` MUST write nothing when the grid does not fit at the floor type size.
- `table` MUST write only under `artifacts/<artifact>/table/`.
- `tool source` MUST drop the references section.
- `tool source` MUST recompute its cache when the PDF's fingerprint changes.
- `formula` MUST write only under `artifacts/<artifact>/formula/`.

## History

- [Agent-first rewrite](logs/2026-10-14_agent-first-rewrite.md): the model-free remainder of summarize, compress, length and ground.
- [Translations of one artifact](logs/2026-10-16_translations.md): per-language outputs, snapshot and measure.
