"""The fit budget, the escalation ladder, and the LaTeX the renderer emits."""

from __future__ import annotations

import pytest

from parla.tools.table_fit import (
    TableFitSettings,
    measure_grid,
    needs_condense,
    plan_fit,
    resolve_fit_settings,
)
from parla.tools.table_parse import TableGrid, parse_delimited
from parla.tools.table_render import build_column_spec, escape_cell, render_table_artifact

NARROW = TableGrid(header=["a", "b"], rows=[["1", "2"]])


def _wide(n_cols: int, cell: str = "0.8123") -> TableGrid:
    return TableGrid(
        header=[f"column_{index}" for index in range(n_cols)],
        rows=[[cell] * n_cols],
    )


def _tall(n_rows: int) -> TableGrid:
    return TableGrid(header=["a", "b"], rows=[["1", "2"]] * n_rows)


def test_measure_sums_widest_cell_per_column_plus_padding():
    measure = measure_grid(TableGrid(header=["ab", "c"], rows=[["d", "efgh"]]))
    assert measure.col_widths == [2, 4]
    assert measure.width_chars == 2 + 4 + 2 * 2
    assert (measure.n_rows, measure.n_cols) == (1, 2)


def test_narrow_table_fits_and_needs_no_condensation():
    settings = TableFitSettings()
    assert not needs_condense(NARROW, settings)
    plan = plan_fit(NARROW, settings)
    assert plan.fits and not plan.resize and plan.font_step == "small"


def test_wide_table_needs_condensation():
    assert needs_condense(_wide(14), TableFitSettings())


def test_long_table_needs_condensation_even_when_narrow():
    settings = TableFitSettings()
    assert not needs_condense(_tall(25), settings)
    assert needs_condense(_tall(26), settings)


def test_font_step_escalates_before_resizing():
    # 22 chars against a 20-char budget: \footnotesize (23) is enough, no \resizebox.
    settings = TableFitSettings(max_width_chars=20)
    grid = TableGrid(header=["a" * 9, "b" * 9], rows=[["1", "2"]])
    plan = plan_fit(grid, settings)
    assert plan.measure.width_chars == 22
    assert plan.fits and plan.font_step == "footnotesize" and not plan.resize


def test_resizebox_is_the_last_rung():
    plan = plan_fit(_wide(30), TableFitSettings(max_width_chars=20))
    assert plan.resize and plan.font_step == "tiny"
    assert plan.strategy == "tiny+resizebox"


def test_resize_disabled_reports_a_table_that_does_not_fit():
    plan = plan_fit(_wide(30), TableFitSettings(max_width_chars=20, resize="off"))
    assert not plan.fits and not plan.resize


def test_resolve_fit_settings_defaults_and_flags():
    assert resolve_fit_settings() == TableFitSettings()
    resolved = resolve_fit_settings(max_width=170, max_rows=40, font_step="tiny")
    assert (resolved.max_width_chars, resolved.max_rows, resolved.font_step) == (170, 40, "tiny")


@pytest.mark.parametrize("bad", [{"font_step": "huge"}, {"max_rows": -1}])
def test_invalid_fit_settings_fail_fast(bad):
    with pytest.raises(ValueError):
        resolve_fit_settings(**bad)


def test_column_spec_infers_alignment():
    grid = parse_delimited(
        "model,acc,note\n"
        "baseline,0.81,a rather long free text explanation of the run\n"
        "ours,0.93,another long free text explanation of this run\n"
    )
    spec = build_column_spec(grid, plan_fit(grid, TableFitSettings()))
    assert spec.startswith("lr")
    assert "p{" in spec and "\\linewidth}" in spec


def test_uncertainty_cells_still_read_as_numeric():
    grid = TableGrid(header=["model", "acc"], rows=[["ours", "0.93 ± 0.02"]])
    assert build_column_spec(grid, plan_fit(grid, TableFitSettings())) == "lr"


def test_escape_cell_protects_math_spans():
    assert escape_cell("50% of $\\alpha_i$ & more_") == "50\\% of $\\alpha_i$ \\& more\\_"


