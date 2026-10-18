# Clearing the suite

`parla build` and `parla check` end with a report, as a test run does. It lists what the author's constraints and the engine's checks found in the lines this job changed, and it ends with one summary line. The job is finished when the suite is green: no failure and no open probe. Treat the report as the definition of done for the text, and read each entry as a located failure to fix.

## Reading the report

- A line with `error` or `warning` and the id `constraint/<id>` is a regex constraint that matched. It names the file, the line, the matched text and a key.
- A line with `probe` is a question the tool located for you: the span to judge, and the tool that helps. Open probes keep the suite red.
- Other ids come from the engine's checks and, after a build, from its log (an overflowing slide, an overfull line). An `error` of this kind stops the build.
- `resolved` marks a finding with a verdict. It reopens when the text of its span changes.

## Fixing a failure

Make the smallest edit that removes the cause, inside the lines the job changed. Run `parla check <artifact>` again, which is fast and needs no compile; `parla build <artifact>` publishes the PDF and the diff, runs the same suite and adds the findings from the engine's log. A `warning` does not keep the suite red, so fix it when the fix is small and mention it otherwise. If the fix touches a sentence a probe covered, the probe reopens, so clear failures first and answer probes last. Text the job did not change stays as it is, whatever the report says about it; mention such a finding to the author instead.

## Answering a probe

Read the span, then verify it against its source with the tool the finding names (for a citation, `parla tool source <key>` prints the cited paper). Record the verdict (the command exits 0 once it is recorded and prints the report again, so read its last line for what remains):

```
parla check <artifact> --resolve <key> --pass --evidence "<a line you read in the source>"
```

The evidence is a quote that proves the span. If the source does not support the span, fix the text: the edit changes the span and the probe reopens with a new key, which you then verify again.

## Answering not applicable

A finding that does not apply, such as a pattern inside a quotation or a number that belongs to a citation key, is answered with

```
parla check <artifact> --resolve <key> --na --why "<the reason>"
```

Use it when the finding is a false positive, and say the reason precisely. Repeated `na` answers on one constraint tell the author its pattern needs tightening, so they are worth reporting in the round block. Never answer `na` to clear a finding you could fix.

## Returning

Return the round block only when the report ends with `suite: 0 fail, 0 probes open`. Put the summary line and each `na` with its reason in the `suite:` field. `parla check --all` covers the whole artifact when the author asks for it.
