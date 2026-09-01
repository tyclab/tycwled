#include "wled.h"

// GLORB factory effects for WLED 16, reimplementing the fork's custom effects
// (0.14.4-GLORB.1.3, fx 189-195) from the decompiled firmware
// (glorb/experiments/2026-08-31-reversing/NOTES.md). The fork's effects are
// adaptations of stock WLED 0.14.4 (MIT) effects by Stepko/ldirko/Elliott
// Kember/Andrew Tuline; slider layouts are verbatim from the fork binary.
//
// The fork's check1 "Sound Reactive" branches (Colorwaves, Running) are
// implemented from the same disassembly, so audioreactive must be built in,
// though every factory preset ships with the toggle off. Every constant and
// argument position is now pinned against the disassembly; no NOTE-MED remain.

#define PALETTE_SOLID_WRAP (paletteBlend == 1 || paletteBlend == 3)

static void glorb_mode_static_fallback(void) {
  SEGMENT.fill(SEGCOLOR(0));
}
#define GLORB_FALLBACK { glorb_mode_static_fallback(); return; }

static um_data_t* glorb_getAudioData() {
  um_data_t *um_data;
  if (!UsermodManager::getUMData(&um_data, USERMOD_ID_AUDIOREACTIVE)) {
    um_data = simulateSound(SEGMENT.soundSim);
  }
  return um_data;
}

// fork's triangle(hPhase): fold a 16-bit phase into a triangle wave.
// The fold is a bitwise complement of the DOUBLED value (0x42043453 slli, 0x42043464 xor -1),
// not 65535-in doubled -- those differ by one, which shifts the palette index at 1 in 128 phases.
static inline uint16_t glorb_triwave16(uint16_t in) {
  const uint16_t v = (uint16_t)(in << 1);
  return (in & 0x8000) ? (uint16_t)~v : v;
}

// ---- the fork's helper stack ---------------------------------------------
// The fork is WLED 0.14.4 and calls FastLED's helpers. WLED 16 replaced all of
// them with its own, and the replacements are not bit-identical: sin8_t differs
// from FastLED's sin8 by up to 5/255, and WLED 16 dropped FastLED's "+1"
// rounding from every scale operation, so blur and fade lose energy the fork
// keeps. Those differences are small per frame and compound badly inside the
// fade/inject/blur feedback loops. WLED 16 ships no FastLED trig at all, so the
// originals are reproduced here and used in place of the WLED spellings.
// Callee identifications and the tables are in NOTES.md section 12.

// FastLED sin8_C — table confirmed at DROM 0x3c167ab8 in the fork image
static uint8_t glorb_sin8(uint8_t theta) {
  static const uint8_t b_m16_interleave[] = {0, 49, 49, 41, 90, 27, 117, 10};
  uint8_t offset = theta;
  if (theta & 0x40) offset = (uint8_t)255 - offset;
  offset &= 0x3F;
  uint8_t secoffset = offset & 0x0F;
  if (theta & 0x40) secoffset++;
  const uint8_t section = offset >> 4;
  const uint8_t b = b_m16_interleave[section * 2];
  const uint8_t m16 = b_m16_interleave[section * 2 + 1];
  int8_t y = (int8_t)(((uint8_t)((m16 * secoffset) >> 4)) + b);
  if (theta & 0x80) y = -y;
  return (uint8_t)(y + 128);
}

// FastLED sin16_C — slope table confirmed at DROM 0x3c167ac0
static int16_t glorb_sin16(uint16_t theta) {
  static const uint16_t base[] = {0, 6393, 12539, 18204, 23170, 27245, 30273, 32137};
  static const uint8_t slope[] = {49, 48, 44, 38, 31, 23, 14, 4};
  uint16_t offset = (theta & 0x3FFF) >> 3;
  if (theta & 0x4000) offset = 2047 - offset;
  const uint8_t section = offset / 256;
  const uint8_t secoffset8 = (uint8_t)offset / 2;
  int16_t y = (int16_t)(slope[section] * secoffset8 + base[section]);
  if (theta & 0x8000) y = -y;
  return y;
}

