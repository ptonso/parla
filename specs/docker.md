# parla Docker Spec

Related: **Read first** [architecture](architecture.md). **See also** [config](config.md), [template](template.md), [cli](cli.md), [latex engine](latex-engine.md), [svg engine](svg-engine.md).

## Overview

This spec defines the container every engine runs in. The image carries TeX Live for the [LaTeX engine](latex-engine.md), `rsvg-convert` and the fonts for the [SVG engine](svg-engine.md), and `pdflatex` and `pdftoppm` for `parla tool formula` ([tools](tools.md#parla-tool-formula-artifact-tex---display)). Each engine decides what to run; this spec fixes how any of them runs: the image, its layers and the run contract.

`parla` compiles documents inside an ephemeral container built from a **locally built** image. The Dockerfile and its build context ship inside the wheel; `parla` builds `parla-texlive:<version>` on first use and reuses it, with persistence handled by the Docker daemon's image store. There is no registry.

A build is one `docker run --rm`: the project's `parla/` is bind-mounted, latexmk runs as the invoking host uid/gid, intermediates land in `parla/.parla/build/<artifact>/`, and the PDF is then published to `parla/artifacts/<artifact>/<artifact>.pdf`, owned by the host user.

## Language

<a id="layers"></a>

- **Layer 1** - TeX distribution and system-wide packages (TeX Live, latexmk, and the IEEE classes `ieeetran` and `ieeeconf` from `tl-packages.txt`). Baked into the image.
- **Layer 2** - redistributable template packages baked under `texmf/tex/latex/` (`arxiv-style`). Venue-specific styles and personal layouts belong to Layer 2b.
- **Layer 2b** - the user's personal TEXMF tree (`[storage].texmf_home`), mounted read-only at runtime, not in the image.
- **Layer 3** - project packages and fonts in `parla/texmf/`, mounted as `TEXMFHOME`.
- **Layer 4** - the project's `parla/` tree (`artifacts/`, `sources/`, `export/`, `.parla/`), owned by the repository.
- **kpathsea** - TeX's path search; resolves Layer 3 → 2b (`TEXMFAUXTREES`) → 2 (`TEXMFLOCAL`) → 1.

## Map

`parla.engines.latex.image` owns identity and `docker build`; `parla.engines.latex.build` owns `docker run`. The build context is `parla/docker/` (Dockerfile, `tl.profile`, `tl-packages.txt`) and `parla/texmf/` (Layer 2 with licenses; see `THIRD-PARTY.md`).

## Contracts

### Run contract
```
docker run --rm \
  --volume "$PARLA_DIR:/workspace/parla" \
  [--volume "$SOURCE_LINK_TARGET:/workspace/parla/sources/$SOURCE_LINK_REL:ro" ...] \
  --workdir /workspace/parla \
  --user "$(id -u):$(id -g)" \
  [--volume "$TEXMF_HOME_HOST:/workspace/.texmf-user:ro"  --env TEXMFAUXTREES=/workspace/.texmf-user, ...] \
  --env TEXMFVAR=/tmp/texmf-var \
  --env TEXMFHOME=/workspace/parla/<paths.texmf> \
  <cfg.image> \
  latexmk \
    -<engine> \
    -silent \
    -interaction=nonstopmode \
    -halt-on-error \
    -file-line-error \
    -outdir=.parla/build/<artifact> \
    artifacts/<artifact>/<entrypoint>
```
- `$PARLA_DIR` is the **symlink-resolved** `parla/` directory. Only `parla/` is mounted - every path in the contract (workdir, `TEXMFHOME`, entrypoint, `-outdir`, figure mounts) lives under it, and `parla/` is commonly a symlink into an out-of-repo asset store. Mounting the parent instead would place that dangling symlink at `/workspace/parla`, and runc aborts container init with `mkdir /workspace/parla: file exists` before latexmk ever runs.
- One `$SOURCE_LINK_*` mount per symlink found by walking `parla/sources/` without following links (declared in `[links]` or made by hand): the resolved host target is mounted read-only at the matching in-project path. A dangling link is a `BuildError` naming it.
- `<engine>` ∈ {`lualatex`, `pdflatex`} from the card's `latex` key.
- `-silent` keeps the transcript terse; `-file-line-error` makes engine errors carry `file:line:` so the failure excerpt (below) can find them.
- The engine PDF appears at host `parla/.parla/build/<artifact>/<stem>.pdf`; on success `build.py` copies it to `parla/artifacts/<artifact>/<artifact>.pdf`. Both are owned by the invoking host user.
- That uid has no container passwd entry, so `$HOME` is unresolvable and the default `TEXMFVAR` under it is unwritable; `TEXMFVAR` MUST therefore be redirected to `/tmp`, or `lualatex` aborts with `luaotfload | load : FATAL ERROR … no writeable cache path`. The cache is discarded with the container, which is `--rm` regardless. `TEXMFCACHE` MUST NOT be set - pointing it at a non-existent path breaks the same lookup that `TEXMFVAR` fixes.

### Build output

`run_docker_latexmk` writes the **complete** latexmk/engine transcript to `parla/.parla/build/<artifact>/<artifact>_build.log`, verbatim. What reaches the console is deliberately minimal, with no hand-maintained allow/deny list:

- A clean build prints nothing from the transcript - the CLI's own one-line "built `<pdf>`" is the whole output.
- A failed build raises a `BuildError` whose message is `build failed (exit <n>) -- full log at <path>` followed by a focused excerpt: the first TeX error up to the `l.<n>` source line it points at, taken from the engine `.log` (`<stem>.log`, which carries `file:line:` and the source context) when it exists, else the tail of the latexmk transcript (a docker/latexmk failure before the engine ran). The CLI prints that message, and the router writes it to `BUILD-ERROR.txt` ([cli](cli.md#parla-build-artifact---watch---diff-from-pathgit-ref---no-diff---all)).

There is no "N lines suppressed" counter; the full log is always one path away.

### Image build inputs (shipped in the wheel under `parla/`)
```
docker/Dockerfile        # FROM debian:bookworm-slim; apt: perl + libalgorithm-diff-perl (latexdiff); installs Layer-1 from a frozen tlnet-final;
                         # copies texmf/ into the image TEXMFLOCAL; runs mktexlsr; a later, separate apt layer adds
                         # librsvg2-bin (rsvg-convert, the SVG engine's SVG-to-PDF rasterizer) and poppler-utils
                         # (pdftoppm, the SVG engine's formula-to-PNG rasterizer) so bumping
                         # either never invalidates the slow TeX Live install layer above it.
docker/tl.profile        # coarse TeX Live collections (scheme-small + basic/latex/latexrec/xetex)
docker/tl-packages.txt   # explicit packages (latexmk; titlesec for personal layout packages; latexdiff for the build diff; ieeetran and ieeeconf, both LPPL)
texmf/tex/latex/
  arxiv-style/            # redistributable template package (MIT), as-is
texmf/bibtex/bib/         # the sample .bib of the template
```
`image.py` runs `docker build --tag <IMAGE_REF> --file <docker/Dockerfile> <parla/>`.

### Image identity
- Local tag only: `parla-texlive:<IMAGE_VERSION>` (`image.IMAGE_REF`, the single source of truth). `IMAGE_VERSION` = `<texlive-year>.<rev>`, matching the frozen snapshot. Bump it when `docker/` or `texmf/` changes.

## Extending

To add a Layer 2 package: drop it under `parla/texmf/tex/latex/<name>/` with its license file, list it in `THIRD-PARTY.md`, and bump `IMAGE_VERSION`. Add explicit TeX Live packages to `tl-packages.txt`; coarse collections belong in `tl.profile`.

## Constraints

- `build.py` MUST emit the run contract above; it is the single source of truth and MUST match [config](config.md) resolution.
- The image MUST NOT contain Layer 2b, 3 or 4 content, and MUST NOT declare a `USER`; the uid is supplied per run.
- The image build MUST be reproducible (`TEXLIVE_MIRROR` points to a frozen `tlnet-final` snapshot, no `tlmgr update --self`) and arch-independent (`tl.profile` names no binary).
- `parla build` (including `--watch`, once before its loop) and `export` MAY build a missing image through the engine's `prepare` but MUST NOT rebuild an existing one. `PARLA_NO_AUTO_BUILD=1` requires an explicit `parla image build`.
- Layer 2 MUST hold redistributable packages only. The default generated templates MUST compile against a bare Layer 1 + Layer 2 image.
- `TEXMFVAR` MUST be `/tmp/texmf-var` and `TEXMFCACHE` MUST NOT be set (see the run contract).
- The image MUST provide a working `latexdiff` (`latexdiff --version` exits 0); the build diff runs it in the same container contract with the latexdiff command in place of latexmk.

## History

- [Outputs in the artifact folder](logs/2026-10-16_outputs-in-artifacts.md): builds publish into the artifact; intermediates in `.parla/`; exports in `export/`.
- [Sources, LaTeX and output folders](logs/2026-09-26_sources-latex-layout.md) - `out/` outdir and published PDFs, `sources/` link mounts, latexdiff in the image.

- [Portable texfy](logs/2026-09-09_portable-texfy.md) - local build instead of a hosted image; personal texmf moved out.
