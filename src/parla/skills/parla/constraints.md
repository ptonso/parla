# Writing a constraint

A constraint is a rule with an exact answer, kept outside the prompt and run by the suite. Propose one when a correction can be tested. The author's existing text stays as it is: a new constraint reports only on lines a job changes, or on the whole artifact with `parla check --all`.

## Choosing the kind

- A **regex constraint** fits what a pattern decides: a character, a phrase, a reference form, a date format. Propose it when you can write one sentence that must match and one that must not.
- A **probe** fits what needs reading: a citation that supports its claim, a number that matches the source, a caption that describes its figure. Pick the locator that finds the spans: `citation`, `number`, `caption`, `paragraph` or `frame`.
- A matter of degree stays a guide principle ([learning.md](learning.md#choose-the-destination)).

## Writing the entry

Read `parla constraint add --help` and `parla constraint list` for the fields and for what exists. Pipe one JSON object into `parla constraint add` after the author accepts it.

- `id`: short, kebab-case, named for the rule.
- `description`: one line that states the rule positively, since a probe shows it to you as the question and a hint shows it in the guide.
- `regex` with `examples`: a `match` list of real sentences it must hit and an `ok` list of near misses it must not hit. The command rejects the entry when either list fails, so the examples are the test. Draw them from the author's text and the correction that prompted the rule.
- `applies`: restrict by `modality`, `engine` or `audience` when the rule belongs to one.
- `severity`: `error` when the author wants the suite red until fixed, `warning` for a nudge.
- `hint`: `true` for a rule you break often even though the suite catches it. A hint prints its description in the guide, so keep the number small.
- `evidence` and `origin`: the case ids that motivated it, and the rule it was promoted from if there was one.

## Tightening

`parla constraint lint` reports a constraint that collected several `na` answers. Read the verdicts at `job end`, find what the false positives share, and propose a narrower pattern with a new `ok` example, or a probe in place of a regex. Apply the accepted change in place with `parla constraint edit <id>`, giving the fields to update as JSON (a narrower `regex` with its new `examples`, a different `applies.files`, a new `severity`). The command checks the examples again. Retire a constraint that no longer earns its place with `parla constraint mark <id> retired`.
