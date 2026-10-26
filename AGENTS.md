# AGENTS.md — tycwled

Port of the GLORB lamp firmware to stock WLED with measured equivalence. README
owns setup; the reversing record is `glorb/experiments/2026-08-31-reversing/NOTES.md`.

- Prove mechanisms offline against factory bytes, disassembly or a model before
  flashing. `make verify` confirms a fix; it is not an iterative search tool and
  can pass on cancelling errors. Never widen tolerances to pass a preset;
  justify any change with offline rescore over saved captures.
- Factory palettes are byte-exact; presets match field-for-field except fx/pal.
  Preserve the palette, preset and effect-ID tests. Find gamma, topology or
  rounding mechanisms instead of fitting the reference data.
- Identify a controller from its live MAC/IP before writing; old role labels are
  not reliable. One measurement job per lamp, one flash at a time. Respect
  configured drift refusals and the current authorized hardware scope.
- Never commit vendor firmware under `glorb/firmware/` or `*/segments/`.
  Captures stay untracked; commit the acceptance verify log. Keep wledlab.py
  standard-library-only and preserve the fleet build's required usermods.
- Main is PR-only with merge commits. Preserve that merge policy, hooks and CI.
  Keep private addresses, personal/employer details and credentials out of this
  public repo; use the repo-local identity or a GitHub noreply address.

Keep code/config comments at or below 20% of nonblank lines; preserve licenses,
tool directives and runtime descriptions. Only the operator may grant a documented,
file-specific exception. See the shared [maintenance policy](https://github.com/tyclab/flakelab/blob/main/docs/agents/maintenance.md)
for exclusions and counting rules. Remove code only with evidence that behavior and
callers are preserved; keep README commands and diagrams aligned with code.

## Read before the task

- Effects, gamma, palettes, microphones, measurements or transport:
  [measurement traps](docs/agents/measurement.md).
- Builds, flashing, acceptance or publishing: [workflow](docs/agents/workflow.md).

Run `make lint test check-palettes check-ledmaps` before publishing. Hardware
acceptance uses the documented verify path and records its evidence.

Keep repository-wide instructions here; put task-specific guidance in `docs/agents/`
and link it from this file. README owns human setup and architecture; plans hold open work only.
