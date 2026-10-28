"""`guide show`: the guides and case hooks that apply to the part about to be touched. See `specs/guides.md#parla-guide-show`."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from .. import casebook, constraints, jobs
from .. import config as config_mod
from ..names import NAME
from . import pages, rules


@dataclass
class Block:
    origin: str  # "public", "private", "card" or "case"; "" for a heading that only groups
    heading: str
    sections: list[rules.Section] = field(default_factory=list)
    text: str | None = None  # pre-rendered body
    lead: str = ""  # prose printed before the sections
    tag: str = ""  # the XML element of the default view, "" for a heading that only groups
    name: str = ""
    sources: tuple[str, ...] = ()  # the files the text comes from

    def body(self) -> str:
        if self.text is not None:
            return self.text
        parts = [self.lead, *(_section(sec) for sec in self.sections if sec.items)]
        return "\n\n".join(p for p in parts if p)

    def __bool__(self) -> bool:
        return bool(self.body().strip())

    def words(self) -> int:
        return len(self.body().split())

    def render(self) -> str:
        body = self.body()
        return f"{self.heading}\n\n{body}" if body else self.heading

    def xml(self) -> str:
        body = _plain(self)
        attr = f' name="{self.name}"' if self.name else ""
        return f"<{self.tag}{attr}>\n{body}\n</{self.tag}>"


@dataclass(frozen=True)
class Load:
    modality: str
    audience: str | None
    engine: str
    traits: dict[str, str]
    part: str | None  # a part of the modality, or None
    topics: list[str]
    card: tuple[str, str] | None = None  # (artifact, body)
    job: str = ""  # what the part does in this modality
    card_file: str = ""


def resolve_topics(
    modality_page: pages.Page, name: str | None, chosen: list[str] | None = None, modality: str | None = None
) -> tuple[str | None, list[str]]:
    """`(part, topics)` for a part or topic name. A part loads the topics in `chosen`, or those of
    its row; no name loads `chosen` and no other topic."""
    table = pages.parts(modality_page)
    known = pages.names("topic")
    unknown = [t for t in chosen or [] if t not in known]
    if unknown:
        raise pages.GuideError(f"unknown topic(s): {', '.join(unknown)} (have: {', '.join(known) or 'none'})")
    if modality is not None:
        pages.check_applicable(chosen or [], modality)
    if name is None:
        return None, chosen or []
    if name in table:
        return name, chosen or table[name][1]
    if pages.exists(f"topic/{name}"):
        if modality is not None:
            pages.check_applicable([name], modality)
        return None, [name]
    raise pages.GuideError(
        f"'{name}' is neither a part nor a topic. Parts: {', '.join(table) or 'none'}. "
        f"Topics: {', '.join(known) or 'none'}"
    )


PACKAGE_DIR = Path(__file__).resolve().parents[1]


def _short(path: Path) -> str:
    """`$private/...` under the private guides root, `$package/...` inside the installed package,
    the absolute path otherwise."""
    path = path.resolve()
    for label, base in (("$private", config_mod.guides_private().resolve()), ("$package", PACKAGE_DIR)):
        if path.is_relative_to(base):
            return f"{label}/{path.relative_to(base).as_posix()}"
    return str(path)


def _project_path(root: Path, path: Path) -> str:
    """The path under the project root as written, so a `parla/` symlinked into an asset store stays `parla/...`."""
    return f"$project/{path.relative_to(root).as_posix()}" if path.is_relative_to(root) else str(path)


def _where(key: str, *, public: bool = True, private: bool = True) -> tuple[str, ...]:
    """The files of page `key` in the roots asked for, that exist."""
    roots = pages.roots()
    wanted = [roots[r] for r, on in (("public", public), ("private", private)) if on]
    return tuple(_short(f) for r in wanted if (f := pages.page_path(r, key)).is_file())


def _prose(parsed: rules.Parsed | None, names: set[str] | None = None) -> str:
    """The prose and bullets of a public page, without section headings; `names` limits the sections."""
    sections = [s for s in parsed.sections if names is None or s.name in names] if parsed else []
    return "\n\n".join(i for s in sections for i in s.items if isinstance(i, str))


def _group(heading: str, blocks: list[Block]) -> list[Block]:
    live = [b for b in blocks if b]
    return [Block("", heading), *live] if live else []


def _titled(heading: str, origin: str, text: str | None = None, sections: list[rules.Section] | None = None, *, tag: str = "", name: str = "", sources: tuple[str, ...] = ()) -> list[Block]:
    block = Block(origin, heading, sections or [], text, tag=tag, name=name, sources=sources)
    return [block] if block else []


def _section(section: rules.Section) -> str:
    """A section as Markdown: prose as it is, each rule as `- [id] text`; the origin stays in the file."""
    out: list[str] = []
    for item in section.items:
        if isinstance(item, rules.Rule):
            line = f"- [{item.id}] {item.text}"
            out.append(f"{out.pop()}\n{line}" if out and out[-1].startswith("- [") else line)
        else:
            out.append(item)
    body = "\n\n".join(out)
    return f"### {section.name}\n\n{body}" if section.name and section.name != "principles" else body


def _plain(block: Block) -> str:
    """The body the model reads: rules as bullets of their text, no ids, `check` sections left out."""
    if block.text is not None:
        return block.text
    out: list[str] = [block.lead] if block.lead else []
    for section in block.sections:
        if section.name == "check" or not section.items:
            continue
        lines: list[str] = []
        for item in section.items:
            if isinstance(item, rules.Rule):
                line = f"- {item.text}"
                if lines and lines[-1].startswith("- "):
                    lines[-1] += f"\n{line}"
                else:
                    lines.append(line)
            else:
                lines.append(item)
        label = [f"{section.name}:"] if section.name and section.name != "principles" else []
        out.append("\n\n".join([*label, *lines]))
    return "\n\n".join(o for o in out if o)


def _page_block(key: str, page: pages.Page, tag: str, name: str, *, exclude: set[str] | frozenset[str] = frozenset(), only: set[str] | None = None) -> Block:
    private = [s for s in _kept(page.private, exclude) if only is None or s.name in only]
    origin = "+".join(o for o in page.origins)
    return Block(origin, f"## {key}", private, lead=_prose(page.public), tag=tag, name=name, sources=_where(key))


def blocks(load: Load, cases: tuple[dict, ...] = ()) -> list[Block]:
    chain = pages.chain(load.modality)
    modality = pages.modality(load.modality)
    pubs = [pages.load(f"modality/{n}") for n in chain]
    general = pages.load("general")

    out = _titled("# How this works", "public", _prose(general.public), tag="context", sources=_where("general", private=False))
    out += _titled(f"# {load.modality}", "public", "\n\n".join(_prose(p.public, {"brief"}) for p in pubs).strip(), tag="brief", name=load.modality, sources=tuple(f for n in chain for f in _where(f"modality/{n}", private=False)))
    if load.part is not None:
        out += _titled(f"## Part: {load.part}", "public", load.job, tag="part", name=load.part, sources=tuple(f for n in chain for f in _where(f"modality/{n}", private=False)))

    engines = [pages.load(f"engine/{n}") for n in (load.engine, *(modality.meta.get("engine_pages") or []))]
    out += _group("# Engine facts", [Block("public", f"## {e.key.removeprefix('engine/')}", text=_prose(e.public), tag="engine", name=e.key.removeprefix("engine/"), sources=_where(e.key, private=False)) for e in engines])
    traits = [pages.load(f"trait/{k}/{v}") for k, v in load.traits.items()]
    out += _group("# Traits", [Block("public", f"## {t.key.removeprefix('trait/')}", text=_prose(t.public), tag="trait", name=t.key.removeprefix("trait/"), sources=_where(t.key, private=False)) for t in traits])

    other_modalities = set(pages.names("modality")) - {load.modality}
    prefs = [Block("private", "## general", _kept(general.private), tag="general", sources=_where("general", public=False))]
    prefs += [Block("private", f"## {p.key}", _kept(p.private, exclude={"parts"}), tag="modality", name=p.key.removeprefix("modality/"), sources=_where(p.key, public=False)) for p in pubs]
    prefs += [_page_block(f"topic/{t}", pages.load(f"topic/{t}"), "topic", t, exclude=other_modalities) for t in load.topics if pages.exists(f"topic/{t}")]
    prefs += [Block("private", f"## {t.key}", _kept(t.private), tag="trait", name=t.key.removeprefix("trait/"), sources=_where(t.key, public=False)) for t in traits]
    prefs += [Block("private", f"## {e.key}", _kept(e.private), tag="engine", name=e.key.removeprefix("engine/"), sources=_where(e.key, public=False)) for e in engines]
    if load.audience is not None:
        audience = pages.load(f"audience/{load.audience}")
        prefs.append(Block("private", f"## {audience.key}", [x for x in _kept(audience.private) if x.name in set(load.topics)], tag="audience", name=load.audience, sources=_where(audience.key)))
    out += _group("# The author's preferences (they win over the defaults)", prefs)

    out += _group("# Cases (the author's earlier corrections)", [case_block(c) for c in cases])
    if load.card is not None:
        card = rules.parse(load.card[1]).sections
        for sec in card:
            sec.items = [t for i in sec.items if (t := _without_title(i)) != ""]
        out += _titled(f"# This artifact: {load.card[0]}", "card", sections=card, tag="card", sources=(load.card_file,) if load.card_file else ())
    return out


def _without_title(item: rules.Rule | str) -> rules.Rule | str:
    """A card's own `# title` line is not content."""
    if isinstance(item, rules.Rule):
        return item
    return "\n".join(line for line in item.splitlines() if not line.startswith("# ")).strip("\n")


