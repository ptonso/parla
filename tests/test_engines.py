"""Engine contract: conformance over the registry, the none engine, and the router."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from conftest import CARD, make_artifact

from parla import config, jobs, router, template
from parla.checks import CheckFailed, Finding
from parla.engines import registry
from parla.engines.base import BuildError, Built, Engine, EngineError, Pages, Starter
from parla.guides.pages import GuideError


def _init(tmp_path: Path) -> Path:
    template.init(tmp_path)
    return tmp_path


@pytest.mark.parametrize("name", sorted(registry.ENGINES))
def test_every_engine_implements_the_contract(name: str, tmp_path: Path) -> None:
    engine = registry.ENGINES[name]
    assert isinstance(engine, Engine) and engine.name == name
    for method in ("starter", "check", "export", "prepare", *(() if name == "none" else ("build",))):
        assert getattr(type(engine), method) is not getattr(Engine, method), method
    starter = engine.starter(tmp_path, "a", "paper", None)
    assert isinstance(starter, Starter) and starter.entrypoint in starter.files
    assert set(engine.card_keys) <= set(starter.card_keys)


def test_unknown_engine_fails_naming_the_registered_ones() -> None:
    with pytest.raises(config.ConfigError, match="registered: latex, none"):
        registry.named("ghost")


def test_an_unimplemented_method_fails_naming_engine_and_method(tmp_path: Path) -> None:
    class Bare(Engine):
        name = "bare"

    with pytest.raises(EngineError, match="engine 'bare' does not implement 'build'"):
        Bare().build(tmp_path, "a", None)


def test_card_with_an_unregistered_engine_or_missing_engine_key_is_rejected(tmp_path: Path) -> None:
    root = _init(tmp_path)
    make_artifact(root, "p", {})
    card = root / "parla/artifacts/p/card.md"
    card.write_text(CARD.format(name="p").replace("engine: latex", "engine: ghost"))
    with pytest.raises(config.ConfigError, match="unknown engine 'ghost'"):
        config.load_card(root, "p")
    card.write_text(CARD.format(name="p").replace("latex: lualatex\n", ""))
    with pytest.raises(config.ConfigError, match="requires card key.*latex"):
        config.load_card(root, "p")


def _text_artifact(root: Path, name: str = "post") -> None:
    router.init_artifact(root, name, "social-post", "linkedin")


def test_init_artifact_writes_a_valid_card_for_each_engine(tmp_path: Path) -> None:
    root = _init(tmp_path)
    router.init_artifact(root, "paper", "paper", "icra")
    _text_artifact(root)
    assert config.document(root, "paper").engine == "lualatex"
    assert config.load_card(root, "post").entrypoint == "post.md"
    with pytest.raises(GuideError, match="unknown modality 'ghost' \\(have: .*paper"):
        router.init_artifact(root, "x", "ghost", "icra")
    with pytest.raises(GuideError, match="unknown audience 'ghost' \\(have: .*icra"):
        router.init_artifact(root, "x", "paper", "ghost")


def test_none_engine_has_no_build_and_leaves_no_error_file(tmp_path: Path) -> None:
    root = _init(tmp_path)
    _text_artifact(root)
    with pytest.raises(EngineError, match="engine 'none' does not implement 'build'"):
        router.build(root, "post")
    assert not (root / "parla/artifacts/post/BUILD-ERROR.txt").exists()


def test_none_engine_export_dereferences_symlinks(tmp_path: Path) -> None:
    root = _init(tmp_path)
    _text_artifact(root)
    (tmp_path / "abstract.md").write_text("shared\n")
    (root / "parla/artifacts/post/abstract.md").symlink_to(tmp_path / "abstract.md")

    out = router.export(root, "post", "Final Cut", False)

    assert out.name.endswith("_final-cut")
    assert (out / "abstract.md").read_text() == "shared\n" and not (out / "abstract.md").is_symlink()
    with pytest.raises(EngineError, match="refusing to overwrite"):
        router.export(root, "post", "Final Cut", False)
    router.export(root, "post", "Final Cut", True)
    assert registry.ENGINES["none"].pages(root, "post") is None


class _Fake(Engine):
    name = "fake"

    def __init__(self, findings: list[Finding]) -> None:
        self.findings, self.calls = findings, []

    def prepare(self, root):
        self.calls.append("prepare")

    def check(self, root, artifact):
        self.calls.append("check")
        return self.findings

    def build(self, root, artifact, baseline):
        self.calls.append(("build", baseline))
        return Built(published=())

    def pages(self, root, artifact):
        return Pages(1, 1)


def _with_fake(monkeypatch: pytest.MonkeyPatch, fake: Engine) -> None:
    monkeypatch.setitem(registry.ENGINES, "none", fake)


def test_an_error_finding_prevents_the_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _init(tmp_path)
    _text_artifact(root)
    err = Finding("artifacts/post/post.md", 1, "error", "source-missing", "x")
    warn = Finding("artifacts/post/post.md", 2, "warning", "todo-marker", "y")
    fake = _Fake([err, warn])
    _with_fake(monkeypatch, fake)
    shown: list[str] = []

    with pytest.raises(CheckFailed) as exc:
        router.build(root, "post", on_output=shown.append)

    assert fake.calls == ["prepare", "check"]
    assert exc.value.findings == [err, warn]
    assert shown == [err.format(), warn.format()]


def test_warnings_print_and_the_build_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _init(tmp_path)
    _text_artifact(root)
    warn = Finding("artifacts/post/post.md", 2, "warning", "todo-marker", "y")
    fake = _Fake([warn])
    _with_fake(monkeypatch, fake)

    router.build(root, "post", on_output=lambda _l: None)

    assert [c if isinstance(c, str) else c[0] for c in fake.calls] == ["prepare", "check", "build"]


class _Failing(_Fake):
    def build(self, root, artifact, baseline):
        raise BuildError("tex exploded at main.tex:3")


def test_a_failed_check_or_build_writes_build_error_and_a_success_removes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _init(tmp_path)
    _text_artifact(root)
    notice = root / "parla/artifacts/post/BUILD-ERROR.txt"
    err = Finding("artifacts/post/post.md", 1, "error", "source-missing", "no file")
    quiet = lambda _l: None  # noqa: E731

    _with_fake(monkeypatch, _Fake([err]))
    with pytest.raises(CheckFailed):
        router.build(root, "post", on_output=quiet)
    text = notice.read_text()
    assert text.startswith("This is a generated file: ") and err.format() in text

    _with_fake(monkeypatch, _Failing([]))
    with pytest.raises(BuildError):
        router.build(root, "post", on_output=quiet)
    assert notice.read_text().endswith("\n\ntex exploded at main.tex:3\n") and "no file" not in notice.read_text()

    _with_fake(monkeypatch, _Fake([]))
    router.build(root, "post", on_output=quiet)
    assert not notice.exists()


def test_ignored_ids_are_dropped_and_findings_are_sorted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _init(tmp_path)
    _text_artifact(root)
    toml = root / "parla/parla.toml"
    toml.write_text(toml.read_text() + '\n[checks]\nignore = ["todo-marker"]\n')
    a = Finding("b.tex", 1, "warning", "todo-marker", "x")
    b = Finding("b.tex", 9, "error", "source-missing", "x")
    c = Finding("a.tex", 5, "error", "source-missing", "x")
    _with_fake(monkeypatch, _Fake([b, a, c]))

    assert router.check(root, "post") == [c, b]


def test_baseline_resolution_order(tmp_path: Path) -> None:
    root = _init(tmp_path)
    _text_artifact(root)
    other = tmp_path / "other"
    other.mkdir()
    assert router.resolve_baseline(root, "post") is None
    jobs.start(root, "post")
    snap = jobs.active_snapshot(root, "post")
    assert router.resolve_baseline(root, "post") == snap
    assert router.resolve_baseline(root, "post", diff_from=str(other)) == other
    assert router.resolve_baseline(root, "post", no_diff=True) is None


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True
    )


def test_baseline_from_a_git_ref_mirrors_the_layout(tmp_path: Path) -> None:
    root = _init(tmp_path)
    _text_artifact(root)
    post = root / "parla/artifacts/post/post.md"
    post.write_text("old\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    post.write_text("new\n")

    baseline = router.resolve_baseline(root, "post", diff_from="HEAD")

    assert baseline is not None
    assert (baseline / "artifacts/post/post.md").read_text() == "old\n"
    assert (baseline / "artifacts/post/card.md").is_file()
    with pytest.raises(config.ConfigError, match="git archive"):
        router.resolve_baseline(root, "post", diff_from="no-such-ref")


def test_git_baseline_outside_a_work_tree_fails(tmp_path: Path) -> None:
    root = _init(tmp_path)
    _text_artifact(root)
    with pytest.raises(config.ConfigError, match="not inside a git work tree"):
        router.resolve_baseline(root, "post", diff_from="HEAD")


def test_watch_rebuilds_on_change_and_survives_a_failing_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _init(tmp_path)
    _text_artifact(root)
    post = root / "parla/artifacts/post/post.md"
    post.write_text("a\n")
    findings: list[list[Finding]] = [[], [Finding("p", 1, "error", "source-missing", "x")], []]
    fake = _Fake([])
    fake.check = lambda r, a: findings.pop(0) or []  # type: ignore[method-assign]
    _with_fake(monkeypatch, fake)
    sleeps = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 1:
            post.write_text("b\n")
            os.utime(post, (1, 1))  # a changed mtime
        elif len(sleeps) == 4:
            post.write_text("c\n")
            os.utime(post, (2, 2))
        elif len(sleeps) > 8:
            raise KeyboardInterrupt

    monkeypatch.setattr(router.time, "sleep", fake_sleep)
    shown: list[str] = []
    with pytest.raises(KeyboardInterrupt):
        router.watch(root, "post", on_output=shown.append)

    builds = [c for c in fake.calls if not isinstance(c, str)]
    assert len(builds) == 2 and any("checks failed" in s for s in shown)


def test_snapshot_excludes_outputs_state_and_exports_and_does_not_enter_source_links(tmp_path: Path) -> None:
    base = tmp_path / "parla"
    (base / "export").mkdir(parents=True)
    (base / ".parla/jobs").mkdir(parents=True)
    (base / "artifacts/a").mkdir(parents=True)
    (tmp_path / "ext").mkdir()
    (tmp_path / "ext/x.png").write_bytes(b"x")
    (base / "sources").mkdir()
    (base / "sources/data").symlink_to(tmp_path / "ext", target_is_directory=True)
    for p in ("artifacts/a/a.pdf", "artifacts/a/a_diff.png", "artifacts/a/BUILD-ERROR.txt", "export/a.tex", ".parla/jobs/j.tex", "artifacts/a/main.tex"):
        (base / p).write_text("x")

    assert set(router._snapshot(base)) == {base / "artifacts/a/main.tex"}
