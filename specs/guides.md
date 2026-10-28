# parla Guides Spec

Related: **Read first** [architecture](architecture.md), [config](config.md). **See also** [casebook](casebook.md), [constraints](constraints.md), [jobs](jobs.md), [checks](checks.md), [cli](cli.md).

## Overview

Guides are the memory of how an artifact is written, in two layers. The **defaults** ship in the package: for each modality, a prose brief that says what the artifact is, who reads it and what each part does, and for each topic a hook and a short craft note, so a fresh install writes well with no configuration. The **preferences** are the author's own rules, kept in the author's private root and in the artifact's card: the idiosyncrasies of how this author likes the modality. Preferences append to the defaults and win over them. Guides carry craft, which is a matter of degree. What a reviewer can answer yes or no lives in [constraints](constraints.md) and runs as a test suite.

The agent never reads guide files directly. `parla guide show` prints one document for the part about to be touched, in the form the model reads: XML blocks, rules as plain bullets, no ids and no origin tags. It stays around 1500 words because the captain of the job picks the topics: `parla guide list topic` prints each topic with its hook and its size, and the captain chooses the ones the job needs. Cases appear as one-line hooks that the agent opens on demand. `--unformatted` prints what the files contain, with ids and origins, for humans and for distillation.

What is specific to guides is the page kinds. A **modality** page holds the default brief of one kind of artifact and its parts table. A **topic** page holds a hook, the default craft note and the author's rules on one subject wherever it appears. An **audience** page sets the limits and starters of one readership and holds the author's overrides for it. Traits, moves, procedures and engines ship as short prose and take the author's additions.

Walk-through: the captain of `icra-paper` runs `parla guide list topic --artifact icra-paper --part introduction` and sees `flow | 298 words | …`, `claims | 179 words | …`, and a footer with the budget left. It starts the job with `--topics contributions,flow,claims`. The worker runs `parla guide show icra-paper introduction`. The loader prints the frame, the paper brief and the job of the `introduction` part, the latex engine facts and the trait presets, the case hooks, then the author's preferences for the paper modality and the three topics, and the card last. A rule in the ICRA page that overrides a topic rule removes the topic rule from the output.

## Language

- **Page**: one Markdown file with frontmatter, addressed by kind and name (`topic/claims`).
- **Brief**: the default prose of a page, written for any author; it holds no rule.
- **Rule**: one preference of the author: a level-six heading with its id and one blockquote line. Rules exist only in private pages and cards, and are craft. Anything a reviewer can answer yes or no is a [constraint](constraints.md).
- **Origin**: where a block comes from: `public` for the shipped defaults, `private`, `card` or `case`; a rule also carries the text in its parenthetical.
- **Part**: one named piece of an artifact in a modality's parts table, such as `introduction`.
- **Trait**: a property of a whole artifact: `reader`, `narrative`, `visual` or `pacing`.
- **Move**: a named technique for one request, loaded for that job only.
- **Procedure**: a recipe for a recurring task, such as grounding citations.
- **Limits**: the budget an audience sets per modality.
- **Hook**: one line that says when a topic or a case applies, so the agent can choose without reading the body.
- **Target, tolerance**: the recommended size of one `guide show` output in words, and the multiple of it beyond which the command warns that the guides need distilling. The cap is soft: it lints the long-term memory and never blocks a job.
- **System part**: everything `guide show` prints except the topics.

## Map

`parla.guides` owns page loading, the three-root merge, rule parsing, `show` and `lint`. `parla.guides.rules` holds the rule format. Public pages ship in `parla/guides/`; private pages live under `[guides].private`.

## Contracts

### Roots

| Root | Location | Holds |
|---|---|---|
| public | `parla/guides/` inside the package | the frame, a brief per modality, a hook and craft note per topic, trait presets, moves and procedures as short recipes, engine facts, the `default` audience; prose only, no rule and nothing that is the author's style |
| private | `<[guides].private>/guides/` | the author's preferences as rules, and the audiences, topics and additions to any public page |
| card | `artifacts/<name>/card.md` | traits, decisions and rules for this artifact |

Public and private share one layout. The agent reads and writes guides only through the CLI. A public page holds no rule, so a private rule can never contradict a public one.

### Layout

