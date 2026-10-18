"""The command surface: parsing, exit codes, `init` and the skill links."""
from __future__ import annotations


import pytest

from parla import cli, config, template
from parla.checks import Finding
from parla.engines import registry
from parla.engines.base import Built, BuildError, Engine


@pytest.fixture(autouse=True)
def _local_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "no-config.toml"))
    monkeypatch.chdir(tmp_path)


def test_unknown_subcommand_is_a_usage_error(capsys):
    with pytest.raises(SystemExit):
        cli.main(["link-figs"])
    assert "invalid choice" in capsys.readouterr().err


def test_commands_outside_a_project_fail_fast(capsys):
    for argv in (["link"], ["check", "p"], ["build", "p"], ["export", "p", "--tag", "t"], ["job", "end", "p"]):
        assert cli.main(argv) == 3
        assert "no parla/parla.toml found" in capsys.readouterr().err


def test_config_path_init_and_show(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "c.toml"))
    assert cli.main(["config", "path"]) == 0
    assert str(tmp_path / "c.toml") in capsys.readouterr().out

    assert cli.main(["config", "init"]) == 0
    assert (tmp_path / "c.toml").is_file()
    assert cli.main(["config", "init"]) == 3  # refuses to overwrite
    assert cli.main(["config", "init", "--force"]) == 0

    assert cli.main(["config", "show"]) == 0
    out = capsys.readouterr().out
    assert "guides.target_words" in out and "1000" in out


def test_init_creates_the_tree_and_links_the_skills(tmp_path, capsys):
    assert cli.main(["init"]) == 0
    assert (tmp_path / "parla/parla.toml").is_file()
    shipped = {p.name for p in template.SKILLS_DIR.iterdir() if p.is_dir()}
    for dest in (".claude/skills", ".agents/skills"):
        linked = {p.name: p for p in (tmp_path / dest).iterdir()}
        assert shipped and set(linked) == shipped
        assert all(p.is_symlink() and p.resolve() == (template.SKILLS_DIR / n).resolve() for n, p in linked.items())
    assert cli.main(["init"]) == 0  # idempotent


def test_init_repoints_a_stale_skill_link_and_refuses_a_real_directory(tmp_path):
    stale = tmp_path / "moved"
    stale.mkdir()
    link = tmp_path / ".agents/skills/parla"
    link.parent.mkdir(parents=True)
    link.symlink_to(stale)
    assert cli.main(["init"]) == 0
    assert link.resolve() == (template.SKILLS_DIR / "parla").resolve()

    link.unlink()
    link.mkdir()
    assert cli.main(["init"]) == 3


def test_init_artifact_writes_card_and_starter(tmp_path):
    cli.main(["init"])
    assert cli.main(["init", "artifact", "icra", "--modality", "paper", "--audience", "icra"]) == 0
    base = tmp_path / "parla/artifacts/icra"
    assert (base / "main.tex").is_file() and (base / "section/introduction.tex").is_file()
    assert config.document(tmp_path, "icra").engine == "lualatex"


class _Scripted(Engine):
    name = "none"

    def __init__(self, findings, error=None, late=()):
        self.findings, self.error, self.built, self.late = findings, error, 0, list(late)

    def post_build(self, root, artifact):
        return self.late

    def prepare(self, root):
        pass

    def check(self, root, artifact):
        return self.findings

    def build(self, root, artifact, baseline):
        if self.error:
            raise self.error
        self.built += 1
        return Built(published=(root / "parla/artifacts/post/post.md",), diff=None)


def _post(tmp_path):
    cli.main(["init"])
    cli.main(["init", "artifact", "post", "--modality", "social-post", "--audience", "linkedin"])


def test_check_exit_codes_and_output(tmp_path, monkeypatch, capsys):
    _post(tmp_path)
    err = Finding("artifacts/post/post.md", 3, "error", "source-missing", "no file")
    warn = Finding("artifacts/post/post.md", 1, "warning", "todo-marker", "left")
    monkeypatch.setitem(registry.ENGINES, "none", _Scripted([err, warn]))
    capsys.readouterr()

    assert cli.main(["check", "post"]) == 1
    assert capsys.readouterr().out.splitlines() == [warn.format(), err.format(), "suite: 1 fail, 0 probes open, 0 resolved"]

    monkeypatch.setitem(registry.ENGINES, "none", _Scripted([warn]))
    assert cli.main(["check", "post"]) == 0


def test_build_exit_codes(tmp_path, monkeypatch, capsys):
    _post(tmp_path)
    err = Finding("artifacts/post/post.md", 3, "error", "source-missing", "no file")
    ok = _Scripted([])
    monkeypatch.setitem(registry.ENGINES, "none", ok)
    assert cli.main(["build", "post"]) == 0 and ok.built == 1
    assert "built" in capsys.readouterr().out

    blocked = _Scripted([err])
    monkeypatch.setitem(registry.ENGINES, "none", blocked)
    assert cli.main(["build", "post"]) == 1 and blocked.built == 0
    assert "nothing was built" in capsys.readouterr().err

    monkeypatch.setitem(registry.ENGINES, "none", _Scripted([], BuildError("compile failed")))
    assert cli.main(["build", "post"]) == 2
    assert "compile failed" in capsys.readouterr().err


