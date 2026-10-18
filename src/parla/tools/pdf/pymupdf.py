from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

from .base import CanonicalPdfLine, CanonicalPdfPage, PdfExtractor
from .heuristics import coerce_float, infer_style_heading_level, is_emphasized_font, normalize_line_text

PYMUPDF_DEFAULT_CONFIG: dict[str, Any] = {
    "heading": {
        "h1_min_size": 16.0,
        "h2_min_size": 13.0,
        "h3_min_size": 10.8,
        "max_chars": 100,
        "max_words": 10,
    }
}


def ensure_available() -> None:
    _load_pymupdf()


def extract_pages(pdf_path: Path, config: dict[str, Any]) -> list[CanonicalPdfPage]:
    fitz = _load_pymupdf()
    heading_cfg = _resolve_heading_config(config)
    document = fitz.open(str(pdf_path))
    try:
        pages: list[CanonicalPdfPage] = []
        for page_number, page in enumerate(document, start=1):
            page_dict = page.get_text("dict", sort=True)
            lines = _extract_page_lines(page_number=page_number, page_dict=page_dict, heading_cfg=heading_cfg)
            pages.append(
                CanonicalPdfPage(
                    page=page_number,
                    text="\n".join(line.text for line in lines).strip(),
                    lines=tuple(lines),
                )
            )
        return pages
    finally:
        close = getattr(document, "close", None)
        if callable(close):
            close()


def _load_pymupdf():
    for module_name in ("fitz", "pymupdf"):
        try:
            return import_module(module_name)
        except ModuleNotFoundError:
            continue
    raise RuntimeError(
        "Extractor 'pymupdf' requires the optional dependency 'PyMuPDF'. "
        "Install it before using system.bib.normalization.extractor=pymupdf."
    )


def _resolve_heading_config(config: dict[str, Any]) -> dict[str, Any]:
    heading_cfg = config.get("heading") if isinstance(config.get("heading"), dict) else {}
    default_heading = PYMUPDF_DEFAULT_CONFIG["heading"]
    return {
        "h1_min_size": float(heading_cfg.get("h1_min_size", default_heading["h1_min_size"])),
        "h2_min_size": float(heading_cfg.get("h2_min_size", default_heading["h2_min_size"])),
        "h3_min_size": float(heading_cfg.get("h3_min_size", default_heading["h3_min_size"])),
        "max_chars": int(heading_cfg.get("max_chars", default_heading["max_chars"])),
        "max_words": int(heading_cfg.get("max_words", default_heading["max_words"])),
    }


def _extract_page_lines(
    *,
    page_number: int,
    page_dict: dict[str, Any],
    heading_cfg: dict[str, Any],
) -> list[CanonicalPdfLine]:
    blocks = page_dict.get("blocks")
    if not isinstance(blocks, list):
        return []

    lines: list[CanonicalPdfLine] = []
    for block in blocks:
        if not isinstance(block, dict) or int(block.get("type", 0) or 0) != 0:
            continue
        for line in block.get("lines", []):
            if not isinstance(line, dict):
                continue
            spans = [span for span in line.get("spans", []) if isinstance(span, dict)]
            line_text = normalize_line_text("".join(str(span.get("text", "") or "") for span in spans))
            if not line_text:
                continue
            max_size = max((coerce_float(span.get("size")) for span in spans), default=0.0)
            emphasized = any(
                is_emphasized_font(
                    font=str(span.get("font", "") or ""),
                    flags=int(coerce_float(span.get("flags"))),
                )
                for span in spans
            )
            heading_level = infer_style_heading_level(
                line_text,
                max_size=max_size,
                emphasized=emphasized,
                h1_min_size=float(heading_cfg["h1_min_size"]),
                h2_min_size=float(heading_cfg["h2_min_size"]),
                h3_min_size=float(heading_cfg["h3_min_size"]),
                max_chars=int(heading_cfg["max_chars"]),
                max_words=int(heading_cfg["max_words"]),
            )
            lines.append(
                CanonicalPdfLine(
                    page=page_number,
                    text=line_text,
                    heading_level=heading_level,
                    heading_source="inferred_style" if heading_level is not None else "none",
                )
            )
    return lines


PYMUPDF_EXTRACTOR = PdfExtractor(
    name="pymupdf",
    ensure_available=ensure_available,
    extract_pages=extract_pages,
    default_config=PYMUPDF_DEFAULT_CONFIG,
)
