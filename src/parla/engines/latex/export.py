"""Dependency tracing + standalone snapshot assembly. The only place that knows which files
an artifact depends on and how a `parla/export/<artifact>/<tag>/` folder is built. Fail-fast."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ... import config as config_mod
from ...config import Config, Document
from ...names import EXPORT_DIR, NAME, PROJECT_DIR
from ..base import ExportError, normalize_tag, prepare_export_dir
from . import build as build_mod

FIGURE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps")

_COMMENT_RE = re.compile(r"(?<!\\)%.*")
# \DiagramSlide{path} \input's its argument (slides-macros.tex); traced like \input/\include.
_INPUT_RE = re.compile(r"\\(?:input|include|DiagramSlide)\{([^}]+)\}")
# Commands whose argument is a file path; the checks import this list. Figure commands take
# their path before any [optional] args: plain \includegraphics plus the slides-macros.tex
# image layout commands.
PATH_COMMANDS = (
    "input", "include", "DiagramSlide",
    "includegraphics", "LeftImage", "RightImage", "TopImage", "BottomImage",
    "bibliography", "addbibresource",
)
_FIGURE_RE = re.compile(
    r"\\(?:includegraphics|LeftImage|RightImage|TopImage|BottomImage)"
    r"(?:\[[^\]]*\])?\{([^}]+)\}"
)
_BIBLIOGRAPHY_RE = re.compile(r"\\bibliography\{([^}]+)\}")
_ADDBIBRESOURCE_RE = re.compile(r"\\addbibresource\{([^}]+)\}")
_PACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}")
_DOCUMENTCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}")


@dataclass
class Manifest:
    tex_files: list[Path] = field(default_factory=list)
    figures: list[Path] = field(default_factory=list)
    bib_files: list[Path] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)
    shared_files: dict[Path, Path] = field(default_factory=dict)  # bare name -> Layer-2 source


def _layer2_root() -> Path:
    """This package's own Layer-2 texmf tree (specs/docker.md), baked into the image."""
    from importlib.resources import files

    return Path(str(files(NAME))) / "texmf"


def _layer2_index() -> dict[str, Path]:
    """`{filename: path}` for `.tex`/`.sty`/`.cls` under the packaged Layer-2 texmf, plus
    the user's `[storage].texmf_home` tree when configured (packaged wins a name clash)."""
    roots = [_layer2_root()]
    user_texmf = config_mod.texmf_home()
    if user_texmf is not None:
        roots.append(user_texmf)

    index: dict[str, Path] = {}
    for root in reversed(roots):  # packaged root processed last -> wins
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix in {".tex", ".sty", ".cls"}:
                index[p.name] = p
    return index


def _strip_comments(text: str) -> str:
    return "\n".join(_COMMENT_RE.sub("", line) for line in text.splitlines())


def _with_tex_suffix(rel: str) -> Path:
    p = Path(rel)
    return p if p.suffix else p.with_suffix(".tex")


def _resolve_figure(tex_root: Path, rel: str) -> Path:
    p = Path(rel)
    if p.suffix:
        if (tex_root / p).is_file():
            return p
        raise ExportError(f"referenced figure is missing: {p}")
    for ext in FIGURE_EXTENSIONS:
        candidate = p.with_suffix(ext)
        if (tex_root / candidate).is_file():
            return candidate
    raise ExportError(f"referenced figure not found (tried {FIGURE_EXTENSIONS}): {p}")


