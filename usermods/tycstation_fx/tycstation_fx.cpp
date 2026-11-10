#include "wled.h"
#include "tycstation_core.h"

// The TycStation squid patterns as WLED effects (Squid Arms, Squid Skin, Squid Plankton) and the TycStation palette
// as a usermod palette. The drawing lives in tycstation_core.h; this file connects it to segments, sliders and sound.

namespace {

const char kName[] PROGMEM = "TycStation";

struct Clock {
  float t;
  uint32_t last;
};

int markPaletteId() {
  for (size_t i = 0; i < usermodPalettes.size(); i++)
    if (usermodPalettes[i].name == kName) return WLED_USERMOD_PALETTE_ID_BASE - int(i);
  return -1;
}

// The default palette and the TycStation one draw the mark's gradient exactly; any other runs through the palette.
bool usesMark() { return SEGMENT.palette == 0 || SEGMENT.palette == markPaletteId(); }

tycfx::Rgb fromPalette(float u) {
  const uint32_t c = SEGMENT.color_from_palette(uint8_t(tycfx::clamp01(u) * 255 + .5f), false, false, 255);
  return {float(R(c)), float(G(c)), float(B(c))};
}

// Loop time in seconds; Speed 128 runs the drawing's own pace, every 64 steps double or halve it.
float advance(Clock &c, float loop) {
  if (SEGENV.call == 0) c = {0, strip.now};
  c.t = fmodf(c.t + (strip.now - c.last) * exp2f((SEGMENT.speed - 128) / 64.f) / 1000.f, loop);
  c.last = strip.now;
  return c.t;
}

// Sound 0 ignores the microphone. Otherwise silence lowers the pulse to 1 - Sound/510 of the drawing's (half at 255)
// and a smoothed volume of 128, the full scale of WLED's own Gravimeter, restores it. No sound data: as drawn.
float strength() {
  um_data_t *um;
  if (SEGMENT.intensity == 0 || !UsermodManager::getUMData(&um, USERMOD_ID_AUDIOREACTIVE)) return 1;
  const float drive = tycfx::clamp01(*(float *)um->u_data[0] / 128.f);
  return 1 - SEGMENT.intensity / 510.f * (1 - drive);
}

// A strip passes (i, 0) or (0, i); a matrix (x, y).
void put(int x, int y, tycfx::Rgb c) {
  uint8_t o[3];
  tycfx::encode(c, gammaCorrectCol, o);
  if (SEGMENT.is2D()) SEGMENT.setPixelColorXY(x, y, RGBW32(o[0], o[1], o[2], 0));
  else SEGMENT.setPixelColor(x + y, RGBW32(o[0], o[1], o[2], 0));
}

void mode_squid_arms() {
  if (!SEGENV.allocateData(sizeof(Clock))) { SEGMENT.fill(BLACK); return; }
  const float t = advance(*reinterpret_cast<Clock *>(SEGENV.data), tycfx::kArmsLoop);
  const bool is2D = SEGMENT.is2D(), mark = usesMark();
  const int w = is2D ? SEG_W : SEGLEN, h = is2D ? SEG_H : 1;
  const float perHalf = 1 + SEGMENT.custom1 / 64.f, height = strength();
  for (int x = 0; x < w; x++) {
    const tycfx::Rgb c = tycfx::armsColumn(x, w, t, perHalf, height, [&](float u) { return mark ? tycfx::gradient(u) : fromPalette(u); });
    for (int y = 0; y < h; y++) put(x, y, c);
  }
}
static const char _data_FX_SQUID_ARMS[] PROGMEM = "Squid Arms@!,Sound,Waves;;!;12v;sx=128,ix=192,c1=64,pal=0";

// The grid is rebuilt whenever the segment's size or the cell size changes.
struct SkinState {
  Clock clock;
  uint16_t w, h, size;
};

void mode_squid_skin() {
  const bool is2D = SEGMENT.is2D(), mark = usesMark();
  const int w = is2D ? SEG_W : SEGLEN, h = is2D ? SEG_H : 1;
  const tycfx::SkinGrid grid = tycfx::skinGrid(w, h, 2 + SEGMENT.custom1 * 6 / 255.f);
  const size_t cells = size_t(grid.nx) * grid.ny;
  if (!SEGENV.allocateData(sizeof(SkinState) + cells * sizeof(tycfx::SkinCell))) { SEGMENT.fill(BLACK); return; }
  SkinState &st = *reinterpret_cast<SkinState *>(SEGENV.data);
  tycfx::SkinCell *cell = reinterpret_cast<tycfx::SkinCell *>(SEGENV.data + sizeof(SkinState));
  if (SEGENV.call == 0 || st.w != w || st.h != h || st.size != SEGMENT.custom1) {
    st.w = w; st.h = h; st.size = SEGMENT.custom1;
    tycfx::skinInit(grid, cell);
  }
  const float t = advance(st.clock, tycfx::kSkinLoop);
  tycfx::skinFrame(grid, cell, t, strength(), [&](float u) { return mark ? tycfx::gradient(u) : fromPalette(u); });
  tycfx::skinDraw(grid, cell, w, h, put);
}
static const char _data_FX_SQUID_SKIN[] PROGMEM = "Squid Skin@!,Sound,Cell size;;!;12v;sx=128,ix=192,c1=85,pal=0";

struct PlanktonState {
  Clock clock;
  uint16_t w, h, n;
};

void mode_squid_plankton() {
  const bool is2D = SEGMENT.is2D(), mark = usesMark();
  const int w = is2D ? SEG_W : 1, h = is2D ? SEG_H : SEGLEN;
  const int n = tycfx::speckCount(w, h, SEGMENT.custom1 / 32.f);
  if (!SEGENV.allocateData(sizeof(PlanktonState) + n * sizeof(tycfx::Speck))) { SEGMENT.fill(BLACK); return; }
  PlanktonState &st = *reinterpret_cast<PlanktonState *>(SEGENV.data);
  tycfx::Speck *speck = reinterpret_cast<tycfx::Speck *>(SEGENV.data + sizeof(PlanktonState));
  if (SEGENV.call == 0 || st.w != w || st.h != h || st.n != n) {
    st.w = w; st.h = h; st.n = n;
    tycfx::planktonInit(n, w, h, speck);
  }
  const float t = advance(st.clock, tycfx::kPlanktonLoop);
  tycfx::planktonFrame(n, w, speck, t, strength(), [&](int i) {
    return mark ? tycfx::speckMark(i) : fromPalette((i % 3) / 3.f);
  });
  tycfx::planktonDraw(n, w, h, speck, put);
}
static const char _data_FX_SQUID_PLANKTON[] PROGMEM = "Squid Plankton@!,Sound,Specks;;!;12v;sx=128,ix=192,c1=32,pal=0";

}  // namespace

