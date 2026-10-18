from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import make_artifact
from parla import config
from parla.engines.latex import build, export

_FIXED_NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)


def _config() -> config.Config:
    return config.Config(
        version=1,
        image="ghcr.io/example/texlive:2026.1",
        texmf="texmf",
        links={},
    )


MAIN = (
    "\\documentclass{article}\n"
    "\\usepackage{graphicx}\n"
    "\\usepackage{project}\n"
    "\\begin{document}\n"
    "\\input{artifacts/paper/section/introduction}\n"
    "% \\input{artifacts/paper/section/commented-out}\n"
    "\\includegraphics{sources/fig/plot}\n"
    "% \\includegraphics{sources/fig/should-not-exist}\n"
    "\\bibliography{artifacts/paper/references}\n"
    "\\end{document}\n"
)


def _project(tmp_path: Path, *, texmf: bool = False) -> Path:
    base = tmp_path / "parla"
    (base / "sources" / "fig").mkdir(parents=True)
    make_artifact(
        tmp_path,
        "paper",
        {"main.tex": MAIN, "section/introduction.tex": "\\section{Intro}\n", "references.bib": "% refs\n"},
    )
    (base / "sources" / "fig" / "plot.png").write_bytes(b"png-bytes")
    if texmf:
        sty_dir = base / "texmf" / "tex" / "latex" / "project"
        sty_dir.mkdir(parents=True)
        (sty_dir / "project.sty").write_text("\\ProvidesPackage{project}\n", encoding="utf-8")
    return tmp_path


def _main(root: Path) -> Path:
    return root / "parla" / "artifacts" / "paper" / "main.tex"


def _fake_build(root: Path, cfg: config.Config, name: str, doc: config.Document | None = None) -> build.BuildResult:
    doc = doc or config.document(root, name)
    pdf_dir = root / "parla" / "artifacts" / name
    pdf_path = pdf_dir / f"{doc.slug}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    return build.BuildResult(pdf=pdf_path, aux=pdf_path.with_suffix(".aux"), published_pdf=pdf_path)


@pytest.fixture(autouse=True)
def _stub_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build, "build", _fake_build)
    monkeypatch.setattr(export, "_utcnow", lambda: _FIXED_NOW)


def test_export_happy_path(tmp_path: Path) -> None:
    root = _project(tmp_path, texmf=True)
    cfg = _config()

    out_dir = export.export_document(root, cfg, "paper", "v1", force=False)

    assert out_dir == root / "parla" / "export" / "paper" / "2026-08-21_v1"
    assert (out_dir / "artifacts/paper/main.tex").is_file()
    assert (out_dir / "artifacts/paper/section/introduction.tex").is_file()
    assert (out_dir / "sources" / "fig" / "plot.png").read_bytes() == b"png-bytes"
    assert (out_dir / "artifacts/paper/references.bib").is_file()
    assert (out_dir / "texmf" / "tex" / "latex" / "project" / "project.sty").is_file()
    assert (out_dir / "latexmkrc").read_text(encoding="utf-8") == (
        "$ENV{'TEXINPUTS'} = './texmf//:' . $ENV{'TEXINPUTS'};\n"
    )
    assert (out_dir / "main.pdf").read_bytes() == b"%PDF-1.4 fake"
    assert not (out_dir / "artifacts/paper/section/commented-out.tex").exists()

    tex_config = (out_dir / "tex-config.yaml").read_text(encoding="utf-8")
    assert "docker_image: ghcr.io/example/texlive:2026.1" in tex_config
    assert "engine: lualatex" in tex_config
    assert "entrypoint: artifacts/paper/main.tex" in tex_config
    assert "packages: [article, graphicx, project]" in tex_config


def test_export_fails_for_undeclared_document(tmp_path: Path) -> None:
    root = _project(tmp_path)
    cfg = _config()

    with pytest.raises(config.ConfigError, match="has no card"):
        export.export_document(root, cfg, "slides", "v1", force=False)


