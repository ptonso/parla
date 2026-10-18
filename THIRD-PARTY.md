# Third-party components

The `parla` LaTeX build image (`src/parla/texmf/`) bundles the following, each under its own license. `parla` itself is Apache-2.0 (see `LICENSE`).

| Path | Component | License | Copyright |
| --- | --- | --- | --- |
| `texmf/tex/latex/arxiv-style/` | arXiv article style (`arxiv.sty`) + sample document | MIT (`arxiv-style/License.txt`) | © 2020 George Kour |
| `texmf/bibtex/bib/arxiv-references.bib` | Sample bibliography shipped with the arXiv template | as the template | - |

The author's personal LaTeX packages (a Beamer theme, slide-layout macros, a CV layout, the SBC conference style) are **not** shipped. Point `[storage].texmf_home` in `~/.config/parla/config.toml` at a local TEXMF tree to add your own.

Origin: copied from the `texfy` repository, `packages/texfy/THIRD-PARTY.md`.

The image also installs `ieeetran` (LPPL 1.3) and `ieeeconf` (LPPL), the IEEE journal and conference classes, from the frozen TeX Live 2025 `tlnet-final` mirror through `docker/tl-packages.txt`. They are installed at image build time and not redistributed in this repository.
