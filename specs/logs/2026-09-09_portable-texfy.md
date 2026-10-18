# Portable texfy: contained by default, local image build

**Affects**: [architecture](../architecture.md), [cli](../cli.md), [config](../config.md), [docker](../docker.md), [template](../template.md).

## Situation

`texfy` was wired to one machine. It read a personal `config.toml` through a path that exists only in a source checkout, `texfy init` demanded an asset-store layout, the build image was `ghcr.io/ptonso/texfy-texlive`, and a personal Beamer theme lived in the repo's Layer 2. None of it survived a `pip install`.

## Alternatives considered

- **Publish the image to a registry.** Ties every user to one author's registry account and to hosted-image upkeep.
- **Keep a repo-level config file.** Unreachable from an installed wheel.
- **Bake the personal texmf into the image.** Not redistributable, and machine-specific.

## Decision

Contained by default; wiring through an optional user config (`~/.config/texfy/config.toml`, with a commented example shipped and never an active one). The image builds locally from a context shipped in the wheel, on first use, from a frozen TeX Live snapshot with an arch-independent Dockerfile. The personal texmf leaves the repo and returns through `[storage].texmf_home`. The repo is MIT with `THIRD-PARTY.md`. It is not on PyPI: `scripts/install.sh` builds a `texfy` wheel and `pipx install`s `texfy-ai` against it. Designs: [config](../config.md#user-config), [docker](../docker.md), [template](../template.md#storage-modes).

## What tipped it

A user with no asset store and no Zotero must still get a working `texfy init` and `texfy build` from a clean install.

## Trade-offs accepted

First build costs a TeX Live download. A wired author must supply personal packages through config. The local-build path and the arch-independent Dockerfile have not yet been verified end to end on a clean machine; that remaining work was a texfy delta, carried into the parla image build.
