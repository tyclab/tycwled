# GLORB.1.3 firmware — reverse-engineering of 6 custom 2D effects

Date: 2026-08-31
Input: `glorb/firmware/firmware_gma_83_debug.bin` (ESP-IDF app image, ESP32-S3 / Xtensa LX7 LE).
Fork: WLED 0.14.4 "GLORB.1.3". No app symbols in the image.
Stock reference: WLED v0.14.4 `wled00/FX.cpp` + `FX.h` (fetched; copies in scratch as `FX_v0.14.4.cpp/.h`).

Goal: faithful C pseudocode for the 6 target effects, each reported as a **delta vs its
stock 0.14.4 ancestor**.

---

## 1. Pipeline / how to reproduce

### 1.1 Image → segments (`parse_image.py`)
ESP-IDF v4.4.3 image, `esp_image_header_t` = 24 bytes, chip_id 9 (ESP32-S3), 6 segments:

| seg | load addr    | size      | region |
|-----|--------------|-----------|--------|
| 0   | 0x3c160020   | 0x6f1a8   | DROM (.rodata / const strings) |
| 1   | 0x3fc98d90   | 0x0e48    | DRAM |
| 2   | **0x42000020** | 0x15a914 | **IROM (.flash.text — all effect code)** |
| 3   | 0x3fc99bd8   | 0x6224    | DRAM |
| 4   | 0x40374000   | 0x14d90   | IRAM (fast-path code, incl. setPixelColorXY) |
| 5   | 0x50000000   | 0x10      | RTC |

`python3 parse_image.py <bin> segments_debug`

### 1.2 Disassembly
Ghidra 12 (nixpkgs) was a dead end: the nixpkgs `ghidra` closure that resolved was
incomplete (no `Ghidra/Processors`, dangling `support/analyzeHeadless`), and mainline
Ghidra ships **no** Xtensa processor module anyway. Capstone 5.0.7 (pip) has no Xtensa
(only capstone-next). **radare2 6.1.8** (`nix shell nixpkgs#radare2`) has a working Xtensa
decoder — used for everything here. Disassembly is decode-only (no decompiler), so the C
below is hand-lifted from the instruction stream, anchored on the exact stock source.

`./disasm.sh 0x4204321c 170`  (maps IROM at 0x42000020, `-a xtensa -b 32`)

### 1.3 Mode table (fx-ID → string → function)
Found the 12 fork mode-metadata strings in DROM, then their `{const char* data, fx_func}`
pairs in an IROM table at **0x4203ea80** (16-byte stride pairs `[str_ptr, func_ptr]`), in
fx-ID order 187..198. Targets:

| fx | effect      | metadata string @DROM | **func @IROM** |
|----|-------------|-----------------------|----------------|
|193 | Hiphotic    | 0x3c167426 | **0x4204321c** |
|192 | Black Hole  | 0x3c1673f0 | **0x420430c0** |
|191 | Frizzles    | 0x3c16745a | **0x42043560** |
|189 | Colorwaves  | 0x3c1674ba | **0x42042e48** |
|190 | Running     | 0x3c167489 | **0x420433b4** |
|195 | Tartan      | 0x3c16738c | **0x42043b28** |

(Full table also covers 187 Static 0x4203df64, 188 Colorloop 0x4203df90, 194 Swirl
0x420436e0, 196 Pulse Wave 0x42042bf0, 197 Gradient Flow 0x4203e130, 198 Fold 0x4203e350.)

### 1.4 Helper functions identified (by structure + stock cross-ref), all high confidence
| addr | identity |
|------|----------|
| 0x4203df64 | `mode_static()` (the `if(!strip.isMatrix) return mode_static()` bailout) |
| 0x4214f340 | `Segment::virtualWidth()` → cols |
| 0x4214f384 | `Segment::virtualHeight()` → rows |
| 0x4203ded8 | `sin8(uint8_t)` — classic FastLED table lookup, table @0x3c167ab8 |
| 0x4204307c | `beatsin8(accum88 bpm, uint8_t low, uint8_t high, uint32_t tb, uint8_t phase)` |
| 0x42042bb8 | `beatsin88(accum88 bpm, uint16_t low, uint16_t high, ...)` |
| 0x42042e08 / 0x42152f58 | `beatsin16(bpm, int16 low, int16 high, ...)` |
| 0x4203de90 | `sin16(uint16_t)` |
| 0x42018ed4 | `Segment::color_from_palette(idx, mapping, wrap, mcol, pbri=255)` |
| 0x4214eb50 | FastLED `ColorFromPalette(pal, idx, bri, LINEARBLEND)` (SEGPALETTE @0x3fc9fe80) |
| 0x4202617c | `color_blend(c1, c2, blend, bool)` |
| 0x42017834 | `Segment::blendPixelColor(i, color, blend)` |
| 0x42017864 | `Segment::addPixelColorXY(x, y, color)` (2D) |
| 0x42011c2c | `Segment::addPixelColorXY(x, y, color)` (variant used by Frizzles/Tartan) |
| 0x4201741c | `Segment::getPixelColorXY(x, y)` (bounds-checked; returns 0 if OOB) |
| 0x40375538 | `Segment::setPixelColorXY(x, y, color)` (IRAM) |
| 0x403757e8 | `Segment::setPixelColor(i, color)` (IRAM, 1D) |
| 0x420194f4 | `Segment::fadeToBlackBy(uint8_t rate)` |
| 0x420195a0 | `Segment::blur(uint8_t)` |
| 0x4201902c | `Segment::fill(uint32_t)` |
| 0x420842f4 | millis()/strip.now getter (Black Hole timebase) |

