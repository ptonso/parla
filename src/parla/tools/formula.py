"""`parla tool formula`: a formula typeset in the container and rasterized to a PNG. The digest,
the PNG header reader and the standalone document are copied from
`texfy_ai.core.draft.formula_render`."""

from __future__ import annotations

import hashlib
import struct
import subprocess
from pathlib import Path

from .. import config as config_mod
from ..engines.base import BuildError
from ..engines.latex.build import compile_entrypoint, docker_base, ensure_image
from ..names import BUILD_DIR, PROJECT_DIR

_FORMULA_DPI = 300


class FormulaError(Exception):
    """A formula cannot be rendered."""


def _formula_digest(formula: str, *, display: bool) -> str:
    payload = f"{'display' if display else 'inline'}:{formula}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _read_png_dimensions(png_path: Path) -> tuple[int, int]:
    """Width/height straight out of a PNG's IHDR chunk -- no image library needed for a format
    this simple: signature (8 bytes), chunk length (4), "IHDR" (4), width (4, big-endian),
    height (4)."""
    header = png_path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise FormulaError(f"{png_path} is not a valid PNG (missing IHDR header).")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def _standalone_formula_tex(formula: str, *, display: bool) -> str:
    body = f"\\[{formula}\\]" if display else f"${formula}$"
    return "\n".join(
        [
            "\\documentclass[preview,border=1pt]{standalone}",
            "\\usepackage{amsmath,amssymb}",
            "\\begin{document}",
            body,
            "\\end{document}",
            "",
        ]
    )


def render(root: Path, artifact: str, formula: str, *, display: bool) -> tuple[Path, int, int]:
    """Writes `artifacts/<artifact>/formula/<hash>.png` unless it exists; returns its path and size."""
    config_mod.load_card(root, artifact)
    base = (root / PROJECT_DIR).resolve()
    digest = _formula_digest(formula, display=display)
    png = base / "artifacts" / artifact / "formula" / f"{digest}.png"
    if not png.is_file():
        cfg = config_mod.load(root)
        ensure_image(cfg)
        work = base / BUILD_DIR / artifact / f"formula-{digest}"
        work.mkdir(parents=True, exist_ok=True)
        rel = work.relative_to(base).as_posix()
        (work / "formula.tex").write_text(_standalone_formula_tex(formula, display=display), encoding="utf-8")
        try:
            compile_entrypoint(
                root, cfg, engine="pdflatex", entrypoint=f"{rel}/formula.tex", outdir=rel,
                log_name=f"formula-{digest}",
            )
        except BuildError as exc:
            raise FormulaError(f'the formula "{formula}" failed to typeset: {exc}') from exc
        convert = subprocess.run(
            [*docker_base(root, cfg), "pdftoppm", "-png", "-r", str(_FORMULA_DPI), "-singlefile",
             f"{rel}/formula.pdf", f"{rel}/formula"],
            capture_output=True, text=True, check=False,
        )
        if convert.returncode != 0:
            raise FormulaError(f'rasterizing the formula "{formula}" failed: {convert.stderr.strip()}')
        png.parent.mkdir(parents=True, exist_ok=True)
        (work / "formula.png").replace(png)
    width, height = _read_png_dimensions(png)
    return png, width, height
