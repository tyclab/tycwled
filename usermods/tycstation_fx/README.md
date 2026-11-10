# tycstation_fx — the TycStation squid patterns as WLED effects

Three effects and one palette for WLED 16.0.1, ported from the squid drawings in
[`curtain/squid/draw.js`](../../curtain/squid/draw.js) (the patterns only; the squid
figure stays a GIF for the Image effect). Every effect runs on 1D and 2D segments of
any size and renders each frame from the time alone, without reading pixels back.

- **Squid Arms** — `armWaves()`: the gradient along the row, blue end to red end, with
  waves running outward from the middle, one period per 2 s; on a matrix every row is the
  same. Custom 1 _Waves_ (default 64): 1 + c1/64 waves on each half, halved under 16 LEDs
  as drawn. Sound sets the wave height.
- **Squid Skin** — `LOOPS.f`'s cells: a jittered grid pulsing in four patterns over 12 s
  (diagonal waves, rings from the middle, a sweep, each cell at its own rate). Custom 1
  _Cell size_ (default 85): cells 2 + 6·c1/255 LEDs apart (4 at 85, as drawn on the
  curtain), at most a third of a matrix's short side. Sound sets the cells' pulse strength.
- **Squid Plankton** — `LOOPS.c`'s water: specks rising through the water gradient and
  twinkling, over 16 s; a strip is the water column, its first LED at the surface.
  Custom 1 _Specks_ (default 32): the drawing's density (44 per 68 × 42 cells) times
  c1/32; a strip counts as a column 2 LEDs wide. Sound sets the twinkle depth.

Speed (default 128) runs the drawing's own pace and doubles or halves it every 64 steps.
Sound (default 192) at 0 ignores the microphone and keeps the drawing's full pulse. Above
0, the AudioReactive usermod's smoothed volume (`volumeSmth`) sets the pulse: at 128 or
more (the full scale of WLED's own Gravimeter) it is the drawing's, in silence it drops
to 1 − Sound/510 of that (half at 255, 0.62 at 192), and the pattern keeps moving.
Without sound data (no AudioReactive, or it is disabled) the pulse is the drawing's.

## Palette

The effects default to palette 0, which draws the mark's gradient exactly from the
TycStation stops (positions 0, 61, 128: blue, violet, red); so does the TycStation
palette itself. Any other palette runs end to end. Plankton's specks take the drawn blue,
violet and eye colours; with another palette they take its colours at 0, 1/3 and 2/3.

The usermod registers the stops of [`fleet/tycstation/mkpalette.py`](../../fleet/tycstation/mkpalette.py)
as a usermod palette named `TycStation`, which WLED 16.0.1 lists as "TycStation 0" (it
always appends an index or a sub-name to usermod palettes). It goes first in the
usermod palette list, so its ID is 255 on every lamp; AudioReactive's palettes, where
enabled, follow it at 254 and below. Stock effects can use it like any palette.

## Gamma

WLED 16 gamma-corrects every pixel in `show()` when colour gamma is on. The drawings are
meant for the 2.8 table the curtain, the couch and the Moon run. On a lamp with colour
gamma off (the GLORBs, `glorb/wled16-port/cfg-overrides.json`) the effects apply WLED's
2.8 table to every pixel they write, and the registered palette holds the 2.8-encoded
stops (as `fleet/tycstation/glorb/palette6.json` does), so both kinds of lamp put the
same values on the wire. The usermod follows a change of the setting at runtime. A lamp
with colour gamma on applies its own table, whatever its value.

## Effect IDs

The effects register with `addEffect(255, …)`, so WLED assigns their IDs at boot; check
presets by name. On the fleet's v16.0.1 builds the stock table leaves 142, 169, 170 and
171 free: without glorb_fx the effects take 142, 169 and 170; on the GLORBs glorb_fx
registers first and they follow at 222 to 224.

## Tests

`tests/test_tycstation_fx.py` checks the metadata strings, the stops and the 2.8 table
against `mkpalette.py`, and compiles `tests/tycstation_fx_host.cpp`, which renders
[`tycstation_core.h`](tycstation_core.h) on the host, against the committed squid GIFs.
