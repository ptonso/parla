"""docker-run composition + invocation. The only place that knows the latexmk flags."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ... import config as config_mod
from ...config import Config, Document
from ...names import BUILD_DIR, ENV_PREFIX, NAME, PROJECT_DIR
from ..base import BuildError
from . import autoload as autoload_mod
from . import image as image_mod

# latexmk runs with `-silent`, so a clean build is near-silent and the whole transcript
# goes to the log file untouched. These are only consulted to carve a focused excerpt out
# of the transcript when the build *fails* -- the first real error and its context.
_ERROR_START_RE = re.compile(r"^(?:! |[^:]+\.\w+:\d+: |! ==> Fatal error|Emergency stop)")
_SOURCE_CONTEXT_RE = re.compile(r"^l\.\d+ ")
_ERROR_CONTEXT_LINES = 20
_ERROR_FALLBACK_LINES = 40
_TRANSCRIPT_BUFFER_LINES = 600


def _texmf_home_mount() -> list[str]:
    """`[storage].texmf_home`, when set, is bind-mounted read-only and added to the search
    path via TEXMFAUXTREES (TL 2023+) - after the project's parla/texmf/, before the image's
    baked packages."""
    user_texmf = config_mod.texmf_home()
    if user_texmf is None:
        return []
    return [
        "--volume", f"{user_texmf.resolve()}:/workspace/.texmf-user:ro",
        "--env", "TEXMFAUXTREES=/workspace/.texmf-user,",
    ]


def ensure_image(cfg: Config, on_output: Callable[[str], None] = print) -> None:
    """Builds the image on first use. A no-op for a custom `[docker].image` or with
    `PARLA_NO_AUTO_BUILD` set."""
    if cfg.image == image_mod.IMAGE_REF and not os.environ.get(f"{ENV_PREFIX}_NO_AUTO_BUILD"):
        image_mod.ensure_image(on_output=on_output)


def docker_base(root: Path, cfg: Config) -> list[str]:
    """`docker run --rm` ... up to and including the image name: mounts (parla/, source links,
    texmf_home), workdir, user, env. The single home of the run contract's flags."""
    # Resolved, because `parla/` may be a symlink to an out-of-repo asset store: mounting the
    # parent would put a dangling symlink at /workspace/parla and runc fails before latexmk runs.
    return [
        "docker", "run", "--rm",
        "--volume", f"{(root / PROJECT_DIR).resolve()}:/workspace/{PROJECT_DIR}",
        *_source_link_mounts(root),
        *_texmf_home_mount(),
        "--workdir", f"/workspace/{PROJECT_DIR}",
        # Run as the host user so build artifacts are not root-owned in the bind mount.
        # That uid has no passwd entry, so TEXMFVAR must be redirected off the unresolvable
        # $HOME or luaotfload aborts with "no writeable cache path"; --rm discards it anyway.
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--env", "TEXMFVAR=/tmp/texmf-var",
        "--env", f"TEXMFHOME=/workspace/{PROJECT_DIR}/{cfg.texmf}",
        cfg.image,
    ]


def docker_command(root: Path, cfg: Config, *, engine: str, entrypoint: str, outdir: str) -> list[str]:
    """The ephemeral run contract from docker.md - the single source of truth."""
    return docker_base(root, cfg) + [
        "latexmk",
        f"-{engine}",
        "-silent",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        f"-outdir={outdir}",
        entrypoint,
    ]


def compile_entrypoint(
    root: Path,
    cfg: Config,
    *,
    engine: str,
    entrypoint: str,
    outdir: str,
    log_name: str,
) -> Path:
    """Run latexmk on `entrypoint` (relative to parla/) with outdir `outdir` (relative to
    parla/). Returns the outdir PDF. Raises BuildError on a non-zero exit, its message holding
    the first TeX error with its source context and the path of the full log."""
    failure: list[str] = []
    cmd = docker_command(root, cfg, engine=engine, entrypoint=entrypoint, outdir=outdir)
    out_dir = root / PROJECT_DIR / outdir
    returncode = run_docker_latexmk(
        cmd,
        log_path=out_dir / f"{log_name}_build.log",
        engine_log_path=out_dir / f"{Path(entrypoint).stem}.log",
        on_output=failure.append,
    )
    if returncode != 0:
        raise BuildError("\n".join(failure).rstrip())
    return out_dir / f"{Path(entrypoint).stem}.pdf"


def run_docker_latexmk(
    cmd: list[str],
    *,
    log_path: Path,
    engine_log_path: Path | None = None,
    on_output: Callable[[str], None] = print,
) -> int:
    """Runs a `docker run ... latexmk ...` command. The complete transcript is written to
    `log_path` verbatim; `on_output` receives **nothing on a clean build** and, on failure,
    a focused excerpt -- the first TeX error and its context (or the log tail) -- plus a
    pointer to the full log. latexmk runs `-silent`, so the transcript is already terse.
    `engine_log_path` is the `(la)tex` `.log`; it is the authoritative source for the error
    excerpt when present. Returns the process's exit code."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tail: deque[str] = deque(maxlen=_TRANSCRIPT_BUFFER_LINES)
    with open(log_path, "w", encoding="utf-8") as log_file:
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                log_file.write(raw_line if raw_line.endswith("\n") else raw_line + "\n")
                tail.append(raw_line.rstrip("\n"))
            returncode = proc.wait()
    if returncode != 0:
        on_output(f"build failed (exit {returncode}) -- full log at {log_path}")
        for line in _failure_excerpt(list(tail), engine_log_path):
            on_output(line)
    return returncode


def _failure_excerpt(transcript: list[str], engine_log_path: Path | None) -> list[str]:
    """The first TeX error and the lines that follow it. Prefers the engine `.log` (it
    carries the `file:line: message` and the `l.<n>` source context); falls back to the
    latexmk transcript tail when the engine never ran (a docker or latexmk failure). The excerpt
    ends with the source line the error points at, before TeX's help text and memory statistics."""
    for source in (_read_lines(engine_log_path), transcript):
        for index, line in enumerate(source):
            if _ERROR_START_RE.search(line):
                chunk = source[index : index + _ERROR_CONTEXT_LINES]
                context = next((i for i, text in enumerate(chunk) if _SOURCE_CONTEXT_RE.match(text)), None)
                return chunk if context is None else chunk[: context + 2]
    return transcript[-_ERROR_FALLBACK_LINES:]