### 1.5 Segment field byte offsets (from FX.h 0.14.4; runtime offsets confirmed against
the binary, e.g. Colorwaves reads step@44 / aux0@52 exactly where stock uses SEGENV.step/aux0)
```
+6  speed(u8)   +7 intensity(u8)   +8 palette(u8)
+16/+20/+24 colors[0..2](u32)
+29 custom1(u8) +30 custom2(u8)
+31 {custom3:5, check1:bit5, check2:bit6, check3:bit7}(u8)   // bit29 of the u32@+28 = check1
+44 step(u32)   +48 call(u32)   +52 aux0(u16)   +54 aux1(u16)
```
`strip` global @0x3fca72a8; `strip+16` = isMatrix; `strip+128` = current segment id;
`strip+60` = segments array base; sizeof(Segment)=68 (index = base + 68*id).

---

## 2. HIPHOTIC  (fx 193, func 0x4204321c)  — CONFIDENCE: HIGH

### Stock `mode_2DHiphotic()` (0.14.4)
```c
const uint32_t a = strip.now / ((SEGMENT.custom3>>1)+1);
for (x) for (y)
  setPixelColorXY(x, y, color_from_palette(
     sin8( cos8(x*SEGMENT.speed/16 + a/3) + sin8(y*SEGMENT.intensity/16 + a/4) + a ),
     false, PALETTE_SOLID_WRAP, 0));
```
Stock metadata `"Hiphotic@X scale,Y scale,,,Speed;!;!;2"` (sx=Xscale, ix=Yscale, c3=Speed).

### Fork metadata `"Hiphotic@Speed,Hue variation,X scale,Y scale;!;!;2g"`
→ sx=Speed, ix=Hue variation, c1=X scale, c2=Y scale.

### Recovered fork pseudocode
```c
if (!strip.isMatrix) return mode_static();
uint16_t cols = SEGMENT.virtualWidth(), rows = SEGMENT.virtualHeight();

// --- per-frame phase: an INTERNAL accumulator in SEGMENT.step, not strip.now ---
SEGMENT.step = SEGMENT.step + (SEGMENT.speed>>6) + 1;   // stored back at end of frame
uint16_t a = SEGMENT.step;                              // "a" timebase (16-bit)

// per-frame intensity-driven modulation (NEW vs stock):
uint8_t shift  = 3 - (SEGMENT.intensity>>6);            // ix=14 ->3, ix=128 ->1, ix>=192 ->0
uint8_t himask = ~(0xFF >> shift) & 0xFF;               // ix=14 ->224, ix=128 ->128
uint8_t bwave  = beatsin8(2, 0, himask, /*tb*/0, /*ph*/0);   // NEW oscillator

uint8_t xstep = (SEGMENT.custom1>>5) + 8;   // c1=X scale  -> 8..15   (stock: speed/16)
uint8_t ystep = (SEGMENT.custom2>>5) + 8;   // c2=Y scale  -> 8..15   (stock: intensity/16)
uint8_t xbase = (a/3) + 64;                 // +64 folds cos8 into sin8 (cos8(t)==sin8(t+64))
uint8_t ybase = (a/2)>>1;                   //  == a/4  (stock a/4)

uint8_t hx = xbase;                          // per-x accumulator
for (int x = 0; x < cols; x++, hx += xstep) {
  uint8_t hy = ybase;                        // per-y accumulator
  for (int y = 0; y < rows; y++, hy += ystep) {
    uint8_t v = sin8( sin8(hy) + sin8(hx) + (uint8_t)a );   // sin8(hx)==cos8(x*xstep+a/3)
    uint8_t idx = (v >> shift) + bwave;                     // palette index (NEW modulation)
    uint32_t col = SEGMENT.color_from_palette(idx, false, PALETTE_SOLID_WRAP, 0, 255);
    uint32_t out = color_blend(SEGMENT.getPixelColorXY(x,y), col, 64);  // 64/255 temporal blend
    SEGMENT.setPixelColorXY(x, y, out);
  }
}
```

### Delta vs stock
1. **Timebase**: stock `a = strip.now/((c3>>1)+1)`. Fork keeps a persistent phase in
   `SEGMENT.step`, incremented **`+(speed>>6)+1` per frame** and written back. So the
   **Speed** slider (sx) is a genuine speed control; strip.now and custom3 are gone.
2. **Coefficients**: stock `x*speed/16`, `y*intensity/16`. Fork uses per-step increments
   `xstep=(c1>>5)+8` and `ystep=(c2>>5)+8` (both clamp to 8..15). c1="X scale", c2="Y scale".
3. **cos8** is implemented as `sin8(hx)` with the `+64` baked into `xbase` — mathematically
   identical, no behavioural delta.
4. **NEW palette-index modulation** (not in stock): `idx = (v >> shift) + beatsin8(2,0,himask)`,
   with `shift = 3-(ix>>6)` and `himask = ~(0xFF>>shift)`. Both driven by **Intensity/"Hue
   variation"** (ix). Stock fed `v` straight in as the index at full brightness.
5. **NEW temporal blend**: fork writes `color_blend(getPixelColorXY, newcol, 64)` — a 64/255
   crossfade with the previous frame — instead of a hard `setPixelColorXY`. Smooths motion.
6. color_from_palette brightness arg is fixed 255 (as stock).

### Why "Hue variation" (ix) produces the bimodal / black-gap look at ix=128 but not ix=14
The index is `idx = (v >> shift) + bwave`, and `v = sin8(...)` spans 0..255.
- **ix=14**: `shift=3` → `v>>3` spans only **0..31**; `bwave` = beatsin8(2,0,**224**). The index
  is a slow beat baseline (0..224) plus a *small* ±31 ripple → the palette pointer stays in a
  narrow, slowly-drifting window → smooth, no dark gaps.
- **ix=128**: `shift=1` → `v>>1` spans a **wide 0..127**; `bwave` = beatsin8(2,0,**128**). Now the
  per-pixel ripple is ~4× larger and, added to the beat, the index sweeps most of the palette
  every frame — crossing the palette's dark/black entries — which reads as **bimodal brightness
  and black gaps**. Higher ix ⇒ smaller right-shift ⇒ larger index excursion ⇒ more of the
  palette (including black) is traversed. The decompiled math fully explains the observation.

