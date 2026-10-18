"""Guides: rules, merge, `guide show`, `add`, `move`, `lint`; and the casebook they attach."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import shutil

import pytest
from conftest import PRIVATE_GUIDES, make_artifact

from parla import casebook, cli, config, jobs, router, template
from parla.guides import edit, lint, pages, rules, show


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project with local storage whose private guide root is `<tmp>/cfg`, filled with the fixture preferences."""
    cfg = tmp_path / "cfg"
    shutil.copytree(PRIVATE_GUIDES, cfg / "guides")
    monkeypatch.setenv("PARLA_CONFIG", str(cfg / "config.toml"))
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "proj"
    root.mkdir()
    template.init(root)
    monkeypatch.chdir(root)
    return root


def _artifact(root: Path, name: str = "icra-paper", extra_card: str = "") -> None:
    make_artifact(root, name, {"main.tex": "x"})
    card = root / f"parla/artifacts/{name}/card.md"
    card.write_text(card.read_text().replace("# " + name, "# " + name + "\n" + extra_card))


def _private(path: str, text: str) -> Path:
    from parla import config as c

    target = c.guides_private() / "guides" / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


# --- rules -----------------------------------------------------------------------------


def test_a_rule_parses_text_origin_and_overrides():
    parsed = rules.parse("## principles\n\n###### a-b\n> say it (once) plain (origin: texfy x (v2); overrides c-d)\n")
    (rule,) = parsed.rules
    assert (rule.id, rule.text, rule.origin, rule.overrides) == ("a-b", "say it (once) plain", "texfy x (v2)", "c-d")
    assert rule.render() == "###### a-b\n> say it (once) plain (origin: texfy x (v2); overrides c-d)"
    assert parsed.problems == []


def test_malformed_rules_are_reported():
    parsed = rules.parse("###### no-quote\n\n###### no-origin\n> text\n\n###### two\n> a (origin: x)\n> b (origin: y)\n")
    assert [(p.id, p.line) for p in parsed.problems] == [
        ("rule-malformed", 1), ("rule-origin-missing", 3), ("rule-malformed", 6),
    ]


def test_render_round_trips_sections_prose_and_rules():
    text = "intro\n\n## principles\n\n###### a\n> r (origin: x)\n\n## check\n\n- one\n- two\n"
    assert rules.parse(text).render() == text


# --- pages and merge -------------------------------------------------------------------


def test_a_private_page_appends_to_the_public_one(project):
    _private("modality/paper.md", """---
kind: modality
modality: paper
replace: true
---
## brief

mine

## principles

###### paper-extra
> a second private rule (origin: me)
""")
    page = pages.load("modality/paper")
    assert page.label == "public+private"
    brief = page.parsed.section("brief")
    assert [i.startswith("Fixture paper brief") for i in brief.items] == [True, False]  # `replace:` is ignored
    assert [r.id for r in page.parsed.section("principles").rules] == ["paper-extra"]
    assert page.public is not None and not page.public.rules


def test_modality_inherits_sections_and_parts_table(project):
    talk = pages.modality("talk")
    assert pages.parts(talk) == {"opening": ("Why the audience should care.", ["positioning"])}
    assert pages.chain("talk") == ["paper", "talk"]
    assert [r.id for r in talk.parsed.section("principles").rules] == ["paper-claims"]
    assert pages.parts(pages.modality("paper")) == {
        "introduction": ("Takes the reader from the field to this paper.", ["positioning", "contributions"]),
        "results": ("Reports what was measured.", ["evidence"]),
    }


def test_a_private_parts_row_adds_topics_to_a_public_part(project):
    _private("modality/paper.md", "---\nkind: modality\nmodality: paper\n---\n## parts\n\n| part | job | topics |\n|---|---|---|\n| introduction | ignored | evidence, positioning |\n")
    job, topics = pages.parts(pages.modality("paper"))["introduction"]
    assert job == "Takes the reader from the field to this paper."
    assert topics == ["positioning", "contributions", "evidence"]


def test_missing_page_fails_fast(project):
    with pytest.raises(pages.GuideError, match="no guide page 'topic/nope'"):
        pages.load("topic/nope")


# --- show ------------------------------------------------------------------------------


