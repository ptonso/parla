"""parla.toml and card load + validation. Single source of truth for the schema; fail-fast.

Three configs, kept apart:
- the per-project `parla/parla.toml` (`load` / `_validate` / `Config` below);
- the per-artifact `parla/artifacts/<name>/card.md` (`load_card` / `Card`);
- the optional user-level `~/.config/parla/config.toml` (`settings.py`), read through the
  `asset_root` / `library_*` / `texmf_home` / `guides_*` accessors here. Every one of
  those degrades gracefully when the file or a key is absent (the project stores `parla/` locally).
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter, settings
from .checks.ids import SEVERITY
from .names import NAME, PROJECT_DIR, TOML

LATEX_ENGINES = {"lualatex", "pdflatex"}
PHASES = {"drafting", "polishing"}
DEFAULT_LANGUAGE = "en"
LANGUAGE_RE = re.compile(r"[a-z]{2,3}")
CARD_REQUIRED = ("modality", "audience", "engine", "entrypoint", "phase", "derived-from")
ALLOWED_TABLES = {"project", "docker", "paths", "packages", "checks", "links"}


class ConfigError(Exception):
    """Raised on any invalid parla.toml or card; surfaced to the user as a fatal error."""


@dataclass(frozen=True)
class Document:
    """One buildable entrypoint of an artifact: the artifact itself (`tag == ""`) or one of its
    translations (`tag` is the language code)."""

    name: str
    entrypoint: str
    engine: str
    tag: str = ""

    @property
    def stem(self) -> str:
        return Path(self.entrypoint).stem

    @property
    def slug(self) -> str:
        """The name of this document's outputs: `<name>` or `<name>-<tag>`."""
        return f"{self.name}-{self.tag}" if self.tag else self.name


@dataclass(frozen=True)
class Config:
    version: int
    image: str
    texmf: str
    links: dict[str, str]
    autoload: tuple[str, ...] = ()
    require: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()


@dataclass(frozen=True)
class Card:
    """`card.md`: the frontmatter keys plus the Markdown body. `keys` is the raw
    frontmatter, where an engine reads its own card keys such as `latex`."""

    modality: str
    audience: str
    engine: str
    entrypoint: str
    phase: str
    derived_from: str | None
    language: str
    translations: dict[str, str]
    traits: dict[str, str]
    limits: dict
    keys: dict
    body: str


def asset_root() -> Path | None:
    """`[storage].asset_root` - the folder `parla init` keeps each project's `parla/` tree in,
    as `<asset_root>/<project folder name>`. `None` (local storage) when unset."""
    return settings.opt_path("storage", "asset_root")


def texmf_home() -> Path | None:
    """`[storage].texmf_home` - an extra personal TEXMF tree bind-mounted read-only into
    the build container. `None` when unset; a configured-but-missing path is fatal."""
    return settings.opt_path("storage", "texmf_home", must_exist=True)


def library_bib() -> Path | None:
    """The Better BibTeX `.bib` auto-export (`[storage].library_bib`), or `None` when the
    key is unset or the file is absent -- an extras-only project is valid."""
    path = settings.opt_path("storage", "library_bib")
    return path if path is not None and path.is_file() else None


def library_json() -> Path | None:
    """The Better BibTeX `.json` auto-export (`[storage].library_json`), source of Zotero
    item keys and PDF attachment paths. `None` when unset or absent."""
    path = settings.opt_path("storage", "library_json")
    return path if path is not None and path.is_file() else None


def guides_private() -> Path:
    """`[guides].private` - the root of the user's guides and casebook; the config directory
    by default."""
    return settings.opt_path("guides", "private") or settings.config_path().parent


def guides_target_words() -> int:
    """`[guides].target_words` - the recommended size of one `guide show` output."""
    if settings.has_key("guides", "max_words"):
        raise ConfigError(f"[guides].max_words was removed; set [guides].target_words (see `{NAME} config init`)")
    return settings.opt_int("guides", "target_words") or 1500


def guides_tolerance() -> float:
    """`[guides].tolerance` - the multiple of the target beyond which a load warns that the guides need distilling."""
    return settings.opt_float("guides", "tolerance") or 1.2


def guides_limit_words() -> int:
    return int(guides_target_words() * guides_tolerance())


def guides_max_page_words() -> int:
    return settings.opt_int("guides", "max_page_words") or 350


def guides_max_probes() -> int:
    return settings.opt_int("guides", "max_probes") or 20


def guides_max_cases() -> int:
    return settings.opt_int("guides", "max_cases") or 8


def guides_distill_min() -> int:
    return settings.opt_int("guides", "distill_min") or 3


