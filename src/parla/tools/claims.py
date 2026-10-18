"""`parla tool claims`: each citation with its sentence, the part of it the key supports, and its
paragraph. The extraction is copied from `texfy_ai.core.ground.bib`, without the model calls."""

from __future__ import annotations

import re
from pathlib import Path

from .. import config as config_mod
from ..engines.latex.build import _document_tex_texts
from ..names import PROJECT_DIR

# --- copied from texfy_ai.core.ground.bib --------------------------------------------------
_CITE_RE = re.compile(r"\\cite\{([^}]+)\}")
_PARAGRAPH_BREAK_RE = re.compile(r"\n\s*\n+")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_BOUNDARIES = (
    ", while ",
    " while ",
    ", whereas ",
    " whereas ",
    ", but ",
    " but ",
    "; ",
    ". ",
)


def _extract_paragraph_span(text: str, start: int, end: int) -> str:
    left, right = _extract_paragraph_bounds(text, start, end)
    return text[left:right].strip()


def _extract_paragraph_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = 0
    right = len(text)
    for match in _PARAGRAPH_BREAK_RE.finditer(text):
        if match.end() <= start:
            left = match.end()
            continue
        if match.start() >= end:
            right = match.start()
            break
    return left, right


def _extract_sentence_span(text: str, start: int, end: int) -> str:
    left, right = _extract_sentence_bounds(text, start, end)
    sentence = text[left:right].strip()
    if sentence:
        return sentence
    return _extract_paragraph_span(text, start, end)


def _extract_sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = 0
    right = len(text)
    for match in _SENTENCE_BOUNDARY_RE.finditer(text):
        if match.end() <= start:
            left = match.end()
            continue
        if match.start() >= end:
            right = match.start()
            break

    if text[left:right].strip():
        return left, right

    return _extract_paragraph_bounds(text, start, end)


def _extract_citation_focus_text(sentence_text: str, citekey: str) -> str:
    target_match = None
    for match in _CITE_RE.finditer(sentence_text):
        citekeys = [item.strip() for item in match.group(1).split(",") if item.strip()]
        if citekey in citekeys:
            target_match = match
            break

    if target_match is None:
        return sentence_text.strip()

    lowered = sentence_text.lower()
    start = 0
    for marker in _CLAUSE_BOUNDARIES:
        idx = lowered.rfind(marker.lower(), 0, target_match.start())
        if idx != -1:
            start = max(start, idx + len(marker))

    end = len(sentence_text)
    for marker in _CLAUSE_BOUNDARIES:
        idx = lowered.find(marker.lower(), target_match.end())
        if idx != -1:
            end = min(end, idx)

    clause = sentence_text[start:end].strip(" ,;\n")
    clause = re.sub(r"^(?:while|and|but)\s+", "", clause, flags=re.I).strip()
    return clause or sentence_text.strip()


# --- parla ----------------------------------------------------------------------------------
_COMMENT_RE = re.compile(r"(?<!\\)%.*")


def blocks(root: Path, artifact: str) -> list[str]:
    """One block per `\\cite` in the artifact's `\\input` tree, in file and line order. A comment is
    blanked rather than removed, so offsets and line numbers still match the file."""
    card = config_mod.load_card(root, artifact)
    own = f"artifacts/{artifact}/"
    texts = _document_tex_texts((root / PROJECT_DIR).resolve(), f"{own}{card.entrypoint}")
    out: list[str] = []
    for rel, text in sorted(t for t in texts if t[0].startswith(own)):
        tex = _COMMENT_RE.sub(lambda m: " " * len(m.group()), text)
        for match in _CITE_RE.finditer(tex):
            keys = [k.strip() for k in match.group(1).split(",") if k.strip()]
            left, right = _extract_sentence_bounds(tex, match.start(), match.end())
            sentence = tex[left:right].strip() or _extract_sentence_span(tex, match.start(), match.end())
            out.append(
                f"{rel}:{tex.count(chr(10), 0, match.start()) + 1} [{', '.join(keys)}]\n"
                f"sentence: {sentence}\n"
                f"focus:    {_extract_citation_focus_text(sentence, keys[0])}\n"
                f"paragraph: {_extract_paragraph_span(tex, match.start(), match.end())}"
            )
    return out