def test_show_orders_the_document_and_applies_overrides(project):
    _artifact(project, extra_card="## decisions\n- keep it short\n\n## rules\n\n###### art-name\n> call it AcmeTrees (origin: 2026-10-13)\n")

    out = show.show(project, "icra-paper", "introduction", unformatted=True)

    heads = [line for line in out.splitlines() if line.startswith("#")]
    assert heads == [
        "# How this works",
        "# paper",
        "## Part: introduction",
        "# Engine facts",
        "## latex",
        "# Traits",
        "## reader/peer",
        "# The author's preferences (they win over the defaults)",
        "## general",
        "## modality/paper",
        "## topic/positioning",
        "### paper",
        "### check",
        "## topic/contributions",
        "## trait/reader/peer",
        "## engine/latex",
        "## audience/icra",
        "### positioning",
        "# This artifact: icra-paper",
        "### decisions",
        "### rules",
    ]
    assert "- [pos-paper] the paper positions against three named works" in out and "origin:" not in out
    assert out.splitlines()[0].startswith("parla guide icra-paper introduction | ")
    assert "Takes the reader from the field to this paper." in out
    assert "pos-paper" in out and "pos-talk" not in out
    assert "###### pos-blend" not in out
    assert out.splitlines()[-1] == "--- overridden: pos-blend by icra-pos"
    assert "keep it short" in out and "art-name" in out
    assert out == show.show(project, "icra-paper", "introduction", unformatted=True)  # deterministic


def test_show_with_no_private_root_prints_the_defaults(project):
    shutil.rmtree(project.parent / "cfg" / "guides")
    _artifact(project)
    out = show.show(project, "icra-paper", "introduction")
    assert "Fixture frame" in out and "Fixture paper brief" in out and "pos-gap" not in out and "pos-paper" not in out


def test_a_card_with_only_a_title_prints_no_section(project):
    _artifact(project)
    assert "<card>" not in show.show(project, "icra-paper", "introduction")


def test_the_card_trait_wins_on_a_kind(project):
    _artifact(project)
    card = project / "parla/artifacts/icra-paper/card.md"
    card.write_text(card.read_text().replace("derived-from: null", "traits:\n  reader: cross-domain\nderived-from: null"))
    out = show.show(project, "icra-paper", "introduction", unformatted=True)
    assert "reader-cross" in out and "reader-peer" not in out and "## reader/cross-domain" in out


def test_a_topic_name_or_unknown_name(project):
    _artifact(project)
    assert "## topic/evidence" in show.show(project, "icra-paper", "evidence", unformatted=True)
    assert '<topic name="evidence">' in show.show(project, "icra-paper", "evidence")
    with pytest.raises(pages.GuideError, match="Parts: introduction, results"):
        show.show(project, "icra-paper", "ghost")


def test_outline_names_each_element_with_its_words_and_files(project):
    _artifact(project)
    out = show.show(project, "icra-paper", "introduction", outline=True)
    lines = out.splitlines()

    def row(prefix: str) -> str:
        return next(line for line in lines if line.startswith(prefix))

    assert "pos-gap" not in out and "the paper positions" not in out  # no bodies
    assert "from:" not in out and "public+private" not in out and not any(line.split()[1:2] == ["public"] for line in lines[1:-2])
    assert "general.md" in row("<context>") and "modality/paper.md" in row('<brief name="paper">')
    topic = row('<topic name="positioning">')
    assert "$private/guides/topic/positioning.md" in topic or ("{" in topic and "$private" in topic)
    assert "constraints.jsonl" in row("<watch>") and "fig-ref-form" in row("<watch>")
    assert lines[0].startswith("parla guide icra-paper introduction | ")
    assert lines[-1].startswith("$")


def test_over_the_target_warns_and_over_the_tolerance_fails(project, capsys):
    _artifact(project)
    total = show.budget(project, "icra-paper", "introduction", ["positioning"])[2]
    cfg = project.parent / "cfg/config.toml"
    cfg.write_text(f"[guides]\ntarget_words = {total - 1}\n")
    out = show.show(project, "icra-paper", "introduction", topics=["positioning"])
    assert "pos-paper" not in out and "the paper positions against three named works" in out
    assert "over the target" in capsys.readouterr().err
    cfg.write_text("[guides]\ntarget_words = 5\n")
    with pytest.raises(pages.GuideError, match="over the limit of 6"):
        show.show(project, "icra-paper", "introduction", topics=["positioning"])


def test_show_page_prints_one_merged_page(project):
    assert "# topic/evidence" in show.show_page("topic", "evidence", unformatted=True)
    assert show.show_page("topic", "evidence").startswith('<topic name="evidence">')


