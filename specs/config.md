# parla Config Spec

Related: **Read first** [architecture](architecture.md). **See also** [cli](cli.md), [docker](docker.md), [template](template.md), [checks](checks.md), [guides](guides.md), [engines](engines.md).

## Overview

`parla` reads three configs and keeps them apart:
- **`parla/parla.toml`** is the per-project contract: paths, packages and source links.
- **`parla/artifacts/<name>/card.md`** is the per-artifact contract: modality, audience, engine, entrypoint and the author's decisions.
- **`~/.config/parla/config.toml`** is the optional user config. With no file, `parla` keeps `parla/` inside the project. The file adds an external asset root, a Zotero library, a personal texmf and a private guide root.

## Language

- **Card**: the Markdown file with YAML frontmatter that describes one artifact.
- **Local / external**: local means `parla/` is a real folder in the project; external means `[storage].asset_root` is set and `parla/` is a symlink into it.
- **Link entry**: one `[links]` key/value pair, a symlink under `sources/` and the host path it points to.

## Map

- `parla.config` owns the `parla.toml` and card schemas and validation, and the accessors over the user config (`asset_root`, `library_*`, `texmf_home`, `guides_private`).
- `parla.settings` is the only reader of the user config file.

## Contracts

### `parla/parla.toml`

```toml
[project]
version = 1                                   # schema version (int, required; must be 1)

# [docker]                                    # optional
# image = "parla-texlive:2025.5"              # default: the tool's own locally-built image

[paths]
texmf = "texmf"                               # project TEXMFHOME, relative to parla/ (default "texmf")

[packages]                                    # optional; written into project.sty before each build
autoload = ["slides-macros"]                  # names of .sty/.tex files under parla/texmf or texmf_home
require  = ["adjustbox"]                      # stock packages

[checks]                                      # optional
ignore = ["todo-marker"]                      # check ids that never report in this project

[links]                                       # optional; synced by `parla link`
"results" = "results"                         # sources/results -> <project root>/results
"eval"    = "~/data/eval-tables"              # absolute and ~ paths are allowed
```

