# CV modality

**Affects**: [template](../template.md), [docker](../docker.md), [guides](../guides.md).

## Situation

The author needs a CV for each kind of employer, starting with deep learning, reinforcement learning and computer vision research and development companies. A CV is close to a paper (LaTeX source, a page budget, one reader to persuade) but it has a fixed layout vocabulary of its own: header, entries with dates, bullets, labelled skill lines.

## Alternatives considered

- **No engine change, a CV as a paper with a class.** The paper starter assumes a bibliography and sections of prose, and the author would rewrite the layout in every artifact.
- **A third-party CV class.** Each one brings its own commands and fonts, and the default starter must compile against a bare image.
- **The package in the author's `texmf_home`.** It keeps the style personal, but the stock starter would not compile for anyone else, and the contract requires that it does.
- **One modality per audience.** The audiences differ only in selection, order and wording, so they are audience pages.

## Decision

`cv` is a modality on the `latex` engine. Its stock template loads `parlacv`, a first-party single-column package in Layer 2 with five commands (`\cvheader`, `\cvsep`, `\cvlink`, `\cventry`, `\cvline`) and a `cvitems` environment. The package ships with a public engine page that documents the commands. The modality page, the audience pages and the topics of how to write a CV live in the private guide root, since they hold the author's style. A set of CVs is one artifact per audience, derived from the closest existing one.

## What tipped it

The layout stays identical across audiences, so one package serves all of them, and the guides carry what varies.

## Trade-offs accepted

- Adding the package changed the image, so `IMAGE_VERSION` moved to `2025.4` and existing users rebuild once (cached layers keep it fast).
- The package avoids icons and tables so parsers read it linearly, which limits the visual design.