# --- add, move, lint -------------------------------------------------------------------


def test_add_creates_a_private_page_and_refuses_a_duplicate(project):
    with pytest.raises(pages.GuideError, match="needs --hook"):
        edit.add(project, "topic/new-topic", "nt-one", "say it once")
    path = edit.add(project, "topic/new-topic", "nt-one", "say it once", origin="session", hook="a new situation")
    assert path == project.parent / "cfg/guides/topic/new-topic.md"
    text = path.read_text()
    assert text.startswith('---\nkind: topic\ntopic: new-topic\nhook: "a new situation"\n---\n')
    assert "###### nt-one\n> say it once (origin: session)" in text
    with pytest.raises(pages.GuideError, match="already exists"):
        edit.add(project, "topic/new-topic", "nt-one", "again")
    with pytest.raises(pages.GuideError, match="already exists"):
        edit.add(project, "topic/new-topic", "pos-gap", "again")
    with pytest.raises(pages.GuideError, match="needs its frontmatter"):
        edit.add(project, "modality/ghost", "m-one", "x")


def test_add_to_an_audience_section_and_the_card(project):
    edit.add(project, "audience/icra", "icra-con", "x", section="contributions", overrides="con-reader")
    page = pages.load("audience/icra")
    assert [r.id for r in page.parsed.section("contributions").rules] == ["icra-con"]
    assert page.meta["language"] == "en"  # the private page only adds; the public meta is kept
    _artifact(project)
    edit.add(project, "ignored", "card-rule", "for this artifact", card="icra-paper")
    assert "###### card-rule" in (project / "parla/artifacts/icra-paper/card.md").read_text()
    assert config.load_card(project, "icra-paper").modality == "paper"
    with pytest.raises(pages.GuideError, match="names no rule"):
        edit.add(project, "topic/new", "x-1", "x", overrides="ghost")


def test_move_a_card_rule_to_a_private_page_and_never_a_public_rule(project):
    _artifact(project, extra_card="## rules\n\n###### art-name\n> call it AcmeTrees (origin: 2026-10-13)\n")
    target = edit.move(project, "art-name", "topic/contributions")
    assert "###### art-name" in target.read_text() and "2026-10-13" in target.read_text()
    assert "art-name" not in (project / "parla/artifacts/icra-paper/card.md").read_text()
    with pytest.raises(pages.GuideError, match="no rule 'ghost'"):
        edit.move(project, "ghost", "topic/contributions")


def test_lint_is_clean_on_the_fixture_guides(project):
    assert lint.lint(project) == []


def test_lint_reports_each_problem(project):
    _private("topic/bad.md", """---
kind: topic
topic: bad
---
## principles

###### no-origin
> text

###### over
> overrides nothing (origin: x; overrides ghost-rule)

###### pos-gap
> duplicate of a public id on another page (origin: x)

[broken](nowhere.md)

a code span `[kept](ignored.md)` is not a link
""")
    found = {(f.id, f.file) for f in lint.lint(project)}
    assert ("rule-origin-missing", "private:topic/bad.md") in found
    assert ("rule-overrides-missing", "private:topic/bad.md") in found
    assert any(i == "rule-duplicate" for i, _ in found)
    assert ("link-broken", "private:topic/bad.md") in found


def test_lint_reports_a_rule_in_a_public_page_and_a_missing_brief(project, monkeypatch, tmp_path):
    public = tmp_path / "public"
    shutil.copytree(pages.PUBLIC_ROOT, public)
    (public / "topic").mkdir(exist_ok=True)
    (public / "topic/oops.md").write_text("---\nkind: topic\ntopic: oops\n---\n## principles\n\n###### oops-1\n> a public rule (origin: x)\n")
    (public / "modality/paper.md").write_text("---\nkind: modality\nmodality: paper\nengine: latex\n---\n## parts\n\n| part | job | topics |\n|---|---|---|\n| intro | | |\n")
    monkeypatch.setattr(pages, "PUBLIC_ROOT", public)
    found = {(f.id, f.file) for f in lint.lint(project)}
    assert ("public-rule", "public:topic/oops.md") in found
    assert ("brief-missing", "public:modality/paper.md") in found


