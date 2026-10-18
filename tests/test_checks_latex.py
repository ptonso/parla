"""The LaTeX check set and the shared checks: one case per id, plus a clean artifact."""
from __future__ import annotations

from pathlib import Path

import pytest
from conftest import make_artifact

from parla import config, router, template
from parla.checks import shared
from parla.checks.ids import SEVERITY
from parla.engines.latex import checks as latex_checks

LIB = """\
@article{alpha2020,
  author = {Alpha, A. and Beta, B.},
  title = {Alpha},
  year = {2020}
}

@article{bad2021,
  author = {family=Smith, given=John},
  title = {Bad},
  year = {2021}
}

@article{commas2022,
  author = {Smith, Jr., John, III},
  title = {Commas},
  year = {2022}
}
"""

MAIN = (
    "\\documentclass{article}\n\\usepackage{graphicx}\n\\usepackage{project}\n\\begin{document}\n"
    "\\input{artifacts/paper/section/introduction}\n\\end{document}\n"
)


@pytest.fixture
def lib(tmp_path, monkeypatch):
    path = tmp_path / "library.bib"
    path.write_text(LIB, encoding="utf-8")
    monkeypatch.setattr(config, "library_bib", lambda: path)
    monkeypatch.setattr(config, "library_json", lambda: None)
    monkeypatch.setattr(config, "texmf_home", lambda: None)


def _project(tmp_path: Path, body: str, main: str = MAIN, **extra: str) -> Path:
    template.init(tmp_path)
    make_artifact(tmp_path, "paper", {"main.tex": main, "section/introduction.tex": body, **extra})
    return tmp_path


def _ids(root: Path) -> list[tuple[str, str, int]]:
    return [(f.id, f.file, f.line) for f in router.check(root, "paper")]


def _only(root: Path, check_id: str) -> list[tuple[str, int]]:
    return [(f.file, f.line) for f in router.check(root, "paper") if f.id == check_id]


INTRO = "artifacts/paper/section/introduction.tex"


def test_a_clean_artifact_has_no_findings(tmp_path, lib):
    root = _project(
        tmp_path,
        "\\section{Intro}\\label{sec:intro}\n"
        "See \\ref{sec:intro} and \\cite{alpha2020}. Figure \\ref{fig:a} shows it.\n"
        "\\begin{figure}\\includegraphics{sources/fig/a.png}\\caption{A}\\label{fig:a}\\end{figure}\n",
    )
    (root / "parla/sources/fig").mkdir(parents=True)
    (root / "parla/sources/fig/a.png").write_bytes(b"x")
    assert router.check(root, "paper") == []


def test_every_check_id_has_a_severity_and_the_ignore_list_validates_ids(tmp_path):
    assert SEVERITY["cite-unresolved"] == "error" and SEVERITY["todo-marker"] == "warning"
    template.init(tmp_path)
    toml = tmp_path / "parla/parla.toml"
    toml.write_text(toml.read_text() + '\n[checks]\nignore = ["nope"]\n')
    with pytest.raises(config.ConfigError, match="no known check: nope"):
        config.load(tmp_path)


def test_cite_unresolved_and_bib_name_syntax(tmp_path, lib):
    root = _project(tmp_path, "\\cite{alpha2020}\n\\cite{ghost1999}\n\\cite{bad2021}\n\\cite{commas2022}\n")
    found = {f.id: f for f in router.check(root, "paper")}
    assert found["cite-unresolved"].line == 2 and "ghost1999" in found["cite-unresolved"].message
    assert found["cite-unresolved"].severity == "error"
    bad = [f for f in router.check(root, "paper") if f.id == "bib-name-syntax"]
    assert sorted(f.line for f in bad) == [3, 4]


def test_cite_extras_resolve_and_commented_cites_are_ignored(tmp_path, lib):
    root = _project(tmp_path, "% \\cite{ghost}\n\\cite{local2019}\n")
    (root / "parla/sources/bib/hand.bib").write_text("@misc{local2019, title={Local}}\n")
    assert _only(root, "cite-unresolved") == []


