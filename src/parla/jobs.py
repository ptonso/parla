"""Jobs: a snapshot of an artifact taken at the start of a piece of work. The snapshot is the
diff baseline of every build in the job and the target of `revert`. See `specs/jobs.md`."""

from __future__ import annotations

import json
import shutil
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from . import config as config_mod
from .guides import pages as guide_pages
from .names import PROJECT_DIR, STATE_DIR, is_output

ID_FORMAT = "%Y%m%dT%H%M%SZ"


class JobError(Exception):
    """Raised when a job command cannot proceed."""


def _jobs_dir(root: Path) -> Path:
    return root / PROJECT_DIR / STATE_DIR / "jobs"


def _artifact_dir(root: Path, artifact: str) -> Path:
    return root / PROJECT_DIR / "artifacts" / artifact


def _read(job: Path) -> dict:
    with (job / "job.toml").open("rb") as fh:
        return tomllib.load(fh)


def _write(job: Path, meta: dict[str, str]) -> None:
    lines = [f'{key} = "{value}"' for key, value in meta.items()]
    (job / "job.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _jobs_of(root: Path, artifact: str) -> list[Path]:
    """The artifact's job folders, oldest first (ids sort chronologically)."""
    base = _jobs_dir(root)
    if not base.is_dir():
        return []
    return [j for j in sorted(base.iterdir()) if (j / "job.toml").is_file() and _read(j)["artifact"] == artifact]


def _active(root: Path, artifact: str) -> Path | None:
    open_jobs = [j for j in _jobs_of(root, artifact) if "ended" not in _read(j)]
    return open_jobs[-1] if open_jobs else None


def _stamp(now: datetime) -> str:
    return now.strftime(ID_FORMAT)


def start(
    root: Path, artifact: str, part: str | None = None, topics: list[str] | None = None, *, now: datetime | None = None
) -> str:
    config_mod.load_card(root, artifact)
    unknown = [t for t in topics or [] if t not in guide_pages.names("topic")]
    if unknown:
        raise JobError(f"unknown topic(s): {', '.join(unknown)} (have: {', '.join(guide_pages.names('topic')) or 'none'})")
    guide_pages.check_applicable(topics or [], config_mod.load_card(root, artifact).modality)
    if _active(root, artifact) is not None:
        raise JobError(f"'{artifact}' already has an active job; end it with `job end` first")
    now = now or datetime.now(UTC)
    job = _jobs_dir(root) / _stamp(now)
    previous = _jobs_of(root, artifact)
    job.mkdir(parents=True)  # a clash at the same second fails here
    source = _artifact_dir(root, artifact)
    shutil.copytree(
        source, job / "snapshot" / "artifacts" / artifact, symlinks=False,
        ignore=lambda folder, names: [n for n in names if Path(folder) == source and is_output(Path("artifacts", artifact, n))],
    )
    for old in previous:
        shutil.rmtree(old / "snapshot", ignore_errors=True)
    meta = {"artifact": artifact, **({"part": part} if part else {}), **({"topics": ",".join(topics)} if topics else {})}
    _write(job, {**meta, "started": now.isoformat(timespec="seconds")})
    return job.name


def is_active(root: Path, artifact: str) -> bool:
    return _active(root, artifact) is not None


def active_job(root: Path, artifact: str) -> Path | None:
    """The folder of the artifact's active job, or `None` without one."""
    return _active(root, artifact)


def active_topics(root: Path, artifact: str) -> list[str]:
    """The topics the captain chose for the active job; empty without a job or without topics."""
    job = _active(root, artifact)
    return [] if job is None else [t for t in _read(job).get("topics", "").split(",") if t]


def verdict_lines(root: Path, artifact: str) -> list[str]:
    """One line per verdict of the artifact's newest job: key, verdict and the evidence or reason."""
    jobs = _jobs_of(root, artifact)
    path = jobs[-1] / "verdicts.jsonl" if jobs else None
    if path is None or not path.is_file():
        return []
    return [
        f"{v['verdict']} {v['key']} {v.get('evidence') or v.get('why', '')}"
        for v in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    ]


def all_verdicts(root: Path) -> list[dict]:
    """Every verdict of every job."""
    base = _jobs_dir(root)
    out: list[dict] = []
    for path in sorted(base.glob("*/verdicts.jsonl")) if base.is_dir() else []:
        out += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return out


def active_snapshot(root: Path, artifact: str) -> Path | None:
    """The diff baseline of the artifact's active job, or `None` without one."""
    job = _active(root, artifact)
    return None if job is None else job / "snapshot"


def _files(base: Path, rel: Path) -> dict[str, Path]:
    return {
        p.relative_to(base).as_posix(): p
        for p in sorted(base.rglob("*"))
        if p.is_file() and not is_output(rel / p.relative_to(base))
    }


def changes(root: Path, artifact: str, snapshot: Path) -> list[tuple[str, str]]:
    """`(status, path)` for every file that differs from the snapshot; paths are relative to `parla/`."""
    rel = Path("artifacts") / artifact
    now = _files(root / PROJECT_DIR / rel, rel)
    then = _files(snapshot / rel, rel)
    out = [("added", p) for p in now if p not in then]
    out += [("removed", p) for p in then if p not in now]
    out += [("changed", p) for p in now if p in then and now[p].read_bytes() != then[p].read_bytes()]
    return sorted(((status, (rel / p).as_posix()) for status, p in out), key=lambda c: c[1])


def end(root: Path, artifact: str, *, now: datetime | None = None) -> list[str]:
    job = _active(root, artifact)
    if job is None:
        raise JobError(f"'{artifact}' has no active job")
    lines = [f"{status} {path}" for status, path in changes(root, artifact, job / "snapshot")]
    _write(job, {**_read(job), "ended": (now or datetime.now(UTC)).isoformat(timespec="seconds")})
    return lines + verdict_lines(root, artifact)


def revert(root: Path, artifact: str) -> list[str]:
    jobs = _jobs_of(root, artifact)
    if not jobs:
        raise JobError(f"'{artifact}' has no job to revert")
    snapshot = jobs[-1] / "snapshot"
    if not snapshot.is_dir():
        raise JobError(f"the snapshot of job {jobs[-1].name} is missing")
    lines = [
        f"{'removed' if status == 'added' else 'restored'} {path}"
        for status, path in changes(root, artifact, snapshot)
    ]
    target = _artifact_dir(root, artifact)
    for child in target.iterdir():
        if not is_output(Path("artifacts", artifact, child.name)):
            shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
    shutil.copytree(snapshot / "artifacts" / artifact, target, symlinks=False, dirs_exist_ok=True)
    return lines