def test_lint_budget_and_contradicted_ported_rule(project, monkeypatch):
    (project.parent / "cfg/config.toml").write_text("[guides]\ntarget_words = 20\n")
    assert any(f.id == "guide-over-budget" for f in lint.lint(project))
    (project.parent / "cfg/config.toml").write_text("")
    _artifact(project)
    casebook.add(project, _case("icra-paper", contradicts=["pos-gap"]), {"positioning"})
    found = [f for f in lint.lint(project) if f.id == "rule-contradicted"]
    assert len(found) == 1 and "pos-gap" in found[0].message  # its origin starts with texfy


# --- casebook ---------------------------------------------------------------------------


def _case(artifact="icra-paper", topics=("positioning",), **extra):
    return {
        "artifact": artifact, "part": "introduction", "topics": list(topics),
        "hook": "a passage that places the paper", "problem": "p", "before": "b", "after": "a", "lesson": "one line", **extra,
    }


def test_case_add_assigns_ids_and_copies_the_card(project):
    _artifact(project)
    first = casebook.add(project, _case(), {"positioning"}, today=date(2026, 10, 14))
    second = casebook.add(project, _case(), {"positioning"}, today=date(2026, 10, 15))
    assert (first, second) == ("c-0001", "c-0002")
    case = casebook.load()["c-0001"]
    assert (case["modality"], case["audience"], case["status"], case["date"]) == ("paper", "icra", "active", "2026-10-14")


def test_case_add_validates(project):
    _artifact(project)
    with pytest.raises(casebook.CaseError, match="missing field"):
        casebook.add(project, {"artifact": "icra-paper"}, {"positioning"})
    with pytest.raises(casebook.CaseError, match="unknown topic"):
        casebook.add(project, _case(topics=("ghost",)), {"positioning"})
    with pytest.raises(config.ConfigError, match="no card"):
        casebook.add(project, _case(artifact="ghost"), {"positioning"})
    with pytest.raises(casebook.CaseError, match="one line"):
        casebook.add(project, _case(lesson="a\nb"), {"positioning"})
    with pytest.raises(casebook.CaseError, match="hook"):
        casebook.add(project, _case(hook="a\nb"), {"positioning"})
    without = _case()
    del without["hook"]
    with pytest.raises(casebook.CaseError, match="missing field.*hook"):
        casebook.add(project, without, {"positioning"})


def test_mark_appends_and_never_rewrites(project):
    _artifact(project)
    casebook.add(project, _case(), {"positioning"})
    before = (project.parent / "cfg/cases.jsonl").read_text()
    casebook.mark("c-0001", "pruned")
    after = (project.parent / "cfg/cases.jsonl").read_text()
    assert after.startswith(before) and len(after.splitlines()) == 2
    assert casebook.load()["c-0001"]["status"] == "pruned"
    with pytest.raises(casebook.CaseError, match="unknown case"):
        casebook.mark("c-9", "pruned")
    with pytest.raises(casebook.CaseError, match="unknown status"):
        casebook.mark("c-0001", "gone")


def test_retrieval_filters_orders_trims_and_logs_use(project):
    _artifact(project)
    _artifact(project, "other")
    ids = {}
    ids["same"] = casebook.add(project, _case(), {"positioning"}, today=date(2026, 1, 1))
    ids["other"] = casebook.add(project, _case(artifact="other"), {"positioning"}, today=date(2026, 2, 1))
    ids["elsewhere"] = casebook.add(project, _case(topics=("evidence",)), {"positioning", "evidence"}, today=date(2026, 3, 1))
    ids["pruned"] = casebook.add(project, _case(), {"positioning"}, today=date(2026, 4, 1))
    casebook.mark(ids["pruned"], "pruned")

    got = casebook.retrieve(topics={"positioning"}, modality="paper", audience="icra", artifact="icra-paper", max_cases=8)
    assert [c["id"] for c in got] == [ids["same"], ids["other"]]
    assert [c["id"] for c in casebook.retrieve(topics={"positioning"}, modality="paper", audience="icra", artifact="icra-paper", max_cases=1)] == [ids["same"]]
    assert casebook.retrieve(topics={"positioning"}, modality="talk", audience="icra", artifact="x", max_cases=8) == []

    out = show.show(project, "icra-paper", "introduction", topics=["positioning"])
    assert "- c-0001: a passage that places the paper" in out and "lesson: one line" not in out and "before: b" not in out
    assert "parla case show <ids>" in out
    assert not (project.parent / "cfg/cases.use.jsonl").exists()  # listing a hook is not a use
    opened = casebook.show([ids["same"], ids["other"]], "icra-paper")
    assert '<case id="c-0001">' in opened and "<lesson>one line</lesson>" in opened and "<before>" not in opened
    uses = [json.loads(line) for line in (project.parent / "cfg/cases.use.jsonl").read_text().splitlines()]
    assert {u["case"] for u in uses} == {ids["same"], ids["other"]}
    show.show(project, "icra-paper", "introduction", topics=["positioning"], outline=True)
    assert len((project.parent / "cfg/cases.use.jsonl").read_text().splitlines()) == 2
    with pytest.raises(casebook.CaseError, match="unknown case"):
        casebook.show(["c-99"], "icra-paper")


