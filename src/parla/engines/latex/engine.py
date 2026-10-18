"""The LaTeX engine: the contract over `build`, `export` and the checks. See `specs/latex-engine.md`."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from ... import config as config_mod
from ... import template
from ...checks import Finding, shared
from ...names import BUILD_DIR, NAME, PROJECT_DIR
from ...tools.measure import body_pages
from ..base import Built, Engine, EngineError, Pages, Starter
from . import build as build_mod
from . import checks as checks_mod
from . import export as export_mod


@dataclass(frozen=True)
class LatexBuilt(Built):
    pdf: Path | None = None
    aux: Path | None = None
    translations: tuple[build_mod.BuildResult, ...] = ()


class LatexEngine(Engine):
    name = "latex"
    card_keys = ("latex",)

    def prepare(self, root: Path) -> None:
        build_mod.ensure_image(config_mod.load(root))

    def starter(self, root: Path, artifact: str, modality: str, setup: dict | None) -> Starter:
        home = config_mod.texmf_home()
        dirs = [Path(str(files(NAME))) / "texmf", root / PROJECT_DIR / "texmf", *([home] if home else [])]
        return Starter("main.tex", {"latex": "lualatex"}, template.stock_files(modality, artifact, setup, dirs))

    def check(self, root: Path, artifact: str) -> list[Finding]:
        return [*shared.source_missing(root, artifact), *checks_mod.check(root, artifact)]

    def build(self, root: Path, artifact: str, baseline: Path | None) -> LatexBuilt:
        cfg = config_mod.load(root)
        main, *others = (
            build_mod.build(root, cfg, artifact, doc=doc, baseline=baseline)
            for doc in config_mod.documents(root, artifact)
        )
        return LatexBuilt(
            published=(main.published_pdf, *(r.published_pdf for r in others)),
            diff=main.diff_pdf,
            diffs=tuple(r.diff_pdf for r in others if r.diff_pdf),
            pdf=main.pdf,
            aux=main.aux,
            translations=tuple(others),
        )

    def mask(self, text: str) -> str:
        return checks_mod._strip(text)

    def post_build(self, root: Path, artifact: str) -> list[Finding]:
        found: list[Finding] = []
        for doc in config_mod.documents(root, artifact):
            log = root / PROJECT_DIR / BUILD_DIR / doc.slug / f"{doc.stem}.log"
            if log.is_file():
                found += checks_mod.log_findings(log.read_text(encoding="utf-8", errors="replace"), f"artifacts/{artifact}/{doc.entrypoint}")
        return found

    def pages(self, root: Path, artifact: str, language: str | None = None) -> Pages | None:
        docs = {d.tag or config_mod.load_card(root, artifact).language: d for d in config_mod.documents(root, artifact)}
        if language is not None and language not in docs:
            raise EngineError(f"artifact '{artifact}' has no language '{language}' (have: {', '.join(docs)})")
        doc = docs[language] if language else next(iter(docs.values()))
        base = root / PROJECT_DIR
        return body_pages(base / "artifacts" / artifact / f"{doc.slug}.pdf", base / BUILD_DIR / doc.slug / f"{doc.stem}.aux")

    def export(self, root: Path, artifact: str, tag: str, force: bool) -> Path:
        cfg = config_mod.load(root)
        main, *_ = (
            export_mod.export_document(root, cfg, artifact, tag, force=force, doc=doc)
            for doc in config_mod.documents(root, artifact)
        )
        return main
