from __future__ import annotations

import sys
from pathlib import Path

import pytest

from conftest import make_artifact
from parla import config as config_mod
from parla.engines.latex import build as build_mod
from parla.engines.base import BuildError
from parla.engines.latex.build import docker_command, run_docker_latexmk


def test_clean_build_prints_nothing_but_logs_everything(tmp_path: Path) -> None:
    script = (
        "print('This is LuaHBTeX, Version 1.24.0')\n"
        "print('(/usr/local/texlive/texmf-dist/tex/latex/base/article.cls')\n"
        "print('Output written on main.pdf (3 pages).')\n"
    )
    cmd = [sys.executable, "-c", script]
    log_path = tmp_path / "build" / "main_build.log"
    shown: list[str] = []

    returncode = run_docker_latexmk(cmd, log_path=log_path, on_output=shown.append)

    assert returncode == 0
    assert shown == []
    logged = log_path.read_text(encoding="utf-8")
    assert "This is LuaHBTeX" in logged
    assert "Output written on main.pdf" in logged


def test_failed_build_emits_the_error_excerpt_and_a_log_pointer(tmp_path: Path) -> None:
    script = (
        "import sys\n"
        "print('(./main.tex')\n"
        "print('./main.tex:12: Undefined control sequence.')\n"
        "print('l.12 \\\\notacommand')\n"
        "print('Latexmk: Errors, so I did not complete making targets.')\n"
        "sys.exit(1)\n"
    )
    cmd = [sys.executable, "-c", script]
    log_path = tmp_path / "build" / "main_build.log"
    shown: list[str] = []

    returncode = run_docker_latexmk(cmd, log_path=log_path, on_output=shown.append)

    assert returncode == 1
    joined = "\n".join(shown)
    assert str(log_path) in joined
    assert "main.tex:12: Undefined control sequence" in joined
    assert "l.12" in joined
    # the whole transcript still reaches the log file
    assert "(./main.tex" in log_path.read_text(encoding="utf-8")


def test_failed_build_prefers_the_engine_log_for_the_excerpt(tmp_path: Path) -> None:
    engine_log = tmp_path / "build" / "main.log"
    engine_log.parent.mkdir(parents=True)
    engine_log.write_text(
        "start of run\n"
        "./sections/intro.tex:4: Missing $ inserted.\n"
        "<recently read> \\par\n"
        "l.4 a_b\n",
        encoding="utf-8",
    )
    cmd = [sys.executable, "-c", "import sys; print('Latexmk: failed'); sys.exit(12)"]
    log_path = tmp_path / "build" / "main_build.log"
    shown: list[str] = []

    returncode = run_docker_latexmk(
        cmd, log_path=log_path, engine_log_path=engine_log, on_output=shown.append
    )

    assert returncode == 12
    joined = "\n".join(shown)
    assert "sections/intro.tex:4: Missing $ inserted" in joined


def test_compile_failure_raises_a_clean_excerpt_ending_at_the_source_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_artifact(tmp_path, "paper", {"main.tex": "x\n"})
    engine_log = tmp_path / "parla" / ".parla" / "build" / "paper" / "main.log"
    engine_log.parent.mkdir(parents=True)
    engine_log.write_text(
        "./artifacts/paper/main.tex:2: Undefined control sequence.\n"
        "<recently read> \\par\n"
        "l.2 \\bogus\n"
        "        \n"
        "Here is how much of LuaTeX's memory you used:\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        build_mod, "docker_command", lambda *a, **k: [sys.executable, "-c", "import sys; sys.exit(12)"]
    )

    with pytest.raises(build_mod.BuildError) as raised:
        build_mod.compile_entrypoint(
            tmp_path, _cfg(), engine="lualatex", entrypoint="artifacts/paper/main.tex",
            outdir=".parla/build/paper", log_name="paper",
        )

    lines = str(raised.value).splitlines()
    assert lines[0].startswith("build failed (exit 12) -- full log at ")
    assert lines[1:] == ["./artifacts/paper/main.tex:2: Undefined control sequence.", "<recently read> \\par", "l.2 \\bogus"]


def test_silent_on_output_still_writes_the_log(tmp_path: Path) -> None:
    cmd = [sys.executable, "-c", "print('anything')"]
    log_path = tmp_path / "build" / "main_build.log"

    returncode = run_docker_latexmk(cmd, log_path=log_path, on_output=lambda _line: None)

    assert returncode == 0
    assert "anything" in log_path.read_text(encoding="utf-8")


