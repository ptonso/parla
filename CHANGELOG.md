# Changelog

## 0.0.2 - 2026-10-28

### Added

- `parla job changes <artifact>` prints the unified diff of the source against the newest job's snapshot, active or ended.
- `parla init --local` keeps `parla/` a real directory even when `[storage].asset_root` is set.
- `parla guide add` reads a bare page name such as `flow` as a topic.
- `parla export` traces Beamer themes (`\usetheme`, `\usecolortheme`, `\usefonttheme`, `\useinnertheme`, `\useoutertheme`) into the packaged dependencies.
- The skill lists the signs that a job has ended and what the agent does at each.

### Changed

- The default `[guides].target_words` is 1500 (was 1000), and the limit with the default tolerance is 1800 words (was 1200).
- A guide over `target_words * tolerance` warns on standard error and asks for distilling. `guide show` and `job start --topics` no longer fail.
- The error for a pre-existing `parla/` symlink under local storage names `--local` as a cause.

### Fixed

- `parla check` no longer scans build outputs such as `BUILD-ERROR.txt`, which counted their own errors again on each failed build.