```
guides/
  general.md
  topic/<name>.md
  modality/<name>.md
  audience/<name>.md
  engine/<name>.md
  trait/<kind>/<name>.md
  move/<name>.md
  procedure/<name>.md
```

### Page frontmatter

Every page has `kind` and the key that names it. Flow-style YAML is not used.

| Kind | Keys |
|---|---|
| general | `kind` |
| topic | `kind`, `topic`, `hook`, `applicable` (optional list of modalities) |
| modality | `kind`, `modality`, `engine`, `traits` (map), `includes` (optional), `engine_pages` (optional list of engine pages loaded after the card's engine, such as `beamer` for a talk) |
| audience | `kind`, `audience`, `language`, `limits`, `setup` |
| engine | `kind`, `engine` |
| trait | `kind`, `trait` (such as `reader/peer`) |
| move, procedure | `kind`, `move` or `procedure` |

A private page that shares its key with a public page adds to it and needs no frontmatter beyond `kind` and the key.

### Rule format

A rule is a level-six heading holding its id, followed by exactly one blockquote line holding the rule and its origin in parentheses:

```markdown
###### pos-gap
> state the gap as what no prior work can do, then name who comes closest (origin: texfy draft/section/rules/plan_directives.txt)
```

- The parenthetical holds `origin: <text>` and may add `overrides <rule-id>`, separated by `;`.
- Ids are unique across all pages and the card.
- A level-six heading is a leaf, so nothing nests under a rule.
- Rules point to each other with ordinary Markdown links.
- Examples keep their own sections, because a before and after does not fit one line. Items a reviewer can test are [constraints](constraints.md), not sections of a page.
- Rules exist only in private pages and cards. A public page holds prose and tables.

### Topic page

The package ships a page for each topic that a public parts table names: the frontmatter `hook`, one line that says when the topic applies, and a short craft note of prose with no rule. A private page of the same key appends `## principles` (rules). It may also set its own `hook`, which wins over the public one, and add one `## <modality>` section with rules that apply only in that modality. A private topic page without a public counterpart needs a `hook`. A topic is a general subject. When it holds rules that make sense for some modalities only, such as the slide frames of a talk, its `applicable` lists them, and a private value wins over a public one. A topic without `applicable` fits every modality. A part may name a topic that has no page, which means nobody has written on it yet.

### Modality page

The public page holds `## brief` (prose: what the artifact is, the quality bar, the reader) and `## parts`, a table of `part | job | topics`. The job is one sentence on what the part does in this kind of artifact, and the topics name the private pages whose preferences load for it. A private page of the same key adds `## principles` (rules), a `## build order` (a numbered list the agent compresses for small tasks), and parts rows: a row for an existing part adds its topics to the public ones. A page with `includes: <modality>` inherits the sections of the page it includes; a section it defines replaces the inherited one.

The brief states the goal and the quality bar. It gives no instruction that a style preference could contradict.

### Audience page

Frontmatter:

```yaml
kind: audience
audience: icra
language: en
limits:
  paper:
    pages: 8
    excluding:
      - references
setup:
  paper:
    template: ieeeconf
    packages:
      - cite
      - graphicx
```

The body has one `## <topic>` section per topic the audience overrides, holding rules. `limits` and `setup` are keyed by modality. A card may override `limits` for one artifact. `setup` feeds `init artifact` ([template](template.md#artifact-folder)). The package ships the audience `default`, with empty `limits` and `setup`.

### Merge

For one page path, public and private merge by appending: the public sections first, then the private ones, with a section of the same name continuing the public one. Rows of the parts table with the same part join their topics. A private page can add and can never replace or remove public text.

### `parla guide show`

`parla guide show <artifact> [<part-or-topic>] [--topics <t,...>] [--unformatted] [--outline]` prints one document, in this order:
1. the frame: `general.md`
2. the modality's brief, and for a part, the job of its row
3. the facts of the engine page, then the modality's `engine_pages`
4. the trait presets the modality and the card select (the card wins on a kind)
5. the descriptions of the constraints marked `hint` that apply
6. the case hooks ([casebook](casebook.md#retrieval))
7. the author's preferences: every private page that applies, grouped by page key: `general`, the modality, the selected topics (each with its section for the artifact's modality), the traits, the engine pages, and the audience sections for those topics
8. the card

A name matching a part of the modality selects the part; otherwise it must match a topic, or the command fails and lists the parts and topics. The topics come from, in order: `--topics`; the topics of the active job ([jobs](jobs.md#parla-job-start-artifact---part-part---topics-t)); the topics of the part's row. With no part and no topic the load holds the system part only, and `guide list topic` shows what to choose from. An unknown topic fails and lists the known ones. A topic whose `applicable` omits the artifact's modality fails before anything prints, naming the topic and the modalities it fits. Later layers win on conflict: preferences over defaults, the card over both. A rule that names `overrides <id>` removes the overridden rule from the output.

`parla guide show --topic <t>`, `--move <m>`, `--procedure <p>` print one page, merged, with no artifact.

Default output, the view the model reads:

```
<guide artifact="icra-paper" part="introduction">
<context>frame</context>
<brief name="paper">brief</brief>
<part name="introduction">job</part>
<engine name="latex">facts</engine>
<traits>
<trait name="reader/peer">preset</trait>
</traits>
<watch>
- description of a hint constraint
</watch>
<case-hooks>
Open the cases that apply with `parla case show <ids>`.
- c-0009: parallel sentences that repeat one verb
</case-hooks>
<preferences>
<general>
- rule text
</general>
<topic name="flow">
- rule text
</topic>
<audience name="icra">
- rule text
</audience>
</preferences>
<card>decisions</card>
</guide>
```

- Rules print as bullets of their text. Ids, origins, page-kind labels and overridden notes do not print. A card with no content beyond its title prints no block.
- Only prose and `## principles` sections print. Sections named `check` do not print.
- `--unformatted` prints the Markdown form of the files instead: a header line with the word count, the target and the number of cases, a heading per section with its origin, rules as `- [id] text`, the cases in full, and a `--- overridden` line per removed rule. Humans read it, and the agent reads it to find rule ids.
- `--outline` prints the header and then one line per element of the default view, in its order: the element (`<topic name="flow">`), its words and the files its text comes from, written `$private/<path in the private root>`, `$package/<path in the installed package>` or `$project/<path in the project>`; a topic whose two files share a path reads `{$package,$private}/guides/topic/flow.md`. The `<watch>` and `<case-hooks>` lines add the ids behind them. A last line gives the roots in use. It prints no bodies and is the quickest way to find the file behind a line of the prompt.
- A load counts its words on the form it prints. Above `[guides].target_words` a warning goes to standard error. Above the target times `[guides].tolerance` the warning lists the words of each block and each topic and asks to distill or trim the guides; the command still prints the guide.

### `parla guide list [kind]`

Prints the page key of every page of both roots, one per line, such as `move/compress` or `trait/reader/peer`. A kind is one of `topic`, `modality`, `audience`, `engine`, `trait`, `move` and `procedure`. The agent finds the names it passes to `guide show` here.

`parla guide list topic [--artifact <a> [--part <p>]]` prints one line per topic, `name | words | hook`, where the words are those of the merged topic as `guide show` prints it. With an artifact it lists only the topics that apply to its modality. Without one, a limited topic ends with `| applies to <modalities>`. With an artifact it ends with a footer that gives the arithmetic of the budget:

```
system 520 words | target 1500 | tolerance 1800 | left for topics 980
topics of this part: contributions, flow, claims, citations, terminology
```

`system` is the load of the artifact and part with no topic. The last line shows the part row's topics as a hint for the captain.

### `parla guide add <page> <rule-id> --text <text> [--origin <text>] [--overrides <rule-id>] [--evidence <case-ids>] [--card <artifact>] [--hook <text>]`

Writes a rule to the private page, creating the page with its frontmatter when it does not exist. A topic page created this way needs `--hook` unless a public page of the same key exists. The rule goes under the page section `--section` names, `principles` by default; an audience page keeps its rules under a topic section. A modality or audience page that exists nowhere is not created, since its frontmatter carries required keys. With `--card`, it writes to the card's `## rules` instead. `--evidence` names cases: their ids go into the origin, and the cases are marked `distilled`. Fails on a duplicate id.

### `parla guide move <rule-id> <page>`

Moves a rule, with its origin, to another page or from a card to a private page.

### `parla guide edit <rule-id> --text <text> [--evidence <case-ids>]`

Rewrites the text of a rule of a private page or a card in place. The id and the page stay, and the origin gains `revised <date>` and the evidence ids. `--evidence` marks the cases `distilled`. The previous text goes to the [history](#history-file). Fails on an unknown id, or on a case that does not exist. The agent runs it to sharpen a rule, to absorb a new lesson into the nearest rule, or to keep a topic inside its page cap.

### `parla guide drop <rule-id>`

Removes a rule, its heading and its blockquote line, from a private page or a card, and records its text in the [history](#history-file). Fails on an unknown id and never touches a public page. The agent runs it after the author accepts, when a rule was promoted to a [constraint](constraints.md), merged into another rule, or found redundant.

### History file

`<[guides].private>/rules.history.jsonl` is append-only. Each line records one `edit` or `drop`: `date`, `action`, `rule`, `page`, the previous `text` and `origin`, and for an edit the `new_text`. No command reads it for the guide view. It lets the author recover a wording.

### Keeping a topic within its cap

After `guide add` or `guide edit` on a topic page, the command prints a warning to standard error when the page is over `[guides].max_page_words`. The warning is the cue to dedupe, generalize or merge rules ([skill](skill.md#supporting-pages)). Merging is a `guide add` of the combined rule, with the ids it replaces in `--origin`, followed by a `guide drop` of each replaced rule.

### `parla guide lint`

Prints findings in the [finding format](checks.md#finding). It reports:
- a rule heading without exactly one blockquote line, a missing origin, a duplicate id;
- an `overrides` that names no rule;
- a rule inside a public page (`public-rule`);
- a public modality page without a brief, or a part row without a job (`brief-missing`);
- a link that does not resolve;
- a topic with no hook in either root (`hook-missing`);
- a topic page over `[guides].max_page_words` (`guide-page-over-cap`);
- the system part of a modality and engine over the tolerance, or a load with every topic of a part over it (`guide-over-budget`);
- a ported rule (origin starting `texfy`) that an active case contradicts ([casebook](casebook.md#entry)).

### Budget

`[guides].target_words` (1500), `[guides].tolerance` (1.2), `[guides].max_page_words` (350) and `[guides].max_cases` (8) ([config](config.md#user-config)) size one load. The target is the recommended output of `guide show`, split roughly in half between the system part and the topics. A job that picks topics up to the target is on budget, and the tolerance absorbs a small excess. Past the tolerance, `guide show` and `job start` warn and `guide lint` reports `guide-over-budget`: a cue to distill cases into rules or trim pages, never a block on the day's work. There is no limit on the number of topics, because topics differ in size.

## Constraints

- Rule ids MUST be unique across private pages and cards.
- A public page MUST NOT hold a rule.
- A private page MUST NOT replace or remove public text.
- Every rule MUST have an origin.
- Every rule heading MUST be followed by exactly one blockquote line.
- `guide show` MUST print the same sections in the same order for the same inputs.
- `guide show --unformatted` MUST tag every section with its origin.
- `guide show` MUST NOT print a rule id, an origin, or a section named `check` in its default form.
- `guide show` MUST warn, and MUST NOT fail, when the output exceeds the target times the tolerance.
- Package guide files MUST NOT be written by any command.
- `guide add` MUST fail on a duplicate id and MUST NOT overwrite a rule.
- A load MUST NOT drop a section silently. The warning over the tolerance lists every block and topic with its words.
- `guide drop` and `guide edit` MUST NOT write a public page, MUST fail on an unknown id, and MUST record the previous text in the history.
- `guide edit` MUST keep the rule id.
- A topic MUST have a hook in one root.
- A topic MUST NOT load for a modality its `applicable` list omits, and the command MUST fail and name the modalities it fits.

## History

- [Guides and casebook](logs/2026-10-14_guides-and-casebook.md): why two memories, the rule format and the merge.
- [Agent-first rewrite](logs/2026-10-14_agent-first-rewrite.md): texfy's prompts become the starting principles.
- [Public defaults](logs/2026-10-16_public-defaults.md): why the package ships a prose brief per modality and the author's rules only append to it.
- [Lean prompts and a constraint suite](logs/2026-10-18_lean-prompts.md): the XML view, topic hooks and budgets, why checkable rules left the guides.
