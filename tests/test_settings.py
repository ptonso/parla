"""User config: `~/.config/parla/config.toml` resolution and the graceful-degrade accessors."""
from __future__ import annotations

from pathlib import Path

import pytest

from parla import config, settings


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_config_path_prefers_parla_config_env(monkeypatch, tmp_path):
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "custom.toml"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert settings.config_path() == tmp_path / "custom.toml"


def test_config_path_falls_back_to_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("PARLA_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert settings.config_path() == tmp_path / "xdg" / "parla" / "config.toml"


def test_missing_file_means_local_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "nope.toml"))
    assert config.asset_root() is None
    assert config.library_bib() is None
    assert config.texmf_home() is None
    assert config.guides_private() == tmp_path
    assert (config.guides_target_words(), config.guides_tolerance(), config.guides_limit_words()) == (1000, 1.2, 1200)
    assert config.guides_stale_days() is None


def test_external_storage(monkeypatch, tmp_path):
    store = tmp_path / "asset"
    store.mkdir()
    _write(
        tmp_path / "c.toml",
        f'[storage]\nasset_root = "{store}"\n'
        f'[guides]\nprivate = "{tmp_path}/g"\ntarget_words = 100\nstale_days = 30\n',
    )
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "c.toml"))
    assert config.asset_root() == store
    assert config.guides_private() == tmp_path / "g"
    assert (config.guides_target_words(), config.guides_stale_days()) == (100, 30)


def test_guides_keys_must_be_positive_integers(monkeypatch, tmp_path):
    _write(tmp_path / "c.toml", '[guides]\ntarget_words = "many"\n')
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "c.toml"))
    with pytest.raises(config.ConfigError, match="target_words"):
        config.guides_target_words()


def test_tolerance_and_the_removed_max_words(monkeypatch, tmp_path):
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "c.toml"))
    _write(tmp_path / "c.toml", "[guides]\ntolerance = 0.5\n")
    with pytest.raises(config.ConfigError, match="tolerance"):
        config.guides_tolerance()
    _write(tmp_path / "c.toml", "[guides]\nmax_words = 100\n")
    with pytest.raises(config.ConfigError, match="target_words"):
        config.guides_target_words()


def test_texmf_home_must_exist(monkeypatch, tmp_path):
    _write(tmp_path / "c.toml", f'[storage]\ntexmf_home = "{tmp_path}/nope"\n')
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "c.toml"))
    with pytest.raises(config.ConfigError, match="texmf_home"):
        config.texmf_home()
