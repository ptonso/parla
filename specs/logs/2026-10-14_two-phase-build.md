# Build checks before it compiles

**Affects**: [checks](../checks.md), [cli](../cli.md), [latex engine](../latex-engine.md), [config](../config.md).

## Situation

texfy-ai enforced many rules silently in post-processing: it escaped underscores, normalized citation style, dropped duplicate figures. With the agent editing the source directly, nothing enforces them, and the first sign of a problem is an engine failure whose log is long and rarely points at the cause. The agent loses a compile (tens of seconds in Docker) per mistake, and its context fills with log text.

## Alternatives considered

- **Keep silent rewriting.** The agent then reads source that changed under it, and the diff shows changes nobody asked for.
- **Compile only, parse the log better.** It still costs a compile per mistake, and some mistakes, such as a dangling `\ref` or a duplicate figure, produce a warning at best.
- **A `--no-check` flag.** It invites skipping the phase that saves the most time. A per-project `[checks].ignore` list records the exception instead.
- **Structured JSON findings.** Humans and agents both read a one-line text format. JSON can be added when something needs it.

## Decision

`build` runs in two phases ([cli](../cli.md#parla-build-artifact---watch---diff-from-pathgit-ref---no-diff---all)). The check phase ([checks](../checks.md)) runs the engine's static checks and stops on errors with short findings. The compile phase keeps the debugged latexmk flags and prints a failure as the same finding format, with exit code 2. Warnings never stop a build. A check that is wrong for a project goes in `[checks].ignore`.

## What tipped it

The author wants the agent, and the human, to iterate fast: a check that costs milliseconds replaces a compile that costs seconds.

## Trade-offs accepted

- The checks duplicate some of what TeX would report, so each must match what the engine does, or it fails a build that would compile. The ignore list is the escape.
- Check ids become part of the project contract.
