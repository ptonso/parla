---
kind: engine
engine: cv
---
## facts

- The starter is `article` at `10pt` with `geometry` margins and `hyperref`, and the page-level styling lives in `parla/texmf/tex/latex/project/project.sty`.
- Write the header as a centered block: the name large and bold, then the headline and the contact line, with links through `\href{url}{text}`.
- Write a job, degree or project as a bold role with its dates on the same line, the organization and place below it in italics, and a `itemize` with one `\item` per bullet.
- Write a labelled line such as `Languages: Python, C++` with `\textbf{label:}`, for skills and other short lists.
- One file per section under `artifacts/<name>/section/`, each starting with `\section{Title}` and `\input` by `main.tex`; a section the audience drops is removed from `main.tex`, and a new one is a new file.
- Keep the layout single-column plain text: no icons, images, tables or text boxes, so applicant-tracking parsers read it in order.