Sanity vs presets: p2 (sx72 ix14 c1128 c2128 c316) and p14 (sx52 ix128 c164 c2190) both fall in
range; ix14→shift3 (smooth), ix128→shift1 (bimodal), consistent with the reported behaviour.
(custom3=16 in p2 is now unused by this effect — confirms c3 no longer wired here.)

Repro: `dis_hiphotic.txt` (0x4204321c). Literal pool consts: /3 magic 0xaaaaaaab @0x4203e914.

---

## 3. BLACK HOLE  (fx 192, func 0x420430c0)  — CONFIDENCE: HIGH (structure), MED (phase detail)

### Stock `mode_2DBlackHole()`: fadeToBlackBy(16+speed>>3); t=millis()/128; **8 outer stars**
(beatsin8 x/y over full grid) + **4 inner stars** + **central WHITE dot** + blur(16).
Stock metadata: `"Black Hole@Fade rate,Outer Y freq.,Outer X freq.,Inner X freq.,Inner Y freq.,Solid;...;2;pal=11"`.

### Fork metadata `"Black Hole@X scale,Y scale,Intensity,Fade rate;!;!;2g"`
→ sx=X scale, ix=Y scale, c1=Intensity, c2=Fade rate.

### Recovered fork pseudocode
```c
if (!strip.isMatrix) return mode_static();
uint16_t cols = virtualWidth(), rows = virtualHeight();

SEGMENT.fadeToBlackBy(SEGMENT.custom2 >> 4);      // c2="Fade rate"   (stock: 16 + speed>>3)
uint32_t t8 = millis_getter() >> 7;               // == millis()/128  (t, 8-bit)

uint8_t count = (SEGMENT.custom1>>6) + 2;          // c1="Intensity" -> 2..5 stars
for (size_t i = 0; i < count; i++) {
  uint8_t xphase = i * (t8 - 128);                 // (see note)  stock: ((i%2)?128:0)+t*i
  uint8_t yphase = (i&1 ? 192 : 64) + i * t8;      // matches stock parity+t*i
  uint16_t x = beatsin8((SEGMENT.speed>>5)+1,  cols/2, (cols*5)/2 - 1, 0, xphase);
  uint16_t y = beatsin8((SEGMENT.intensity>>4)+1, 1,    rows - 2,       0, yphase);
  uint32_t col = SEGMENT.color_from_palette(i*63, false, PALETTE_SOLID_WRAP,
                                            SEGMENT.check1?0:255);
  SEGMENT.addPixelColorXY(x % cols, y, col);       // X taken modulo width (wraps)
}
SEGMENT.blur(32);                                  // stock: blur(16)
return FRAMETIME;
```

### Delta vs stock
1. **Only ONE star loop** — the 4 inner stars **and** the central white dot are **removed**.
2. **Star count is variable** `(custom1>>6)+2` (2..5), driven by **Intensity** (c1). Stock: fixed 8.
3. **X beatsin range is widened to `[cols/2, cols*5/2-1]` then taken `% cols`** — X wraps around
   the matrix (a recurring fork idiom, also in Frizzles). Y range `[1, rows-2]`. Stock: `[0,cols-1]`/`[0,rows-1]`.
4. **bpm wiring**: X bpm `(speed>>5)+1` (sx="X scale"), Y bpm `(intensity>>4)+1` (ix="Y scale").
   Stock: `custom1>>3` / `intensity>>3`.
5. **fade** `custom2>>4` (c2="Fade rate"); **blur 32** (stock 16).
6. **palette index `i*63`** (stock `i*32`). `check1` still selects the solid-wrap mcol (0 vs 255).
7. X-phase accumulation differs slightly from stock's `((i%2)?128:0)+t*i` (fork accumulates
   `i*(t-128)`); low confidence on that exact term, high on everything else.

Repro: `dis_blackhole.txt` (0x420430c0). Single loop 0x4204314b→0x4204320d; blur(32)@0x42043212.

---

## 4. FRIZZLES  (fx 191, func 0x42043560)  — CONFIDENCE: HIGH (structure/wiring), MED (exact bpm shifts)

### Stock `mode_2DFrizzles()`
```c
fadeToBlackBy(16);
for (i=8; i>0; i--)
  addPixelColorXY(beatsin8(speed/8 + i, 0, cols-1),
                  beatsin8(intensity/8 - i, 0, rows-1),
                  ColorFromPalette(SEGPALETTE, beatsin8(12,0,255), 255, LINEARBLEND));
blur(custom1>>3);
```
Stock metadata `"Frizzles@X frequency,Y frequency,Blur;;!;2"` (sx,ix,c1).

### Fork metadata `"Frizzles@X scale,Y scale,Blur,Intensity;!;!;2g"`
→ sx=X scale, ix=Y scale, c1=Blur, **c2=Intensity (NEW slider)**.

### Recovered fork pseudocode
```c
if (!strip.isMatrix) return mode_static();
uint16_t cols = virtualWidth(), rows = virtualHeight();

SEGMENT.fadeToBlackBy(8);                          // stock: 16

int count = (SEGMENT.custom2>>5) + 1;              // c2="Intensity" -> 1..8 points (stock: fixed 8)
for (int i = count; i > 0; i--) {
  uint16_t x = beatsin8(i + (SEGMENT.speed>>5),      cols/2, (cols*5)/2 - 1);  // sx="X scale"
  uint16_t y = beatsin8((SEGMENT.intensity>>6)+8 - i, 1,      rows - 2);        // ix="Y scale"
  uint8_t  h = beatsin8(12, 0, 255);
  uint32_t c = ColorFromPalette(SEGPALETTE, h, 255, LINEARBLEND);
  SEGMENT.addPixelColorXY(x % cols, y, c);         // X modulo width (wraps), as Black Hole
}
SEGMENT.blur((SEGMENT.custom1>>4) + 4);            // c1="Blur"  (stock: custom1>>3)
return FRAMETIME;
```

### Delta vs stock
1. **NEW slider c2="Intensity"** sets the point count `(c2>>5)+1` (1..8). Stock: fixed 8.
2. **X beatsin range widened to `[cols/2, cols*5/2-1]` then `% cols`** (wrap); Y `[1, rows-2]`.
   Stock: `[0,cols-1]` / `[0,rows-1]`.
