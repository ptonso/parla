# Ending jobs, reading their changes, and a soft guide cap

**Affects**: [jobs](../jobs.md), [skill](../skill.md), [guides](../guides.md), [config](../config.md), [checks](../checks.md).

## Situation

In a 10-minute talk session the learning step ran only because the author asked for it. The author approved the work and moved on without the captain suggesting an end, and the distill groups went unproposed. The captain had to rebuild before and after texts from its memory. `guide show` refused to print once the fixed part of the guide neared the cap, so no topic could load. `parla check` scanned `BUILD-ERROR.txt` and counted its own errors again on each failed build.

## Alternatives considered

- **Auto-close a job when another starts.** Two open jobs on two artifacts (slides and paper) are normal, so a new job says nothing about the old one.
- **A remember tool**: a footer on every command naming jobs awaiting review. It adds state and output for what a clear signal list in the skill covers.
- **A cache of every round's source.** The snapshot, the current source and the captain's memory of the rounds are enough to recover the corrections.

## Decision

`job changes <artifact>` prints the unified diff of the source against the newest job's snapshot, active or ended. The skill lists the signs of a job's end and what the captain does at each: one closing line when its reply is probably the last, a suggestion before moving on after a short message, and a three-way question before a substantial unrelated request, whose third option holds the review until the new work settles. The guide cap warns and never fails, with a default target of 1500 words. Build outputs are not artifact sources for the checks. `guide add` reads a bare page name as a topic.

## What tipped it

The cap matters as a lint of the long-term memory (cases distilled into rules), and blocking the day's work for it costs more than it protects. Ending a job is a judgment on conversation, which the skill can describe and no tool can see.

## Trade-offs accepted

A reversal within a job (A to B to A) is invisible in the snapshot diff, and is recovered only from the captain's memory or the job notes.
