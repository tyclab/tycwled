# Build, flash and acceptance

Read for this topic; paths below are relative to the repository root unless stated otherwise.

- `make lint test check-palettes check-ledmaps` before pushing; `make verify REF=<factory lamp>
TARGET=<port lamp>` is the acceptance check (~24 min, occupies both lamps, restores presets).
- PR-only main, merge commits. Verify evidence: commit the verify log (see
  `glorb/experiments/2026-08-31-reversing/verify-*.log`); capture JSONs stay untracked.
- NEVER commit anything under `glorb/firmware/` or `*/segments/` — carved vendor firmware, not
  redistributable. gitignored; keep it that way.
- `wledlab.py` is stdlib-only; keep it that way.
- Our lamps run `fleet/` builds (stock WLED updates would drop the syslog usermod): build
  with `fleet/build.sh`, flash one lamp at a time with `wledlab.py flash`, which refuses
  cfg or preset drift.
- The curtain effect census of 2026-10-07 (census, scored frames, DDP strobe capture and its
  tools) is archived outside git in `~/.local/share/tycwled/census-2026-10-07/`; its
  `ARCHIVED.md` lists the known defects. PR #30 closed it unmerged.