3. **bpm**: X `i + (speed>>5)` (stock `speed/8 + i`); Y `(intensity>>6)+8 - i` (stock `intensity/8 - i`).
   Note the different shift amounts (>>5, >>6) and the `+8` on Y — MED confidence on these exact
   shifts, HIGH that speed→X-bpm and intensity→Y-bpm as `±i`.
4. **fade 8** (stock 16); **blur `(c1>>4)+4`** (stock `c1>>3`). c1="Blur".
5. Color index `beatsin8(12,0,255)` and SEGPALETTE/LINEARBLEND — **unchanged**.

Repro: `dis_frizzles.txt` (0x42043560). Loop 0x420435f1→0x420436bb; `rems x,cols`@0x4204365a.

---

## 5. COLORWAVES  (fx 189, func 0x42042e48)  — CONFIDENCE: MED-HIGH

### Stock `mode_colorwaves()` — 1D over SEGLEN, uses SEGENV.step/aux0, beatsin88 set
`brightdepth=beatsin88(341,96,224)`, `brightnessthetainc16=beatsin88(203,25*256,40*256)`,
`msmultiplier=beatsin88(147,23,60)`, `hueinc16=beatsin88(113,60,300)*intensity*10/255`,
`sHue16 += duration*beatsin88(400,5,9)`, `duration=10+speed`; per pixel a squared-sine
brightness and `blendPixelColor(i, color_from_palette(hue8,...), 128)`.

Stock metadata `"Colorwaves@!,Hue;!;!"` (sx=speed, ix=Hue).

### Fork metadata `"Colorwaves@Speed,Intensity,,,,Sound Reactive;!;!;2vg"`
→ sx=Speed, ix=Intensity, **check1="Sound Reactive"**, and the effect is **rendered over the
2D grid** (the `;2` + `v` flags; the `g` = ledmap).

### Recovered structure (helpers all confirmed)
```c
if (!strip.isMatrix) return mode_static();
cols=virtualWidth(); rows=virtualHeight();
uint16_t sPseudotime = SEGMENT.step, sHue16 = SEGMENT.aux0;      // +44 / +52 (== stock SEGENV)
uint8_t  brightdepth          = beatsin88(341, 96, 224);
uint16_t brightnessthetainc16 = beatsin88(203, 25*256, 40*256);
uint8_t  msmultiplier         = beatsin88(147, 23, 60);
uint16_t hueinc16             = /* from beatsin88(113,60,300), see delta */;
uint16_t duration = 10 + SEGMENT.speed;
// ... if (check1) { pull audio (getAudioData @0x42150ba4) and fold FFT/volume into
//                   hueinc16/duration via float path } ...
sPseudotime += duration*msmultiplier;  sHue16 += duration*beatsin88(400,5,9);
for (each pixel p in the 2D grid, index i) {
  hue16 += hueinc16; hue8 = fold(hue16);
  b16 = sin16(brightnesstheta16 += brightnessthetainc16) + 32768;
  bri16 = (b16*b16)/65536; bri8 = (bri16*brightdepth)/65536 + (255-brightdepth);
  SEGMENT.blendPixelColor(i, SEGMENT.color_from_palette(hue8, false, PALETTE_SOLID_WRAP, 0, bri8), 128);
}
SEGMENT.step = sPseudotime; SEGMENT.aux0 = sHue16;
```

### Delta vs stock
1. **Rendered over the 2D matrix** (nested cols×rows) rather than 1D SEGLEN; uses the
   fork's 2D `color_from_palette`/`blendPixelColor` path.
2. **NEW `check1` = Sound Reactive** branch (`bbci check1` @0x42042eef → float/audio path at
   0x42042fed calling audio getter 0x42150ba4, `utrunc.s`/`quos`). When on, audio data feeds
   the hue increment / step; when off, the pure-time stock math runs.
3. **hueinc16 / duration** — CORRECTED in §10.3 (this earlier text was wrong; I had conflated
   two separate quantities). Definitive: SR-off `hueinc16 = beatsin88(113,60,300)*(intensity>>3)*10/255`
   and `duration = (speed>>4)+10`. See §10.3 for the full trace and the SR-on form.
4. All five beatsin88 magic constants (341/96/224, 203/6400/10240, 147/23/60, 113/60/300,
   400/5/9) are **byte-for-byte identical to stock** — confirms this is the colorwaves engine.
5. step@44 / aux0@52 persistence identical to stock SEGENV.step / SEGENV.aux0.

Repro: `dis_colorwaves.txt` (0x42042e48). beatsin88=0x42042bb8, sin16=0x4203de90, blendPixelColor=0x42017834.

---

## 6. RUNNING  (fx 190, func 0x420433b4)  — CONFIDENCE: MED-HIGH (1D port + wiring), MED (palette-index detail)

### Stock `mode_running_lights()` → `running_base(false)`
```c
uint8_t  x_scale = intensity >> 2;
uint32_t counter = (strip.now * speed) >> 9;
for (i<SEGLEN) {
  uint16_t a = i*x_scale - counter;
  uint8_t  s = sin8(a);
  setPixelColor(i, color_blend(SEGCOLOR(1), color_from_palette(i,true,PALETTE_SOLID_WRAP,0), s));
}
```
Stock metadata `"Running@!,Wave width;!,!;!"` (sx=speed, ix=Wave width).

### Fork metadata `"Running@Speed,Wave width,,,,Sound Reactive;!;!;g"`
→ sx=Speed, ix=Wave width, **check1="Sound Reactive"**. Still **1D** (no `2` flag).

