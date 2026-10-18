from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import make_artifact

from parla import jobs
from parla.config import ConfigError

T1 = datetime(2026, 10, 14, 15, 30, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 14, 16, 0, 0, tzinfo=UTC)


def _art(tmp_path: Path) -> Path:
    return make_artifact(tmp_path, "p", {"main.tex": "one\n", "section/a.tex": "A\n", "table/t.tex": "T\n"})


def test_start_snapshots_the_artifact_and_returns_a_utc_id(tmp_path):
    art = _art(tmp_path)
    (tmp_path / "shared.tex").write_text("shared\n")
    (art / "section" / "link.tex").symlink_to(tmp_path / "shared.tex")

    job_id = jobs.start(tmp_path, "p", "results", now=T1)

    assert job_id == "20261014T153000Z"
    snap = tmp_path / "parla/.parla/jobs" / job_id / "snapshot" / "artifacts" / "p"
    assert (snap / "section/a.tex").read_text() == "A\n"
    assert (snap / "section/link.tex").read_text() == "shared\n"
    assert not any(p.is_symlink() for p in snap.rglob("*"))
    assert jobs.active_snapshot(tmp_path, "p") == tmp_path / "parla/.parla/jobs" / job_id / "snapshot"
    assert 'part = "results"' in (snap.parents[2] / "job.toml").read_text()


def test_second_start_fails_and_a_missing_card_fails(tmp_path):
    _art(tmp_path)
    jobs.start(tmp_path, "p", now=T1)
    with pytest.raises(jobs.JobError, match="active job"):
        jobs.start(tmp_path, "p", now=T2)
    with pytest.raises(ConfigError, match="no card"):
        jobs.start(tmp_path, "ghost", now=T1)


def test_same_second_clash_fails(tmp_path):
    _art(tmp_path)
    make_artifact(tmp_path, "q", {"main.tex": "x"})
    jobs.start(tmp_path, "p", now=T1)
    with pytest.raises(FileExistsError):
        jobs.start(tmp_path, "q", now=T1)


def test_end_lists_changes_and_closes_the_job(tmp_path):
    art = _art(tmp_path)
    jobs.start(tmp_path, "p", now=T1)
    (art / "main.tex").write_text("two\n")
    (art / "section/b.tex").write_text("B\n")
    (art / "table/t.tex").unlink()

    lines = jobs.end(tmp_path, "p", now=T2)

    assert lines == [
        "changed artifacts/p/main.tex",
        "added artifacts/p/section/b.tex",
        "removed artifacts/p/table/t.tex",
    ]
    assert jobs.active_snapshot(tmp_path, "p") is None
    with pytest.raises(jobs.JobError, match="no active job"):
        jobs.end(tmp_path, "p")


def test_revert_restores_changed_and_removed_files_and_deletes_added(tmp_path):
    art = _art(tmp_path)
    jobs.start(tmp_path, "p", now=T1)
    (art / "main.tex").write_text("two\n")
    (art / "section/b.tex").write_text("B\n")
    (art / "table/t.tex").unlink()

    lines = jobs.revert(tmp_path, "p")

    assert sorted(lines) == [
        "removed artifacts/p/section/b.tex",
        "restored artifacts/p/main.tex",
        "restored artifacts/p/table/t.tex",
    ]
    assert (art / "main.tex").read_text() == "one\n"
    assert (art / "table/t.tex").is_file() and not (art / "section/b.tex").exists()
    assert jobs.changes(tmp_path, "p", tmp_path / "parla/.parla/jobs/20261014T153000Z/snapshot") == []


def test_revert_works_after_end_and_fails_without_a_job(tmp_path):
    art = _art(tmp_path)
    with pytest.raises(jobs.JobError, match="no job"):
        jobs.revert(tmp_path, "p")
    jobs.start(tmp_path, "p", now=T1)
    jobs.end(tmp_path, "p", now=T2)
    (art / "main.tex").write_text("three\n")
    jobs.revert(tmp_path, "p")
    assert (art / "main.tex").read_text() == "one\n"