def _kept(parsed: rules.Parsed | None, exclude: frozenset[str] | set[str] = frozenset()) -> list[rules.Section]:
    return [s for s in parsed.sections if s.name not in exclude] if parsed else []


def apply_overrides(items: list[Block]) -> list[str]:
    """Removes every rule that another rule overrides; returns the `--- overridden` lines."""
    present = {r.id for b in items for s in b.sections for r in s.rules}
    pairs = {r.overrides: r.id for b in items for s in b.sections for r in s.rules if r.overrides in present}
    for block in items:
        for section in block.sections:
            section.items = [i for i in section.items if not (isinstance(i, rules.Rule) and i.id in pairs)]
    return [f"--- overridden: {old} by {new}" for old, new in pairs.items()]


def case_block(case: dict) -> Block:
    fields = "\n".join(f"{k}: {case[k]}" for k in ("problem", "after", "lesson"))
    return Block("case", f"## {case['id']}", text=fields)


def card_load(root: Path, artifact: str, name: str | None, topics: list[str] | None = None) -> Load:
    card = config_mod.load_card(root, artifact)
    modality = pages.modality(card.modality)
    chosen = topics or jobs.active_topics(root, artifact)
    part, resolved = resolve_topics(modality, name, chosen, card.modality)
    traits = {**(modality.meta.get("traits") or {}), **card.traits}
    job = pages.parts(modality)[part][0] if part else ""
    return Load(card.modality, card.audience, card.engine, traits, part, resolved, (artifact, card.body), job, _project_path(root, config_mod.card_path(root, artifact)))


