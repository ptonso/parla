from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import make_artifact
from parla import config as config_mod
from parla.engines.latex import diff as diff_mod
from parla.engines.base import BuildError
from parla.engines.latex.diff import flatten, render_diff


def _cfg() -> config_mod.Config:
    return config_mod.Config(
        version=1,
        image="custom/nonexistent:1",  # != image_mod.IMAGE_REF, so render_diff skips ensure_image
        texmf="texmf",
        links={},
    )


# --- flatten -----------------------------------------------------------------------------

SECTION = "artifacts/paper/section"


def test_flatten_inlines_nested_prose_inputs(tmp_path: Path) -> None:
    sections = tmp_path / SECTION
    sections.mkdir(parents=True)
    (sections / "intro.tex").write_text(f"Intro.\n\\input{{{SECTION}/motivation}}\n", encoding="utf-8")
    (sections / "motivation.tex").write_text("Motivation text.\n", encoding="utf-8")

    result = flatten(f"\\input{{{SECTION}/intro}}\n", [tmp_path], "paper")

    assert "Intro." in result
    assert "Motivation text." in result
    assert "\\input" not in result


def test_flatten_keeps_tables_diagrams_and_other_artifacts(tmp_path: Path) -> None:
    text = (
        "\\input{artifacts/paper/table/results}\n"
        "\\input{artifacts/other/section/intro}\n"
        "\\input{sources/diagram/pipeline}\n"
    )

    assert flatten(text, [tmp_path], "paper") == text


def test_flatten_keeps_a_commented_input(tmp_path: Path) -> None:
    sections = tmp_path / SECTION
    sections.mkdir(parents=True)
    (sections / "intro.tex").write_text("Intro body.\n", encoding="utf-8")
    text = f"% \\input{{{SECTION}/intro}}\n"

    assert flatten(text, [tmp_path], "paper") == text


def test_flatten_resolves_the_old_side_against_the_baseline_first(tmp_path: Path) -> None:
    old_dir = tmp_path / "baseline"
    base = tmp_path / "parla"
    (old_dir / SECTION).mkdir(parents=True)
    (base / SECTION).mkdir(parents=True)
    (old_dir / SECTION / "intro.tex").write_text("Old intro.\n", encoding="utf-8")
    (base / SECTION / "intro.tex").write_text("New intro.\n", encoding="utf-8")

    result = flatten(f"\\input{{{SECTION}/intro}}\n", [old_dir, base], "paper")

    assert "Old intro." in result
    assert "New intro." not in result


# --- render_diff ---------------------------------------------------------------------------


def test_render_diff_rejects_a_baseline_without_the_entrypoint(tmp_path: Path) -> None:
    make_artifact(tmp_path, "paper", {"main.tex": "x"})
    empty = tmp_path / "elsewhere"
    empty.mkdir()

    with pytest.raises(BuildError, match="the baseline must be a directory holding"):
        render_diff(tmp_path, _cfg(), "paper", empty)


def test_render_diff_writes_diff_tex_and_publishes_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "parla"
    old_dir = base / ".parla" / "jobs" / "x" / "snapshot"
    make_artifact(tmp_path, "paper", {"main.tex": f"\\input{{{SECTION}/intro}}\n", "section/intro.tex": "New body.\n"})
    (old_dir / SECTION).mkdir(parents=True)
    (old_dir / "artifacts/paper/main.tex").write_text(f"\\input{{{SECTION}/intro}}\n", encoding="utf-8")
    (old_dir / SECTION / "intro.tex").write_text("Old body.\n", encoding="utf-8")

    def fake_run(cmd, *, capture_output, text):
        return SimpleNamespace(returncode=0, stdout="DIFF OUTPUT", stderr="")

    def fake_compile_entrypoint(root, cfg, *, engine, entrypoint, outdir, log_name):
        pdf_path = base / outdir / f"{Path(entrypoint).stem}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.4")
        return pdf_path

    monkeypatch.setattr(diff_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(diff_mod, "compile_entrypoint", fake_compile_entrypoint)

    published = render_diff(tmp_path, _cfg(), "paper", old_dir)

    work = base / ".parla" / "build" / "paper_diff"
    assert (work / "old.flat.tex").read_text(encoding="utf-8").strip() == "Old body."
    assert (work / "new.flat.tex").read_text(encoding="utf-8").strip() == "New body."
    assert (work / "main_diff.tex").read_text(encoding="utf-8") == "DIFF OUTPUT"
    assert published == base / "artifacts" / "paper" / "paper_diff.pdf"
    assert published.read_bytes() == b"%PDF-1.4"