def test_export_fails_without_force_on_existing_tag(tmp_path: Path) -> None:
    root = _project(tmp_path)
    cfg = _config()
    export.export_document(root, cfg, "paper", "v1", force=False)

    with pytest.raises(export.ExportError, match="rerun with --force"):
        export.export_document(root, cfg, "paper", "v1", force=False)


def test_export_force_overwrites_existing_tag(tmp_path: Path) -> None:
    root = _project(tmp_path)
    cfg = _config()
    export.export_document(root, cfg, "paper", "v1", force=False)
    (root / "parla" / "export" / "paper" / "2026-08-21_v1" / "stale.txt").write_text(
        "stale", encoding="utf-8"
    )

    out_dir = export.export_document(root, cfg, "paper", "v1", force=True)

    assert not (out_dir / "stale.txt").exists()
    assert (out_dir / "artifacts/paper/main.tex").is_file()


def test_export_hardcopies_symlinked_figure(tmp_path: Path) -> None:
    root = _project(tmp_path)
    external = tmp_path / "external-store"
    external.mkdir()
    external_plot = external / "plot.png"
    external_plot.write_bytes(b"external-bytes")
    (root / "parla" / "sources" / "fig" / "plot.png").unlink()
    (root / "parla" / "sources" / "fig" / "plot.png").symlink_to(external_plot)
    cfg = _config()

    out_dir = export.export_document(root, cfg, "paper", "v1", force=False)

    exported_plot = out_dir / "sources" / "fig" / "plot.png"
    assert exported_plot.read_bytes() == b"external-bytes"
    assert not exported_plot.is_symlink()


def test_export_normalizes_tag_to_lowercase_kebab_case(tmp_path: Path) -> None:
    root = _project(tmp_path)
    cfg = _config()

    out_dir = export.export_document(root, cfg, "paper", "Arxiv Submission_V2!!", force=False)

    assert out_dir == root / "parla" / "export" / "paper" / "2026-08-21_arxiv-submission-v2"


def test_export_rejects_tag_with_no_alphanumeric_characters(tmp_path: Path) -> None:
    root = _project(tmp_path)
    cfg = _config()

    with pytest.raises(export.ExportError, match="--tag must contain at least one"):
        export.export_document(root, cfg, "paper", "!!!", force=False)


def _stub_layer2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    layer2_dir = tmp_path / "layer2-texmf"
    (layer2_dir / "tex" / "latex" / "tonso").mkdir(parents=True)
    monkeypatch.setattr(export, "_layer2_root", lambda: layer2_dir)
    return layer2_dir / "tex" / "latex" / "tonso"


def test_export_resolves_bare_input_from_layer2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    shared_dir = _stub_layer2(monkeypatch, tmp_path)
    (shared_dir / "slides-macros.tex").write_text(
        "\\newcommand{\\DiagramSlide}[1]{\\input{#1}}\n", encoding="utf-8"
    )
    _main(root).write_text(
        "\\documentclass{article}\n\\input{slides-macros.tex}\n\\begin{document}\\end{document}\n",
        encoding="utf-8",
    )
    cfg = _config()

    out_dir = export.export_document(root, cfg, "paper", "v1", force=False)

    assert (out_dir / "slides-macros.tex").is_file()
    tex_config = (out_dir / "tex-config.yaml").read_text(encoding="utf-8")
    assert "bundled_shared_files: [slides-macros.tex]" in tex_config


def test_export_resolves_usepackage_from_layer2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    shared_dir = _stub_layer2(monkeypatch, tmp_path)
    (shared_dir / "beamerthemeScience.sty").write_text(
        "\\ProvidesPackage{beamerthemeScience}\n", encoding="utf-8"
    )
    _main(root).write_text(
        "\\documentclass{article}\n\\usepackage{beamerthemeScience}\n\\begin{document}\\end{document}\n",
        encoding="utf-8",
    )
    cfg = _config()

    out_dir = export.export_document(root, cfg, "paper", "v1", force=False)

    assert (out_dir / "beamerthemeScience.sty").read_text(encoding="utf-8") == (
        "\\ProvidesPackage{beamerthemeScience}\n"
    )


