"""The SVG engine: one case per check id on small SVGs, a clean generated diagram, and the build
with the container stubbed."""
from __future__ import annotations

from pathlib import Path

import pytest
from conftest import make_artifact

from parla import cli, router, template
from parla.engines import registry
from parla.engines.base import BuildError
from parla.engines.svg import build as svg_build
from parla.engines.svg import checks, fonts

FIXTURES = Path(__file__).parent / "fixtures" / "svg"
HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 120" font-family="Latin Modern Sans">\n'
BOX = '<rect x="10" y="10" width="140" height="40" fill="#fff" stroke="#000"/>\n'


def _scan(body: str, base: Path = Path("/nonexistent"), head: str = HEAD) -> list[tuple[str, int]]:
    scene = checks.collect(checks.parse(head + body + "</svg>\n"))
    return [(f.id, f.line) for f in checks.check_scene(scene, "d.svg", base)]


def test_a_well_formed_diagram_is_clean():
    assert _scan(BOX + '<text x="20" y="35" font-size="15">Photo and boxes</text>\n') == []


def test_the_generated_knn_diagram_is_clean():
    scene = checks.collect(checks.parse((FIXTURES / "knn-graph.svg").read_text()))
    assert (len(scene.texts), len(scene.arrows), len(scene.images)) == (62, 4, 2)
    assert checks.check_scene(scene, "knn.svg", Path("/nonexistent")) == []


def test_overflow_from_its_box_and_from_the_canvas():
    assert _scan(BOX + '<text x="20" y="35" font-size="15">a label much wider than its small box</text>\n') == [("svg-overflow", 3)]
    assert _scan('<text x="250" y="60" font-size="15">leaves the canvas</text>\n') == [("svg-overflow", 2)]


def test_text_width_uses_the_font_metrics():
    narrow, wide = fonts.text_width("iiii", "sans", False, False, 15), fonts.text_width("MMMM", "sans", False, False, 15)
    assert 0 < narrow < wide
    assert fonts.text_width("abc", "sans", True, False, 15) > fonts.text_width("abc", "sans", False, False, 15)


def test_text_anchor_and_tspan_lines_set_the_extent():
    centered = '<text x="80" y="35" font-size="15" text-anchor="middle">centered</text>\n'
    assert _scan(BOX + centered) == []
    wrapped = '<text x="20" y="30" font-size="15">one <tspan x="20" dy="15">two</tspan></text>\n'
    assert _scan(BOX + wrapped) == []


def test_collision_between_texts_and_with_a_shape():
    assert _scan('<text x="20" y="40" font-size="15">first</text><text x="22" y="44" font-size="15">second</text>\n') == [("svg-collision", 2)]
    ids = {i for i, _ in _scan('<rect x="10" y="10" width="60" height="30"/>\n<text x="50" y="80" font-size="15">sticks out</text><rect x="60" y="70" width="10" height="20"/>\n')}
    assert "svg-collision" in ids


def test_adjacent_wrapped_lines_do_not_collide():
    lines = "".join(f'<text x="20" y="{30 + 18.75 * i}" font-size="15">line {i}</text>\n' for i in range(3))
    assert _scan(lines) == []


def test_arrow_crossing_a_shape_that_is_neither_end():
    marker = '<defs><marker id="a" markerWidth="10" markerHeight="10"><path d="M0,0 L10,5 L0,10 Z"/></marker></defs>\n'
    boxes = '<rect x="10" y="40" width="40" height="40"/><rect x="120" y="40" width="40" height="40"/>\n'
    arrow = '<path d="M50,60 L120,60" marker-end="url(#a)"/>\n'
    assert _scan(marker + boxes + arrow) == []
    middle = '<rect x="75" y="55" width="20" height="40"/>\n'
    assert _scan(marker + boxes + middle + arrow) == [("svg-arrow-crossing", 5)]
    big = '<rect x="55" y="20" width="60" height="80"/>\n'
    assert _scan(marker + boxes + big + arrow) == [("svg-arrow-crossing", 5)]  # centred on the arrow, but not a badge
    badge = '<circle cx="85" cy="60" r="9"/>\n'
    assert _scan(marker + boxes + badge + arrow) == []  # a badge centred on the arrow is its label


def test_glyph_missing_and_math_in_text():
    assert _scan('<text x="20" y="30" font-size="15">kanji \u6f22 here</text>\n') == [("svg-glyph-missing", 2)]
    assert _scan('<text x="20" y="30" font-size="15">cost is $x^2$</text>\n') == [("svg-math-in-text", 2)]


def test_href_missing_only_for_paths_outside_sources(tmp_path):
    (tmp_path / "artifacts/a").mkdir(parents=True)
    (tmp_path / "artifacts/a/there.png").write_bytes(b"x")
    body = (
        '<image href="artifacts/a/there.png" x="0" y="0" width="10" height="10"/>\n'
        '<image href="artifacts/a/ghost.png" x="20" y="0" width="10" height="10"/>\n'
        '<image href="sources/ghost.png" x="40" y="0" width="10" height="10"/>\n'
        '<image href="data:image/png;base64,AAAA" x="60" y="0" width="10" height="10"/>\n'
    )
    assert _scan(body, tmp_path) == [("svg-href-missing", 3)]


