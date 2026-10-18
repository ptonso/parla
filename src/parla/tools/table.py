"""`parla tool table`: parse a table source, plan the fit and write the LaTeX. See `specs/tools.md`."""

from __future__ import annotations

import re
from pathlib import Path

from .. import config as config_mod
from ..names import PROJECT_DIR
from .table_fit import (
    DEFAULT_CITATION_WIDTH,
    FONT_STEP_MULTIPLIERS,
    measure_grid,
    needs_condense,
    plan_fit,
    resolve_fit_settings,
)
from .table_parse import parse_table_file
from .table_render import render_table_artifact

_NON_KEBAB_RE = re.compile(r"[^a-z0-9]+")


class TableError(Exception):
    """A table cannot be fitted or written."""


def kebab(stem: str, *, fallback: str) -> str:
    return _NON_KEBAB_RE.sub("-", stem.strip().lower()).strip("-") or fallback


def run(
    root: Path, artifact: str, source: str, *, table_id: str | None = None,
    max_width: int | None = None, max_rows: int | None = None, font_step: str | None = None,
) -> list[str]:
    """Writes `artifacts/<artifact>/table/<id>.tex` and returns the lines to print. Writes nothing
    when the grid does not fit at the floor type size."""
    config_mod.load_card(root, artifact)
    path = Path(source) if Path(source).is_absolute() else root / PROJECT_DIR / source
    if not path.is_file():
        raise TableError(f"table source not found: {path}")
    try:
        grid = parse_table_file(path)
        settings = resolve_fit_settings(max_width=max_width, max_rows=max_rows, font_step=font_step)
    except ValueError as exc:
        raise TableError(str(exc)) from exc
    if needs_condense(grid, settings):
        measure = measure_grid(grid, citation_width=DEFAULT_CITATION_WIDTH)
        budget = int(settings.max_width_chars * FONT_STEP_MULTIPLIERS[settings.font_step_floor])
        raise TableError(
            f"{source} does not fit at {settings.font_step_floor}: {measure.width_chars} chars wide "
            f"(budget {budget}), {measure.n_rows} rows (max {settings.max_rows}). Condense the source."
        )
    plan = plan_fit(grid, settings)
    name = table_id or kebab(path.stem, fallback="table")
    out = root / PROJECT_DIR / "artifacts" / artifact / "table" / f"{name}.tex"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_table_artifact(grid, plan, source=source), encoding="utf-8")
    return [
        f"type size: {plan.font_step}",
        f"strategy: {plan.strategy}",
        f"width: {plan.measure.width_chars} chars, rows: {plan.measure.n_rows}",
        f"wrote {out.relative_to(root / PROJECT_DIR)}",
    ]
