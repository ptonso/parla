"""Page loading and the public/private merge. See `specs/guides.md#merge`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .. import config as config_mod
from .. import frontmatter
from . import rules

PUBLIC_ROOT = Path(__file__).parent
KINDS = ("topic", "modality", "audience", "engine", "move", "procedure")


class GuideError(Exception):
    """A guide page is missing or malformed."""


@dataclass
class Page:
    key: str  # "topic/positioning"
    meta: dict
    parsed: rules.Parsed
    origins: tuple[str, ...]  # ("public",), ("private",) or ("public", "private")
    path: Path | None = None  # the private file, or the public one without it
    public: rules.Parsed | None = None  # the shipped defaults of this page, prose only
    private: rules.Parsed | None = None  # the author's preferences on this page

    @property
    def label(self) -> str:
        return "+".join(self.origins)


def roots() -> dict[str, Path]:
    return {"public": PUBLIC_ROOT, "private": config_mod.guides_private() / "guides"}


def page_path(root: Path, key: str) -> Path:
    return root / f"{key}.md"


def _read(path: Path) -> tuple[dict, rules.Parsed]:
    try:
        meta, body = frontmatter.split(path.read_text(encoding="utf-8"))
    except (ValueError, yaml.YAMLError) as exc:
        raise GuideError(f"{path}: invalid frontmatter: {exc}") from exc
    return meta, rules.parse(body)


def exists(key: str) -> bool:
    return any(page_path(root, key).is_file() for root in roots().values())


def names(kind: str) -> list[str]:
    """The names of every page of a kind, across both roots."""
    found = {
        p.relative_to(root / kind).with_suffix("").as_posix()
        for root in roots().values()
        if (root / kind).is_dir()
        for p in (root / kind).rglob("*.md")
    }
    return sorted(found)


def load(key: str) -> Page:
    """The merged page: the public sections first, then the private ones, a section of the same
    name continuing the public one. A private page adds and never replaces public text."""
    found = {o: page_path(r, key) for o, r in roots().items() if page_path(r, key).is_file()}
    if not found:
        raise GuideError(f"no guide page '{key}'")
    public = _read(found["public"]) if "public" in found else None
    private = _read(found["private"]) if "private" in found else None
    if public is None:
        assert private is not None
        return Page(key, private[0], private[1], ("private",), found["private"], None, private[1])
    if private is None:
        return Page(key, public[0], public[1], ("public",), found["public"], public[1], None)
    meta = {**public[0], **private[0]}
    return Page(key, meta, _merge(public[1], private[1]), ("public", "private"), found["private"], public[1], private[1])


def _merge(public: rules.Parsed, private: rules.Parsed) -> rules.Parsed:
    sections = [rules.Section(s.name, list(s.items)) for s in public.sections]
    for extra in private.sections:
        target = next((s for s in sections if s.name == extra.name), None)
        if target is None:
            sections.append(rules.Section(extra.name, list(extra.items)))
        else:
            target.items.extend(extra.items)
    return rules.Parsed(sections, public.problems + private.problems)


def chain(name: str) -> list[str]:
    """The modality and the pages it includes, the most general first."""
    parent = load(f"modality/{name}").meta.get("includes")
    return [*(chain(parent) if parent else []), name]


def modality(name: str) -> Page:
    """A modality page with the sections it inherits from `includes` filled in."""
    page = load(f"modality/{name}")
    parent = page.meta.get("includes")
    if parent is None:
        return page
    base = modality(parent)
    own = {s.name for s in page.parsed.sections}
    inherited = [s for s in base.parsed.sections if s.name not in own]
    return Page(page.key, {**base.meta, **page.meta}, rules.Parsed([*inherited, *page.parsed.sections]), page.origins, page.path, page.public, page.private)


def parts(page: Page) -> dict[str, tuple[str, list[str]]]:
    """The modality page's `## parts` table: part name to its job and topics. Rows of one part
    join their topics, so a private row adds topics to a public part."""
    section = page.parsed.section("parts")
    table: dict[str, tuple[str, list[str]]] = {}
    for item in section.items if section else []:
        if isinstance(item, rules.Rule):
            continue
        for line in item.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 3 or cells[0].lower() == "part" or set(cells[0]) <= set("-: "):
                continue
            name = cells[0].strip("`")
            job, topics = table.get(name, ("", []))
            added = [t.strip().strip("`") for t in cells[2].split(",") if t.strip()]
            table[name] = (job or cells[1], [*topics, *(t for t in added if t not in topics)])
    return table


def applicable(key: str) -> list[str]:
    """The modalities a topic page is limited to, or `[]` when it applies to every modality."""
    value = load(key).meta.get("applicable") or []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise GuideError(f"{key}: `applicable` must be a list of modality names")
    return value


def check_applicable(topics: list[str], modality: str) -> None:
    """Fails when a topic is limited to other modalities, so a captain cannot compose a topic set
    that does not fit the artifact."""
    misfits = {t: applicable(f"topic/{t}") for t in topics if exists(f"topic/{t}")}
    misfits = {t: mods for t, mods in misfits.items() if mods and modality not in mods}
    if misfits:
        detail = ", ".join(f"'{t}' applies to {', '.join(mods)}" for t, mods in misfits.items())
        raise GuideError(
            f"not applicable to {modality}: {detail}. "
            f"List the topics that fit this artifact with `guide list topic --artifact <artifact>`"
        )
