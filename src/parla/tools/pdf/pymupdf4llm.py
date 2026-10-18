from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

from ...names import NAME
from .base import CanonicalPdfLine, CanonicalPdfPage, PdfExtractor
from .heuristics import normalize_line_text, strip_markdown_heading

PYMUPDF4LLM_DEFAULT_CONFIG: dict[str, Any] = {
    "heading": {
        "max_level": 6,
    }
}


def ensure_available() -> None:
    _load_pymupdf4llm()


def extract_pages(pdf_path: Path, config: dict[str, Any]) -> list[CanonicalPdfPage]:
    pymupdf4llm = _load_pymupdf4llm()
    heading_cfg = _resolve_heading_config(config)
    page_chunks = pymupdf4llm.to_markdown(
        str(pdf_path),
        page_chunks=True,
        header=False,
        footer=False,
        use_ocr=False,
        detect_bg_color=False,
        graphics_limit=300,
        ignore_images=True,
    )
    if not isinstance(page_chunks, list):
        raise RuntimeError("pymupdf4llm returned a non-page-chunk result.")

    pages: list[CanonicalPdfPage] = []
    for expected_page, item in enumerate(page_chunks, start=1):
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        page_number = _coerce_page_number(metadata.get("page_number"), fallback=expected_page)
        text = str(item.get("text", "") or "")
        lines = _canonical_lines_from_markdown(page_number, text, heading_cfg)
        pages.append(_canonical_page(page_number, lines))
    return pages


def _load_pymupdf4llm():
    try:
        return import_module("pymupdf4llm")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"`{NAME} tool source` needs the optional `pdf` extra: pip install '{NAME}[pdf]'."
        ) from exc


def _resolve_heading_config(config: dict[str, Any]) -> dict[str, Any]:
    heading_cfg = config.get("heading") if isinstance(config.get("heading"), dict) else {}
    default_heading = PYMUPDF4LLM_DEFAULT_CONFIG["heading"]
    return {
        "max_level": max(1, min(6, int(heading_cfg.get("max_level", default_heading["max_level"])))),
    }


def _coerce_page_number(raw: Any, fallback: int) -> int:
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return fallback


def _canonical_lines_from_markdown(
    page_number: int,
    text: str,
    heading_cfg: dict[str, Any],
) -> tuple[CanonicalPdfLine, ...]:
    lines: list[CanonicalPdfLine] = []
    max_level = int(heading_cfg["max_level"])
    for raw_line in str(text).replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line_text = normalize_line_text(raw_line)
        if not line_text:
            continue
        stripped_text, heading_level = strip_markdown_heading(line_text)
        if heading_level is not None:
            heading_level = max(1, min(max_level, heading_level))
        lines.append(
            CanonicalPdfLine(
                page=page_number,
                text=stripped_text,
                heading_level=heading_level,
                heading_source="extractor_markdown" if heading_level is not None else "none",
            )
        )
    return tuple(lines)


def _canonical_page(page_number: int, lines: tuple[CanonicalPdfLine, ...]) -> CanonicalPdfPage:
    return CanonicalPdfPage(
        page=page_number,
        text="\n".join(line.text for line in lines).strip(),
        lines=lines,
    )


PYMUPDF4LLM_EXTRACTOR = PdfExtractor(
    name="pymupdf4llm",
    ensure_available=ensure_available,
    extract_pages=extract_pages,
    default_config=PYMUPDF4LLM_DEFAULT_CONFIG,
)