def trace_dependencies(root: Path, doc: Document, texmf: str) -> Manifest:
    """Walk `doc.entrypoint` and everything it \\input/\\include's, recursively.

    A bare (no directory) target missing from parla/ falls back to this package's own Layer-2
    texmf tree (e.g. `slides-macros.tex`, mirroring kpathsea's TEXMFHOME -> image TEXMFLOCAL
    order). Layer-2 files are copied opaquely, never recursively scanned: they're TeX package
    code and may contain macro-parameter braces (`{#1}`) that look like further \\input targets
    but aren't.
    """
    tex_root = root / PROJECT_DIR
    manifest = Manifest()
    seen_tex: set[Path] = set()
    packages_seen: set[str] = set()
    layer2 = _layer2_index()
    queue = [Path(doc.entrypoint)]

    while queue:
        rel = queue.pop(0)
        if rel in seen_tex:
            continue
        seen_tex.add(rel)
        path = tex_root / rel
        if not path.is_file():
            shared = layer2.get(rel.name) if rel.parent == Path(".") else None
            if shared is None:
                raise ExportError(f"referenced tex file is missing: {rel}")
            manifest.shared_files[rel] = shared
            continue
        manifest.tex_files.append(rel)
        text = _strip_comments(path.read_text(encoding="utf-8"))

        for m in _INPUT_RE.finditer(text):
            target = _with_tex_suffix(m.group(1).strip())
            if target not in seen_tex:
                queue.append(target)

        for m in _FIGURE_RE.finditer(text):
            manifest.figures.append(_resolve_figure(tex_root, m.group(1).strip()))

        for m in _BIBLIOGRAPHY_RE.finditer(text):
            for name in m.group(1).split(","):
                manifest.bib_files.append(Path(name.strip()).with_suffix(".bib"))

        for m in _ADDBIBRESOURCE_RE.finditer(text):
            for name in m.group(1).split(","):
                manifest.bib_files.append(Path(name.strip()))

        for m in (*_PACKAGE_RE.finditer(text), *_DOCUMENTCLASS_RE.finditer(text)):
            for name in m.group(1).split(","):
                packages_seen.add(name.strip())

    manifest.figures = list(dict.fromkeys(manifest.figures))
    manifest.bib_files = list(dict.fromkeys(manifest.bib_files))
    manifest.packages = sorted(packages_seen)

    for name in manifest.packages:
        if name == "project":
            continue
        for suffix in (".sty", ".cls"):
            shared = layer2.get(f"{name}{suffix}")
            if shared is not None:
                manifest.shared_files.setdefault(Path(f"{name}{suffix}"), shared)
                break

    _add_personal_texmf_deps(root / PROJECT_DIR / texmf, manifest, layer2)
    return manifest


_SHARED_REF_RE = re.compile(r"\\(?:usepackage|RequirePackage|LoadClass|input)(?:\[[^\]]*\])?\{([^}]+)\}")


def _add_personal_texmf_deps(project_texmf: Path, manifest: Manifest, layer2: dict[str, Path]) -> None:
    """Pulls in what the user's own TeX code loads in turn.

    Only `[storage].texmf_home` files and the project's texmf are scanned: the packaged Layer-2
    files stay opaque (their `{#1}` parameters look like `\\input` targets)."""
    packaged = _layer2_root().resolve()
    pending = [
        p for p in (*manifest.shared_files.values(), *sorted(project_texmf.rglob("*")))
        if p.is_file() and p.suffix in {".tex", ".sty", ".cls"} and not p.resolve().is_relative_to(packaged)
    ]
    while pending:
        text = _strip_comments(pending.pop().read_text(encoding="utf-8"))
        for m in _SHARED_REF_RE.finditer(text):
            for name in m.group(1).split(","):
                name = name.strip()
                for candidate in (name, f"{name}.sty", f"{name}.cls", f"{name}.tex"):
                    src = layer2.get(candidate)
                    if src is not None and Path(candidate) not in manifest.shared_files:
                        manifest.shared_files[Path(candidate)] = src
                        if not src.resolve().is_relative_to(packaged):
                            pending.append(src)
                        break


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _copy_manifest(tex_root: Path, manifest: Manifest, out_dir: Path) -> None:
    """.resolve() dereferences symlinks (e.g. [links] entries under sources/) so the export holds real,
    self-contained files rather than links into external storage."""
    for rel in (*manifest.tex_files, *manifest.figures, *manifest.bib_files):
        src = tex_root / rel
        if not src.is_file():
            raise ExportError(f"referenced file is missing: {rel}")
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src.resolve(), dst)


