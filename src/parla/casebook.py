"""The casebook: approved corrections as an append-only JSON-lines store. See `specs/casebook.md`."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from . import config as config_mod
from .checks import Finding
from .checks.ids import finding

STATUSES = ("active", "distilled", "contradicted", "pruned")
REQUIRED = ("artifact", "part", "topics", "hook", "problem", "before", "after", "lesson")
CASES_FILE = "cases.jsonl"
USE_FILE = "cases.use.jsonl"


class CaseError(Exception):
    """A case command cannot proceed."""


def _path(name: str) -> Path:
    return config_mod.guides_private() / name


def _lines(name: str) -> list[dict]:
    path = _path(name)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append(name: str, entry: dict) -> None:
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load() -> dict[str, dict]:
    """The current state of every case: its lines folded in order. Insertion order is first-seen."""
    cases: dict[str, dict] = {}
    for entry in _lines(CASES_FILE):
        cases.setdefault(entry["id"], {}).update(entry)
    return cases


def add(root: Path, payload: dict, known_topics: set[str], *, today: date | None = None) -> str:
    missing = [k for k in REQUIRED if not payload.get(k)]
    if missing:
        raise CaseError(f"missing field(s): {', '.join(missing)}")
    if not isinstance(payload["topics"], list):
        raise CaseError("topics must be a list")
    unknown = [t for t in payload["topics"] if t not in known_topics]
    if unknown:
        raise CaseError(f"unknown topic(s): {', '.join(unknown)} (have: {', '.join(sorted(known_topics))})")
    for key in ("hook", "lesson"):
        if "\n" in payload[key].strip():
            raise CaseError(f"the {key} must be one line")
    card = config_mod.load_card(root, payload["artifact"])
    cases = load()
    number = max((int(i.removeprefix("c-")) for i in cases), default=0) + 1
    entry = {
        "id": f"c-{number:04d}",
        "date": (today or datetime.now(UTC).date()).isoformat(),
        **{k: payload[k] for k in REQUIRED},
        "modality": card.modality,
        "audience": card.audience,
        "contradicts": payload.get("contradicts", []),
        "status": "active",
    }
    _append(CASES_FILE, entry)
    return entry["id"]


EDITABLE = ("hook", "lesson", "problem", "topics")


def edit(case_id: str, fields: dict, known_topics: set[str]) -> None:
    """Appends an update to a case. Only the hook, lesson, problem and topics can change; the before
    and after stay as the author left them."""
    if case_id not in load():
        raise CaseError(f"unknown case '{case_id}'")
    bad = set(fields) - set(EDITABLE)
    if bad or not fields:
        raise CaseError(f"edit takes {', '.join(EDITABLE)}; got {', '.join(sorted(bad)) or 'nothing'}")
    for key in ("hook", "lesson"):
        if key in fields and ("\n" in str(fields[key]).strip() or not str(fields[key]).strip()):
            raise CaseError(f"the {key} must be one non-empty line")
    unknown = [t for t in fields.get("topics", []) if t not in known_topics]
    if unknown:
        raise CaseError(f"unknown topic(s): {', '.join(unknown)} (have: {', '.join(sorted(known_topics))})")
    _append(CASES_FILE, {"id": case_id, **fields})


def mark(case_id: str, status: str) -> None:
    if status not in STATUSES:
        raise CaseError(f"unknown status '{status}' (have: {', '.join(STATUSES)})")
    if case_id not in load():
        raise CaseError(f"unknown case '{case_id}'")
    _append(CASES_FILE, {"id": case_id, "status": status})


def list_lines(topic: str | None = None, status: str | None = None) -> list[str]:
    return [
        f"{c['id']} {c['status']} {','.join(c['topics'])} {c['audience']} {c.get('hook', '-')} | {c['lesson']}"
        for c in load().values()
        if (topic is None or topic in c["topics"]) and (status is None or c["status"] == status)
    ]


def retrieve(
    *, topics: set[str], modality: str, audience: str | None, artifact: str, max_cases: int
) -> list[dict]:
    """Active or distilled cases on the loaded topics whose audience and modality match or are
    absent, best first: same artifact, same audience, same modality, most recent."""
    hits = [
        c for c in load().values()
        if c["status"] in ("active", "distilled")
        and topics & set(c["topics"])
        and (not c.get("audience") or c["audience"] == audience)
        and (not c.get("modality") or c["modality"] == modality)
    ]
    hits.sort(
        key=lambda c: (c["artifact"] == artifact, c.get("audience") == audience, c.get("modality") == modality, c["date"], c["id"]),
        reverse=True,
    )
    return hits[:max_cases]


def show(case_ids: list[str], artifact: str) -> str:
    """The cases in full as XML, in the order asked; logs one use per case."""
    cases = load()
    unknown = [i for i in case_ids if i not in cases]
    if unknown:
        raise CaseError(f"unknown case(s): {', '.join(unknown)}")
    log_use(case_ids, artifact)
    return "\n\n".join(
        f'<case id="{i}">\n'
        + "\n".join(f"<{k}>{cases[i][k]}</{k}>" for k in ("problem", "after", "lesson"))
        + "\n</case>"
        for i in case_ids
    )


def log_use(case_ids: list[str], artifact: str, *, today: date | None = None) -> None:
    stamp = (today or datetime.now(UTC).date()).isoformat()
    for case_id in case_ids:
        _append(USE_FILE, {"case": case_id, "date": stamp, "artifact": artifact})


def lint(*, distill_min: int, stale_days: int | None, today: date | None = None) -> list[Finding]:
    today = today or datetime.now(UTC).date()
    cases = load()
    first_line: dict[str, int] = {}
    for number, entry in enumerate(_lines(CASES_FILE), 1):
        first_line.setdefault(entry["id"], number)
    active = [c for c in cases.values() if c["status"] == "active"]
    findings: list[Finding] = []
    groups: dict[tuple[str, str], list[str]] = {}
    for c in active:
        for topic in c["topics"]:
            groups.setdefault((topic, c.get("audience", "")), []).append(c["id"])
    for (topic, audience), ids in sorted(groups.items()):
        if len(ids) >= distill_min:
            findings.append(finding(
                "case-distill", CASES_FILE, first_line[ids[0]],
                f"{len(ids)} active cases on '{topic}' for '{audience}' ({', '.join(ids)}): propose a principle",
            ))
    if stale_days is not None:
        last_use: dict[str, str] = {}
        for use in _lines(USE_FILE):
            last_use[use["case"]] = max(last_use.get(use["case"], ""), use["date"])
        cutoff = today - timedelta(days=stale_days)
        for c in active:
            seen = date.fromisoformat(last_use.get(c["id"], c["date"]))
            if seen < cutoff:
                findings.append(finding("case-stale", CASES_FILE, first_line[c["id"]], f"{c['id']} was not retrieved since {seen}"))
    return findings