def test_export_layer2_fallback_requires_bare_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    shared_dir = _stub_layer2(monkeypatch, tmp_path)
    (shared_dir / "slides-macros.tex").write_text("dummy", encoding="utf-8")
    _main(root).write_text(
        "\\input{macros/slides-macros}\n", encoding="utf-8"
    )
    cfg = _config()

    with pytest.raises(export.ExportError, match="referenced tex file is missing"):
        export.trace_dependencies(root, config.document(root, "paper"), cfg.texmf)


def test_export_traces_slide_image_macros(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "parla" / "sources" / "fig" / "left.png").write_bytes(b"left-bytes")
    (root / "parla" / "sources" / "fig" / "top.jpg").write_bytes(b"top-bytes")
    (root / "parla" / "artifacts" / "paper" / "slide").mkdir(parents=True)
    (root / "parla" / "artifacts" / "paper" / "slide" / "001.tex").write_text(
        "\\LeftImage{sources/fig/left}[caption]\n\\TopImage{sources/fig/top}\n", encoding="utf-8"
    )
    _main(root).write_text(
        "\\documentclass{beamer}\n\\input{artifacts/paper/slide/001}\n\\begin{document}\\end{document}\n",
        encoding="utf-8",
    )
    cfg = _config()

    out_dir = export.export_document(root, cfg, "paper", "v1", force=False)

    assert (out_dir / "sources" / "fig" / "left.png").read_bytes() == b"left-bytes"
    assert (out_dir / "sources" / "fig" / "top.jpg").read_bytes() == b"top-bytes"


def test_export_traces_diagram_slide_as_input(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "parla" / "artifacts" / "diagram").mkdir(parents=True)
    (root / "parla" / "artifacts" / "diagram" / "flow.tex").write_text(
        "\\begin{tikzpicture}\\end{tikzpicture}\n", encoding="utf-8"
    )
    _main(root).write_text(
        "\\documentclass{beamer}\n\\DiagramSlide{artifacts/diagram/flow}[caption]\n"
        "\\begin{document}\\end{document}\n",
        encoding="utf-8",
    )
    cfg = _config()

    out_dir = export.export_document(root, cfg, "paper", "v1", force=False)

    assert (out_dir / "artifacts" / "diagram" / "flow.tex").is_file()


def test_trace_dependencies_missing_input_fails_fast(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _main(root).write_text(
        "\\input{artifacts/paper/section/missing}\n", encoding="utf-8"
    )
    cfg = _config()

    with pytest.raises(export.ExportError, match="referenced tex file is missing"):
        export.trace_dependencies(root, config.document(root, "paper"), cfg.texmf)


def test_export_omits_latexmkrc_without_texmf(tmp_path: Path) -> None:
    root = _project(tmp_path, texmf=False)
    cfg = _config()

    out_dir = export.export_document(root, cfg, "paper", "v1", force=False)

    assert not (out_dir / "latexmkrc").exists()


def test_export_follows_personal_texmf_dependencies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    (home / "slides-macros.tex").write_text("\\RequirePackage{image-slides}\n", encoding="utf-8")
    (home / "image-slides.sty").write_text("\\ProvidesPackage{image-slides}\n", encoding="utf-8")
    packaged = tmp_path / "packaged"
    packaged.mkdir()
    monkeypatch.setattr(export, "_layer2_root", lambda: packaged)
    monkeypatch.setattr(
        export, "_layer2_index", lambda: {p.name: p for p in home.iterdir()}
    )
    _main(root).write_text(
        "\\documentclass{article}\n\\input{slides-macros.tex}\n\\begin{document}\\end{document}\n",
        encoding="utf-8",
    )

    out_dir = export.export_document(root, _config(), "paper", "v1", force=False)

    assert (out_dir / "image-slides.sty").is_file()
