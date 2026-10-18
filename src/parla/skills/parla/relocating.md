# Relocating existing rules

An author's guides often hold rules of several kinds in the same lists: craft, exact checks and illustrations. Relocating moves each rule to the home that serves it, so the brief the writer reads stays short and what can be tested is tested. No rule is deleted without a new home, and the author decides every move.

## Take the inventory

Read the guides with `parla guide show --topic <t> --unformatted` and `parla guide list`, and the cases with `parla case list`. Build one table of the rules: page, id, words, and the destination you would propose. Measure the loads with `parla guide list topic --artifact <a> --part <p>` and show the totals against the target.

## Propose in batches

Take at most 5 items at a time, triaged with a toggle list and then worded one question per item, as in [learning.md](learning.md#review-in-batches). Group by the move:

- **To a regex constraint:** a rule a pattern decides. Draw the match and ok examples from the author's own text.
- **To a probe:** a rule decided by reading a span against its source.
- **To merged rules:** several craft rules that overlap, said once in a few atomic rules, one theme each, without "always" or "never". Show the original rules beside the new ones, and keep each new rule an id and one instruction. Resolve conflicts here, for instance a numeric limit that fights a rule about natural prose, by turning the limit into a structural one or into a probe.
- **To a topic hook:** a topic page without a hook, or with one too vague to route by. A hook names the situation in which the topic helps.
- **To a case hook:** a case without a hook, written as in [learning.md](learning.md#phrase-the-case) and applied with `parla case edit <id>`.

## Where a modality-specific rule goes

A topic is a general subject that any artifact may use. Keep the general idea in the topic, and put the part that holds for one modality only in a `## <modality>` section of that topic page, which prints in that modality alone. When the whole topic belongs to some modalities (the frames of a deck, a diagram, a paper abstract), give its page an `applicable` list, so the topic table hides it from other artifacts and a mismatched choice fails before anything prints.

## Public or private

Say where each item lives. The package carries what any competent author of the modality would accept and that encodes no taste: briefs, topic notes, engine facts and universal checks. The author's private root carries personal taste, house terms, banned phrases, venue limits and every constraint that encodes a preference. Default to private, and propose public only for universal items. No command writes the package, so a public item is reported to the author as a change for the package maintainers.

## Apply and measure

Apply accepted items with `parla constraint add` or `parla constraint edit`, `parla guide add`, `parla guide edit`, `parla guide move`, `parla case add` or `parla case edit`, and then `parla guide drop` for the rules that moved. Re-measure after each batch and report the new sizes against the target.