### Recovered fork pseudocode
```c
uint8_t sr = SEGMENT.check1;                       // bit29 of u32@+28
uint8_t x_scale = (SEGMENT.intensity >> 2) + 12;   // ix="Wave width"  (stock: intensity>>2, no +12)
uint32_t counter = (SEGMENT.speed >> (sr ? 7 : 6)) + 1;   // base rate; stock: (strip.now*speed)>>9
// counter is persisted via SEGMENT.step(+44)/aux0(+52) and, when sr, incremented by an
// audio-derived term (getAudioData @0x42150ba4, float→ (fftResult>>? & 0x7ff)).
counter += SEGMENT.step; ...                        // accumulator, written back at end
for (int i = 0; i < SEGLEN; i++) {
  uint16_t a = i*x_scale + phase;                   // running phase
  uint8_t  s = sin8((uint8_t)a);
  uint32_t pcol = SEGMENT.color_from_palette(/*idx*/, false, wrap, 0, 255);
  uint32_t c    = color_blend(BLACK, pcol, s);       // stock blends SEGCOLOR(1); here color1=0
  SEGMENT.setPixelColor(i, c);
}
SEGMENT.step = ...; SEGMENT.aux0 = ...;             // s32i @+44, s16i @+52
return FRAMETIME;
```

### Delta vs stock
1. **Wave-width offset**: `x_scale = (intensity>>2) + 12` (stock `intensity>>2`). ix="Wave width".
2. **Speed/counter is a persistent accumulator** in step(+44)/aux0(+52) driven by
   `speed >> (check1?7:6)`, rather than the stateless `(strip.now*speed)>>9`.
3. **NEW `check1` = Sound Reactive**: adds an audio term to the counter (float path via 0x42150ba4).
4. color1 in the blend is **BLACK (0)** rather than `SEGCOLOR(1)` — equivalent when the
   background color is black (the usual case), a behavioural delta only if SEGCOLOR(1) is set.
5. Still 1D `setPixelColor` (0x403757e8) over SEGLEN. sin8 blend preserved.
6. The **palette index** passed to color_from_palette is uncertain (it is fed from a
   time/phase temp `[a1+8]` rather than the raw loop index `i` as in stock) — MED confidence;
   flag for follow-up.

Repro: `dis_running.txt` (0x420433b4). Loop 0x42043476→0x420434dd; writeback @0x420434e0.

---

## 7. TARTAN  (fx 195, func 0x42043b28)  — CONFIDENCE: HIGH

### Stock `mode_2Dtartan()`
```c
if (SEGENV.call==0) fill(BLACK);
int offsetX=beatsin16(3,-360,360), offsetY=beatsin16(2,-360,360);
int sharpness = custom3/8;                       // 0..3
for (x) for (y) {
  hue = x*beatsin16(10,1,10) + offsetY;
  intensity = bri = sin8(x*speed/2 + offsetX);
  for(i<sharpness) intensity*=bri;  intensity >>= 8*sharpness;
  setPixelColorXY(x,y, ColorFromPalette(SEGPALETTE, hue, intensity, LINEARBLEND));
  hue = y*3 + offsetX;
  intensity = bri = sin8(y*intensity/2 + offsetY);
  for(i<sharpness) intensity*=bri;  intensity >>= 8*sharpness;
  addPixelColorXY(x,y, ColorFromPalette(SEGPALETTE, hue, intensity, LINEARBLEND));
}
```
Stock metadata `"Tartan@X scale,Y scale,,,Sharpness;;!;2"` (sx,ix,c3=Sharpness).

### Fork metadata `"Tartan@X scale,Y scale,Sharpness,Speed;!;!;2g"`
→ sx=X scale, ix=Y scale, **c1=Sharpness**, **c2=Speed (NEW)**.

### Recovered fork pseudocode
```c
if (!strip.isMatrix) return mode_static();
cols=virtualWidth(); rows=virtualHeight();
if (SEGMENT.call == 0) SEGMENT.fill(BLACK);                          // call@+48

int amp     = SEGMENT.custom2 + 232;                                 // c2="Speed" -> 232..487
int offsetX = beatsin16(3, -amp, amp);                               // stock: beatsin16(3,-360,360)
int offsetY = beatsin16(2, -amp, amp);                               // stock: beatsin16(2,-360,360)
int sharpness = SEGMENT.custom1 >> 6;                                // c1="Sharpness", 0..3 (stock c3/8)
uint16_t hmul = beatsin16(10, 1, 10);                                // per-frame x hue multiplier
uint8_t  sh   = 8 * sharpness;

for (int x = 0; x < cols; x++) {
  for (int y = 0; y < rows; y++) {
    // pass 1 (set)
    uint8_t bri = sin8((uint8_t)(x*SEGMENT.speed/2 + offsetX));      // sx="X scale"
    uint32_t I = bri; for (i<sharpness) I*=bri; I >>= sh;
    uint8_t hue = x*hmul + offsetY;                                  // (hmul = beatsin16(10,1,10))
    SEGMENT.setPixelColorXY(x, y, ColorFromPalette(SEGPALETTE, hue, I, LINEARBLEND));
    // pass 2 (add)
    bri = sin8((uint8_t)(y*SEGMENT.intensity/2 + offsetY));          // ix="Y scale"
    I = bri; for (i<sharpness) I*=bri; I >>= sh;
    hue = y*3 + offsetX;
    SEGMENT.addPixelColorXY(x, y, ColorFromPalette(SEGPALETTE, hue, I, LINEARBLEND));
  }
}
return FRAMETIME;
```

### Delta vs stock
1. **Sharpness moved to c1** (`custom1>>6`) from stock c3 (`custom3/8`). c1="Sharpness".
2. **offsetX/offsetY amplitude is now `±(custom2+232)`** (c2="Speed") instead of fixed `±360`.
   Note **c2=128 → ±360 = exactly stock**, so the default matches; the slider widens/narrows the
   plaid drift range.
3. Everything else — `call==0` black fill, `x*speed/2+offsetX`, `y*intensity/2+offsetY`, the
   `intensity *= bri` sharpen-and-`>>=8*sharpness`, SEGPALETTE/LINEARBLEND, set-then-add — is a
   **faithful port** of stock. sx drives the X sine, ix drives the Y sine (as stock).

Repro: `dis_tartan.txt` (0x42043b28). beatsin16=0x42042e08/0x42152f58, fill=0x4201902c.

