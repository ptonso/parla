---
kind: engine
engine: latex
---
## facts

- Write paths relative to `parla/`, as in `\input{artifacts/<name>/section/introduction}` and `\includegraphics{sources/results/fig.png}`. There is no `\graphicspath`.
- Cite with `\cite{key}`. `artifacts/<name>/references.bib` is generated at every build from the library and `sources/bib/`, so never edit it.
- A table is a file at `artifacts/<name>/table/<id>.tex` that `parla tool table` writes, and the text `\input`s it.
- Keep `\label{parla:body-end}` after the last body line of a paper or CV. `parla tool measure --pages` reads it to find the body pages.
- `parla check` runs before every build, and an error finding stops the build. Fix the source and build again.