def test_rendered_artifact_shape():
    grid = parse_delimited("model,acc\nbaseline,0.81\n")
    tex = render_table_artifact(grid, plan_fit(grid, TableFitSettings()), source="table/main.csv")
    assert "\\providecommand{\\toprule}{\\hline}" in tex
    assert "\\begin{tabular}{lr}" in tex
    assert "model & acc \\\\" in tex
    assert tex.count("\\toprule") == 2  # the shim definition and the rule itself
    assert "\\midrule" in tex and "\\bottomrule" in tex
    assert "\\resizebox" not in tex
    assert "table/main.csv" in tex


def test_rendered_artifact_wraps_in_resizebox_when_planned():
    grid = _wide(30)
    tex = render_table_artifact(
        grid, plan_fit(grid, TableFitSettings(max_width_chars=20)), source="table/wide.csv"
    )
    assert "\\resizebox{\\linewidth}{!}{%" in tex
    assert tex.rstrip().endswith("}")


def test_normalsize_emits_no_font_group():
    grid = parse_delimited("a,b\n1,2\n")
    tex = render_table_artifact(
        grid, plan_fit(grid, TableFitSettings(font_step="normalsize")), source="table/a.csv"
    )
    assert "{\\normalsize" not in tex


def test_display_width_discounts_markers_that_print_short():
    from parla.tools.table_parse import display_width

    # A citekey is ~50 source characters but prints as "[12]".
    assert display_width("BaobabView~<bib:vandenelzenBaobabViewInteractiveConstruction2011>") == 15
    assert display_width("**AcmeTrees (Ours)**") == len("AcmeTrees (Ours)")
    assert display_width("$R^2$ 0.99") == len("R^2 0.99")


def test_citation_heavy_table_is_measured_on_printed_width():
    grid = TableGrid(
        header=["Tool", "Support"],
        rows=[["BaobabView~<bib:vandenelzenBaobabViewInteractiveConstruction2011>", "Featured"]],
    )
    # 65 source characters in that cell, but it prints in ~15.
    assert measure_grid(grid).col_widths[0] < 20
    assert not needs_condense(grid, TableFitSettings())


def test_condense_only_when_type_shrinking_cannot_rescue():
    settings = TableFitSettings(max_width_chars=100, font_step_floor="scriptsize")
    fits_at_scriptsize = TableGrid(header=["a" * 60, "b" * 60], rows=[["1", "2"]])  # 124 chars
    assert not needs_condense(fits_at_scriptsize, settings)

    too_wide_for_any_step = TableGrid(header=["a" * 120, "b" * 120], rows=[["1", "2"]])  # 244
    assert needs_condense(too_wide_for_any_step, settings)


def test_row_overflow_still_condenses_regardless_of_width():
    assert needs_condense(_tall(40), TableFitSettings(max_width_chars=1000))


def test_bib_markers_become_citations_with_a_tie():
    assert escape_cell("BaobabView~<bib:vandenelzen2011>") == "BaobabView~\\cite{vandenelzen2011}"
    assert escape_cell("Tool <bib:a, b>") == "Tool~\\cite{a, b}"


def test_markdown_emphasis_becomes_latex():
    assert escape_cell("**Ours**") == "\\textbf{Ours}"
    assert escape_cell("*stressed*") == "\\emph{stressed}"
    assert escape_cell("`code_path`") == "\\texttt{code\\_path}"


CITED = TableGrid(
    header=["Tool", "Support"],
    rows=[
        ["BaobabView~<bib:vandenelzen2011>", "Absent"],
        ["iForest~<bib:zhao2019>", "Featured"],
        ["AcmeTrees", "Featured"],
    ],
)


def test_citation_width_is_configurable_and_changes_measurement():
    from parla.tools.table_fit import measure_grid as measure

    numeric = measure(CITED, citation_width=4).width_chars
    author_year = measure(CITED, citation_width=26).width_chars
    assert author_year > numeric
    assert author_year - numeric == 22


def test_hoisting_is_preferred_over_shrinking_type():
    # Inline overflows at \small; hoisting rescues it without stepping the font down.
    settings = TableFitSettings(max_width_chars=42, citation_width=26)
    plan = plan_fit(CITED, settings)
    assert plan.hoist_citations
    assert plan.font_step == "small"
    assert plan.strategy == "small+legend"


def test_inline_is_preferred_when_it_already_fits():
    plan = plan_fit(CITED, TableFitSettings(max_width_chars=200, citation_width=26))
    assert not plan.hoist_citations
    assert plan.strategy == "small"