class TycStationFx : public Usermod {
  bool encoded = false;

  // The registered stops follow the lamp's colour gamma setting, also when it changes at runtime.
  void loadPalette() {
    uint8_t stops[20];
    tycfx::paletteBytes(gammaCorrectCol, stops);
    CRGBPalette16 pal;
    pal.loadDynamicGradientPalette(stops);
    for (auto &p : usermodPalettes)
      if (p.name == kName) p.palette = pal;
    encoded = !gammaCorrectCol;
  }

 public:
  void setup() override {
    strip.addEffect(255, &mode_squid_arms, _data_FX_SQUID_ARMS);
    strip.addEffect(255, &mode_squid_skin, _data_FX_SQUID_SKIN);
    strip.addEffect(255, &mode_squid_plankton, _data_FX_SQUID_PLANKTON);
    // First in the list, so the palette is ID 255 whatever AudioReactive adds or removes around it.
    if (usermodPalettes.size() < WLED_MAX_USERMOD_PALETTES)
      usermodPalettes.insert(usermodPalettes.begin(), UsermodPalette{CRGBPalette16(CRGB(BLACK)), kName, 0, nullptr});
    loadPalette();
  }
  void loop() override {
    if (encoded == gammaCorrectCol) loadPalette();
  }
};

static TycStationFx tycstation_fx;
REGISTER_USERMOD(tycstation_fx);