def _copy_shared_files(manifest: Manifest, out_dir: Path) -> None:
    for rel, src in manifest.shared_files.items():
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src.resolve(), dst)


def _write_latexmkrc(cfg: Config, out_dir: Path) -> None:
    """Overleaf (and any other latexmk-driven compiler) has no equivalent of the docker
    build's TEXMFHOME env var (engines/latex/build.py), so it never looks inside a project-local texmf/
    TDS tree on its own. latexmk reads a `latexmkrc` at the project root automatically,
    before compiling, so this is enough to make e.g. `\\usepackage{project}` resolve there
    too -- no change to the .tex sources themselves."""
    (out_dir / "latexmkrc").write_text(
        f"$ENV{{'TEXINPUTS'}} = './{cfg.texmf}//:' . $ENV{{'TEXINPUTS'}};\n", encoding="utf-8"
    )


def _copy_texmf(root: Path, cfg: Config, out_dir: Path) -> None:
    texmf_src = root / PROJECT_DIR / cfg.texmf
    if not texmf_src.is_dir():
        return
    shutil.copytree(texmf_src, out_dir / cfg.texmf, symlinks=False)
    _write_latexmkrc(cfg, out_dir)


def _copy_pdf(root: Path, cfg: Config, doc: Document, out_dir: Path) -> Path:
    pdf_src = root / PROJECT_DIR / "artifacts" / doc.name / f"{doc.slug}.pdf"
    if not pdf_src.is_file():
        raise ExportError(f"expected compiled PDF missing after build: {pdf_src}")
    dst = out_dir / f"{doc.stem}.pdf"
    shutil.copy2(pdf_src.resolve(), dst)
    return dst


def _source_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root, capture_output=True, text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _write_tex_config(
    root: Path, cfg: Config, doc: Document, manifest: Manifest, out_dir: Path, *, now: datetime
) -> None:
    lines = [
        f"{NAME}_project_version: {cfg.version}",
        f"docker_image: {cfg.image}",
        f"engine: {doc.engine}",
        f"entrypoint: {doc.entrypoint}",
        f"exported_at: {now.isoformat(timespec='seconds')}",
    ]
    commit = _source_commit(root)
    if commit is not None:
        lines.append(f"source_commit: {commit}")
    # references.bib is materialized by the build preflight (engines/latex/build.py), so a traced
    # bibliography holds exactly the citekeys this document uses -- already standalone.
    if manifest.bib_files:
        lines.append("bib_source: generated")
    lines.append(f"packages: [{', '.join(manifest.packages)}]")
    if manifest.shared_files:
        bundled = ", ".join(sorted(p.name for p in manifest.shared_files))
        lines.append(f"bundled_shared_files: [{bundled}]")
    (out_dir / "tex-config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_document(
    root: Path, cfg: Config, name: str, tag: str, *, force: bool, doc: Document | None = None
) -> Path:
    """Compile-check <name> (or its translation `doc`), trace its dependencies, and assemble a
    standalone snapshot at parla/export/<name>/<yyyy-mm-dd>_<tag>[-<language>]/. <tag> is
    normalized to lowercase, kebab-case."""
    doc = doc or config_mod.document(root, name)
    build_mod.build(root, cfg, name, doc=doc)
    manifest = trace_dependencies(root, doc, cfg.texmf)
    now = _utcnow()
    out_dir = root / PROJECT_DIR / EXPORT_DIR / name / f"{now:%Y-%m-%d}_{normalize_tag(tag)}{'-' + doc.tag if doc.tag else ''}"
    prepare_export_dir(out_dir, force=force)
    _copy_manifest(root / PROJECT_DIR, manifest, out_dir)
    _copy_shared_files(manifest, out_dir)
    _copy_texmf(root, cfg, out_dir)
    _copy_pdf(root, cfg, doc, out_dir)
    _write_tex_config(root, cfg, doc, manifest, out_dir, now=now)
    return out_dir