def test_only_the_last_snapshot_is_kept(tmp_path):
    art = _art(tmp_path)
    first = jobs.start(tmp_path, "p", now=T1)
    jobs.end(tmp_path, "p", now=T1)
    (art / "main.tex").write_text("two\n")
    second = jobs.start(tmp_path, "p", now=T2)

    base = tmp_path / "parla/.parla/jobs"
    assert not (base / first / "snapshot").exists() and (base / first / "job.toml").is_file()
    assert (base / second / "snapshot").is_dir()
    assert jobs.active_snapshot(tmp_path, "p") == base / second / "snapshot"


def test_jobs_of_other_artifacts_are_independent(tmp_path):
    _art(tmp_path)
    make_artifact(tmp_path, "q", {"main.tex": "x"})
    jobs.start(tmp_path, "p", now=T1)
    jobs.start(tmp_path, "q", now=T2)
    assert jobs.active_snapshot(tmp_path, "p") != jobs.active_snapshot(tmp_path, "q")
    assert jobs.active_snapshot(tmp_path, "p").is_dir()


def test_outputs_stay_out_of_the_snapshot_and_the_change_list_and_survive_a_revert(tmp_path):
    art = _art(tmp_path)
    outputs = ("p.pdf", "p_diff.pdf", "p.png", "BUILD-ERROR.txt")
    for name in outputs:
        (art / name).write_text("old\n")
    job_id = jobs.start(tmp_path, "p", now=T1)
    snap = tmp_path / "parla/.parla/jobs" / job_id / "snapshot" / "artifacts" / "p"
    assert not any((snap / name).exists() for name in outputs)

    (art / "main.tex").write_text("two\n")
    (art / "p.pdf").write_text("new\n")
    assert jobs.end(tmp_path, "p") == ["changed artifacts/p/main.tex"]

    jobs.revert(tmp_path, "p")
    assert (art / "main.tex").read_text() == "one\n"
    assert all((art / name).exists() for name in outputs)


def test_topics_are_stored_validated_and_read_back(tmp_path):
    _art(tmp_path)
    with pytest.raises(jobs.JobError, match="unknown topic"):
        jobs.start(tmp_path, "p", topics=["ghost"], now=T1)
    jobs.start(tmp_path, "p", "results", ["positioning"], now=T1)
    assert jobs.active_topics(tmp_path, "p") == ["positioning"]
    assert 'topics = "positioning"' in (jobs.active_job(tmp_path, "p") / "job.toml").read_text()
    assert jobs.active_topics(tmp_path, "q") == []


def test_end_lists_the_verdicts_of_the_job(tmp_path):
    _art(tmp_path)
    jobs.start(tmp_path, "p", now=T1)
    (jobs.active_job(tmp_path, "p") / "verdicts.jsonl").write_text(
        '{"key": "cite-grounded#a41c9e", "verdict": "pass", "evidence": "ICE plots show"}\n'
        '{"key": "no-very#1b2c3d", "verdict": "na", "why": "a quotation"}\n'
    )
    assert jobs.end(tmp_path, "p", now=T2)[-2:] == ["pass cite-grounded#a41c9e ICE plots show", "na no-very#1b2c3d a quotation"]


def test_the_generated_bibliography_is_an_output_not_a_change(tmp_path):
    art = make_artifact(tmp_path, "p", {"main.tex": "one\n", "references.bib": "@article{a}\n"})
    jobs.start(tmp_path, "p", now=T1)
    (art / "references.bib").write_text("@article{a}\n@article{b}\n")
    (art / "main.tex").write_text("two\n")
    assert jobs.end(tmp_path, "p", now=T2) == ["changed artifacts/p/main.tex"]
    snap = tmp_path / "parla/.parla/jobs/20261014T153000Z/snapshot/artifacts/p"
    assert not (snap / "references.bib").exists()
