# Translations of one artifact

**Affects**: [config](../config.md), [latex engine](../latex-engine.md), [checks](../checks.md), [engines](../engines.md), [tools](../tools.md), [jobs](../jobs.md), [template](../template.md).

## Situation

The author keeps each CV in English and in Portuguese. A first attempt used a second artifact per language (`cv-ai-rd` and `cv-ai-rd-pt`, linked by `derived-from`). The two drifted apart by construction: a change in one needed a manual copy into the other, and nothing in the tool knew they were the same document.

## Alternatives considered

- **One artifact per language, linked by `derived-from`.** Needs no change in the tool, but jobs, diffs and checks treat the versions as strangers, so a missing bullet in one version goes unnoticed.
- **One file per language sharing the sections** (`main.pt.tex`). Sections differ in text per language, so sharing has nothing to share, and the parity check would have to compare inside files.
- **Automatic translation in the build.** The tool makes no model calls.

## Decision

A card may name `language` (default `en`) and `translations`, a map from language code to a folder inside the artifact. Each folder holds a complete second tree with the same entrypoint name. `build` compiles every language and publishes `<artifact>.pdf` and `<artifact>-<code>.pdf` with their diffs. A `translation-parity` check compares the file set and the structural commands of each file, so a missing file, section, entry or bullet is an error. The cv modality guide carries the rule that a change in one language is applied to all in the same round.

## What tipped it

One artifact gives one job, one snapshot and one diff baseline for all languages, and the check can see both trees.

## Trade-offs accepted

- Translation is the agent's work, and the check verifies structure, not meaning.
- The references of all languages share one `references.bib`, scanned from every entrypoint.
- Only the `latex` engine supports translations.
