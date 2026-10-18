"""The `none` engine: plain-text artifacts with no compile step. See `specs/none-engine.md`."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from ... import config as config_mod
from ...checks import Finding, shared
from ...names import EXPORT_DIR, PROJECT_DIR
from ..base import Engine, Pages, Starter, normalize_tag, prepare_export_dir


class NoneEngine(Engine):
    name = "none"

    def prepare(self, root: Path) -> None:
        pass

    def starter(self, root: Path, artifact: str, modality: str, setup: dict | None) -> Starter:
        return Starter("post.md", {}, {"post.md": ""})

    def check(self, root: Path, artifact: str) -> list[Finding]:
        return shared.source_missing(root, artifact)

    def export(self, root: Path, artifact: str, tag: str, force: bool) -> Path:
        config_mod.load_card(root, artifact)
        base = root / PROJECT_DIR
        out_dir = base / EXPORT_DIR / artifact / f"{datetime.now(UTC):%Y-%m-%d}_{normalize_tag(tag)}"
        prepare_export_dir(out_dir, force=force)
        shutil.copytree(base / "artifacts" / artifact, out_dir, symlinks=False, dirs_exist_ok=True)
        return out_dir

    def pages(self, root: Path, artifact: str, language: str | None = None) -> Pages | None:
        return None
