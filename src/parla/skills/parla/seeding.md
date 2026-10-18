# Seeding a guide from good examples

The author sometimes brings text they consider good and wants the guides to capture why. Extract candidate principles from it and let the author keep the ones that are theirs.

1. Read the examples side by side and ask what each does that a plain version would not: how it opens, how it places evidence, what it leaves out.
2. State each candidate as a one-line quality, never as a description of one sentence.
3. Propose them one at a time, with the lines of the example that show it, and the page each belongs on: a topic, an audience or a modality section.
4. Write an accepted one with `parla guide add <page> <rule-id> --text ... --origin <the example>`, after the author accepts the exact wording.
5. Run `parla guide lint` at the end.
