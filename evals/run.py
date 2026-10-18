"""Pilot eval of the guide loads: asks a worker model to perform each task under three loads.

    python evals/run.py <out-dir>

Conditions: `old` (the load recorded before the lean-prompts change, in baseline/), `defaults`
(the package alone, no private root) and `new` (the package plus the author's preferences), both
in the XML view the model reads, with the topics of the part's row.
Outputs go to <out-dir>/<task>__<condition>.md.
"""

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
PARLA = HERE.parent / ".venv/bin/parla"
WORKER_MODEL = "sonnet"
CONDITIONS = ("old", "defaults", "new")
PROMPT = """Task in a parla project. The text above is the output of `parla guide show` for this artifact. You cannot run commands in this exercise.

Request from the author: {request}

The author's material and library:
{material}

Allowed citation keys: {keys}

Reply with the LaTeX source of the {part} only, no commentary. If the artifact needs a fact the material does not hold, put a line starting with `ASK:` before the text and write the rest without inventing it."""


def guide(condition: str, task: dict, project: Path, empty_config: Path) -> str:
    modality, part = task["modality"], task["part"]
    if condition == "old":
        return (HERE / "baseline" / f"{modality}-{part}.txt").read_text()
    artifact = f"base-{modality}" if condition == "new" else f"default-{modality}"
    env = {**os.environ, **({"PARLA_CONFIG": str(empty_config)} if condition == "defaults" else {})}
    return subprocess.run([PARLA, "guide", "show", artifact, part], cwd=project, env=env, capture_output=True, text=True, check=True).stdout


def work(system: str, task: dict) -> str:
    keys = ", ".join(task["keys"]) or "none"
    prompt = PROMPT.format(request=task["request"], material=task["material"], keys=keys, part=task["part"])
    result = subprocess.run(
        ["claude", "-p", "--setting-sources", "project", "--tools", "", "--no-session-persistence",
         "--model", WORKER_MODEL, "--system-prompt", system, prompt],
        cwd=tempfile.gettempdir(), capture_output=True, text=True, check=True,
    )
    return result.stdout


def setup(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    (project / "parla").mkdir(parents=True)
    (project / "parla/parla.toml").write_text("[project]\nversion = 1\n")
    empty = root / "empty.toml"
    empty.write_text(f'[guides]\nprivate = "{root}/none"\n')
    for name, modality, audience in (("base-paper", "paper", "default"), ("base-cv", "cv", "ai-rd"),
                                     ("default-paper", "paper", "default"), ("default-cv", "cv", "default")):
        cfg = {**os.environ, **({"PARLA_CONFIG": str(empty)} if name.startswith("default") else {})}
        subprocess.run([PARLA, "init", "artifact", name, "--modality", modality, "--audience", audience],
                       cwd=project, env=cfg, capture_output=True, check=True)
    return project, empty


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    tasks = json.loads((HERE / "tasks.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        project, empty = setup(Path(tmp))
        jobs = [(t, c, guide(c, t, project, empty)) for t in tasks for c in CONDITIONS]
    for task, cond, text in jobs:
        (out / f"{task['id']}__{cond}.guide.txt").write_text(text)
    with ThreadPoolExecutor(4) as pool:
        results = pool.map(lambda j: work(j[2], j[0]), jobs)
        for (task, cond, _), text in zip(jobs, results):
            (out / f"{task['id']}__{cond}.md").write_text(text)
            print(task["id"], cond, len(text.split()), "words", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
