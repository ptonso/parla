"""`[links]` sync: makes `parla/sources/<key>` a symlink to its configured host target."""

from __future__ import annotations

from pathlib import Path

from ...config import Config
from ...names import NAME, PROJECT_DIR


class LinkError(Exception):
    """A [links] entry cannot be synced."""


def sync_links(root: Path, cfg: Config) -> list[str]:
    """Make parla/sources/<key> a symlink to each [links] value; return one line per created or repointed link."""
    lines: list[str] = []
    sources = root / PROJECT_DIR / "sources"
    for key, value in sorted(cfg.links.items()):
        target = Path(value).expanduser()
        target = (target if target.is_absolute() else root / target).resolve()
        if not target.exists():
            raise LinkError(f"[links] {key!r}: target does not exist: {target}")
        link = sources / key
        if link.is_symlink():
            if link.resolve() == target:
                continue
            link.unlink()
            lines.append(f"repointed sources/{key} -> {target}")
        elif link.exists():
            raise LinkError(f"{link} is a real path; move it aside so {NAME} can link it")
        else:
            lines.append(f"linked sources/{key} -> {target}")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
    return lines
