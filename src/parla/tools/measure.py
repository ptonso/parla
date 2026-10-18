"""`parla tool measure`: words per file and body pages. See `specs/tools.md`."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .. import config as config_mod
from ..engines.base import EngineError, Pages
from ..engines.latex.build import _document_tex_texts
from ..names import BODY_END_LABEL, PROJECT_DIR

# --- copied from texfy_ai.core.draft.length ------------------------------------------------
_LATEX_COMMENT_RE = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
_MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_LATEX_COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?(?:\s*\[[^\]]*\])*")
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\u2019./-]*")


def count_words(text: str) -> int:
    """Prose words in markdown notes or LaTeX, ignoring markup.

    A markdown link keeps its label and drops its target, so a citation counts as the one
    word a reader sees rather than as a path.
    """
    stripped = _LATEX_COMMENT_RE.sub("", text)
    stripped = _MARKDOWN_LINK_RE.sub(r"\1", stripped)
    stripped = _LATEX_COMMAND_RE.sub(" ", stripped)
    stripped = stripped.replace("{", " ").replace("}", " ").replace("$", " ")
    return len(_WORD_RE.findall(stripped))


# --- copied from texfy_ai.core.draft.compress and common.pdf.pdftotext ---------------------
# `\newlabel{parla:body-end}{{<x>}{<page>}...}` - base LaTeX writes `{{x}{page}}`, hyperref
# `{{x}{page}{name}{anchor}{}}`; either way the second brace group is the page.
_BODY_END_LABEL_RE = re.compile(rf"\\newlabel\{{{re.escape(BODY_END_LABEL)}\}}\{{\{{[^{{}}]*\}}\{{([^{{}}]+)\}}")


def pdf_page_count(pdf_path: Path) -> int:
    result = subprocess.run(["pdfinfo", str(pdf_path)], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise EngineError(f"pdfinfo failed for {pdf_path}: {result.stderr.strip() or result.stdout.strip()}")
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, flags=re.MULTILINE)
    if not match:
        raise EngineError(f"Unable to parse page count from pdfinfo for {pdf_path}")
    return int(match.group(1))


def body_pages(pdf: Path, aux: Path) -> Pages:
    """The page count of `pdf` and the page the body-end anchor of `aux` lands on. A page shared
    by the last body line and the start of the references counts as body."""
    if not pdf.is_file():
        raise EngineError(f"{pdf} does not exist; run `build` first")
    total = pdf_page_count(pdf)
    match = _BODY_END_LABEL_RE.search(aux.read_text(encoding="utf-8")) if aux.is_file() else None
    if match is None or not match.group(1).isdigit():
        raise EngineError(
            f"\\label{{{BODY_END_LABEL}}} is missing or unreadable in {aux}. The paper starter places it "
            "after the last body line; restore it and rebuild."
        )
    return Pages(total=total, body=int(match.group(1)))


def words(root: Path, artifact: str, language: str | None = None) -> list[tuple[str, int]]:
    """`(file relative to parla/, words)` for the entrypoint of `language` (default: the artifact's
    own) and every file its `\\input` tree reaches inside the artifact folder."""
    card = config_mod.load_card(root, artifact)
    folder = f"{card.translations[language]}/" if language in card.translations else ""
    own = f"artifacts/{artifact}/"
    texts = _document_tex_texts((root / PROJECT_DIR).resolve(), f"{own}{folder}{card.entrypoint}")
    return [(rel, count_words(text)) for rel, text in texts if rel.startswith(own)]
