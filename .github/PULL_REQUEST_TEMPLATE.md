## What this changes

<!-- One or two sentences. Link the issue if there is one: Fixes #123 -->

## Why

<!-- The measurement or report that motivated it. -->

## Checklist

- [ ] `make lint` passes (pre-commit suite plus the repo checks — CI runs the same target).
- [ ] `make test` passes.
- [ ] Palettes, presets, ledmap or cfg overrides changed → the `make verify` table from my lamps is below, or I say why I could not run it.
- [ ] `CHANGELOG.md` has an entry under `## [Unreleased]` if this is user-visible.
- [ ] No Wi-Fi credentials, tokens, private hostnames or coordinates in the diff (a raw `cfg.json` carries all four).

## `make verify` / measurements

<!-- Table or "could not run". -->

## Anything a reviewer should know

<!-- Sharp edges, things you decided against, follow-up work. -->
