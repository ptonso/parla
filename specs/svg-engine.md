# parla SVG Engine Spec

Related: **Read first** [engines](engines.md), [architecture](architecture.md), [checks](checks.md), [docker](docker.md). **See also** [cli](cli.md), [tools](tools.md), [jobs](jobs.md).

## Overview

The SVG engine implements the [engine contract](engines.md#the-engine) for `engine: svg`: a diagram written by the agent as plain SVG. The engine checks the SVG geometrically, renders it to PDF and PNG with `rsvg-convert` in the same image as the LaTeX build, and shows what changed since the baseline. The agent looks at the PNG and fixes the SVG until it reads well, and a paper includes the PDF as a figure.

texfy-ai produced diagrams through a layout engine that made overflow and overlap impossible by construction. The agent now writes absolute coordinates itself, so the guarantee moves into checks: a diagram that overflows or collides fails the check phase with a short message before any render.

Walk-through: the agent writes `artifacts/knn-graph/knn-graph.svg` and runs `parla build knn-graph`. The check phase measures every label with the Latin Modern metrics, finds one label wider than its box, and stops with `knn-graph.svg:14: error svg-overflow: ...`. The agent widens the box, builds again, and the render lands in `artifacts/knn-graph/knn-graph.pdf` and `artifacts/knn-graph/knn-graph.png`.

## Language

- **Entrypoint**: the `.svg` file the card names.
- **Box**: the smallest `<rect>` whose area contains a text's anchor point.
- **Supported subset**: the SVG elements and attributes the checks understand ([below](#supported-subset)).
- **Side-by-side**: the diff image: the baseline render on the left, the current render on the right.

## Map

- `parla.engines.svg.engine` implements the contract by delegating to the modules below.
- `parla.engines.svg.build` renders with `rsvg-convert` through the same container contract as the LaTeX build ([docker](docker.md#run-contract)).
- `parla.engines.svg.fonts` loads the bundled Latin Modern fonts and measures text.
- `parla.engines.svg.checks` holds the geometric checks.
- Fonts ship in `parla/assets/fonts/`.

## Contracts

### Implementation of the contract

| Method | Behavior |
|---|---|
| `prepare` | ensures the image, as the LaTeX engine does ([docker](docker.md)) |
| `starter` | entrypoint `<artifact>.svg` holding an empty canvas, `viewBox="0 0 800 450"`; no engine-specific card keys |
| `check` | the shared checks and the SVG check set ([checks](checks.md#svg-engine)) |
| `build` | [Build](#build) |
| `export` | [Export](#export) |
| `pages` | returns `None` |

`card_keys` is empty.

### Build

`build` renders the SVG; the router has already run the checks and resolved the baseline ([engines](engines.md#router-behavior)).
- **Render.** `rsvg-convert -f pdf` and `-f png -z 2` run in the container with `rsvg-convert` in place of latexmk. An `<image href>` is relative to `parla/`, and librsvg reads only below the SVG's own directory, so each render is of a temporary copy at `parla/.render-<name>.svg`, removed afterwards. Outputs go to `.parla/build/<artifact>/<artifact>.pdf` and `.png`, with the transcript in `<artifact>_build.log`, and are published to `artifacts/<artifact>/<artifact>.pdf` and `.png`.
- **Diff.** When a baseline exists, the baseline SVG is rendered the same way and a wrapper SVG places the two PNGs side by side; it is rendered to `artifacts/<artifact>/<artifact>_diff.png`.
- A render failure exits with code 2 and prints `rsvg-convert`'s message as a finding with id `compile-error`.

### Export

`export(artifact, tag, force)` builds the artifact, then assembles `export/<artifact>/<yyyy-mm-dd>_<tag>/` holding the SVG, its published PDF and PNG, and every file an `<image href>` names, copied with symlinks dereferenced at the same relative paths. The tag normalization and the failures are those of the [LaTeX export](latex-engine.md#export).

### Fonts

Diagrams use the Latin Modern families (sans and mono). The image carries the same fonts through fontconfig, and `fonts` measures with the same files, so a text measured by the checks is the width `rsvg-convert` draws.

### Supported subset

The checks understand: `svg`, `g` (with `translate` transforms), `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `path` (commands `M L H V Z` and their relative forms), `text` and `tspan`, `image`, `defs`, `marker`, gradients. Other elements and transforms produce a `svg-unsupported` warning naming them, and are excluded from the geometric checks.

An arrow is a `line`, `polyline` or `path` with a `marker-end` or `marker-start`.

### Images and formulas

An `<image href>` is a path relative to `parla/` (`sources/...` or an artifact file). Math in a diagram is a rendered formula ([tools](tools.md#parla-tool-formula-artifact-tex---display)) placed as an `<image>`, because the width of typeset math cannot be predicted from characters. Literal `$...$` in a `<text>` is reported as `svg-math-in-text`.

### Geometric checks

- `svg-overflow`: a text's measured extent leaves its box, or the canvas.
- `svg-collision`: the extents of two texts overlap, or a text overlaps a shape that does not contain it.
- `svg-arrow-crossing`: an arrow passes through a shape that is neither its start nor its end.
- `svg-glyph-missing`: a character the font lacks.
- `svg-href-missing`: an `<image href>` that does not resolve.

The ids and severities are in [checks](checks.md#svg-engine).

## Constraints

- The check phase MUST measure text with the same font files the image renders with.
- An element outside the supported subset MUST produce a warning and MUST NOT be silently skipped.
- The engine MUST write only under `.parla/`, `export/` and the artifact's own folder.
- `rsvg-convert` MUST run in the container, never on the host.

## History

- [Agent-first rewrite](logs/2026-10-14_agent-first-rewrite.md): the layout engine ends and its guarantees become checks.
