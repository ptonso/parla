"""Constraints: regex constraints and probes that run as a test suite inside `check` and `build`.
See `specs/constraints.md`."""

from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from . import config as config_mod
from . import jobs
from .checks import Finding, shared
from .checks.finding import Severity
from .checks.ids import finding
from .engines import registry
from .guides import pages
from .names import NAME, PROJECT_DIR

FILE = "constraints.jsonl"
KINDS = ("regex", "probe")
STATUSES = ("active", "retired")
SEVERITIES = ("error", "warning")
APPLIES = ("modality", "engine", "audience", "files")
FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}
LOCATORS = ("citation", "number", "caption", "paragraph", "frame")
REQUIRED = ("id", "kind", "description")

_CITE_RE = re.compile(r"\\[A-Za-z]*cite[A-Za-z]*\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}")
_CAPTION_RE = re.compile(r"\\caption(?:\[[^\]]*\])?\{")
_LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
_FRAME_RE = re.compile(r"\\begin\{frame\}(.*?)\\end\{frame\}", re.DOTALL)
_FRAMETITLE_RE = re.compile(r"\\frametitle\{([^}]*)\}|\\begin\{frame\}(?:<[^>]*>)?(?:\[[^\]]*\])?\{([^}]*)\}")
_DIGIT_RE = re.compile(r"\d")
_SKIPPED_ARGS_RE = re.compile(
    r"\\(?:[A-Za-z]*cite[A-Za-z]*|[a-z]*ref|eqref|label|includegraphics|input|include|url|href|bibliography\w*|usepackage|documentclass|setlength|geometry)\*?(?:\[[^\]]*\])*\{[^}]*\}"
)
_PARAGRAPH_BREAK_RE = re.compile(r"\n\s*\n+")
_STRUCTURAL_LINE_RE = re.compile(r"[ \t]*\\(?:chapter|section|subsection|subsubsection|paragraph|begin|end|label|item)\b[^\n]*\n")


class ConstraintError(Exception):
    """A constraint command cannot proceed."""


@dataclass(frozen=True)
class Hit:
    finding: Finding
    key: str
    kind: str


def _public_path() -> Path:
    return pages.PUBLIC_ROOT / FILE


def _private_path() -> Path:
    return config_mod.guides_private() / FILE


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load() -> dict[str, dict]:
    """The current state of every constraint of both stores: its lines folded in order. Each entry
    carries `store`, `public` or `private`."""
    out: dict[str, dict] = {}
    for store, path in (("public", _public_path()), ("private", _private_path())):
        for entry in _lines(path):
            current = out.setdefault(entry["id"], {"store": store})
            if current["store"] != store:
                raise ConstraintError(f"constraint id '{entry['id']}' is defined in both stores")
            current.update(entry)
    return out


def _check_regex(entry: dict) -> None:
    flags = entry.get("flags", "")
    if set(flags) - set(FLAGS):
        raise ConstraintError(f"flags must be a subset of {''.join(FLAGS)}, got '{flags}'")
    try:
        pattern = re.compile(entry["regex"], _flags(flags))
    except re.error as exc:
        raise ConstraintError(f"the regex does not compile: {exc}") from exc
    examples = entry.get("examples") or {}
    if not examples.get("match") or not examples.get("ok"):
        raise ConstraintError("a regex constraint needs examples with a non-empty `match` and `ok` list")
    for text in examples["match"]:
        if not pattern.search(text):
            raise ConstraintError(f"the regex misses its match example: {text!r}")
    for text in examples["ok"]:
        if pattern.search(text):
            raise ConstraintError(f"the regex hits its ok example: {text!r}")


def _flags(flags: str) -> int:
    value = 0
    for char in flags:
        value |= FLAGS[char]
    return value


def add(payload: dict, *, today: date | None = None) -> str:
    missing = [k for k in REQUIRED if not payload.get(k)]
    if missing:
        raise ConstraintError(f"missing field(s): {', '.join(missing)}")
    if payload["kind"] not in KINDS:
        raise ConstraintError(f"kind must be one of {', '.join(KINDS)}")
    severity = payload.get("severity", "error")
    if severity not in SEVERITIES:
        raise ConstraintError(f"severity must be one of {', '.join(SEVERITIES)}")
    if payload["id"] in load():
        raise ConstraintError(f"constraint id '{payload['id']}' already exists")
    unknown = set(payload.get("applies") or {}) - set(APPLIES)
    if unknown:
        raise ConstraintError(f"unknown applies key(s): {', '.join(sorted(unknown))}")
    if payload["kind"] == "regex":
        if not payload.get("regex"):
            raise ConstraintError("a regex constraint needs `regex`")
        _check_regex(payload)
    elif payload.get("locator") not in LOCATORS:
        raise ConstraintError(f"a probe needs a locator, one of {', '.join(LOCATORS)}")
    entry = {
        "hint": False, "evidence": [], "origin": "", "applies": {}, **payload,
        "severity": severity, "status": "active", "date": (today or datetime.now(UTC).date()).isoformat(),
    }
    _append(entry)
    return entry["id"]