// FastLED scale8/scale16 with FASTLED_SCALE8_FIXED: the "+1" WLED 16 dropped
static inline uint8_t glorb_scale8(uint8_t i, uint8_t s) { return ((uint16_t)i * (uint16_t)(s + 1)) >> 8; }
static inline uint16_t glorb_scale16(uint16_t i, uint16_t s) { return ((uint32_t)i * (uint32_t)(s + 1)) >> 16; }

static inline uint16_t glorb_beat88(uint32_t bpm88, uint32_t timebase) {
  return ((strip.now - timebase) * bpm88 * 280) >> 16;
}
static inline uint16_t glorb_beat16(uint32_t bpm, uint32_t timebase) {
  if (bpm < 256) bpm <<= 8;
  return glorb_beat88(bpm, timebase);
}
static uint8_t glorb_beatsin8(uint16_t bpm, uint8_t lowest = 0, uint8_t highest = 255,
                              uint32_t timebase = 0, uint8_t phase_offset = 0) {
  const uint8_t beat = glorb_beat16(bpm, timebase) >> 8;
  return lowest + glorb_scale8(glorb_sin8(beat + phase_offset), highest - lowest);
}
static uint16_t glorb_beatsin16(uint16_t bpm, uint16_t lowest = 0, uint16_t highest = 65535,
                                uint32_t timebase = 0, uint16_t phase_offset = 0) {
  const uint16_t beat = glorb_beat16(bpm, timebase);
  return lowest + glorb_scale16((uint16_t)(glorb_sin16(beat + phase_offset) + 32768), highest - lowest);
}
static uint16_t glorb_beatsin88(uint32_t bpm88, uint16_t lowest = 0, uint16_t highest = 65535,
                                uint32_t timebase = 0, uint16_t phase_offset = 0) {
  const uint16_t beat = glorb_beat88(bpm88, timebase);
  return lowest + glorb_scale16((uint16_t)(glorb_sin16(beat + phase_offset) + 32768), highest - lowest);
}

// 0.14.4 color_blend: weights sum to 255/256, so it bleeds slightly toward
// black each iteration where WLED 16's (256-b)/(b+1) pair is a fixed point
static inline uint32_t glorb_color_blend(uint32_t c1, uint32_t c2, uint8_t blend) {
  const uint8_t inv = 255 - blend;
  return RGBW32((R(c1) * inv + R(c2) * blend) >> 8, (G(c1) * inv + G(c2) * blend) >> 8,
                (B(c1) * inv + B(c2) * blend) >> 8, (W(c1) * inv + W(c2) * blend) >> 8);
}

// FastLED nscale8x3 — the "+1" again
static inline uint32_t glorb_nscale8(uint32_t c, uint8_t s) {
  const uint16_t sc = (uint16_t)s + 1;
  return RGBW32((R(c) * sc) >> 8, (G(c) * sc) >> 8, (B(c) * sc) >> 8, (W(c) * sc) >> 8);
}

// 0.14.4 fadeToBlackBy(f) is nscale8(c, 255-f) with FastLED's rounding, keeping
// (v*(256-f))>>8; WLED 16 keeps (v*(255-f))>>8. Delegating as fadeToBlackBy(f-1)
// looks equivalent but breaks at f == 1, where WLED 16 treats 0 as "no fade at
// all" -- and in a trail effect the difference between a slow decay and no decay
// is not small: Black Hole's fade argument is custom2>>4, which is 1 on the
// factory's preset 11, and delegating left its trails immortal (mean_r 1.72).
static void glorb_fadeToBlackBy(uint8_t fadeBy) {
  const uint8_t keep = 255 - fadeBy;
  const int cols = SEG_W;
  const int rows = SEG_H;
  for (int y = 0; y < rows; y++) {
    for (int x = 0; x < cols; x++) {
      SEGMENT.setPixelColorXY(x, y, glorb_nscale8(SEGMENT.getPixelColorXY(x, y), keep));
    }
  }
}