def test_condense_is_judged_on_the_hoisted_variant():
    # Inline blows the floor budget, hoisted does not, so no LLM call is warranted.
    settings = TableFitSettings(max_width_chars=32, citation_width=26)
    from parla.tools.table_fit import measure_grid as measure

    assert measure(CITED, citation_width=26).width_chars > 32 * 1.35
    assert measure(CITED, citation_width=4).width_chars <= 32 * 1.35
    assert not needs_condense(CITED, settings)


def test_tables_without_citations_never_hoist():
    plan = plan_fit(_wide(30), TableFitSettings(max_width_chars=20))
    assert not plan.hoist_citations
    assert plan.resize


def test_legend_numbers_cells_and_lists_keys_once():
    grid = TableGrid(
        header=["Tool", "Note"],
        rows=[
            ["A~<bib:keyA>", "cf. <bib:keyB>"],
            ["B~<bib:keyB>", "again <bib:keyA>"],
        ],
    )
    plan = plan_fit(grid, TableFitSettings(max_width_chars=10, citation_width=26))
    assert plan.hoist_citations
    tex = render_table_artifact(grid, plan, source="table/t.md")

    assert "A~[1]" in tex and "B~[2]" in tex
    assert "cf.~[2]" in tex and "again~[1]" in tex
    assert tex.count(r"\cite{keyA}") == 1
    assert tex.count(r"\cite{keyB}") == 1
    assert r"[1]~\cite{keyA}" in tex and r"[2]~\cite{keyB}" in tex
    assert r"\begin{minipage}{\linewidth}\footnotesize\raggedright" in tex


def test_no_legend_when_not_hoisting():
    grid = TableGrid(header=["Tool"], rows=[["A~<bib:keyA>"]])
    plan = plan_fit(grid, TableFitSettings(max_width_chars=200, citation_width=26))
    tex = render_table_artifact(grid, plan, source="table/t.md")
    assert r"\minipage" not in tex
    assert r"A~\cite{keyA}" in tex


def test_grouped_citation_marker_lists_both_numbers():
    grid = TableGrid(header=["Tool"], rows=[["A~<bib:keyA, keyB>"]])
    plan = plan_fit(grid, TableFitSettings(max_width_chars=4, citation_width=26))
    tex = render_table_artifact(grid, plan, source="table/t.md")
    assert "A~[1, 2]" in tex


REAL_COMPARISON_TABLE = """
| Tool | Whole Ens. | Interact. | Counterfact. | Boundary | XGBoost | Rule Aggr. | Sub-path Aggr. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **AcmeTrees (Ours)** | Featured | Featured | Featured | Featured | Featured | Featured | Featured |
| BaobabView~<bib:vandenelzenBaobabViewInteractiveConstruction2011> | Absent | Featured | Absent | Partial | Absent | Absent | Absent |
| RuleExplorer~<bib:liRuleExplorerScalableMatrix2025> | Partial | Featured | Absent | Absent | Partial | Featured | Absent |
| DeforestVis~<bib:chatzimparmpasDeforestVisBehaviorAnalysis2024> | Absent | Featured | Partial | Absent | Absent | Partial | Absent |
"""


def test_real_author_year_comparison_table_fits_via_legend_without_condensing():
    """Regression for an overfull box in a real paper's comparison table.

    With `\\bibliographystyle{sbc}` a citation prints as `[Chatzimparmpas et al. 2024]`, so the
    inline table overflows. Hoisting must rescue it, and must not spend an LLM call.
    """
    from parla.tools.table_parse import parse_markdown

    grid = parse_markdown(REAL_COMPARISON_TABLE)
    settings = TableFitSettings()

    assert not needs_condense(grid, settings)

    plan = plan_fit(grid, settings)
    assert plan.hoist_citations and plan.fits and not plan.resize

    tex = render_table_artifact(grid, plan, source="table/comparison.md")
    assert "BaobabView~[1]" in tex
    assert r"\cite{vandenelzenBaobabViewInteractiveConstruction2011}" in tex
    assert r"\textbf{AcmeTrees (Ours)}" in tex
    # The rendered width the plan written to must be the hoisted one.
    assert plan.measure.width_chars <= settings.max_width_chars * 1.35