def _append(entry: dict) -> None:
    path = _private_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def edit(constraint_id: str, fields: dict) -> None:
    """Updates fields of a private constraint. The merged entry is validated as `add` validates, and
    the update is appended, so the earlier state stays in the file."""
    entry = load().get(constraint_id)
    if entry is None:
        raise ConstraintError(f"unknown constraint '{constraint_id}'")
    if entry["store"] == "public":
        raise ConstraintError(f"'{constraint_id}' is a public constraint; mute it with constraint/{constraint_id} in [checks].ignore")
    if {"id", "kind", "store", "status", "date"} & set(fields):
        raise ConstraintError("id, kind, status and date cannot be edited")
    merged = {**entry, **fields}
    if set(merged.get("applies") or {}) - set(APPLIES):
        raise ConstraintError(f"unknown applies key(s): {', '.join(sorted(set(merged['applies']) - set(APPLIES)))}")
    if merged.get("severity", "error") not in SEVERITIES:
        raise ConstraintError(f"severity must be one of {', '.join(SEVERITIES)}")
    if merged["kind"] == "regex":
        _check_regex(merged)
    elif merged.get("locator") not in LOCATORS:
        raise ConstraintError(f"a probe needs a locator, one of {', '.join(LOCATORS)}")
    _append({"id": constraint_id, **fields})


def mark(constraint_id: str, status: str) -> None:
    if status not in STATUSES:
        raise ConstraintError(f"unknown status '{status}' (have: {', '.join(STATUSES)})")
    entry = load().get(constraint_id)
    if entry is None:
        raise ConstraintError(f"unknown constraint '{constraint_id}'")
    if entry["store"] == "public":
        raise ConstraintError(f"'{constraint_id}' is a public constraint; mute it with constraint/{constraint_id} in [checks].ignore")
    _append({"id": constraint_id, "status": status})


def list_lines(kind: str | None = None, status: str | None = None) -> list[str]:
    return [
        f"{c['id']} {c['kind']} {c.get('severity', 'error')} {c['status']} {c['store']} {c['description']}"
        for c in load().values()
        if (kind is None or c["kind"] == kind) and (status is None or c["status"] == status)
    ]


def _applies(entry: dict, modality: str, engine: str, audience: str) -> bool:
    wanted = entry.get("applies") or {}
    return all(not wanted.get(k) or v in wanted[k] for k, v in (("modality", modality), ("engine", engine), ("audience", audience)))


def _in_files(entry: dict, inside: str) -> bool:
    """True when the constraint has no `files` globs, or one matches `inside`, the path within the artifact."""
    globs = (entry.get("applies") or {}).get("files")
    return not globs or any(fnmatch.fnmatch(inside, g) for g in globs)


def active(root: Path, artifact: str) -> list[dict]:
    card = config_mod.load_card(root, artifact)
    return [c for c in load().values() if c["status"] == "active" and _applies(c, card.modality, card.engine, card.audience)]


def hint_entries(root: Path, artifact: str) -> list[dict]:
    return [c for c in active(root, artifact) if c.get("hint")]


def hints(root: Path, artifact: str) -> list[str]:
    return [c["description"] for c in hint_entries(root, artifact)]


def key(constraint_id: str, span_text: str) -> str:
    return f"{constraint_id}#{hashlib.sha1(span_text.strip().encode()).hexdigest()[:6]}"


def _changed_lines(old: str, new: str) -> set[int]:
    """The 1-based lines of `new` that are not in `old`."""
    out: set[int] = set()
    matcher = difflib.SequenceMatcher(None, old.splitlines(), new.splitlines(), autojunk=False)
    for tag, _, _, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "insert"):
            out.update(range(j1 + 1, j2 + 1))
    return out


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _blank_args(text: str) -> str:
    return _SKIPPED_ARGS_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)


def _sentence(text: str, start: int, end: int) -> tuple[int, int]:
    """The sentence around `[start, end)`, without the structural command lines that precede it."""
    from .tools import claims

    left, right = claims._extract_sentence_bounds(text, start, end)
    while (m := _STRUCTURAL_LINE_RE.match(text, left, right)) and m.end() < start:
        left = m.end()
    return left, right


