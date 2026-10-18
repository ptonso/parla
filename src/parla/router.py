"""What does not depend on the format: the check-then-build order, the diff baseline and the
watch loop. Engines are reached only through the registry. See `specs/engines.md#router-behavior`."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tarfile
import time
from collections.abc import Callable
from pathlib import Path

import dataclasses

from . import config as config_mod
from . import constraints, jobs, template
from .checks import CheckFailed, Finding, shared
from .checks.ids import is_constraint
from .config import ConfigError
from .engines import registry
from .engines.base import BuildError, Built, Engine, EngineError, Pages
from .guides import pages as guide_pages
from .names import BUILD_ERROR, EXPORT_DIR, NAME, PROJECT_DIR, STATE_DIR, is_output

POLL_SECONDS = 1.0
DEBOUNCE_SECONDS = 2.0
WATCH_SUFFIXES = {".tex", ".bib", ".sty", ".cls", ".png", ".jpg", ".jpeg", ".pdf", ".md", ".svg"}


def _engine(root: Path, artifact: str) -> Engine:
    return registry.get(config_mod.load_card(root, artifact))


def init_artifact(
    root: Path, name: str, modality: str, audience: str, *, force: bool = False
) -> list[Path]:
    """Write the card and the starter files of the engine the modality page names. The audience
    page must exist; its `setup` for the modality shapes the starter."""
    for kind, page in (("modality", modality), ("audience", audience)):
        if page not in guide_pages.names(kind):
            raise guide_pages.GuideError(
                f"unknown {kind} '{page}' (have: {', '.join(guide_pages.names(kind)) or 'none; add pages to the guides'})"
            )
    engine = guide_pages.modality(modality).meta.get("engine")
    if engine is None:
        raise ConfigError(f"modality page '{modality}' names no engine")
    setup = (guide_pages.load(f"audience/{audience}").meta.get("setup") or {}).get(modality)
    starter = registry.named(engine).starter(root, name, modality, setup)
    keys = {
        "modality": modality, "audience": audience, "engine": engine, **starter.card_keys,
        "entrypoint": starter.entrypoint, "phase": "drafting", "derived-from": "null",
    }
    card = "---\n" + "".join(f"{k}: {v}\n" for k, v in keys.items()) + f"---\n# {name}\n"
    return template.init_artifact(root, name, card, starter.files, force)


def blocking(findings: list[Finding]) -> bool:
    """True when an engine check reported an error. Constraint findings never stop a build."""
    return any(f.severity == "error" and not is_constraint(f) for f in findings)


def check(root: Path, artifact: str, *, all_lines: bool = False) -> list[Finding]:
    """The suite in file and line order: the engine's findings and the constraints, without the
    ids in `[checks].ignore`. A card that does not validate is the only finding: no engine can be
    chosen from it."""
    invalid = shared.card_invalid(root, artifact)
    if invalid is not None:
        return [invalid]
    ignore = config_mod.load(root).ignore
    findings = [*_engine(root, artifact).check(root, artifact), *constraints.run(root, artifact, all_lines=all_lines)]
    return sorted((f for f in findings if f.id not in ignore), key=lambda f: (f.file, f.line))


def resolve_baseline(
    root: Path, artifact: str, diff_from: str | None = None, no_diff: bool = False
) -> Path | None:
    if no_diff:
        return None
    if diff_from is None:
        return jobs.active_snapshot(root, artifact)
    if Path(diff_from).is_dir():
        return Path(diff_from)
    return _git_baseline(root, artifact, diff_from)


def _git_baseline(root: Path, artifact: str, ref: str) -> Path:
    """The artifact folder at git `ref`, extracted into a directory that mirrors the project layout."""
    folder = (root / PROJECT_DIR / "artifacts" / artifact).resolve()
    top = subprocess.run(
        ["git", "-C", str(folder), "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    )
    if top.returncode != 0:
        raise ConfigError(f"--diff-from '{ref}' is not a directory and {folder} is not inside a git work tree")
    rel = folder.relative_to(Path(top.stdout.strip()).resolve()).as_posix()
    archive = subprocess.run(
        ["git", "-C", top.stdout.strip(), "archive", "--format=tar", ref, "--", rel],
        capture_output=True, check=False,
    )
    if archive.returncode != 0:
        raise ConfigError(f"git archive {ref} failed: {archive.stderr.decode(errors='replace').strip()}")
    baseline = root / PROJECT_DIR / STATE_DIR / "baseline"
    target = baseline / "artifacts" / artifact
    if baseline.exists():
        shutil.rmtree(baseline)
    target.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        for member in tar.getmembers():
            member.name = member.name.removeprefix(rel).lstrip("/")
            if member.name:
                tar.extract(member, target, filter="data")
    return baseline


def build(
    root: Path,
    artifact: str,
    *,
    diff_from: str | None = None,
    no_diff: bool = False,
    all_lines: bool = False,
    on_output: Callable[[str], None] = print,
) -> Built:
    """`prepare`, the checks, then the engine's build, then the post-build findings. An engine
    error finding raises `CheckFailed`; the suite of the build is in `Built.findings`.
    A failed check or build leaves its errors in `artifacts/<artifact>/BUILD-ERROR.txt`, and the
    next successful build removes the file."""
    notice = root / PROJECT_DIR / "artifacts" / artifact / BUILD_ERROR
    try:
        built = _build(root, artifact, diff_from, no_diff, all_lines, on_output)
    except (CheckFailed, BuildError) as exc:
        if notice.parent.is_dir():
            notice.write_text(
                f"This is a generated file: {NAME} rewrites it on every failed build and deletes it when a build succeeds.\n\n{exc}\n",
                encoding="utf-8",
            )
        raise
    notice.unlink(missing_ok=True)
    return built


def _build(
    root: Path, artifact: str, diff_from: str | None, no_diff: bool, all_lines: bool, on_output: Callable[[str], None]
) -> Built:
    invalid = shared.card_invalid(root, artifact)
    if invalid is not None:
        on_output(invalid.format())
        raise CheckFailed([invalid])
    engine = _engine(root, artifact)
    engine.prepare(root)
    findings = check(root, artifact, all_lines=all_lines)
    if blocking(findings):
        for finding in findings:
            on_output(finding.format())
        raise CheckFailed([f for f in findings if not is_constraint(f)])
    built = engine.build(root, artifact, resolve_baseline(root, artifact, diff_from, no_diff))
    ignore = config_mod.load(root).ignore
    late = [f for f in engine.post_build(root, artifact) if f.id not in ignore]
    suite = sorted([*findings, *late], key=lambda f: (f.file, f.line))
    for line in constraints.report(suite, artifact):
        on_output(line)
    return dataclasses.replace(built, findings=tuple(suite))


def export(root: Path, artifact: str, tag: str, force: bool) -> Path:
    engine = _engine(root, artifact)
    engine.prepare(root)
    return engine.export(root, artifact, tag, force)


def pages(root: Path, artifact: str, language: str | None = None) -> Pages:
    """The page counts of the artifact's published output in `language` (default: the artifact's
    own); fails for an engine with no pages."""
    engine = _engine(root, artifact)
    found = engine.pages(root, artifact, language)
    if found is None:
        raise EngineError(f"engine '{engine.name}' has no pages; use --words")
    return found


def _snapshot(base: Path) -> dict[Path, float]:
    """Map of watched source file -> mtime, excluding `.parla/`, `export/` and the build outputs
    of each artifact."""
    excluded = {EXPORT_DIR, STATE_DIR}
    snap: dict[Path, float] = {}
    for current, dirnames, filenames in os.walk(base, followlinks=False):
        rel = Path(current).relative_to(base)
        if rel.parts and rel.parts[0] in excluded:
            dirnames[:] = []
            continue
        for name in filenames:
            path = Path(current) / name
            if path.suffix.lower() in WATCH_SUFFIXES and not is_output(path.relative_to(base)):
                snap[path] = path.stat().st_mtime
    return snap


def watch(
    root: Path,
    artifact: str,
    *,
    diff_from: str | None = None,
    no_diff: bool = False,
    all_lines: bool = False,
    on_output: Callable[[str], None] = print,
) -> None:
    """Foreground loop: build, then rebuild on any source change. A failing cycle prints its
    findings and the loop continues. Ctrl-C exits."""
    base = root / PROJECT_DIR

    def cycle() -> None:
        try:
            built = build(root, artifact, diff_from=diff_from, no_diff=no_diff, all_lines=all_lines, on_output=on_output)
            for path in (*built.published, *([built.diff] if built.diff else []), *built.diffs):
                on_output(f"[{NAME}] built {path}")
        except CheckFailed:
            on_output(f"[{NAME}] checks failed; waiting for a change")
        except EngineError as exc:
            on_output(f"[{NAME}] {exc}")

    cycle()
    last = _snapshot(base)
    on_output(f"[{NAME}] watching {PROJECT_DIR}/ for changes (Ctrl-C to stop)")
    while True:
        time.sleep(POLL_SECONDS)
        now = _snapshot(base)
        if now == last:
            continue
        while True:  # debounce: wait until writes settle
            time.sleep(DEBOUNCE_SECONDS)
            settled = _snapshot(base)
            if settled == now:
                break
            now = settled
        last = now
        cycle()
