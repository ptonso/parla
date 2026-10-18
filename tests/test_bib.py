from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_artifact
from parla import config
from parla.engines.latex import bib, build

_LIB = """
@article{alpha2020,
  title = {Alpha Methods},
  author = {Ada Alpha and Bo Alpha},
  year = {2020},
  doi = {10.1/alpha},
}

@inproceedings{beta2021,
  title = {Beta at Scale},
  author = {Bea Beta},
  date = {2021-06-01},
}
"""


def test_parse_bibtex_keeps_raw_and_entrytype() -> None:
    entries = bib.parse_bibtex(_LIB, source="library.bib")
    assert set(entries) == {"alpha2020", "beta2021"}
    assert entries["alpha2020"].entrytype == "article"
    assert entries["alpha2020"].fields["year"] == "2020"
    assert entries["beta2021"].fields["year"] == "2021"  # derived from date
    assert entries["alpha2020"].raw.startswith("@article{alpha2020,")
    assert entries["alpha2020"].raw.rstrip().endswith("}")


def test_parse_bibtex_missing_key_raises() -> None:
    with pytest.raises(bib.BibError):
        bib.parse_bibtex("@article{, title = {x}}", source="bad.bib")


def test_scan_cite_keys_first_seen_order_and_comment_stripping() -> None:
    tex = [
        "text \\citep[e.g.][]{beta2021, alpha2020} more \\cite{alpha2020}\n",
        "% \\cite{commented2000}\n",
        "\\textcite{gamma2022}  \\nocite{*}\n",
        "prose [?]%TODO(parla): unresolved citekey 'ghost1999' -- gone\n",
    ]
    assert bib.scan_cite_keys(tex) == ["beta2021", "alpha2020", "gamma2022"]


def _write_lib(tmp_path: Path, text: str = _LIB) -> Path:
    path = tmp_path / "library.bib"
    path.write_text(text, encoding="utf-8")
    return path


def test_resolve_library_wins_and_reports_shadow_and_unresolved(tmp_path: Path) -> None:
    library = bib.load_library(library_bib=_write_lib(tmp_path), library_json=None)
    extras = {
        "alpha2020": bib.Entry("alpha2020", "misc", {}, "@misc{alpha2020, title={WRONG}}", "x.bib"),
        "delta2019": bib.Entry("delta2019", "misc", {}, "@misc{delta2019, title={D}}", "x.bib"),
    }
    result = bib.resolve(["alpha2020", "delta2019", "ghost2000"], library=library, extras=extras)
    assert "WRONG" not in result.entries["alpha2020"].raw  # library wins
    assert result.entries["delta2019"].source == "x.bib"  # extra fills a gap
    assert result.unresolved == ["ghost2000"]
    assert result.shadowed == [("alpha2020", "x.bib")]


def test_materialize_is_idempotent(tmp_path: Path) -> None:
    library = bib.load_library(library_bib=_write_lib(tmp_path), library_json=None)
    result = bib.resolve(["alpha2020"], library=library, extras={})
    out = tmp_path / "bib" / "references.bib"

    assert bib.materialize(result, out) is True
    first_mtime = out.stat().st_mtime_ns
    assert "@article{alpha2020" in out.read_text(encoding="utf-8")
    assert "beta2021" not in out.read_text(encoding="utf-8")

    assert bib.materialize(result, out) is False
    assert out.stat().st_mtime_ns == first_mtime


def test_load_library_missing_files_is_empty(tmp_path: Path) -> None:
    library = bib.load_library(library_bib=tmp_path / "nope.bib", library_json=tmp_path / "nope.json")
    assert library.entries == {}
    assert library.zotero_meta == {}


def test_load_zotero_meta_reads_item_key_and_pdf(tmp_path: Path) -> None:
    js = tmp_path / "library.json"
    js.write_text(
        '{"items": [{"citationKey": "alpha2020", "itemKey": "ABCD1234",'
        ' "attachments": [{"path": "/pdf/alpha.pdf"}, {"path": "/notes/x.txt"}]}]}',
        encoding="utf-8",
    )
    library = bib.load_library(library_bib=None, library_json=js)
    assert library.zotero_meta["alpha2020"]["item_key"] == "ABCD1234"
    assert library.zotero_meta["alpha2020"]["attachments"] == ["/pdf/alpha.pdf"]


# --- build preflight (_regenerate_references_bib) --------------------------------------


def _doc() -> config.Document:
    return config.Document(name="paper", entrypoint="artifacts/paper/main.tex", engine="lualatex")


def _tex_project(tmp_path: Path, body: str) -> Path:
    root = tmp_path / "proj"
    (root / "parla" / "sources" / "bib").mkdir(parents=True)
    make_artifact(
        root,
        "paper",
        {
            "main.tex": "\\documentclass{article}\\begin{document}\n"
            "\\input{artifacts/paper/section/introduction}\n"
            "\\bibliography{artifacts/paper/references}\\end{document}\n",
            "section/introduction.tex": body,
        },
    )
    return root


def test_regenerate_references_bib_scopes_to_cited_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = _write_lib(tmp_path)
    monkeypatch.setattr(config, "library_bib", lambda: lib)
    monkeypatch.setattr(config, "library_json", lambda: None)
    root = _tex_project(tmp_path, "\\section{I}\\cite{alpha2020}\n")

    build._regenerate_references_bib(root, _doc(), on_output=lambda _l: None)

    generated = (root / "parla" / "artifacts" / "paper" / "references.bib").read_text(encoding="utf-8")
    assert "@article{alpha2020" in generated
    assert "beta2021" not in generated


def test_regenerate_references_bib_unresolved_user_key_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = _write_lib(tmp_path)
    monkeypatch.setattr(config, "library_bib", lambda: lib)
    monkeypatch.setattr(config, "library_json", lambda: None)
    root = _tex_project(tmp_path, "\\section{I}\\cite{ghost2000}\n")

    with pytest.raises(build.BuildError, match="ghost2000"):
        build._regenerate_references_bib(root, _doc(), on_output=lambda _l: None)


def test_regenerate_references_bib_merges_extras_library_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = _write_lib(tmp_path)
    monkeypatch.setattr(config, "library_bib", lambda: lib)
    monkeypatch.setattr(config, "library_json", lambda: None)
    root = _tex_project(tmp_path, "\\section{I}\\cite{alpha2020}\\cite{local2019}\n")
    (root / "parla" / "sources" / "bib" / "hand.bib").write_text(
        "@misc{local2019, title={Local}}\n@article{alpha2020, title={WRONG}}\n", encoding="utf-8"
    )
    warnings: list[str] = []

    build._regenerate_references_bib(root, _doc(), on_output=warnings.append)

    generated = (root / "parla" / "artifacts" / "paper" / "references.bib").read_text(encoding="utf-8")
    assert "@misc{local2019" in generated
    assert "WRONG" not in generated
    assert any("alpha2020" in w and "library wins" in w for w in warnings)
