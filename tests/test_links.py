from __future__ import annotations

from pathlib import Path

import pytest

from parla import config
from parla.engines.latex.links import LinkError, sync_links


def _cfg(links: dict[str, str]) -> config.Config:
    return config.Config(
        version=1,
        image="parla-texlive:2025.2",
        texmf="texmf",
        links=links,
    )


def _project(tmp_path: Path) -> Path:
    (tmp_path / "parla" / "sources").mkdir(parents=True)
    return tmp_path


def test_creates_a_link(tmp_path: Path) -> None:
    root = _project(tmp_path)
    target = tmp_path / "reports"
    target.mkdir()

    lines = sync_links(root, _cfg({"fig/results": "reports"}))

    link = root / "parla" / "sources" / "fig" / "results"
    assert link.is_symlink()
    assert link.resolve() == target.resolve()
    assert lines == [f"linked sources/fig/results -> {target.resolve()}"]


def test_keeps_a_matching_link(tmp_path: Path) -> None:
    root = _project(tmp_path)
    target = tmp_path / "reports"
    target.mkdir()
    cfg = _cfg({"fig/results": "reports"})
    sync_links(root, cfg)

    lines = sync_links(root, cfg)

    assert lines == []


def test_repoints_a_link(tmp_path: Path) -> None:
    root = _project(tmp_path)
    old_target = tmp_path / "old"
    new_target = tmp_path / "new"
    old_target.mkdir()
    new_target.mkdir()
    sync_links(root, _cfg({"fig/results": "old"}))

    lines = sync_links(root, _cfg({"fig/results": "new"}))

    link = root / "parla" / "sources" / "fig" / "results"
    assert link.resolve() == new_target.resolve()
    assert lines == [f"repointed sources/fig/results -> {new_target.resolve()}"]


def test_fails_on_a_real_path(tmp_path: Path) -> None:
    root = _project(tmp_path)
    target = tmp_path / "reports"
    target.mkdir()
    real = root / "parla" / "sources" / "fig"
    real.mkdir(parents=True)
    (real / "results").mkdir()

    with pytest.raises(LinkError, match="real path"):
        sync_links(root, _cfg({"fig/results": "reports"}))


def test_fails_on_a_missing_target(tmp_path: Path) -> None:
    root = _project(tmp_path)

    with pytest.raises(LinkError, match="does not exist"):
        sync_links(root, _cfg({"fig/results": "nope"}))


def test_resolves_a_relative_value_against_the_project_root(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "data" / "eval").mkdir(parents=True)

    sync_links(root, _cfg({"table/eval": "data/eval"}))

    link = root / "parla" / "sources" / "table" / "eval"
    assert link.resolve() == (root / "data" / "eval").resolve()


def test_expands_tilde(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / "home"
    (fake_home / "asset" / "figs").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    root = _project(tmp_path / "proj")

    sync_links(root, _cfg({"fig/results": "~/asset/figs"}))

    link = root / "parla" / "sources" / "fig" / "results"
    assert link.resolve() == (fake_home / "asset" / "figs").resolve()
