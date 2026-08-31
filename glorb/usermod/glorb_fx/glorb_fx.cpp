#include "wled.h"

// GLORB factory effects for WLED 16, reimplementing the fork's custom effects
// (0.14.4-GLORB.1.3, fx 189-195) from the decompiled firmware
// (glorb/experiments/2026-08-31-reversing/NOTES.md). The fork's effects are
// adaptations of stock WLED 0.14.4 (MIT) effects by Stepko/ldirko/Elliott
// Kember/Andrew Tuline; slider layouts are verbatim from the fork binary.
//
// The fork's check1 "Sound Reactive" toggles are OFF in every factory preset,
// so the audio branches are intentionally not implemented; the checkbox is a
// no-op here (marked NOTE-AUDIO). Two decompile details carry MED confidence
// and are marked NOTE-MED for follow-up against gate measurements.

#define PALETTE_SOLID_WRAP (paletteBlend == 1 || paletteBlend == 3)

static void glorb_mode_static_fallback(void) {
  SEGMENT.fill(SEGCOLOR(0));
}
#define GLORB_FALLBACK { glorb_mode_static_fallback(); return; }

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
  const uint8_t bwave  = beatsin8_t(2, 0, himask);
  const uint8_t xstep  = (SEGMENT.custom1 >> 5) + 8;
  const uint8_t ystep  = (SEGMENT.custom2 >> 5) + 8;
  uint8_t hx = (uint8_t)(a / 3) + 64;  // +64 folds cos8 into sin8
  for (int x = 0; x < cols; x++, hx += xstep) {
    uint8_t hy = (uint8_t)(a / 4);
    for (int y = 0; y < rows; y++, hy += ystep) {
      const uint8_t v = sin8_t(sin8_t(hy) + sin8_t(hx) + (uint8_t)a);
      const uint8_t idx = (v >> shift) + bwave;
      const uint32_t col = SEGMENT.color_from_palette(idx, false, PALETTE_SOLID_WRAP, 0);
      SEGMENT.setPixelColorXY(x, y, color_blend(SEGMENT.getPixelColorXY(x, y), col, 64));
    }
  }
}
static const char _data_FX_MODE_GLORB_HIPHOTIC[] PROGMEM = "Hiphotic@Speed,Hue variation,X scale,Y scale;!;!;2g";

// ---- Black Hole (fork fx 192) — HIGH structure / MED x-phase -------------
// sx=X scale (bpm), ix=Y scale (bpm), c1=Intensity (star count 2..5),
// c2=Fade rate. Delta vs stock: single star loop (inner stars + white dot
// removed), X beat range widened to [cols/2, cols*5/2-1] then wrapped %cols,
// Y in [1, rows-2], palette index i*63, blur 32.
static void glorb_mode_blackhole(void) {
  if (!strip.isMatrix || !SEGMENT.is2D()) GLORB_FALLBACK;
  const int cols = SEG_W;
  const int rows = SEG_H;
  SEGMENT.fadeToBlackBy(SEGMENT.custom2 >> 4);
  const uint32_t t8 = strip.now >> 7;  // == millis()/128
  const uint8_t count = (SEGMENT.custom1 >> 6) + 2;
  for (size_t i = 0; i < count; i++) {
    const uint8_t xphase = (uint8_t)(i * (uint8_t)(t8 - 128));  // NOTE-MED exact x-phase term
    const uint8_t yphase = ((i & 1) ? 192 : 64) + (uint8_t)(i * t8);
    const int x = beatsin8_t((SEGMENT.speed >> 5) + 1, cols / 2, (cols * 5) / 2 - 1, 0, xphase);
    const int y = beatsin8_t((SEGMENT.intensity >> 4) + 1, 1, rows - 2, 0, yphase);
    const uint32_t col = SEGMENT.color_from_palette(i * 63, false, PALETTE_SOLID_WRAP, SEGMENT.check1 ? 0 : 255);
    SEGMENT.addPixelColorXY(x % cols, y, col);
  }
  SEGMENT.blur(32);
}
static const char _data_FX_MODE_GLORB_BLACKHOLE[] PROGMEM = "Black Hole@X scale,Y scale,Intensity,Fade rate;!;!;2g";

// ---- Frizzles (fork fx 191) — HIGH wiring / MED exact bpm shifts ---------
// sx=X scale, ix=Y scale, c1=Blur, c2=Intensity (point count 1..8).
// Delta vs stock: variable count, X range widened + wrapped %cols,
// Y in [1, rows-2], fade 8, blur (c1>>4)+4.
static void glorb_mode_frizzles(void) {
  if (!strip.isMatrix || !SEGMENT.is2D()) GLORB_FALLBACK;
  const int cols = SEG_W;
  const int rows = SEG_H;
  SEGMENT.fadeToBlackBy(8);
  const int count = (SEGMENT.custom2 >> 5) + 1;
  for (int i = count; i > 0; i--) {
    const int x = beatsin8_t(i + (SEGMENT.speed >> 5), cols / 2, (cols * 5) / 2 - 1);  // NOTE-MED shift
    const int y = beatsin8_t((SEGMENT.intensity >> 6) + 8 - i, 1, rows - 2);           // NOTE-MED shift
    const uint32_t c = ColorFromPalette(SEGPALETTE, beatsin8_t(12, 0, 255), 255, LINEARBLEND);
    SEGMENT.addPixelColorXY(x % cols, y, c);
  }
  SEGMENT.blur((SEGMENT.custom1 >> 4) + 4);
}
static const char _data_FX_MODE_GLORB_FRIZZLES[] PROGMEM = "Frizzles@X scale,Y scale,Blur,Intensity;!;!;2g";

