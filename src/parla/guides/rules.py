"""The rule format: a level-six heading with the id, then one blockquote line holding the rule
and its origin in parentheses. See `specs/guides.md#rule-format`."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_RULE_HEADING_RE = re.compile(r"^###### (\S+)\s*$")
_SECTION_RE = re.compile(r"^## (.+?)\s*$")
_META_RE = re.compile(r"^origin: (?P<origin>.*?)(?:;\s*overrides\s+(?P<overrides>\S+))?$")


@dataclass
class Rule:
    id: str
    text: str
    origin: str | None = None
    overrides: str | None = None
    line: int = 0

    def render(self) -> str:
        meta = [f"origin: {self.origin}"] if self.origin else []
        if self.overrides:
            meta.append(f"overrides {self.overrides}")
        suffix = f" ({'; '.join(meta)})" if meta else ""
        return f"###### {self.id}\n> {self.text}{suffix}"


@dataclass
class Section:
    name: str  # "" for the text before the first `##` heading
    items: list[Rule | str] = field(default_factory=list)  # a rule, or a block of prose

    @property
    def rules(self) -> list[Rule]:
        return [i for i in self.items if isinstance(i, Rule)]

    def render(self) -> str:
        body = "\n\n".join(i.render() if isinstance(i, Rule) else i for i in self.items)
        return f"## {self.name}\n\n{body}" if self.name else body


@dataclass(frozen=True)
class Problem:
    line: int
    id: str  # a check id
    message: str


@dataclass
class Parsed:
    sections: list[Section] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    def section(self, name: str) -> Section | None:
        return next((s for s in self.sections if s.name == name), None)

    @property
    def rules(self) -> list[Rule]:
        return [r for s in self.sections for r in s.rules]

    def render(self) -> str:
        return "\n\n".join(s.render() for s in self.sections if s.items or s.name) + "\n"


def _quote(line: str) -> tuple[str, str | None, str | None]:
    """`(text, origin, overrides)` of a blockquote line."""
    content = line.removeprefix(">").strip()
    start = content.rfind("(origin:")
    if start < 0 or not content.endswith(")"):
        return content, None, None
    match = _META_RE.match(content[start + 1 : -1])
    if match is None:
        return content, None, None
    return content[:start].rstrip(), match["origin"].strip(), match["overrides"]


def parse(text: str) -> Parsed:
    parsed = Parsed()
    current = Section("")
    prose: list[str] = []

    def flush() -> None:
        block = "\n".join(prose).strip("\n")
        if block.strip():
            current.items.append(block)
        prose.clear()

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if (m := _SECTION_RE.match(line)) is not None:
            flush()
            parsed.sections.append(current)
            current = Section(m.group(1))
        elif (m := _RULE_HEADING_RE.match(line)) is not None:
            flush()
            index, rule = _read_rule(lines, index, m.group(1), parsed)
            current.items.append(rule)
            continue
        else:
            prose.append(line)
        index += 1
    flush()
    parsed.sections.append(current)
    parsed.sections = [s for s in parsed.sections if s.items or s.name]
    return parsed


def _read_rule(lines: list[str], index: int, rule_id: str, parsed: Parsed) -> tuple[int, Rule]:
    """Reads the blockquote that follows the heading at `index`; returns the next index."""
    number = index + 1
    cursor = index + 1
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1
    if cursor >= len(lines) or not lines[cursor].startswith(">"):
        parsed.problems.append(Problem(number, "rule-malformed", f"rule '{rule_id}' has no blockquote line"))
        return index + 1, Rule(rule_id, "", line=number)
    text, origin, overrides = _quote(lines[cursor])
    if origin is None:
        parsed.problems.append(Problem(number, "rule-origin-missing", f"rule '{rule_id}' has no (origin: ...)"))
    nxt = cursor + 1
    if nxt < len(lines) and lines[nxt].startswith(">"):
        parsed.problems.append(Problem(number, "rule-malformed", f"rule '{rule_id}' has more than one blockquote line"))
        while nxt < len(lines) and lines[nxt].startswith(">"):
            nxt += 1
    return nxt, Rule(rule_id, text, origin, overrides, number)
