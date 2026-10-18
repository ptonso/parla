"""Every check id and its severity. Ids are stable: projects list them in `[checks].ignore`."""

from __future__ import annotations

from .finding import Finding, Severity

SEVERITY: dict[str, Severity] = {
    "card-invalid": "error",
    "source-missing": "error",
    "cite-unresolved": "error",
    "figure-missing": "error",
    "bib-name-syntax": "error",
    "unescaped-char": "error",
    "brace-unbalanced": "error",
    "macro-missing": "error",
    "translation-parity": "error",
    "ref-dangling": "warning",
    "float-unreferenced": "warning",
    "float-order": "warning",
    "figure-duplicate": "warning",
    "abbreviation-repeated": "warning",
    "cite-style": "warning",
    "todo-marker": "warning",
    "appendix-structure": "warning",
    "svg-overflow": "error",
    "svg-collision": "error",
    "svg-arrow-crossing": "error",
    "svg-glyph-missing": "error",
    "svg-href-missing": "error",
    "svg-malformed": "error",
    "svg-math-in-text": "error",
    "svg-unsupported": "warning",
    "rule-malformed": "error",
    "rule-origin-missing": "error",
    "rule-duplicate": "error",
    "rule-overrides-missing": "error",
    "public-rule": "error",
    "brief-missing": "error",
    "link-broken": "error",
    "guide-over-budget": "warning",
    "guide-page-over-cap": "warning",
    "hook-missing": "error",
    "topic-applicable-unknown": "error",
    "constraint-example-failed": "error",
    "constraint-refine": "warning",
    "frame-overflow": "error",
    "overfull-line": "warning",
    "rule-contradicted": "warning",
    "case-distill": "warning",
    "case-stale": "warning",
}


def finding(check_id: str, file: str, line: int, message: str) -> Finding:
    return Finding(file, line, SEVERITY[check_id], check_id, message)


def is_constraint(f: Finding) -> bool:
    return f.id.startswith("constraint/")