def guides_stale_days() -> int | None:
    return settings.opt_int("guides", "stale_days")



def find_root(start: Path) -> Path:
    """Nearest ancestor whose parla/parla.toml exists. Fail-fast if none."""
    for d in (start, *start.parents):
        if (d / PROJECT_DIR / TOML).is_file():
            return d
    raise ConfigError(f"no {PROJECT_DIR}/{TOML} found in {start} or any ancestor")


def load(root: Path) -> Config:
    path = root / PROJECT_DIR / TOML
    if not path.is_file():
        raise ConfigError(f"missing {path}")
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    return _validate(raw)


def _validate(raw: dict) -> Config:
    unknown = set(raw) - ALLOWED_TABLES
    if unknown:
        raise ConfigError(f"unknown top-level table(s): {', '.join(sorted(unknown))}")

    project = raw.get("project") or {}
    version = project.get("version")
    if not isinstance(version, int):
        raise ConfigError("[project].version is required (int)")
    if version != 1:
        raise ConfigError("[project].version must be 1")

    image = (raw.get("docker") or {}).get("image")
    if image is None:
        from .engines.latex import image as image_mod

        image = image_mod.IMAGE_REF
    elif not isinstance(image, str) or not image:
        raise ConfigError("[docker].image must be a non-empty string when set")
    elif ":" not in image.rsplit("/", 1)[-1]:
        raise ConfigError(f"[docker].image must be a tagged reference, got '{image}'")

    paths = raw.get("paths") or {}
    unknown = set(paths) - {"texmf"}
    if unknown:
        raise ConfigError(
            f"unknown [paths] key(s): {', '.join(sorted(unknown))}; only 'texmf' remains "
            "(builds publish into the artifact folder and exports go to export/)"
        )
    return Config(
        version=version,
        image=image,
        texmf=paths.get("texmf", "texmf"),
        links=_links(raw.get("links") or {}),
        autoload=_package_list(raw.get("packages") or {}, "autoload"),
        require=_package_list(raw.get("packages") or {}, "require"),
        ignore=_ignore_list(raw.get("checks") or {}),
    )


def _ignore_list(raw: dict) -> tuple[str, ...]:
    unknown = set(raw) - {"ignore"}
    if unknown:
        raise ConfigError(f"unknown [checks] key(s): {', '.join(sorted(unknown))}")
    ids = raw.get("ignore", [])
    if not isinstance(ids, list) or not all(isinstance(i, str) and i for i in ids):
        raise ConfigError("[checks].ignore must be a list of check ids")
    from . import constraints

    known = set(SEVERITY) | {f"constraint/{c}" for c in constraints.load()}
    undefined = sorted(set(ids) - known)
    if undefined:
        raise ConfigError(f"[checks].ignore names no known check: {', '.join(undefined)}")
    return tuple(ids)


def _package_list(raw: dict, key: str) -> tuple[str, ...]:
    unknown = set(raw) - {"autoload", "require"}
    if unknown:
        raise ConfigError(f"unknown [packages] key(s): {', '.join(sorted(unknown))}")
    names = raw.get(key, [])
    if not isinstance(names, list) or not all(isinstance(n, str) and n for n in names):
        raise ConfigError(f"[packages].{key} must be a list of non-empty package names")
    return tuple(names)


def add_packages(root: Path, *, autoload: tuple[str, ...] = (), require: tuple[str, ...] = ()) -> bool:
    """Adds names to `[packages]` in `parla/parla.toml` in place, keeping the rest of the file.
    Returns whether the file changed."""
    path = root / PROJECT_DIR / TOML
    cfg = load(root)
    merged = {
        "autoload": (*cfg.autoload, *(n for n in autoload if n not in cfg.autoload)),
        "require": (*cfg.require, *(n for n in require if n not in cfg.require)),
    }
    if merged == {"autoload": cfg.autoload, "require": cfg.require}:
        return False
    lines = [
        f"{key} = [{', '.join(json.dumps(n) for n in names)}]" for key, names in merged.items() if names
    ]
    text = path.read_text(encoding="utf-8")
    if "[packages]" in text:
        text = re.sub(r"^(autoload|require)\s*=\s*\[[^\]]*\]\s*\n", "", text, flags=re.M)
        text = text.replace("[packages]", "[packages]\n" + "\n".join(lines), 1)
    else:
        text = text.rstrip("\n") + "\n\n[packages]\n" + "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")
    return True


def _links(raw: dict) -> dict[str, str]:
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            raise ConfigError(f"[links] {key!r}: key must be a non-empty string")
        if ".." in Path(key).parts or Path(key).is_absolute():
            raise ConfigError(f"[links] {key!r}: key must be a relative path with no '..' part")
        if not isinstance(value, str) or not value:
            raise ConfigError(f"[links] {key!r}: value must be a non-empty string")
    return dict(raw)


