"""`parla init` with local storage (real parla/ dir) vs external storage (symlink into the asset root),
and the artifact folder writer."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from parla import config, template

_INPUT_RE = re.compile(r"\\input\{([^}]+)\}")


def test_local_init_makes_a_real_parla_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "asset_root", lambda: None)
    proj = tmp_path / "paper"
    proj.mkdir()

    written = template.init(proj)

    base = proj / "parla"
    assert base.is_dir() and not base.is_symlink()
    for rel in template.DIRS:
        assert (base / rel).is_dir()
    for rel in template.FILES:
        assert (base / rel).is_file()
    assert (base / "parla.toml") in written
    assert (base / "export").is_dir() and not (base / "out").exists()
    raw = tomllib.loads((base / "parla.toml").read_text())
    assert "docker" not in raw
    assert config.load(proj).version == 1
    assert config.find_root(proj / "parla") == proj


def test_local_init_rejects_a_pre_existing_symlink(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "asset_root", lambda: None)
    proj = tmp_path / "paper"
    proj.mkdir()
    (proj / "parla").symlink_to(tmp_path)

    with pytest.raises(config.ConfigError, match="symlink but no .storage..asset_root"):
        template.init(proj)


def test_external_init_makes_a_symlink(monkeypatch, tmp_path):
    asset = tmp_path / "asset"
    proj = tmp_path / "anywhere" / "paper"
    proj.mkdir(parents=True)
    monkeypatch.setattr(config, "asset_root", lambda: asset)

    template.init(proj)

    base = proj / "parla"
    assert base.is_symlink()
    assert base.resolve() == (asset / "paper").resolve()


def test_external_init_rejects_a_real_dir_a_wrong_symlink_and_a_shared_name(monkeypatch, tmp_path):
    asset = tmp_path / "asset"
    proj = tmp_path / "p"
    (proj / "parla").mkdir(parents=True)
    monkeypatch.setattr(config, "asset_root", lambda: asset)
    with pytest.raises(config.ConfigError, match="real directory"):
        template.init(proj)

    (proj / "parla").rmdir()
    (proj / "parla").symlink_to(tmp_path)
    with pytest.raises(config.ConfigError, match="expected"):
        template.init(proj)

    (proj / "parla").unlink()
    (asset / "p").mkdir(parents=True)
    with pytest.raises(config.ConfigError, match="does not link to it"):
        template.init(proj)


CARD = """\
---
modality: paper
audience: icra
engine: latex
latex: lualatex
entrypoint: main.tex
phase: drafting
traits:
  reader: cross-domain
derived-from: null
---
# P
"""


@pytest.mark.parametrize("modality", ["paper", "talk", "cv"])
def test_stock_starters_compile_inputs_exist(monkeypatch, tmp_path, modality):
    monkeypatch.setattr(config, "asset_root", lambda: None)
    template.init(tmp_path)
    files = template.stock_files(modality, "p")
    written = template.init_artifact(tmp_path, "p", CARD, files)

    base = tmp_path / "parla" / "artifacts" / "p"
    assert base / "card.md" in written
    for target in _INPUT_RE.findall((base / "main.tex").read_text()):
        assert (tmp_path / "parla" / f"{target}.tex").is_file()
    main = (base / "main.tex").read_text()
    assert ("parla:body-end" in main) == (modality in ("paper", "cv"))
    assert ("artifacts/p/references" in main) == (modality != "cv")


def test_init_artifact_is_idempotent_and_force_overwrites(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "asset_root", lambda: None)
    template.init(tmp_path)
    files = template.stock_files("paper", "p")
    template.init_artifact(tmp_path, "p", CARD, files)
    main = tmp_path / "parla/artifacts/p/main.tex"
    main.write_text("edited")
    assert template.init_artifact(tmp_path, "p", CARD, files) == []
    assert main.read_text() == "edited"
    template.init_artifact(tmp_path, "p", CARD, files, force=True)
    assert main.read_text() != "edited"


def test_card_load_and_document_shim(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "asset_root", lambda: None)
    template.init(tmp_path)
    template.init_artifact(tmp_path, "p", CARD, template.stock_files("paper", "p"))

    card = config.load_card(tmp_path, "p")
    assert (card.modality, card.audience, card.phase) == ("paper", "icra", "drafting")
    assert card.traits == {"reader": "cross-domain"} and card.derived_from is None
    doc = config.document(tmp_path, "p")
    assert (doc.entrypoint, doc.engine, doc.stem) == ("artifacts/p/main.tex", "lualatex", "main")


@pytest.mark.parametrize(
    "edit,match",
    [
        (lambda c: c.replace("phase: drafting\n", ""), "missing card key"),
        (lambda c: c.replace("drafting", "documenting"), "phase"),
        (lambda c: c.replace("main.tex", "../x.tex"), "entrypoint"),
        (lambda c: c.replace("lualatex", "xelatex"), "latex must be"),
        (lambda c: c.removeprefix("---\n"), "frontmatter"),
    ],
)
def test_invalid_cards_fail(monkeypatch, tmp_path, edit, match):
    monkeypatch.setattr(config, "asset_root", lambda: None)
    template.init(tmp_path)
    template.init_artifact(tmp_path, "p", edit(CARD), {})
    with pytest.raises(config.ConfigError, match=match):
        config.document(tmp_path, "p")


def test_missing_card_fails(tmp_path):
    with pytest.raises(config.ConfigError, match="no card"):
        config.load_card(tmp_path, "nope")


def test_parla_toml_validation(tmp_path):
    def load(body):
        base = tmp_path / "parla"
        base.mkdir(exist_ok=True)
        (base / "parla.toml").write_text(body)
        return config.load(tmp_path)

    assert load('[project]\nversion = 1\n[checks]\nignore = ["todo-marker"]\n').ignore == ("todo-marker",)
    with pytest.raises(config.ConfigError, match="unknown top-level"):
        load("[project]\nversion = 1\n[documents.x]\n")
    with pytest.raises(config.ConfigError, match="must be 1"):
        load("[project]\nversion = 2\n")
    with pytest.raises(config.ConfigError, match="ignore"):
        load('[project]\nversion = 1\n[checks]\nignore = "x"\n')


def test_cv_starter_loads_the_package_and_inputs_every_section(monkeypatch, tmp_path):
    files = template.stock_files("cv", "p")
    main = files["main.tex"]
    assert "\\usepackage{hyperref}" in main
    assert [f"\\input{{artifacts/p/{Path(rel).with_suffix('')}}}" in main for rel in files if rel != "main.tex"] == [True] * 6
    assert files["section/header.tex"].startswith("\\begin{center}")


def test_a_leftover_paths_out_key_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "asset_root", lambda: None)
    template.init(tmp_path)
    toml = tmp_path / "parla/parla.toml"
    toml.write_text(toml.read_text().replace('[paths]\n', '[paths]\nout = "out"\n'))
    with pytest.raises(config.ConfigError, match=r"unknown \[paths\] key\(s\): out"):
        config.load(tmp_path)
