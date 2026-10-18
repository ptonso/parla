"""Split a Markdown file into its YAML frontmatter mapping and its body."""

from __future__ import annotations

import yaml


def split(text: str) -> tuple[dict, str]:
    """Raises `ValueError` when the file has no frontmatter block or it is not a mapping."""
    head, sep, body = text.removeprefix("---\n").partition("\n---\n")
    if not text.startswith("---\n") or not sep:
        raise ValueError("the file must start with a YAML frontmatter block")
    keys = yaml.safe_load(head)
    if not isinstance(keys, dict):
        raise ValueError("the frontmatter must be a mapping")
    return keys, body
