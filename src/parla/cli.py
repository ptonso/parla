"""argparse router: one handler per command. Commands that depend on the artifact's format
go through the router, so no handler names an engine. Exit codes: see `specs/cli.md#exit-codes`."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import config as config_mod
from . import casebook, constraints, jobs, router, settings, template
from .checks import CheckFailed, Finding
from .engines.base import BuildError, EngineError
from .engines.latex import image as image_mod
from .engines.latex import links as links_mod
from .guides import edit, lint, pages, show
from .tools import claims, formula, measure, source, table
from .tools.formula import FormulaError
from .tools.source import SourceError
from .tools.table import TableError
from .names import CONFIG_DIR_NAME, NAME, PROJECT_DIR

EXIT_CHECK, EXIT_BUILD, EXIT_OTHER, EXIT_SUITE = 1, 2, 3, 4

CONSTRAINT_FIELDS = """JSON on standard input.
  regex:  {"id": "no-emdash", "kind": "regex", "description": "...", "regex": "...", "flags": "i",
           "severity": "error", "hint": false, "applies": {"modality": ["paper"], "files": ["abstract/*.tex"]},
           "examples": {"match": ["a sentence it must hit"], "ok": ["a near miss it must not hit"]}, "origin": "..."}
  probe:  {"id": "cite-grounded", "kind": "probe", "locator": "citation", "description": "the question", "severity": "error"}
  locators: citation, number, caption, paragraph, frame. applies keys: modality, engine, audience, files (globs)."""

CASE_FIELDS = """JSON on standard input: {"artifact": "...", "part": "...", "topics": ["flow"], "hook": "the situation in one line",
"problem": "...", "before": "...", "after": "...", "lesson": "one line about the quality"}"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=NAME, description="Agent-first tool for papers, slides, posts and diagrams")
    sub = parser.add_subparsers(dest="command", required=True)

    modalities, audiences = pages.names("modality"), pages.names("audience")
    searched = ", ".join(str(r) for r in pages.roots().values())
    found = lambda names, kind: ", ".join(names) or f"none found: add {kind} pages to the guides ({searched})"  # noqa: E731
    p_init = sub.add_parser(
        "init",
        help=f"create the base {PROJECT_DIR}/ layout, or add an artifact",
        epilog=(
            f"add an artifact: {NAME} init artifact <name> --modality <m> [--audience <a>]\n"
            f"  modalities: {found(modalities, 'modality')}\n  audiences: {found(audiences, 'audience')}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_init.add_argument("--force", action="store_true", help="overwrite template files")
    p_init.add_argument("--local", action="store_true", help=f"keep {PROJECT_DIR}/ a real directory even when [storage].asset_root is set")
    init_sub = p_init.add_subparsers(dest="init_target")
    p_art = init_sub.add_parser("artifact", help="add an artifact: its card and the engine's starter files")
    p_art.add_argument("name")
    p_art.add_argument("--modality", required=True, choices=modalities or None, metavar="MODALITY", help=f"the kind of artifact: {found(modalities, 'modality')}")
    p_art.add_argument("--audience", default="default", choices=audiences or None, metavar="AUDIENCE", help=f"the readership (default: default): {found(audiences, 'audience')}")
    p_art.add_argument("--force", action="store_true", help="overwrite existing files")

    p_config = sub.add_parser("config", help=f"inspect / create the user config (~/.config/{CONFIG_DIR_NAME}/config.toml)")
    p_config.add_argument("action", choices=["path", "init", "edit", "show"])
    p_config.add_argument("--force", action="store_true", help="config init: overwrite an existing file")

    p_image = sub.add_parser("image", help="the local Docker image")
    p_image.add_argument("action", choices=["build", "status"])
    p_image.add_argument("--force", action="store_true", help="image build: --no-cache")

    sub.add_parser("list", help="the artifacts of the project with their modality, audience and phase")

    p_check = sub.add_parser("check", help="run the artifact's static checks and the constraints")
    p_check.add_argument("artifact")
    p_check.add_argument("--all", action="store_true", help="cover the whole artifact, not the lines changed in the job")
    p_check.add_argument("--resolve", metavar="KEY", help="record a verdict for the finding with this key")
    verdict = p_check.add_mutually_exclusive_group()
    verdict.add_argument("--pass", dest="verdict_pass", action="store_true", help="the span satisfies the question (needs --evidence)")
    verdict.add_argument("--na", action="store_true", help="the finding does not apply (needs --why)")
    p_check.add_argument("--evidence", help="a quoted line of the source that proves --pass")
    p_check.add_argument("--why", help="the reason for --na")

    p_build = sub.add_parser("build", help="check, build, publish and diff an artifact")
    p_build.add_argument("artifact")
    p_build.add_argument("--watch", action="store_true", help="rebuild on every change")
    p_build.add_argument("--diff-from", metavar="PATH|GIT-REF", help="diff baseline (default: the active job's snapshot)")
    p_build.add_argument("--no-diff", action="store_true", help="skip the diff")
    p_build.add_argument("--all", action="store_true", help="cover the whole artifact with the constraints")

    sub.add_parser("link", help=f"sync {PROJECT_DIR}/sources/ with the [links] table")

    p_export = sub.add_parser("export", help="package an artifact into a standalone snapshot")
    p_export.add_argument("artifact")
    p_export.add_argument("--tag", required=True, help="snapshot label, e.g. arxiv-v2 (normalized to lowercase kebab-case)")
    p_export.add_argument("--force", action="store_true", help="overwrite an existing snapshot with the same tag")

    p_job = sub.add_parser("job", help="a snapshot of the artifact for one piece of work")
    job_sub = p_job.add_subparsers(dest="job_command", required=True)
    p_start = job_sub.add_parser("start", help="snapshot the artifact; the snapshot is the diff baseline")
    p_start.add_argument("artifact")
    p_start.add_argument("--part", help="the part of the artifact the job works on")
    p_start.add_argument("--topics", metavar="T,...", help="the style topics the job loads, comma-separated")
    job_sub.add_parser("end", help="close the job and list the changed files").add_argument("artifact")
    job_sub.add_parser("revert", help="restore the artifact from the snapshot").add_argument("artifact")

    p_tool = sub.add_parser("tool", help="deterministic tools for the agent")
    tool_sub = p_tool.add_subparsers(dest="tool_command", required=True)
    p_measure = tool_sub.add_parser("measure", help="words per file and body pages")
    p_measure.add_argument("artifact")
    p_measure.add_argument("--words", action="store_true")
    p_measure.add_argument("--pages", action="store_true")
    p_measure.add_argument("--language", help="a translation's language code; default: every language of the card")
    p_table = tool_sub.add_parser("table", help="parse, fit and render a table")
    p_table.add_argument("artifact")
    p_table.add_argument("source", help=f"a .csv, .tsv, .md, .json or .tex file, relative to {PROJECT_DIR}/")
    p_table.add_argument("--id")
    p_table.add_argument("--max-width", type=int)
    p_table.add_argument("--max-rows", type=int)
    p_table.add_argument("--font-step")
    p_formula = tool_sub.add_parser("formula", help="render a formula as a PNG")
    p_formula.add_argument("artifact")
    p_formula.add_argument("tex")
    p_formula.add_argument("--display", action="store_true")
    p_source = tool_sub.add_parser("source", help="text of a cited PDF, by section")
    p_source.add_argument("citekey")
    p_source.add_argument("--section")
    p_source.add_argument("--pages", metavar="A-B")
    tool_sub.add_parser("claims", help="each citation with its sentence and paragraph").add_argument("artifact")

    p_guide = sub.add_parser("guide", help="the guides: stable principles")
    guide_sub = p_guide.add_subparsers(dest="guide_command", required=True)
    p_show = guide_sub.add_parser("show", help="the guides and cases for the part about to be touched")
    p_show.add_argument("artifact", nargs="?")
    p_show.add_argument("part", nargs="?", help="a part of the modality, or a topic")
    p_show.add_argument("--outline", action="store_true", help="page names and word counts, no bodies")
    p_show.add_argument("--unformatted", action="store_true", help="the Markdown of the files: ids, origins, full cases")
    p_show.add_argument("--topics", metavar="T,...", help="the topics to load (default: the active job's, then the part's)")
    for kind in ("topic", "move", "procedure"):
        p_show.add_argument(f"--{kind}", metavar=kind.upper(), help=f"print one {kind} page, merged")
    p_add = guide_sub.add_parser("add", help="write a rule to the private root or a card")
    p_add.add_argument("page")
    p_add.add_argument("rule_id")
    p_add.add_argument("--text", required=True)
    p_add.add_argument("--origin")
    p_add.add_argument("--overrides", metavar="RULE-ID")
    p_add.add_argument("--evidence", metavar="CASE-IDS", help="comma-separated case ids; marks them distilled")
    p_add.add_argument("--card", metavar="ARTIFACT", help="write to the card's rules instead")
    p_add.add_argument("--section", default="principles", help="the page section (an audience page uses a topic)")
    p_add.add_argument("--hook", help="one line that says when a new topic page applies")
    p_move = guide_sub.add_parser("move", help="move a rule to another page")
    p_move.add_argument("rule_id")
    p_move.add_argument("page")
    guide_sub.add_parser("drop", help="remove a private rule; its text goes to the history").add_argument("rule_id")
    p_edit = guide_sub.add_parser("edit", help="rewrite the text of a private rule in place")
    p_edit.add_argument("rule_id")
    p_edit.add_argument("--text", required=True)
    p_edit.add_argument("--evidence", metavar="CASE-IDS", help="comma-separated case ids; marks them distilled")
    p_glist = guide_sub.add_parser("list", help="the pages of the guides, optionally of one kind")
    p_glist.add_argument("kind", nargs="?", choices=[*pages.KINDS, "trait"])
    p_glist.add_argument("--artifact", help="list topic: the artifact whose sizes and budget to show")
    p_glist.add_argument("--part", help="list topic: the part of the artifact")
    guide_sub.add_parser("lint", help="structure, origins, links and budget of the guides")

    p_case = sub.add_parser("case", help="the casebook: approved corrections")
    case_sub = p_case.add_subparsers(dest="case_command", required=True)
    case_sub.add_parser(
        "add", help="append a case read from standard input", formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=CASE_FIELDS,
    )
    case_sub.add_parser("edit", help="update the hook, lesson, problem or topics of a case, read as JSON from standard input").add_argument("id")
    p_cshow = case_sub.add_parser("show", help="print cases in full and log their use")
    p_cshow.add_argument("ids", help="comma-separated case ids")
    p_cshow.add_argument("--artifact", default="", help="the artifact the cases are read for")
    p_list = case_sub.add_parser("list", help="list cases")
    p_list.add_argument("--topic")
    p_list.add_argument("--status")
    p_mark = case_sub.add_parser("mark", help="change a case's status")
    p_mark.add_argument("id")
    p_mark.add_argument("status")
    case_sub.add_parser("lint", help="groups ready to distill and stale cases")

    p_con = sub.add_parser("constraint", help="constraints: regex checks and probes that run in check and build")
    con_sub = p_con.add_subparsers(dest="constraint_command", required=True)
    con_sub.add_parser(
        "add", help="append a constraint read from standard input", formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=CONSTRAINT_FIELDS,
    )
    p_clist = con_sub.add_parser("list", help="list constraints")
    p_clist.add_argument("--kind", choices=constraints.KINDS)
    p_clist.add_argument("--status", choices=constraints.STATUSES)
    con_sub.add_parser(
        "edit", help="update fields of a private constraint, read as JSON from standard input",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog="JSON with any field of `constraint add` except id and kind, such as regex, examples, applies, severity or description.",
    ).add_argument("id")
    p_cmark = con_sub.add_parser("mark", help="change a constraint's status")
    p_cmark.add_argument("id")
    p_cmark.add_argument("status")
    con_sub.add_parser("lint", help="examples that fail and constraints to refine")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    given = sys.argv[1:] if argv is None else argv
    if given[:1] == ["init"] and len(given) > 1 and given[1] in pages.names("modality"):
        parser.error(
            f"'{given[1]}' is a modality, not a command. Add an artifact with: "
            f"{NAME} init artifact <name> --modality {given[1]} [--audience <audience>]"
        )
    args = parser.parse_args(argv)
    cwd = Path.cwd()
    try:
        if args.command == "init":
            if args.init_target == "artifact":
                return _init_artifact(config_mod.find_root(cwd), args)
            return _init(cwd, args.force, args.local)
        if args.command == "config":
            return _config(args.action, args.force)
        if args.command == "image":
            return _image(args.action, args.force)
        root = config_mod.find_root(cwd)
        if args.command == "tool":
            return _tool(root, args)
        if args.command == "list":
            return _list(root)
        if args.command == "check":
            return _check(root, args)
        if args.command == "build":
            return _build(root, args)
        if args.command == "link":
            return _link(root)
        if args.command == "export":
            return _export(root, args.artifact, args.tag, args.force)
        if args.command == "job":
            return _job(root, args)
        if args.command == "guide":
            return _guide(root, args)
        if args.command == "case":
            return _case(root, args)
        if args.command == "constraint":
            return _constraint(root, args)
        raise AssertionError(args.command)
    except CheckFailed as exc:
        errors = sum(f.severity == "error" for f in exc.findings)
        print(f"{NAME}: {errors} check error(s); nothing was built", file=sys.stderr)
        return EXIT_CHECK
    except BuildError as exc:
        print(f"{NAME}: {exc}", file=sys.stderr)
        return EXIT_BUILD
    except (
        config_mod.ConfigError,
        EngineError,
        image_mod.ImageError,
        links_mod.LinkError,
        jobs.JobError,
        pages.GuideError,
        FormulaError,
        SourceError,
        TableError,
        casebook.CaseError,
        constraints.ConstraintError,
        FileExistsError,
    ) as exc:
        print(f"{NAME}: {exc}", file=sys.stderr)
        return EXIT_OTHER


def _init(root: Path, force: bool, local: bool) -> int:
    written = template.init(root, force=force, local=local)
    template.link_skills(root)
    base = root / PROJECT_DIR
    verb = "linked at" if base.is_symlink() else "created at"
    print(f"{NAME}: init wrote {len(written)} file(s) under {base.resolve()} ({verb} {base})")
    return 0


def _init_artifact(root: Path, args: argparse.Namespace) -> int:
    written = router.init_artifact(root, args.name, args.modality, args.audience, force=args.force)
    print(f"{NAME}: artifact '{args.name}' wrote {len(written)} file(s)")
    return 0


def _config(action: str, force: bool) -> int:
    path = settings.config_path()
    if action == "path":
        print(path)
        return 0
    if action == "init":
        if path.exists() and not force:
            print(f"{NAME}: {path} already exists (use --force to overwrite)", file=sys.stderr)
            return EXIT_OTHER
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(settings.example_path().read_text(encoding="utf-8"), encoding="utf-8")
        print(f"{NAME}: wrote {path}")
        return 0
    if action == "edit":
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(settings.example_path().read_text(encoding="utf-8"), encoding="utf-8")
        editor = os.environ.get("EDITOR") or shutil.which("nano") or "vi"
        return subprocess.call([editor, str(path)])
    print(f"config: {path}{'' if path.exists() else '  (not present - local storage)'}")
    for label, value in (
        ("storage.asset_root", config_mod.asset_root()),
        ("storage.texmf_home", settings.opt_path("storage", "texmf_home")),
        ("storage.library_bib", config_mod.library_bib()),
        ("storage.library_json", config_mod.library_json()),
        ("guides.private", config_mod.guides_private()),
        ("guides.target_words", config_mod.guides_target_words()),
        ("guides.tolerance", config_mod.guides_tolerance()),
        ("guides.max_page_words", config_mod.guides_max_page_words()),
        ("guides.max_probes", config_mod.guides_max_probes()),
        ("guides.max_cases", config_mod.guides_max_cases()),
        ("guides.distill_min", config_mod.guides_distill_min()),
        ("guides.stale_days", config_mod.guides_stale_days()),
    ):
        print(f"  {label:22} {value if value is not None else '(unset)'}")
    return 0


def _image(action: str, force: bool) -> int:
    if action == "status":
        for key, value in image_mod.status().items():
            print(f"  {key:14} {value}")
        return 0
    image_mod.build_image(no_cache=force)
    print(f"{NAME}: built {image_mod.IMAGE_REF}")
    return 0


def _print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(finding.format())


def _list(root: Path) -> int:
    for card in edit.cards(root):
        name = card.parent.name
        try:
            c = config_mod.load_card(root, name)
        except config_mod.ConfigError as exc:
            print(f"{name}  (invalid card: {exc})")
            continue
        job = "  job active" if jobs.is_active(root, name) else ""
        print(f"{name}  {c.modality}  {c.audience}  {c.phase}{job}")
    return 0


def _check(root: Path, args: argparse.Namespace) -> int:
    if args.resolve:
        verdict = "pass" if args.verdict_pass else "na" if args.na else None
        if verdict is None:
            raise constraints.ConstraintError("--resolve needs --pass --evidence or --na --why")
        constraints.resolve(root, args.artifact, args.resolve, verdict=verdict, text=args.evidence if verdict == "pass" else args.why)
    findings = router.check(root, args.artifact, all_lines=args.all)
    for line in constraints.report(findings, args.artifact):
        print(line)
    if args.resolve:
        return 0  # the verdict is recorded; the summary line says what remains
    if router.blocking(findings):
        return EXIT_CHECK
    return EXIT_SUITE if constraints.red(findings) else 0


def _build(root: Path, args: argparse.Namespace) -> int:
    if args.watch:
        try:
            router.watch(root, args.artifact, diff_from=args.diff_from, no_diff=args.no_diff, all_lines=args.all)
        except KeyboardInterrupt:
            print(f"\n{NAME}: watch stopped")
        return 0
    built = router.build(root, args.artifact, diff_from=args.diff_from, no_diff=args.no_diff, all_lines=args.all)
    for path in (*built.published, *([built.diff] if built.diff else []), *built.diffs):
        print(f"{NAME}: built {path}")
    return EXIT_SUITE if constraints.red(list(built.findings)) else 0


def _link(root: Path) -> int:
    lines = links_mod.sync_links(root, config_mod.load(root))
    if not lines:
        print(f"{NAME}: links up to date")
        return 0
    for line in lines:
        print(f"{NAME}: {line}")
    return 0


def _export(root: Path, artifact: str, tag: str, force: bool) -> int:
    out_dir = router.export(root, artifact, tag, force)
    print(f"{NAME}: exported {artifact} to {out_dir}")
    return 0


def _job(root: Path, args: argparse.Namespace) -> int:
    if args.job_command == "start":
        topics = [t for t in (args.topics or "").split(",") if t]
        if topics:
            card = config_mod.load_card(root, args.artifact)
            pages.check_applicable(topics, card.modality)
            part = args.part if args.part in pages.parts(pages.modality(card.modality)) else None
            system, per_topic, total = show.budget(root, args.artifact, part, topics)
            show.enforce(total, system, per_topic)
        print(jobs.start(root, args.artifact, args.part, topics))
        return 0
    suite = router.check(root, args.artifact) if args.job_command == "end" else []
    lines = jobs.end(root, args.artifact) if args.job_command == "end" else jobs.revert(root, args.artifact)
    for line in lines:
        print(line)
    if args.job_command == "end":
        print(constraints.report(suite)[-1])
    return 0


def _tool(root: Path, args: argparse.Namespace) -> int:
    if args.tool_command == "source":
        return _tool_source(args)
    if args.tool_command == "measure":
        both = not (args.words or args.pages)
        card = config_mod.load_card(root, args.artifact)
        languages = [args.language] if args.language else [None, *card.translations]
        for language in languages:
            label = f" [{language}]" if language else ""
            if args.words or both:
                counted = measure.words(root, args.artifact, language)
                for file, count in counted:
                    print(f"{count:6d} {file}")
                print(f"{sum(c for _, c in counted):6d} total{label}")
            if args.pages or both:
                found = router.pages(root, args.artifact, language)
                print(f"pages{label}: {found.total} total, {found.body} body")
    elif args.tool_command == "table":
        for line in table.run(
            root, args.artifact, args.source, table_id=args.id, max_width=args.max_width,
            max_rows=args.max_rows, font_step=args.font_step,
        ):
            print(line)
    elif args.tool_command == "formula":
        path, width, height = formula.render(root, args.artifact, args.tex, display=args.display)
        print(f"{path} {width}x{height}")
    else:
        print("\n\n".join(claims.blocks(root, args.artifact)))
    return 0


def _tool_source(args: argparse.Namespace) -> int:
    span = None
    if args.pages:
        first, _, last = args.pages.partition("-")
        if not (first.isdigit() and (last or first).isdigit()):
            raise SourceError(f"--pages must look like 3-5, got '{args.pages}'")
        span = (int(first), int(last or first))
    print(source.render(source.load_sections(args.citekey), label=args.section, pages=span))
    return 0


def _guide(root: Path, args: argparse.Namespace) -> int:
    if args.guide_command == "show":
        for kind in ("topic", "move", "procedure"):
            if getattr(args, kind):
                print(show.show_page(kind, getattr(args, kind), unformatted=args.unformatted))
                return 0
        if args.artifact is None:
            raise pages.GuideError("guide show needs an artifact, or one of --topic, --move, --procedure")
        topics = [t for t in (args.topics or "").split(",") if t]
        print(show.show(root, args.artifact, args.part, topics=topics or None, unformatted=args.unformatted, outline=args.outline))
    elif args.guide_command == "add":
        evidence = args.evidence.split(",") if args.evidence else None
        path = edit.add(
            root, args.page, args.rule_id, args.text, origin=args.origin, overrides=args.overrides,
            evidence=evidence, card=args.card, section=args.section, hook=args.hook,
        )
        print(f"{NAME}: wrote rule '{args.rule_id}' to {path}")
        _warn_page(args.page)
    elif args.guide_command == "list" and args.kind == "topic":
        for line in show.topic_table(root, args.artifact, args.part):
            print(line)
    elif args.guide_command == "list":
        for kind in [args.kind] if args.kind else [*pages.KINDS, "trait"]:
            for name in pages.names(kind):
                print(f"{kind}/{name}")
    elif args.guide_command == "edit":
        evidence = args.evidence.split(",") if args.evidence else None
        path = edit.edit(root, args.rule_id, args.text, evidence=evidence)
        print(f"{NAME}: rewrote rule '{args.rule_id}' in {path}")
        _warn_page(f"topic/{path.stem}" if path.parent.name == "topic" else "")
    elif args.guide_command == "drop":
        print(f"{NAME}: dropped '{args.rule_id}' from {edit.drop(root, args.rule_id)}")
    elif args.guide_command == "move":
        print(f"{NAME}: moved '{args.rule_id}' to {edit.move(root, args.rule_id, args.page)}")
    else:
        findings = lint.lint(root)
        _print_findings(findings)
        return EXIT_CHECK if any(f.severity == "error" for f in findings) else 0
    return 0


def _warn_page(key: str) -> None:
    warning = edit.page_warning(key) if key else None
    if warning:
        print(f"{NAME}: warning: {warning}", file=sys.stderr)


def _case(root: Path, args: argparse.Namespace) -> int:
    if args.case_command == "add":
        try:
            payload = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            raise casebook.CaseError(f"standard input is not JSON: {exc}") from exc
        print(casebook.add(root, payload, set(pages.names("topic"))))
    elif args.case_command == "edit":
        try:
            fields = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            raise casebook.CaseError(f"standard input is not JSON: {exc}") from exc
        casebook.edit(args.id, fields, set(pages.names("topic")))
    elif args.case_command == "show":
        print(casebook.show([i for i in args.ids.split(",") if i], args.artifact))
    elif args.case_command == "list":
        for line in casebook.list_lines(args.topic, args.status):
            print(line)
    elif args.case_command == "mark":
        casebook.mark(args.id, args.status)
    else:
        findings = casebook.lint(
            distill_min=config_mod.guides_distill_min(), stale_days=config_mod.guides_stale_days()
        )
        _print_findings(findings)
        return EXIT_CHECK if any(f.severity == "error" for f in findings) else 0
    return 0


def _constraint(root: Path, args: argparse.Namespace) -> int:
    if args.constraint_command == "add":
        try:
            payload = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            raise constraints.ConstraintError(f"standard input is not JSON: {exc}") from exc
        print(constraints.add(payload))
    elif args.constraint_command == "edit":
        try:
            fields = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            raise constraints.ConstraintError(f"standard input is not JSON: {exc}") from exc
        constraints.edit(args.id, fields)
    elif args.constraint_command == "list":
        for line in constraints.list_lines(args.kind, args.status):
            print(line)
    elif args.constraint_command == "mark":
        constraints.mark(args.id, args.status)
    else:
        findings = constraints.lint(root, distill_min=config_mod.guides_distill_min())
        _print_findings(findings)
        return EXIT_CHECK if any(f.severity == "error" for f in findings) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
