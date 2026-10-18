# Running a job

A job (defined in [SKILL.md](SKILL.md#the-language-of-the-system)) has a snapshot, a folder for the brief and notes, the topics you chose, and one worker. You are the captain: you hold the author's request and the choice of topics, relay the author's words and answers, and write to the memories. The worker holds the guide, the text and the suite. In the `polishing` phase say in the brief that the worker reads the build and its diff first.

## Choose the topics

`parla guide list topic --artifact <artifact> --part <part>` prints one line per topic that applies to the artifact's modality, `name | words | hook`, and a footer with the system part, the target and the words left for topics. Choose the topics whose hooks match the request and the part, and keep the sum of their words near the budget left. The footer also names the topics of the part's row as a hint. A topic left out costs craft guidance for the round, and the suite still guards every constraint. Start the job with `--topics`. When the feedback moves to another topic, read the table again and send the worker the new topics.

## The worker

Launch one worker for the job and resume the same one for every round, forwarding each piece of the author's feedback verbatim. A small edit, such as one sentence or a renamed term, may run in your own session: follow [worker.md](worker.md) yourself, with `parla guide show --topics`.

Write `.parla/jobs/<id>/brief.md` for the worker. The id is printed by `parla job start`. Start it with the line that sends the worker to its instructions, naming the skill folder this skill was loaded from: "Read <skill folder>/worker.md and <skill folder>/suite.md first." Then:

- the artifact, the part and the card's phase
- the author's words, verbatim
- the chosen topics
- what changed, as pointers to files and never as summaries
- decisions not yet in the card
- your own suggestion, labelled as yours
- what must not change

The worker cannot see this skill's other pages, so anything it needs beyond the brief and those two pages goes into the brief. Launch it with one instruction: read the brief at its path and do what it says.

When the worker returns, run `parla check <artifact>` yourself before you relay anything, and compare its last line with the `suite:` line of the round block. A worker that stopped on a failing tool (a missing extra, a missing file) names what it needs under `asked:`; that is yours to fix when it is the environment, and the author's to answer when it is about what to say.

## Questions

A subagent cannot ask the author. The worker returns the questions it needs settled, each with the options it sees, and stops. Ask them following [asking.md](asking.md), record the answers in the card, and resume the worker with the answers verbatim.

## Job notes

When the context grows too large, propose writing `.parla/jobs/<id>/notes.md` and continuing in a fresh worker. The notes hold what a continuing context needs: decisions, the steering so far and open threads.

## Ending

When the author is done, run `parla job end` and follow [learning.md](learning.md). A job ends with a green suite: every failure fixed and every probe answered. `job end` prints the suite's summary line last. When it shows a failure or an open probe, the job is not finished: resume the worker, or tell the author what remains and why.
