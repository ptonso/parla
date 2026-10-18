"""`[packages].autoload`: texmf files the project loads on every document, written as a managed
block in the project's own `project.sty` so no entrypoint needs editing."""

from __future__ import annotations

from pathlib import Path

from ... import config as config_mod
from ...config import Config, ConfigError
from ...names import NAME, PROJECT_DIR, TOML

BEGIN = f"% >>> {NAME} autoload (generated from {TOML} [packages].autoload)"
END = f"% <<< {NAME} autoload"


def project_sty(root: Path, cfg: Config) -> Path:
    return root / PROJECT_DIR / cfg.texmf / "tex" / "latex" / "project" / "project.sty"


def resolve(root: Path, cfg: Config) -> list[Path]:
    """The texmf file behind each autoload name, project texmf first, then `texmf_home`."""
    home = config_mod.texmf_home()
    roots = [root / PROJECT_DIR / cfg.texmf, *([home] if home is not None else [])]
    resolved = []
    for name in cfg.autoload:
        candidates = [
            path
            for base in roots
            if base.is_dir()
            for suffix in (".sty", ".tex")
            for path in sorted(base.rglob(f"{name}{suffix}"))
        ]
        if not candidates:
            raise ConfigError(f"[packages].autoload: '{name}' is not a .sty or .tex under the project texmf or texmf_home")
        resolved.append(candidates[0])
    return resolved


def render_block(files: list[Path], require: tuple[str, ...] = ()) -> str:
    lines = [f"\\RequirePackage{{{n}}}" for n in require] + [
        f"\\RequirePackage{{{p.stem}}}" if p.suffix == ".sty" else f"\\input{{{p.name}}}" for p in files
    ]
    return "\n".join([BEGIN, *lines, END])


def sync_project_sty(root: Path, cfg: Config) -> None:
    """Idempotent. Replaces the managed block, or inserts it before `\\endinput`."""
    sty = project_sty(root, cfg)
    if not cfg.autoload and not cfg.require and not sty.is_file():
        return
    text = sty.read_text(encoding="utf-8")
    block = render_block(resolve(root, cfg), cfg.require) if cfg.autoload or cfg.require else ""
    if BEGIN in text:
        head, rest = text.split(BEGIN, 1)
        tail = rest.split(END, 1)[1]
        new = head.rstrip("\n") + ("\n" + block if block else "") + tail
    elif block:
        new = text.replace("\\endinput", block + "\n\\endinput", 1) if "\\endinput" in text else text.rstrip("\n") + "\n" + block + "\n"
    else:
        return
    if new != text:
        sty.write_text(new, encoding="utf-8")