def _spans(locator: str, text: str) -> list[tuple[int, int, str]]:
    """`(start offset, end offset, extra)` of each span a locator finds in `text`."""
    spans: dict[tuple[int, int], str] = {}
    if locator == "citation":
        keys: dict[tuple[int, int], list[str]] = {}
        for m in _CITE_RE.finditer(text):
            found = [k.strip() for k in m.group(1).split(",") if k.strip()]
            keys.setdefault(_sentence(text, m.start(), m.end()), []).extend(found)
        spans = {bounds: ", ".join(found) for bounds, found in keys.items()}
    elif locator == "number":
        for m in _DIGIT_RE.finditer(_blank_args(text)):
            spans[_sentence(text, m.start(), m.end())] = ""
    elif locator == "caption":
        for m in _CAPTION_RE.finditer(text):
            depth, i = 1, m.end()
            while i < len(text) and depth:
                depth += (text[i] == "{") - (text[i] == "}")
                i += 1
            label = _LABEL_RE.search(text, i, i + 300)
            spans[(m.end(), i - 1)] = label.group(1) if label else ""
    elif locator == "paragraph":
        start = 0
        for brk in [*_PARAGRAPH_BREAK_RE.finditer(text), None]:
            end = brk.start() if brk else len(text)
            body = re.sub(r"\\[A-Za-z]+\*?", " ", text[start:end])
            if len(body.split()) >= 5:
                spans[(start, end)] = ""
            start = brk.end() if brk else end
    elif locator == "frame":
        for m in _FRAME_RE.finditer(text):
            title = _FRAMETITLE_RE.search(text[m.start():m.end()])
            spans[(m.start(), m.end())] = next((g for g in (title.groups() if title else ()) if g), "")
    return [(a, b, extra) for (a, b), extra in sorted(spans.items()) if text[a:b].strip()]


def _hits(root: Path, artifact: str, all_lines: bool) -> list[Hit]:
    entries = active(root, artifact)
    if not entries:
        return []
    card = config_mod.load_card(root, artifact)
    engine = registry.get(card)
    base = root / PROJECT_DIR
    snapshot = None if all_lines else jobs.active_snapshot(root, artifact)
    hits: list[Hit] = []
    own = f"artifacts/{artifact}/"
    for path in shared.artifact_files(root, artifact):
        rel = path.relative_to(base).as_posix()
        entries_here = [e for e in entries if _in_files(e, rel.removeprefix(own))]
        if not entries_here:
            continue
        text = engine.mask(path.read_text(encoding="utf-8"))
        old = snapshot / rel if snapshot is not None else None
        changed = _changed_lines(engine.mask(old.read_text(encoding="utf-8")), text) if old is not None and old.is_file() else None

        def kept(first: int, last: int) -> bool:
            return changed is None or any(n in changed for n in range(first, last + 1))

        for entry in entries_here:
            if entry["kind"] == "regex":
                pattern = re.compile(entry["regex"], _flags(entry.get("flags", "")))
                for m in pattern.finditer(text):
                    line = _line(text, m.start())
                    if not kept(line, _line(text, max(m.end() - 1, m.start()))):
                        continue
                    span = text.splitlines()[line - 1]
                    k = key(entry["id"], span)
                    message = f'{entry["description"]}: "{_window(text, m)}" (key {k})'
                    hits.append(Hit(finding_for(entry, rel, line, message), k, "regex"))
            else:
                for start, end, extra in _spans(entry["locator"], text):
                    first, last = _line(text, start), _line(text, end)
                    if not kept(first, last):
                        continue
                    span = text[start:end].strip()
                    k = key(entry["id"], span)
                    hits.append(Hit(finding_for(entry, rel, first, _probe_message(entry, span, extra, k), "probe"), k, "probe"))
    return hits


def _window(text: str, match: re.Match[str], width: int = 60) -> str:
    """The matched text with `width` characters of its line on each side."""
    start = text.rfind("\n", 0, match.start()) + 1
    end = text.find("\n", match.end())
    end = len(text) if end < 0 else end
    left, right = max(start, match.start() - width), min(end, match.end() + width)
    return f"{'...' if left > start else ''}{text[left:right].strip()}{'...' if right < end else ''}"


def finding_for(entry: dict, file: str, line: int, message: str, severity: str | None = None) -> Finding:
    return Finding(file, line, cast(Severity, severity or entry.get("severity", "error")), f"constraint/{entry['id']}", message)


