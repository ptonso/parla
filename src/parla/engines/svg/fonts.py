"""Latin Modern metrics: the same font files the image renders with. `_font`, `text_width` and
`asc_desc` are copied from `texfy_ai.core.draft.diagram_layout`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ...names import NAME

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
WIDTH_MARGIN = 1.015

FONT_FILES = {
    ("sans", False, False): "lmsans10-regular.otf",
    ("sans", True, False): "lmsans10-bold.otf",
    ("sans", False, True): "lmsans10-oblique.otf",
    ("sans", True, True): "lmsans10-boldoblique.otf",
    ("mono", False, False): "lmmono10-regular.otf",
    ("mono", True, False): "lmmonolt10-bold.otf",
    ("mono", False, True): "lmmono10-italic.otf",
    ("mono", True, True): "lmmono10-italic.otf",
}
FAMILY_NAME = {"sans": "Latin Modern Sans", "mono": "Latin Modern Mono"}


@lru_cache(maxsize=None)
def _font(fam: str, bold: bool, ital: bool):
    try:
        from fontTools.ttLib import TTFont
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"the SVG checks need the optional `svg` extra: pip install '{NAME}[svg]'") from exc
    f = TTFont(FONT_DIR / FONT_FILES[(fam, bold, ital)])
    return f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm, f["hhea"], f["OS/2"]


def has_glyph(ch: str, fam: str, bold: bool, ital: bool) -> bool:
    return ord(ch) in _font(fam, bold, ital)[0]


def text_width(s: str, fam: str, bold: bool, ital: bool, size: float) -> float:
    """The drawn width of `s`; characters the font lacks count as zero (the glyph check reports them)."""
    cmap, hmtx, upem, *_ = _font(fam, bold, ital)
    total = 0
    for ch in s:
        g = cmap.get(ord(ch))
        if g is not None:
            total += hmtx[g][0]
    return total / upem * size * WIDTH_MARGIN


def asc_desc(fam: str, size: float) -> tuple[float, float]:
    """The ascent and descent of the drawn glyphs. texfy's copy read the `hhea` line metrics
    (1.15 and 0.31 em), which include leading, so two lines at 1.25 em spacing would overlap; the
    OS/2 typographic metrics are the extent of the glyphs themselves."""
    font = _font(fam, False, False)
    os2 = font[4]
    return os2.sTypoAscender / font[2] * size, -os2.sTypoDescender / font[2] * size
