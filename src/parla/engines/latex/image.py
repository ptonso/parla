"""The LaTeX build image: identity, presence check, and local build.

parla does not host an image. The Dockerfile and its build context ship inside this
package; the image is built on the user's machine the first time it is needed and then
lives in the local Docker daemon's image store (there is no separate persistence). See
`specs/docker.md`.

Kept free of `build`/`config`/`template` imports to avoid cycles.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ...names import IMAGE_NAME, NAME

IMAGE_VERSION = "2025.5"  # bump when docker/ or texmf/ changes; matches the frozen TeX Live snapshot
IMAGE_REF = f"{IMAGE_NAME}:{IMAGE_VERSION}"


class ImageError(Exception):
    """Raised when the image build fails or Docker is unreachable."""


def context_dir() -> Path:
    """The `docker build` context: this installed package's directory, which holds
    `docker/` and `texmf/`. (Relies on the wheel being installed unzipped, which hatchling
    does; a zip-import layout would need `importlib.resources.as_file`.)"""
    from importlib.resources import files

    return Path(str(files(NAME)))


def dockerfile() -> Path:
    return context_dir() / "docker" / "Dockerfile"


def image_exists() -> bool:
    try:
        return (
            subprocess.run(
                ["docker", "image", "inspect", IMAGE_REF],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )
    except FileNotFoundError as exc:  # docker not installed
        raise ImageError("docker is not installed or not on PATH") from exc


def build_image(*, no_cache: bool = False, on_output=print) -> None:
    cmd = ["docker", "build", "--tag", IMAGE_REF, "--file", str(dockerfile())]
    if no_cache:
        cmd.append("--no-cache")
    cmd.append(str(context_dir()))
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            on_output(line.rstrip("\n"))
        code = proc.wait()
    if code != 0:
        raise ImageError(f"`docker build` for {IMAGE_REF} failed (exit {code})")


def ensure_image(on_output=print) -> None:
    """Build the image if it is not already present. A no-op on the common path."""
    if image_exists():
        return
    on_output(f"{NAME}: building {IMAGE_REF} (first run; TeX Live install, several minutes)...")
    build_image(on_output=on_output)


def status() -> dict:
    if not image_exists():
        return {"ref": IMAGE_REF, "present": False}
    out = subprocess.run(
        ["docker", "image", "inspect", IMAGE_REF], capture_output=True, text=True
    ).stdout
    data = json.loads(out)[0]
    return {
        "ref": IMAGE_REF,
        "present": True,
        "id": data.get("Id", "")[:19],
        "created": data.get("Created", ""),
        "architecture": data.get("Architecture", ""),
        "size_mb": round(data.get("Size", 0) / 1e6, 1),
    }