def test_figure_missing_for_inputs_and_figures_but_not_sources_or_bare_names(tmp_path, lib):
    root = _project(
        tmp_path,
        "\\includegraphics{artifacts/paper/figs/ghost.png}\n"
        "\\input{artifacts/paper/table/ghost}\n"
        "\\includegraphics{sources/fig/ghost.png}\n"
        "\\input{slides-macros.tex}\n"
        "\\includegraphics{artifacts/paper/figs/there}\n",
    )
    (root / "parla/artifacts/paper/figs").mkdir()
    (root / "parla/artifacts/paper/figs/there.png").write_bytes(b"x")
    assert _only(root, "figure-missing") == [(INTRO, 1), (INTRO, 2)]
    assert _only(root, "source-missing") == [(INTRO, 3)]


def test_source_missing_scans_every_artifact_text_file_but_not_comments_or_the_card(tmp_path, lib):
    root = _project(tmp_path, "% \\includegraphics{sources/ghost.png}\n", **{"notes.md": "see sources/results/x.csv.\n"})
    card = root / "parla/artifacts/paper/card.md"
    card.write_text(card.read_text() + "\nmentions sources/in/card.png\n")
    assert _only(root, "source-missing") == [("artifacts/paper/notes.md", 1)]
    (root / "parla/sources/results").mkdir()
    (root / "parla/sources/results/x.csv").write_text("a")
    assert _only(root, "source-missing") == []


def test_unescaped_underscore_and_percent(tmp_path, lib):
    root = _project(
        tmp_path,
        "a snake_case word\n$x_i$ and \\ref{fig_a} and \\label{fig_a}\nescaped \\_ fine\nit gained 85% accuracy here\n"
        "a trailing 5%\n",
    )
    assert _only(root, "unescaped-char") == [(INTRO, 1), (INTRO, 4)]


def test_brace_unbalanced(tmp_path, lib):
    root = _project(tmp_path, "\\cite{alpha2020}}\n")
    assert _only(root, "brace-unbalanced") == [(INTRO, 1)]
    (root / "parla" / INTRO).write_text("\\textbf{open\n")
    assert _only(root, "brace-unbalanced") == [(INTRO, 1)]
    (root / "parla" / INTRO).write_text("literal \\{ and \\} braces\n")
    assert _only(root, "brace-unbalanced") == []


def test_macro_missing_until_a_loaded_package_defines_it(tmp_path, lib, monkeypatch):
    root = _project(tmp_path, "\\SplashSlide{x}\n")
    assert _only(root, "macro-missing") == [(INTRO, 1)]
    home = tmp_path / "home"
    home.mkdir()
    (home / "slides-macros.tex").write_text("\\NewDocumentCommand{\\SplashSlide}{ O{} m g }{}")
    (home / "image-slides.sty").write_text("\\input{slides-macros}")
    monkeypatch.setattr(config, "texmf_home", lambda: home)
    assert _only(root, "macro-missing") == [(INTRO, 1)]  # on the search path, never loaded
    main = root / "parla/artifacts/paper/main.tex"
    main.write_text(main.read_text().replace("\\usepackage{graphicx}", "\\usepackage{image-slides}"))
    assert _only(root, "macro-missing") == []


def test_entrypoints_load_slide_macros_transitively(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "slides-macros.tex").write_text("\\NewDocumentCommand{\\SplashSlide}{ O{} m g }{}")
    (home / "image-slides.sty").write_text("\\input{slides-macros}")
    main = tmp_path / "main.tex"
    main.write_text("\\usepackage{image-slides}")
    assert latex_checks.entrypoints_load_slide_macros([main], [tmp_path, home])
    main.write_text("\\usepackage{graphicx}")
    assert not latex_checks.entrypoints_load_slide_macros([main], [tmp_path, home])


