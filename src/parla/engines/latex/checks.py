"""The LaTeX check set: detection only, over the artifact's `\\input` tree. See `specs/checks.md#latex-engine`.

Each check copies the regexes and logic of the texfy-ai post-processing that used to rewrite
the text silently; here every one reports a finding with file and line and changes nothing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ... import config as config_mod
from ...checks import Finding
from ...checks.ids import finding
from ...names import PROJECT_DIR
from . import bib
from .build import _document_tex_texts
from .export import FIGURE_EXTENSIONS, PATH_COMMANDS

_COMMENT_RE = bib._COMMENT_RE
_INPUT_RE = re.compile(r"\\(?:input|include|DiagramSlide)\{([^}]+)\}")

# --- copied from texfy_ai.core.draft.post ----------------------------------------------
_MATH_ENVIRONMENTS = (
    "equation", "align", "gather", "multline", "eqnarray",
    "alignat", "flalign", "math", "displaymath", "split", "cases",
    "array", "aligned", "gathered",
)
# Commands whose braced argument is a structural key/path/url, not prose:
# underscores inside them are literal.
_UNDERSCORE_PROTECTED_COMMANDS = (
    "cite", "citep", "citet", "ref", "eqref", "label",
    "includegraphics", "input", "include", "href", "url",
    "LeftImage", "TopImage", "RightImage", "BottomImage",
    "DiagramSlide",
    "cref", "Cref", "autoref", "pageref", "nameref", "citeauthor", "citeyear",
    "bibliography", "lstinputlisting",
)
# A protected region (math span/environment or a protected command's argument) or a single
# bare underscore. Only the latter is reported.
_UNDERSCORE_ESCAPE_RE = re.compile(
    r"(?P<protected>"
    r"\\\[.*?\\\]|\\\(.*?\\\)|\$\$.*?\$\$|\$[^$]*\$"
    rf"|\\begin\{{(?P<env>(?:{'|'.join(map(re.escape, _MATH_ENVIRONMENTS))})\*?)\}}.*?\\end\{{(?P=env)\}}"
    rf"|\\(?:{'|'.join(_UNDERSCORE_PROTECTED_COMMANDS)})(?:\[[^\]\n]*\])?\{{[^{{}}]*\}}"
    r")|(?P<us>(?<!\\)_)",
    re.DOTALL,
)
_ESCAPED_BRACE_RE = re.compile(r"\\[{}]")
_FLOAT_LABEL_RE = re.compile(r"\\label\{[^}]*\}")
_FLOAT_ENV_BY_LABEL_RE = re.compile(r"\\begin\{(figure|table)\*?\}.*?\\end\{\1\*?\}", re.DOTALL)
# A percent that follows a digit and starts prose comments out the rest of the line.
_PERCENT_PROSE_RE = re.compile(r"(?<!\\)(?<=\d)%[ \t]+[A-Za-z]")


def _normalize_latex_reference_style(text: str) -> str:
    normalized = text
    reference_glue_chars = " Ü"
    # texfy also counted the tie `~` as glue, which would flag the standard `Figure~\\ref`; dropped here.
    glue_pattern = rf"(?:\\,|\\u00[aA]0|\\u00[dD][cC]|[{re.escape(reference_glue_chars)}])"
    normalized = re.sub(r"([(\[{])\s*\\[uU]\s*\\?(ref|cite)\{", r"\1\\\2{", normalized)
    normalized = re.sub(r"(?<=\S)\s*\\[uU]\s*\\?(ref|cite)\{", r" \\\1{", normalized)
    normalized = re.sub(rf"([(\[{{])\s*{glue_pattern}\s*(\\(?:ref|cite)\{{)", r"\1\2", normalized)
    normalized = re.sub(rf"(?<=\S)\s*{glue_pattern}\s*(\\(?:ref|cite)\{{)", r" \1", normalized)
    normalized = re.sub(r"([(\[{])\s*(?:\\+\s*)+(\\(?:ref|cite)\{)", r"\1\2", normalized)
    normalized = re.sub(r"(?<=\S)\s*(?:\\+\s*)+(\\(?:ref|cite)\{)", r" \1", normalized)
    normalized = re.sub(r"Figure\s*~\s*ef\{fig:([A-Za-z0-9:_-]+)\}", r"Figure \\ref{fig:\1}", normalized)
    normalized = re.sub(r"Figure\s+ef\{fig:([A-Za-z0-9:_-]+)\}", r"Figure \\ref{fig:\1}", normalized)
    return normalized


# --- copied from texfy_ai.core.draft.index ---------------------------------------------
_ACRONYM_DEFINITION_RE = re.compile(r"\(([A-Z]{2,6})\)")
_APPENDIX_COMMAND_RE = re.compile(r"^[ \t]*\\appendix[ \t]*\n?", re.MULTILINE)
_SECTIONING_CMD_RE = re.compile(r"\\(section|subsection|subsubsection|paragraph)\*?\{")
_SECTIONING_DEPTH = {"section": 0, "subsection": 1, "subsubsection": 2, "paragraph": 3}

# --- copied from texfy_ai.core.draft.macros --------------------------------------------
_SPLASH_DEFINITION_RE = re.compile(
    r"\\(?:NewDocumentCommand|newcommand|renewcommand|providecommand|DeclareDocumentCommand|def)"
    r"\s*\{?\\SplashSlide\b"
)
_LOAD_RE = re.compile(r"\\(?:usepackage|RequirePackage|input|include)(?:\[[^\]]*\])?\{([^}]+)\}")
_TEX_SUFFIXES = (".sty", ".tex", ".cls")
_SLIDE_MACRO_RE = re.compile(r"\\(SplashSlide|LeftImage|RightImage|TopImage|BottomImage|DiagramSlide)\b")


def entrypoints_load_slide_macros(entrypoints: list[Path], roots: list[Path]) -> bool:
    """Follows `\\usepackage`, `\\RequirePackage` and `\\input` from the entrypoints, resolving
    each name against `roots` by file name, and looks for a `\\SplashSlide` definition."""
    index = {
        path.name: path
        for root in reversed(roots)
        if root.is_dir()
        for path in root.rglob("*")
        if path.suffix in _TEX_SUFFIXES and path.is_file()
    }
    pending, seen = list(entrypoints), set()
    while pending:
        path = pending.pop()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        text = _COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="ignore"))
        if _SPLASH_DEFINITION_RE.search(text):
            return True
        for match in _LOAD_RE.finditer(text):
            for name in match.group(1).split(","):
                name = Path(name.strip()).name
                for candidate in (name, *(f"{name}{suffix}" for suffix in _TEX_SUFFIXES)):
                    if candidate in index:
                        pending.append(index[candidate])
                        break
    return False


# --- copied from texfy_ai.core.summarize.bib_ingest ------------------------------------
def _count_unbraced_commas(value: str) -> int:
    depth = 0
    count = 0
    for char in value:
        if char == "{":
            depth += 1
        elif char == "}" and depth:
            depth -= 1
        elif char == "," and depth == 0:
            count += 1
    return count


def _person_name_problem(entry: bib.Entry) -> str | None:
    """The `validate_bibtex_person_names` verdict for one entry, as a message."""
    structured_field_re = re.compile(r"(?:^|[,\s])(family|given|prefix|suffix|useprefix)\s*=", re.IGNORECASE)
    for field in ("author", "editor"):
        value = entry.fields.get(field, "").strip()
        if not value:
            continue
        if structured_field_re.search(value):
            return (
                f"Invalid BibTeX {field} field for '{entry.key}': BibLaTeX structured-name fragments are not "
                "supported by BibTeX. Re-export this entry as Better BibTeX or use standard BibTeX names."
            )
        for name in re.split(r"\s+and\s+", value, flags=re.IGNORECASE):
            if _count_unbraced_commas(name) > 2:
                return (
                    f"Invalid BibTeX {field} field for '{entry.key}': a person name contains more than two "
                    "unbraced commas. Re-export this entry as Better BibTeX or use a standard BibTeX name."
                )
    return None


# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Source:
    """One file of the artifact's `\\input` tree. `stripped` keeps every newline of `text`, so a
    line number found in one is the line number in the other."""

    file: str  # relative to parla/
    text: str
    stripped: str

    def line(self, offset: int) -> int:
        return self.stripped.count("\n", 0, offset) + 1


def _strip(text: str) -> str:
    return "\n".join(_COMMENT_RE.sub("", line) for line in text.splitlines())


def sources(root: Path, artifact: str, entrypoint: str) -> list[Source]:
    """The entrypoint and every file it reaches inside the artifact folder."""
    own = f"artifacts/{artifact}/"
    texts = _document_tex_texts((root / PROJECT_DIR).resolve(), entrypoint)
    return [Source(rel, text, _strip(text)) for rel, text in texts if rel.startswith(own)]


def reading_order(root: Path, entrypoint: str) -> list[tuple[str, int, str]]:
    """`(file, line, comment-stripped line)` in the order TeX reads them: each `\\input` is
    expanded where it stands."""
    base = (root / PROJECT_DIR).resolve()
    out: list[tuple[str, int, str]] = []

    def walk(rel: Path, seen: tuple[Path, ...]) -> None:
        if rel.suffix == "":
            rel = rel.with_suffix(".tex")
        path = base / rel
        if rel in seen or not path.is_file():
            return
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = _COMMENT_RE.sub("", line)
            out.append((rel.as_posix(), number, code))
            for m in _INPUT_RE.finditer(code):
                walk(Path(m.group(1).strip()), (*seen, rel))

    walk(Path(entrypoint), ())
    return out


def _cite_occurrences(srcs: list[Source]) -> list[tuple[str, str, int]]:
    """`(key, file, line)` for every key of every `\\cite`-family command."""
    return [
        (key, s.file, s.line(m.start()))
        for s in srcs
        for m in bib._CITE_RE.finditer(s.stripped)
        for key in bib._split_keys(m.group(1))
    ]


def _cite_findings(root: Path, srcs: list[Source]) -> list[Finding]:
    """`cite-unresolved` and `bib-name-syntax`, resolved as the overlay resolves. Only the
    first citation of each key is reported."""
    occurrences = _cite_occurrences(srcs)
    library = bib.load_library(library_bib=config_mod.library_bib(), library_json=config_mod.library_json())
    extras = bib.load_extras(root / PROJECT_DIR / "sources" / "bib")
    result = bib.resolve([key for key, _, _ in occurrences], library=library, extras=extras)
    findings: list[Finding] = []
    for key, file, line in dict((o[0], o) for o in reversed(occurrences)).values():
        if key in result.unresolved:
            findings.append(
                finding("cite-unresolved", file, line,
                        f"citekey '{key}' is in neither the Zotero library nor {PROJECT_DIR}/sources/bib/*.bib")
            )
        elif (problem := _person_name_problem(result.entries[key])) is not None:
            findings.append(finding("bib-name-syntax", file, line, problem))
    return findings


def _path_findings(root: Path, srcs: list[Source]) -> list[Finding]:
    """`figure-missing`: an `\\input` or figure path that does not exist. Paths under `sources/`
    belong to the shared `source-missing` check; bare names resolve through the texmf trees."""
    base = root / PROJECT_DIR
    commands = "|".join(c for c in PATH_COMMANDS if c not in ("bibliography", "addbibresource"))
    path_re = re.compile(rf"\\(?:{commands})(?:\[[^\]]*\])?\{{([^}}]+)\}}")
    findings: list[Finding] = []
    for s in srcs:
        for m in path_re.finditer(s.stripped):
            target = m.group(1).strip()
            if target.startswith("sources/") or "/" not in target:
                continue
            path = base / target
            if not (path.is_file() or path.with_name(path.name + ".tex").is_file()
                    or any(path.with_name(path.name + ext).is_file() for ext in FIGURE_EXTENSIONS)):
                findings.append(finding("figure-missing", s.file, s.line(m.start()), f"{target} does not exist"))
    return findings


def _text_findings(srcs: list[Source]) -> list[Finding]:
    findings: list[Finding] = []
    for s in srcs:
        for m in _UNDERSCORE_ESCAPE_RE.finditer(s.stripped):
            if m.group("us") is not None:
                findings.append(finding("unescaped-char", s.file, s.line(m.start()), "unescaped `_` outside math; write `\\_`"))
        for m in _PERCENT_PROSE_RE.finditer(s.text):
            line = s.text.count("\n", 0, m.start()) + 1
            findings.append(finding("unescaped-char", s.file, line, "unescaped `%` starts a comment and drops the rest of the line; write `\\%`"))
        findings += _brace_findings(s)
        for number, (old, new) in enumerate(zip(s.stripped.splitlines(), _normalize_latex_reference_style(s.stripped).splitlines(), strict=False), 1):
            if old != new:
                findings.append(finding("cite-style", s.file, number, f"reference spacing or form off the house style; write `{new.strip()}`"))
        for m in re.finditer(r"%TODO[^\n]*", s.text):
            findings.append(finding("todo-marker", s.file, s.text.count("\n", 0, m.start()) + 1, m.group(0).strip()))
    return findings


def _brace_findings(s: Source) -> list[Finding]:
    scrubbed = _ESCAPED_BRACE_RE.sub("", s.stripped)
    depth = 0
    for index, char in enumerate(scrubbed):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                context = scrubbed[max(0, index - 40) : index + 1]
                return [finding("brace-unbalanced", s.file, s.line(index), f"unmatched closing brace near: ...{context!r}")]
    if depth != 0:
        return [finding("brace-unbalanced", s.file, 1, f"{depth} unclosed `{{` brace(s)")]
    return []


def _structure_findings(root: Path, artifact: str, entrypoint: str, srcs: list[Source]) -> list[Finding]:
    findings: list[Finding] = []
    combined = [(s, m) for s in srcs for m in re.finditer(r"\\label\{([^{}]+)\}", s.stripped)]
    labels = {m.group(1) for _, m in combined}
    seen_refs: set[str] = set()
    for s in srcs:
        for m in re.finditer(r"\\(?:ref|eqref)\{([^{}]+)\}", s.stripped):
            key = m.group(1)
            if key not in labels and key not in seen_refs:
                seen_refs.add(key)
                findings.append(finding("ref-dangling", s.file, s.line(m.start()), f"no \\label{{{key}}} found"))

    counts: dict[str, int] = {}
    for s in srcs:
        for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", s.stripped):
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
            if counts[m.group(1)] == 2:
                findings.append(finding("figure-duplicate", s.file, s.line(m.start()), f"figure '{m.group(1)}' is included more than once"))

    acronyms: dict[str, int] = {}
    for s in srcs:
        for m in _ACRONYM_DEFINITION_RE.finditer(s.stripped):
            acronyms[m.group(1)] = acronyms.get(m.group(1), 0) + 1
            if acronyms[m.group(1)] == 2:
                findings.append(finding("abbreviation-repeated", s.file, s.line(m.start()), f"abbreviation '{m.group(1)}' looks introduced more than once"))

    findings += _float_findings(root, entrypoint)
    findings += _appendix_findings(root, entrypoint, srcs)
    return findings


def _float_findings(root: Path, entrypoint: str) -> list[Finding]:
    """`float-unreferenced` and `float-order`, in the order TeX reads the files."""
    lines = reading_order(root, entrypoint)
    floats: list[tuple[str, str, int, int]] = []  # label, file, line, reading position
    open_float: tuple[str, int, int] | None = None
    refs: dict[str, int] = {}
    for position, (file, number, code) in enumerate(lines):
        if open_float is None and (m := re.search(r"\\begin\{(figure|table)\*?\}", code)):
            open_float = (file, number, position)
        if open_float is not None:
            for m in _FLOAT_LABEL_RE.finditer(code):
                floats.append((m.group(0)[len("\\label{"):-1], *open_float))
            if re.search(r"\\end\{(figure|table)\*?\}", code):
                open_float = None
        for m in re.finditer(r"\\(?:ref|autoref|cref|Cref|vref|pageref)\*?\{([^}]+)\}", code):
            for key in m.group(1).split(","):
                refs.setdefault(key.strip(), position)
    findings: list[Finding] = []
    for label, file, number, position in floats:
        if label not in refs:
            findings.append(finding("float-unreferenced", file, number, f"no text references '{label}'"))
        elif refs[label] > position:
            findings.append(finding("float-order", file, number, f"'{label}' appears before its first reference"))
    return findings


def _appendix_findings(root: Path, entrypoint: str, srcs: list[Source]) -> list[Finding]:
    """A section included after `\\appendix` must start at `\\section`; `\\appendix` belongs in the entrypoint."""
    findings: list[Finding] = []
    for s in srcs:
        if s.file != entrypoint:
            for m in _APPENDIX_COMMAND_RE.finditer(s.stripped):
                findings.append(finding("appendix-structure", s.file, s.line(m.start()), "stray \\appendix; it belongs in the entrypoint"))
    after_appendix = False
    checked: set[str] = set()
    for file, _, code in reading_order(root, entrypoint):
        if file == entrypoint and re.search(r"\\appendix\b", code):
            after_appendix = True
        elif after_appendix and file != entrypoint and file not in checked:
            checked.add(file)
            src = next((s for s in srcs if s.file == file), None)
            if src is None:
                continue
            depths = [_SECTIONING_DEPTH[m.group(1)] for m in _SECTIONING_CMD_RE.finditer(src.stripped)]
            if depths and min(depths) > 0:
                findings.append(finding("appendix-structure", file, 1, "an appendix section must start at \\section; its shallowest heading is deeper"))
    return findings


def _macro_findings(root: Path, entrypoint: str, srcs: list[Source]) -> list[Finding]:
    uses = [(s, m) for s in srcs for m in _SLIDE_MACRO_RE.finditer(s.stripped)]
    if not uses:
        return []
    base = root / PROJECT_DIR
    cfg = config_mod.load(root)
    home = config_mod.texmf_home()
    roots = [base, base / cfg.texmf, *([home] if home is not None else [])]
    if entrypoints_load_slide_macros([base / entrypoint], roots):
        return []
    s, m = uses[0]
    return [finding("macro-missing", s.file, s.line(m.start()), f"\\{m.group(1)} is used but no loaded package defines the slide macros")]


_STRUCTURE_RE = re.compile(r"\\(?:section|cventry|cvline|item|input)\b")
def _tree(root: Path, entrypoint: str, folder: str) -> dict[str, str]:
    """Path relative to `folder` -> the sequence of structural commands, for every file the
    entrypoint reaches inside `folder`."""
    texts = _document_tex_texts((root / PROJECT_DIR).resolve(), entrypoint)
    return {
        Path(rel).relative_to(folder).as_posix(): " ".join(m.group(0) for m in _STRUCTURE_RE.finditer(text))
        for rel, text in texts
        if rel.startswith(f"{folder}/")
    }


def translation_parity(root: Path, artifact: str) -> list[Finding]:
    """Every translation reaches the same files as the artifact's own entrypoint, and each file
    holds the same sections, entries, lines and bullets in the same order."""
    card = config_mod.load_card(root, artifact)
    main, *others = config_mod.documents(root, artifact)
    home = f"artifacts/{artifact}"
    own = {
        k: v for k, v in _tree(root, main.entrypoint, home).items()
        if not any(k.startswith(f"{folder}/") for folder in card.translations.values())
    }
    findings: list[Finding] = []
    for doc in others:
        folder = f"{home}/{card.translations[doc.tag]}"
        other = _tree(root, doc.entrypoint, folder)
        for path in sorted(own.keys() | other.keys()):
            if path not in other:
                findings.append(finding("translation-parity", folder, 1, f"{path} is not reached in the '{doc.tag}' translation"))
            elif path not in own:
                findings.append(finding("translation-parity", f"{folder}/{path}", 1, f"{path} has no counterpart in the '{card.language}' version"))
            elif own[path] != other[path]:
                findings.append(finding("translation-parity", f"{folder}/{path}", 1, f"structure differs from {path} in the '{card.language}' version"))
    return findings


def check(root: Path, artifact: str) -> list[Finding]:
    findings: list[Finding] = []
    for doc in config_mod.documents(root, artifact):
        srcs = sources(root, artifact, doc.entrypoint)
        findings += [
            *_cite_findings(root, srcs),
            *_path_findings(root, srcs),
            *_text_findings(srcs),
            *_structure_findings(root, artifact, doc.entrypoint, srcs),
            *_macro_findings(root, doc.entrypoint, srcs),
        ]
    return [*dict.fromkeys(findings), *translation_parity(root, artifact)]


_OVERFULL_H_RE = re.compile(r"Overfull \\hbox \(([\d.]+)pt too wide\) in paragraph at lines (\d+)--\d+")
_OVERFULL_V_RE = re.compile(r"Overfull \\vbox \(([\d.]+)pt too high\)")
_PAGE_RE = re.compile(r"\[(\d+)\]")
OVERFULL_LINE_MIN = 5.0


def log_findings(log: str, entrypoint: str) -> list[Finding]:
    """`frame-overflow` and `overfull-line` read from the engine log of one document. Lines are
    attributed to the entrypoint, since the log does not name the file reliably."""
    beamer = "Document Class: beamer" in log
    findings: list[Finding] = []
    for number, line in enumerate(log.splitlines()):
        if (m := _OVERFULL_H_RE.search(line)) and float(m.group(1)) > OVERFULL_LINE_MIN:
            findings.append(finding("overfull-line", entrypoint, int(m.group(2)), f"a line overfills its box by {m.group(1)}pt"))
        elif beamer and (m := _OVERFULL_V_RE.search(line)) and float(m.group(1)) > 0:
            tail = " ".join(log.splitlines()[number : number + 4])
            page = _PAGE_RE.search(tail)
            where = f" on page {page.group(1)}" if page else ""
            findings.append(finding("frame-overflow", entrypoint, 1, f"a frame overflows the page by {m.group(1)}pt{where}"))
    return findings
