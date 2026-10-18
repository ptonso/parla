"""Constraints: stores, the runner, locators, verdicts, and the suite in check and build."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from conftest import make_artifact

from parla import cli, constraints, jobs, router
from parla.checks import Finding
from parla.constraints import ConstraintError, add
from parla.engines.latex import checks as latex_checks

VERY = {
    "id": "no-very", "kind": "regex", "description": "no 'very'", "regex": r"\bvery\b",
    "examples": {"match": ["a very long way"], "ok": ["a long way"]},
}

TEX = """\
\\section{Intro}
The model is very fast~\\cite{goldstein2015}. It reaches 91.2 accuracy.

% a very commented line
See Fig.~\\ref{fig:a}.

\\begin{figure}
\\caption{Accuracy over runs.}
\\label{fig:a}
\\end{figure}

\\begin{frame}{Results}
Short.
\\end{frame}
"""


def _art(tmp_path, text=TEX):
    return make_artifact(tmp_path, "p", {"main.tex": text})


def _ids(findings):
    return [(f.id, f.severity, f.line) for f in findings]


def test_add_validates_the_entry(tmp_path):
    with pytest.raises(ConstraintError, match="missing field"):
        add({"id": "x"})
    with pytest.raises(ConstraintError, match="does not compile"):
        add({**VERY, "regex": "("})
    with pytest.raises(ConstraintError, match="misses its match example"):
        add({**VERY, "examples": {"match": ["nothing"], "ok": ["fine"]}})
    with pytest.raises(ConstraintError, match="hits its ok example"):
        add({**VERY, "examples": {"match": ["very"], "ok": ["very"]}})
    with pytest.raises(ConstraintError, match="non-empty"):
        add({**VERY, "examples": {"match": ["very"], "ok": []}})
    with pytest.raises(ConstraintError, match="locator"):
        add({"id": "p", "kind": "probe", "description": "d", "locator": "ghost"})
    assert add(VERY) == "no-very"
    with pytest.raises(ConstraintError, match="already exists"):
        add(VERY)
    with pytest.raises(ConstraintError, match="already exists"):
        add({**VERY, "id": "fig-ref-form"})  # the public fixture
    entry = constraints.load()["no-very"]
    assert (entry["status"], entry["store"], entry["severity"]) == ("active", "private", "error")


def test_mark_retires_a_private_constraint_and_refuses_a_public_one(tmp_path):
    add(VERY)
    constraints.mark("no-very", "retired")
    assert constraints.load()["no-very"]["status"] == "retired"
    with pytest.raises(ConstraintError, match="public constraint"):
        constraints.mark("fig-ref-form", "retired")
    assert any(line.startswith("no-very regex error retired private") for line in constraints.list_lines())


def test_a_regex_hit_is_reported_with_its_line_and_comments_are_masked(tmp_path):
    _art(tmp_path)
    add(VERY)
    found = constraints.run(tmp_path, "p")
    hits = [f for f in found if f.id == "constraint/no-very"]
    assert [(f.line, f.severity) for f in hits] == [(2, "error")]
    assert hits[0].file == "artifacts/p/main.tex" and "(key no-very#" in hits[0].message


def test_only_the_lines_changed_in_the_job_are_reported(tmp_path):
    art = _art(tmp_path)
    add(VERY)
    jobs.start(tmp_path, "p")
    assert [f.line for f in constraints.run(tmp_path, "p") if f.id == "constraint/no-very"] == []
    (art / "main.tex").write_text(TEX + "\nA very new line.\n")
    new = TEX.count("\n") + 2
    assert [f.line for f in constraints.run(tmp_path, "p") if f.id == "constraint/no-very"] == [new]
    assert [f.line for f in constraints.run(tmp_path, "p", all_lines=True) if f.id == "constraint/no-very"] == [2, new]


def test_applies_filters_by_modality_and_engine(tmp_path):
    _art(tmp_path)
    add({**VERY, "applies": {"modality": ["talk"]}})
    assert [f for f in constraints.run(tmp_path, "p") if f.id == "constraint/no-very"] == []


def test_each_locator_finds_its_spans(tmp_path):
    _art(tmp_path)
    for locator in constraints.LOCATORS:
        add({"id": f"q-{locator}", "kind": "probe", "description": f"question {locator}", "locator": locator})
    found = constraints.run(tmp_path, "p")
    by: dict[str, Finding] = {}
    for f in found:
        if f.id.startswith("constraint/q-"):
            by.setdefault(f.id.split("-", 1)[1], f)
    assert all(f.severity == "probe" for f in by.values())
    assert "goldstein2015" in by["citation"].message and "parla tool source goldstein2015" in by["citation"].message
    assert "91.2" in by["number"].message
    assert "Accuracy over runs." in by["caption"].message and "fig:a" in by["caption"].message
    assert "Results" in by["frame"].message
    assert by["paragraph"].line == 1 and "\\section" not in by["citation"].message.split("span:")[1]


def test_a_verdict_resolves_a_probe_until_the_span_changes(tmp_path):
    art = _art(tmp_path)
    add({"id": "grounded", "kind": "probe", "description": "supported?", "locator": "citation"})
    jobs.start(tmp_path, "p")
    (art / "main.tex").write_text(TEX.replace("is very fast", "is fast"))
    (probe,) = [f for f in constraints.run(tmp_path, "p") if f.severity == "probe"]
    k = probe.message.split("key: ")[1].split()[0]
    with pytest.raises(ConstraintError, match="--pass needs --evidence"):
        constraints.resolve(tmp_path, "p", k, verdict="pass", text=None)
    with pytest.raises(ConstraintError, match="--na needs --why"):
        constraints.resolve(tmp_path, "p", k, verdict="na", text="")
    with pytest.raises(ConstraintError, match="no finding has the key"):
        constraints.resolve(tmp_path, "p", "grounded#000000", verdict="na", text="x")
    constraints.resolve(tmp_path, "p", k, verdict="pass", text="Goldstein sec. 2: ICE plots")
    assert [f.severity for f in constraints.run(tmp_path, "p") if f.id == "constraint/grounded"] == ["resolved"]
    (art / "main.tex").write_text(TEX.replace("is very fast", "is much faster"))
    assert [f.severity for f in constraints.run(tmp_path, "p") if f.id == "constraint/grounded"] == ["probe"]
    assert any("pass" in line and "Goldstein" in line for line in jobs.verdict_lines(tmp_path, "p"))


def test_a_regex_hit_accepts_only_na_and_resolve_needs_a_job(tmp_path):
    _art(tmp_path)
    add(VERY)
    (hit,) = [f for f in constraints.run(tmp_path, "p") if f.id == "constraint/no-very"]
    k = hit.message.split("(key ")[1].rstrip(")")
    with pytest.raises(ConstraintError, match="no active job"):
        constraints.resolve(tmp_path, "p", k, verdict="na", text="quoted on purpose")
    jobs.start(tmp_path, "p")
    with pytest.raises(ConstraintError, match="fixed in the text"):
        constraints.resolve(tmp_path, "p", k, verdict="pass", text="x")
    constraints.resolve(tmp_path, "p", k, verdict="na", text="a quotation")
    assert constraints.run(tmp_path, "p", all_lines=True)[0].severity in ("resolved", "warning", "error")


def test_the_report_counts_and_the_probe_limit(tmp_path, monkeypatch):
    findings = [Finding("a.tex", n, "probe", "constraint/q", f"q {n}") for n in range(1, 4)]
    findings += [Finding("a.tex", 9, "error", "constraint/e", "bad"), Finding("a.tex", 10, "resolved", "constraint/e", "pass k")]
    monkeypatch.setenv("PARLA_CONFIG", str(tmp_path / "c.toml"))
    (tmp_path / "c.toml").write_text("[guides]\nmax_probes = 2\n")
    lines = constraints.report(findings)
    assert lines[-1] == "suite: 1 fail, 3 probes open, 1 resolved"
    assert "1 more probes" in lines[-2] and not any("q 3" in line for line in lines)
    assert constraints.red(findings) and not constraints.red([findings[-1]])


def test_hints_and_the_ignore_list(tmp_path):
    from parla import template

    template.init(tmp_path)
    _art(tmp_path)
    assert constraints.hints(tmp_path, "p") == ["a figure is referenced as Figure~\\ref"]
    assert [f.id for f in router.check(tmp_path, "p")].count("constraint/fig-ref-form") == 1
    toml = tmp_path / "parla/parla.toml"
    toml.write_text(toml.read_text() + '\n[checks]\nignore = ["constraint/fig-ref-form"]\n')
    assert "constraint/fig-ref-form" not in [f.id for f in router.check(tmp_path, "p")]
    toml.write_text(toml.read_text().replace("constraint/fig-ref-form", "constraint/ghost"))
    with pytest.raises(Exception, match="no known check"):
        router.check(tmp_path, "p")


def test_lint_reports_failed_examples_and_constraints_to_refine(tmp_path):
    _art(tmp_path)
    add(VERY)
    path = constraints._private_path()
    path.write_text(path.read_text().replace("a very long way", "a quick way"))
    assert [f.id for f in constraints.lint(tmp_path, distill_min=3)] == ["constraint-example-failed"]
    path.write_text(path.read_text().replace("a quick way", "a very long way"))
    for n in range(3):
        jobs.start(tmp_path, "p", now=datetime(2026, 10, 14, 15, 30, n, tzinfo=UTC))
        job = jobs.active_job(tmp_path, "p")
        (job / "verdicts.jsonl").write_text(json.dumps({"key": f"no-very#{n:06d}", "verdict": "na", "why": "quote"}) + "\n")
        jobs.end(tmp_path, "p")
    assert [f.id for f in constraints.lint(tmp_path, distill_min=3)] == ["constraint-refine"]


def test_the_check_command_exit_codes_and_resolve(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "parla").mkdir(exist_ok=True)
    from parla import template

    template.init(tmp_path)
    _art(tmp_path, TEX.replace("~\\cite{goldstein2015}", ""))
    add({**VERY, "severity": "warning"})
    add({"id": "grounded", "kind": "probe", "description": "supported?", "locator": "number"})
    capsys.readouterr()
    assert cli.main(["check", "p"]) == 4  # an open probe keeps the suite red
    out = capsys.readouterr().out
    assert out.splitlines()[-1] == "suite: 0 fail, 1 probes open, 0 resolved"
    k = out.split("key: ")[1].split()[0]
    assert cli.main(["check", "p", "--resolve", k, "--na", "--why", "x"]) == 3  # no active job
    assert cli.main(["job", "start", "p"]) == 0
    assert cli.main(["check", "p", "--resolve", k, "--pass"]) == 3  # no evidence
    assert cli.main(["check", "p", "--resolve", k, "--pass", "--evidence", "line"]) == 0
    assert cli.main(["constraint", "list"]) == 0


def test_log_findings_read_overfull_boxes_and_frames():
    log = (
        "Document Class: beamer 2024\n"
        "Overfull \\hbox (12.5pt too wide) in paragraph at lines 45--47\n"
        "Overfull \\hbox (2.0pt too wide) in paragraph at lines 50--51\n"
        "Overfull \\vbox (30.1pt too high) has occurred while \\output is active\n"
        "[3]\n"
    )
    found = latex_checks.log_findings(log, "artifacts/p/main.tex")
    assert [(f.id, f.line) for f in found] == [("overfull-line", 45), ("frame-overflow", 1)]
    assert "page 3" in found[1].message
    assert [f.id for f in latex_checks.log_findings(log.replace("Document Class: beamer", "Document Class: article"), "m")] == ["overfull-line"]


def test_files_scope_a_constraint_to_part_of_the_artifact(tmp_path):
    art = make_artifact(tmp_path, "p", {"main.tex": "a: colon here\n", "abstract/abstract.tex": "an abstract: with a colon\n"})
    add({"id": "no-colon", "kind": "regex", "description": "no colon", "regex": ":",
         "applies": {"files": ["abstract/*.tex"]},
         "examples": {"match": ["a: b"], "ok": ["a b"]}})
    found = [f for f in constraints.run(tmp_path, "p") if f.id == "constraint/no-colon"]
    assert [f.file for f in found] == ["artifacts/p/abstract/abstract.tex"]
    assert art.exists()


def test_edit_updates_fields_validates_and_refuses_a_public_or_unknown_constraint(tmp_path):
    _art(tmp_path)
    add(VERY)
    constraints.edit("no-very", {"applies": {"files": ["main.tex"]}, "severity": "warning"})
    entry = constraints.load()["no-very"]
    assert (entry["severity"], entry["applies"]) == ("warning", {"files": ["main.tex"]})
    with pytest.raises(ConstraintError, match="misses its match example"):
        constraints.edit("no-very", {"regex": r"\bnever\b"})
    with pytest.raises(ConstraintError, match="cannot be edited"):
        constraints.edit("no-very", {"kind": "probe"})
    with pytest.raises(ConstraintError, match="public constraint"):
        constraints.edit("fig-ref-form", {"severity": "warning"})
    with pytest.raises(ConstraintError, match="unknown constraint"):
        constraints.edit("ghost", {})


def test_the_report_says_how_to_answer_a_finding_and_job_end_prints_the_suite(tmp_path, monkeypatch, capsys):
    findings = [Finding("a.tex", 1, "probe", "constraint/q", "q\n    key: q#abc123")]
    lines = constraints.report(findings, "p")
    assert lines[-2].startswith("answer a finding by its key: parla check p --resolve <key> --pass --evidence")
    assert lines[-1] == "suite: 0 fail, 1 probes open, 0 resolved"
    assert not any("answer a finding" in line for line in constraints.report([Finding("a.tex", 1, "error", "cite-unresolved", "m")], "p"))
    monkeypatch.chdir(tmp_path)
    from parla import template

    template.init(tmp_path)
    _art(tmp_path, TEX.replace("~\\cite{goldstein2015}", ""))
    add({"id": "q", "kind": "probe", "description": "d", "locator": "number"})
    assert cli.main(["job", "start", "p"]) == 0
    capsys.readouterr()
    assert cli.main(["job", "end", "p"]) == 0  # the job changed nothing, so the suite is empty
    assert capsys.readouterr().out.splitlines()[-1] == "suite: 0 fail, 0 probes open, 0 resolved"


def test_resolving_exits_0_even_while_the_suite_is_still_red(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from parla import template

    template.init(tmp_path)
    _art(tmp_path, "One probe here with 91 percent.\n\nAnother paragraph with 42 percent.\n")
    add({"id": "q", "kind": "probe", "description": "d", "locator": "number"})
    assert cli.main(["job", "start", "p"]) == 0
    (tmp_path / "parla/artifacts/p/main.tex").write_text("One probe here with 91 percent.\n\nAnother paragraph with 43 percent.\n")
    capsys.readouterr()
    assert cli.main(["check", "p"]) == 4
    first = capsys.readouterr().out.split("key: ")[1].split()[0]
    assert cli.main(["check", "p", "--resolve", first, "--pass", "--evidence", "line"]) == 0
    out = capsys.readouterr().out
    assert "resolved" in out.splitlines()[-1] and "probes open" in out.splitlines()[-1]
