# parla Architecture Spec

Related: **See also** [template](template.md), [config](config.md), [cli](cli.md), [checks](checks.md), [constraints](constraints.md), [engines](engines.md), [jobs](jobs.md), [guides](guides.md), [casebook](casebook.md), [tools](tools.md), [svg engine](svg-engine.md), [skill](skill.md), [latex engine](latex-engine.md), [docker](docker.md).

## Overview

`parla` helps a coding agent produce communication artifacts (papers, slides, posts, diagrams) directly in their final format. The author decides what to say. The agent writes the source files and learns how to say it from three memories: guides of stable craft principles, constraints that run as a test suite, and a casebook of the corrections the author made.

`parla` makes no model calls. Every command is deterministic: it reads the filesystem, acts and exits. The agent does all the reasoning, and the commands give it what it cannot do alone: a pinned Docker LaTeX build, diffs against a job snapshot, exports, table rendering, checks, the constraint suite, and the guides and case hooks for the part it is about to touch.

The LaTeX machinery is the `texfy` core, ported whole. Its contracts ([docker](docker.md), [latex engine](latex-engine.md), [template](template.md), [config](config.md)) change only where the artifact layout forces it.

Walk-through of `parla build icra-paper`: the CLI finds the project root, `config` reads `parla/parla.toml` and the artifact's card, `build` materializes `artifacts/icra-paper/references.bib`, ensures the image exists and runs the container; latexmk writes into `parla/.parla/build/icra-paper/` through the bind mount, the PDF is published to `parla/artifacts/icra-paper/icra-paper.pdf`, and when a diff baseline exists the change PDF is published beside it. A failed build leaves its errors in `parla/artifacts/icra-paper/BUILD-ERROR.txt`.

The image is built on the user's machine from a context shipped in the wheel. Without a user config the project keeps `parla/` *locally*; a user config adds an external asset root, a Zotero library, a personal texmf and a private guide root. See [config](config.md).

## Language

