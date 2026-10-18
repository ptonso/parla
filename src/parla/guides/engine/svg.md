---
kind: engine
engine: svg
---
## facts

- Use only the elements the checks understand: `svg`, `g` with `translate`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `path` with `M L H V Z`, `text` and `tspan`, `image`, `defs`, `marker` and gradients. Anything else is reported as `svg-unsupported` and is not checked.
- Set `font-family="Latin Modern Sans"` (or `Latin Modern Mono`) on the text. The checks measure with those font files, so a measured width is the width that is drawn.
- An arrow is a `line`, `polyline` or `path` with `marker-end` or `marker-start`. Define the marker in `defs`.
- An `<image href>` is a path relative to `parla/`, such as `sources/...` or a file of the artifact.
