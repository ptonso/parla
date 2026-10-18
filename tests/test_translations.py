from __future__ import annotations

from pathlib import Path

import pytest

from parla import config as config_mod
from parla.engines.latex import checks as checks_mod
from parla.names import is_output

from conftest import make_artifact

SECTION = "\\section{Experience}\n\\cventry{a}{b}{c}{d}\n\\begin{cvitems}\n\\item one\n\\item two\n\\end{cvitems}\n"
MAIN = "\\input{artifacts/cv/section/experience}\n"


def _cv(tmp_path: Path, pt_section: str = SECTION) -> Path:
    base = make_artifact(
        tmp_path, "cv",
        {"main.tex": MAIN, "section/experience.tex": SECTION,
         "pt/main.tex": MAIN.replace("cv/", "cv/pt/"), "pt/section/experience.tex": pt_section},
    )
    card = base / "card.md"
    card.write_text(card.read_text().replace("derived-from: null", "derived-from: null\nlanguage: en\ntranslations:\n  pt: pt"))
    return base


def test_documents_lists_the_artifact_then_each_translation(tmp_path: Path) -> None:
    _cv(tmp_path)

    main, pt = config_mod.documents(tmp_path, "cv")

    assert (main.entrypoint, main.slug) == ("artifacts/cv/main.tex", "cv")
    assert (pt.entrypoint, pt.slug, pt.tag) == ("artifacts/cv/pt/main.tex", "cv-pt", "pt")


def test_a_card_without_translations_has_one_document(tmp_path: Path) -> None:
    make_artifact(tmp_path, "paper")

    assert [d.slug for d in config_mod.documents(tmp_path, "paper")] == ["paper"]


@pytest.mark.parametrize("translations", ["  en: pt", "  pt: ../pt", "  pt: ''", "  PT: pt"])
def test_invalid_translations_fail_fast(tmp_path: Path, translations: str) -> None:
    base = make_artifact(tmp_path, "cv")
    card = base / "card.md"
    card.write_text(card.read_text().replace("derived-from: null", f"derived-from: null\ntranslations:\n{translations}"))

    with pytest.raises(config_mod.ConfigError):
        config_mod.load_card(tmp_path, "cv")


def test_parity_passes_for_matching_trees(tmp_path: Path) -> None:
    _cv(tmp_path)

    assert checks_mod.translation_parity(tmp_path, "cv") == []


def test_parity_reports_a_missing_file_and_a_missing_bullet(tmp_path: Path) -> None:
    base = _cv(tmp_path, SECTION.replace("\\item two\n", ""))
    (base / "section" / "skills.tex").write_text("\\section{Skills}\n", encoding="utf-8")
    (base / "main.tex").write_text(MAIN + "\\input{artifacts/cv/section/skills}\n", encoding="utf-8")

    messages = [f.message for f in checks_mod.translation_parity(tmp_path, "cv")]

    assert any("section/skills.tex is not reached" in m for m in messages)
    assert any("structure differs from section/experience.tex" in m for m in messages)


def test_translation_outputs_count_as_outputs() -> None:
    assert is_output(Path("artifacts/cv/cv-pt.pdf")) and is_output(Path("artifacts/cv/cv-pt_diff.pdf"))
    assert not is_output(Path("artifacts/cv/cv-portuguese.pdf"))