def _read_lines(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _source_link_mounts(root: Path) -> list[str]:
    base = (root / PROJECT_DIR).resolve()
    sources = base / "sources"
    mounts: list[str] = []
    if not sources.is_dir():
        return mounts
    for current, dirnames, filenames in os.walk(sources, followlinks=False):
        dirnames.sort()
        for name in sorted([*dirnames, *filenames]):
            path = Path(current) / name
            if not path.is_symlink():
                continue
            target = path.resolve()
            if not target.exists():
                raise BuildError(f"source link is missing: {path} -> {target}")
            rel = path.relative_to(base).as_posix()
            mounts.extend(["--volume", f"{target}:/workspace/{PROJECT_DIR}/{rel}:ro"])
    return mounts


@dataclass(frozen=True)
class BuildResult:
    pdf: Path            # parla/.parla/build/<slug>/<stem>.pdf
    aux: Path            # parla/.parla/build/<slug>/<stem>.aux
    published_pdf: Path  # parla/artifacts/<artifact>/<slug>.pdf, the slug being <artifact> or <artifact>-<language>
    diff_pdf: Path | None = None  # parla/artifacts/<artifact>/<slug>_diff.pdf when a baseline was given


def build(
    root: Path,
    cfg: Config,
    name: str,
    *,
    doc: Document | None = None,
    baseline: Path | None = None,
    on_output: Callable[[str], None] = print,
) -> BuildResult:
    """Compile <name> (or its translation `doc`) in an ephemeral container and publish the PDF;
    with a `baseline` directory, also publish the change PDF. The caller runs the checks and
    picks the baseline.

    `parla/artifacts/<name>/references.bib` is first materialized from the Zotero library
    plus `parla/sources/bib/*.bib`, scoped to the `\\cite` keys the artifact actually uses.
    """
    doc = doc or config_mod.document(root, name)
    autoload_mod.sync_project_sty(root, cfg)
    ensure_image(cfg, on_output)
    _regenerate_references_bib(root, doc, on_output=on_output)
    pdf = compile_entrypoint(
        root, cfg,
        engine=doc.engine, entrypoint=doc.entrypoint, outdir=f"{BUILD_DIR}/{doc.slug}",
        log_name=doc.slug,
    )
    published = root / PROJECT_DIR / "artifacts" / doc.name / f"{doc.slug}.pdf"
    shutil.copy2(pdf, published)
    diff_pdf = None
    if baseline is not None:
        from .diff import render_diff  # diff imports this module

        diff_pdf = render_diff(root, cfg, name, baseline, doc=doc, on_output=on_output)
    return BuildResult(pdf=pdf, aux=pdf.with_suffix(".aux"), published_pdf=published, diff_pdf=diff_pdf)


_INPUT_RE = re.compile(r"\\(?:input|include|DiagramSlide)\{([^}]+)\}")


def _document_tex_texts(base: Path, entrypoint: str) -> list[tuple[str, str]]:
    """`(parla/-relative path, text)` for the entrypoint and everything it \\input's. A
    missing child is skipped."""
    seen: set[Path] = set()
    out: list[tuple[str, str]] = []
    queue = [Path(entrypoint)]
    while queue:
        rel = queue.pop(0)
        if rel.suffix == "":
            rel = rel.with_suffix(".tex")
        if rel in seen:
            continue
        seen.add(rel)
        path = base / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        out.append((rel.as_posix(), text))
        for m in _INPUT_RE.finditer(text):
            queue.append(Path(m.group(1).strip()))
    return out


def _regenerate_references_bib(root: Path, doc: Document, *, on_output: Callable[[str], None]) -> None:
    from . import bib

    base = (root / PROJECT_DIR).resolve()
    texts = [t for d in config_mod.documents(root, doc.name) for t in _document_tex_texts(base, d.entrypoint)]
    cite_sources = bib.scan_cite_key_sources(texts)
    library = bib.load_library(
        library_bib=config_mod.library_bib(), library_json=config_mod.library_json()
    )
    extras = bib.load_extras(base / "sources" / "bib")
    result = bib.resolve(cite_sources, library=library, extras=extras)

    if result.unresolved:
        raise BuildError(bib.format_unresolved(result.unresolved, cite_sources))
    for key, source in result.shadowed:
        on_output(f"{NAME}: extra '{source}' redefines '{key}'; the Zotero library wins")
    references = base / "artifacts" / doc.name / "references.bib"
    if bib.materialize(result, references):
        n = len(result.entries)
        on_output(f"{NAME}: wrote {PROJECT_DIR}/artifacts/{doc.name}/references.bib ({n} entr{'y' if n == 1 else 'ies'})")
