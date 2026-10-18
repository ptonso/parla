from __future__ import annotations

from pathlib import Path

import pytest

PUBLIC_GUIDES = Path(__file__).parent / "fixtures" / "guides" / "public"
PRIVATE_GUIDES = Path(__file__).parent / "fixtures" / "guides" / "private"


@pytest.fixture(autouse=True)
def _public_guides(monkeypatch, tmp_path):
    """Tests read the fixture guides as the public root, never the package pages, and never
    the user's own config."""
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "no-user-config.toml"))
    from parla.guides import pages

    monkeypatch.setattr(pages, "PUBLIC_ROOT", PUBLIC_GUIDES)

CARD = """\
---
modality: paper
audience: icra
engine: latex
latex: lualatex
entrypoint: main.tex
phase: drafting
derived-from: null
---
# {name}
"""


def make_artifact(root: Path, name: str = "paper", files: dict[str, str] | None = None) -> Path:
    """`parla/artifacts/<name>/` with a card and the given files; returns the artifact folder."""
    base = root / "parla" / "artifacts" / name
    base.mkdir(parents=True, exist_ok=True)
    (base / "card.md").write_text(CARD.format(name=name), encoding="utf-8")
    for rel, text in (files or {}).items():
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(text, encoding="utf-8")
    return base
