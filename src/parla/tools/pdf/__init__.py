from __future__ import annotations

from copy import deepcopy

from .base import CanonicalPdfLine, CanonicalPdfPage, PdfExtractor
from .pdftotext import PDFTOTEXT_EXTRACTOR
from .pymupdf import PYMUPDF_EXTRACTOR
from .pymupdf4llm import PYMUPDF4LLM_EXTRACTOR

_EXTRACTORS: dict[str, PdfExtractor] = {
    PDFTOTEXT_EXTRACTOR.name: PDFTOTEXT_EXTRACTOR,
    PYMUPDF_EXTRACTOR.name: PYMUPDF_EXTRACTOR,
    PYMUPDF4LLM_EXTRACTOR.name: PYMUPDF4LLM_EXTRACTOR,
}


def get_pdf_extractor(name: str) -> PdfExtractor:
    normalized = str(name).strip().lower()
    extractor = _EXTRACTORS.get(normalized)
    if extractor is None:
        supported = ", ".join(sorted(_EXTRACTORS))
        raise ValueError(f"Unsupported extractor '{name}'. Supported extractors: {supported}.")
    return extractor


def get_pdf_extractor_default_configs() -> dict[str, dict[str, object]]:
    return {
        name: deepcopy(extractor.default_config)
        for name, extractor in _EXTRACTORS.items()
    }


__all__ = [
    "CanonicalPdfLine",
    "CanonicalPdfPage",
    "PdfExtractor",
    "get_pdf_extractor",
    "get_pdf_extractor_default_configs",
]
