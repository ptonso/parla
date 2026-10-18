# parla Engines Spec

Related: **Read first** [architecture](architecture.md), [config](config.md). **See also** [cli](cli.md), [checks](checks.md), [jobs](jobs.md), [latex engine](latex-engine.md), [svg engine](svg-engine.md), [none engine](none-engine.md).

## Overview

An engine turns one kind of artifact source into its output. The card names it (`engine: latex`), and every command that depends on the format, `check`, `build`, `export` and `init artifact`, is routed to that engine. The CLI never branches on an engine name: it looks the engine up in a registry and calls the same methods on whichever it finds. Adding an engine means implementing the contract and registering it.

The contract holds what every format needs: starter files, static checks, a build that publishes outputs and a change view, an export snapshot, and an optional page count. The router owns what does not depend on the format: running the checks before the build, choosing the diff baseline, and the watch loop.

Walk-through of `parla build knn-graph --watch`: the router reads the card and finds `engine: svg`. It calls `svg.prepare` once, then loops: it runs `svg.check`, stops on an error finding, otherwise resolves the baseline from the active job and calls `svg.build(root, "knn-graph", baseline)`, prints the published paths, and waits for the next file change.

## Language

- **Engine**: an implementation of the contract, registered under a name.
- **Registry**: the map from engine name to engine.
- **Router**: the CLI layer that finds the card's engine and calls it.
- **Baseline**: the earlier state a diff compares against: a directory that mirrors the project layout and holds `artifacts/<artifact>/`.
- **Starter**: the entrypoint name, the engine-specific card keys and the files `init artifact` writes for a new artifact.

## Map

- `parla.engines.base` holds the `Engine` contract, `Built`, `Starter` and `EngineError`.
- `parla.engines.registry` holds the name-to-engine map and `get(card)`.
- `parla.engines.latex`, `parla.engines.svg` and `parla.engines.none` implement it.
- `parla.router` holds the format-independent behavior: the check-then-build order, baseline resolution and the watch loop.

## Contracts

### The Engine

```python
class Engine:
    name: str
    card_keys: tuple[str, ...]                          # engine-specific required card keys
    def prepare(self, root) -> None                     # ensure what the engine needs, once
    def starter(self, root, artifact, modality, setup) -> Starter
    def check(self, root, artifact) -> list[Finding]
    def build(self, root, artifact, baseline) -> Built
    def export(self, root, artifact, tag, force) -> Path
    def pages(self, root, artifact, language=None) -> Pages | None  # optional
```

| Method | Contract |
|---|---|
| `prepare` | Idempotent. Ensures the engine's prerequisites exist, such as the Docker image ([docker](docker.md)), without rebuilding one that exists. |
| `starter` | Returns the `Starter`: the entrypoint file name, the engine's card keys with defaults (such as `latex: lualatex`), and a map from relative path to content. It writes nothing; `init artifact` writes the files without replacing existing ones. `modality` is the card's modality, and `setup` is the audience page's setup for it, or `None`. |
| `check` | Runs the engine's check set plus the shared checks ([checks](checks.md#runner)) and returns findings. Writes nothing. |
| `build` | Builds the artifact, publishes outputs into the artifact folder, and when `baseline` is not `None` also publishes a change view. Returns `Built`. Raises `BuildError` on failure. Does not run checks. |
| `export` | Assembles a standalone snapshot at `export/<artifact>/<yyyy-mm-dd>_<tag>/` and returns its path. Builds first, and fails when the build or any traced dependency fails. Fails when the snapshot exists, unless `force`. |
| `pages` | Returns the total and body page counts of the published output in `language` (default: the artifact's own), or `None` when the format has no pages. |

`Built` holds `published` (the paths in the artifact folder the CLI prints), `diff` (the change view, or `None`) and `diffs` (the change views of the artifact's translations). An engine may return a subclass with more fields; the LaTeX engine returns `LatexBuilt`, which adds `pdf` and `aux`.

A method an engine does not implement raises `EngineError` naming the engine and the method. `BuildError` and `ExportError` are `EngineError`s that the engines raise for a failed build or export. Every registered engine MUST implement `starter`, `check` and `export`, and `build` when its format has a build.

### Routing

`registry.get(card)` returns the engine named by the card's `engine`, or fails naming the registered engines. The CLI commands that call it:

| Command | Calls |
|---|---|
| `init artifact` | `starter`, then writes the card and the files |
| `check` | `check` |
| `build` | `prepare`, `check`, then `build` |
| `export` | `prepare`, then `export` |
| `tool measure --pages` | `pages` |

### Router behavior

- **Two phases.** `build` runs `check` and stops with exit code 1 when a finding is an error; only then does it call the engine's `build`. An engine's `build` never runs checks itself.
- **Baseline.** The router resolves it: the directory given by `--diff-from`; a git ref extracted with `git archive` of the artifact folder into a temporary layout-mirroring directory (failing when the folder is not inside a git work tree); else the snapshot of the artifact's active job ([jobs](jobs.md#diff-baseline)); else `None`. `--no-diff` passes `None`.
- **Watch.** `build --watch` runs `prepare` once, builds, then polls the modification times of every file under `parla/` except `export/`, `.parla/` and the build outputs of each artifact folder, never descending into symlinked directories under `sources/`, and rebuilds on change, running the same two phases. A failing cycle prints its findings and the loop continues. Ctrl-C exits with code 0.

### Engine-specific card keys

An engine declares `card_keys`, and config validation requires them in the card ([config](config.md#the-card)). The LaTeX engine requires `latex`.

## Extending

To add an engine: create `parla/engines/<name>/`, implement `Engine`, register it in `registry`, and write a spec named `<name>-engine.md` that says how each method is implemented, what its check set is ([checks](checks.md)) and what its starter holds. Check ids go in [checks](checks.md#ids). Imitate [none engine](none-engine.md), the smallest one. Reuse the container ([docker](docker.md)) for anything that needs tools beyond Python.

## Constraints

- Code outside `parla.engines` MUST NOT import a concrete engine; it uses the registry.
- Every registered engine MUST implement `starter`, `check` and `export`.
- An engine's `build` MUST NOT run checks and MUST NOT resolve the baseline.
- `check` MUST NOT write any file.
- `export` MUST NOT run when the snapshot exists, unless `force`.
- An engine MUST write only under `export/`, `.parla/` and the artifact's own folder.
- The registry MUST reject a card whose `engine` is not registered.

## History

- [Translations of one artifact](logs/2026-10-16_translations.md): `diffs` and the `language` argument of `pages`.
- [Engine contract](logs/2026-10-14_engine-contract.md): why commands are routed per engine and what the router owns.