---

## 8. Summary of confidence

| effect | confidence | notes |
|--------|-----------|-------|
| Hiphotic   | **HIGH** | full lift; ix bimodal-black-gap mechanism explained exactly |
| Tartan     | **HIGH** | near-faithful port; only sharpness(c1) + amplitude(c2) rewired |
| Black Hole | HIGH struct / MED phase | inner stars + white dot removed; count=(c1>>6)+2; X wraps %cols |
| Frizzles   | HIGH wiring / MED bpm shifts | NEW c2=count; X wraps %cols; fade8/blur(c1>>4)+4 |
| Colorwaves | MED-HIGH | 2D port; beatsin88 consts identical; NEW check1 sound-reactive; hueinc reduction approx |
| Running    | MED-HIGH | 1D; x_scale+12; NEW check1 sound-reactive; palette-index source uncertain |

Recurring fork idioms discovered: (a) many effects widen a 2D beatsin range to ~`[dim/2,
5*dim/2-1]` and take the coordinate **modulo the matrix dimension** so it wraps; (b) `check1`
is repurposed as a **Sound Reactive** toggle gating an audio (getAudioData @0x42150ba4) path;
(c) Hiphotic replaced strip.now with a per-segment `step` accumulator so its Speed slider works.

Artifacts in this dir: `parse_image.py`, `disasm.sh`, and `dis_<effect>.txt` for each target.
Scratch (not committed): full segment dumps under
`/tmp/claude-1000/.../scratchpad/reversing/segments_debug/`, stock `FX_v0.14.4.cpp/.h`.

---

## 9. Sound Reactive audio branches (follow-up)  — CONFIDENCE: HIGH

Two of the six presets read audio: **Colorwaves** and **Running**, gated by `check1`
("Sound Reactive"). Branch polarity: `check1 == 1` → audio path (correct SR semantics).
The other four (Hiphotic, Black Hole, Frizzles, Tartan) contain **zero** references to the
audio helpers — verified by literal/callsite scan of each function body. Expected (no SR slot).

### 9.1 Audio acquisition helpers
| addr | identity | signature (recovered) |
|------|----------|-----------------------|
| 0x3fca7220 | `UsermodManager usermods` (global) | — |
| 0x42150ba4 | `UsermodManager::getUMData(um_data_t** out, uint8_t modId)` | iterates usermods, calls each vtbl `getId()`(vtbl+72) and, on match, `getUMData()`(vtbl+24); writes `*out`; returns true on hit |
| 0x42049f18 | `simulateSound(uint8_t simId)` → `um_data_t*` | fallback when no AudioReactive usermod; builds a synthetic um_data (8-ptr array, allocates on first call, cached at 0x3fca11b0) |

Both effects call it identically (only the local out-slot differs):
```c
um_data_t *ud;
if (!usermods.getUMData(&ud, 32)) {          // 32 = AudioReactive usermod id filter
    ud = simulateSound(SEGMENT.soundSim);    // soundSim = options bits 12-13 (bits 28-29 of u32@seg+8)
}
```

### 9.2 `um_data_t` fields actually read
Both effects dereference **exactly one** field, via `[ud+8] -> [+0] -> load float`:
```
ud (um_data_t*)          // returned by getUMData/simulateSound
  +8 : void** u_data      // pointer array (NOTE: u_data sits at struct offset +8 in this build)
u_data[0] : float* -> volumeSmth   // the smoothed overall volume, IEEE-754 float
```
Neither effect reads `volumeRaw`, `fftResult[]` bins, `samplePeak`, `FFT_MajorPeak`, or
`my_magnitude`. **Only `volumeSmth` (u_data[0], float)** is consumed. Confirmed byte-identical
dereference chain in both: colorwaves 0x42043016-0x42043023, running 0x4204341e-0x42043424.

### 9.3 Colorwaves audio branch (func 0x42042e48, path @0x42042fed)
Runs once per frame in the setup, when `check1` set. Folds volume into the **hue increment base**
(the register that is then multiplied to form `hueinc16`, so louder = faster hue travel):
```c
// entering: hbase = (beatsin88(113,60,300) >> 4) + 10;   // normal per-frame hue-inc base
um_data_t *ud;
if (!usermods.getUMData(&ud, 32)) ud = simulateSound(SEGMENT.soundSim);
float   vol = *(float*)ud->u_data[0];                 // volumeSmth
uint16_t v  = (uint16_t)(uint32_t)vol;                // utrunc.s + &0xFFFF (0..65535)
int      d  = 12 - (SEGMENT.intensity >> 5);          // ix="Intensity" -> divisor 12..5
hbase = (hbase + v / d) & 0xFFFF;                      // signed div (quos); folded into hueinc16
// ... continues into the normal hueinc16 = msmultiplier * hbase path ...
```
Delta vs the non-audio branch: the non-SR path computes `hbase` from `beatsin88(113,60,300)`
alone; the SR path **adds `volumeSmth / (12 - (intensity>>5))`** on top. Everything downstream
(the b16 squared-sine brightness, blendPixelColor 128, step/aux0 persistence) is unchanged.
Constants: shift **>>5** on intensity, divisor base **12**, hbase seed `(beatsin>>4)+10`.

### 9.4 Running audio branch (func 0x420433b4, path @0x420433f5)
Runs once per frame, when `check1` set. Folds volume into **both** phase accumulators:
```c
// entering:  aPhase = (speed >> (check1?7:6)) + 1;    // running-wave start phase (a2)
//            hPhase = (speed >> 1) + 10;              // hue/step phase (a3)
if (SEGMENT.check1) {
  um_data_t *ud;
  if (!usermods.getUMData(&ud, 32)) ud = simulateSound(SEGMENT.soundSim);
  float    vol = *(float*)ud->u_data[0];               // volumeSmth
  uint32_t k   = ((uint32_t)vol >> 5) & 0x7FF;         // extui(bit5,width11): (vol>>5)&0x7FF
  aPhase += k;                                         // both accumulators advanced by same term
  hPhase += k;
}
aPhase = (aPhase + SEGMENT.step)  & 0xFFFF;            // step @+44
hPhase = (hPhase + SEGMENT.aux0)  & 0xFFFF;            // aux0 @+52
// aPhase -> running-wave start; hPhase -> sin/palette phase; both persisted back at frame end
```
Note the `speed >> (check1?7:6)`: turning Sound Reactive on **also** halves the base
time-advance (shift 7 vs 6), so the audio term dominates the motion. Constant: volume reduction
**`(vol >> 5) & 0x7FF`** (0..2047), added equally to wave phase and hue phase.