def _probe_message(entry: dict, span: str, extra: str, k: str) -> str:
    lines = [entry["description"], f'    span: "{" ".join(span.split())[:240]}"']
    if entry["locator"] == "citation" and extra:
        lines.append(f"    verify: {NAME} tool source {extra.split(', ')[0]}   [{extra}]")
    elif entry["locator"] in ("caption", "frame") and extra:
        lines.append(f"    in: {extra}")
    lines.append(f"    key: {k}")
    return "\n".join(lines)


def verdicts(root: Path, artifact: str) -> dict[str, dict]:
    job = jobs.active_job(root, artifact)
    path = job / "verdicts.jsonl" if job is not None else None
    if path is None or not path.is_file():
        return {}
    return {v["key"]: v for v in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())}


def run(root: Path, artifact: str, *, all_lines: bool = False) -> list[Finding]:
    """The constraint findings, with the ones that have a verdict in the active job marked `resolved`."""
    done = verdicts(root, artifact)
    return [
        Finding(h.finding.file, h.finding.line, "resolved", h.finding.id, f"{done[h.key]['verdict']} {h.key}")
        if h.key in done else h.finding
        for h in _hits(root, artifact, all_lines)
    ]


def resolve(root: Path, artifact: str, key_: str, *, verdict: str, text: str | None) -> None:
    job = jobs.active_job(root, artifact)
    if job is None:
        raise ConstraintError(f"'{artifact}' has no active job; start one with `job start` to record a verdict")
    if verdict == "pass" and not text:
        raise ConstraintError("--pass needs --evidence with a quoted line of the source")
    if verdict == "na" and not text:
        raise ConstraintError("--na needs --why with the reason")
    hit = next((h for h in _hits(root, artifact, True) if h.key == key_), None)
    if hit is None:
        raise ConstraintError(f"no finding has the key '{key_}'; it reopens when the text of its span changes")
    if hit.kind == "regex" and verdict == "pass":
        raise ConstraintError("a regex hit is fixed in the text, or answered with --na when it is a false positive")
    entry = {
        "key": key_, "verdict": verdict, "file": hit.finding.file, "line": hit.finding.line,
        "date": datetime.now(UTC).date().isoformat(), ("evidence" if verdict == "pass" else "why"): text,
    }
    with (job / "verdicts.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def red(findings: list[Finding]) -> bool:
    """True while a failure or an open probe remains."""
    return any(f.severity in ("error", "probe") for f in findings)


def report(findings: list[Finding], artifact: str | None = None) -> list[str]:
    """The lines of the suite: every finding, open probes limited to `[guides].max_probes`, then the
    summary. With an artifact and an open constraint finding, a line says how to answer one."""
    limit = config_mod.guides_max_probes()
    lines: list[str] = []
    shown = 0
    for f in findings:
        if f.severity == "probe":
            shown += 1
            if shown > limit:
                continue
        lines.append(f.format())
    probes = sum(f.severity == "probe" for f in findings)
    if probes > limit:
        lines.append(f"{probes - limit} more probes; resolve the ones above to list them")
    fails = sum(f.severity == "error" for f in findings)
    resolved = sum(f.severity == "resolved" for f in findings)
    if artifact and any(f.id.startswith("constraint/") and f.severity in ("error", "probe") for f in findings):
        lines.append(
            f'answer a finding by its key: {NAME} check {artifact} --resolve <key> --pass --evidence "<a line you read in the source>"'
            ' (a probe), or --na --why "<reason>" (a false positive)'
        )
    lines.append(f"suite: {fails} fail, {probes} probes open, {resolved} resolved")
    return lines


def lint(root: Path, *, distill_min: int) -> list[Finding]:
    findings: list[Finding] = []
    for entry in load().values():
        file = f"{entry['store']}:{FILE}"
        if entry["kind"] == "regex" and entry["status"] == "active":
            try:
                _check_regex(entry)
            except ConstraintError as exc:
                findings.append(finding("constraint-example-failed", file, 1, f"{entry['id']}: {exc}"))
    counts: dict[str, int] = {}
    for v in jobs.all_verdicts(root):
        if v["verdict"] == "na":
            cid = v["key"].split("#")[0]
            counts[cid] = counts.get(cid, 0) + 1
    for cid, n in sorted(counts.items()):
        if n >= distill_min and cid in load():
            findings.append(finding("constraint-refine", f"{load()[cid]['store']}:{FILE}", 1, f"{cid} was answered not applicable {n} times: tighten the regex or add an ok example"))
    return findings
