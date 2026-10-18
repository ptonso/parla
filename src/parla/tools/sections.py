"""PDF pages to sections: copied from `texfy_ai.core.summarize.bib_ingest`, where the sections fed a
model. `_cleanup_*`, `_segment_sections`, `_filter_sections` and what they call are unchanged."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .pdf import (
    CanonicalPdfLine,
    CanonicalPdfPage,
    get_pdf_extractor_default_configs,
)
from .pdf.heuristics import (
    canonical_section_match,
    heading_normalization_details,
    infer_text_heading_level,
    looks_like_explicit_section_heading,
    looks_like_noise_heading,
    normalize_line_text,
    strip_inline_markdown_formatting,
)

_SECTIONING_VERSION = 4


DEFAULT_INGEST_CONFIG: dict[str, Any] = {
    "extractor": "pdftotext",
    "chunk_chars": 1400,
    "chunk_overlap_chars": 180,
    "min_chunk_chars": 350,
    "superchunk_target_chunks": 4,
    "superchunk_flex_chunks": 1,
    "fix_hyphenation": True,
    "normalize_whitespace": True,
    "include_appendix": False,
    "sectioning_version": _SECTIONING_VERSION,
}


def _build_default_ingest_settings() -> dict[str, Any]:
    defaults = _deep_copy_jsonish(DEFAULT_INGEST_CONFIG)
    defaults["extractors"] = get_pdf_extractor_default_configs()
    defaults["extractor"] = str(defaults.get("extractor", "pdftotext")).strip().lower()
    defaults["extractor_config"] = _deep_copy_jsonish(defaults["extractors"].get(defaults["extractor"], {}))
    defaults["sectioning_version"] = _SECTIONING_VERSION
    return defaults


def _deep_copy_jsonish(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _persisted_normalization_config(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_chars": int(settings.get("chunk_chars", DEFAULT_INGEST_CONFIG["chunk_chars"])),
        "chunk_overlap_chars": int(settings.get("chunk_overlap_chars", DEFAULT_INGEST_CONFIG["chunk_overlap_chars"])),
        "min_chunk_chars": int(settings.get("min_chunk_chars", DEFAULT_INGEST_CONFIG["min_chunk_chars"])),
        "superchunk_target_chunks": int(
            settings.get("superchunk_target_chunks", DEFAULT_INGEST_CONFIG["superchunk_target_chunks"])
        ),
        "superchunk_flex_chunks": int(
            settings.get("superchunk_flex_chunks", DEFAULT_INGEST_CONFIG["superchunk_flex_chunks"])
        ),
        "fix_hyphenation": bool(settings.get("fix_hyphenation", DEFAULT_INGEST_CONFIG["fix_hyphenation"])),
        "normalize_whitespace": bool(
            settings.get("normalize_whitespace", DEFAULT_INGEST_CONFIG["normalize_whitespace"])
        ),
        "include_appendix": bool(settings.get("include_appendix", DEFAULT_INGEST_CONFIG["include_appendix"])),
        "extractor_config": _deep_copy_jsonish(settings.get("extractor_config", {})),
        "sectioning_version": int(settings.get("sectioning_version", _SECTIONING_VERSION)),
    }


def _normalized_paper_matches_settings(data: dict[str, Any], settings: dict[str, Any]) -> bool:
    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    extractor = str(config.get("extractor", "")).strip().lower()
    expected_extractor = str(settings.get("extractor", "")).strip().lower()
    if extractor != expected_extractor:
        return False
    normalization = config.get("normalization") if isinstance(config.get("normalization"), dict) else {}
    return normalization == _persisted_normalization_config(settings)


def _pdf_path_candidates(raw: str, bib_dir: Path) -> list[Path]:
    if not raw:
        return []

    resolved: list[Path] = []
    seen: set[str] = set()

    for match in re.finditer(r"((?:file://)?[^;\n]+?\.pdf)", raw, flags=re.IGNORECASE):
        token = match.group(1).strip().strip("{}")
        if not token:
            continue

        token = token.replace("\\\\", "\\")
        if token.startswith("file://"):
            token = token[7:]
        token = unquote(token)

        path = Path(token)
        if not path.is_absolute():
            path = (bib_dir / path).resolve()
        else:
            path = path.resolve()

        key = path.as_posix()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(path)

    return resolved


def _fingerprint_pdf(path: Path) -> dict[str, Any]:
    sha256 = hashlib.sha256()
    with path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            sha256.update(chunk)

    return {
        "sha256": sha256.hexdigest(),
        "bytes": path.stat().st_size,
    }


def _cleanup_canonical_pages(
    raw_pages: list[CanonicalPdfPage],
    settings: dict[str, Any],
) -> list[CanonicalPdfPage]:
    return [_cleanup_canonical_page(page, settings) for page in raw_pages]


def _cleanup_canonical_page(page: CanonicalPdfPage, settings: dict[str, Any]) -> CanonicalPdfPage:
    cleanup_cfg = settings.get("cleanup") if isinstance(settings.get("cleanup"), dict) else settings
    cleaned_lines: list[CanonicalPdfLine] = []
    for line in page.lines:
        cleaned_text = _cleanup_line_text(line.text, cleanup_cfg)
        if not cleaned_text:
            continue
        cleaned_lines.append(
            CanonicalPdfLine(
                page=int(line.page),
                text=cleaned_text,
                heading_level=line.heading_level,
                heading_source=line.heading_source if line.heading_level is not None else "none",
            )
        )

    if bool(cleanup_cfg.get("fix_hyphenation", True)):
        cleaned_lines = list(_fix_hyphenated_lines(cleaned_lines))

    return CanonicalPdfPage(
        page=int(page.page),
        text="\n".join(line.text for line in cleaned_lines).strip(),
        lines=tuple(cleaned_lines),
    )


def _cleanup_line_text(raw_text: str, cleanup_cfg: dict[str, Any]) -> str:
    text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    if bool(cleanup_cfg.get("normalize_whitespace", True)):
        return normalize_line_text(text)
    return text.strip()


def _fix_hyphenated_lines(lines: list[CanonicalPdfLine]) -> tuple[CanonicalPdfLine, ...]:
    merged: list[CanonicalPdfLine] = []
    for line in lines:
        if merged and _should_merge_hyphenated_lines(merged[-1], line):
            previous = merged.pop()
            merged.append(
                CanonicalPdfLine(
                    page=int(previous.page),
                    text=f"{previous.text[:-1]}{line.text}",
                    heading_level=None,
                    heading_source="none",
                )
            )
            continue
        merged.append(line)
    return tuple(merged)


def _should_merge_hyphenated_lines(left: CanonicalPdfLine, right: CanonicalPdfLine) -> bool:
    if left.heading_level is not None or right.heading_level is not None:
        return False
    if not re.search(r"\w-$", left.text):
        return False
    return bool(re.match(r"^\w", right.text))


def _segment_sections(
    pages: list[CanonicalPdfPage],
    include_debug: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
    lines = _prepare_section_lines(pages)

    if not lines:
        if include_debug:
            return [], {
                "schema_version": 4,
                "line_count": 0,
                "canonical_lines": [],
                "decisions": [],
                "sections": [],
                "detected_sections": [],
                "included_sections": [],
                "excluded_sections": [],
                "section_filters": [],
                "counts": {
                    "detected": 0,
                    "included": 0,
                    "excluded": 0,
                },
            }
        return []

    sections: list[dict[str, Any]] = []
    current = _new_section(label="front_matter", page=int(lines[0]["page"]))
    body_heading_seen = False
    appendix_region_active = False
    decisions: list[dict[str, Any]] = []

    for line_index, raw_item in enumerate(lines, start=1):
        page_number = int(raw_item["page"])
        line = normalize_line_text(raw_item["text"])
        item = CanonicalPdfLine(
            page=page_number,
            text=line,
            heading_level=raw_item["heading_level"],
            heading_source=raw_item["heading_source"],
        )
        body_heading_seen_before = body_heading_seen
        current_label_before = str(current.get("label", "")).strip()
        analysis = _heading_analysis(item)
        analysis["merged_with_next"] = bool(raw_item.get("merged_with_next"))
        analysis["tail_split"] = bool(raw_item.get("tail_split"))
        should_split = _is_structural_heading_candidate(analysis)
        new_section_label = ""
        suppression_reason = ""

        if should_split:
            new_section_label = _resolve_section_label(
                current_label=current_label_before,
                analysis=analysis,
                body_heading_seen=body_heading_seen,
                appendix_region_active=appendix_region_active,
            )
            should_split, suppression_reason = _should_start_section(
                current_label=current_label_before,
                new_label=new_section_label,
                analysis=analysis,
                body_heading_seen=body_heading_seen,
            )

        if should_split:
            if current["lines"]:
                sections.append(current)
            current = _new_section(
                label=new_section_label,
                page=page_number,
                heading_text=line,
                heading_level=item.heading_level,
                split_source=item.heading_source,
            )
            if new_section_label == "appendix":
                appendix_region_active = True
            elif new_section_label == "references":
                appendix_region_active = False
            if _label_enters_body(new_section_label):
                body_heading_seen = True
            if include_debug:
                decisions.append(
                    _section_debug_decision(
                        action="start_section",
                        reason=_section_split_reason(
                            analysis=analysis,
                            label=new_section_label,
                        ),
                        line_index=line_index,
                        page_number=page_number,
                        line=line,
                        analysis=analysis,
                        body_heading_seen_before=body_heading_seen_before,
                        current_label_before=current_label_before,
                        new_section_label=new_section_label,
                        split_source=item.heading_source,
                    )
                )
            continue

        if include_debug and suppression_reason:
            decisions.append(
                _section_debug_decision(
                    action="append_line",
                    reason=suppression_reason,
                    line_index=line_index,
                    page_number=page_number,
                    line=line,
                    analysis=analysis,
                    body_heading_seen_before=body_heading_seen_before,
                    current_label_before=current_label_before,
                    new_section_label="",
                    split_source=item.heading_source,
                )
            )

        if _label_enters_body(str(current.get("label", "")).strip()):
            body_heading_seen = True
        current["page_end"] = page_number
        current["lines"].append(line)
        if _label_enters_body(str(current.get("label", "")).strip()):
            body_heading_seen = True
        if include_debug and not suppression_reason:
            decisions.append(
                _section_debug_decision(
                    action="append_line",
                    reason=_section_append_reason(
                        analysis=analysis,
                    ),
                    line_index=line_index,
                    page_number=page_number,
                    line=line,
                    analysis=analysis,
                    body_heading_seen_before=body_heading_seen_before,
                    current_label_before=current_label_before,
                    new_section_label="",
                    split_source=item.heading_source if item.heading_level is not None else "none",
                )
            )

    if current["lines"]:
        sections.append(current)

    normalized: list[dict[str, Any]] = []
    for idx, section in enumerate([section for section in sections if section.get("lines")], start=1):
        section_id = f"s{idx:03d}"
        normalized.append(
            {
                "section_id": section_id,
                "label": section["label"],
                "page_start": section["page_start"],
                "page_end": section["page_end"],
                "chunk_ids": [],
                "heading_text": str(section.get("heading_text", "")).strip(),
                "heading_level": section.get("heading_level"),
                "split_source": str(section.get("split_source", "none")).strip() or "none",
                "text": "\n".join(section["lines"]).strip(),
            }
        )

    if not normalized:
        fallback_sections = [
            {
                "section_id": "s001",
                "label": "body",
                "page_start": int(lines[0]["page"] or 1),
                "page_end": int(lines[-1]["page"] or 1),
                "chunk_ids": [],
                "heading_text": "",
                "heading_level": None,
                "split_source": "none",
                "text": "\n".join(normalize_line_text(line["text"]) for line in lines if normalize_line_text(line["text"])),
            }
        ]
        if include_debug:
            return fallback_sections, {
                "schema_version": 4,
                "line_count": len(lines),
                "canonical_lines": [_canonical_line_debug_item(line) for line in lines],
                "decisions": decisions,
                "sections": _section_debug_summary(fallback_sections),
                "detected_sections": _section_debug_summary(fallback_sections),
                "included_sections": _section_debug_summary(fallback_sections),
                "excluded_sections": [],
                "section_filters": [
                    _section_filter_decision(section, included=True, reason="included_body_section")
                    for section in fallback_sections
                ],
                "counts": {
                    "detected": len(fallback_sections),
                    "included": len(fallback_sections),
                    "excluded": 0,
                },
            }
        return fallback_sections

    if include_debug:
        return normalized, {
            "schema_version": 4,
            "line_count": len(lines),
            "canonical_lines": [_canonical_line_debug_item(line) for line in lines],
            "decisions": decisions,
            "sections": _section_debug_summary(normalized),
            "detected_sections": _section_debug_summary(normalized),
            "included_sections": _section_debug_summary(normalized),
            "excluded_sections": [],
            "section_filters": [
                _section_filter_decision(section, included=True, reason="included_detected_section")
                for section in normalized
            ],
            "counts": {
                "detected": len(normalized),
                "included": len(normalized),
                "excluded": 0,
            },
        }
    return normalized


def _filter_sections(
    sections: list[dict[str, Any]],
    settings: dict[str, Any],
    include_debug: bool = False,
    section_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
    included_sections: list[dict[str, Any]] = []
    excluded_sections: list[dict[str, Any]] = []
    filter_decisions: list[dict[str, Any]] = []
    include_appendix = bool(settings.get("include_appendix", False))

    for section in sections:
        label = str(section.get("label", "")).strip()
        if label == "references":
            included = False
            reason = "excluded_reference_section"
        elif label == "appendix" and not include_appendix:
            included = False
            reason = "excluded_appendix_by_default"
        elif label == "appendix":
            included = True
            reason = "included_appendix_by_config"
        elif label == "front_matter":
            included = True
            reason = "included_front_matter_section"
        else:
            included = True
            reason = "included_body_section"

        section_copy = dict(section)
        filter_decisions.append(_section_filter_decision(section_copy, included=included, reason=reason))
        if included:
            included_sections.append(section_copy)
        else:
            excluded_sections.append(_section_debug_summary_item(section_copy, reason=reason))

    if not include_debug:
        return included_sections

    report = dict(section_report or {})
    report["schema_version"] = 4
    report["sections"] = _section_debug_summary(included_sections)
    report["detected_sections"] = _section_debug_summary(sections)
    report["included_sections"] = _section_debug_summary(included_sections)
    report["excluded_sections"] = excluded_sections
    report["section_filters"] = filter_decisions
    report["counts"] = {
        "detected": len(sections),
        "included": len(included_sections),
        "excluded": len(excluded_sections),
    }
    return included_sections, report


def _prepare_section_lines(pages: list[CanonicalPdfPage]) -> list[dict[str, Any]]:
    lines = list(_iter_section_page_lines(pages))
    lines = _split_back_matter_tail_markers(lines)
    lines = _merge_numbered_heading_lines(lines)
    return lines


def _iter_section_page_lines(pages: list[CanonicalPdfPage]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for page in pages:
        if isinstance(page, CanonicalPdfPage):
            page_number = int(page.page)
            page_lines = list(page.lines)
        elif isinstance(page, dict):
            page_number = int(page.get("page", 0) or 0) or 1
            page_lines = []
            for raw_line in str(page.get("text", "")).replace("\r\n", "\n").replace("\r", "\n").splitlines():
                line_text = normalize_line_text(raw_line)
                if not line_text:
                    continue
                heading_level = infer_text_heading_level(line_text)
                page_lines.append(
                    CanonicalPdfLine(
                        page=page_number,
                        text=line_text,
                        heading_level=heading_level,
                        heading_source="inferred_text" if heading_level is not None else "none",
                    )
                )
        else:
            continue

        for line in page_lines:
            line_text = normalize_line_text(line.text)
            if not line_text:
                continue
            if line.heading_level is not None:
                line_text = strip_inline_markdown_formatting(line_text)
            prepared.append(
                {
                    "page": page_number,
                    "text": line_text,
                    "heading_level": line.heading_level,
                    "heading_source": line.heading_source if line.heading_level is not None else "none",
                    "merged_with_next": False,
                    "tail_split": False,
                }
            )
    return prepared


def _split_back_matter_tail_markers(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    split_lines: list[dict[str, Any]] = []
    for line in lines:
        if line["heading_level"] is not None:
            split_lines.append(dict(line))
            continue

        text = normalize_line_text(line["text"])
        tail_split = _tail_back_matter_marker_match(text)
        if tail_split is None:
            split_lines.append(dict(line))
            continue

        body_text, heading_text = tail_split
        split_lines.append(
            {
                **line,
                "text": body_text,
            }
        )
        split_lines.append(
            {
                **line,
                "text": heading_text,
                "heading_level": 1,
                "heading_source": "inferred_text",
                "tail_split": True,
            }
        )
    return split_lines


def _tail_back_matter_marker_match(line: str) -> tuple[str, str] | None:
    normalized = normalize_line_text(line)
    for marker in ["Literature Cited", "Works Cited", "Bibliography", "References"]:
        pattern = rf"^(?P<body>.+?)\s+(?P<marker>{re.escape(marker)})\s*$"
        match = re.match(pattern, normalized)
        if not match:
            continue
        body_text = normalize_line_text(match.group("body"))
        if len(body_text) < 20 or body_text.endswith((".", "!", "?", ";", ":")):
            continue
        return body_text, marker
    return None


def _merge_numbered_heading_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        current = dict(lines[index])
        if index + 1 < len(lines):
            next_item = dict(lines[index + 1])
            if _should_merge_heading_prefix_line(current, next_item):
                current["text"] = f"{normalize_line_text(current['text'])} {normalize_line_text(next_item['text'])}".strip()
                heading_levels = [
                    level
                    for level in [current["heading_level"], next_item["heading_level"]]
                    if level is not None
                ]
                current["heading_level"] = min(heading_levels) if heading_levels else next_item["heading_level"]
                current["heading_source"] = str(next_item["heading_source"] or current["heading_source"])
                current["merged_with_next"] = True
                current["tail_split"] = bool(current.get("tail_split")) or bool(next_item.get("tail_split"))
                merged.append(current)
                index += 2
                continue
        merged.append(current)
        index += 1
    return merged


def _should_merge_heading_prefix_line(current: dict[str, Any], next_item: dict[str, Any]) -> bool:
    if int(current.get("page", 0) or 0) != int(next_item.get("page", 0) or 0):
        return False
    if current.get("heading_level") is None or next_item.get("heading_level") is None:
        return False
    current_details = heading_normalization_details(str(current.get("text", "")))
    next_details = heading_normalization_details(str(next_item.get("text", "")))
    if current_details["prefix_kind"] not in {"numeric", "roman", "alpha_hierarchical", "alpha_single"}:
        return False
    if current_details["normalized_heading_core"]:
        return False
    if not next_details["normalized_heading_core"]:
        return False
    if looks_like_noise_heading(str(next_item.get("text", "")), details=next_details):
        return False
    return True


def _new_section(
    label: str,
    page: int,
    heading_text: str = "",
    heading_level: int | None = None,
    split_source: str = "none",
) -> dict[str, Any]:
    return {
        "label": label or "body",
        "page_start": page,
        "page_end": page,
        "heading_text": heading_text,
        "heading_level": heading_level,
        "split_source": split_source,
        "lines": [],
    }


def _label_enters_body(label: str) -> bool:
    return label not in {"", "front_matter", "abstract", "appendix", "references"}


def _is_structural_heading_candidate(analysis: dict[str, Any]) -> bool:
    heading_level = analysis.get("heading_level")
    if heading_level is None:
        return False
    if bool(analysis.get("looks_like_noise_heading")):
        return False

    heading_source = str(analysis.get("heading_source", "")).strip()
    canonical_label = str(analysis.get("canonical_label", "")).strip()
    prefix_kind = str(analysis.get("prefix_kind", "")).strip()
    explicit = bool(analysis.get("looks_like_explicit_section_heading"))
    word_count = int(analysis.get("word_count", 0) or 0)
    line_length = int(analysis.get("line_length", 0) or 0)

    if canonical_label:
        return True
    if prefix_kind:
        return explicit or heading_source != "none"
    if heading_source == "extractor_markdown":
        return explicit and word_count >= 2
    if heading_source == "inferred_style":
        if heading_level <= 2 and explicit:
            return True
        return explicit and word_count >= 2 and line_length >= 8
    if heading_source == "inferred_text":
        return explicit and word_count >= 2
    return False


def _resolve_section_label(
    *,
    current_label: str,
    analysis: dict[str, Any],
    body_heading_seen: bool,
    appendix_region_active: bool,
) -> str:
    label = str(analysis.get("canonical_label", "")).strip()
    prefix_kind = str(analysis.get("prefix_kind", "")).strip()

    if label == "references":
        return "references"
    if current_label == "references":
        return "appendix" if label == "appendix" else "references"
    if label == "appendix":
        return "appendix"
    if appendix_region_active and label != "references":
        return "appendix"
    if current_label == "appendix" and prefix_kind in {"appendix_keyword", "alpha_hierarchical", "alpha_single"}:
        return "appendix"
    if not body_heading_seen:
        if label in {"abstract", "introduction"}:
            return label
        if label and _looks_like_confident_body_entry(analysis):
            return label
        if not label and _looks_like_confident_body_entry(analysis):
            return "body"
        return "front_matter"
    if label:
        return label
    return "body"


def _should_start_section(
    *,
    current_label: str,
    new_label: str,
    analysis: dict[str, Any],
    body_heading_seen: bool,
) -> tuple[bool, str]:
    if current_label == "references" and new_label != "appendix":
        return False, "Kept the line inside the references section because back matter remains references until an appendix heading appears."
    if new_label == "front_matter":
        return False, "Kept the line inside front matter because it was not a confident body-entry heading."
    if (not body_heading_seen) and new_label == "body" and not _looks_like_confident_body_entry(analysis):
        return False, "Kept the line inside front matter because unmatched early headings require stronger evidence before entering the body."
    return True, ""


def _looks_like_confident_body_entry(analysis: dict[str, Any]) -> bool:
    label = str(analysis.get("canonical_label", "")).strip()
    prefix_kind = str(analysis.get("prefix_kind", "")).strip()
    explicit = bool(analysis.get("looks_like_explicit_section_heading"))
    heading_level = int(analysis.get("heading_level", 0) or 0)
    heading_source = str(analysis.get("heading_source", "")).strip()
    word_count = int(analysis.get("word_count", 0) or 0)

    if label in {"abstract", "introduction"}:
        return True
    if prefix_kind in {"numeric", "roman", "alpha_hierarchical"} and explicit and word_count >= 2:
        return True
    if label in {"background", "experiments", "method"} and explicit:
        if heading_source == "extractor_markdown":
            return True
        if heading_source == "inferred_style" and heading_level <= 2:
            return True
    return False


def _heading_analysis(line: CanonicalPdfLine | str) -> dict[str, Any]:
    if isinstance(line, CanonicalPdfLine):
        stripped = normalize_line_text(line.text)
        heading_level = line.heading_level
        heading_source = line.heading_source
    else:
        stripped = normalize_line_text(line)
        heading_level = infer_text_heading_level(stripped)
        heading_source = "inferred_text" if heading_level is not None else "none"
    details = heading_normalization_details(stripped)
    cleaned, matched_token, canonical_label = _canonical_section_match(stripped)
    ends_with_terminal_punctuation = stripped.endswith((".", "?", "!", ";", ":"))
    matches_numbered_heading = details["prefix_kind"] in {"numeric", "roman", "alpha_hierarchical", "alpha_single"}
    uppercase_letters = sum(1 for char in stripped if char.isalpha() and char.isupper())
    letters = sum(1 for char in stripped if char.isalpha())
    uppercase_ratio = (uppercase_letters / letters) if letters > 0 else 0.0
    word_count = len(stripped.split())
    looks_like_major_heading = heading_level is not None
    return {
        "cleaned_text": cleaned,
        "matched_token": matched_token,
        "canonical_label": canonical_label,
        "normalized_full_text": details["normalized_full_text"],
        "normalized_heading_core": details["normalized_heading_core"],
        "prefix_kind": details["prefix_kind"],
        "prefix_text": details["prefix_text"],
        "heading_level": heading_level,
        "heading_source": heading_source,
        "matches_numbered_heading": matches_numbered_heading,
        "uppercase_ratio": round(uppercase_ratio, 3),
        "word_count": word_count,
        "line_length": len(stripped),
        "ends_with_terminal_punctuation": ends_with_terminal_punctuation,
        "looks_like_major_heading": looks_like_major_heading,
        "looks_like_explicit_section_heading": _looks_like_explicit_section_heading(stripped),
        "looks_like_noise_heading": looks_like_noise_heading(
            stripped,
            details=details,
            canonical_label=canonical_label,
        ),
    }


def _looks_like_explicit_section_heading(line: str) -> bool:
    return looks_like_explicit_section_heading(line)


def _canonical_section_match(line: str) -> tuple[str, str, str]:
    return canonical_section_match(line)


def _section_debug_decision(
    *,
    action: str,
    reason: str,
    line_index: int,
    page_number: int,
    line: str,
    analysis: dict[str, Any],
    body_heading_seen_before: bool,
    current_label_before: str,
    new_section_label: str,
    split_source: str,
) -> dict[str, Any]:
    return {
        "line_index": line_index,
        "page": page_number,
        "line": line,
        "current_section_label_before": current_label_before,
        "body_heading_seen_before": body_heading_seen_before,
        "action": action,
        "new_section_label": new_section_label,
        "split_source": split_source,
        "reason": reason,
        "analysis": analysis,
    }


def _section_split_reason(*, analysis: dict[str, Any], label: str) -> str:
    matched_token = str(analysis.get("matched_token", "")).strip()
    heading_source = str(analysis.get("heading_source", "")).strip()
    prefix_kind = str(analysis.get("prefix_kind", "")).strip()
    if heading_source == "extractor_markdown":
        return f"Started a new '{label}' section because the extractor emitted this line as a markdown heading."
    if heading_source == "inferred_style":
        return f"Started a new '{label}' section because the canonical style-based heading heuristic marked this line."
    if matched_token:
        return (
            f"Started a new '{label}' section because the line matched canonical token "
            f"'{matched_token}' and the canonical heading field was set."
        )
    if prefix_kind:
        return (
            f"Started a new '{label}' section because the line looked like a structural heading with "
            f"prefix kind '{prefix_kind}'."
        )
    if bool(analysis.get("matches_numbered_heading")):
        return f"Started a new '{label}' section because the canonical heading field came from a numbered heading pattern."
    if bool(analysis.get("looks_like_explicit_section_heading")):
        return f"Started a new '{label}' section because the canonical heading field came from an explicit section heading."
    return f"Started a new '{label}' section because the canonical heading field was present on this line."


def _section_append_reason(*, analysis: dict[str, Any]) -> str:
    if analysis.get("heading_level") is not None and analysis.get("looks_like_noise_heading"):
        return "Kept the line inside the current section because it looked like table, metadata, or layout noise instead of a section heading."
    if analysis.get("heading_level") is not None:
        return "Kept the line inside the current section because the front-matter/body region guard suppressed this heading."
    if analysis.get("canonical_label"):
        return "Kept the line inside the current section because it did not pass the split guard."
    return "Kept the line inside the current section because it did not look like a section heading."


def _section_filter_decision(section: dict[str, Any], *, included: bool, reason: str) -> dict[str, Any]:
    text = str(section.get("text", "")).strip()
    return {
        "section_id": str(section.get("section_id", "")).strip(),
        "label": str(section.get("label", "")).strip(),
        "page_start": int(section.get("page_start", 0) or 0),
        "page_end": int(section.get("page_end", 0) or 0),
        "char_count": len(text),
        "included": bool(included),
        "reason": reason,
    }


def _section_debug_summary_item(section: dict[str, Any], *, reason: str = "") -> dict[str, Any]:
    text = str(section.get("text", "")).strip()
    item = {
        "section_id": str(section.get("section_id", "")).strip(),
        "label": str(section.get("label", "")).strip(),
        "page_start": int(section.get("page_start", 0) or 0),
        "page_end": int(section.get("page_end", 0) or 0),
        "heading_text": str(section.get("heading_text", "")).strip(),
        "heading_level": section.get("heading_level"),
        "split_source": str(section.get("split_source", "none")).strip() or "none",
        "char_count": len(text),
        "preview": text[:240],
    }
    if reason:
        item["reason"] = reason
    return item


def _section_debug_summary(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_section_debug_summary_item(section) for section in sections]


def _canonical_line_debug_item(line: CanonicalPdfLine | dict[str, Any]) -> dict[str, Any]:
    if isinstance(line, CanonicalPdfLine):
        text = normalize_line_text(line.text)
        heading_level = line.heading_level
        heading_source = line.heading_source
        page = int(line.page)
        merged_with_next = False
        tail_split = False
    else:
        text = normalize_line_text(line.get("text", ""))
        heading_level = line.get("heading_level")
        heading_source = str(line.get("heading_source", "none") or "none")
        page = int(line.get("page", 0) or 0)
        merged_with_next = bool(line.get("merged_with_next"))
        tail_split = bool(line.get("tail_split"))
    details = heading_normalization_details(text)
    return {
        "page": page,
        "text": text,
        "heading_level": heading_level,
        "heading_source": heading_source,
        "normalized_heading_core": details["normalized_heading_core"],
        "prefix_kind": details["prefix_kind"],
        "merged_with_next": merged_with_next,
        "tail_split": tail_split,
    }
