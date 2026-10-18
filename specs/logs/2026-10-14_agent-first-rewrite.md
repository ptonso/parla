# The agent edits the source; parla is a new tool

**Affects**: [architecture](../architecture.md), [template](../template.md), [config](../config.md), [latex engine](../latex-engine.md), [cli](../cli.md), [docker](../docker.md).

## Situation

`texfy-ai` orchestrated writing: it split ideas into notes, drafted sections through model calls, revised them through change lists and kept a checkpoint. The author now works through a coding agent that can read the repository, edit the `.tex` directly and run commands. Two orchestrators competed for the same job, and every feature of the drafter (ideas, injections, scope, change lists) existed to steer a model the agent now replaces.

## Alternatives considered

- **Keep the two-phase flow (ideas, then text).** Ideas and `.tex` desync as soon as the author edits the text, and a facts folder does not capture flow edits.
- **One prompt per subagent.** It splits the author's steering across contexts. A job keeps one context over many rounds of feedback.
- **Copy the injections one to one.** Scope, expansion and compression measured prose against idea bullets that no longer exist. Their techniques survive as moves.
- **An MCP server.** A CLI is enough, runs in every harness and needs no process.
- **Hydra for guide pages.** Guides are Markdown pages merged by path; settings are TOML.
- **Notes and indexes of figures, tables and papers.** The agent reads figures, PDFs and plotting code directly, so the indexes only add drift.
- **Refactor `texfy-ai` in place.** The orchestrator, its model plumbing and the idea vault run through every module. A new repo with `texfy` as a read-only reference keeps the old tool running until the new one proves more useful.

## Decision

`parla` is a new tool in its own repository. The artifact is the source of truth, and the agent edits it directly. Guides (stable principles) and a casebook (corrections the author approved) tell the agent how to say it. The deterministic machinery of `texfy` is copied module by module and keeps its contracts: the LaTeX core is ported as [latex engine](../latex-engine.md) and [docker](../docker.md), with the layout in [template](../template.md) and [config](../config.md).

What changed in the ported contracts:
- The document table moves into the artifact's card, so an artifact owns its engine and entrypoint.
- `main_paper.tex` and `main_slides.tex` become a starter per artifact, chosen by the audience and modality.
- `workspace/references.bib` becomes one `references.bib` per artifact.
- The diff baseline is the job snapshot, and `diff` is part of `build` through `--diff-from`.
- Order files and `_appendix` files end: the agent edits `main.tex` directly.
- `[bib]` stores and `--frozen-bib` end: only the summarizer used the stores, and the drafter was the one that invented keys.
- The `texfy-ai` edits to `[packages]` end: the agent edits `parla.toml`.

## What tipped it

The author's own corrections to drafted text were the valuable signal, and the drafter had no place to keep them. A casebook the author approves, distilled into guides, keeps them.

## Trade-offs accepted

- Two tools coexist until the migration lands.
- The LaTeX engine is a copy, so a fix in `texfy` is ported by hand while both live.
