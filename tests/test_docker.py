"""Builds through the real container. Skipped unless the image exists: `parla image build`."""
from __future__ import annotations

import pytest

from parla import cli, router, template
from parla.engines.latex import image
from parla.tools import formula

pytestmark = pytest.mark.docker

try:
    HAVE_IMAGE = image.image_exists()
except image.ImageError:
    HAVE_IMAGE = False


@pytest.fixture
def project(tmp_path, monkeypatch):
    if not HAVE_IMAGE:
        pytest.skip(f"{image.IMAGE_REF} is not built")
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "no-config.toml"))
    monkeypatch.setenv("PARLA_NO_AUTO_BUILD", "1")
    root = tmp_path / "proj"
    root.mkdir()
    template.init(root)
    monkeypatch.chdir(root)
    return root


def test_a_stock_paper_builds_and_measures_its_body(project, monkeypatch):
    from conftest import PUBLIC_GUIDES  # noqa: F401  (the autouse fixture points the guides at the fixtures)

    assert cli.main(["init", "artifact", "p", "--modality", "paper", "--audience", "linkedin"]) == 0
    assert cli.main(["build", "p"]) == 0
    assert (project / "parla/artifacts/p/p.pdf").is_file()
    pages = router.pages(project, "p")
    assert pages.total >= 1 and pages.body == 1


def test_a_stock_cv_builds_on_one_page(project):
    assert cli.main(["init", "artifact", "c", "--modality", "cv", "--audience", "ai-rd"]) == 0
    base = project / "parla/artifacts/c/section"
    (base / "header.tex").write_text("\\begin{center}{\\LARGE\\bfseries Ada Lovelace}\\par ada@example.org\\end{center}\n")
    (base / "experience.tex").write_text(
        "\\section{Experience}\n\\begin{itemize}\n\\item Cut latency 30\\%.\n\\end{itemize}\n"
    )
    assert cli.main(["build", "c"]) == 0
    pages = router.pages(project, "c")
    assert pages.total == 1 and pages.body == 1


def test_an_svg_diagram_renders_pdf_and_png(project):
    assert cli.main(["init", "artifact", "d", "--modality", "diagram", "--audience", "icra"]) == 0
    svg = project / "parla/artifacts/d/d.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 120" font-family="Latin Modern Sans">'
        '<rect x="10" y="10" width="200" height="50" fill="#fff" stroke="#000"/>'
        '<text x="20" y="40" font-size="15">hello</text></svg>'
    )
    assert cli.main(["build", "d"]) == 0
    assert (project / "parla/artifacts/d/d.pdf").is_file() and (project / "parla/artifacts/d/d.png").is_file()


def test_a_formula_renders_to_a_png(project):
    assert cli.main(["init", "artifact", "p", "--modality", "paper", "--audience", "linkedin"]) == 0
    path, width, height = formula.render(project, "p", "x^2 + y^2", display=False)
    assert path.is_file() and width > 0 and height > 0
