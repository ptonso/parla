# Quick start

## Install

`parla` needs Python 3.12 and Docker.

```bash
python -m venv .venv
source .venv/bin/activate
pip install "parla[svg,pdf]"
parla image build
```

The `svg` extra holds the font metrics of the SVG checks and the `pdf` extra the PDF text extraction of `parla tool source`. `parla image build` builds the LaTeX image once.

## Start a project

In your project folder:

```bash
parla init
parla init artifact my-paper --modality paper
```

`parla init` creates the `parla/` folder and links the `parla` skill into `.claude/skills` and `.agents/skills`, so Claude Code and opencode find it. `parla init artifact` writes the artifact's card and a starter that compiles.

The modality is one of `paper`, `short-paper`, `thesis`, `cv`, `talk`, `diagram` or `social-post`. Add `--audience <name>` to set a readership such as a conference, which sets the page limits and the starter template ([guides](../../specs/guides.md#audience-page)).

## Run a job

Open your coding agent and type:

```
/parla my-paper introduction
```

The agent reads the card and `parla guide list topic`, which shows each topic with its size and when it applies, and picks the topics the section needs. It starts a job, which snapshots the artifact, and hands one worker a short brief. The worker loads about 1000 words of your guides for those topics, edits the source and checks it. You give feedback in your own words, and the worker's questions about what to say come to you through the agent. The result is `parla/artifacts/my-paper/my-paper.pdf`, with a change PDF beside it that shows everything the job touched.

`parla check` and `parla build` end with a one-line suite summary, `suite: 0 fail, 0 probes open` when the text satisfies your constraints ([how it learns](learning.md#constraints)). To see what the worker received, run `parla guide show my-paper introduction`, and add `--outline` to see which file each part of it comes from.

Say "done" to end the job. The agent then proposes what to remember from your corrections. To drop the whole job, run `parla job revert my-paper`.

## Make it yours

Your guides, constraints and casebook live in `~/.config/parla`. To keep the `parla/` folder outside the project, to wire a Zotero library, to move your guides or to change the 1000-word prompt budget (`[guides].target_words`), run `parla config init` and edit `~/.config/parla/config.toml` ([config](../../specs/config.md)).

## Next

- [How it learns](learning.md)
- [CLI reference](../../specs/cli.md)
