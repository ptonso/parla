import re
from pathlib import Path

NAME = "parla"
ENV_PREFIX = NAME.upper()
IMAGE_NAME = f"{NAME}-texlive"
CONFIG_DIR_NAME = NAME
PROJECT_DIR = NAME
TOML = f"{NAME}.toml"
STATE_DIR = f".{NAME}"
BODY_END_LABEL = f"{NAME}:body-end"
BUILD_DIR = f"{STATE_DIR}/build"
EXPORT_DIR = "export"
BUILD_ERROR = "BUILD-ERROR.txt"
OUTPUT_SUFFIXES = (".pdf", ".png", "_diff.pdf", "_diff.png")


def is_output(rel: Path) -> bool:
    """Whether `rel`, a path relative to `parla/`, is a file a build writes into an artifact folder: the
    published PDFs and PNGs, `BUILD-ERROR.txt` and the generated `references.bib`."""
    parts = rel.parts
    if len(parts) != 3 or parts[0] != "artifacts":
        return False
    suffixes = "|".join(re.escape(s) for s in OUTPUT_SUFFIXES)
    return parts[2] in (BUILD_ERROR, "references.bib") or re.fullmatch(rf"{re.escape(parts[1])}(-[a-z]{{2,3}})?({suffixes})", parts[2]) is not None