def _hooks(cases: list[dict]) -> str:
    lines = [f"- {c['id']}: {c.get('hook', '-')}" for c in cases]
    return "\n".join([f"Open the cases that apply with `{NAME} case show <ids>`.", *lines])


def render(root: Path, artifact: str, load: Load) -> tuple[str, list[dict]]:
    """The default view: XML blocks in the order the model reads them, and the retrieved cases."""
    cases = casebook.retrieve(
        topics=set(load.topics), modality=load.modality, audience=load.audience,
        artifact=artifact, max_cases=config_mod.guides_max_cases(),
    )
    items = blocks(load)
    apply_overrides(items)
    live = [b for b in items if b.tag]
    by = lambda *tags: [b for b in live if b.tag in tags]  # noqa: E731
    watch = constraints.hints(root, artifact)
    head = f'<guide artifact="{artifact}"' + (f' part="{load.part}"' if load.part else "") + ">"
    parts = [head]
    parts += [b.xml() for b in by("context", "brief", "part")]
    parts += [b.xml() for b in by("engine") if b.text is not None]
    traits = [b for b in by("trait") if b.text is not None]
    if traits:
        parts.append("<traits>\n" + "\n".join(b.xml() for b in traits) + "\n</traits>")
    if watch:
        parts.append("<watch>\n" + "\n".join(f"- {w}" for w in watch) + "\n</watch>")
    if cases:
        parts.append(f"<case-hooks>\n{_hooks(cases)}\n</case-hooks>")
    prefs = [b for b in live if b.tag in ("general", "modality", "topic", "trait", "engine", "audience") and b.text is None and b]
    if prefs:
        inner = "\n".join(b.xml() if b.tag != "general" else f"<general>\n{_plain(b)}\n</general>" for b in prefs)
        parts.append(f"<preferences>\n{inner}\n</preferences>")
    parts += [b.xml() for b in by("card")]
    parts.append("</guide>")
    return "\n".join(parts), cases


