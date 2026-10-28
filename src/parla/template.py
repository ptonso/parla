"""parla/ base-tree writer for `parla init` and the artifact folder writer. The only place that
knows the base layout.

With `[storage].asset_root` set, the base tree is written under `<asset_root>/<project folder
name>` and `parla/` in the project is a symlink to it. Without it, `parla/` is a real directory
in the project.
"""

from __future__ import annotations

from pathlib import Path

from . import config as config_mod
from .engines.latex.image import IMAGE_REF
from .names import BODY_END_LABEL, NAME, PROJECT_DIR, TOML

SKILLS_DIR = Path(__file__).parent / "skills"

# Directories that exist in the base tree even when otherwise empty.
DIRS = (
    "artifacts",
    "sources/bib",
    "texmf/tex/latex/project",
    "texmf/fonts/opentype/project",
    "export",
)

PARLA_TOML = f"""\
[project]
version = 1

# [docker]
# image = "{IMAGE_REF}"   # optional; defaults to the tool's own locally-built image

[paths]
texmf = "texmf"

# [checks]
# ignore = ["todo-marker"]         # check ids that never report in this project

# [links]                          # symlinks under sources/, synced by `{NAME} link`
# "results" = "results"            # value: relative to the project root, or absolute / ~
"""

PROJECT_STY = """\
\\NeedsTeXFormat{LaTeX2e}
\\ProvidesPackage{project}[2026/01/01 v0.1 project-local package]
% Project-specific macros, packages, and styling live here.
\\endinput
"""

FILES = {
    TOML: PARLA_TOML,
    "texmf/tex/latex/project/project.sty": PROJECT_STY,
}

PAPER = """\
\\documentclass{docclass}

{packages}
\\usepackage{{project}}

\\begin{{document}}

\\input{{artifacts/{name}/section/introduction}}

\\label{{{label}}}

\\bibliographystyle{{ieeetr}}
\\bibliography{{artifacts/{name}/references}}

\\end{{document}}
"""

TALK = """\
\\documentclass{docclass}

{packages}
\\usepackage{{project}}

\\title{{}}
\\author{{}}
\\date{{}}

\\begin{{document}}

\\begin{{frame}}[allowframebreaks]{{References}}
  \\bibliographystyle{{apalike}}
  \\bibliography{{artifacts/{name}/references}}
\\end{{frame}}

\\end{{document}}
"""

CV = """\\documentclass{docclass}

\\usepackage[margin=1.6cm]{{geometry}}
{packages}
\\usepackage{{project}}

\\begin{{document}}

{inputs}

\\label{{{label}}}

\\end{{document}}
"""

INTRODUCTION = "\\section{Introduction}\n"
CV_SECTIONS = {
    "header": "\\begin{center}\n{\\LARGE\\bfseries Name\\par}\n{\\small Contact line\\par}\n\\end{center}\n",
    **{name: f"\\section{{{name.capitalize()}}}\n" for name in ("summary", "experience", "projects", "education", "skills")},
}


STOCK = {
    "paper": (PAPER, "[a4paper,12pt]{article}", ("amsmath", "graphicx", "hyperref")),
    "talk": (TALK, "[aspectratio=169,11pt]{beamer}", ("graphicx", "adjustbox", "appendixnumberbeamer")),
    "cv": (CV, "[10pt]{article}", ("hyperref",)),
}
SECTION_FILES = {
    "paper": {"section/introduction.tex": INTRODUCTION},
    "cv": {f"section/{name}.tex": text for name, text in CV_SECTIONS.items()},
}
# Classes the image provides: the base TeX Live set and the IEEE classes of docker/tl-packages.txt.
IMAGE_CLASSES = ("article", "report", "book", "beamer", "IEEEtran", "ieeeconf")


def _class_available(cls: str, texmf_dirs: list[Path]) -> bool:
    return cls in IMAGE_CLASSES or any(
        next(d.rglob(f"{cls}.cls"), None) is not None for d in texmf_dirs if d.is_dir()
    )


def stock_files(
    modality: str, name: str, setup: dict | None = None, texmf_dirs: list[Path] | None = None
) -> dict[str, str]:
    """The starter files of a LaTeX modality, keyed by path relative to the artifact folder: the
    stock template, or the audience's `setup` (a document class and the packages it loads)."""
    if modality not in STOCK:
        raise config_mod.ConfigError(f"no stock template for modality '{modality}' (have: {', '.join(STOCK)})")
    skeleton, docclass, packages = STOCK[modality]
    if setup is not None:
        cls = setup.get("template")
        if not isinstance(cls, str) or not _class_available(cls, texmf_dirs or []):
            raise config_mod.ConfigError(
                f"the audience setup needs the class '{cls}', which no layer provides "
                "(image, packaged texmf, [storage].texmf_home or the project texmf)"
            )
        docclass, packages = f"{{{cls}}}", tuple(setup.get("packages") or ())
    sections = SECTION_FILES.get(modality, {})
    main = skeleton.format(
        name=name, label=BODY_END_LABEL, docclass=docclass, packages="\n".join(f"\\usepackage{{{p}}}" for p in packages),
        inputs="\n".join(f"\\input{{artifacts/{name}/{Path(rel).with_suffix('')}}}" for rel in sections),
    )
    return {"main.tex": main, **sections}


