"""Readers that turn any supported table source into one canonical grid.

Badly formatted input is expected: ragged CSV rows, a stray title line above the header,
misaligned Markdown pipes, hand-tuned `tabular`. Everything downstream works on the grid.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import json
import logging
from pathlib import Path
import re

LOG = logging.getLogger(__name__)

SUPPORTED_TABLE_EXTENSIONS = {".csv", ".tsv", ".md", ".markdown", ".json", ".tex"}

_MD_SEPARATOR_CELL_RE = re.compile(r"^:?-{1,}:?$")
_BIB_MARKER_RE = re.compile(r"<\s*(?:full-bib|bib):([^<>]+?)\s*>", re.IGNORECASE)
# A condensed table cell may echo a citation as a markdown link into `../bib/<key>.md` instead
# of the `<bib:key>` marker (the model wasn't shown the marker vocabulary, only the link syntax
# idea notes use); recognized here so it renders identically to `<bib:key>` rather than passing
# through as literal, unescaped markdown.
_MD_BIB_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*(?:\.\./)*bib/([^)/]+?)(?:\.md)?\s*\)", re.IGNORECASE)
_EMPHASIS_RE = re.compile(r"(\*\*|\*|`)(.+?)\1")
_MATH_SPAN_RE = re.compile(r"\$([^$]*)\$")
_TEX_ROW_SPLIT_RE = re.compile(r"\\\\(?:\s*\[[^\]]*\])?")
_TEX_CELL_SPLIT_RE = re.compile(r"(?<!\\)&")
_TEX_RULE_RE = re.compile(
    r"\\(?:toprule|midrule|bottomrule|hline|cmidrule|addlinespace|rowcolor)\b(?:\[[^\]]*\])?(?:\{[^{}]*\})*"
)
_TEX_MULTICOLUMN_RE = re.compile(r"\\multicolumn\s*\{[^{}]*\}\s*\{[^{}]*\}\s*\{(?P<text>[^{}]*)\}")
_TEX_MULTIROW_RE = re.compile(r"\\multirow\s*\{[^{}]*\}\s*(?:\[[^\]]*\])?\{[^{}]*\}\s*\{(?P<text>[^{}]*)\}")
_TEX_TABULAR_RE = re.compile(
    r"\\begin\s*\{(?P<env>tabular\*?|tabularx|longtable|array)\}"
    r"(?:\s*\{[^{}]*\})?"
    r"\s*\{(?P<spec>[^{}]*)\}"
    r"(?P<body>.*?)"
    r"\\end\s*\{(?P=env)\}",
    re.DOTALL,
)
_TEX_WHOLE_CELL_COMMAND_RE = re.compile(r"^\\[A-Za-z@]+\s*\{(?P<inner>.*)\}$", re.DOTALL)
_TEX_UNESCAPE = (
    (r"\%", "%"),
    (r"\_", "_"),
    (r"\&", "&"),
    (r"\#", "#"),
    (r"\$", "$"),
    (r"\{", "{"),
    (r"\}", "}"),
)


class TableParseError(ValueError):
    """Raised when a table source cannot be reduced to a usable grid."""


@dataclass(frozen=True)
class TableGrid:
    """A header row plus body rows, all cells already whitespace-normalized."""

    header: list[str]
    rows: list[list[str]]

    @property
    def n_cols(self) -> int:
        return len(self.header)

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    def column(self, index: int) -> list[str]:
        return [self.header[index], *(row[index] for row in self.rows)]

    def to_markdown(self) -> str:
        lines = [_markdown_row(self.header), _markdown_row(["---"] * self.n_cols)]
        lines.extend(_markdown_row(row) for row in self.rows)
        return "\n".join(lines)


def parse_table_file(path: Path) -> TableGrid:
    """Read one table source into the canonical grid, dispatching on file extension."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_TABLE_EXTENSIONS:
        raise TableParseError(
            f"Unsupported table format '{suffix or path.name}'; expected one of "
            f"{', '.join(sorted(SUPPORTED_TABLE_EXTENSIONS))}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise TableParseError(f"Table source {path} is not valid UTF-8: {exc}") from exc

    if suffix in {".csv", ".tsv"}:
        return parse_delimited(text, default_delimiter="\t" if suffix == ".tsv" else ",")
    if suffix in {".md", ".markdown"}:
        return parse_markdown(text)
    if suffix == ".json":
        return parse_json(text)
    return parse_latex(text)


def parse_delimited(text: str, *, default_delimiter: str = ",") -> TableGrid:
    stripped = text.strip("\ufeff").strip()
    if not stripped:
        raise TableParseError("Table source is empty")

    delimiter = default_delimiter
    try:
        delimiter = csv.Sniffer().sniff(stripped[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        LOG.debug("csv.Sniffer could not detect a delimiter; falling back to %r", default_delimiter)

    rows = [
        [_normalize_cell(cell) for cell in raw_row]
        for raw_row in csv.reader(io.StringIO(stripped), delimiter=delimiter)
    ]
    return _grid_from_rows(rows)


def parse_markdown(text: str) -> TableGrid:
    rows: list[list[str]] = []
    for line in text.splitlines():
        candidate = line.strip()
        if "|" not in candidate:
            continue
        cells = [_normalize_cell(cell) for cell in _split_markdown_row(candidate)]
        if not any(cells):
            continue
        if all(_MD_SEPARATOR_CELL_RE.match(cell) for cell in cells if cell):
            continue
        rows.append(cells)

    if not rows:
        raise TableParseError("No Markdown pipe-table rows found in table source")
    return _grid_from_rows(rows)


def parse_json(text: str) -> TableGrid:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TableParseError(f"Table source is not valid JSON: {exc}") from exc

    if isinstance(payload, dict):
        columns = payload.get("columns") or payload.get("header")
        body = payload.get("rows") or payload.get("data")
        if not isinstance(columns, list) or not isinstance(body, list):
            raise TableParseError("JSON table object must carry 'columns' and 'rows' lists")
        header = [_normalize_cell(_as_cell(column)) for column in columns]
        rows = [[_normalize_cell(_as_cell(cell)) for cell in _as_row(row)] for row in body]
        return _grid_from_rows([header, *rows])

    if not isinstance(payload, list) or not payload:
        raise TableParseError("JSON table must be a non-empty list or a {columns, rows} object")

    if all(isinstance(item, dict) for item in payload):
        header: list[str] = []
        for item in payload:
            for key in item:
                if key not in header:
                    header.append(key)
        rows = [
            [_normalize_cell(_as_cell(item.get(key, ""))) for key in header]
            for item in payload
        ]
        return _grid_from_rows([[_normalize_cell(key) for key in header], *rows])

    rows = [[_normalize_cell(_as_cell(cell)) for cell in _as_row(row)] for row in payload]
    return _grid_from_rows(rows)


def parse_latex(text: str) -> TableGrid:
    """`\\multicolumn` and `\\multirow` are flattened to their text; merged cells are lost."""
    match = _TEX_TABULAR_RE.search(text)
    body = match.group("body") if match else text

    rows: list[list[str]] = []
    for raw_row in _TEX_ROW_SPLIT_RE.split(body):
        line = _strip_latex_comments(raw_row)
        line = _TEX_RULE_RE.sub("", line)
        if not line.strip():
            continue
        cells = [_clean_latex_cell(cell) for cell in _TEX_CELL_SPLIT_RE.split(line)]
        if not any(cells):
            continue
        rows.append(cells)

    if not rows:
        raise TableParseError("No tabular rows found in LaTeX table source")
    return _grid_from_rows(rows)


def _grid_from_rows(rows: list[list[str]]) -> TableGrid:
    populated = [row for row in rows if any(cell for cell in row)]
    if not populated:
        raise TableParseError("Table source contains no non-empty rows")

    width = _modal_width(populated)

    # A title line above the header parses as a short row; never let it become the header.
    while len(populated) > 1 and _significant_width(populated[0]) < width:
        LOG.debug("Dropping leading table line with %d cells (grid is %d wide)", len(populated[0]), width)
        populated.pop(0)

    width = max(_significant_width(row) for row in populated)
    squared = [_fit_row(row, width) for row in populated]
    squared = _drop_empty_columns(squared)
    if not squared or not squared[0]:
        raise TableParseError("Table source reduced to an empty grid")

    header, *body = squared
    return TableGrid(header=header, rows=body)


def _modal_width(rows: list[list[str]]) -> int:
    counts: dict[int, int] = {}
    for row in rows:
        significant = _significant_width(row)
        if significant:
            counts[significant] = counts.get(significant, 0) + 1
    if not counts:
        return 0
    return max(counts, key=lambda width: (counts[width], width))


def _significant_width(row: list[str]) -> int:
    width = len(row)
    while width > 0 and not row[width - 1]:
        width -= 1
    return width


def _fit_row(row: list[str], width: int) -> list[str]:
    trimmed = row[:width]
    return trimmed + [""] * (width - len(trimmed))


def _drop_empty_columns(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows
    keep = [
        index
        for index in range(len(rows[0]))
        if any(row[index] for row in rows)
    ]
    if len(keep) == len(rows[0]):
        return rows
    return [[row[index] for index in keep] for row in rows]


def _split_markdown_row(line: str) -> list[str]:
    trimmed = line.strip()
    if trimmed.startswith("|"):
        trimmed = trimmed[1:]
    if trimmed.endswith("|") and not trimmed.endswith("\\|"):
        trimmed = trimmed[:-1]
    return [cell.replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", trimmed)]


def _markdown_row(cells: list[str]) -> str:
    escaped = [cell.replace("|", "\\|") for cell in cells]
    return "| " + " | ".join(escaped) + " |"


def _strip_latex_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def _clean_latex_cell(cell: str) -> str:
    text = _TEX_MULTICOLUMN_RE.sub(lambda match: match.group("text"), cell)
    text = _TEX_MULTIROW_RE.sub(lambda match: match.group("text"), text)
    text = _TEX_RULE_RE.sub("", text)
    text = text.strip()

    while True:
        match = _TEX_WHOLE_CELL_COMMAND_RE.match(text)
        if not match:
            break
        inner = match.group("inner")
        if "{" in inner and "}" not in inner:
            break
        text = inner.strip()

    for escaped, literal in _TEX_UNESCAPE:
        text = text.replace(escaped, literal)
    return _normalize_cell(text)


CITATION_MARKER_WIDTH = 4


def display_width(cell: str, *, citation_width: int = CITATION_MARKER_WIDTH) -> int:
    """Width of a cell as printed, not as authored.

    Markers and emphasis are much wider in the source than on the page. How wide a citation
    prints depends on the bibliography style - `[12]` for a numeric one, but
    `[Chatzimparmpas et al. 2024]` for an author-year one - so the caller supplies it.
    """
    text = _BIB_MARKER_RE.sub("x" * max(citation_width, 0), cell)
    text = _MD_BIB_LINK_RE.sub("x" * max(citation_width, 0), text)
    text = _EMPHASIS_RE.sub(r"\2", text)
    text = _MATH_SPAN_RE.sub(lambda match: match.group(1), text)
    return len(text)


def extract_citekeys(cell: str) -> list[str]:
    """Citekeys referenced by one cell, in order: `<bib:a, b>` groups and markdown `../bib/<key>.md`
    links alike."""
    matches = sorted(
        [*_BIB_MARKER_RE.finditer(cell), *_MD_BIB_LINK_RE.finditer(cell)],
        key=lambda match: match.start(),
    )
    keys: list[str] = []
    for match in matches:
        for key in match.group(1).split(","):
            key = key.strip()
            if key:
                keys.append(key)
    return keys


def grid_citekeys(grid: TableGrid) -> list[str]:
    """Unique citekeys over the whole grid, in row-major first-appearance order."""
    ordered: list[str] = []
    seen: set[str] = set()
    for row in [grid.header, *grid.rows]:
        for cell in row:
            for key in extract_citekeys(cell):
                if key not in seen:
                    seen.add(key)
                    ordered.append(key)
    return ordered


def _normalize_cell(value: str) -> str:
    return " ".join(str(value).split())


def _as_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _as_row(row: object) -> list[object]:
    if isinstance(row, list):
        return row
    if isinstance(row, dict):
        return list(row.values())
    return [row]
