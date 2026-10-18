"""The engine contract. See `specs/engines.md`."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from ..checks import Finding

_TAG_INVALID_RE = re.compile(r"[^a-z0-9]+")


class EngineError(Exception):
    """An engine cannot do what was asked."""


class BuildError(EngineError):
    """An engine failed to build an artifact."""


class ExportError(EngineError):
    """An artifact cannot be exported."""


@dataclass(frozen=True)
class Starter:
    entrypoint: str
    card_keys: dict[str, str]  # engine-specific card keys with defaults
    files: dict[str, str]  # path relative to the artifact folder -> content


@dataclass(frozen=True)
class Pages:
    total: int
    body: int | None


@dataclass(frozen=True)
class Built:
    published: tuple[Path, ...]  # the outputs in the artifact folder the CLI prints
    diff: Path | None = None  # the change view, when a baseline was given
    diffs: tuple[Path, ...] = ()  # the change views of the translations, when a baseline was given
    findings: tuple[Finding, ...] = ()  # the suite of the build: check, constraint and post-build findings


class Engine:
    """Subclasses implement the methods their format needs. A method left unimplemented
    raises `EngineError` naming the engine, so an unsupported command fails fast."""

    name: str
    card_keys: tuple[str, ...] = ()

    def _unsupported(self, method: str) -> EngineError:
        return EngineError(f"engine '{self.name}' does not implement '{method}'")

    def prepare(self, root: Path) -> None:
        raise self._unsupported("prepare")

    def starter(self, root: Path, artifact: str, modality: str, setup: dict | None) -> Starter:
        raise self._unsupported("starter")

    def check(self, root: Path, artifact: str) -> list[Finding]:
        raise self._unsupported("check")

    def build(self, root: Path, artifact: str, baseline: Path | None) -> Built:
        raise self._unsupported("build")

    def post_build(self, root: Path, artifact: str) -> list[Finding]:
        """Findings read from the engine's own output after a successful build."""
        return []

    def mask(self, text: str) -> str:
        """`text` with comments blanked, newlines kept, so a pattern never matches commented text."""
        return text

    def export(self, root: Path, artifact: str, tag: str, force: bool) -> Path:
        raise self._unsupported("export")

    def pages(self, root: Path, artifact: str, language: str | None = None) -> Pages | None:
        raise self._unsupported("pages")


def normalize_tag(tag: str) -> str:
    normalized = _TAG_INVALID_RE.sub("-", tag.strip().lower()).strip("-")
    if not normalized:
        raise ExportError(f"--tag must contain at least one alphanumeric character: {tag!r}")
    return normalized


def prepare_export_dir(out_dir: Path, *, force: bool) -> None:
    if out_dir.exists():
        if not force:
            raise ExportError(f"refusing to overwrite existing export {out_dir}; rerun with --force")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
