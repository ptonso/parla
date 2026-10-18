"""Whether a grid fits the page, and the cheapest way to make it fit.

Width is in characters, not points: there are no font metrics here, and a per-class character
budget is good enough to catch a table running into the margin, and testable.

Escalation is condense, then shrink the type, then scale the box.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .table_parse import (
    CITATION_MARKER_WIDTH,
    TableGrid,
    display_width,
    grid_citekeys,
)

# Extra width bought relative to \small, the base budget unit.
FONT_STEP_MULTIPLIERS: dict[str, float] = {
    "normalsize": 0.85,
    "small": 1.0,
    "footnotesize": 1.15,
    "scriptsize": 1.35,
    "tiny": 1.6,
}
_FONT_STEP_ORDER = ("normalsize", "small", "footnotesize", "scriptsize", "tiny")

_COLUMN_PADDING_CHARS = 2

DEFAULT_MAX_WIDTH_CHARS = 90
DEFAULT_MAX_ROWS = 25
DEFAULT_FONT_STEP = "small"
DEFAULT_RESIZE = "fit"
# Smallest type we will set a table in before the agent must condense the source instead.
DEFAULT_FONT_STEP_FLOOR = "scriptsize"
# Printed width of one \cite. ~4 for a numeric style, ~26 for author-year; the conservative
# default is author-year, since guessing low is what produces overfull tables.
DEFAULT_CITATION_WIDTH = 26


@dataclass(frozen=True)
class TableFitSettings:
    max_width_chars: int = DEFAULT_MAX_WIDTH_CHARS
    max_rows: int = DEFAULT_MAX_ROWS
    font_step: str = DEFAULT_FONT_STEP
    font_step_floor: str = DEFAULT_FONT_STEP_FLOOR
    citation_width: int = DEFAULT_CITATION_WIDTH
    resize: str = DEFAULT_RESIZE

    @property
    def resize_enabled(self) -> bool:
        return str(self.resize).strip().lower() in {"fit", "true", "yes", "on"}


@dataclass(frozen=True)
class TableMeasure:
    col_widths: list[int]
    width_chars: int
    n_rows: int
    n_cols: int


@dataclass(frozen=True)
class FitPlan:
    font_step: str
    resize: bool
    fits: bool
    measure: TableMeasure
    hoist_citations: bool = False

    @property
    def strategy(self) -> str:
        parts = [self.font_step]
        if self.hoist_citations:
            parts.append("legend")
        if self.resize:
            parts.append("resizebox")
        return "+".join(parts)


def resolve_fit_settings(
    *, max_width: int | None = None, max_rows: int | None = None, font_step: str | None = None
) -> TableFitSettings:
    """The defaults, overridden by the flags of `parla tool table`."""
    step = (font_step or DEFAULT_FONT_STEP).strip().lower()
    if step not in FONT_STEP_MULTIPLIERS:
        raise ValueError(f"--font-step must be one of {', '.join(_FONT_STEP_ORDER)}; got '{step}'")
    return TableFitSettings(
        max_width_chars=_positive_int(max_width or DEFAULT_MAX_WIDTH_CHARS, "--max-width"),
        max_rows=_positive_int(max_rows or DEFAULT_MAX_ROWS, "--max-rows"),
        font_step=step,
    )


def measure_grid(grid: TableGrid, *, citation_width: int = CITATION_MARKER_WIDTH) -> TableMeasure:
    col_widths = [
        max((display_width(cell, citation_width=citation_width) for cell in grid.column(index)), default=0)
        for index in range(grid.n_cols)
    ]
    width_chars = sum(col_widths) + _COLUMN_PADDING_CHARS * grid.n_cols
    return TableMeasure(
        col_widths=col_widths,
        width_chars=width_chars,
        n_rows=grid.n_rows,
        n_cols=grid.n_cols,
    )


def needs_condense(grid: TableGrid, settings: TableFitSettings) -> bool:
    """True only when no lossless transform rescues the table, so content must be dropped.

    Shrinking type to `font_step_floor` and hoisting citations into a legend are both free.
    A table that fits either way is not "really large".
    """
    if grid.n_rows > settings.max_rows:
        return True
    best = _measure(grid, settings, hoist=True)
    return best.width_chars > settings.max_width_chars * _floor_multiplier(settings)


def plan_fit(grid: TableGrid, settings: TableFitSettings) -> FitPlan:
    """Largest type that fits; at a given size, inline citations before a legend.

    Hoisting is tried before stepping the font down because it is worth far more width on a
    citation-heavy table (a whole author-year label per row) and leaves the type readable.
    """
    hoistable = bool(grid_citekeys(grid))
    modes = [False, True] if hoistable else [False]

    for step in _steps_from(settings.font_step):
        budget = settings.max_width_chars * FONT_STEP_MULTIPLIERS[step]
        for hoist in modes:
            measure = _measure(grid, settings, hoist=hoist)
            if measure.width_chars <= budget:
                return FitPlan(
                    font_step=step,
                    resize=False,
                    fits=True,
                    measure=measure,
                    hoist_citations=hoist,
                )

    smallest = _steps_from(settings.font_step)[-1]
    measure = _measure(grid, settings, hoist=hoistable)
    return FitPlan(
        font_step=smallest,
        resize=settings.resize_enabled,
        fits=settings.resize_enabled,
        measure=measure,
        hoist_citations=hoistable,
    )


def _measure(grid: TableGrid, settings: TableFitSettings, *, hoist: bool) -> TableMeasure:
    width = CITATION_MARKER_WIDTH if hoist else settings.citation_width
    return measure_grid(grid, citation_width=width)


def _floor_multiplier(settings: TableFitSettings) -> float:
    floor_index = _FONT_STEP_ORDER.index(settings.font_step_floor)
    reachable = [
        step for step in _steps_from(settings.font_step) if _FONT_STEP_ORDER.index(step) <= floor_index
    ]
    return max(
        (FONT_STEP_MULTIPLIERS[step] for step in reachable),
        default=FONT_STEP_MULTIPLIERS[settings.font_step],
    )


def _steps_from(font_step: str) -> list[str]:
    start = _FONT_STEP_ORDER.index(font_step)
    return list(_FONT_STEP_ORDER[start:])


def _positive_int(value: Any, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{key} must be an int > 0")
    return value
