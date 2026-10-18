"""`parla tool source`: the text of a cited paper, by section, from the PDF the library lists.

The sections come from `sections.py`; the settings are the constants texfy-ai's
`conf/system/bib.yaml` used."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .. import config as config_mod
from ..engines.latex import bib
from ..names import NAME
from .pdf import get_pdf_extractor
from .sections import (
    _build_default_ingest_settings,
    _cleanup_canonical_pages,
    _deep_copy_jsonish,
    _filter_sections,
    _fingerprint_pdf,
    _normalized_paper_matches_settings,
    _pdf_path_candidates,
    _persisted_normalization_config,
    _segment_sections,
)

EXTRACTOR = "pymupdf4llm"  # the extractor texfy-ai's conf/system/bib.yaml selects


class SourceError(Exception):
    """A cited paper's text cannot be produced."""


@dataclass(frozen=True)
class Section:
    label: str
    page_start: int
    page_end: int
    text: str


def settings() -> dict[str, Any]:
    merged = _build_default_ingest_settings()
    merged["extractor"] = EXTRACTOR
    merged["extractor_config"] = _deep_copy_jsonish(merged["extractors"][EXTRACTOR])
    return merged


def cache_path(citekey: str) -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or "~/.cache").expanduser()
    return base / NAME / "source" / f"{citekey}.json"


def find_pdf(citekey: str) -> Path:
    """The PDF the library lists for `citekey`: the entry's `file` field, then the Zotero attachments."""
    library_bib = config_mod.library_bib()
    library = bib.load_library(library_bib=library_bib, library_json=config_mod.library_json())
    entry = library.entries.get(citekey)
    if entry is None:
        raise SourceError(f"'{citekey}' has no entry in the library ({library_bib or 'no [storage].library_bib set'})")
    raws = [entry.fields.get("file", ""), *library.zotero_meta.get(citekey, {}).get("attachments", [])]
    base = library_bib.parent if library_bib is not None else Path.cwd()
    for raw in raws:
        for candidate in _pdf_path_candidates(raw, bib_dir=base):
            if candidate.is_file():
                return candidate
    raise SourceError(f"'{citekey}' lists no readable PDF")


def load_sections(citekey: str) -> list[Section]:
    pdf = find_pdf(citekey)
    config = settings()
    fingerprint = _fingerprint_pdf(pdf)
    path = cache_path(citekey)
    doc = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    if doc is None or doc.get("pdf_fingerprint") != fingerprint or not _normalized_paper_matches_settings(doc, config):
        extractor = get_pdf_extractor(EXTRACTOR)
        extractor.ensure_available()
        raw = extractor.extract_pages(pdf, config["extractor_config"])
        if not raw:
            raise SourceError(f"no pages could be read from {pdf}")
        detected = cast(list[dict[str, Any]], _segment_sections(_cleanup_canonical_pages(raw, config)))
        sections = cast(list[dict[str, Any]], _filter_sections(detected, settings=config))
        if not sections:
            raise SourceError(f"no text could be read from {pdf}")
        doc = {
            "bibtex_key": citekey,
            "pdf_fingerprint": fingerprint,
            "sections": [{k: s[k] for k in ("label", "page_start", "page_end", "text")} for s in sections],
            "config": {"extractor": EXTRACTOR, "normalization": _persisted_normalization_config(config)},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return [Section(s["label"], int(s["page_start"]), int(s["page_end"]), s["text"]) for s in doc["sections"]]


def render(sections: list[Section], *, label: str | None = None, pages: tuple[int, int] | None = None) -> str:
    """Each section under a `## <label> (pp. a-b)` heading. `label` keeps one section; `pages`
    keeps the sections that touch the range."""
    kept = [
        s for s in sections
        if (label is None or s.label == label) and (pages is None or (s.page_end >= pages[0] and s.page_start <= pages[1]))
    ]
    if not kept:
        raise SourceError(f"no section matches (have: {', '.join(dict.fromkeys(s.label for s in sections))})")
    return "\n\n".join(f"## {s.label} (pp. {s.page_start}-{s.page_end})\n{s.text}" for s in kept)
