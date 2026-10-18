"""The name-to-engine map. The only module that names concrete engines."""

from __future__ import annotations

from ..config import Card, ConfigError
from .base import Engine
from .latex.engine import LatexEngine
from .none.engine import NoneEngine
from .svg.engine import SvgEngine

ENGINES: dict[str, Engine] = {e.name: e for e in (LatexEngine(), NoneEngine(), SvgEngine())}


def named(name: str) -> Engine:
    try:
        return ENGINES[name]
    except KeyError:
        raise ConfigError(f"unknown engine '{name}' (registered: {', '.join(sorted(ENGINES))})") from None


def get(card: Card) -> Engine:
    return named(card.engine)
