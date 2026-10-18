# Sources, LaTeX and output each get one folder

**Affects**: [template](../template.md), [config](../config.md), [cli](../cli.md), [docker](../docker.md), [architecture](../architecture.md).

## Situation

The base tree mixed four kinds of material at the `tex/` root:
- hand-edited or generated LaTeX (`sections/`, `slides/`, `bib/references.bib`);
- inputs (`figs/`, `bib/extras/`);
- build intermediates and PDFs, together in `build/<doc>/`;
- exports (`exports/`).

Figures from a code project arrived through `link-figs`, which forced a `figs/results/` level and was re-run from hand-written scripts in each project. The `texfy-ai` plugin layers its own sub-tree on this base. Its layout change (ideas, sources, latex and system state as separate folders) needs the base to agree on where sources and LaTeX live.

## Alternatives considered

- **Keep `figs/` and `sections/` at the root and let the plugin differ.** The two layers would disagree on where figures live, and plain `texfy` users would keep the clutter.
- **`\graphicspath` to keep short figure paths.** It adds a hidden resolution rule that `export` would also have to follow; explicit `sources/figs/...` paths trace directly.
- **Keep `link-figs` and add `link-tables`.** It is still imperative, still per project, and still repeated in a script. A declared table is reproducible and shows at a glance where every source comes from.
- **Build intermediates under a hidden `.texfy/`.** The user wanted every output, good and trash, in one visible output folder with a clear split between them.

## Decision

The base tree is described in [template](../template.md#base-tree):
- `latex/` holds the LaTeX that `main_*.tex` includes, plus the generated `references.bib`.
- `sources/` holds inputs: `figs/`, `tables/`, and hand-authored `bib/*.bib`.
- `out/` holds `build/<doc>/` (latexmk intermediates and logs), `pdfs/` (published PDFs, including `<doc>.diff.pdf`) and `exports/`.
- `texmf/` holds project styles.

`[links]` in `texfy.toml` declares symlinks under `sources/`, and `texfy link` syncs them ([cli](../cli.md#parla-link)). The build mounts the target of every symlink under `sources/` read-only.

`texfy diff` renders a latexdiff PDF against an earlier copy of `latex/`, and the image gains `latexdiff`.

`texfy.toml` moves to version 2 and rejects version 1 trees. Existing projects are migrated once.

## What tipped it

- The plugin's revise workflow makes `latex/` a folder the human edits.
- The live projects all link their figures from a code repository.

Both point to one declared `sources/` folder and one `latex/` folder shared by both layers.

## Trade-offs accepted

- Figure paths in LaTeX are longer (`sources/figs/...`).
- `link-figs` is removed with no alias.
- A tree at `texfy.toml` version 1 no longer builds until it is migrated.