def words(text: str) -> int:
    return len(text.split())


def budget(root: Path, artifact: str, name: str | None, topics: list[str]) -> tuple[int, dict[str, int], int]:
    """`(system words, words per topic, total words)` of the default view with `topics`."""
    base = card_load(root, artifact, name, topics=None)
    system = words(render(root, artifact, _with(base, []))[0])
    per_topic = {t: words(render(root, artifact, _with(base, [t]))[0]) - system for t in topics}
    total = words(render(root, artifact, _with(base, topics))[0])
    return system, per_topic, total


def _with(load: Load, topics: list[str]) -> Load:
    return Load(load.modality, load.audience, load.engine, load.traits, load.part, topics, load.card, load.job, load.card_file)


def enforce(total: int, system: int, per_topic: dict[str, int]) -> None:
    """Warns on standard error above the target, and above target times tolerance asks for distilling.
    The cap is soft: it lints the long-term memory and never blocks a job."""
    target, limit = config_mod.guides_target_words(), config_mod.guides_limit_words()
    detail = ", ".join([f"system {system}", *(f"{t} {w}" for t, w in per_topic.items())])
    if total > limit:
        print(f"{NAME}: the guide is {total} words, over the limit of {limit} (target {target}): {detail}; distill or trim the guides", file=sys.stderr)
    elif total > target:
        print(f"{NAME}: the guide is {total} words, over the target of {target}: {detail}", file=sys.stderr)


def show(root: Path, artifact: str, name: str | None = None, *, topics: list[str] | None = None, unformatted: bool = False, outline: bool = False) -> str:
    load = card_load(root, artifact, name, topics)
    text, cases = render(root, artifact, load)
    system, per_topic, total = budget(root, artifact, name, load.topics)
    if not outline:
        enforce(total, system, per_topic)
    target = config_mod.guides_target_words()
    head = f"{NAME} guide {artifact}{f' {name}' if name else ''} | {total} words / target {target} | {len(cases)} cases"
    if not unformatted and not outline:
        return text
    items = blocks(load, tuple(cases))
    notes = apply_overrides(items)
    if outline:
        return _outline(root, artifact, head, items, cases)
    return "\n\n".join([head, *(b.render() for b in items)] + (["\n".join(notes)] if notes else []))


def _files(sources: tuple[str, ...]) -> str:
    """The files of an element; two roots with the same path below them read `{$package,$private}/path`."""
    split = [f.split("/", 1) for f in sources if "/" in f]
    if len(split) > 1 and len(split) == len(sources) and len({rest for _, rest in split}) == 1:
        return "{" + ",".join(root for root, _ in split) + "}/" + split[0][1]
    return "  ".join(sources)


