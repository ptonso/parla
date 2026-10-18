"""Every supported format, however badly formatted, reduces to the same canonical grid."""

from __future__ import annotations

import pytest

from parla.tools.table_parse import (
    TableParseError,
    parse_delimited,
    parse_json,
    parse_latex,
    parse_markdown,
)

EXPECTED_HEADER = ["model", "acc", "f1"]
EXPECTED_ROWS = [["baseline", "0.81", "0.79"], ["ours", "0.93", "0.91"]]


def _assert_canonical(grid) -> None:
    assert grid.header == EXPECTED_HEADER
    assert grid.rows == EXPECTED_ROWS


def test_clean_csv():
    _assert_canonical(parse_delimited("model,acc,f1\nbaseline,0.81,0.79\nours,0.93,0.91\n"))


def test_csv_with_title_line_above_the_header():
    _assert_canonical(
        parse_delimited("Results for run 3\nmodel,acc,f1\nbaseline,0.81,0.79\nours,0.93,0.91\n")
    )


def test_ragged_csv_rows_are_squared():
    grid = parse_delimited("model,acc,f1\nbaseline,0.81\nours,0.93,0.91\n")
    assert grid.header == EXPECTED_HEADER
    assert grid.rows == [["baseline", "0.81", ""], ["ours", "0.93", "0.91"]]


def test_csv_trailing_delimiter_column_is_dropped():
    _assert_canonical(parse_delimited("model,acc,f1,\nbaseline,0.81,0.79,\nours,0.93,0.91,\n"))


def test_semicolon_delimiter_is_sniffed():
    _assert_canonical(parse_delimited("model;acc;f1\nbaseline;0.81;0.79\nours;0.93;0.91\n"))


def test_tsv_falls_back_to_tab_when_sniffing_fails():
    grid = parse_delimited("model\tacc\tf1\nbaseline\t0.81\t0.79\n", default_delimiter="\t")
    assert grid.header == EXPECTED_HEADER


def test_misaligned_markdown_pipes():
    _assert_canonical(
        parse_markdown(
            "| model   | acc  |  f1 |\n"
            "|:---|---:|:--:|\n"
            "| baseline |0.81|   0.79|\n"
            "|ours | 0.93 | 0.91 |\n"
        )
    )


def test_markdown_without_outer_pipes():
    _assert_canonical(
        parse_markdown("model | acc | f1\n--- | --- | ---\nbaseline | 0.81 | 0.79\nours | 0.93 | 0.91\n")
    )


def test_markdown_ignores_surrounding_prose():
    _assert_canonical(
        parse_markdown(
            "Some notes about the run.\n\n"
            "| model | acc | f1 |\n| --- | --- | --- |\n"
            "| baseline | 0.81 | 0.79 |\n| ours | 0.93 | 0.91 |\n"
        )
    )


def test_json_list_of_objects():
    _assert_canonical(
        parse_json(
            '[{"model": "baseline", "acc": 0.81, "f1": 0.79},'
            ' {"model": "ours", "acc": 0.93, "f1": 0.91}]'
        )
    )


def test_json_columns_and_rows_object():
    _assert_canonical(
        parse_json(
            '{"columns": ["model", "acc", "f1"],'
            ' "rows": [["baseline", 0.81, 0.79], ["ours", 0.93, 0.91]]}'
        )
    )


def test_latex_booktabs_tabular():
    _assert_canonical(
        parse_latex(
            "\\begin{tabular}{lrr}\n"
            "\\toprule\n"
            "model & acc & f1 \\\\\n"
            "\\midrule\n"
            "baseline & 0.81 & 0.79 \\\\\n"
            "ours & 0.93 & 0.91 \\\\\n"
            "\\bottomrule\n"
            "\\end{tabular}\n"
        )
    )


def test_latex_strips_wrappers_multicolumn_and_comments():
    grid = parse_latex(
        "\\begin{table}[ht]\n\\centering\n"
        "\\begin{tabular}{lrr}\n"
        "\\hline\n"
        "\\multicolumn{1}{c}{model} & \\textbf{acc} & \\texttt{f1} \\\\ % header\n"
        "\\hline\n"
        "baseline & 0.81 & 0.79 \\\\[2pt]\n"
        "ours & 0.93 & 0.91 \\\\\n"
        "\\hline\n"
        "\\end{tabular}\n\\end{table}\n"
    )
    _assert_canonical(grid)


def test_latex_unescapes_cells_so_the_renderer_can_re_escape():
    grid = parse_latex(
        "\\begin{tabular}{ll}\nmetric & value \\\\\ncoverage \\% & 50\\_units \\\\\n\\end{tabular}\n"
    )
    assert grid.rows == [["coverage %", "50_units"]]


def test_to_markdown_round_trips():
    grid = parse_delimited("model,acc,f1\nbaseline,0.81,0.79\nours,0.93,0.91\n")
    _assert_canonical(parse_markdown(grid.to_markdown()))


@pytest.mark.parametrize(
    "parser,payload",
    [
        (parse_delimited, "   "),
        (parse_markdown, "no table here"),
        (parse_json, "{not json"),
        (parse_latex, "\\begin{tabular}{l}\n\\end{tabular}"),
    ],
)
def test_unusable_sources_raise(parser, payload):
    with pytest.raises(TableParseError):
        parser(payload)
