"""Blind pairwise judge of the worker outputs, both orders per pair.

    python evals/judge.py <out-dir>

Pairs: new vs old and defaults vs old. A condition wins a task when it wins both orders, or one
order and ties the other. The judge sees the author's material and the rubric, never the load.
"""

import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
JUDGE_MODEL = "opus"
RUBRIC = """You are judging two drafts of the same part of an artifact (paper or CV) written from the same author material.
Criteria, in order: (1) grounding: no claim, number, citation or fact beyond the material, and open gaps are asked about instead of filled; (2) claim strength matches the evidence; (3) structure fits the part's job in this kind of artifact; (4) economy and clarity of the prose; (5) fit for the reader (a peer reviewer, or a CV screener and then a technical reader).
Material:
{material}

Draft A:
{a}

Draft B:
{b}

Reply with one JSON object only: {{"winner": "A" | "B" | "tie", "reason": "<one sentence>"}}"""


def ask(material: str, a: str, b: str) -> dict:
    out = subprocess.run(
        ["claude", "-p", "--setting-sources", "project", "--tools", "", "--no-session-persistence", "--model", JUDGE_MODEL,
         RUBRIC.format(material=material, a=a, b=b)],
        cwd=tempfile.gettempdir(), capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out[out.index("{"): out.rindex("}") + 1])


def verdict(material: str, left: str, right: str) -> str:
    """'left', 'right' or 'tie' over both presentation orders."""
    first, second = ask(material, left, right), ask(material, right, left)
    score = {"A": 1, "B": -1, "tie": 0}
    total = score[first["winner"]] - score[second["winner"]]
    return "left" if total > 0 else "right" if total < 0 else "tie"


def main(out: Path) -> None:
    tasks = json.loads((HERE / "tasks.json").read_text())
    pairs = [(t, c) for t in tasks for c in ("new", "defaults")]

    def read(task: dict, cond: str) -> str:
        return (out / f"{task['id']}__{cond}.md").read_text()

    def judge(pair: tuple[dict, str]) -> str:
        task, cond = pair
        return verdict(task["material"], read(task, cond), read(task, "old"))

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(judge, pairs))
    tally: dict[str, dict[str, int]] = {"new": {"left": 0, "right": 0, "tie": 0}, "defaults": {"left": 0, "right": 0, "tie": 0}}
    for (task, cond), v in zip(pairs, results):
        tally[cond][v] += 1
        print(f"{task['id']:16} {cond:9} vs old: {'wins' if v == 'left' else 'loses' if v == 'right' else 'ties'}")
    for cond, t in tally.items():
        print(f"{cond} vs old: {t['left']} wins, {t['tie']} ties, {t['right']} losses")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
