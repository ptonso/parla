"""Image identity and the `[docker].image` default."""
from __future__ import annotations

from parla.config import _validate
from parla.engines.latex import image


def test_image_ref_is_a_local_tag():
    assert image.IMAGE_REF == f"{image.IMAGE_NAME}:{image.IMAGE_VERSION}"
    assert "/" not in image.IMAGE_REF  # no registry host


def test_packaged_build_context_is_present():
    assert image.dockerfile().is_file()
    assert (image.context_dir() / "texmf").is_dir()
    assert (image.context_dir() / "texmf" / "tex" / "latex" / "tonso").exists() is False


def test_manifest_has_the_ieee_classes():
    names = (image.context_dir() / "docker" / "tl-packages.txt").read_text().split()
    assert {"ieeetran", "ieeeconf", "preview"} <= set(names)


def test_image_exists_shells_docker(monkeypatch):
    calls = []

    class _R:
        returncode = 1

    monkeypatch.setattr(image.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _R())
    assert image.image_exists() is False
    assert calls[0][:3] == ["docker", "image", "inspect"]


def test_docker_image_defaults_to_the_tool_tag_when_omitted():
    assert _validate({"project": {"version": 1}}).image == image.IMAGE_REF


def test_docker_image_override_wins():
    cfg = _validate({"project": {"version": 1}, "docker": {"image": "my/texlive:9"}})
    assert cfg.image == "my/texlive:9"
