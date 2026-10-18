"""The SVG engine: diagrams written as plain SVG, checked geometrically and rendered in the
container. See `specs/svg-engine.md`."""

from __future__ import annotations

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from ... import config as config_mod
from ...checks import Finding, shared
from ...names import EXPORT_DIR, PROJECT_DIR
from ..base import Built, Engine, Pages, Starter, normalize_tag, prepare_export_dir
from ..latex.build import ensure_image
from . import build as build_mod
from . import checks as checks_mod

EMPTY = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 450">\n</svg>\n'
_IMAGE_HREF = re.compile(r'<image\b[^>]*?\bhref="([^"]+)"')


class SvgEngine(Engine):
    name = "svg"

    def prepare(self, root: Path) -> None:
        ensure_image(config_mod.load(root))

    def starter(self, root: Path, artifact: str, modality: str, setup: dict | None) -> Starter:
        return Starter(f"{artifact}.svg", {}, {f"{artifact}.svg": EMPTY})

    def check(self, root: Path, artifact: str) -> list[Finding]:
        card = config_mod.load_card(root, artifact)
        return [*shared.source_missing(root, artifact), *checks_mod.check(root, artifact, card.entrypoint)]

    def build(self, root: Path, artifact: str, baseline: Path | None) -> Built:
        pdf, png, diff = build_mod.build(root, artifact, baseline)
        return Built(published=(pdf, png), diff=diff)

    def export(self, root: Path, artifact: str, tag: str, force: bool) -> Path:
        built = self.build(root, artifact, None)
        base = root / PROJECT_DIR
        card = config_mod.load_card(root, artifact)
        out_dir = base / EXPORT_DIR / artifact / f"{datetime.now(UTC):%Y-%m-%d}_{normalize_tag(tag)}"
        prepare_export_dir(out_dir, force=force)
        entry = Path("artifacts") / artifact / card.entrypoint
        files = [entry, *(Path(h) for h in _IMAGE_HREF.findall((base / entry).read_text(encoding="utf-8")) if not h.startswith(("data:", "http://", "https://")))]
        for rel in files:
            (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile((base / rel).resolve(), out_dir / rel)
        for path in built.published:
            shutil.copyfile(path, out_dir / path.name)
        return out_dir

    def pages(self, root: Path, artifact: str, language: str | None = None) -> Pages | None:
        return None
