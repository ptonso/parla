# Two memories: guides and a casebook

**Affects**: [guides](../guides.md), [casebook](../casebook.md), [checks](../checks.md), [cli](../cli.md).

## Situation

texfy-ai kept its writing knowledge in prompt files steered by configured injections. The author's corrections to drafted text, which are the best signal of how they write, had no home, and prompt files grew without a way to know which lines still earned their place.

## Alternatives considered

- **One memory of principles.** Every correction would need to be generalized at once, and the generalization would be wrong often.
- **One memory of examples.** The agent would reread an unbounded pile of examples with no distilled principle.
- **Copy the injections one to one.** `scope`, `expansion` and `compression` measured prose against idea bullets that no longer exist.
- **Hydra for guide pages.** Guides are Markdown merged by path, so composition adds nothing.
- **`[^id]` or `^id` syntax for rule ids.** It is not native Markdown. A level-six heading gives every rule a native anchor and a leaf position.
- **Detect shared lessons with a model.** `parla` makes no model calls, so `case lint` groups by topic and audience and the agent judges the lesson.

## Decision

Guides hold stable principles in pages by subject, merged from public, private and card roots ([guides](../guides.md)). The casebook holds approved concrete corrections ([casebook](../casebook.md)). `guide show` prints both. Principles ported from texfy carry their origin and are judged by the cases like any other. Budgets, language and starter templates belong to the audience, because the venue sets them.

## What tipped it

Cases are cheap to capture and wrong to generalize early. Keeping them apart lets the author approve a principle only after several cases agree.

## Trade-offs accepted

- Two stores to maintain.
- Lint finds candidate groups and cannot tell whether they share a lesson.
- A load can exceed the budget; the author trims by merging or dropping rules.
