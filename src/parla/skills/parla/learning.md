# Learning from a job

To learn is to propose, for each correction of a finished job that is worth keeping, where it belongs in the author's memory. The author's corrections are the most precise statement of how they write. At the end of a job you collect them, and the author decides which ones are kept and in what form. Nothing is written until the author accepts the exact wording. Decisions about what to say never enter the memories of writing: they go to the card.

## Find the corrections worth keeping

Run `parla job changes <artifact>`, or read the job's saved `changes.diff`: the diff against the snapshot holds the before and after of every correction, to copy as is. Read it with your memory of the rounds and the job's notes, which hold the author's reasons, the corrections that recur, and the corrections reversed within the job, which show what the author really wanted. Read the verdicts `parla job end` printed too: a false positive answered `na` more than once points at a constraint to tighten. A single edit the author made for the sake of this artifact is a decision, and a correction about the way of writing is worth keeping.

## Choose the destination

Ask of each correction, in this order:

1. Can a pattern decide it? It becomes a **regex constraint** ([constraints.md](constraints.md)). Test it with one sentence that must match and one that must not.
2. Can a reader answer yes or no after reading the span and its source? It becomes a **probe**.
3. Is it a matter of degree, a tendency of the author's voice? It becomes a **style principle** in a guide, reached through cases that share the lesson ([distilling.md](distilling.md)), or at once when the author states it as their rule.
4. Is it a concrete illustration of one of these? It becomes a **case**.

A correction with an exact answer should not stay a case, because the suite enforces it on every build while a case only informs a draft. Propose the destination with the correction, and let the author change it.

A style destination is a change to the guide, and it has three forms: a new rule for a new theme, a **rewrite** of the existing rule the lesson refines, or a **merge** of rules that now overlap. Check the topic page first ([distilling.md](distilling.md#keep-the-guide-inside-its-budget)) and propose the form that keeps the page small. Put such tidying proposals in the same batches, labelled with the rules they replace.

## Phrase the case

- **Lesson:** one line about the quality, never about the sentence. "A contribution states what the reader can now do" teaches, and a note about a word swap does not.
- **Hook:** one line that names the situation in which the case applies, written as something recognizable in a draft: "a table caption that carries definitions", "a contribution that restates the method". The lesson states the rule and the hook states when to open the case. Write it so that someone scanning a list of hooks while editing a different passage can tell whether the case is theirs.
- **Topics:** the guide topics the correction concerns, chosen from `parla guide list topic`.
- **Before and after:** the text as it stood and as the author left it, in their words.
- **Problem:** what was wrong, in one line.

## Review in batches

The author reviews cases in batches of at most 3, ranked by value, in two steps. An AskUserQuestion list holds 4 options and one is reserved for "Chat more".

### Step 1: triage

1. Collect the corrections of the job, drop the ones an existing case or a guide rule already covers, and group the rest into batches.
2. Present the batch in the reply as text, each case laid out with one field per line. The before and after are real text, copied from the artifact's snapshot or the transcript and never rebuilt from memory.

```
Case 1: <short label>
  Destination: case | regex constraint | probe | style principle
  Hook: <one line, the situation>
  Problem: <one line>
  Before:
    <text as it stood>
  After:
    <text as the author left it>
  Lesson: <one line about the quality>
  Topics: a, b
```

3. End the reply with one multiSelect AskUserQuestion. Each option is one case, with the label "Case N: <label>" and the description holding the lesson draft and the topics. A correction that shows a tendency gets a lesson draft worded as a tendency. One more option is "Chat more". Checked cases go on to step 2 and unchecked cases are dropped as not general enough, without argument.
4. Nothing advances while "Chat more" is checked: answer the author, revise the cases they ask to change, and present the batch again.

### Step 2: phrasing

For the checked cases, ask one AskUserQuestion call with one single-select question per case, up to 4 per call, with the header "Case N". The options are 2 or 3 phrasings of the lesson that mostly differ in strictness, from a firm rule that holds every time to a soft tendency, and the description says how. Match the strictness to what the correction showed: a numeric cap on ideas, words or items is a firm rule only when the author stated the number. "Other" carries the author's typed feedback on language and scope. A chosen option is written as is. Feedback under "Other" is applied and the lesson is shown back once before writing. Then write the case with `parla case add`, which reads one JSON object from standard input with `artifact`, `part`, `topics`, `hook`, `problem`, `before`, `after` and `lesson`. A correction headed for a constraint is written with `parla constraint add` after the same two steps, and its motivating case is marked distilled with the constraint as its evidence.

The review ends when every batch has had both steps. Report the answers in the end block, naming the corrections dropped at step 1 and the phrasing chosen at step 2.