def test_ref_dangling(tmp_path, lib):
    root = _project(tmp_path, "See~\\ref{fig:missing}. \\label{fig:present}\n\\eqref{fig:present}\n")
    assert _only(root, "ref-dangling") == [(INTRO, 1)]
    (root / "parla" / INTRO).write_text("\\label{sec:a} \\ref{sec:a}\n")
    assert _only(root, "ref-dangling") == []


def test_figure_duplicate(tmp_path, lib):
    root = _project(tmp_path, "\\includegraphics{sources/a.png}\n\\includegraphics[width=1in]{sources/a.png}\n\\includegraphics{sources/b.png}\n")
    assert _only(root, "figure-duplicate") == [(INTRO, 2)]


def test_todo_marker_is_read_from_the_comment(tmp_path, lib):
    root = _project(tmp_path, "prose [?]%TODO: add the ghost1999 citation\nno marker \\cite{alpha2020}\n")
    found = [f for f in router.check(root, "paper") if f.id == "todo-marker"]
    assert [(f.line, f.severity) for f in found] == [(1, "warning")]
    assert "ghost1999" in found[0].message


def test_abbreviation_repeated(tmp_path, lib):
    root = _project(tmp_path, "Out of distribution (OOD) samples\nlater, out of distribution (OOD) again\nonce (ABC)\n")
    assert _only(root, "abbreviation-repeated") == [(INTRO, 2)]


def test_float_unreferenced_and_float_order(tmp_path, lib):
    body = (
        "\\begin{figure}\\caption{A}\\label{fig:early}\\end{figure}\n"
        "Text with Figure~\\ref{fig:early} after it.\n"
        "\\begin{figure}\\caption{B}\\label{fig:orphan}\\end{figure}\n"
        "Table~\\ref{tab:ok}.\n\\begin{table}\\caption{T}\\label{tab:ok}\\end{table}\n"
    )
    root = _project(tmp_path, body)
    assert _only(root, "float-order") == [(INTRO, 1)]
    assert _only(root, "float-unreferenced") == [(INTRO, 3)]


def test_cite_style(tmp_path, lib):
    root = _project(tmp_path, "as shown (\\,\\cite{alpha2020}) and Figure ef{fig:a}\nplain \\cite{alpha2020} and Figure~\\ref{fig:a}\n")
    assert [line for _, line in _only(root, "cite-style")] == [1]


def test_appendix_structure(tmp_path, lib):
    main = MAIN.replace(
        "\\end{document}",
        "\\appendix\n\\input{artifacts/paper/section/app-ok}\n\\input{artifacts/paper/section/app-deep}\n\\end{document}",
    )
    root = _project(
        tmp_path, "\\appendix\n\\section{Intro}\n", main,
        **{"section/app-ok.tex": "\\section{A}\n\\subsection{B}\n", "section/app-deep.tex": "\\subsection{B}\n"},
    )
    assert _only(root, "appendix-structure") == [("artifacts/paper/section/app-deep.tex", 1), (INTRO, 1)]


def test_card_invalid_is_a_finding_and_blocks_a_build(tmp_path, lib, capsys):
    root = _project(tmp_path, "x\n")
    card = root / "parla/artifacts/paper/card.md"
    card.write_text(card.read_text().replace("phase: drafting\n", ""))
    found = router.check(root, "paper")
    assert [(f.id, f.severity, f.file) for f in found] == [("card-invalid", "error", "artifacts/paper/card.md")]
    from parla.checks import CheckFailed

    with pytest.raises(CheckFailed):
        router.build(root, "paper", on_output=lambda _l: None)
    assert shared.card_invalid(root, "ghost") is None


def test_ignored_ids_do_not_report(tmp_path, lib):
    root = _project(tmp_path, "%TODO: later\n")
    assert _only(root, "todo-marker") == [(INTRO, 1)]
    toml = root / "parla/parla.toml"
    toml.write_text(toml.read_text() + '\n[checks]\nignore = ["todo-marker"]\n')
    assert _only(root, "todo-marker") == []


def test_check_writes_nothing(tmp_path, lib):
    root = _project(tmp_path, "\\cite{alpha2020}\n")
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    router.check(root, "paper")
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) == before
