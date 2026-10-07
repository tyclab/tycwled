# Curtain effect census, 2026-10-07

Measured on tyccurtain (Gledopto, WLED 16.0.1 tycwled build, 68×42 matrix, 1560 mapped LEDs)
with `wledlab.py capture` over the websocket liveview. The liveview raster is the matrix
downsampled 2:1 per row (34×42 = 1428 cells); the Solid effect lights 27.3 % of it, which is
the "everything on" baseline every coverage figure is normalised to.

## Native effects (`census.jsonl`, `census-scored.json`, `frames/`)

`census.py`: every effect set with `fxdef:true` (WLED's own slider defaults), then
`sx 200, ix 180, pal 9 (Ocean)`, 1.5 s settle, 3.5 s capture. Per effect: lit share (cells
above 35 % value) and its range, change rate per liveview frame (~12 Hz), blue and white hue
shares, saturation, value, the fxdata string (4th field flags: `2` = 2D, `v`/`f` = needs
audio) and the sliders that were in force. `rank2.py` re-scores the frames and ranks them against the operator's phone video of
2026-10-05 04:42. The video is measured by `gifcrop.py` inside the window crop
(x 75-250, y 70-450 of the 361×640 GIF), counting only pixels brighter than 150/255 so the
blue room glow does not count as curtain (`video-crop-metrics.json`: lit 0.38, range
0.23-0.56, blue 0.98, white 0.01, sat 0.75). The score is a rough distance, not an
identification: the video is bloomed camera footage, the liveview is pre-gamma pixel data.
`sheet-crop-top.png` shows the cropped video over the eight best-scoring effects; the
measured first place, PS Waterfall (196), is also the effect the operator singled out while
the census ran. Its own defaults are palette Ocean, speed 15, intensity 200.

The AudioReactive usermod was **on** with the PDM mic and the room quiet, so sound-reactive
effects (`v`/`f`) are measured in silence and show their idle state. Swirl (175), the
reconstruction from HA history, is one of them: it is static in silence.

## Streamed DDP (`strobe-ddp-liveview.json.gz`, `strobe2.py`)

Full-panel square-wave strobes over DDP (2856 pixels, 1200-byte packets) at 5, 10 and 20 Hz
in white then blue, 3.5 s each, a 1 s black gap, a 3.5 s white hold, then black; phase start
times are in `meta.phases` (seconds since the sender started; the capture clock runs ~1.0 s
later, see `capture_offset_s`). Liveview ran at ~10 Hz, so the 10 and 20 Hz phases alias:
what the capture proves is that the panel toggles fully (lit 0.00 to 1.00 in every phase)
and holds white at full coverage, not the true visible rate above ~5 Hz.

Caveat found on the way: DDP packets of 1440 data bytes sent from a host on the overlay
network (10.29.0.2) lit only three matrix rows; 1200-byte and smaller packets lit the whole
panel. A tunnel MTU is the likely cause; untested from the LAN (tychome).
