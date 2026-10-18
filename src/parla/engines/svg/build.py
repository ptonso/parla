"""Render an SVG artifact to PDF and PNG with `rsvg-convert` in the container, and the
side-by-side diff against a baseline. See `specs/svg-engine.md#build`. `rsvg_to_pdf` descends from
`texfy_ai.core.draft.svg_render`."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ... import config as config_mod
from ...config import Config
from ...names import BUILD_DIR, PROJECT_DIR
from ...tools.formula import _read_png_dimensions
from ..base import BuildError
from ..latex.build import docker_base, ensure_image

PNG_ZOOM = "2"
DIFF_GAP = 20


@dataclass(frozen=True)
class Rendered:
    pdf: Path
    png: Path


def _rsvg(root: Path, cfg: Config, args: list[str], *, log: Path, file: str) -> None:
    result = subprocess.run([*docker_base(root, cfg), "rsvg-convert", *args], capture_output=True, text=True, check=False)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise BuildError(f"{file}:1: error compile-error: rsvg-convert failed: {result.stderr.strip()} (log: {log})")


def render(
    root: Path, cfg: Config, svg: Path, outdir: Path, stem: str, *, file: str, pdf_too: bool = True
) -> Rendered:
    """Renders `svg` to `outdir/<stem>.pdf` and `.png`. `<image href>` paths are relative to
    `parla/` while librsvg only reads below the SVG's own directory, so the render is of a copy
    at the root of `parla/`."""
    base = (root / PROJECT_DIR).resolve()
    copy = base / f".render-{stem}.svg"
    shutil.copyfile(svg, copy)
    outdir.mkdir(parents=True, exist_ok=True)
    pdf, png = outdir / f"{stem}.pdf", outdir / f"{stem}.png"
    log = outdir / f"{stem}_build.log"
    try:
        if pdf_too:
            _rsvg(root, cfg, ["-f", "pdf", "-o", pdf.relative_to(base).as_posix(), copy.name], log=log, file=file)
        _rsvg(root, cfg, ["-f", "png", "-z", PNG_ZOOM, "-o", png.relative_to(base).as_posix(), copy.name], log=log, file=file)
    finally:
        copy.unlink(missing_ok=True)
    return Rendered(pdf, png)


def side_by_side(root: Path, cfg: Config, old_png: Path, new_png: Path, out_png: Path, *, file: str) -> None:
    """A wrapper SVG with the baseline render on the left and the current one on the right."""
    (w1, h1), (w2, h2) = _read_png_dimensions(old_png), _read_png_dimensions(new_png)
    work = new_png.parent
    shutil.copyfile(old_png, work / "old.png")
    shutil.copyfile(new_png, work / "new.png")
    wrapper = work / "diff.svg"
    wrapper.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w1 + DIFF_GAP + w2} {max(h1, h2)}">\n'
        f'<rect width="100%" height="100%" fill="#ffffff"/>\n'
        f'<image href="old.png" x="0" y="0" width="{w1}" height="{h1}"/>\n'
        f'<image href="new.png" x="{w1 + DIFF_GAP}" y="0" width="{w2}" height="{h2}"/>\n</svg>\n',
        encoding="utf-8",
    )
    base = (root / PROJECT_DIR).resolve()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    _rsvg(
        root, cfg, ["-f", "png", "-o", out_png.relative_to(base).as_posix(), wrapper.relative_to(base).as_posix()],
        log=work / "diff_build.log", file=file,
    )


def build(root: Path, artifact: str, baseline: Path | None) -> tuple[Path, Path, Path | None]:
    """`(published pdf, published png, published diff png or None)`."""
    cfg = config_mod.load(root)
    card = config_mod.load_card(root, artifact)
    ensure_image(cfg)
    base = (root / PROJECT_DIR).resolve()
    rel = f"artifacts/{artifact}/{card.entrypoint}"
    rendered = render(root, cfg, base / rel, base / BUILD_DIR / artifact, artifact, file=rel)
    pdf_dir = base / "artifacts" / artifact
    pdf, png = pdf_dir / f"{artifact}.pdf", pdf_dir / f"{artifact}.png"
    shutil.copyfile(rendered.pdf, pdf)
    shutil.copyfile(rendered.png, png)
    if baseline is None:
        return pdf, png, None
    old_svg = baseline / rel
    if not old_svg.is_file():
        raise BuildError(f"the baseline must hold {rel}, got {baseline}")
    work = base / BUILD_DIR / f"{artifact}_diff"
    old = render(root, cfg, old_svg, work, "old-render", file=rel, pdf_too=False)
    shutil.copyfile(rendered.png, work / "new-render.png")
    diff = pdf_dir / f"{artifact}_diff.png"
    side_by_side(root, cfg, old.png, work / "new-render.png", diff, file=rel)
    return pdf, png, diff