- **Artifact** - one piece of communication for one audience in one modality, as a folder `parla/artifacts/<name>/`. Its source files are the only truth for its content.
- **Card** - `card.md` in the artifact folder: modality, audience, engine, entrypoint, phase, traits, the decisions about what to say, and rules for this artifact. See [config](config.md#the-card).
- **Engine** - what turns an artifact's source into its output: `latex`, `svg` or `none`. The card names it.
- **Modality** - the kind of artifact: paper, talk, social post, diagram.
- **Audience** - the readership an artifact is written for. It sets limits, language and starter templates ([guides](guides.md#audience-page)).
- **Guides** - a default brief per modality shipped in the package, plus the author's preferences from the private root and the card, printed as one document ([guides](guides.md)).
- **Casebook** - the author's approved corrections, listed as hooks with the guides, opened on demand and distilled into guides or constraints ([casebook](casebook.md)).
- **Constraint** - a testable rule, a regex or a probe, that runs in `check` and `build` and reports what failed and where ([constraints](constraints.md)).
- **Job** - one piece of work on one part of one artifact, in one context. See [jobs](jobs.md). `job start` snapshots the artifact, and every build in the job diffs against that snapshot.
- **Image** - the local Docker image carrying TeX Live and the redistributable template packages (`parla-texlive:<version>`). See [docker](docker.md).
- **Project-local texmf** - `parla/texmf/`, mounted as `TEXMFHOME` (Layer 3, see [docker](docker.md#layers)).
- **Ephemeral build** - one `docker run --rm` per build; no persistent container.
- **Local / external** - whether `parla/` is a real folder in the project or a symlink into `[storage].asset_root`. See [config](config.md#user-config).
- **Project root** - the nearest ancestor directory containing `parla/parla.toml`; relative `[links]` values resolve against it.
- **`artifacts/`, `sources/`, `export/`** - the files an artifact owns (including the outputs of its builds), the read-only inputs it reads, and the export snapshots. See [template](template.md#base-tree).

## Map

- **Entry point**: `parla.cli` routes every command. Contracts in [cli](cli.md).
- **Name**: `parla.names` holds the one constant (`NAME`) from which the package name, CLI entry point, config directory, environment prefix and image tag derive.
- **Configuration**: `parla.config` validates `parla.toml` and the card and exposes the user-config accessors; `parla.settings` is the only reader of `~/.config/parla/config.toml`. Contracts in [config](config.md).
- **Engines** (`parla.engines`): `base` holds the contract, `registry` the name-to-engine map, and `parla.router` the format-independent behavior. Contracts in [engines](engines.md).
- **LaTeX engine** (`parla.engines.latex`): `build` is the only place that knows the `docker run`/`latexmk` flags; `image` owns image identity and the local `docker build`; `bib` resolves and materializes `references.bib`; `diff`, `export`, `links` and `autoload` serve the build. Contracts in [latex engine](latex-engine.md) and [docker](docker.md).
- **Jobs, guides and casebook**: `parla.jobs` owns the snapshot ([jobs](jobs.md)); `parla.guides` merges and prints the guides ([guides](guides.md)); `parla.casebook` stores and retrieves cases ([casebook](casebook.md)); `parla.constraints` stores constraints and runs the suite ([constraints](constraints.md)).
- **Project layout**: `parla.template` writes the `parla/` tree and the artifact starters. Contracts in [template](template.md).
- **Shipped data**: `parla/docker/` (image build context), `parla/texmf/` (Layer 2 packages), `parla/data/config.example.toml`, `parla/guides/` (public guide pages), `parla/skills/` (the skill), `parla/assets/fonts/`.
- **Checks**: `parla.checks` defines the finding and runs the check set of the artifact's engine. Contracts in [checks](checks.md).
- **SVG engine** (`parla.engines.svg`): renders diagrams and checks them geometrically. Contracts in [svg engine](svg-engine.md).
- **None engine** (`parla.engines.none`): plain-text artifacts. Contracts in [none engine](none-engine.md).
- **Tools** (`parla.tools`): measure, table, source, claims, formula, under `parla tool`. Contracts in [tools](tools.md).
- **Skill** (`parla/skills/parla/`): how the agent uses the tool. Contracts in [skill](skill.md).

## Contracts

### No model calls

`parla` never imports a model client and never makes a network call to compile once the image exists. The agent is the model.

### Stateless commands

Each command reads the filesystem, `parla.toml` and the card, acts, and exits. Only `build --watch` loops, in the foreground.

### One name constant

The product name appears in exactly one constant. Everything that carries the name derives from it, so a rename is a one-line change.

## Constraints

- `parla` MUST NOT import or call a model client.
- Commands other than `init` and `config` MUST fail fast when no `parla.toml` is found.
- The `docker run` flag set MUST live in `engines/latex/build.py` only and match [docker](docker.md#run-contract) verbatim.
- `engines/latex/image.py` MUST NOT import `build`, `config` or `template`.
- `config.py` MUST reject unknown top-level tables and missing required fields.
- The name MUST NOT be written as a literal outside `parla.names` and the package directory name.

## History

- [Engine contract](logs/2026-10-14_engine-contract.md): commands routed per engine.
- [Two-phase build](logs/2026-10-14_two-phase-build.md): static checks before the compile.
- [Jobs and the snapshot diff](logs/2026-10-14_jobs.md): the job owns the diff baseline.
- [Guides and casebook](logs/2026-10-14_guides-and-casebook.md): two memories.
- [Lean prompts and a constraint suite](logs/2026-10-18_lean-prompts.md): the third memory, constraints, and why the prompt shrank.
- [Outputs in the artifact folder](logs/2026-10-16_outputs-in-artifacts.md): why builds publish into the artifact folder.
- [Agent-first rewrite](logs/2026-10-14_agent-first-rewrite.md): why a new tool replaces the orchestrator, and the decisions behind the artifact layout.
- [Sources, LaTeX and output folders](logs/2026-09-26_sources-latex-layout.md): inherited from texfy; `sources/`, `out/`, `[links]`.
- [Portable texfy](logs/2026-09-09_portable-texfy.md): inherited; contained by default, user config, local image build, no registry.