// 0.14.4 blur2d: blurRow over every row then blurCol over every column, with
// FastLED's rounding. WLED 16's blur2D uses fast_color_scale, which rounds down.
static void glorb_blur2d(uint8_t blur_amount) {
  const int cols = SEG_W;
  const int rows = SEG_H;
  const uint8_t keep = 255 - blur_amount;
  const uint8_t seep = blur_amount >> 1;
  for (int y = 0; y < rows; y++) {
    uint32_t carryover = BLACK;
    for (int x = 0; x < cols; x++) {
      const uint32_t cur = SEGMENT.getPixelColorXY(x, y);
      const uint32_t part = glorb_nscale8(cur, seep);
      uint32_t out = color_add(glorb_nscale8(cur, keep), carryover, false);
      if (x > 0) SEGMENT.setPixelColorXY(x - 1, y, color_add(SEGMENT.getPixelColorXY(x - 1, y), part, false));
      SEGMENT.setPixelColorXY(x, y, out);
      carryover = part;
    }
  }
  for (int x = 0; x < cols; x++) {
    uint32_t carryover = BLACK;
    for (int y = 0; y < rows; y++) {
      const uint32_t cur = SEGMENT.getPixelColorXY(x, y);
      const uint32_t part = glorb_nscale8(cur, seep);
      uint32_t out = color_add(glorb_nscale8(cur, keep), carryover, false);
      if (y > 0) SEGMENT.setPixelColorXY(x, y - 1, color_add(SEGMENT.getPixelColorXY(x, y - 1), part, false));
      SEGMENT.setPixelColorXY(x, y, out);
      carryover = part;
    }
  }
}

// ---- Hiphotic (fork fx 193) — exact lift, HIGH confidence ----------------
// sx=Speed (per-frame step accumulator), ix=Hue variation (index compression
// shift + beat window), c1=X scale, c2=Y scale. Delta vs stock: persistent
// SEGENV.step phase instead of strip.now/custom3; per-axis steps (cN>>5)+8;
// palette index (v>>shift)+beatsin8(2,0,~(0xFF>>shift)); 64/255 temporal
// blend with the previous frame.
static void glorb_mode_hiphotic(void) {
  if (!strip.isMatrix || !SEGMENT.is2D()) GLORB_FALLBACK;
  const int cols = SEG_W;
  const int rows = SEG_H;
  SEGENV.step += (SEGMENT.speed >> 6) + 1;
  const uint16_t a = (uint16_t)SEGENV.step;
  const uint8_t shift  = 3 - (SEGMENT.intensity >> 6);
  const uint8_t himask = (uint8_t)~(0xFF >> shift);
  const uint8_t bwave  = glorb_beatsin8(2, 0, himask);
  const uint8_t xstep  = (SEGMENT.custom1 >> 5) + 8;
  const uint8_t ystep  = (SEGMENT.custom2 >> 5) + 8;
  uint8_t hx = (uint8_t)(a / 3) + 64;  // +64 folds cos8 into sin8
  for (int x = 0; x < cols; x++, hx += xstep) {
    uint8_t hy = (uint8_t)(a / 4);
    for (int y = 0; y < rows; y++, hy += ystep) {
      const uint8_t v = glorb_sin8(glorb_sin8(hy) + glorb_sin8(hx) + (uint8_t)a);
      const uint8_t idx = (v >> shift) + bwave;
      const uint32_t col = SEGMENT.color_from_palette(idx, false, PALETTE_SOLID_WRAP, 0);
      SEGMENT.setPixelColorXY(x, y, glorb_color_blend(SEGMENT.getPixelColorXY(x, y), col, 64));
    }
  }
}
static const char _data_FX_MODE_GLORB_HIPHOTIC[] PROGMEM = "Hiphotic@Speed,Hue variation,X scale,Y scale;!;!;2g";

