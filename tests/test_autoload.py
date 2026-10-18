from pathlib import Path

import pytest

from parla import config
from parla.engines.latex import autoload
from parla.config import ConfigError

STY = "\\NeedsTeXFormat{LaTeX2e}\n\\ProvidesPackage{project}\n\\endinput\n"


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, names: tuple[str, ...]):
    home = tmp_path / "home" / "tex" / "latex" / "tonso"
    home.mkdir(parents=True)
    (home / "slides-macros.tex").write_text("%", encoding="utf-8")
    (home / "image-slides.sty").write_text("%", encoding="utf-8")
    sty = tmp_path / "parla" / "texmf" / "tex" / "latex" / "project" / "project.sty"
    sty.parent.mkdir(parents=True)
    sty.write_text(STY, encoding="utf-8")
    monkeypatch.setattr(config, "texmf_home", lambda: tmp_path / "home")
    cfg = config.Config(version=1, image="x:1", texmf="texmf", links={}, autoload=names)
    return cfg, sty


def test_sync_writes_managed_block_before_endinput(tmp_path, monkeypatch):
    cfg, sty = _setup(tmp_path, monkeypatch, ("slides-macros", "image-slides"))
    autoload.sync_project_sty(tmp_path, cfg)
    text = sty.read_text(encoding="utf-8")
    assert "\\input{slides-macros.tex}\n\\RequirePackage{image-slides}\n% <<<" in text
    assert text.rstrip().endswith("\\endinput")
    autoload.sync_project_sty(tmp_path, cfg)
    assert sty.read_text(encoding="utf-8") == text


def test_sync_replaces_block_when_list_shrinks(tmp_path, monkeypatch):
    cfg, sty = _setup(tmp_path, monkeypatch, ("slides-macros",))
    autoload.sync_project_sty(tmp_path, cfg)
    empty = config.Config(**{**cfg.__dict__, "autoload": ()})
    autoload.sync_project_sty(tmp_path, empty)
    assert sty.read_text(encoding="utf-8") == STY


def test_unknown_name_fails_fast(tmp_path, monkeypatch):
    cfg, _ = _setup(tmp_path, monkeypatch, ("nope",))
    with pytest.raises(ConfigError):
        autoload.sync_project_sty(tmp_path, cfg)


def test_add_packages_edits_toml_in_place(tmp_path):
    (tmp_path / "parla").mkdir()
    toml = tmp_path / "parla" / "parla.toml"
    toml.write_text(
        '[project]\nversion = 1\n\n[links]\n"fig/a" = "b"\n',
        encoding="utf-8",
    )
    assert config.add_packages(tmp_path, autoload=("slides-macros",), require=("adjustbox",))
    assert not config.add_packages(tmp_path, autoload=("slides-macros",))
    config.add_packages(tmp_path, require=("booktabs",))
    cfg = config.load(tmp_path)
    assert cfg.autoload == ("slides-macros",) and cfg.require == ("adjustbox", "booktabs")
    assert '"fig/a" = "b"' in toml.read_text(encoding="utf-8")