### 9.5 Non-audio effects — confirmed audio-free
Scan of each function body for `getUMData`(0x42150ba4), `simulateSound`(0x42049f18) callsites,
and the `usermods`(0x3fca7220) literal: **Hiphotic, Black Hole, Frizzles, Tartan = 0 refs each.**
Their metadata has no Sound Reactive slot; the binary agrees — none read audio.

Repro: `./disasm.sh 0x42042fed 60` (Colorwaves), `./disasm.sh 0x420433f2 40` (Running),
`./disasm.sh 0x42150ba4 40` (getUMData), `./disasm.sh 0x42049f18 30` (simulateSound).

---

## 10. GLORB usermod, 'g' flag, Colorwaves hueinc16 correction, Running per-pixel, LEDs 0/21/62

### 10.1 The "GLORB" usermod — what `enabled=true` does  (CONFIDENCE: HIGH)
The fork registers three custom usermods alongside the stock ones: **AudioReactive**,
**HomeKit** (HomeSpan-based), and **GLORB**. Each is a `Usermod` subclass with its own vtable.

- GLORB name string `"GLORB"` @0x3c1672f0; config keys `"GLORB"`/`"enabled"` (@0x3c1672e0? no —
  GLORB uses 0x3c1672f0/0x3c1672e8). GLORB **vtable @0x3c1671d8**.
- Overridden vtable slots (all other slots point to the base-class no-op cluster
  0x42150de0..0x42150ef8, each just `entry; retw`):
  - **slot 3 = 0x42046f34** — `readFromJsonState`/`addToJsonState`: reads `[this+9]`, then
    manipulates a JSON object under key `"GLORB"` and the **MQTT/remote key table @0x3c164890**
    (`broker`,`cid`,`topics`,`device`,`rtn`,`remote_enabled`,`linked_remote`,`iv`,…).
  - **slot 6 = 0x42046fd8** — `addToConfig`: writes `{"GLORB":{"enabled":<bool>}}`.
  - **slot 7 = 0x42046230** — `readFromConfig`: reads `GLORB.enabled` into `[this+8]`.
- GLORB has **no** `setup`/`loop` override, **no** `handleOverlayDraw`, **no** `getUMData`.
  It **never** calls `setPixelColor*`, `blur`, `fill`, or any bus/ledmap API.

Verified negatives (whole-image scan):
- **No IMU / gesture / accelerometer** code or strings (`MPU`,`LSM`,`IMU`,`accel`,`gyro`,
  `gesture` → none; only unrelated `tap`/`BLE`/`HomeSpan`). No sensor path exists.
- **No usermod overrides a non-empty overlay-draw slot** — HomeKit's real slots are 1/6/7/11
  (its slot-1 = HomeSpan service init @0x42045a80: allocations + `"HomeSpan-ESP32"` +
  callbacks — an Apple-Home integration, not LEDs); GLORB's are 3/6/7. Neither writes pixels.

**Conclusion:** `GLORB.enabled=true` turns on a **cloud/app/MQTT remote-control integration**
(broker/topics/device linking), gated by a single bool. It does **not** hook rendering, remap
geometry, switch ledmaps, or read an IMU. **The WLED 16 port does NOT need the GLORB usermod
for visual parity** — all visuals come from the 12 effect functions (§2-7) + the ledmap.

### 10.2 The trailing `'g'` metadata flag  (CONFIDENCE: HIGH)
Exhaustive DROM scan of every effect metadata string: the trailing `;…g` flag appears on
**exactly the 12 GLORB custom effects and nothing else**. All ~99 stock effects lack it
(they end in the dimension digit / stock flags: `2`, `2f`, `2v`, optional `;c1=8`/`;si=0`).
Tellingly, the **original stock Tartan is retained as `"Tartan - Legacy@…;;!;2"` (no `g`)**
while the fork's replacement `"Tartan@…;!;!;2g"` carries it.

WLED effect metadata is `Name@sliders;colors;palette;flags;defaults`. The firmware C effect
path dispatches purely by the **mode-table function pointer** (§1.3) and derives 1D/2D from the
live matrix config — it never scans the flag field for arbitrary letters. There is **no readable
web-UI JS in DROM** (`querySelector`/`getModeInfo`/`addEventListener` = 0 hits → the UI is
gzipped). So `'g'` is **not consumed by any rendering C code**; it is a fork **UI/app metadata
badge** that tags "these are the GLORB effects" for the (gzipped) web UI / companion app to
recognise or filter. It gates nothing in the render pipeline — safe to ignore for the port.

### 10.3 Colorwaves `hueinc16` / `duration` — DEFINITIVE (supersedes §5.3 and §9.3)
I previously conflated two independent per-frame quantities. Exact register trace of the setup
(0x42042ea3-0x42042f4b):

Registers: `a2=speed`(l8ui+6), `a7=step`(sPseudotime,+44), `a3=aux0`(sHue16,+52),
`a4=msmultiplier=beatsin88(147,23,60)`, `a10(BW)=beatsin88(113,60,300)`.

