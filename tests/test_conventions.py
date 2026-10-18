"""Repository rules from the delta's definition of done."""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "parla"
CONCRETE = ("parla.engines.latex.engine", "parla.engines.none", "parla.engines.svg")


def _modules():
    return sorted(p for p in SRC.rglob("*.py") if p.name != "names.py")


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def test_the_product_name_is_a_literal_only_in_names_py():
    offenders = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstring_ids(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                if "parla" in node.value.lower():
                    offenders.append(f"{path.relative_to(SRC)}:{node.lineno}: {node.value[:50]!r}")
    assert offenders == []


def test_no_module_outside_the_engines_imports_a_concrete_engine():
    offenders = []
    for path in _modules():
        rel = path.relative_to(SRC).as_posix()
        if rel.startswith("engines/"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.ImportFrom):
                base = ("parla." + ".".join(rel.removesuffix(".py").split("/")[:-node.level])) if node.level else ""
                module = f"{base}.{node.module}" if node.level and node.module else (base or node.module or "")
                names = [module, *(f"{module}.{a.name}" for a in node.names)]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            if any(n == c or n.startswith(c + ".") for n in names for c in CONCRETE):
                offenders.append(f"{rel}:{node.lineno}")
    assert offenders == []


def test_no_module_mentions_texfy_except_to_cite_a_source():
    offenders = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstring_ids(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                if "texfy" in node.value.lower() and node.value != "texfy":
                    offenders.append(f"{path.relative_to(SRC)}:{node.lineno}: {node.value[:50]!r}")
    assert offenders == []
