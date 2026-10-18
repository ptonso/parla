"""`guide lint`: structure, origins, links and budget of the guides. See `specs/guides.md#parla-guide-lint`."""

from __future__ import annotations

import re
from pathlib import Path

from .. import casebook
from .. import config as config_mod
from ..checks import Finding
from ..checks.ids import finding
from ..names import PROJECT_DIR
from . import edit, pages, rules, show

_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_CODE_RE = re.compile(r"`[^`]*`")


def _display(root: Path, path: Path) -> str:
    base = root / PROJECT_DIR
    if path.is_relative_to(base):
        return path.relative_to(base).as_posix()
    for label, guide_root in pages.roots().items():
        if path.is_relative_to(guide_root):
            return f"{label}:{path.relative_to(guide_root).as_posix()}"
    return str(path)


def lint(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    defined: dict[str, list[tuple[str, str, rules.Rule]]] = {}  # id -> (page key, file, rule)
    for key, path in edit.files(root):
        file = _display(root, path)
        text = path.read_text(encoding="utf-8")
        _, body = edit.split_raw(text)
        parsed = rules.parse(body)
        findings += [finding(p.id, file, p.line, p.message) for p in parsed.problems]
        in_file: set[str] = set()
        public = path.is_relative_to(pages.PUBLIC_ROOT)
        for rule in parsed.rules:
            if public:
                findings.append(finding("public-rule", file, rule.line, f"public pages hold no rule; '{rule.id}' belongs in the private root"))
            if rule.id in in_file:
                findings.append(finding("rule-duplicate", file, rule.line, f"rule id '{rule.id}' is defined twice in this file"))
            in_file.add(rule.id)
            defined.setdefault(rule.id, []).append((key, file, rule))
        for number, line in enumerate(text.splitlines(), 1):
            for target in _LINK_RE.findall(_CODE_RE.sub("", line)):
                target = target.split("#")[0]
                if target and "://" not in target and not target.startswith("mailto:") and not (path.parent / target).exists():
                    findings.append(finding("link-broken", file, number, f"link target '{target}' does not exist"))

    for rule_id, places in defined.items():
        keys = {k for k, _, _ in places}
        if len(keys) > 1:
            _, file, rule = places[-1]
            others = ", ".join(sorted(keys - {places[-1][0]}))
            findings.append(finding("rule-duplicate", file, rule.line, f"rule id '{rule_id}' is also defined in {others}"))
        for _, file, rule in places:
            if rule.overrides is not None and rule.overrides not in defined:
                findings.append(finding("rule-overrides-missing", file, rule.line, f"'{rule.id}' overrides '{rule.overrides}', which names no rule"))

    findings += _modality_findings(root)
    findings += _topic_findings()
    contradicted = {r for c in casebook.load().values() if c["status"] == "active" for r in c.get("contradicts", [])}
    for rule_id, places in defined.items():
        for _, file, rule in places:
            if rule_id in contradicted and (rule.origin or "").startswith("texfy"):
                findings.append(finding("rule-contradicted", file, rule.line, f"an active case contradicts the ported rule '{rule_id}'"))
    return sorted(findings, key=lambda f: (f.file, f.line))


def _topic_findings() -> list[Finding]:
    findings: list[Finding] = []
    cap = config_mod.guides_max_page_words()
    for name in pages.names("topic"):
        page = pages.load(f"topic/{name}")
        file = f"{'public' if page.public is not None else 'private'}:topic/{name}.md"
        if not page.meta.get("hook"):
            findings.append(finding("hook-missing", file, 1, f"topic '{name}' has no `hook` in either root"))
        unknown = [m for m in pages.applicable(f"topic/{name}") if m not in pages.names("modality")]
        if unknown:
            findings.append(finding("topic-applicable-unknown", file, 1, f"topic '{name}' is limited to unknown modality {', '.join(unknown)}"))
        size = len(show._plain(show._page_block(page.key, page, "topic", name)).split())
        if size > cap:
            findings.append(finding("guide-page-over-cap", file, 1, f"topic '{name}' takes {size} words, over the {cap} page cap"))
    return findings


def _words(load: show.Load) -> int:
    return sum(len(show._plain(b).split()) for b in show.blocks(load) if b.tag)


def _modality_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    limit = config_mod.guides_limit_words()
    for name in pages.names("modality"):
        page = pages.modality(name)
        file = f"{'public' if page.public is not None else 'private'}:modality/{name}.md"
        table = pages.parts(page)
        if page.public is not None and not any(sec.name == "brief" for sec in page.public.sections):
            findings.append(finding("brief-missing", file, 1, f"modality '{name}' has no `## brief`"))
        for part, (job, topics) in table.items():
            if page.public is not None and not job:
                findings.append(finding("brief-missing", file, 1, f"part '{part}' has no job"))
            try:
                system = _words(show.Load(name, None, page.meta.get("engine", "latex"), page.meta.get("traits") or {}, part, [], None, job))
                full = _words(show.Load(name, None, page.meta.get("engine", "latex"), page.meta.get("traits") or {}, part, topics, None, job))
            except pages.GuideError as exc:
                findings.append(finding("link-broken", file, 1, str(exc)))
                continue
            for label, words in (("the system part", system), ("with all its topics", full)):
                if words > limit:
                    findings.append(finding("guide-over-budget", file, 1, f"loading part '{part}' ({label}) takes {words} words, over the {limit} limit"))
    return findings
