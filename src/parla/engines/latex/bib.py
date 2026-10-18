"""Bibliography resolution: Zotero library + project extras -> generated `parla/artifacts/<name>/references.bib`.

The single place that knows how a project's `references.bib` is produced. Zotero, via a
Better BibTeX auto-export, is the source of truth; this module only ever reads it:

- `library.bib`  -- entry text, sliced verbatim (BBT is the serializer, not this code)
- `library.json` -- Zotero item keys and PDF attachment paths, keyed by citation key

`parla/artifacts/<name>/references.bib` is a generated cache: exactly the citekeys a document uses, each
entry copied byte-for-byte from `library.bib` or a `parla/sources/bib/*.bib` file. On a
citekey collision the library wins; an extra only contributes keys the library lacks.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from ...names import NAME, PROJECT_DIR

# `\cite`, `\citep`, `\citet`, `\textcite`, `\parencite`, `\autocite`, `\nocite`, ... with
# up to two bracketed optional arguments. Case-insensitive so biblatex's `\Cite` matches.
_CITE_RE = re.compile(
    r"\\[a-z]*cite[a-z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]+)\}",
    re.IGNORECASE,
)
# A TeX line comment (`%` not preceded by a backslash) to end of line -- stripped before
# scanning so a commented-out `\cite` and our own `%TODO(...)` markers never count.
_COMMENT_RE = re.compile(r"(?<!\\)%.*")


class BibError(Exception):
    """Raised on an unrecoverable bibliography problem surfaced to the user as fatal."""


@dataclass(frozen=True)
class Entry:
    key: str
    entrytype: str  # lowercased, e.g. "article", "inproceedings"
    fields: dict[str, str]
    raw: str  # the verbatim "@type{key, ... }" span
    source: str  # the file the entry was parsed from


@dataclass(frozen=True)
class Library:
    entries: dict[str, Entry] = field(default_factory=dict)
    # citekey -> {"item_key": str, "attachments": [absolute pdf path, ...]}
    zotero_meta: dict[str, dict] = field(default_factory=dict)

    @property
    def keys(self) -> set[str]:
        return set(self.entries)


@dataclass
class ResolveResult:
    entries: dict[str, Entry]
    unresolved: list[str]
    shadowed: list[tuple[str, str]]  # (citekey, extra filename that lost to the library)


# --------------------------------------------------------------------------------------
# BibTeX parsing (pure stdlib; retains each entry's verbatim span)
# --------------------------------------------------------------------------------------


def parse_bibtex(text: str, *, source: str) -> dict[str, Entry]:
    """Parse `@type{key, field = value, ...}` entries, keeping the raw span of each."""
    entries: dict[str, Entry] = {}
    cursor = 0
    while cursor < len(text):
        at_index = text.find("@", cursor)
        if at_index < 0:
            break
        open_brace = text.find("{", at_index)
        if open_brace < 0:
            break
        comma = text.find(",", open_brace)
        if comma < 0:
            break

        entrytype = text[at_index + 1 : open_brace].strip().lower()
        key = _sanitize_key(text[open_brace + 1 : comma].strip())
        if not key:
            raise BibError(
                f"BibTeX entry without a cite key in {source}; re-export as 'Better BibTeX'."
            )

        body_start = comma + 1
        depth = 1
        idx = body_start
        while idx < len(text) and depth > 0:
            char = text[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            idx += 1

        body = text[body_start : max(body_start, idx - 1)]
        entries[key] = Entry(
            key=key,
            entrytype=entrytype,
            fields=_parse_fields(body),
            raw=text[at_index:idx].strip(),
            source=source,
        )
        cursor = idx
    return entries


def _parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    i = 0
    while i < len(body):
        while i < len(body) and body[i] in {" ", "\n", "\r", "\t", ","}:
            i += 1
        if i >= len(body):
            break

        name_start = i
        while i < len(body) and re.match(r"[A-Za-z0-9_\-]", body[i]):
            i += 1
        name = body[name_start:i].strip().lower()
        if not name:
            i += 1
            continue

        while i < len(body) and body[i].isspace():
            i += 1
        if i >= len(body) or body[i] != "=":
            while i < len(body) and body[i] != ",":
                i += 1
            continue

        i += 1
        while i < len(body) and body[i].isspace():
            i += 1

        value, i = _parse_value(body, i)
        normalized = re.sub(r"\s+", " ", value).strip()
        if normalized:
            fields[name] = normalized

        while i < len(body) and body[i] not in {",", "\n"}:
            i += 1
        if i < len(body) and body[i] == ",":
            i += 1

    if "year" not in fields and "date" in fields:
        year = _extract_year(fields["date"])
        if year:
            fields["year"] = year
    elif "year" in fields:
        year = _extract_year(fields["year"])
        if year:
            fields["year"] = year
    return fields


def _parse_value(text: str, start: int) -> tuple[str, int]:
    if start >= len(text):
        return "", start
    marker = text[start]
    if marker == "{":
        depth = 1
        idx = start + 1
        while idx < len(text) and depth > 0:
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
            idx += 1
        return text[start + 1 : max(start + 1, idx - 1)], idx
    if marker == '"':
        idx = start + 1
        escaped = False
        while idx < len(text):
            char = text[idx]
            if char == '"' and not escaped:
                return text[start + 1 : idx], idx + 1
            escaped = char == "\\" and not escaped
            if char != "\\":
                escaped = False
            idx += 1
        return text[start + 1 :], idx
    idx = start
    while idx < len(text) and text[idx] not in {",", "\n", "\r"}:
        idx += 1
    return text[start:idx], idx


def _sanitize_key(raw: str) -> str:
    value = raw.strip().replace("/", "_").replace("\\", "_")
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^A-Za-z0-9_.:\-]", "_", value)
    return value.strip("_")


def _extract_year(raw: str) -> str:
    text = str(raw).strip()
    match = re.search(r"\b(\d{4})\b", text)
    return match.group(1) if match else ""


# --------------------------------------------------------------------------------------
# Library + extras loading
# --------------------------------------------------------------------------------------


def load_library(*, library_bib: Path | None, library_json: Path | None) -> Library:
    """The Zotero library. Missing files yield an empty `Library`, never an error --
    a project with only `parla/sources/bib/*.bib` and no Zotero export is valid."""
    entries: dict[str, Entry] = {}
    if library_bib is not None and library_bib.is_file():
        entries = parse_bibtex(library_bib.read_text(encoding="utf-8"), source=library_bib.name)
    return Library(entries=entries, zotero_meta=_load_zotero_meta(library_json))


def _load_zotero_meta(library_json: Path | None) -> dict[str, dict]:
    if library_json is None or not library_json.is_file():
        return {}
    try:
        data = json.loads(library_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return {}
    meta: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        citekey = str(item.get("citationKey") or "").strip()
        if not citekey:
            continue
        attachments = [
            str(att.get("path") or "").strip()
            for att in item.get("attachments") or []
            if isinstance(att, dict) and str(att.get("path") or "").strip().lower().endswith(".pdf")
        ]
        meta[citekey] = {
            "item_key": str(item.get("itemKey") or item.get("key") or "").strip(),
            "attachments": attachments,
        }
    return meta


def load_extras(extras_dir: Path) -> dict[str, Entry]:
    """Every `*.bib` under `parla/sources/bib/`, merged. Later files win on an intra-extras
    collision; `entry.source` records which file each entry came from."""
    if not extras_dir.is_dir():
        return {}
    merged: dict[str, Entry] = {}
    for path in sorted(extras_dir.glob("*.bib")):
        merged.update(parse_bibtex(path.read_text(encoding="utf-8"), source=path.name))
    return merged


# --------------------------------------------------------------------------------------
# Cite scanning, resolution, materialization
# --------------------------------------------------------------------------------------


def scan_cite_keys(tex_texts: Iterable[str]) -> list[str]:
    """Every citekey referenced by a `\\cite`-family command across the given TeX sources,
    in first-seen order. Line comments are stripped first."""
    return list(scan_cite_key_sources(("", text) for text in tex_texts))


def scan_cite_key_sources(named_texts: Iterable[tuple[str, str]]) -> dict[str, str]:
    """`{citekey: name of the first `(name, text)` source that cites it}`, first-seen order."""
    sources: dict[str, str] = {}
    for name, text in named_texts:
        stripped = "\n".join(_COMMENT_RE.sub("", line) for line in text.splitlines())
        for match in _CITE_RE.finditer(stripped):
            for key in _split_keys(match.group(1)):
                sources.setdefault(key, name)
    return sources


def _split_keys(blob: str) -> list[str]:
    return [part.strip() for part in blob.split(",") if part.strip() and part.strip() != "*"]


def resolve(
    citekeys: Iterable[str], *, library: Library, extras: dict[str, Entry]
) -> ResolveResult:
    """Resolve each citekey: library first, then extras, else unresolved. `shadowed`
    lists every key an extra defines that the library already provides (library wins),
    independent of whether it is cited."""
    resolved: dict[str, Entry] = {}
    unresolved: list[str] = []
    for key in dict.fromkeys(citekeys):
        if key in library.entries:
            resolved[key] = library.entries[key]
        elif key in extras:
            resolved[key] = extras[key]
        else:
            unresolved.append(key)
    shadowed = sorted(
        (key, extras[key].source) for key in extras if key in library.entries
    )
    return ResolveResult(entries=resolved, unresolved=unresolved, shadowed=shadowed)


_HEADER = (
    f"% Generated by {NAME} from the Zotero library + {PROJECT_DIR}/sources/bib/*.bib.\n"
    "% Do not edit and do not commit -- regenerated on every build.\n"
)


def render(result: ResolveResult) -> str:
    body = "\n\n".join(result.entries[key].raw.strip() for key in sorted(result.entries))
    return _HEADER + ("\n" + body + "\n" if body else "")


def format_unresolved(unresolved: Iterable[str], sources: Mapping[str, str] | None = None) -> str:
    """The message body for a fatal unresolved-citekey set: one citekey per line, each
    followed by where it is cited (dimmed on a tty so the citekeys stand out)."""
    lines = [f"citekey(s) not found in the Zotero library or {PROJECT_DIR}/sources/bib/*.bib:"]
    for key in sorted(unresolved):
        lines.append(f"- {key}")
        origin = (sources or {}).get(key)
        if origin:
            lines.append(_dim(f"    ↳ requested from: {origin}"))
    return "\n".join(lines)


def _dim(text: str) -> str:
    return f"\033[38;5;245m{text}\033[0m" if sys.stderr.isatty() else text


def materialize(result: ResolveResult, out: Path) -> bool:
    """Write `out` (`parla/artifacts/<name>/references.bib`) from `result`. Returns `True` when the file
    was written, `False` when its content was already byte-identical -- the no-op guard
    keeps `build --watch` from a regenerate/rebuild loop."""
    content = render(result)
    if out.is_file() and out.read_text(encoding="utf-8") == content:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return True
