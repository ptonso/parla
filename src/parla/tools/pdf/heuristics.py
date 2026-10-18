from __future__ import annotations

import re
from typing import Any

_NON_HEADING_PREFIXES = ("figure ", "table ", "algorithm ", "listing ")
_BACK_MATTER_MARKERS: tuple[str, ...] = (
    "appendices",
    "appendix",
    "bibliography",
    "literature cited",
    "reference",
    "references",
    "supplemental material",
    "supplementary information",
    "supplementary material",
    "works cited",
)
_HEADING_STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "via",
    "with",
}
_SECTION_KEYWORD_MAP: tuple[tuple[str, str], ...] = (
    ("abstract", "abstract"),
    ("summary", "abstract"),
    ("introduction", "introduction"),
    ("background", "background"),
    ("related work", "background"),
    ("related works", "background"),
    ("preliminary", "background"),
    ("preliminaries", "background"),
    ("method", "method"),
    ("methods", "method"),
    ("approach", "method"),
    ("model", "method"),
    ("methodology", "method"),
    ("experimental setup", "experiments"),
    ("evaluation protocol", "experiments"),
    ("experiment", "experiments"),
    ("experiments", "experiments"),
    ("evaluation", "experiments"),
    ("result", "results"),
    ("results", "results"),
    ("analysis", "discussion"),
    ("discussion", "discussion"),
    ("limitation", "limitations"),
    ("limitations", "limitations"),
    ("future work", "limitations"),
    ("conclusion", "conclusion"),
    ("conclusions", "conclusion"),
    ("literature cited", "references"),
    ("works cited", "references"),
    ("bibliography", "references"),
    ("reference", "references"),
    ("references", "references"),
    ("supplementary information", "appendix"),
    ("supplementary material", "appendix"),
    ("supplemental material", "appendix"),
    ("appendices", "appendix"),
    ("appendix", "appendix"),
)
_SURROUNDING_INLINE_MARKERS: tuple[str, ...] = ("**", "__", "*", "_", "`")
_SECTION_CONTINUATION_WORDS = _HEADING_STOP_WORDS | {"overview"}
_STRICT_SECTION_TOKENS = {
    "abstract",
    "analysis",
    "approach",
    "background",
    "conclusion",
    "conclusions",
    "discussion",
    "evaluation",
    "experiment",
    "experiments",
    "introduction",
    "limitation",
    "limitations",
    "method",
    "methodology",
    "methods",
    "model",
    "reference",
    "references",
    "result",
    "results",
    "summary",
}
_UPPERCASE_CELL_WORDS = {
    "ap",
    "base",
    "coding",
    "cpu",
    "dataset",
    "dense",
    "dtd",
    "gpu",
    "lvis",
    "math",
    "mean",
    "mode",
    "pets",
    "reasoning",
    "resisc45",
    "rgb",
    "rgbd",
    "svhn",
    "tasks",
}


