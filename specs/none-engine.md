# parla None Engine Spec

Related: **Read first** [engines](engines.md), [architecture](architecture.md). **See also** [checks](checks.md), [cli](cli.md).

## Overview

The `none` engine builds artifacts that are plain text with no compile step: a social post, a README section, a note. It has no Docker and no render. It checks the shared rules and exports a copy of the artifact folder. It has no build, since the entrypoint is already the output; a build will later mean publishing the text. It is the smallest engine and the template for new ones.

Walk-through: the author asks for a LinkedIn post. `init artifact linkedin-result --modality social-post --audience linkedin` writes the card and an empty `post.md`. The agent edits the post and runs `check`; `build` fails with `engine 'none' does not implement 'build'`, and `export` copies the folder to `export/linkedin-result/<yyyy-mm-dd>_<tag>/`.

## Language

- **Entrypoint**: the text file the card names, `post.md` by default.

## Map

`parla.engines.none` holds the engine. It uses no other engine and no container.

## Contracts

### Implementation of the contract

| Method | Behavior |
|---|---|
| `prepare` | does nothing |
| `starter` | entrypoint `post.md`, no engine-specific card keys, one empty file `post.md` |
| `check` | the shared checks only ([checks](checks.md#text-engine)) |
| `build` | not implemented: raises an `EngineError` naming the engine and the method |
| `export` | copies the artifact folder, dereferencing symlinks, to `export/<artifact>/<yyyy-mm-dd>_<tag>/`, with the same tag normalization and failures as the [LaTeX export](latex-engine.md#export) |
| `pages` | returns `None` |

`card_keys` is empty.

## Constraints

- `build` MUST fail with an `EngineError` and MUST NOT write any file.
- `export` MUST dereference symlinks.

## History

- [Engine contract](logs/2026-10-14_engine-contract.md): the smallest engine, and the template for new ones.