// ---- Black Hole (fork fx 192) — decompiled, HIGH -------------------------
// sx=X scale (bpm), ix=Y scale (bpm), c1=Intensity (star count 2..5),
// c2=Fade rate. Delta vs stock: single star loop (inner stars + white dot
// removed), X beat range widened to [cols/2, cols*5/2-1] then wrapped %cols,
// Y in [1, rows-2], palette index i*63, blur 32.
static void glorb_mode_blackhole(void) {
  if (!strip.isMatrix || !SEGMENT.is2D()) GLORB_FALLBACK;
  const int cols = SEG_W;
  const int rows = SEG_H;
  glorb_fadeToBlackBy(SEGMENT.custom2 >> 4);
  const uint32_t t8 = strip.now >> 7;  // == millis()/128
  const uint8_t count = (SEGMENT.custom1 >> 6) + 2;
  for (size_t i = 0; i < count; i++) {
    // Phases are the fork helper's 4th argument. That helper (0x4204307c) takes
    // (bpm, lowest, highest, phase_offset) and has NO timebase: after entry, arg4 lands in a5
    // and 0x420430a3 adds it straight to the beat angle before sin8. Passing these as a
    // timebase instead bunches the stars into near-unison and collapses the lit-cell count.
    const uint8_t xphase = (uint8_t)(i * (uint8_t)(t8 - 128));
    const uint8_t yphase = ((i & 1) ? 192 : 64) + (uint8_t)(i * t8);
    const int x = glorb_beatsin8((SEGMENT.speed >> 5) + 1, cols / 2, (cols * 5) / 2 - 1, 0, xphase);
    const int y = glorb_beatsin8((SEGMENT.intensity >> 4) + 1, 1, rows - 2, 0, yphase);
    const uint32_t col = SEGMENT.color_from_palette(i * 63, false, PALETTE_SOLID_WRAP, SEGMENT.check1 ? 0 : 255);
    SEGMENT.addPixelColorXY(x % cols, y, col);
  }
  glorb_blur2d(32);
}
static const char _data_FX_MODE_GLORB_BLACKHOLE[] PROGMEM = "Black Hole@X scale,Y scale,Intensity,Fade rate;!;!;2g";

// ---- Frizzles (fork fx 191) — decompiled, HIGH ---------------------------
// sx=X scale, ix=Y scale, c1=Blur, c2=Intensity (point count 1..8).
// Delta vs stock: variable count, X range widened + wrapped %cols,
// Y in [1, rows-2], fade 8, blur (c1>>4)+4.
static void glorb_mode_frizzles(void) {
  if (!strip.isMatrix || !SEGMENT.is2D()) GLORB_FALLBACK;
  const int cols = SEG_W;
  const int rows = SEG_H;
  glorb_fadeToBlackBy(8);
  const int count = (SEGMENT.custom2 >> 5) + 1;
  for (int i = count; i > 0; i--) {
    // both bpm terms confirmed against the binary (0x4204360b: i + speed>>5;
    // 0x42043632: (intensity>>6) + 8 - i), both with timebase 0
    const int x = glorb_beatsin8(i + (SEGMENT.speed >> 5), cols / 2, (cols * 5) / 2 - 1);
    const int y = glorb_beatsin8((SEGMENT.intensity >> 6) + 8 - i, 1, rows - 2);
    const uint32_t c = ColorFromPalette(SEGPALETTE, glorb_beatsin8(12, 0, 255), 255, LINEARBLEND);
    SEGMENT.addPixelColorXY(x % cols, y, c);
  }
  glorb_blur2d((SEGMENT.custom1 >> 4) + 4);
}
static const char _data_FX_MODE_GLORB_FRIZZLES[] PROGMEM = "Frizzles@X scale,Y scale,Blur,Intensity;!;!;2g";