def normalize_line_text(raw: Any) -> str:
    text = str(raw or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_markdown_heading(line: str) -> tuple[str, int | None]:
    match = re.match(r"^\s*(#{1,6})\s+(.*?)\s*$", str(line or ""))
    if not match:
        return normalize_line_text(line), None
    return normalize_line_text(match.group(2)), len(match.group(1))


def strip_inline_markdown_formatting(line: str) -> str:
    stripped = normalize_line_text(line)
    previous = ""
    while stripped and stripped != previous:
        previous = stripped
        for marker in _SURROUNDING_INLINE_MARKERS:
            marker_len = len(marker)
            if (
                len(stripped) > marker_len * 2
                and stripped.startswith(marker)
                and stripped.endswith(marker)
            ):
                stripped = stripped[marker_len:-marker_len].strip()
    return stripped


def repair_spaced_heading_text(line: str) -> str:
    repaired = normalize_line_text(line)
    previous = ""
    while repaired and repaired != previous:
        previous = repaired
        repaired = re.sub(
            r"\b([A-Z])\s+([A-Z][A-Za-z]{1,})\b",
            lambda match: f"{match.group(1)}{match.group(2)}",
            repaired,
        )
        repaired = re.sub(
            r"\b(?:[A-Z]\s+){2,}[A-Z]\b",
            lambda match: match.group(0).replace(" ", ""),
            repaired,
        )
    return repaired


def heading_normalization_details(line: str) -> dict[str, str]:
    stripped, _ = strip_markdown_heading(line)
    stripped = strip_inline_markdown_formatting(stripped)
    stripped = repair_spaced_heading_text(stripped)
    stripped = normalize_line_text(stripped)

    prefix_kind = ""
    prefix_text = ""
    heading_core = stripped

    appendix_match = re.match(
        (
            r"^(?P<prefix>"
            r"(?:appendices|appendix|supplementary information|supplementary material|supplemental material)"
            r"(?:\s+[A-Za-z](?:\.\d+)*)?"
            r")(?:(?:[.)])|\b)\s*(?P<rest>.*)$"
        ),
        stripped,
        flags=re.IGNORECASE,
    )
    if appendix_match:
        prefix_kind = "appendix_keyword"
        prefix_text = normalize_line_text(appendix_match.group("prefix"))
        heading_core = normalize_line_text(appendix_match.group("rest"))
    else:
        heading_core, prefix_kind, prefix_text = _strip_heading_prefix(stripped)

    normalized_full_text = _sanitize_heading_text(stripped)
    normalized_heading_core = _sanitize_heading_text(heading_core)

    return {
        "heading_text": stripped,
        "heading_core": heading_core,
        "normalized_full_text": normalized_full_text,
        "normalized_heading_core": normalized_heading_core,
        "prefix_kind": prefix_kind,
        "prefix_text": prefix_text,
    }


def canonical_section_match(line: str) -> tuple[str, str, str]:
    details = heading_normalization_details(line)
    candidates = [
        (details["heading_text"], details["normalized_full_text"]),
        (details["heading_core"], details["normalized_heading_core"]),
    ]
    seen: set[tuple[str, str]] = set()
    for raw_candidate, cleaned in candidates:
        matchable = _normalize_heading_match_text(raw_candidate)
        if not matchable or not cleaned:
            continue
        marker = (matchable, cleaned)
        if marker in seen:
            continue
        seen.add(marker)
        for token, label in _SECTION_KEYWORD_MAP:
            if heading_starts_with_token(matchable, token):
                return cleaned, token, label
    if not details["normalized_heading_core"]:
        return "", "", ""
    return details["normalized_heading_core"], "", ""


def canonical_section_label(line: str) -> str:
    _, _, label = canonical_section_match(line)
    return label


def heading_starts_with_token(cleaned: str, token: str) -> bool:
    matchable = _normalize_heading_match_text(cleaned)
    if not matchable.startswith(token):
        return False
    if matchable == token:
        return True

    next_char = matchable[len(token)]
    if next_char in {":", ";", ",", ".", ")", "]"}:
        return True
    if next_char != " ":
        return False

    remainder = matchable[len(token) :].strip()
    if not remainder:
        return True
    if token in _STRICT_SECTION_TOKENS:
        next_word_match = re.match(r"([a-z]+)", remainder)
        if not next_word_match:
            return False
        return next_word_match.group(1) in _SECTION_CONTINUATION_WORDS
    return True


def looks_like_explicit_section_heading(line: str) -> bool:
    stripped = normalize_line_text(line)
    if not stripped:
        return False
    stripped = strip_inline_markdown_formatting(stripped)
    details = heading_normalization_details(stripped)
    heading_text = details["heading_text"]
    if heading_text.lower().startswith(_NON_HEADING_PREFIXES):
        return False
    if canonical_section_label(heading_text):
        return True
    if looks_like_noise_heading(heading_text):
        return False
    if re.match(r"^#{1,6}\s+\S", stripped):
        return True
    if details["prefix_kind"] in {"numeric", "roman", "alpha_hierarchical", "alpha_single", "appendix_keyword"}:
        return True

    words = re.findall(r"[A-Za-z][A-Za-z'-]*", details["heading_core"])
    if not words:
        return False

    significant = [word for word in words if word.lower() not in _HEADING_STOP_WORDS] or words
    heading_like = sum(1 for word in significant if word.isupper() or word[:1].isupper())
    return (heading_like / len(significant)) >= 0.8


def looks_like_heading_candidate(
    text: str,
    *,
    max_chars: int,
    max_words: int,
) -> bool:
    normalized = normalize_line_text(text)
    lowered = normalized.lower()
    if not normalized:
        return False
    if lowered.startswith(_NON_HEADING_PREFIXES):
        return False
    normalized = strip_inline_markdown_formatting(normalized)
    details = heading_normalization_details(normalized)
    canonical_label = canonical_section_label(normalized)
    if _is_empty_heading_after_prefix(details):
        return False
    if len(normalized) > max_chars:
        return False
    words = normalized.split()
    if len(words) > max_words:
        return False
    if normalized[-1:] in {".", ",", ";", "!", "?"}:
        return False
    if re.search(r"\b(?:19|20)\d{2}\b", normalized) and ("(" in normalized or ")" in normalized):
        return False
    if "et al." in lowered or "http://" in lowered or "https://" in lowered:
        return False
    if re.search(r"[:]\s+\S", normalized):
        if not canonical_label and details["prefix_kind"] == "":
            return False
    if looks_like_noise_heading(normalized, details=details, canonical_label=canonical_label):
        return False
    return True


def infer_text_heading_level(
    text: str,
    *,
    max_chars: int = 120,
    max_words: int = 8,
) -> int | None:
    stripped, markdown_level = strip_markdown_heading(text)
    if markdown_level is not None:
        return markdown_level
    stripped = strip_inline_markdown_formatting(stripped)
    if not looks_like_heading_candidate(stripped, max_chars=max_chars, max_words=max_words):
        return None

    details = heading_normalization_details(stripped)
    _, _, canonical_label = canonical_section_match(stripped)
    matches_numbered_heading = details["prefix_kind"] in {"numeric", "roman", "alpha_hierarchical", "alpha_single"}
    uppercase_letters = sum(1 for char in stripped if char.isalpha() and char.isupper())
    letters = sum(1 for char in stripped if char.isalpha())
    uppercase_ratio = (uppercase_letters / letters) if letters > 0 else 0.0
    if canonical_label:
        return 1
    if matches_numbered_heading:
        return 2
    if looks_like_explicit_section_heading(stripped):
        return 2
    if letters > 0 and uppercase_ratio >= 0.85:
        return 3
    return None


def infer_style_heading_level(
    text: str,
    *,
    max_size: float,
    emphasized: bool,
    h1_min_size: float = 16.0,
    h2_min_size: float = 13.0,
    h3_min_size: float = 10.8,
    max_chars: int = 100,
    max_words: int = 10,
) -> int | None:
    normalized = normalize_line_text(text)
    normalized = strip_inline_markdown_formatting(normalized)
    if not looks_like_heading_candidate(normalized, max_chars=max_chars, max_words=max_words):
        return None
    if canonical_section_label(normalized):
        return 1
    details = heading_normalization_details(normalized)
    if looks_like_noise_heading(normalized, details=details):
        return None
    if max_size >= h1_min_size:
        return 1
    if max_size >= h2_min_size:
        return 2
    if max_size >= h3_min_size and emphasized:
        if details["prefix_kind"] == "" and len(re.findall(r"[A-Za-z0-9]+", details["heading_core"])) <= 1:
            return None
        return 3
    if emphasized and looks_like_explicit_section_heading(normalized):
        return 3
    return None


def looks_like_noise_heading(
    line: str,
    *,
    details: dict[str, str] | None = None,
    canonical_label: str = "",
) -> bool:
    normalized = normalize_line_text(line)
    if not normalized:
        return True
    details = details or heading_normalization_details(normalized)
    if canonical_label:
        return False

    normalized_core = details["normalized_heading_core"] or details["normalized_full_text"]
    words = re.findall(r"[A-Za-z0-9]+", details["heading_core"])
    lowered_words = [word.lower() for word in words]
    number_tokens = re.findall(r"\b\d+(?:\.\d+)?\b", normalized)
    alphanumeric_metric_tokens = re.findall(r"\b[A-Za-z]*\d+(?:\.\d+)?[A-Za-z]*\b", normalized)

    if re.search(r"\barxiv\b", normalized, flags=re.IGNORECASE):
        return True
    if re.search(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b", normalized, flags=re.IGNORECASE):
        if number_tokens:
            return True
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", normalized):
        return True
    if len(alphanumeric_metric_tokens) >= 3:
        return True
    if len(number_tokens) >= 2 and ("/" in normalized or re.search(r"\b(?:yes|no)\b", normalized, flags=re.IGNORECASE)):
        return True
    if len(number_tokens) >= 4:
        return True
    if "%" in normalized and len(words) <= 3 and details["prefix_kind"] == "":
        return True
    if len(set(lowered_words)) < len(lowered_words) and len(lowered_words) >= 3:
        return True
    if re.search(r"\b(?:[A-Z]{2,}\s+){2,}[A-Z]{2,}\b", normalized):
        return True
    if len(words) >= 2 and all(len(word) <= 5 for word in words):
        if sum(1 for word in words if word.isupper()) >= max(2, len(words) - 1):
            return True
    if len(words) <= 4 and lowered_words:
        if lowered_words[-1] in {"benchmarks", "categories", "datasets", "metrics", "scores", "tasks"}:
            return True
    if len(words) == 1 and details["prefix_kind"] == "":
        token = lowered_words[0]
        if len(token) <= 6:
            return True
        if token in _UPPERCASE_CELL_WORDS:
            return True
    if re.search(r"[A-Za-z]\d", normalized) and len(number_tokens) >= 2:
        return True
    if normalized_core.endswith(" references") and details["prefix_kind"] == "":
        return True
    return False


def is_emphasized_font(font: str, flags: int) -> bool:
    normalized_font = str(font or "").lower()
    return bool(flags & 16) or any(
        token in normalized_font for token in ["bold", "black", "heavy", "demi", "semibold"]
    )


def coerce_float(raw: Any) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _sanitize_heading_text(text: str) -> str:
    cleaned = normalize_line_text(text)
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip().lower()


def _normalize_heading_match_text(text: str) -> str:
    return normalize_line_text(text).lower()


def _strip_heading_prefix(text: str) -> tuple[str, str, str]:
    stripped = normalize_line_text(text)

    numeric_match = re.match(r"^(?P<prefix>\(?\d+(?:\.\d+)*\)?[.)]?)\s+(?P<rest>.+)$", stripped)
    if numeric_match:
        return normalize_line_text(numeric_match.group("rest")), "numeric", numeric_match.group("prefix")

    alpha_hierarchical_match = re.match(r"^(?P<prefix>[A-Z](?:\.\d+)+(?:\.\d+)*[.)]?)\s+(?P<rest>.+)$", stripped)
    if alpha_hierarchical_match:
        return (
            normalize_line_text(alpha_hierarchical_match.group("rest")),
            "alpha_hierarchical",
            alpha_hierarchical_match.group("prefix"),
        )

    roman_match = re.match(r"^(?P<prefix>\(?[IVXLCDM]+\)?[.)]?)\s+(?P<rest>.+)$", stripped)
    if roman_match:
        return normalize_line_text(roman_match.group("rest")), "roman", roman_match.group("prefix")

    alpha_single_match = re.match(r"^(?P<prefix>[A-Z][.)]?)\s+(?P<rest>.+)$", stripped)
    if alpha_single_match and _looks_like_alpha_appendix_prefix(alpha_single_match.group("rest")):
        return normalize_line_text(alpha_single_match.group("rest")), "alpha_single", alpha_single_match.group("prefix")

    numeric_only_match = re.match(r"^(?P<prefix>\(?\d+(?:\.\d+)*\)?[.)]?)$", stripped)
    if numeric_only_match:
        return "", "numeric", numeric_only_match.group("prefix")

    alpha_hierarchical_only_match = re.match(r"^(?P<prefix>[A-Z](?:\.\d+)+(?:\.\d+)*[.)]?)$", stripped)
    if alpha_hierarchical_only_match:
        return "", "alpha_hierarchical", alpha_hierarchical_only_match.group("prefix")

    roman_only_match = re.match(r"^(?P<prefix>\(?[IVXLCDM]+\)?[.)]?)$", stripped)
    if roman_only_match:
        return "", "roman", roman_only_match.group("prefix")

    alpha_single_only_match = re.match(r"^(?P<prefix>[A-Z][.)]?)$", stripped)
    if alpha_single_only_match:
        return "", "alpha_single", alpha_single_only_match.group("prefix")

    return stripped, "", ""


def _looks_like_alpha_appendix_prefix(rest: str) -> bool:
    normalized = normalize_line_text(rest)
    if not normalized:
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", normalized)
    if not words:
        return False
    if len(words) > 8:
        return False
    return words[0][:1].isupper()


def _is_empty_heading_after_prefix(details: dict[str, str]) -> bool:
    if details["normalized_heading_core"]:
        return False
    return details["prefix_kind"] in {"numeric", "roman", "alpha_hierarchical", "alpha_single"}
