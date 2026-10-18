"""Change PDF: flatten prose \\input/\\include, run latexdiff, compile the result. See
`specs/latex-engine.md#diff`."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ... import config as config_mod
from ...config import Config, Document
from ...names import BUILD_DIR, PROJECT_DIR
from .build import BuildError, compile_entrypoint, docker_base, ensure_image

_INPUT = re.compile(r"\\(?:input|include)\{([^}]+)\}")


def _split_comment(line: str) -> tuple[str, str]:
    match = re.search(r"(?<!\\)%", line)
    return (line, "") if match is None else (line[: match.start()], line[match.start():])


def _is_prose(target: str, artifact: str) -> bool:
    """Targets inside the artifact folder, except its rendered tables."""
    return target.startswith(f"artifacts/{artifact}/") and not target.startswith(
        f"artifacts/{artifact}/table/"
    )


def flatten(text: str, bases: list[Path], artifact: str, depth: int = 0) -> str:
    """Inline \\input/\\include of the artifact's own files (not its tables), recursively.
    Each target is looked up in `bases` in order, as written and then with `.tex`. Anything
    else (diagram, table, a commented-out line) is kept as-is."""
    if depth > 20:
        raise BuildError("\\input nesting deeper than 20 levels")
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        code, comment = _split_comment(line)

        def inline(match: re.Match[str]) -> str:
            target = match.group(1).strip()
            if not _is_prose(target, artifact):
                return match.group(0)
            for base in bases:
                for candidate in (base / target, base / f"{target}.tex"):
                    if candidate.is_file():
                        return flatten(candidate.read_text(encoding="utf-8"), bases, artifact, depth + 1)
            return match.group(0)

        out.append(_INPUT.sub(inline, code) + comment)
    return "".join(out)


def render_diff(
    root: Path, cfg: Config, name: str, baseline: Path, *, doc: Document | None = None, on_output=print
) -> Path:
    """Flatten both sides, latexdiff them, compile the result, and publish it as
    `parla/artifacts/<name>/<slug>_diff.pdf`. The baseline is any directory that holds the entrypoint."""
    doc = doc or config_mod.document(root, name)
    tex = (root / PROJECT_DIR).resolve()
    old_dir = baseline.resolve()
    if not (old_dir / doc.entrypoint).is_file():
        raise BuildError(f"the baseline must be a directory holding {doc.entrypoint}, got {old_dir}")

    work = tex / BUILD_DIR / f"{doc.slug}_diff"
    work.mkdir(parents=True, exist_ok=True)
    (work / "old.flat.tex").write_text(
        flatten((old_dir / doc.entrypoint).read_text(encoding="utf-8"), [old_dir, tex], name), encoding="utf-8"
    )
    (work / "new.flat.tex").write_text(
        flatten((tex / doc.entrypoint).read_text(encoding="utf-8"), [tex], name), encoding="utf-8"
    )
    rel = work.relative_to(tex).as_posix()

    # Ensure the image exists exactly like build() does - render_diff calls
    # compile_entrypoint directly, bypassing build()'s own check.
    ensure_image(cfg, on_output)

    proc = subprocess.run(
        docker_base(root, cfg) + [
            "latexdiff", "--type=UNDERLINE",
            "--config", r"PICTUREENV=(?:picture|tikzpicture|DIFnomarkup)[\w\d*@]*",
            f"{rel}/old.flat.tex", f"{rel}/new.flat.tex",
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        (work / "latexdiff.log").write_text(proc.stderr, encoding="utf-8")
        raise BuildError(f"latexdiff failed (exit {proc.returncode}); see {work / 'latexdiff.log'}")

    stem = Path(doc.entrypoint).stem
    (work / f"{stem}_diff.tex").write_text(proc.stdout, encoding="utf-8")
    pdf = compile_entrypoint(
        root, cfg, engine=doc.engine, entrypoint=f"{rel}/{stem}_diff.tex",
        outdir=rel, log_name=f"{doc.slug}_diff",
    )
    published = tex / "artifacts" / name / f"{doc.slug}_diff.pdf"
    shutil.copy2(pdf, published)
    return published