def test_guide_add_with_evidence_marks_cases_distilled_and_records_them(project):
    _artifact(project)
    a = casebook.add(project, _case(), {"positioning"})
    b = casebook.add(project, _case(), {"positioning"})
    edit.add(project, "topic/positioning", "pos-distilled", "state the gap first", evidence=[a, b])
    assert casebook.load()[a]["status"] == "distilled"
    text = (project.parent / "cfg/guides/topic/positioning.md").read_text()
    assert f"origin: distilled from {a}, {b}" in text
    with pytest.raises(pages.GuideError, match="unknown case"):
        edit.add(project, "topic/positioning", "pos-x", "x", evidence=["c-99"])
    still = casebook.retrieve(topics={"positioning"}, modality="paper", audience="icra", artifact="icra-paper", max_cases=8)
    assert {c["id"] for c in still} == {a, b}


def test_case_lint_groups_and_stale(project):
    _artifact(project)
    for day in (1, 2, 3):
        casebook.add(project, _case(), {"positioning"}, today=date(2026, 1, day))
    found = casebook.lint(distill_min=3, stale_days=None, today=date(2026, 10, 1))
    assert [f.id for f in found] == ["case-distill"] and "c-0001, c-0002, c-0003" in found[0].message
    assert casebook.lint(distill_min=4, stale_days=None) == []
    stale = casebook.lint(distill_min=9, stale_days=30, today=date(2026, 10, 1))
    assert [f.id for f in stale] == ["case-stale"] * 3
    casebook.log_use(["c-0001"], "icra-paper", today=date(2026, 9, 25))
    assert len(casebook.lint(distill_min=9, stale_days=30, today=date(2026, 10, 1))) == 2


# --- the CLI ------------------------------------------------------------------------------