```c
// duration base (both paths):  a2 = (speed>>4) + 10       // stock: 10 + speed
int duration = (SEGMENT.speed >> 4) + 10;

if (!check1) {                              // ---- Sound Reactive OFF (pure time) ----
   uint8_t i8 = SEGMENT.intensity >> 3;                          // intensity/8, 0..31
   hueinc16 = (uint16_t)( ((uint32_t)BW * i8 * 10) / 255 );      // <-- exact
   // (÷255 via muluh with 0x80808081 then >>7; ×10 via (x<<2 + x)<<1)
} else {                                    // ---- Sound Reactive ON  ----
   float vol = *(float*)ud->u_data[0];                           // volumeSmth
   duration  = duration + (uint16_t)vol / (12 - (SEGMENT.intensity>>5));  // +audio
   hueinc16  = 0;                                                // <-- forced to 0 in SR mode
}
sPseudotime += duration * msmultiplier;                          // a7 += duration*msmultiplier
sHue16      += duration * beatsin88(400, 5, 9);                  // a3 += duration*bs(400,5,9)
```
Answers to the three questions:
- **Final hueinc16, SR off** = `beatsin88(113,60,300) * (SEGMENT.intensity>>3) * 10 / 255`.
  The multiplier is **`intensity>>3`** (stock used full `intensity`). It is *not* `msmultiplier`
  and *not* `(beatsin>>4)+10` — that latter expression was actually `duration`.
- **Final hueinc16, SR on** = **0** (the spatial hue gradient is flattened; only `sHue16` drifts
  the whole field over time). Louder audio instead speeds `duration`.
- **Where SEGMENT.intensity enters the non-audio path:** *only* in `hueinc16`, as `intensity>>3`.
  (In the audio path it also appears in the divisor `12-(intensity>>5)`.)
- `msmultiplier = beatsin88(147,23,60)` multiplies `duration` for `sPseudotime` (as stock).

### 10.4 Running per-pixel body — DEFINITIVE (closes §6's open flag)  (CONFIDENCE: HIGH)
With `aPhase` (wave) and `hPhase` (hue) as recovered in §9.4, the frame setup then computes a
**triangle wave of hPhase** as a single global palette index, and the loop applies a running
`sin8` brightness wave (0x42043446-0x420434dd):
```c
uint16_t hp = (hPhase + SEGMENT.aux0) & 0xFFFF;            // aux0@+52
uint16_t t2 = (hp << 1) & 0xFFFF;
uint8_t  hueIdx = ((int16_t)hp >= 0 ? t2 : ~t2) >> 8;      // triangle(hPhase) -> 8-bit index
uint16_t ap = (aPhase + SEGMENT.step) & 0xFFFF;            // step@+44 ; wave start phase
uint8_t  x_scale = (SEGMENT.intensity>>2) + 12;            // ix="Wave width"
bool wrap = (strip.paletteBlend-ish bit) ... ;            // PALETTE_SOLID_WRAP flag from strip[1]&~2

for (int i = 0; i < SEGLEN; i++) {
    uint8_t s = sin8( (uint8_t)(ap + i * x_scale) );                 // running brightness wave
    uint32_t pcol = SEGMENT.color_from_palette(hueIdx, /*mapping*/false, wrap, /*mcol*/0, 255);
    uint32_t c    = color_blend(/*BLACK*/0, pcol, s, false);
    SEGMENT.setPixelColor(i, c);                                     // 1D writer @0x403757e8
}
SEGMENT.step = ap-ish; SEGMENT.aux0 = hp-ish;             // persisted
```
Exact per-pixel facts:
- **sin8 argument** = `(aPhase + i*x_scale) & 0xFF`, where the accumulator adds
  `x_scale = (intensity>>2)+12` each pixel — i.e. `sin8(aPhase + i*x_scale)`.
- **palette index** = `hueIdx = triangle(hPhase) >> 8` — a **single value shared by all pixels**,
  advancing only in time (hPhase = speed/audio/aux0), **not** `i`. **mapping flag = false**
  (stock passed `i` with mapping=**true**). So the whole strip is one time-evolving color whose
  brightness runs along the length via the sin8 wave; stock instead painted a moving palette
  gradient (`color_from_palette(i, true, …)`). This is the section-6 delta, now resolved.
- `color_blend(BLACK, pcol, s)` — color1 is literal 0 (stock used `SEGCOLOR(1)`).

### 10.5 LEDs 0 / 21 / 62 — is anything writing the ledmap holes?  (CONFIDENCE: MED-HIGH)
The factory grid ledmap maps 80 logical cells onto physical 1..82 except {0,21,62}. Searching
the whole image for another writer of those three:
- **No usermod writes LEDs** at all (§10.1): GLORB and HomeKit never call a pixel/bus writer;
  the `handleOverlayDraw` slot is the base no-op in every custom usermod → no overlay pass draws.
- **No literal-index pixel write** to 0/21/62 in a render context: `movi *,21`(3 sites) and
  `movi *,62`(6 sites) all land in unrelated helpers (FFT/util code at 0x42084xxx/0x420cbxxx/…),
  none adjacent to a `setPixelColor`/bus call.
- Effects reach the panel **only** through the ledmap, which by construction excludes {0,21,62}.

**Conclusion:** no code path in this app image deliberately lights physical LEDs 0/21/62. They
are either **gap entries** (physically absent — the firmware has a gap-map: strings "Reading LED
gap from"/"Gaps loaded"/"Matrix ledmap:") or real LEDs left **black**. Either way the original
firmware does **not** light them, so a grid-based port loses nothing visible. Caveat: whether
they are gaps-vs-black, and whether a second full-strip segment exists, is decided by
`ledmap.json`/`cfg.json` in **littlefs**, which is *not* in this app binary — confirm against the
device's `/cfg.json` + `/ledmap.json` if certainty on the gap-vs-black distinction is needed.

### 10.6 Per-model LED-count constants
This image is the **gma_83** build; DROM contains only its banner `WLED v0.14.4-GLORB.1.3`
and **no** `gma_81`/`sph_81`/`sph_83` model strings — the variants are separate builds/configs,
not switched by a runtime string in this binary. LED count is not a compile-time literal switched
by model here; it comes from `cfg.json`/NVS (WLED bus config). `movi` immediates of 80 (19×),
82 (3×), 83 (4×), 120 (67×) exist but none could be tied to the strip length with confidence
(120 is common/unrelated). No reliable static per-model count constant to report.
