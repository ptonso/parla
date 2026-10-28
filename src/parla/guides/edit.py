"""`guide add` and `guide move`: the only writers of guide files, and only of the private root and
the cards. See `specs/guides.md`."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .. import casebook
from .. import config as config_mod
from ..names import PROJECT_DIR
from . import pages, rules

HISTORY = "rules.history.jsonl"
NEW_PAGE_KINDS = ("general", "topic", "trait", "move", "procedure", "engine")


def split_raw(text: str) -> tuple[str, str]:
    """The frontmatter block verbatim, and the body."""
    head, sep, body = text.removeprefix("---\n").partition("\n---\n")
    return f"---\n{head}\n---\n", body


def cards(root: Path) -> list[Path]:
    return sorted((root / PROJECT_DIR / "artifacts").glob("*/card.md"))


def files(root: Path) -> list[tuple[str, Path]]:
    """`(page key, file)` of every guide page of both roots, and `("card:<artifact>", file)` of every card."""
    found = [
        (p.relative_to(r).with_suffix("").as_posix(), p)
        for r in pages.roots().values() if r.is_dir()
        for p in sorted(r.rglob("*.md"))
    ]
    return found + [(f"card:{c.parent.name}", c) for c in cards(root)]


def all_ids(root: Path) -> dict[str, set[str]]:
    """Rule id to the page keys that define it, over public, private and cards."""
    ids: dict[str, set[str]] = {}
    for key, path in files(root):
        _, body = split_raw(path.read_text(encoding="utf-8"))
        for rule in rules.parse(body).rules:
            ids.setdefault(rule.id, set()).add(key)
    return ids


def _new_page(key: str, hook: str | None) -> str:
    kind, _, name = key.partition("/")
    if key == "general":
        return "---\nkind: general\n---\n"
    extra = f"hook: {json.dumps(hook)}\n" if hook else ""
    return f"---\nkind: {kind}\n{kind}: {name}\n{extra}---\n"


def _target(root: Path, key: str, hook: str | None = None) -> Path:
    key = key if "/" in key or key == "general" else f"topic/{key}"
    kind = key.partition("/")[0]
    path = pages.page_path(pages.roots()["private"], key)
    if path.is_file():
        return path
    if kind not in NEW_PAGE_KINDS and not pages.page_path(pages.PUBLIC_ROOT, key).is_file():
        raise pages.GuideError(f"no guide page '{key}'; a {kind} page needs its frontmatter and cannot be created by `guide add`")
    if kind == "topic" and not hook and not pages.page_path(pages.PUBLIC_ROOT, key).is_file():
        raise pages.GuideError(f"a new topic page needs --hook, one line that says when '{key.partition('/')[2]}' applies")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_new_page(key, hook), encoding="utf-8")
    return path


def _insert(path: Path, rule: rules.Rule, section: str) -> None:
    head, body = split_raw(path.read_text(encoding="utf-8"))
    parsed = rules.parse(body)
    target = parsed.section(section)
    if target is None:
        target = rules.Section(section)
        parsed.sections.append(target)
    target.items.append(rule)
    path.write_text(head + "\n" + parsed.render(), encoding="utf-8")


def add(
    root: Path, page: str, rule_id: str, text: str, *, origin: str | None = None,
    overrides: str | None = None, evidence: list[str] | None = None,
    card: str | None = None, section: str = "principles", hook: str | None = None,
) -> Path:
    if rule_id in all_ids(root):
        raise pages.GuideError(f"rule id '{rule_id}' already exists in {', '.join(sorted(all_ids(root)[rule_id]))}")
    if overrides is not None and overrides not in all_ids(root):
        raise pages.GuideError(f"overrides '{overrides}' names no rule")
    known = casebook.load()
    unknown = [c for c in evidence or [] if c not in known]
    if unknown:
        raise pages.GuideError(f"unknown case(s): {', '.join(unknown)}")
    if evidence:
        origin = f"{origin or 'distilled'} from {', '.join(evidence)}"
    origin = origin or f"added {datetime.now(UTC).date()}"
    rule = rules.Rule(rule_id, text, origin, overrides)
    if card is not None:
        path = config_mod.card_path(root, card)
        config_mod.load_card(root, card)
        _insert(path, rule, "rules")
    else:
        path = _target(root, page, hook)
        _insert(path, rule, section)
    for case_id in evidence or []:
        casebook.mark(case_id, "distilled")
    return path


def move(root: Path, rule_id: str, page: str) -> Path:
    for key, path in files(root):
        if key.startswith("card:") or path.is_relative_to(pages.roots()["private"]):
            head, body = split_raw(path.read_text(encoding="utf-8"))
            parsed = rules.parse(body)
            for section in parsed.sections:
                for rule in section.rules:
                    if rule.id == rule_id:
                        target = _target(root, page)
                        _insert(target, rule, section.name if not key.startswith("card:") else "principles")
                        section.items.remove(rule)
                        path.write_text(head + "\n" + parsed.render(), encoding="utf-8")
                        return target
    raise pages.GuideError(f"no rule '{rule_id}'")


def _history(action: str, key: str, rule: rules.Rule, new_text: str | None = None) -> None:
    """Appends what a rule was before an `edit` or a `drop`, so no wording is ever lost."""
    path = config_mod.guides_private() / HISTORY
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"date": datetime.now(UTC).date().isoformat(), "action": action, "rule": rule.id, "page": key,
             "text": rule.text, "origin": rule.origin, **({"new_text": new_text} if new_text else {})}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _private_files(root: Path):
    for key, path in files(root):
        if key.startswith("card:") or path.is_relative_to(pages.roots()["private"]):
            yield key, path


def drop(root: Path, rule_id: str) -> Path:
    """Removes a rule from a private page or a card; its text goes to the history."""
    for key, path in _private_files(root):
        head, body = split_raw(path.read_text(encoding="utf-8"))
        parsed = rules.parse(body)
        for section in parsed.sections:
            for rule in section.rules:
                if rule.id == rule_id:
                    _history("drop", key, rule)
                    section.items.remove(rule)
                    path.write_text(head + "\n" + parsed.render(), encoding="utf-8")
                    return path
    raise pages.GuideError(f"no private rule '{rule_id}'")


def edit(root: Path, rule_id: str, text: str, *, evidence: list[str] | None = None) -> Path:
    """Rewrites the text of a private rule in place. The id stays, the origin records the revision,
    and the previous text goes to the history."""
    known = casebook.load()
    unknown = [c for c in evidence or [] if c not in known]
    if unknown:
        raise pages.GuideError(f"unknown case(s): {', '.join(unknown)}")
    for key, path in _private_files(root):
        head, body = split_raw(path.read_text(encoding="utf-8"))
        parsed = rules.parse(body)
        for rule in parsed.rules:
            if rule.id == rule_id:
                _history("edit", key, rule, text)
                stamp = f"revised {datetime.now(UTC).date()}" + (f" from {', '.join(evidence)}" if evidence else "")
                rule.text, rule.origin = text, f"{rule.origin}, {stamp}" if rule.origin else stamp
                path.write_text(head + "\n" + parsed.render(), encoding="utf-8")
                for case_id in evidence or []:
                    casebook.mark(case_id, "distilled")
                return path
    raise pages.GuideError(f"no private rule '{rule_id}'")


def page_warning(key: str) -> str | None:
    """A sentence when a topic page is over `[guides].max_page_words`, so the agent consolidates it."""
    from . import show

    if not key.startswith("topic/"):
        return None
    page = pages.load(key)
    size = len(show._plain(show._page_block(key, page, "topic", key.partition("/")[2])).split())
    cap = config_mod.guides_max_page_words()
    if size <= cap:
        return None
    return f"topic '{key.partition('/')[2]}' is now {size} words, over the page cap of {cap}: dedupe, generalize or merge its rules before adding more"