def test_returns_nonzero_exit_code(tmp_path: Path) -> None:
    cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]
    log_path = tmp_path / "build" / "main_build.log"

    returncode = run_docker_latexmk(cmd, log_path=log_path, on_output=lambda _line: None)

    assert returncode == 1


# --- source link mounts, build(), docker_command ----------------------------------------


def _cfg() -> config_mod.Config:
    return config_mod.Config(
        version=1,
        image="custom/nonexistent:1",  # != image_mod.IMAGE_REF, so build() skips ensure_image
        texmf="texmf",
        links={},
    )


def test_source_link_mounts_nested_file_and_directory_symlinks(tmp_path: Path) -> None:
    sources = tmp_path / "parla" / "sources"
    sources.mkdir(parents=True)
    file_target = tmp_path / "reports" / "plot.png"
    file_target.parent.mkdir(parents=True)
    file_target.write_bytes(b"png")
    dir_target = tmp_path / "bib-store"
    dir_target.mkdir()

    (sources / "fig").mkdir()
    (sources / "fig" / "plot.png").symlink_to(file_target)
    (sources / "bib").symlink_to(dir_target)

    joined = " ".join(build_mod._source_link_mounts(tmp_path))

    assert f"{file_target.resolve()}:/workspace/parla/sources/fig/plot.png:ro" in joined
    assert f"{dir_target.resolve()}:/workspace/parla/sources/bib:ro" in joined


def test_source_link_mounts_dangling_link_raises(tmp_path: Path) -> None:
    sources = tmp_path / "parla" / "sources"
    sources.mkdir(parents=True)
    (sources / "ghost").symlink_to(tmp_path / "does-not-exist")

    with pytest.raises(BuildError, match="source link is missing"):
        build_mod._source_link_mounts(tmp_path)


def test_build_returns_build_result_and_publishes_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_artifact(tmp_path, "paper", {"main.tex": "\\documentclass{article}\\begin{document}\\end{document}\n"})
    cfg = _cfg()

    def fake_run_docker_latexmk(cmd, *, log_path, engine_log_path=None, on_output=print):
        pdf_path = engine_log_path.with_suffix(".pdf")
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.4")
        return 0

    monkeypatch.setattr(build_mod, "run_docker_latexmk", fake_run_docker_latexmk)

    result = build_mod.build(tmp_path, cfg, "paper")

    assert isinstance(result, build_mod.BuildResult)
    assert result.pdf == tmp_path / "parla" / ".parla" / "build" / "paper" / "main.pdf"
    assert result.aux == result.pdf.with_suffix(".aux")
    assert result.published_pdf == tmp_path / "parla" / "artifacts" / "paper" / "paper.pdf"
    assert result.published_pdf.read_bytes() == b"%PDF-1.4"


def test_docker_command_ends_with_outdir_and_entrypoint(tmp_path: Path) -> None:
    cfg = _cfg()

    cmd = docker_command(
        tmp_path, cfg, engine="lualatex", entrypoint="main.tex", outdir=".parla/build/paper"
    )

    assert cmd[-2:] == ["-outdir=.parla/build/paper", "main.tex"]


def test_build_with_a_baseline_publishes_the_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_artifact(tmp_path, "paper", {"main.tex": "x"})
    monkeypatch.setattr(
        build_mod,
        "run_docker_latexmk",
        lambda cmd, *, log_path, engine_log_path=None, on_output=print: (
            engine_log_path.with_suffix(".pdf").parent.mkdir(parents=True, exist_ok=True),
            engine_log_path.with_suffix(".pdf").write_bytes(b"%PDF"),
            0,
        )[-1],
    )
    seen = []
    from parla.engines.latex import diff as diff_mod

    monkeypatch.setattr(diff_mod, "render_diff", lambda root, cfg, name, baseline, doc=None, on_output=print: seen.append(baseline) or Path("d.pdf"))

    result = build_mod.build(tmp_path, _cfg(), "paper", baseline=tmp_path / "base")

    assert seen == [tmp_path / "base"] and result.diff_pdf == Path("d.pdf")
    assert build_mod.build(tmp_path, _cfg(), "paper").diff_pdf is None
