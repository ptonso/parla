# parla

`parla` lets a coding agent write papers, CVs, talks, posts and diagrams in your own voice.

It keeps your long-term memory of how you write, loads the part of it that the section being written needs, checks the text against the rules of yours that a tool can test, and asks you before anything becomes permanent. The goal is to automate communication while keeping your idiosyncrasies.

`parla` works as a plugin for agentic tools. It ships a skill that Claude Code and opencode load, and the skill carries the working method: how a job is routed, when the agent asks you, and how it learns from your corrections. The `parla` CLI supplies what the agent cannot do alone, and you talk to the agent as usual:

```
/parla icra-paper introduction
```

- **Final format.** The agent edits LaTeX, SVG or plain text directly, and `parla` builds it in a pinned Docker image. See the [architecture](https://github.com/ptonso/parla/blob/master/specs/architecture.md).
- **Good defaults.** A brief per modality, a note per topic and a few starter checks give a reasonable first draft before you teach anything. See [guides](https://github.com/ptonso/parla/blob/master/specs/guides.md).
- **Checks what can be tested.** A pattern, such as an em dash or a reference form, fails the build with its line, and a question, such as whether a citation supports its claim, is located for the agent to answer with a quoted line. See [constraints](https://github.com/ptonso/parla/blob/master/specs/constraints.md).
- **Learns from corrections.** Your fixes become cases, rules or constraints, always with your approval. See the [casebook](https://github.com/ptonso/parla/blob/master/specs/casebook.md).
- **Safe to steer.** Every job is snapshotted and diffed, and can be reverted. See [jobs](https://github.com/ptonso/parla/blob/master/specs/jobs.md).
- **Local.** Your guides and casebook are plain files on your machine, and `parla` makes no model calls.

## Vision

`parla` keeps a human in the loop. You make the decisions about what to say and which writing preferences to keep. The agent applies the decisions you already made and proposes text that follows them. It asks before anything becomes permanent: a case, a rule, a constraint or a claim in the card.

A job has two roles. The agent you talk to chooses the topics the section needs (`parla guide list topic` shows each with its size and when it applies), relays the worker's questions to you and keeps your memories. One worker subagent writes. Its prompt is short, about 1000 words: your rules for those topics, one-line hooks of earlier corrections and the card ([skill spec](https://github.com/ptonso/parla/blob/master/specs/skill.md)). The worker is done when `parla check` ends with `suite: 0 fail, 0 probes open`.

## How it learns

When a job ends, the agent proposes where each correction belongs and you accept, rephrase or decline: a case for an illustration, a rule for a matter of degree, a constraint for what a pattern or a yes-or-no question can decide. When several cases share a lesson, it proposes a rule with the cases as evidence, and it keeps the guides inside their size budget by merging and rewriting rules.

| Memory | Holds | Changes |
|---|---|---|
| Guides | your stable rules, on top of the shipped defaults | slowly |
| Constraints | patterns and questions with an exact answer, run by every check and build | when a correction has an exact answer |
| Casebook | your corrections, each with a before, an after and a lesson | every job |
| Card | the decisions of one artifact: claim strength, scope, which result leads | per artifact |

More in [how it learns](https://github.com/ptonso/parla/blob/master/docs/guide/learning.md).

## Modalities

| Modality | Output |
|---|---|
| `paper`, `short-paper`, `thesis` | PDF, plus a change PDF against the job snapshot |
| `cv` | PDF |
| `talk` | Beamer PDF |
| `diagram` | SVG and PNG |
| `social-post` | plain text |

## Quick start

`parla` needs Python 3.12 and Docker.

```bash
pip install "parla[svg,pdf]"
parla image build
parla init
parla init artifact my-paper --modality paper
```

`parla init` links the skill into `.claude/skills` and `.agents/skills`. Open your agent and type `/parla my-paper`. The full walk-through is in the [quick start](https://github.com/ptonso/parla/blob/master/docs/guide/quickstart.md).

## Documentation

- [Quick start](https://github.com/ptonso/parla/blob/master/docs/guide/quickstart.md): install, first artifact, first job.
- [How it learns](https://github.com/ptonso/parla/blob/master/docs/guide/learning.md): cases, rules, constraints and the four memories.
- [Development](https://github.com/ptonso/parla/blob/master/docs/guide/development.md): tests and linting.
- [specs/](https://github.com/ptonso/parla/blob/master/specs/README.md): the contract of every command and format. The agent's method is the [skill spec](https://github.com/ptonso/parla/blob/master/specs/skill.md).

## License

Apache 2.0. See [LICENSE](https://github.com/ptonso/parla/blob/master/LICENSE) and [THIRD-PARTY.md](https://github.com/ptonso/parla/blob/master/THIRD-PARTY.md).
