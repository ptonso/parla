# Commands are routed per engine

**Affects**: [engines](../engines.md), [cli](../cli.md), [latex engine](../latex-engine.md), [svg engine](../svg-engine.md), [none engine](../none-engine.md), [tools](../tools.md).

## Situation

The first specs documented `build`, `watch` and `export` as LaTeX behavior, with the SVG and plain-text engines as footnotes. Each engine needs the same operations, and a command that names its engine in the CLI forces every new engine to touch the CLI. The tools sat as five separate top-level commands, and `watch` was a command of its own.

## Alternatives considered

- **Keep per-engine commands.** The CLI grows a branch per engine and per command.
- **One module per command that switches on the engine name.** Same problem inside the module.
- **Make `watch` an engine method.** The loop does not depend on the format: it polls files under `parla/` and rebuilds, so every engine would copy it.
- **Merge `docker.md` into the LaTeX spec.** The container serves the LaTeX engine, the SVG engine and `formula`, so it belongs to none of them.

## Decision

An engine contract ([engines](../engines.md)): `prepare`, `starter`, `check`, `build`, `export` and an optional `pages`. The CLI calls the card's engine through a registry, and the router owns what is independent of the format: running the checks before the build, resolving the diff baseline, and the watch loop. `watch` becomes `build --watch`. The five tools move under `parla tool`, and `check claims` and `source text` become `tool claims` and `tool source`, since they print facts and make no findings. The plain-text engine gets its own spec as the smallest example of the contract.

## What tipped it

A new engine (slides as HTML, say) should cost one package and one registry line. The conformance test makes that checkable.

## Trade-offs accepted

- An engine that cannot support an optional method fails at call time, not at registration.
- The router and the contract are one more layer to learn before reading an engine.