def test_unsupported_elements_transforms_and_commands_warn_and_are_skipped():
    found = _scan(
        '<use href="#x"/>\n<g transform="rotate(30)"><rect x="0" y="0" width="900" height="900"/></g>\n'
        '<path d="M0,0 C10,10 20,20 30,30"/>\n<g transform="translate(10,10)"><text x="0" y="20" font-size="15">ok</text></g>\n'
    )
    assert found == [("svg-unsupported", 2), ("svg-unsupported", 3), ("svg-unsupported", 4)]


def test_parse_rejects_malformed_xml_with_its_line():
    with pytest.raises(ValueError) as exc:
        checks.parse("<svg>\n<g></svg>")
    assert exc.value.args[1] == 2


def test_a_bad_file_gives_svg_malformed(tmp_path):
    make_artifact(tmp_path, "a", {"a.svg": HEAD + "<rect>\n</svg>\n"})
    (tmp_path / "parla").mkdir(exist_ok=True)
    found = checks.check(tmp_path, "a", "a.svg")
    assert [(f.id, f.severity, f.file) for f in found] == [("svg-malformed", "error", "artifacts/a/a.svg")]
    assert found[0].line == 3


# --- the engine --------------------------------------------------------------------------


def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "no-config.toml"))
    monkeypatch.setenv("PARLA_NO_AUTO_BUILD", "1")
    root = tmp_path / "proj"
    root.mkdir()
    template.init(root)
    monkeypatch.chdir(root)
    assert cli.main(["init", "artifact", "knn", "--modality", "diagram", "--audience", "icra"]) == 0
    return root


def test_the_starter_writes_an_empty_canvas_and_a_valid_card(tmp_path, monkeypatch):
    root = _project(tmp_path, monkeypatch)
    svg = root / "parla/artifacts/knn/knn.svg"
    assert 'viewBox="0 0 800 450"' in svg.read_text()
    assert "engine: svg" in (root / "parla/artifacts/knn/card.md").read_text()
    assert router.check(root, "knn") == []


def test_check_errors_stop_the_build_before_any_render(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path, monkeypatch)
    (root / "parla/artifacts/knn/knn.svg").write_text(HEAD + '<text x="290" y="60" font-size="15">too far right</text>\n</svg>\n')
    monkeypatch.setattr(svg_build.subprocess, "run", lambda *a, **k: pytest.fail("rendered"))
    assert cli.main(["build", "knn"]) == 1
    assert "knn.svg:2: error svg-overflow" in capsys.readouterr().out.replace("artifacts/knn/", "")


class _Run:
    def __init__(self, calls):
        self.calls = calls

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        out = Path(cmd[cmd.index("-o") + 1])
        target = Path.cwd() / "parla" / out
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + (30).to_bytes(4, "big") + (20).to_bytes(4, "big") + b"\x00" * 8)

        class R:
            returncode, stdout, stderr = 0, "", ""

        return R()


def test_build_renders_pdf_png_and_the_side_by_side_diff(tmp_path, monkeypatch):
    root = _project(tmp_path, monkeypatch)
    svg = root / "parla/artifacts/knn/knn.svg"
    svg.write_text(HEAD + BOX + "</svg>\n")
    from parla import jobs

    jobs.start(root, "knn")
    svg.write_text(HEAD + BOX + '<text x="20" y="35" font-size="15">new</text></svg>\n')
    calls: list[list[str]] = []
    monkeypatch.setattr(svg_build.subprocess, "run", _Run(calls))

    built = router.build(root, "knn", on_output=lambda _l: None)

    out = root / "parla/artifacts/knn"
    assert built.published == (out / "knn.pdf", out / "knn.png") and built.diff == out / "knn_diff.png"
    assert all("rsvg-convert" in c and c[0] == "docker" for c in calls)
    assert [c[c.index("-f") + 1] for c in calls] == ["pdf", "png", "png", "png"]
    wrapper = (root / "parla/.parla/build/knn_diff/diff.svg").read_text()
    assert 'viewBox="0 0 80 20"' in wrapper and 'href="old.png"' in wrapper and 'href="new.png"' in wrapper
    assert not list((root / "parla").glob(".render-*"))  # the temporary copies are gone


def test_a_failed_render_is_a_build_error_with_the_message(tmp_path, monkeypatch):
    root = _project(tmp_path, monkeypatch)

    class Fail:
        returncode, stdout, stderr = 1, "", "bad svg"

    monkeypatch.setattr(svg_build.subprocess, "run", lambda *a, **k: Fail())
    with pytest.raises(BuildError, match="error compile-error: rsvg-convert failed: bad svg"):
        router.build(root, "knn", on_output=lambda _l: None)
    assert not list((root / "parla").glob(".render-*"))


def test_export_copies_the_svg_its_images_and_the_renders(tmp_path, monkeypatch):
    root = _project(tmp_path, monkeypatch)
    (root / "parla/sources/fig").mkdir(parents=True, exist_ok=True)
    (root / "parla/sources/fig/a.png").write_bytes(b"png")
    (root / "parla/artifacts/knn/knn.svg").write_text(
        HEAD + '<image href="sources/fig/a.png" x="0" y="0" width="10" height="10"/></svg>\n'
    )
    monkeypatch.setattr(svg_build.subprocess, "run", _Run([]))

    out = router.export(root, "knn", "v1", False)

    assert (out / "artifacts/knn/knn.svg").is_file() and (out / "sources/fig/a.png").read_bytes() == b"png"
    assert (out / "knn.pdf").is_file() and (out / "knn.png").is_file()
    assert registry.ENGINES["svg"].pages(root, "knn") is None
