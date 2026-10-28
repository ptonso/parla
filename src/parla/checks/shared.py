"""Checks every engine shares. See `specs/checks.md#ids`."""

from __future__ import annotations

import re
from pathlib import Path

from .. import config as config_mod
from ..names import PROJECT_DIR, is_output
from .finding import Finding
from .ids import finding

TEXT_SUFFIXES = {".tex", ".md", ".svg", ".txt"}
SKIPPED_FILES = {"card.md", "references.bib"}
_FIGURE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg", ".tex")
_COMMENT_RE = re.compile(r"(?<!\\)%.*")
_SOURCE_PATH_RE = re.compile(r"(?<![\w/.\-])sources/[^\s{}()\[\],\"'<>]+")


def card_invalid(root: Path, artifact: str) -> Finding | None:
    """A finding when the artifact has a card that does not validate; `None` when there is no
    card file (the caller fails on that) or the card is valid."""
    if not config_mod.card_path(root, artifact).is_file():
        return None
    try:
        config_mod.load_card(root, artifact)
    except config_mod.ConfigError as exc:
        return finding("card-invalid", f"artifacts/{artifact}/card.md", 1, str(exc))
    return None


def artifact_files(root: Path, artifact: str) -> list[Path]:
    """The text sources of an artifact; build outputs such as `BUILD-ERROR.txt` are not sources."""
    base = root / PROJECT_DIR / "artifacts" / artifact
    return [
        p for p in sorted(base.rglob("*"))
        if p.is_file() and p.suffix in TEXT_SUFFIXES and p.name not in SKIPPED_FILES
        and not is_output(p.relative_to(root / PROJECT_DIR))
    ]


def _exists(base: Path, rel: str) -> bool:
    path = base / rel
    return path.exists() or any(path.with_name(path.name + ext).exists() for ext in _FIGURE_EXTENSIONS)


def source_missing(root: Path, artifact: str) -> list[Finding]:
    """Every `sources/...` path an artifact file names that does not exist under `parla/`."""
    base = root / PROJECT_DIR
    findings: list[Finding] = []
    for path in artifact_files(root, artifact):
        rel_file = path.relative_to(base).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            text = _COMMENT_RE.sub("", line) if path.suffix == ".tex" else line
            for match in _SOURCE_PATH_RE.finditer(text):
                target = match.group(0).rstrip(".:;")
                if not _exists(base, target):
                    findings.append(finding("source-missing", rel_file, number, f"{target} does not exist"))
    return findings
