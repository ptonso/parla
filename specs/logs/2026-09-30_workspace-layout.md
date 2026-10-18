# `workspace/` replaces `latex/`

**Affects**: [template](../template.md#base-tree), [cli](../cli.md), [config](../config.md).

## Decision

The base tree names the LaTeX folder `workspace/`: it holds what the entrypoints include and what they read from it (tables, diagrams, `references.bib`), whether written by hand or drafted by a plugin. Kind folders lose their plural: `sources/{fig,table,bib}`, `workspace/{section,slide}`, `out/{build,pdf,export}`. `[links]` keys follow (`fig/results`). `texfy diff` flattens prose under `workspace/{section,slide,abstract}/`, and `texfy build` writes `workspace/references.bib`. The reasoning is in the texfy-ai log of the same day.