// ---- Colorwaves (fork fx 189) — MED-HIGH ---------------------------------
// sx=Speed, ix=Intensity, check1=Sound Reactive (NOTE-AUDIO: no-op here).
// The stock 0.14.4 colorwaves engine (all beatsin88 constants byte-identical
// in the fork binary) rendered over the segment; hueinc16 reduction is the
// fork's ((beatsin88>>4)+10)*(ix>>3) — NOTE-MED vs stock *ix*10/255.
static void glorb_mode_colorwaves(void) {
  const uint16_t duration = 10 + SEGMENT.speed;
  uint16_t sPseudotime = SEGENV.step;
  uint16_t sHue16 = SEGENV.aux0;
  const uint8_t brightdepth = beatsin88_t(341, 96, 224);
  const uint16_t brightnessthetainc16 = beatsin88_t(203, (25 * 256), (40 * 256));
  const uint8_t msmultiplier = beatsin88_t(147, 23, 60);
  uint16_t hue16 = sHue16;
  const uint16_t hueinc16 = ((beatsin88_t(113, 60, 300) >> 4) + 10) * (SEGMENT.intensity >> 3);  // NOTE-MED
  sPseudotime += duration * msmultiplier;
  sHue16 += duration * beatsin88_t(400, 5, 9);
  uint16_t brightnesstheta16 = sPseudotime;
  for (int i = 0; i < (int)SEGLEN; i++) {
    hue16 += hueinc16;
    uint8_t hue8;
    const uint16_t h16_128 = hue16 >> 7;
    if (h16_128 & 0x100) hue8 = 255 - (h16_128 >> 1);
    else                 hue8 = h16_128 >> 1;
    brightnesstheta16 += brightnessthetainc16;
    const uint16_t b16 = sin16_t(brightnesstheta16) + 32768;
    const uint16_t bri16 = (uint32_t)((uint32_t)b16 * (uint32_t)b16) / 65536;
    uint8_t bri8 = (uint32_t)(((uint32_t)bri16) * brightdepth) / 65536;
    bri8 += (255 - brightdepth);
    SEGMENT.blendPixelColor(i, SEGMENT.color_from_palette(hue8, false, PALETTE_SOLID_WRAP, 0, bri8), 128);
  }
  SEGENV.step = sPseudotime;
  SEGENV.aux0 = sHue16;
}
static const char _data_FX_MODE_GLORB_COLORWAVES[] PROGMEM = "Colorwaves@Speed,Intensity,,,,Sound Reactive;!;!;2vg";

// ---- Running (fork fx 190) — MED-HIGH ------------------------------------
// sx=Speed (persistent accumulator), ix=Wave width ((ix>>2)+12),
// check1=Sound Reactive (NOTE-AUDIO: no-op). Background blend color is BLACK
// (fork) rather than SEGCOLOR(1). Palette index kept as the stock mapped i —
// NOTE-MED: the decompile suggests a time/phase-derived index; revisit if the
// gate flags p4/p5.
static void glorb_mode_running(void) {
  SEGENV.step += (SEGMENT.speed >> 6) + 1;
  const uint16_t phase = (uint16_t)SEGENV.step;
  const uint8_t x_scale = (SEGMENT.intensity >> 2) + 12;
  for (int i = 0; i < (int)SEGLEN; i++) {
    const uint8_t s = sin8_t((uint8_t)(i * x_scale + phase));
    const uint32_t pcol = SEGMENT.color_from_palette(i, true, PALETTE_SOLID_WRAP, 0);
    SEGMENT.setPixelColor(i, color_blend(BLACK, pcol, s));
  }
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
  const int offsetX = beatsin16_t(3, -amp, amp);
  const int offsetY = beatsin16_t(2, -amp, amp);
  const int sharpness = SEGMENT.custom1 >> 6;
  const uint16_t hmul = beatsin16_t(10, 1, 10);
  for (int x = 0; x < cols; x++) {
    for (int y = 0; y < rows; y++) {
      uint8_t bri = sin8_t((uint8_t)(x * SEGMENT.speed / 2 + offsetX));
      size_t inten = bri;
      for (int i = 0; i < sharpness; i++) inten *= bri;
      inten >>= 8 * sharpness;
      uint8_t hue = x * hmul + offsetY;
      SEGMENT.setPixelColorXY(x, y, ColorFromPalette(SEGPALETTE, hue, inten, LINEARBLEND));
      bri = sin8_t((uint8_t)(y * SEGMENT.intensity / 2 + offsetY));
      inten = bri;
      for (int i = 0; i < sharpness; i++) inten *= bri;
      inten >>= 8 * sharpness;
      hue = y * 3 + offsetX;
      SEGMENT.addPixelColorXY(x, y, ColorFromPalette(SEGPALETTE, hue, inten, LINEARBLEND));
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
