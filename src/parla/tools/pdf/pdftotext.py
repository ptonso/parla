from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from .base import CanonicalPdfLine, CanonicalPdfPage, PdfExtractor
from .heuristics import infer_text_heading_level, normalize_line_text

PDFTOTEXT_DEFAULT_CONFIG: dict[str, Any] = {
    "heading": {
        "max_chars": 120,
        "max_words": 8,
    }
}


def ensure_available() -> None:
    for tool in ["pdftotext", "pdfinfo"]:
        if shutil.which(tool) is None:
            raise RuntimeError(f"Missing required PDF tool: {tool}")


def extract_pages(pdf_path: Path, config: dict[str, Any]) -> list[CanonicalPdfPage]:
    n_pages = _pdf_page_count(pdf_path)
    if n_pages < 1:
        raise ValueError(f"Failed to read pages from {pdf_path}")

    heading_cfg = _resolve_heading_config(config)
    pages: list[CanonicalPdfPage] = []
    for page_number in range(1, n_pages + 1):
        text = _extract_pdf_page_text(pdf_path, page_number)
        lines = _canonical_lines_from_text(page_number, text, heading_cfg)
        pages.append(_canonical_page(page_number, lines))
    return pages


def _resolve_heading_config(config: dict[str, Any]) -> dict[str, Any]:
    heading_cfg = config.get("heading") if isinstance(config.get("heading"), dict) else {}
    default_heading = PDFTOTEXT_DEFAULT_CONFIG["heading"]
    return {
        "max_chars": int(heading_cfg.get("max_chars", default_heading["max_chars"])),
        "max_words": int(heading_cfg.get("max_words", default_heading["max_words"])),
    }


def _canonical_lines_from_text(
    page_number: int,
    text: str,
    heading_cfg: dict[str, Any],
) -> tuple[CanonicalPdfLine, ...]:
    lines: list[CanonicalPdfLine] = []
    for raw_line in str(text).replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line_text = normalize_line_text(raw_line)
        if not line_text:
            continue
        heading_level = infer_text_heading_level(
            line_text,
            max_chars=int(heading_cfg["max_chars"]),
            max_words=int(heading_cfg["max_words"]),
        )
        lines.append(
            CanonicalPdfLine(
                page=page_number,
                text=line_text,
                heading_level=heading_level,
                heading_source="inferred_text" if heading_level is not None else "none",
            )
        )
    return tuple(lines)


def _canonical_page(page_number: int, lines: tuple[CanonicalPdfLine, ...]) -> CanonicalPdfPage:
    return CanonicalPdfPage(
        page=page_number,
        text="\n".join(line.text for line in lines).strip(),
        lines=lines,
    )


def _pdf_page_count(pdf_path: Path) -> int:
    output = _run_command(["pdfinfo", str(pdf_path)])
    match = re.search(r"^Pages:\s+(\d+)\s*$", output, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"Unable to parse page count from pdfinfo for {pdf_path}")
    return int(match.group(1))


def pdf_page_count(pdf_path: Path) -> int:
    """Public entry point for callers that only need the page count, not full text extraction."""
    return _pdf_page_count(pdf_path)


def _extract_pdf_page_text(pdf_path: Path, page_number: int) -> str:
    return _run_command(
        [
            "pdftotext",
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-enc",
            "UTF-8",
            "-layout",
            str(pdf_path),
            "-",
        ]
    )


def _run_command(args: list[str]) -> str:
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Command failed ({' '.join(args)}): {stderr}")
    return result.stdout


PDFTOTEXT_EXTRACTOR = PdfExtractor(
    name="pdftotext",
    ensure_available=ensure_available,
    extract_pages=extract_pages,
    default_config=PDFTOTEXT_DEFAULT_CONFIG,
)