def test_build_reports_the_suite_after_the_compile_and_exits_4_while_it_is_red(tmp_path, monkeypatch, capsys):
    _post(tmp_path)
    late = Finding("artifacts/post/post.md", 1, "error", "frame-overflow", "a frame overflows")
    monkeypatch.setitem(registry.ENGINES, "none", _Scripted([], late=[late]))
    capsys.readouterr()
    assert cli.main(["build", "post"]) == 4  # built, and the suite is not green
    out = capsys.readouterr().out.splitlines()
    assert "built" in out[-1] or "built" in " ".join(out)
    assert late.format() in out and "suite: 1 fail, 0 probes open, 0 resolved" in out
    monkeypatch.setitem(registry.ENGINES, "none", _Scripted([], late=[]))
    assert cli.main(["build", "post"]) == 0


def test_build_flags_reach_the_router(tmp_path, monkeypatch):
    _post(tmp_path)
    seen = {}
    monkeypatch.setattr(cli.router, "build", lambda root, a, **kw: seen.update(kw) or Built(published=()))
    cli.main(["build", "post", "--diff-from", "HEAD", "--no-diff"])
    assert seen["diff_from"] == "HEAD" and seen["no_diff"] is True


def test_build_watch_exits_zero_on_ctrl_c(tmp_path, monkeypatch):
    _post(tmp_path)

    def interrupted(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.router, "watch", interrupted)
    assert cli.main(["build", "post", "--watch"]) == 0


def test_job_commands(tmp_path, capsys):
    _post(tmp_path)
    post = tmp_path / "parla/artifacts/post/post.md"
    post.write_text("one\n")
    capsys.readouterr()

    assert cli.main(["job", "start", "post", "--part", "intro"]) == 0
    assert capsys.readouterr().out.strip().endswith("Z")
    assert cli.main(["job", "start", "post"]) == 3
    post.write_text("two\n")
    assert cli.main(["build", "post"]) == 3
    assert cli.main(["job", "end", "post"]) == 0
    assert "changed artifacts/post/post.md" in capsys.readouterr().out
    assert cli.main(["job", "revert", "post"]) == 0
    assert post.read_text() == "one\n"


def test_export_and_link(tmp_path, capsys):
    _post(tmp_path)
    assert cli.main(["link"]) == 0
    assert "links up to date" in capsys.readouterr().out
    assert cli.main(["export", "post", "--tag", "v1"]) == 0
    assert "exported post" in capsys.readouterr().out
    assert cli.main(["export", "post", "--tag", "v1"]) == 3
    assert cli.main(["export", "ghost", "--tag", "v1"]) == 3


def test_init_help_lists_the_modalities_and_audiences_found_in_the_guides(capsys):
    with pytest.raises(SystemExit):
        cli.main(["init", "--help"])
    out = capsys.readouterr().out
    assert "modalities: cv, diagram, paper, social-post, talk" in out and "icra" in out
    with pytest.raises(SystemExit):
        cli.main(["init", "artifact", "--help"])
    assert "the kind of artifact: cv, diagram, paper" in capsys.readouterr().out


def test_init_artifact_rejects_an_unknown_modality_naming_the_choices(capsys):
    with pytest.raises(SystemExit):
        cli.main(["init", "artifact", "x", "--modality", "ghost", "--audience", "icra"])
    err = capsys.readouterr().err
    assert "invalid choice: 'ghost'" in err and "paper" in err


def test_init_with_a_modality_name_explains_the_right_command(capsys):
    with pytest.raises(SystemExit):
        cli.main(["init", "paper"])
    err = capsys.readouterr().err
    assert "'paper' is a modality" in err and "init artifact <name> --modality paper" in err


def test_init_help_says_where_it_looked_when_no_guides_exist(monkeypatch, capsys, tmp_path):
    from parla.guides import pages

    monkeypatch.setattr(pages, "PUBLIC_ROOT", tmp_path / "none")
    with pytest.raises(SystemExit):
        cli.main(["init", "artifact", "--help"])
    out = "".join(capsys.readouterr().out.split())  # argparse wraps long paths at hyphens
    assert "nonefound:addmodalitypagestotheguides" in out and str(tmp_path / "none") in out


def test_list_prints_each_artifact_with_its_state(tmp_path, capsys):
    _post(tmp_path)
    cli.main(["init", "artifact", "icra", "--modality", "paper", "--audience", "icra"])
    capsys.readouterr()
    assert cli.main(["job", "start", "post"]) == 0
    capsys.readouterr()
    assert cli.main(["list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "icra  paper  icra  drafting",
        "post  social-post  linkedin  drafting  job active",
    ]