def test_guide_and_case_commands(project, capsys, monkeypatch):
    _artifact(project)
    capsys.readouterr()
    assert cli.main(["guide", "show", "icra-paper", "introduction", "--outline"]) == 0
    assert "parla guide icra-paper introduction" in capsys.readouterr().out
    assert cli.main(["guide", "show", "--topic", "evidence"]) == 0
    assert "every number carries its unit" in capsys.readouterr().out
    assert cli.main(["guide", "show", "--topic", "evidence", "--unformatted"]) == 0
    assert "ev-number" in capsys.readouterr().out
    assert cli.main(["guide", "show"]) == 3
    assert cli.main(["guide", "add", "topic/t1", "t1-a", "--text", "x", "--origin", "me", "--hook", "h1"]) == 0
    assert cli.main(["guide", "add", "topic/t1", "t1-a", "--text", "x"]) == 3
    assert cli.main(["guide", "add", "topic/t2", "t2-a", "--text", "y", "--hook", "h2"]) == 0
    assert cli.main(["guide", "move", "t1-a", "topic/t2"]) == 0
    assert cli.main(["guide", "drop", "t2-a"]) == 0
    assert cli.main(["guide", "drop", "t2-a"]) == 3
    assert cli.main(["guide", "lint"]) == 0
    capsys.readouterr()
    assert cli.main(["guide", "list", "trait"]) == 0
    assert capsys.readouterr().out.split() == ["trait/reader/cross-domain", "trait/reader/peer"]

    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_case())))
    capsys.readouterr()
    assert cli.main(["case", "add"]) == 0
    assert capsys.readouterr().out.strip() == "c-0001"
    assert cli.main(["case", "list", "--topic", "positioning"]) == 0
    assert "c-0001 active positioning icra a passage that places the paper | one line" in capsys.readouterr().out
    assert cli.main(["case", "show", "c-0001", "--artifact", "icra-paper"]) == 0
    assert '<case id="c-0001">' in capsys.readouterr().out
    assert cli.main(["case", "show", "c-0009"]) == 3
    assert cli.main(["case", "mark", "c-0001", "pruned"]) == 0
    assert cli.main(["case", "mark", "c-0001", "gone"]) == 3
    assert cli.main(["case", "lint"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert cli.main(["case", "add"]) == 3


def test_guide_lint_exits_1_on_an_error(project):
    _private("topic/bad.md", "---\nkind: topic\ntopic: bad\n---\n## principles\n\n###### x\n> no origin\n")
    assert cli.main(["guide", "lint"]) == 1


def test_init_artifact_uses_the_audience_setup(project, capsys):
    assert cli.main(["init", "artifact", "p", "--modality", "paper", "--audience", "icra"]) == 0
    main = (project / "parla/artifacts/p/main.tex").read_text()
    assert main.startswith("\\documentclass{IEEEtran}") and "\\usepackage{cite}" in main
    assert "\\label{parla:body-end}" in main
    assert config.load_card(project, "p").engine == "latex"
    assert cli.main(["init", "artifact", "q", "--modality", "social-post", "--audience", "linkedin"]) == 0
    assert (project / "parla/artifacts/q/post.md").is_file()
    assert "engine: none" in (project / "parla/artifacts/q/card.md").read_text()


def test_a_setup_class_no_layer_provides_fails_naming_it(project, monkeypatch):
    _private("audience/icra.md", "---\nkind: audience\naudience: icra\nsetup:\n  paper:\n    template: nonexistentclass\n---\n")
    with pytest.raises(config.ConfigError, match="nonexistentclass"):
        router.init_artifact(project, "p", "paper", "icra")


def test_a_modality_loads_its_extra_engine_pages_after_the_card_engine(project):
    make_artifact(project, "deck", {"main.tex": "x"})
    card = project / "parla/artifacts/deck/card.md"
    card.write_text(card.read_text().replace("modality: paper", "modality: talk"))
    out = show.show(project, "deck", "opening", unformatted=True)
    heads = [line for line in out.splitlines() if line.startswith("## ")]
    assert heads.index("## latex") + 1 == heads.index("## beamer")


# --- the view the model reads, topic routing and the budget ------------------------------


def test_the_default_view_is_xml_without_ids_origins_or_check_sections(project):
    _artifact(project, extra_card="## decisions\n- keep it short\n")
    out = show.show(project, "icra-paper", "introduction")
    tags = [line for line in out.splitlines() if line.startswith("<") and not line.startswith("</")]
    assert tags[0] == '<guide artifact="icra-paper" part="introduction">'
    assert tags[1:6] == ["<context>", '<brief name="paper">', '<part name="introduction">', '<engine name="latex">', "<traits>"]
    assert tags.index("<preferences>") < tags.index("<card>")
    assert out.splitlines()[-2] == "</card>" and out.splitlines()[-1] == "</guide>"
    assert "[pos-paper]" not in out and "###### " not in out and "origin" not in out
    assert "the gap is one sentence" not in out  # the `check` section is not printed
    assert "pos-blend" not in out and "blend the gap" not in out  # overridden by icra-pos
    assert "- the paper positions against three named works" in out
    assert out == show.show(project, "icra-paper", "introduction")


def test_the_unformatted_view_keeps_ids_and_prints_the_check_section(project):
    _artifact(project)
    out = show.show(project, "icra-paper", "introduction", unformatted=True)
    assert "- [pos-paper]" in out and "the gap is one sentence" in out and "<guide" not in out


def test_topics_come_from_the_call_then_the_job_then_the_part_row(project):
    _artifact(project)
    by_row = show.show(project, "icra-paper", "introduction")
    assert '<topic name="positioning">' in by_row and '<topic name="contributions">' in by_row
    jobs.start(project, "icra-paper", "introduction", ["contributions"])
    by_job = show.show(project, "icra-paper", "introduction")
    assert '<topic name="contributions">' in by_job and '<topic name="positioning">' not in by_job
    by_call = show.show(project, "icra-paper", "introduction", topics=["evidence"])
    assert '<topic name="evidence">' in by_call and '<topic name="contributions">' not in by_call
    with pytest.raises(pages.GuideError, match=r"unknown topic\(s\): ghost"):
        show.show(project, "icra-paper", "introduction", topics=["ghost"])


def test_the_hint_constraints_print_in_a_watch_block(project):
    _artifact(project)
    out = show.show(project, "icra-paper", "introduction")
    assert "<watch>\n- a figure is referenced as Figure~\\ref\n</watch>" in out


def test_the_topic_table_lists_words_and_hooks_and_the_budget_footer(project):
    _artifact(project)
    lines = show.topic_table(project, None, None)
    assert "positioning | " in lines[2] or any(line.startswith("positioning | ") for line in lines)
    assert any(line.endswith("| a passage that places the paper against prior work") for line in lines)
    with_artifact = show.topic_table(project, "icra-paper", "introduction")
    footer = [line for line in with_artifact if line.startswith("system ")]
    assert footer and "target 1000 | tolerance 1200 | left for topics" in footer[0]
    assert with_artifact[-1] == "topics of this part: positioning, contributions"
    assert cli.main(["guide", "list", "topic", "--artifact", "icra-paper", "--part", "introduction"]) == 0


def test_job_start_fails_over_the_tolerance_and_stores_the_topics(project, capsys):
    _artifact(project)
    (project.parent / "cfg/config.toml").write_text("[guides]\ntarget_words = 5\n")
    assert cli.main(["job", "start", "icra-paper", "--part", "introduction", "--topics", "positioning"]) == 3
    assert "over the limit" in capsys.readouterr().err
    (project.parent / "cfg/config.toml").write_text("")
    assert cli.main(["job", "start", "icra-paper", "--part", "introduction", "--topics", "positioning,ghost"]) == 3
    assert cli.main(["job", "start", "icra-paper", "--part", "introduction", "--topics", "positioning"]) == 0
    assert jobs.active_topics(project, "icra-paper") == ["positioning"]


def test_lint_reports_a_topic_without_a_hook_and_a_page_over_the_cap(project):
    _private("topic/nohook.md", "---\nkind: topic\ntopic: nohook\n---\n## principles\n\n###### nh-1\n> " + "word " * 40 + "(origin: x)\n")
    (project.parent / "cfg/config.toml").write_text("[guides]\nmax_page_words = 10\n")
    found = {(f.id, f.file) for f in lint.lint(project)}
    assert ("hook-missing", "private:topic/nohook.md") in found
    assert ("guide-page-over-cap", "private:topic/nohook.md") in found


def test_drop_removes_only_the_named_private_rule(project):
    path = edit.drop(project, "ev-number")
    assert "ev-number" not in path.read_text() and "## principles" in path.read_text()
    with pytest.raises(pages.GuideError, match="no private rule 'pos-paper-ghost'"):
        edit.drop(project, "pos-paper-ghost")
    public = pages.PUBLIC_ROOT / "modality/paper.md"
    before = public.read_text()
    with pytest.raises(pages.GuideError):
        edit.drop(project, "does-not-exist")
    assert public.read_text() == before


def test_edit_rewrites_in_place_and_keeps_the_old_text_in_the_history(project):
    _artifact(project)
    a = casebook.add(project, _case(topics=("evidence",)), {"evidence"})
    path = edit.edit(project, "ev-number", "every number carries its unit and its source", evidence=[a])
    text = path.read_text()
    assert "###### ev-number\n> every number carries its unit and its source (origin: fixture, revised " in text
    assert casebook.load()[a]["status"] == "distilled"
    history = [json.loads(line) for line in (project.parent / "cfg/rules.history.jsonl").read_text().splitlines()]
    assert history[0]["action"] == "edit" and history[0]["text"] == "every number carries its unit"
    assert history[0]["new_text"] == "every number carries its unit and its source"
    with pytest.raises(pages.GuideError, match="no private rule 'ghost'"):
        edit.edit(project, "ghost", "x")
    with pytest.raises(pages.GuideError, match="unknown case"):
        edit.edit(project, "ev-number", "x", evidence=["c-99"])


def test_drop_records_the_rule_in_the_history(project):
    edit.drop(project, "con-reader")
    (entry,) = [json.loads(line) for line in (project.parent / "cfg/rules.history.jsonl").read_text().splitlines()]
    assert (entry["action"], entry["rule"], entry["page"]) == ("drop", "con-reader", "topic/contributions")
    assert "what the reader can now do" in entry["text"]


def test_a_topic_page_over_the_cap_warns_when_a_rule_is_added_or_edited(project, capsys):
    (project.parent / "cfg/config.toml").write_text("[guides]\nmax_page_words = 12\n")
    capsys.readouterr()
    assert cli.main(["guide", "add", "topic/contributions", "con-two", "--text", "a second rule that pushes the page over its cap"]) == 0
    assert "over the page cap of 12" in capsys.readouterr().err
    assert cli.main(["guide", "edit", "con-two", "--text", "short"]) == 0
    assert cli.main(["guide", "edit", "ghost", "--text", "x"]) == 3


def test_case_edit_appends_an_update_and_protects_before_and_after(project):
    _artifact(project)
    first = casebook.add(project, _case(), {"positioning"})
    lines = (project.parent / "cfg/cases.jsonl").read_text().splitlines()
    casebook.edit(first, {"hook": "a new hook"}, {"positioning"})
    assert casebook.load()[first]["hook"] == "a new hook" and casebook.load()[first]["before"] == "b"
    assert (project.parent / "cfg/cases.jsonl").read_text().splitlines()[: len(lines)] == lines
    with pytest.raises(casebook.CaseError, match="edit takes"):
        casebook.edit(first, {"before": "x"}, {"positioning"})
    with pytest.raises(casebook.CaseError, match="one non-empty line"):
        casebook.edit(first, {"hook": "a\nb"}, {"positioning"})
    with pytest.raises(casebook.CaseError, match="unknown topic"):
        casebook.edit(first, {"topics": ["ghost"]}, {"positioning"})
    with pytest.raises(casebook.CaseError, match="unknown case"):
        casebook.edit("c-9", {"hook": "x"}, {"positioning"})


# --- topics limited to some modalities --------------------------------------------------


def test_a_topic_limited_to_other_modalities_fails_early_and_leaves_the_table(project, capsys):
    _artifact(project)
    with pytest.raises(pages.GuideError, match=r"not applicable to paper: 'slides-only' applies to talk"):
        show.show(project, "icra-paper", "introduction", topics=["slides-only"])
    with pytest.raises(pages.GuideError, match="not applicable to paper"):
        show.show(project, "icra-paper", "slides-only")
    assert cli.main(["job", "start", "icra-paper", "--topics", "slides-only"]) == 3
    assert "guide list topic --artifact" in capsys.readouterr().err
    assert not any(line.startswith("slides-only") for line in show.topic_table(project, "icra-paper", "introduction"))
    assert any(line.startswith("slides-only | ") and line.endswith("| applies to talk") for line in show.topic_table(project, None, None))


def test_a_topic_limited_to_the_modality_loads(project):
    make_artifact(project, "deck", {"main.tex": "x"})
    card = project / "parla/artifacts/deck/card.md"
    card.write_text(card.read_text().replace("modality: paper", "modality: talk"))
    assert '<topic name="slides-only">' in show.show(project, "deck", "opening", topics=["slides-only"])
    assert any(line.startswith("slides-only | ") for line in show.topic_table(project, "deck", "opening"))


def test_lint_reports_a_topic_limited_to_an_unknown_modality(project):
    _private("topic/odd.md", "---\nkind: topic\ntopic: odd\nhook: x\napplicable:\n  - ghost\n---\n## principles\n\n###### odd-1\n> a rule (origin: x)\n")
    assert ("topic-applicable-unknown", "private:topic/odd.md") in {(f.id, f.file) for f in lint.lint(project)}


def test_a_hook_with_a_colon_is_quoted_and_a_broken_frontmatter_fails_with_the_path(project):
    path = edit.add(project, "topic/colon", "co-1", "x", hook="a frame: with a colon")
    assert pages.load("topic/colon").meta["hook"] == "a frame: with a colon" and path.exists()
    _private("topic/broken.md", "---\nkind: topic\ntopic: broken\nhook: a: b: c\n---\n")
    with pytest.raises(pages.GuideError, match="broken.md: invalid frontmatter"):
        pages.load("topic/broken")


def test_a_card_title_that_differs_from_the_artifact_name_prints_no_card_block(project):
    _artifact(project)
    card = project / "parla/artifacts/icra-paper/card.md"
    card.write_text(card.read_text().replace("# icra-paper", "# A different title"))
    out = show.show(project, "icra-paper", "introduction")
    assert "<card>" not in out and "A different title" not in out


def test_the_outline_works_when_parla_is_a_symlink_into_an_asset_store(project, tmp_path):
    store = tmp_path / "store"
    shutil.move(str(project / "parla"), str(store))
    (project / "parla").symlink_to(store)
    _artifact_in(project)
    out = show.show(project, "icra-paper", "introduction", outline=True)
    assert out.splitlines()[0].startswith("parla guide icra-paper")


def _artifact_in(root: Path) -> None:
    _artifact(root, extra_card="## decisions\n- keep it short\n")
