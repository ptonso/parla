# parla Specs

Related: **See also** [architecture](architecture.md).

`parla` helps a coding agent produce communication artifacts (papers, slides, posts, diagrams) in their final format, following the author's guides and learning from the author's corrections. It makes no model calls. These specs describe its contracts. Start with the architecture, then read the surface you need.

## Reading order

1. [Architecture](architecture.md) - parts, boundaries, shared terms.
2. [Template](template.md) - the `parla/` layout, artifact folders and starters, storage modes.
3. [Config](config.md) - `parla.toml`, the card and the user config.
4. [CLI](cli.md) - every command and the exit codes.
5. [Jobs](jobs.md) - the job folder, the snapshot, revert and the phase.
6. [Guides](guides.md) - roots, page kinds, the rule format, `guide show`.
7. [Casebook](casebook.md) - cases, hooks, retrieval, distillation.
8. [Constraints](constraints.md) - regex constraints and probes that run as a test suite.
9. [Checks](checks.md) - the finding format, severities, and the check set of each engine.
10. [Tools](tools.md) - `parla tool`: measure, table, formula, source, claims.
11. [Engines](engines.md) - the contract every engine implements, and the routing.
12. [LaTeX engine](latex-engine.md) - build, bibliography overlay, diff, export.
13. [SVG engine](svg-engine.md) - diagrams as SVG, rendered and checked.
14. [None engine](none-engine.md) - plain-text artifacts.
15. [Docker](docker.md) - the container every engine runs in: image, layers, run contract.
16. [Skill](skill.md) - how the agent uses the tool.

## History

- [logs/index.md](logs/index.md) - the reasoning behind decisions, including those inherited from texfy.
