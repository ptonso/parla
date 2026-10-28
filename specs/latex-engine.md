# parla LaTeX Engine Spec

Related: **Read first** [engines](engines.md), [architecture](architecture.md), [docker](docker.md), [config](config.md). **See also** [cli](cli.md), [template](template.md), [checks](checks.md).

## Overview

The LaTeX engine is the implementation of the [engine contract](engines.md#the-engine) for `engine: latex`: it turns an artifact into a PDF and shows what changed since the baseline. It is the `texfy` core, ported whole: the same build, bibliography overlay, diff and export, with the paths adapted from `tex/workspace/` to `parla/artifacts/<artifact>/`.

It is deliberately thin. It holds almost no LaTeX logic: each method reads the filesystem and the card, composes a deterministic `docker run ... latexmk ...` ([docker](docker.md#run-contract)), and lets the container compile.

Walk-through of a build: the engine reads the card, scans the artifact's `\input` tree for `\cite` keys, writes `artifacts/<artifact>/references.bib` when it changed, refreshes the managed block of `project.sty`, runs latexmk in the container, and publishes the PDF. When a baseline exists, it then flattens the old and new sources, runs latexdiff and publishes `<artifact>_diff.pdf`.

## Language

- **Baseline**: see [engines](engines.md#language). The router passes it to `build`.
- **Flatten**: replace each `\input` or `\include` by the content of its target, recursively, so latexdiff sees one file.
- **Published PDF**: `parla/artifacts/<artifact>/<artifact>.pdf`, the copy of a successful build's PDF that the author reads.
- **Document**: one buildable entrypoint of an artifact: the artifact's own, or one translation.
- **Slug**: the name of a document's outputs: `<artifact>` for the artifact's own, `<artifact>-<code>` for a translation.
- **Overlay**: the bibliography resolution that merges the user library and the project's `sources/bib/*.bib` into the artifact's `references.bib`.

## Map

- `parla.engines.latex.engine` implements the contract by delegating to the modules below.
- `build` owns `docker run`; `image` owns image identity ([docker](docker.md#map)).
- `bib` owns the overlay: it parses BibTeX, loads the library, scans `\cite` keys, resolves them and materializes `references.bib`.
- `autoload` writes the managed block of `project.sty`.
- `diff` flattens, runs latexdiff and publishes the change PDF.
- `export` traces an artifact's dependency graph and assembles a snapshot.
- `links` syncs the `[links]` symlinks under `sources/`.

## Contracts

### Implementation of the contract

| Method | Behavior |
|---|---|
| `prepare` | builds the image on first use, unless `PARLA_NO_AUTO_BUILD=1` ([docker](docker.md#constraints)) |
| `starter` | entrypoint `main.tex` and the files of the stock template or the audience's `setup` ([template](template.md#stock-templates)); card key `latex: lualatex` |
| `check` | the shared checks and the LaTeX check set ([checks](checks.md#latex-engine)) |
| `build` | [Build](#build) and, with a baseline, [Diff](#diff) |
| `export` | [Export](#export) |
| `pages` | the PDF page count and the body-end page ([tools](tools.md#parla-tool-measure-artifact---words---pages)) |

`card_keys` is `("latex",)`.

### Build

`build` compiles the artifact's entrypoint in an ephemeral container. The router has already run the checks and resolved the baseline ([engines](engines.md#router-behavior)).

- The engine (`lualatex` or `pdflatex`) and the entrypoint come from the card ([config](config.md#the-card)).
- **Bibliography first.** Before compiling, it materializes the overlay ([below](#bibliography-overlay)).
- **Outputs.** latexmk writes every intermediate and log to `parla/.parla/build/<artifact>/`. On success, the PDF is copied to `parla/artifacts/<artifact>/<artifact>.pdf`, and the CLI prints that path.
- **Return value.** `build()` returns a `BuildResult(pdf, aux, published_pdf, diff_pdf)`: `pdf` and `aux` are the outdir files, `published_pdf` is the copy in `pdf/`, and `diff_pdf` is the change PDF or `None`. The engine wraps it as a `LatexBuilt`.
- **Diff.** After a successful compile, `build` publishes the change PDF when it received a baseline ([Diff](#diff)).

The console output follows [docker](docker.md#build-output): nothing on success except the published path. A failed compile exits with code 2 and prints the first TeX error as a finding ([checks](checks.md#finding)), with its source context and the path of the full log.

### Translations

A card with `translations` ([config](config.md#the-card)) holds one document per language. A translation `pt: pt` is the entrypoint `artifacts/<artifact>/pt/<entrypoint>`, and its files use paths relative to `parla/` as the artifact's own do.

- `build` compiles the artifact's own document, then each translation in card order, and publishes `<slug>.pdf` and, with a baseline, `<slug>_diff.pdf` for each. Intermediates go to `parla/.parla/build/<slug>/`.
- One `references.bib` serves all languages: the overlay scans the `\cite` keys of every document.
- The checks run on every document, and `translation-parity` ([checks](checks.md#ids)) compares the trees.
- `export` produces one snapshot per document, the translations as `<yyyy-mm-dd>_<tag>-<code>`, and returns the artifact's own.
- `pages` and `tool measure` take a language code ([tools](tools.md#parla-tool-measure-artifact---words---pages)).

### Bibliography overlay

The user config names the library (`library_bib`, `library_json`, Better BibTeX exports). Before each build:
- The artifact's `\input` tree is scanned for `\cite` keys. Commented-out text is ignored.
- Each key is resolved against the library and `parla/sources/bib/*.bib`. The library wins a collision, and a shadowed key warns.
- An unresolved key is a `BuildError`.
- The result is the artifact's `references.bib`, each entry copied byte for byte from its source. It is rewritten only when its content changes, so `build --watch` cannot loop.

The library's `library.json` and the entries' `file` field give the path of each cited PDF.

### Package autoload

Before each build, `[packages].autoload` and `[packages].require` ([config](config.md#parlaparlatoml)) are written into the managed block of `parla/texmf/tex/latex/project/project.sty`. Content outside the block is untouched.

### Diff

`build` runs the diff against the baseline it received, in three steps.

- **Step 1, flatten.** On the host, build a flat copy of each side:
  - Replace every `\input{...}` and `\include{...}` whose target is inside `artifacts/<artifact>/`, except under `table/`, by the target file's content, recursively.
  - Targets under `table/`, targets elsewhere and `\DiagramSlide{...}` are left as they are. The compile resolves them from the current tree.
  - The baseline side resolves its targets against the baseline directory, then against `parla/`; the new side resolves against `parla/`.
  - A target is tried as written, then with `.tex` appended. A missing target is left as it is.
  - Commented-out commands (after an unescaped `%`) are ignored.
  - The two flat files are written to `parla/.parla/build/<artifact>_diff/{old,new}.flat.tex`.
- **Step 2, latexdiff.** In the container, run `latexdiff --type=UNDERLINE --config "PICTUREENV=(?:picture|tikzpicture|DIFnomarkup)[\w\d*@]*" old.flat.tex new.flat.tex`. Its stdout is written to `parla/.parla/build/<artifact>_diff/<stem>_diff.tex`.
- **Step 3, compile.** Compile that file with the artifact's engine, with `parla/` as working directory and outdir `parla/.parla/build/<artifact>_diff/`, so `sources/`, `references.bib` and unflattened inputs resolve.
- **Result.** The PDF is copied to `parla/artifacts/<artifact>/<artifact>_diff.pdf`. Any failure of latexdiff or of the compile is a `BuildError` with the log path.

The baseline holds `artifacts/<artifact>/<entrypoint>` and may be a job snapshot or an earlier export.

### Export

`export(artifact, tag, force)` compile-checks the artifact, traces exactly the files the compilation depends on, and assembles a standalone snapshot at `parla/export/<artifact>/<yyyy-mm-dd>_<tag>/`. The snapshot is a hand-off (Overleaf or a submission portal), and the command never commits it.

- `<yyyy-mm-dd>` is the UTC export date. `<tag>` is normalized to lowercase kebab-case (`Arxiv V2` becomes `arxiv-v2`).
- **What is traced,** starting from the entrypoint:
  - `\input`, `\include` and `\DiagramSlide`;
  - `\includegraphics` and the `\LeftImage`/`\RightImage`/`\TopImage`/`\BottomImage` family;
  - `\bibliography` and `\addbibresource`;
  - `\usepackage`, `\documentclass` and Beamer's `\use[color|font|inner|outer]theme` (resolved to `beamer<kind>theme<Name>.sty`), as metadata and for the shared-file lookup.

  The list of path-taking commands is shared with the checks. Paths stay relative to `parla/`, so no source rewriting is needed.
- **Fallback for bare names.** A bare `\input`/`\include`/`\usepackage`/`\usetheme` target not found under `parla/` falls back to the packaged Layer 2 tree, then to `[storage].texmf_home`, mirroring kpathsea order. Matches are copied as-is to the export root and listed under `bundled_shared_files` in `tex-config.yaml`.
- **No links in the snapshot.** Every copy dereferences symlinks, so the snapshot holds real files, never links into external storage.
- **Whole folders.** `parla/<paths.texmf>/` is copied wholesale, along with the published PDF.
- **`latexmkrc`.** When `parla/<paths.texmf>/` is copied, a `latexmkrc` is written at the export root that recursively extends `TEXINPUTS` over it. A receiving latexmk-driven compiler such as Overleaf has no built-in way to discover a project-local texmf TDS tree, so without this file anything living under `texmf/` (for example `project.sty`) fails to resolve there even though the export holds it.
- **`tex-config.yaml`** records `parla_project_version`, `docker_image`, `engine`, `entrypoint`, `exported_at`, `source_commit` (best effort) and `packages`.

## Constraints

- The engine MUST fail fast when the artifact's card does not say `engine: latex`.
- A build MUST write nothing into the artifact folder except `references.bib`, the published `<slug>.pdf` and `<slug>_diff.pdf` of each document, and `BUILD-ERROR.txt`, nothing outside it and `parla/.parla/` except the managed block of `project.sty`.
- `references.bib` MUST be rewritten only when its content changes.
- A shadowed library key MUST warn, and an unresolved key MUST fail the build.
- The diff MUST NOT flatten targets under `table/`.
- The diff MUST fail when the baseline lacks `artifacts/<artifact>/<entrypoint>`.
- `export` MUST fail if normalizing the tag leaves no alphanumeric character.
- `export` MUST fail if the target snapshot directory exists, unless `force`, which replaces it entirely.
- `export` MUST fail if any traced dependency (input, figure, bib file) is missing.

## History

- [Translations of one artifact](logs/2026-10-16_translations.md): documents, slugs and the per-language build.
- [Outputs in the artifact folder](logs/2026-10-16_outputs-in-artifacts.md): builds publish into the artifact; intermediates in `.parla/`; exports in `export/`.
- [Sources, LaTeX and output folders](logs/2026-09-26_sources-latex-layout.md): inherited; diff, export paths, `out/`.
- [Portable texfy](logs/2026-09-09_portable-texfy.md): inherited; generated references file, the overlay.
- [Two-phase build](logs/2026-10-14_two-phase-build.md): the check phase before the compile.
- [Engine contract](logs/2026-10-14_engine-contract.md): `watch` and the baseline move to the router; the engine implements the contract.
- [Agent-first rewrite](logs/2026-10-14_agent-first-rewrite.md): the baseline is the job snapshot; one `references.bib` per artifact; `diff` is part of `build`.