def card_path(root: Path, name: str) -> Path:
    return root / PROJECT_DIR / "artifacts" / name / "card.md"


def load_card(root: Path, name: str) -> Card:
    path = card_path(root, name)
    if not path.is_file():
        raise ConfigError(f"artifact '{name}' has no card at {path}")
    try:
        keys, body = frontmatter.split(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    return _card(path, keys, body)


def _card(path: Path, keys: dict, body: str) -> Card:
    missing = [k for k in CARD_REQUIRED if k not in keys]
    if missing:
        raise ConfigError(f"{path}: missing card key(s): {', '.join(missing)}")
    for k in ("modality", "audience", "engine", "entrypoint"):
        if not isinstance(keys[k], str) or not keys[k]:
            raise ConfigError(f"{path}: card key '{k}' must be a non-empty string")
    from .engines import registry  # the registry imports the engines, which import this module

    if keys["engine"] not in registry.ENGINES:
        raise ConfigError(
            f"{path}: unknown engine '{keys['engine']}' (registered: {', '.join(sorted(registry.ENGINES))})"
        )
    absent = [k for k in registry.ENGINES[keys["engine"]].card_keys if k not in keys]
    if absent:
        raise ConfigError(f"{path}: engine '{keys['engine']}' requires card key(s): {', '.join(absent)}")
    if keys["phase"] not in PHASES:
        raise ConfigError(f"{path}: phase must be one of {sorted(PHASES)}, got '{keys['phase']}'")
    entry = Path(keys["entrypoint"])
    if entry.is_absolute() or ".." in entry.parts:
        raise ConfigError(f"{path}: entrypoint must be relative and stay inside the artifact folder")
    derived = keys["derived-from"]
    if derived is not None and not isinstance(derived, str):
        raise ConfigError(f"{path}: derived-from must be an artifact name or null")
    language = keys.get("language", DEFAULT_LANGUAGE)
    translations = keys.get("translations") or {}
    _validate_translations(path, keys["engine"], language, translations)
    traits = keys.get("traits") or {}
    limits = keys.get("limits") or {}
    if not isinstance(traits, dict) or not isinstance(limits, dict):
        raise ConfigError(f"{path}: traits and limits must be mappings")
    return Card(
        modality=keys["modality"],
        audience=keys["audience"],
        engine=keys["engine"],
        entrypoint=keys["entrypoint"],
        phase=keys["phase"],
        derived_from=derived,
        language=language,
        translations=translations,
        traits=traits,
        limits=limits,
        keys=keys,
        body=body,
    )


def _validate_translations(path: Path, engine: str, language: object, translations: object) -> None:
    if not isinstance(language, str) or not LANGUAGE_RE.fullmatch(language):
        raise ConfigError(f"{path}: language must be a lowercase language code such as 'en' or 'pt'")
    if not isinstance(translations, dict):
        raise ConfigError(f"{path}: translations must map a language code to a folder")
    if translations and engine != "latex":
        raise ConfigError(f"{path}: translations are supported by the latex engine only")
    for code, folder in translations.items():
        if not isinstance(code, str) or not LANGUAGE_RE.fullmatch(code) or code == language:
            raise ConfigError(f"{path}: translation '{code}' must be a language code other than '{language}'")
        rel = Path(folder) if isinstance(folder, str) and folder else None
        if rel is None or rel.is_absolute() or ".." in rel.parts or rel == Path("."):
            raise ConfigError(f"{path}: translation '{code}' needs a folder inside the artifact")


def documents(root: Path, name: str) -> list[Document]:
    """The artifact's own document, then one per translation, in card order."""
    main = document(root, name)
    card = load_card(root, name)
    return [
        main,
        *(
            Document(name, f"artifacts/{name}/{folder}/{card.entrypoint}", main.engine, code)
            for code, folder in card.translations.items()
        ),
    ]


def document(root: Path, name: str) -> Document:
    """The LaTeX modules are written against `Document`; this maps a card onto it with the
    entrypoint relative to `parla/`."""
    card = load_card(root, name)
    if card.engine != "latex":
        raise ConfigError(f"artifact '{name}' has engine '{card.engine}', expected 'latex'")
    tex = card.keys.get("latex")
    if tex not in LATEX_ENGINES:
        raise ConfigError(f"artifact '{name}': latex must be one of {sorted(LATEX_ENGINES)}, got '{tex}'")
    return Document(name=name, entrypoint=f"artifacts/{name}/{card.entrypoint}", engine=tex)
