from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal


@dataclass(frozen=True)
class CanonicalPdfLine:
    page: int
    text: str
    heading_level: int | None = None
    heading_source: Literal["none", "inferred_text", "extractor_markdown", "inferred_style"] = "none"


@dataclass(frozen=True)
class CanonicalPdfPage:
    page: int
    text: str
    lines: tuple[CanonicalPdfLine, ...]


@dataclass(frozen=True)
class PdfExtractor:
    name: str
    ensure_available: Callable[[], None]
    extract_pages: Callable[[Path, dict[str, Any]], list[CanonicalPdfPage]]
    default_config: dict[str, Any]
