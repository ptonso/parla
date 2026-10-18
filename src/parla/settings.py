"""User-level config: `~/.config/parla/config.toml`.

Distinct from the per-project `parla/parla.toml` handled by `config.py`. This file holds a
user's personal wiring (asset store, shared Zotero library, personal texmf, private guides). It
is entirely optional: with no file, parla keeps `parla/` inside the project. See `data/config.example.toml`.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from .names import CONFIG_DIR_NAME, ENV_PREFIX


def config_path() -> Path:
    """`$PARLA_CONFIG`, else `$XDG_CONFIG_HOME/parla/config.toml`, else `~/.config/parla/config.toml`."""
    override = os.environ.get(f"{ENV_PREFIX}_CONFIG")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / CONFIG_DIR_NAME / "config.toml"


def example_path() -> Path:
    """The shipped, fully-commented template."""
    from importlib.resources import files

    return Path(str(files(CONFIG_DIR_NAME))) / "data" / "config.example.toml"


def _raw() -> dict:
    path = config_path()
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _table(name: str) -> dict:
    value = _raw().get(name)
    return value if isinstance(value, dict) else {}


def opt_path(table: str, key: str, *, must_exist: bool = False) -> Path | None:
    """A `~`-expanded path from `[table].key`, or `None` when unset. When `must_exist`, a
    configured-but-missing path is a fatal `ConfigError` (a configured feature was asked for)."""
    value = _table(table).get(key)
    if not isinstance(value, str) or not value:
        return None
    path = Path(value).expanduser()
    if must_exist and not path.exists():
        from .config import ConfigError

        raise ConfigError(f"[{table}].{key} = {value!r} does not exist (set in {config_path()})")
    return path


def str_list(table: str, key: str) -> list[str]:
    """A list-of-strings value from `[table].key`, or `[]` when unset."""
    value = _table(table).get(key)
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        return []
    return list(value)


def opt_int(table: str, key: str) -> int | None:
    """An integer value from `[table].key`, or `None` when unset. A non-integer is fatal."""
    value = _table(table).get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        from .config import ConfigError

        raise ConfigError(f"[{table}].{key} must be a positive integer (set in {config_path()})")
    return value


def opt_float(table: str, key: str, *, minimum: float = 1.0) -> float | None:
    """A number from `[table].key` of at least `minimum`, or `None` when unset. Anything else is fatal."""
    value = _table(table).get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or value < minimum:
        from .config import ConfigError

        raise ConfigError(f"[{table}].{key} must be a number of at least {minimum:g} (set in {config_path()})")
    return float(value)


def has_key(table: str, key: str) -> bool:
    return key in _table(table)
