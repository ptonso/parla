"""Deterministic metrics of one worker output.

    python evals/metrics.py <out-dir>

Per output: em dashes, banned-phrase hits, citation keys outside the allowed list, numbers the
material does not hold, `ASK:` lines and words. A run passes when the first four are zero.
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
BANNED = ("underscores the importance", "provides insights", "bridge the gap", "promising approach", "powerful", "comprehensive", "facilitate")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER.findall(text)}


def measure(task: dict, text: str) -> dict:
    body = "\n".join(line for line in text.splitlines() if not line.startswith("ASK:"))
    keys = {k.strip() for group in re.findall(r"\\cite\w*\{([^}]*)\}", body) for k in group.split(",")}
    invented = numbers(re.sub(r"\\(?:ref|label|cite\w*|section|subsection)\{[^}]*\}", "", body)) - numbers(task["material"])
    return {
        "em_dash": body.count("\u2014"),
        "banned": sum(body.lower().count(p) for p in BANNED),
        "bad_keys": len(keys - set(task["keys"])),
        "bad_numbers": len(invented),
        "asks": len(text.splitlines()) - len(body.splitlines()),
        "words": len(body.split()),
    }


def main(out: Path) -> None:
    tasks = {t["id"]: t for t in json.loads((HERE / "tasks.json").read_text())}
    rows = {}
    for path in sorted(out.glob("*__*.md")):
        task_id, cond = path.stem.split("__")
        rows[(task_id, cond)] = measure(tasks[task_id], path.read_text())
    print(f"{'task':16} {'cond':9} em ban key num ask words pass")
    for (task_id, cond), m in rows.items():
        ok = not (m["em_dash"] or m["banned"] or m["bad_keys"] or m["bad_numbers"])
        print(f"{task_id:16} {cond:9} {m['em_dash']:2} {m['banned']:3} {m['bad_keys']:3} {m['bad_numbers']:3} {m['asks']:3} {m['words']:5} {'yes' if ok else 'NO'}")
    for cond in ("old", "defaults", "new"):
        mine = [m for (t, c), m in rows.items() if c == cond]
        passed = sum(not (m["em_dash"] or m["banned"] or m["bad_keys"] or m["bad_numbers"]) for m in mine)
        print(f"{cond}: {passed}/{len(mine)} pass")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