def parla_dir(root: Path) -> Path:
    return root / PROJECT_DIR


def _ensure_parla_link(root: Path, local: bool) -> Path:
    """Provision `<root>/parla` and return the path the base tree is written to.

    Local storage (no `[storage].asset_root`, or `local`): `parla/` is a real directory in the project.
    External storage: `parla/` is a symlink to `<asset_root>/<project folder name>`; a
    pre-existing real `parla/` directory, a symlink pointing elsewhere, or an existing target
    that `parla/` does not link to is a fatal error.
    """
    parla_link = root / PROJECT_DIR
    assets = None if local else config_mod.asset_root()

    if assets is None:
        if parla_link.is_symlink():
            raise config_mod.ConfigError(
                f"{parla_link} is a symlink but storage is local (no [storage].asset_root, or --local). "
                f"Remove it, or set [storage].asset_root (`{NAME} config init`)."
            )
        parla_link.mkdir(parents=True, exist_ok=True)
        return parla_link

    target = assets / root.resolve().name
    if parla_link.is_symlink():
        current = parla_link.resolve()
        if current != target.resolve():
            raise config_mod.ConfigError(
                f"{parla_link} is a symlink to {current}, expected {target}. "
                f"Fix or remove it manually, then re-run `{NAME} init`."
            )
    elif parla_link.exists():
        raise config_mod.ConfigError(
            f"{parla_link} already exists as a real directory. `{NAME} init` with [storage].asset_root "
            f"stores project content under {target} and links it in as {PROJECT_DIR}/. Move the existing "
            f"contents there yourself, e.g.:\n"
            f"  mkdir -p {target.parent}\n"
            f"  mv {parla_link} {target}\n"
            f"  ln -s {target} {parla_link}\n"
            f"then re-run `{NAME} init`."
        )
    elif target.exists():
        raise config_mod.ConfigError(
            f"{target} already exists but {parla_link} does not link to it: another project may share the "
            f"folder name '{root.resolve().name}'. Link it yourself with `ln -s {target} {parla_link}` if it "
            f"is this project's tree, or rename this project's folder."
        )
    else:
        target.mkdir(parents=True)
        parla_link.symlink_to(target, target_is_directory=True)

    return target


def init(root: Path, force: bool = False, local: bool = False) -> list[Path]:
    """Create the base parla/ tree for `root`, stored under an external asset target and
    symlinked in as `<root>/parla`; `local` keeps `parla/` a real directory despite a configured
    asset root. Idempotent; --force overwrites files.

    Returns the list of files written (created or, with force, overwritten).
    """
    root = root.resolve()
    base = _ensure_parla_link(root, local)
    for rel in DIRS:
        (base / rel).mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for rel, content in FILES.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            continue
        path.write_text(content)
        written.append(path)
    return written


def init_artifact(
    root: Path, name: str, card: str, files: dict[str, str], force: bool = False
) -> list[Path]:
    """Write `artifacts/<name>/card.md` and the starter files. Idempotent; `force` overwrites.
    Returns the files written."""
    root = root.resolve()
    base = parla_dir(root) / "artifacts" / name
    written: list[Path] = []
    for rel, content in {"card.md": card, **files}.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            continue
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def link_skills(project_root: Path) -> list[Path]:
    """Symlink every skill shipped in `skills/` into `<project>/.claude/skills/` and
    `<project>/.agents/skills/`.

    The package owns these links, so one pointing elsewhere (the package moved) is
    repointed; a real file or directory at the destination is never replaced.
    """
    linked: list[Path] = []
    for dest_dir in (project_root / ".claude" / "skills", project_root / ".agents" / "skills"):
        dest_dir.mkdir(parents=True, exist_ok=True)
        for skill in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()):
            link = dest_dir / skill.name
            if link.is_symlink():
                if link.resolve() == skill.resolve():
                    continue
                link.unlink()
            elif link.exists():
                raise FileExistsError(f"{link} is not a symlink; move it aside so init can link the {skill.name} skill")
            link.symlink_to(skill)
            linked.append(link)
    return linked