// ---- Colorwaves (fork fx 189) — decompiled, HIGH -------------------------
// sx=Speed (duration=(sx>>4)+10), ix=Intensity (hue-gradient scale),
// check1=Sound Reactive: hueinc16=0 (gradient flattened) and volumeSmth
// speeds duration by vol/(12-(ix>>5)). The stock colorwaves engine (all
// beatsin88 constants byte-identical in the fork binary), but run as a 2D
// effect: the hue advances once per row, and its triangle fold spans the whole
// palette where stock's covers only the lower half.
static void glorb_mode_colorwaves(void) {
  if (!strip.isMatrix || !SEGMENT.is2D()) GLORB_FALLBACK;  // the fork checks this too (0x42042e51)
  uint16_t duration = (SEGMENT.speed >> 4) + 10;
  uint16_t sPseudotime = SEGENV.step;
  uint16_t sHue16 = SEGENV.aux0;
  const uint8_t brightdepth = glorb_beatsin88(341, 96, 224);
  const uint16_t brightnessthetainc16 = glorb_beatsin88(203, (25 * 256), (40 * 256));
  const uint8_t msmultiplier = glorb_beatsin88(147, 23, 60);
  uint16_t hue16 = sHue16;
  uint16_t hueinc16;
  if (SEGMENT.check1) {
    um_data_t *um_data = glorb_getAudioData();
    const float vol = *(float*)um_data->u_data[0];  // volumeSmth
    hueinc16 = 0;
    duration += (uint16_t)((uint32_t)vol / (12 - (SEGMENT.intensity >> 5)));
  } else {
    hueinc16 = glorb_beatsin88(113, 60, 300) * (SEGMENT.intensity >> 3) * 10 / 255;
  }
  sPseudotime += duration * msmultiplier;
  sHue16 += duration * glorb_beatsin88(400, 5, 9);
  uint16_t brightnesstheta16 = sPseudotime;
  const int cols = SEG_W;
  const int rows = SEG_H;
  for (int y = 0; y < rows; y++) {
    // the fork advances the hue once per ROW, so the gradient spans 6 steps, not 120
    hue16 += hueinc16;
    // full-range triangle: stock WLED folds to 0..127 and would only ever address
    // the lower half of the palette (0x42042f57: slli 1, then 65535 - 2*hue16)
    const uint8_t t = (uint8_t)(hue16 >> 7);
    const uint8_t hue8 = (hue16 & 0x8000) ? (uint8_t)(255 - t) : t;
    for (int x = 0; x < cols; x++) {
      brightnesstheta16 += brightnessthetainc16;
      const uint16_t b16 = glorb_sin16(brightnesstheta16) + 32768;
      const uint16_t bri16 = (uint32_t)((uint32_t)b16 * (uint32_t)b16) / 65536;
      uint8_t bri8 = (uint32_t)(((uint32_t)bri16) * brightdepth) / 65536;
      bri8 += (255 - brightdepth);
      const uint32_t col = SEGMENT.color_from_palette(hue8, false, PALETTE_SOLID_WRAP, 0, bri8);
      SEGMENT.setPixelColorXY(x, y, glorb_color_blend(SEGMENT.getPixelColorXY(x, y), col, 128));
    }
  }
  SEGENV.step = sPseudotime;
  SEGENV.aux0 = sHue16;
}
static const char _data_FX_MODE_GLORB_COLORWAVES[] PROGMEM = "Colorwaves@Speed,Intensity,,,,Sound Reactive;!;!;2vg";

// ---- Running (fork fx 190) — decompiled, HIGH ----------------------------
// sx=Speed, ix=Wave width ((ix>>2)+12), check1=Sound Reactive (volumeSmth
// advances both phases by (vol>>5)&0x7FF and halves the base time-advance).
// Two persistent accumulators: aPhase (wave, step) and hPhase (hue, aux0).
// One time-evolving palette color for all pixels (triangle(hPhase)>>8,
// mapping=false), brightness = running sine wave, background BLACK.
static void glorb_mode_running(void) {
  const bool sr = SEGMENT.check1;
  uint32_t aPhase = (SEGMENT.speed >> (sr ? 7 : 6)) + 1;
  uint32_t hPhase = (SEGMENT.speed >> 1) + 10;
  if (sr) {
    um_data_t *um_data = glorb_getAudioData();
    const float vol = *(float*)um_data->u_data[0];  // volumeSmth
    const uint32_t k = ((uint32_t)vol >> 5) & 0x7FF;
    aPhase += k;
    hPhase += k;
  }
  aPhase = (aPhase + SEGENV.step) & 0xFFFF;
  hPhase = (hPhase + SEGENV.aux0) & 0xFFFF;
  const uint8_t x_scale = (SEGMENT.intensity >> 2) + 12;
  const uint8_t idx = glorb_triwave16((uint16_t)hPhase) >> 8;
  const uint32_t pcol = SEGMENT.color_from_palette(idx, false, PALETTE_SOLID_WRAP, 0);
  for (int i = 0; i < (int)SEGLEN; i++) {
    const uint8_t s = glorb_sin8((uint8_t)(aPhase + i * x_scale));
    SEGMENT.setPixelColor(i, glorb_color_blend(BLACK, pcol, s));
  }
  SEGENV.step = aPhase;
  SEGENV.aux0 = hPhase;
}
static const char _data_FX_MODE_GLORB_RUNNING[] PROGMEM = "Running@Speed,Wave width,,,,Sound Reactive;!;!;g";

