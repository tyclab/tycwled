# Contributing

Everything here was measured on two GLORB lamps (one factory, one ported).
Your lamps may disagree — that is useful information, please report it.

## Report what you see

Open an issue with:

- firmware versions of the lamps involved (`/json/info` → `ver`),
- the preset number and what differs (motion, colour, brightness, mapping),
- if you can: `python3 wledlab.py capture --host <lamp> --seconds 120 --out
  capture.json` and the output of `python3 wledlab.py analyse capture.json`,
  or a `make verify` run if you have a factory lamp next to it.

## Change something

1. Fork, branch, edit.
2. Palettes are generated: edit `PLAN` in `glorb/mkpalettes.py` and run it,
   do not hand-edit `paletteN.json`.
3. `make lint` must pass (CI runs it on every pull request).
4. If you touched presets, palettes, ledmap or cfg overrides, paste the
   `make verify` table from your lamps into the pull request — or say that
   you could not run it, that is fine too.
5. Open the pull request against `main`. Main is protected: changes land
   through pull requests only, after CI is green.

Keep the notes in the README present-tense: what is, and what needs to be —
not what used to be.
