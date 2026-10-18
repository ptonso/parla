# parla-texlive image: Layer 1 (TeX Live + manifest packages) and Layer 2 (shared texmf/).
# Built locally by `parla image build` from the copy of this directory that ships in the
# wheel. Reproducible: pinned to a frozen TeX Live snapshot, no `tlmgr update`.
# Arch-independent: install-tl picks the host-platform binary; a `bin/default` symlink and
# `tlmgr path add` (after the manifest install) put every tool on PATH.
#
# Collections: scheme-small + basic/latex/latexrecommended/xetex.

FROM debian:bookworm-slim

# Frozen TeX Live 2025 net-install tree. Bump deliberately when a new frozen snapshot ships.
ARG TEXLIVE_MIRROR=https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2025/tlnet-final
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/usr/local/texlive/bin/default:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates perl libalgorithm-diff-perl tar gzip fontconfig gpg \
    && rm -rf /var/lib/apt/lists/*

# Layer 1 - install TeX Live from a baked profile, then the explicit package manifest.
COPY docker/tl.profile /tmp/tl.profile
COPY docker/tl-packages.txt /tmp/tl-packages.txt
RUN set -eux; \
    cd /tmp; \
    curl -fsSL "${TEXLIVE_MIRROR}/install-tl-unx.tar.gz" -o install-tl.tar.gz; \
    mkdir install-tl; \
    tar -xzf install-tl.tar.gz -C install-tl --strip-components=1; \
    ./install-tl/install-tl --profile=/tmp/tl.profile --location "${TEXLIVE_MIRROR}"; \
    ln -sfn "$(basename "$(dirname "$(echo /usr/local/texlive/bin/*/tlmgr)")")" /usr/local/texlive/bin/default; \
    tlmgr option repo "${TEXLIVE_MIRROR}"; \
    xargs tlmgr install < /tmp/tl-packages.txt; \
    tlmgr path add; \
    rm -rf /tmp/install-tl /tmp/install-tl.tar.gz /tmp/tl.profile /tmp/tl-packages.txt

# Layer 2 - bake redistributable template packages into TEXMFLOCAL, then refresh the db.
COPY texmf/ /usr/local/texlive/texmf-local/
RUN mktexlsr

# rsvg-convert: renders a diagram's laid-out SVG to PDF (engines/svg/build.py); the fontconfig
# entry below lets it find TeX Live's Latin Modern, the font the SVG checks measure with.
# pdftoppm (poppler-utils): rasterizes a standalone-rendered formula to PNG
# (tools/formula.py), so a diagram can embed it like a real photo. A separate,
# later RUN so bumping either never invalidates the slow TeX Live install layer above.
RUN apt-get update && apt-get install -y --no-install-recommends librsvg2-bin poppler-utils \
    && rm -rf /var/lib/apt/lists/*
RUN printf '%s' '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>/usr/local/texlive/texmf-dist/fonts/opentype/public/lm</dir></fontconfig>' \
        > /etc/fonts/conf.d/60-texlive-lm.conf && fc-cache -f

WORKDIR /workspace/parla