def _outline(root: Path, artifact: str, head: str, items: list[Block], cases: list[dict]) -> str:
    """One line per element of the default view, in its order: the element, its words and the files
    its text comes from."""
    live = [b for b in items if b.tag and b]
    by = lambda tags, text: [b for b in live if b.tag in tags and (b.text is not None) == text]  # noqa: E731
    rows: list[tuple[str, int, str]] = []

    def element(b: Block) -> tuple[str, int, str]:
        label = f'<{b.tag} name="{b.name}">' if b.name else f"<{b.tag}>"
        return label, len(_plain(b).split()), _files(b.sources)

    rows += [element(b) for b in by(("context", "brief", "part"), True)]
    rows += [element(b) for b in by(("engine",), True)]
    rows += [element(b) for b in by(("trait",), True)]
    entries = constraints.hint_entries(root, artifact)
    if entries:
        paths = {"public": _short(constraints._public_path()), "private": _short(constraints._private_path())}
        grouped = [f"{paths[store]} ({', '.join(c['id'] for c in entries if c['store'] == store)})" for store in ("private", "public") if any(c["store"] == store for c in entries)]
        rows.append(("<watch>", sum(len(c["description"].split()) for c in entries), "  ".join(grouped)))
    if cases:
        rows.append(("<case-hooks>", len(_hooks(cases).split()), f"{_short(casebook._path(casebook.CASES_FILE))} ({', '.join(c['id'] for c in cases)})"))
    rows += [element(b) for b in live if b.tag in ("general", "modality", "topic", "trait", "engine", "audience") and b.text is None]
    rows += [element(b) for b in live if b.tag == "card"]
    wide = max(len(r[0]) for r in rows)
    lines = [head, *(f"{label:<{wide}} {words:>5}  {files}" for label, words, files in rows)]
    used = " ".join(f"{k}={v}" for k, v in (("$package", PACKAGE_DIR), ("$private", config_mod.guides_private()), ("$project", root)) if any(k in r[2] for r in rows))
    return "\n".join([*lines, "", used])


def show_page(kind: str, name: str, *, unformatted: bool = False) -> str:
    page = pages.load(f"{kind}/{name}")
    if unformatted:
        return Block(page.label, f"# {page.key}", page.parsed.sections).render()
    block = Block(page.label, f"# {page.key}", page.parsed.sections, tag=kind, name=name)
    return block.xml()


def topic_table(root: Path, artifact: str | None, part: str | None) -> list[str]:
    """The lines of `guide list topic`: `name | words | hook`, and the budget footer with an artifact."""
    lines = []
    system = 0
    loaded = (artifact, card_load(root, artifact, part, topics=[])) if artifact else None
    if loaded:
        system = words(render(root, loaded[0], _with(loaded[1], []))[0])
    for topic in pages.names("topic"):
        page = pages.load(f"topic/{topic}")
        limited = pages.applicable(f"topic/{topic}")
        if loaded and limited and loaded[1].modality not in limited:
            continue
        if loaded:
            size = words(render(root, loaded[0], _with(loaded[1], [topic]))[0]) - system
        else:
            size = words(_plain(_page_block(f"topic/{topic}", page, "topic", topic)))
        only = f" | applies to {', '.join(limited)}" if not loaded and limited else ""
        lines.append(f"{topic} | {size} words | {page.meta.get('hook', '-')}{only}")
    if loaded:
        target, limit = config_mod.guides_target_words(), config_mod.guides_limit_words()
        row = pages.parts(pages.modality(loaded[1].modality)).get(part or "", ("", []))[1]
        lines.append(f"system {system} words | target {target} | tolerance {limit} | left for topics {max(target - system, 0)}")
        if row:
            lines.append(f"topics of this part: {', '.join(row)}")
    return lines
