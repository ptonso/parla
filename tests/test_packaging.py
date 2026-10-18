"""The built wheel is self-contained (docker/ + texmf/ + data/ + fonts + guides + skills) and carries no personal data."""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]


def test_wheel_contents(tmp_path):
    out = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(tmp_path), str(PKG_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    wheel = next(tmp_path.glob("parla-*.whl"))
    names = zipfile.ZipFile(wheel).namelist()

    for needle in (
        "parla/docker/Dockerfile",
        "parla/docker/tl.profile",
        "parla/docker/tl-packages.txt",
        "parla/texmf/tex/latex/arxiv-style/arxiv.sty",
        "parla/texmf/tex/latex/arxiv-style/License.txt",
        "parla/data/config.example.toml",
        "parla/assets/fonts/lmsans10-regular.otf",
        "parla/assets/fonts/LICENSE-Latin-Modern.txt",
        "parla/guides/general.md",
        "parla/guides/topic/flow.md",
        "parla/guides/constraints.jsonl",
        "parla/skills/parla/SKILL.md",
        "parla/py.typed",
    ):
        assert any(n.endswith(needle) for n in names), f"missing {needle}"
    assert any(".dist-info/licenses/LICENSE" in n for n in names)

    assert not any("tonso" in n or "parlacv" in n or "sbc" in n or "/logs/" in n for n in names)
    assert not any(n.endswith("parla/config.toml") for n in names)