// ---- Tartan (fork fx 195) — exact lift, HIGH confidence ------------------
// sx=X scale, ix=Y scale, c1=Sharpness (c1>>6), c2=Speed (offset amplitude
// ±(c2+232); c2=128 reproduces stock's ±360 exactly).
static void glorb_mode_tartan(void) {
  if (!strip.isMatrix || !SEGMENT.is2D()) GLORB_FALLBACK;
  const int cols = SEG_W;
  const int rows = SEG_H;
  if (SEGENV.call == 0) SEGMENT.fill(BLACK);
  const int amp = SEGMENT.custom2 + 232;
  const int offsetX = glorb_beatsin16(3, -amp, amp);
  const int offsetY = glorb_beatsin16(2, -amp, amp);
  const int sharpness = SEGMENT.custom1 >> 6;
  // One global palette index for the whole frame, mapped from the slow Y offset sine
  // (0x42043bd5 sign-extends it, 0x42043bde maps it to 0..255, 0x42043be1 stores it once
  // before both loops). Stock colours Tartan by position instead; the fork's sine dwells at
  // the palette ends, which is where Fairy Reaf keeps its magenta.
  const int16_t offYs = (int16_t)offsetY;
  const uint8_t ghue = (uint8_t)(((int32_t)(offYs + amp) * 255) / (2 * amp));
  for (int x = 0; x < cols; x++) {
    for (int y = 0; y < rows; y++) {
      uint8_t bri = glorb_sin8((uint8_t)(x * SEGMENT.speed / 2 + offsetX));
      size_t inten = bri;
      for (int i = 0; i < sharpness; i++) inten *= bri;
      inten >>= 8 * sharpness;
      SEGMENT.setPixelColorXY(x, y, ColorFromPalette(SEGPALETTE, ghue, inten, LINEARBLEND));
      bri = glorb_sin8((uint8_t)(y * SEGMENT.intensity / 2 + offsetY));
      inten = bri;
      for (int i = 0; i < sharpness; i++) inten *= bri;
      inten >>= 8 * sharpness;
      SEGMENT.addPixelColorXY(x, y, ColorFromPalette(SEGPALETTE, ghue, inten, LINEARBLEND));
    }
  }
}
static const char _data_FX_MODE_GLORB_TARTAN[] PROGMEM = "Tartan@X scale,Y scale,Sharpness,Speed;!;!;2g";

class GlorbFxUsermod : public Usermod {
 public:
  void setup() override {
    strip.addEffect(255, &glorb_mode_colorwaves, _data_FX_MODE_GLORB_COLORWAVES);
    strip.addEffect(255, &glorb_mode_running, _data_FX_MODE_GLORB_RUNNING);
    strip.addEffect(255, &glorb_mode_frizzles, _data_FX_MODE_GLORB_FRIZZLES);
    strip.addEffect(255, &glorb_mode_blackhole, _data_FX_MODE_GLORB_BLACKHOLE);
    strip.addEffect(255, &glorb_mode_hiphotic, _data_FX_MODE_GLORB_HIPHOTIC);
    strip.addEffect(255, &glorb_mode_tartan, _data_FX_MODE_GLORB_TARTAN);
  }
  void loop() override {}
  uint16_t getId() override { return USERMOD_ID_USER_FX; }
};

static GlorbFxUsermod glorb_fx;
REGISTER_USERMOD(glorb_fx);
