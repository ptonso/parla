# parla CLI Spec

Related: **Read first** [architecture](architecture.md). **See also** [engines](engines.md), [tools](tools.md), [jobs](jobs.md), [guides](guides.md), [casebook](casebook.md), [constraints](constraints.md), [checks](checks.md), [config](config.md), [template](template.md), [docker](docker.md), [skill](skill.md).

## Overview

`parla` is one command with thirteen subcommands. Commands take an *artifact selector* (the folder name under `artifacts/`), never a filename. The engine, entrypoint and limits come from the card.

Commands that depend on the artifact's format (`check`, `build`, `export`, `init artifact`) are routed to the artifact's engine ([engines](engines.md)), so they behave the same for every engine. This spec owns the command surface, the project commands and the exit codes; the other groups are specified where their subsystem is, and the table links to each.

## Commands

| Group | Command | Does | Spec |
|---|---|---|---|
| Project | `parla init` | create the `parla/` tree and link the skills | [cli](#parla-init---force) |
|  | `parla init artifact <name>` | add an artifact: its card and the engine's starter files | [cli](#parla-init-artifact-name---modality-m---audience-a---force) |
|  | `parla link` | sync the `sources/` symlinks from `[links]` | [cli](#parla-link) |
|  | `parla config {path,init,edit,show}` | find, create, edit or print the user config | [cli](#parla-config-pathiniteditshow) |
|  | `parla image {build,status}` | build or inspect the Docker image | [cli](#parla-image-buildstatus) |
| Artifact | `parla list` | the project's artifacts with modality, audience, phase and whether a job is active | [cli](#parla-list) |
|  | `parla check <artifact>` | run the engine's static checks and the constraints; `--resolve` records a verdict | [cli](#parla-check-artifact---all---resolve-key) |
|  | `parla build <artifact>` | check, build, publish and diff, then report the suite; `--watch` repeats on change | [cli](#parla-build-artifact---watch---diff-from-pathgit-ref---no-diff---all) |
|  | `parla export <artifact> --tag <t>` | standalone snapshot of the artifact | [engines](engines.md#routing) |
| Tool | `parla tool measure <artifact>` | words per file and body pages | [tools](tools.md#parla-tool-measure-artifact---words---pages) |
|  | `parla tool table <artifact> <source>` | parse, fit and render a table | [tools](tools.md#parla-tool-table-artifact-source---id-id---max-width-n---max-rows-n---font-step-step) |
|  | `parla tool formula <artifact> <tex>` | render a formula as a PNG | [tools](tools.md#parla-tool-formula-artifact-tex---display) |
|  | `parla tool source <citekey>` | text of a cited PDF, by section | [tools](tools.md#parla-tool-source-citekey---section-label---pages-a-b) |
|  | `parla tool claims <artifact>` | each citation with its sentence and paragraph | [tools](tools.md#parla-tool-claims-artifact) |
| Job | `parla job start <artifact>` | snapshot the artifact; the snapshot is the diff baseline | [jobs](jobs.md#parla-job-start-artifact---part-part---topics-t) |
|  | `parla job end <artifact>` | close the job and list the changed files | [jobs](jobs.md#parla-job-end-artifact) |
|  | `parla job revert <artifact>` | restore the artifact from the snapshot | [jobs](jobs.md#parla-job-revert-artifact) |
| Guide | `parla guide show <artifact> [part]` | the guides for what is about to be touched, as the model reads them; `--topics`, `--unformatted`, `--outline` | [guides](guides.md#parla-guide-show) |
|  | `parla guide show --topic`, `--move`, `--procedure` | one page, merged | [guides](guides.md#parla-guide-show) |
|  | `parla guide add <page> <rule-id>` | write a rule to the private root or a card; `--section` names the page section | [guides](guides.md#parla-guide-add-page-rule-id---text-text---origin-text---overrides-rule-id---evidence-case-ids---card-artifact---hook-text) |
|  | `parla guide move <rule-id> <page>` | move a rule to another page | [guides](guides.md#parla-guide-move-rule-id-page) |
|  | `parla guide edit <rule-id> --text <t>` | rewrite a private rule in place; the old text goes to the history | [guides](guides.md#parla-guide-edit-rule-id---text-text---evidence-case-ids) |
|  | `parla guide drop <rule-id>` | remove a private rule; its text goes to the history | [guides](guides.md#parla-guide-drop-rule-id) |
|  | `parla guide list [kind]` | the pages of the guides; `list topic` adds words and hooks | [guides](guides.md#parla-guide-list-kind) |
|  | `parla guide lint` | structure, origins, links and budget of the guides | [guides](guides.md#parla-guide-lint) |
| Case | `parla case add` | append a case read from standard input | [casebook](casebook.md#parla-case-add) |
|  | `parla case show <ids>` | print cases in full and log their use | [casebook](casebook.md#parla-case-show-idid) |
|  | `parla case list` | list cases by topic or status | [casebook](casebook.md#parla-case-list---topic-t---status-s) |
|  | `parla case edit <id>` | update the hook, lesson, problem or topics of a case | [casebook](casebook.md#parla-case-edit-id) |
|  | `parla case mark <id> <status>` | change a case's status | [casebook](casebook.md#parla-case-mark-id-status) |
|  | `parla case lint` | groups ready to distill and stale cases | [casebook](casebook.md#parla-case-lint) |
| Constraint | `parla constraint add` | append a constraint read from standard input | [constraints](constraints.md#parla-constraint-add) |
|  | `parla constraint list` | list constraints by kind or status | [constraints](constraints.md#parla-constraint-list---kind-k---status-s) |
|  | `parla constraint edit <id>` | update fields of a private constraint, read as JSON from standard input | [constraints](constraints.md#parla-constraint-edit-id) |
|  | `parla constraint mark <id> <status>` | change a constraint's status | [constraints](constraints.md#parla-constraint-mark-id-status) |
|  | `parla constraint lint` | examples that fail and constraints to refine | [constraints](constraints.md#parla-constraint-lint) |

## Language

- **Artifact selector**: the folder name `artifacts/<name>/`.
- **Project root**: see [architecture](architecture.md#language).
- **Router**: the layer that finds the card's engine and calls it ([engines](engines.md#language)).
- **Published output**: a file in the artifact folder (`<artifact>.pdf`, `<artifact>_diff.pdf`, the same pair as `<artifact>-<code>` for each translation, and the `.png` pair of a diagram), the copy of a successful build that the author reads. `BUILD-ERROR.txt` belongs to the same set of generated files.

## Map

`parla.cli` has one handler per command, delegating as follows:

| Command | Module |
|---|---|
| `init` | `template` |
| `init artifact`, `check`, `build`, `export` | `router`, then the engine from the registry |
| `link` | `engines.latex.links` |
| `image` | `engines.latex.image` |
| `config` | `settings` / `config` |
| `tool` | `tools` |
| `job` | `jobs` |
| `guide` | `guides` |
| `case` | `casebook` |
| `constraint` | `constraints` |

## Contracts

### `parla init [--force]`

Creates the `parla/` base layout, including `parla.toml` ([template](template.md#base-tree)).
- **Local:** `parla/` is a real directory.
- **External** (`[storage].asset_root`): the tree is written under `<asset_root>/<project folder name>`, and `parla/` is a symlink to it.
- **Idempotent:** existing files are kept unless `--force`.
- **Skills.** Every skill shipped in the package is symlinked into `<project>/.claude/skills/<name>` and `<project>/.agents/skills/<name>`. A link to another target is repointed, and a real file or directory at that path is an error.

### `parla init artifact <name> --modality <m> [--audience <a>] [--force]`

Adds `artifacts/<name>/`: the card and the engine's starter files ([template](template.md#artifact-folder)). The engine comes from the modality page, and its `starter` method supplies the entrypoint, the engine's card keys and the files. The audience defaults to `default`. Idempotent: existing files are kept unless `--force`. Fails when the modality or audience is unknown, or when a class the starter needs is missing.

### `parla list`

Prints one line per artifact folder: its name, modality, audience and phase, and `job active` when it has an active job. A card that does not validate prints its error in place of the fields. It writes nothing.

### `parla check <artifact> [--all] [--resolve <key>]`

Runs the artifact's engine's checks and the [constraints](constraints.md), prints one finding per line ([checks](checks.md#finding)) and the summary line of the suite. Constraints cover the lines changed in the active job, or the whole artifact with `--all` or without a job. It writes nothing, except with `--resolve`, which takes `--pass --evidence <quote>` or `--na --why <reason>`, appends one verdict to the active job ([constraints](constraints.md#verdicts)) and prints the suite again. Exits 1 on an engine error, 4 when the suite is not green, and 0 otherwise. With `--resolve` it exits 0 once the verdict is recorded, whatever the summary line says, so a chain of resolves runs to the end.

### `parla build <artifact> [--watch] [--diff-from <path|git-ref>] [--no-diff] [--all]`

Builds in three phases, routed to the artifact's engine ([engines](engines.md#router-behavior)):
1. **Check.** Runs `check`. An error finding stops the build and nothing is built. Warnings print and the build continues.
2. **Build.** Builds with the engine the card names, publishes the output into the artifact folder and, when a baseline exists, the change view. A failed build prints its first error with source context.

3. **Suite.** After a successful compile, reads the engine's post-build findings, appends the constraint findings and prints the report ([checks](checks.md#runner)). The published output stays in place when the suite is not green, and the command exits with code 4.

A failed check or build also writes `artifacts/<artifact>/BUILD-ERROR.txt`: a first line saying it is a generated file that `parla` rewrites on every failed build and deletes when a build succeeds, then the error text only (the error findings of a failed check, or the first TeX error with its source context and the path of the full log). Warnings are left out. The next successful build deletes the file. An engine without a build (`none`) fails with an engine error and writes no file.

`--diff-from` names the diff baseline and `--no-diff` skips the diff. `--watch` builds once and then rebuilds on every change under `parla/` ([engines](engines.md#router-behavior)); Ctrl-C exits. There is no flag that skips the check phase; a check that is wrong for a project goes in `[checks].ignore` ([config](config.md#parlaparlatoml)).

### `parla link`

Syncs `parla/sources/` with the `[links]` table ([config](config.md#parlaparlatoml)). For each entry, `parla/sources/<key>` becomes a symlink to the resolved value:
- A missing link is created, along with its parent folders.
- A symlink pointing elsewhere is repointed.
- A matching symlink is left as-is.
- A real file or directory at the path is an error: move it aside first.
- A value that does not exist on the host is an error.
- Symlinks under `sources/` that are not declared are left alone.

The command prints one line per created or repointed link.

### `parla config {path|init|edit|show}`

Operates on the user config ([config](config.md#user-config)):
- `path` prints its location.
- `init [--force]` writes the commented template.
- `edit` opens `$EDITOR`, creating the file from the template first.
- `show` prints every resolved `[storage]`/`[guides]` value, or `(unset)`.

It runs before the project-root lookup, so it works outside a project.

### `parla image {build|status}`

The image is shared by every engine that runs in the container ([docker](docker.md)).
- `status` reports whether `parla-texlive:<version>` exists locally, with its id, arch and size.
- `build [--force]` runs `docker build` from the packaged context. `--force` means `--no-cache`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | done; warnings may have printed |
| 1 | a check found an error; nothing was built |
| 2 | the engine failed to build |
| 3 | any other failure: usage, configuration, Docker unavailable |
| 4 | `check` or `build` found no engine error, and the suite is not green: a failure or an open probe remains (a build has published its output) |

`guide lint`, `case lint` and `constraint lint` print findings in the [finding format](checks.md#finding) and exit 1 when one is an error. `build --watch` exits 0 on Ctrl-C and never exits on a failing cycle.

## Constraints

- Every command except `init`, `config` and `image` MUST fail fast when no `parla.toml` is found.
- `build`, `check`, `export` and `init artifact` MUST reach the engine only through the registry.
- `build` and `export` MUST fail fast when `<artifact>` has no card.
- `check` MUST NOT modify any file, apart from the verdict that `--resolve` appends to the job.
- `build` MUST run the check phase before the engine's build, and MUST NOT build when a check reports an error.
- Every command MUST exit with the codes above.
- `link` MUST NOT delete or overwrite a real file or directory, and MUST NOT touch undeclared symlinks.
- `init` MUST NOT replace a real file or directory at a skill link path.

## History

- [Sources, LaTeX and output folders](logs/2026-09-26_sources-latex-layout.md): inherited; `link`, `export`.
- [Portable texfy](logs/2026-09-09_portable-texfy.md): inherited; `config` and `image` commands, contained-by-default `init`.
- [Agent-first rewrite](logs/2026-10-14_agent-first-rewrite.md): `init artifact`, the diff inside `build`, no document selector.
- [Two-phase build](logs/2026-10-14_two-phase-build.md): `check`, the exit codes, the ignore list.
- [Jobs and the snapshot diff](logs/2026-10-14_jobs.md): the `job` group.
- [Guides and casebook](logs/2026-10-14_guides-and-casebook.md): the `guide` and `case` groups.
- [Lean prompts and a constraint suite](logs/2026-10-18_lean-prompts.md): `constraint`, `case show`, `guide drop`, the suite report and exit code 4.
- [Engine contract](logs/2026-10-14_engine-contract.md): routed commands, `tool`, `build --watch`.
- [Translations of one artifact](logs/2026-10-16_translations.md): per-language outputs, snapshot and measure.