Resolution rules:
- **Outputs.** Build intermediates and logs go to `parla/.parla/build/<artifact>/`. The published PDF and diff go into the artifact folder (`parla/artifacts/<artifact>/<artifact>.pdf`, `<artifact>_diff.pdf`), and exports go to `parla/export/`. These locations are fixed, and `[paths]` accepts only `texmf`.
- **`TEXMFHOME`** is `/workspace/parla/<paths.texmf>` in the container.
- **`[storage].texmf_home`**, when set, is mounted read-only at `/workspace/.texmf-user` and added through `TEXMFAUXTREES` ([docker](docker.md#run-contract)).
- **Not configurable:** the engine and entrypoint belong to the card, and the `artifacts/` and `sources/` folder names are fixed ([template](template.md#base-tree)).

`[checks].ignore` lists check ids ([checks](checks.md#ids)) that are skipped for this project.

`[packages].autoload` is a list of `.sty` or `.tex` names resolved against the project texmf, then `[storage].texmf_home`. Before every build `parla` writes `\RequirePackage{name}` (`.sty`) or `\input{name.tex}` lines into a managed block in `parla/texmf/tex/latex/project/project.sty`, so entrypoints stay untouched. `[packages].require` lists stock LaTeX packages written as `\RequirePackage{name}` in the same block. An unresolvable `autoload` name is a fatal error.

`[links]` resolution:
- A **key** is a relative path under `parla/sources/`, for example `results`.
- A **value** is a host path:
  - `~` is expanded;
  - an absolute path is taken as-is;
  - a relative path resolves against the **project root**, the directory that holds `parla` ([architecture](architecture.md#language)).

`parla link` makes `parla/sources/<key>` a symlink to the resolved value ([cli](cli.md#parla-link)).

### The card

```markdown
---
modality: paper
audience: icra
engine: latex
latex: lualatex
entrypoint: main.tex
phase: polishing
traits:
  reader: cross-domain
derived-from: null
language: en
translations:
  pt: pt
---
# AcmeTrees, ICRA 2027

## decisions
- the architecture variants go only in the appendix (2026-10-13)

## rules

###### art-name
> call the method AcmeTrees, never "the tool" (origin: 2026-10-13)
```

| Key | Required | Meaning |
|---|---|---|
| `modality` | yes | the kind of artifact |
| `audience` | yes | the readership |
| `engine` | yes | a registered engine ([engines](engines.md)): `latex`, `svg` or `none` |
| `latex` | when `engine: latex` | `lualatex` or `pdflatex`; each engine declares its own keys in `card_keys` |
| `entrypoint` | yes | the file the engine builds, relative to the artifact folder |
| `phase` | yes | `drafting` or `polishing` |
| `traits` | no | map of trait kind to value (`reader`, `narrative`, `visual`, `pacing`) |
| `language` | no | the language code of the artifact's own entrypoint, lowercase; default `en` |
| `translations` | no | map of language code to a folder inside the artifact; each folder holds a full second tree with the same `entrypoint` name ([latex engine](latex-engine.md#translations)). `latex` engine only |
| `derived-from` | yes | name of the artifact this one was made from, or `null` |
| `limits` | no | per-artifact override of the audience's limits |

The body holds `## decisions` (what to say, dated) and `## rules` (style rules in the rule format owned by the guides).

### User config

Location: `$PARLA_CONFIG`, else `$XDG_CONFIG_HOME/parla/config.toml`, else `~/.config/parla/config.toml`. A commented template ships as `parla/data/config.example.toml`, and `parla config init` copies it.

```toml
[storage]
asset_root   = "~/parla-assets" # `parla init` keeps parla/ in <asset_root>/<project folder> and symlinks it
texmf_home   = "~/texmf"        # extra personal TEXMF tree, mounted :ro into the build
library_bib  = "~/zotero/library.bib"    # Better BibTeX export; enables library \cite resolution
library_json = "~/zotero/library.json"

[guides]
private      = "~/.config/parla"   # default; holds the user's guides and the casebook
target_words = 1500                # recommended size of one `guide show` output
tolerance    = 1.2                 # `guide show` and `job start --topics` warn to distill beyond target_words * tolerance
max_page_words = 350               # `guide lint` warns on a topic page over this
max_cases    = 8                   # case hooks listed in one load
max_probes   = 20                  # open probes the suite report lists at once
distill_min  = 3                   # active cases on one topic and audience before `case lint` reports a group
# stale_days = 180                 # unset: `case lint` makes no stale report
```

- **Local** (no `asset_root`): `parla init` makes a real `parla/`, and each artifact's `references.bib` merges `parla/sources/bib/*.bib`, scoped to the `\cite` keys.
- **External** (`asset_root` set): see [template](template.md#storage-modes).
- **`texmf_home`**, when set, must exist. It is consulted after the project's `parla/texmf/` and before the image's baked packages.
- **`[guides].private`** defaults to the config directory. [guides](guides.md), [casebook](casebook.md) and [constraints](constraints.md) own what it holds and what the other `[guides]` keys size.

## Constraints

- `[project].version` MUST be `1`.
- The card MUST carry every required key. `engine` MUST be a registered engine and the card MUST carry the engine's `card_keys`; `latex` MUST be `lualatex` or `pdflatex`; `phase` MUST be `drafting` or `polishing`.
- `entrypoint` MUST be relative and MUST NOT escape the artifact folder.
- `language` and every `translations` key MUST be a lowercase code of two or three letters, and a translation key MUST differ from `language`. A translation folder MUST be relative, MUST NOT contain `..` and MUST NOT be the artifact folder itself. `translations` MUST be empty unless `engine: latex`.
- `[docker].image`, when present, MUST be a tagged reference with no implicit `latest`. When absent, it is `image.IMAGE_REF`.
- Unknown top-level tables MUST be rejected. The allowed tables are `project`, `docker`, `paths`, `packages`, `checks` and `links`. An id in `[checks].ignore` that no check or constraint defines MUST be rejected. Unknown `[packages]` keys MUST be rejected.
- A `[links]` key MUST be relative, MUST NOT contain `..`, and MUST NOT be empty. Its value MUST be a non-empty string.
- `[guides].target_words` and `max_page_words` MUST be positive integers, `tolerance` MUST be a number of at least 1, and a removed key (`max_words`) MUST be rejected with the name of its replacement.
- Every user-config key is optional. An absent file or key means local storage and no extra features, never an error. A configured feature requested with a missing key MUST raise a `ConfigError` naming the key.

## History

- [Translations of one artifact](logs/2026-10-16_translations.md): the `language` and `translations` keys.
- [Sources, LaTeX and output folders](logs/2026-09-26_sources-latex-layout.md): inherited; `[paths] out`, `[links]`.
- [Portable texfy](logs/2026-09-09_portable-texfy.md): inherited; user config, contained default, optional `[docker].image`.
- [Two-phase build](logs/2026-10-14_two-phase-build.md): the `[checks]` table.
- [Lean prompts and a constraint suite](logs/2026-10-18_lean-prompts.md): the `[guides]` budget keys replace `max_words`.
- [Agent-first rewrite](logs/2026-10-14_agent-first-rewrite.md): the document table moves into the card; `[bib]` stores and `--frozen-bib` are dropped.
