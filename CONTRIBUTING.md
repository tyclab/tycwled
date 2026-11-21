# Contributing

Everything here was measured on two GLORB lamps (one factory, one ported).
Your lamps may disagree — that is useful information, please report it.

## Report what you see

Open an issue with:

- firmware versions of the lamps involved (`/json/info` → `ver`),
- the preset number and what differs (motion, colour, brightness, mapping),
- if you can: run `python3 wledlab.py capture --host <lamp> --seconds 120 --out
capture.json` and post the output of `python3 wledlab.py analyse capture.json`,
  or the summary of a `make verify` run if you have a factory lamp next to it.
  Keep `capture.json` itself: a recording stays with you, the analysis is what
  an issue needs.

## Lint hooks and tests

```bash
pip install pre-commit   # once, if you do not have it
make install-hooks       # one-time per clone
make lint                # pre-commit over the tree + ledmap/palette checks
make test                # offline palette-emulation tests, seconds
```

Hooks: the private-data check, gitleaks, yamllint, markdownlint-cli2, prettier
(never on the lamp files under `glorb/`, which are byte-exact), ruff-check.
`make install-hooks` installs them for commits and for pushes. CI runs the same
`make lint` and `make test`, plus a gitleaks scan of the history.

The private-data check (`tools/check_private_lamp_data.py`) reads file content,
compressed files included, in the staged tree, in every commit of a push and in
every commit of a pull request. It refuses recordings, device backups, MAC
addresses, private network addresses, Wi-Fi names and coordinates, and a branch
that starts from the history before the recordings were removed. Tests and
examples use documentation values: MACs from `00:00:5E:00:53:00` to `…:FF`,
addresses from `192.0.2.0/24`, network names that start with `example`.

## Change something

1. Fork, branch, edit — one change per pull request.
2. Palettes are generated: edit `PLAN` in `glorb/mkpalettes.py`, run
   `python3 glorb/mkpalettes.py` (`--check` only compares, `--report` prints
   the residual vs the fork); do not hand-edit `paletteN.json`.
3. `make lint` and `make test` green.
4. If you touched presets, palettes, ledmap or cfg overrides, paste the
   `make verify` table from your lamps into the pull request — or say that
   you could not run it, that is fine too.
5. Add a `## [Unreleased]` entry to [`CHANGELOG.md`](CHANGELOG.md) for
   anything user-visible.
6. Open the pull request against `main`. Main is protected: changes land
   through pull requests only, after CI is green.

## Reporting problems

Bugs and improvements go to the issue tracker; the forms ask for what is
usually needed. **Security vulnerabilities do not** — see
[`SECURITY.md`](SECURITY.md) for the private channel.

By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

Keep the notes in the README present-tense: what is, and what needs to be —
not what used to be.
