# Public defaults, private preferences

**Affects**: [guides](../guides.md), [casebook](../casebook.md), [skill](../skill.md).

## Situation

The package shipped 588 words of engine facts and an empty `general.md`. The writing knowledge of papers, CVs, talks and diagrams lived in the author's private root: 299 rules, 271 of them ported from the texfy prompt chain. A fresh install wrote with no guidance. `guide show` printed a merge of those rules with no role, no description of the artifact and no quality bar, and the reader could not tell a universal default from a personal taste.

The rules were tuned over long debugging sessions against weak models driven by injected prompts. Some name machinery that no longer exists (plan directives, the storyboard-to-layout handoff, idea bullets), and many state one thought several times. The agent is now a capable model that edits the source directly, so it needs the goal and the quality bar, and fewer low-level instructions.

## Alternatives considered

- **Brief plus a few public rules.** Rule ids stay citeable, and private rules can contradict them again.
- **Keep the rules and prepend a brief.** Least change, and the load stays rule-heavy.
- **Private pages that can replace public ones (`replace:`, `drop:`).** More power, and it brings back the conflict problem. With no public rule there is nothing to replace.
- **Delete rules that a capable model follows anyway.** A rule's text does not show whether it patched a weak model or records a decision of the author, so taste would be lost. Only dead references and duplicates are removed, each with the author's approval.
- **XML-tagged output.** The gain over Markdown headers is small and the human reading gets worse.

## Decision

The package ships defaults as prose: a frame, a brief per modality with a parts table, trait presets, moves and procedures as short recipes, and engine facts ([guides](../guides.md#roots)). No public page holds a rule. The private root and the card hold the author's preferences, which append to the defaults and win over them ([merge](../guides.md#merge)). `guide show` prints one document, goal first, with the preferences, the cases and the card last ([output](../guides.md#parla-guide-show)).

## What tipped it

A prose brief cannot conflict with a rule, so the two layers need no override machinery between them. Putting the preferences and cases at the end of the load uses recency for the items an agent most often forgets.

## Trade-offs accepted

- The load does not shrink by much: the briefs add about 400 words and the cleanup of dead rules and duplicates removes about as many.
- The brief is interpreted by the agent, so a rule that must always hold has to be a preference, a check or an engine fact.
- The `social-post` brief is a first draft without a private seed from the author.
