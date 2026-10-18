# Outputs in the artifact folder

**Affects**: [template](../template.md), [config](../config.md), [cli](../cli.md), [engines](../engines.md), [latex engine](../latex-engine.md), [svg engine](../svg-engine.md), [none engine](../none-engine.md), [jobs](../jobs.md), [docker](../docker.md).

## Situation

A build wrote its results under `parla/out/`: the PDF and the diff PDF in `out/pdf/`, intermediates in `out/build/`, exports in `out/export/`. Since `parla/` is usually a hidden folder kept in an external asset store, `out/pdf/` was one more place the author had to open to read the result of the artifact they had just edited. A failed build left its reason in a console that is gone by the next command.

## Alternatives considered

- **Keep `out/` and add a link in the artifact.** The link breaks when the asset store moves, and it is one more thing to generate.
- **Put the intermediates in the artifact too** (`artifacts/<name>/.build/`). Everything of one artifact would sit in one folder, but jobs, watch and export would all have to skip a second kind of generated content. Hidden state already has a home in `.parla/`.
- **Keep the plain-text copy.** The `none` engine copied `post.md` to `<artifact>.md` next to the original. With outputs in the artifact folder the copy duplicates the source, and a build of a post will later mean publishing it, so `build` is unsupported for now.

## Decision

A successful build copies `<artifact>.pdf` and, with a baseline, `<artifact>_diff.pdf` into the artifact folder (diagrams also write the `.png` files). Intermediates go to `.parla/build/<artifact>/`. Exports go to `parla/export/`. `[paths].out` is removed and `[paths]` accepts only `texmf`. A failed check or build writes `BUILD-ERROR.txt` into the artifact folder, starting with a line that says it is generated, holding only the error text; the next successful build deletes it. `names.is_output` is the single definition of these generated files.

## What tipped it

The author reads the artifact folder. The PDF, the diff and the reason a build failed belong next to the source they describe.

## Trade-offs accepted

- Generated files share the folder with sources, so every tool that walks the folder must skip them: the job snapshot, the change list of `job end`, `job revert` (which keeps them) and the `build --watch` loop, which would otherwise rebuild on its own output.
- A compile failure now carries its excerpt in the `BuildError` message instead of printing it during the compile, so the console and `BUILD-ERROR.txt` show the same text.
- Projects built before this change need a one-time move of their `out/` content; the migration script does it.
