"""The shipped skill: every link resolves, and every supporting page is reachable from the registry."""
from __future__ import annotations

import re

from parla.template import SKILLS_DIR

SKILL = SKILLS_DIR / "parla"


def _links(text: str) -> list[str]:
    prose = re.sub(r"```.*?```|`[^`]*`", "", text, flags=re.S)
    return re.findall(r"\]\(([\w.-]+\.md)(?:#[\w-]+)?\)", prose)


def test_skill_documents_link_only_to_existing_files():
    for doc in SKILL.glob("*.md"):
        for target in _links(doc.read_text(encoding="utf-8")):
            assert (SKILL / target).exists(), f"{doc.name} links to missing {target}"


def test_every_supporting_page_is_in_the_registry():
    registry = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("## Where to read next", 1)[1].split("\n## ", 1)[0]
    listed = set(_links(registry))
    pages = {p.name for p in SKILL.glob("*.md")} - {"SKILL.md"}
    assert pages == listed


def test_the_skill_names_itself_and_holds_no_private_material():
    head = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    assert "name: parla" in head and "description:" in head
    assert not any(SKILL.rglob("cases*.jsonl"))
