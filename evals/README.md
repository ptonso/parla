# evals

Development tooling for the guide loads. It calls models, so it lives outside the package.

```
.venv/bin/python evals/run.py evals/runs/<name>     # worker outputs under three loads
.venv/bin/python evals/metrics.py evals/runs/<name> # deterministic metrics
.venv/bin/python evals/judge.py evals/runs/<name>   # blind pairwise judge
```

`baseline/` holds the loads recorded before the lean-prompts change and `runs/` the outputs; both stay out of git because they quote the author's private guides.
