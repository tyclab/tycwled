#pragma once
// The TycStation squid patterns of curtain/squid/draw.js as functions of time and position. Nothing here uses WLED:
// tests/tycstation_fx_host.cpp renders the same code on the host. Lengths are draw.js canvas units (one curtain cell).
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace tycfx {

constexpr float kPi = 3.14159265f, kTau = 6.28318531f;
// fleet/tycstation/mkpalette.py STOPS: position, R, G, B (blue, violet, red, violet, blue).
constexpr uint8_t kStops[20] = {0, 90, 162, 255, 61, 139, 108, 240, 128, 255, 74, 61,
                                195, 139, 108, 240, 255, 90, 162, 255};
// WLED 16's output table for colour gamma 2.8 (colors.cpp calcGammaTable).
constexpr uint8_t kGamma28[256] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2,
    2, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7,
    7, 8, 8, 8, 9, 9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 13, 13, 13, 14, 14, 15, 15, 16, 16,
    17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22, 23, 24, 24, 25, 25, 26, 27, 27, 28, 29, 29, 30,
    31, 32, 32, 33, 34, 35, 35, 36, 37, 38, 39, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 50,
    51, 52, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 66, 67, 68, 69, 70, 72, 73, 74, 75, 77, 78,
    79, 81, 82, 83, 85, 86, 87, 89, 90, 92, 93, 95, 96, 98, 99, 101, 102, 104, 105, 107, 109, 110, 112, 114,
    115, 117, 119, 120, 122, 124, 126, 127, 129, 131, 133, 135, 137, 138, 140, 142, 144, 146, 148, 150, 152, 154, 156, 158,
    160, 162, 164, 167, 169, 171, 173, 175, 177, 180, 182, 184, 186, 189, 191, 193, 196, 198, 200, 203, 205, 208, 210, 213,
    215, 218, 220, 223, 225, 228, 231, 233, 236, 239, 241, 244, 247, 249, 252, 255};

struct Rgb {
  float r, g, b;
};
inline Rgb operator*(Rgb c, float k) { return {c.r * k, c.g * k, c.b * k}; }
inline Rgb operator+(Rgb a, Rgb b) { return {a.r + b.r, a.g + b.g, a.b + b.b}; }

inline float clamp01(float x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
inline float ease(float u) { return u * u * (3 - 2 * u); }
inline float frac(float x) { return x - std::floor(x); }
// sin() to 2e-4, the same polynomial on the lamp and on the host
inline float fsin(float x) {
  x -= kTau * std::floor(x / kTau + .5f);
  if (x > kPi / 2) x = kPi - x;
  else if (x < -kPi / 2) x = -kPi - x;
  const float x2 = x * x;
  return x * (1 - x2 / 6 * (1 - x2 / 20 * (1 - x2 / 42)));
}
// draw.js hash() needs doubles, so it runs once per cell or speck, never per frame
inline float hash(double a, double b) {
  const double x = std::sin(a * 127.1 + b * 311.7) * 43758.5453;
  return float(x - std::floor(x));
}

// A lamp with colour gamma on applies its own table in show(); with it off this applies 2.8, so every lamp puts a
// 2.8 lamp's values on the wire. The palette stops get the same encoding (fleet/tycstation/glorb/palette6.json).
// A canvas radial gradient's cone of radius r averaged over the LED's square (side k) on an n x n grid, as the GIFs'
// supersampling averages it; n 1 along a strip's missing axis.
inline float cover(float dx, float dy, float r, float k, int nx, int ny) {
  float sum = 0;
  for (int i = 0; i < nx; i++)
    for (int j = 0; j < ny; j++) {
      const float x = dx + ((i + .5f) / nx - .5f) * k * (nx > 1), y = dy + ((j + .5f) / ny - .5f) * k * (ny > 1);
      const float d2 = x * x + y * y;
      if (d2 < r * r) sum += 1 - std::sqrt(d2) / r;
    }
  return sum / (nx * ny);
}

inline uint8_t wire(float v, bool lampGamma) {
  const uint8_t b = v >= 255 ? 255 : v <= 0 ? 0 : uint8_t(v + .5f);
  return lampGamma ? b : kGamma28[b];
}
inline void encode(Rgb c, bool lampGamma, uint8_t out[3]) {
  out[0] = wire(c.r, lampGamma);
  out[1] = wire(c.g, lampGamma);
  out[2] = wire(c.b, lampGamma);
}
inline void paletteBytes(bool lampGamma, uint8_t out[20]) {
  for (int i = 0; i < 20; i++) out[i] = (i % 4 == 0 || lampGamma) ? kStops[i] : kGamma28[kStops[i]];
}

// The mark's gradient as drawn, u 0 the blue end and 1 the red one: the palette's first half (positions 0-128).
inline Rgb gradient(float u) {
  const float p = clamp01(u) * kStops[8];
  const int k = p < kStops[4] ? 0 : 4;
  const float f = (p - kStops[k]) / (kStops[k + 4] - kStops[k]);
  auto mix = [&](int c) { return kStops[k + c] + (kStops[k + 4 + c] - kStops[k + c]) * f; };
  return {mix(1), mix(2), mix(3)};
}
// draw.js plankton colours: blue, violet, eye
inline Rgb speckMark(int i) {
  static const Rgb eye = {180, 140, 245};
  return i % 3 == 2 ? eye : gradient(i % 3 ? float(kStops[4]) / kStops[8] : 0);
}

// ---- Squid Arms: armWaves(), waves running outward from the middle of the row, one period per 2 s. perHalf
// waves on each half (halved under 16 LEDs, as drawn); height scales the wave above its floor, 1 as drawn.
constexpr float kArmsLoop = 2;
template <class Colour>
inline Rgb armsColumn(int x, int w, float t, float perHalf, float height, Colour colour) {
  const float n = w >= 16 ? perHalf : std::fmax(1.f, perHalf / 2);
  const float s = .5f + .5f * fsin(std::fabs(x - (w - 1) * .5f) * kTau * n / (w * .5f) - kPi * t);
  return colour(w > 1 ? float(x) / (w - 1) : 0.f) * (.08f + .92f * height * s * s * s);
}

// ---- Squid Skin: LOOPS.f's cells without the squid. A jittered grid 4 x 3.9 apart pulses in four patterns over
// 12 s: diagonal waves, rings from the middle, a sweep, every cell at its own rate. Each cell is a dot whose radius
// and alpha follow its level; dots add up. A strip is one row of cells.
constexpr float kSkinLoop = 12;
// 2 x 2 samples per LED: 4 x 4 moved the wire sum against Chromium's frames from +3.3 % only to +2.6 %
constexpr int kSkinSamples = 2;
struct SkinCell {
  float x, y, r;
  uint16_t h, hp;
  uint8_t c[3];
};
struct SkinGrid {
  float k, w, h;  // k: drawing units per LED; w, h: the segment in drawing units, h 0 on a strip
  int nx, ny;
};
inline SkinGrid skinGrid(int W, int H, float pitch) {
  if (H > 1) pitch = std::fmin(pitch, std::fmin(W, H) / 3.f);  // three cells or more across a matrix's short side
  SkinGrid g;
  g.k = 4 / pitch;
  g.w = W * g.k;
  g.h = H > 1 ? H * g.k : 0;
  g.nx = int(std::ceil(g.w / 4));
  g.ny = H > 1 ? int(std::ceil(g.h / 3.9f)) : 1;
  return g;
}
inline void skinInit(const SkinGrid &g, SkinCell *cells) {
  for (int cy = 0; cy < g.ny; cy++)
    for (int cx = 0; cx < g.nx; cx++) {
      SkinCell &c = cells[cy * g.nx + cx];
      c.x = 2 + cx * 4 + (hash(cx, cy) - .5f) * 1.6f + (cy % 2) * 2 - 1;
      c.y = g.h > 0 ? 2 + cy * 3.9f + (hash(cy, cx + 40) - .5f) * 1.6f : 0;
      c.h = uint16_t(hash(cx + 7, cy) * 65535 + .5f);
      c.hp = uint16_t(hash(cy, cx) * 65535 + .5f);
    }
}
template <class Colour>
inline void skinFrame(const SkinGrid &g, SkinCell *cells, float t, float strength, Colour colour) {
  const float L = kSkinLoop;
  auto w = [&](float k) { return kTau * k * t / L; };
  auto win = [&](float at) {
    const float d = std::fabs(t - at);
    return ease(clamp01(2 - std::fmin(d, L - d)));
  };
  const float w1 = win(1.5f), w2 = win(4.5f), w3 = win(7.5f), w4 = win(10.5f);
  const float band = -14 + (t - 5.5f) / 4 * (g.w + 28);
  for (int i = 0; i < g.nx * g.ny; i++) {
    SkinCell &c = cells[i];
    const float h = c.h / 65535.f;
    const float v = w1 * fsin(c.x * .2f + c.y * .12f - w(6) + h * 1.2f) +
                    w2 * fsin(std::hypot(c.x - g.w / 2, (c.y - g.h / 2) * 1.3f) * .42f - w(9)) +
                    w3 * (1 - 2 * clamp01(std::fabs(c.x - band) / 9)) +
                    w4 * fsin(w(6 + std::floor(h * 6)) + c.hp / 65535.f * kTau);
    const float s = ease(clamp01(v * strength * .6f + .5f));
    c.r = .9f + 2.4f * s;
    const float u = (1 - w3) * (.5f + .5f * fsin(c.x * .06f + c.y * .05f - w(1))) + w3 * c.x / g.w;
    const Rgb col = colour(u) * (.25f + .75f * s);
    c.c[0] = uint8_t(col.r + .5f);
    c.c[1] = uint8_t(col.g + .5f);
    c.c[2] = uint8_t(col.b + .5f);
  }
}
template <class Put>
inline void skinDraw(const SkinGrid &g, const SkinCell *cells, int W, int H, Put put) {
  for (int py = 0; py < H; py++) {
    const float v = g.h > 0 ? (py + .5f) * g.k : 0;
    const int y0 = g.h > 0 ? std::max(0, int(std::floor((v - 6.1f) / 3.9f))) : 0;
    const int y1 = g.h > 0 ? std::min(g.ny - 1, int(std::floor((v + 2.1f) / 3.9f))) : 0;
    for (int px = 0; px < W; px++) {
      const float u = (px + .5f) * g.k;
      const int x0 = std::max(0, int(std::floor((u - 7.1f) / 4))), x1 = std::min(g.nx - 1, int(std::floor((u + 3.1f) / 4)));
      Rgb sum = {0, 0, 0};
      for (int cy = y0; cy <= y1; cy++)
        for (int cx = x0; cx <= x1; cx++) {
          const SkinCell &c = cells[cy * g.nx + cx];
          const float dx = u - c.x, dy = v - c.y, reach = c.r + g.k * .71f;
          if (dx * dx + dy * dy >= reach * reach) continue;
          const float f = cover(dx, dy, c.r, g.k, kSkinSamples, g.h > 0 ? kSkinSamples : 1);
          sum = sum + Rgb{float(c.c[0]), float(c.c[1]), float(c.c[2])} * f;
        }
      put(px, py, sum);
    }
  }
}

// ---- Squid Plankton: LOOPS.c's water, specks rising through dim blue water and twinkling, over 16 s. A strip is
// the water column, its first LED at the surface.
constexpr float kPlanktonLoop = 16;
struct Speck {
  float sp, ph, x0, y0, tw, x, y;
  uint8_t c[3];
};
// The drawing's 44 specks per 68 x 42 cells, times density; a strip counts as a column two cells wide.
inline int speckCount(int W, int H, float density) { return int(std::lround((W > 1 ? W : 2) * H * 44.f / (68 * 42) * density)); }
inline void planktonInit(int n, int W, int H, Speck *s) {
  for (int i = 0; i < n; i++) {
    const float life = kPlanktonLoop / (1 + i % 2);
    s[i].sp = .5f + hash(i, 1) * 1.5f;
    s[i].ph = hash(i, 5);
    s[i].x0 = hash(i, 2) * W;
    s[i].y0 = hash(i, 3) * (H + 8) - 4 + s[i].sp * life / 2;
    s[i].tw = std::fmax(1.f, std::round((.5f + hash(i, 4)) * kPlanktonLoop / kPi));
  }
}
template <class Colour>
inline void planktonFrame(int n, int W, Speck *s, float t, float strength, Colour colour) {
  for (int i = 0; i < n; i++) {
    const float life = kPlanktonLoop / (1 + i % 2), tau = frac(t / life + s[i].ph) * life;
    const float env = std::fmin(1.f, 2.5f * fsin(kPi * tau / life));
    s[i].x = std::fmod(std::fmod(s[i].x0 + fsin(kTau * t / kPlanktonLoop + i) * 1.5f + tau * s[i].sp * .3f, float(W)) + W, float(W));
    s[i].y = s[i].y0 - s[i].sp * tau;
    const float a = (.3f + .7f * strength * std::fabs(fsin(kPi * s[i].tw * t / kPlanktonLoop + i))) * .85f * env;
    const Rgb c = colour(i) * a;
    s[i].c[0] = uint8_t(c.r + .5f);
    s[i].c[1] = uint8_t(c.g + .5f);
    s[i].c[2] = uint8_t(c.b + .5f);
  }
}
// draw.js's water, rgba(18,40,100,.85) at the top to rgba(3,5,16,.4) at the bottom over black; colour and alpha
// interpolate apart, as Chromium's canvas does
inline Rgb water(int py, int H) {
  const float f = (py + .5f) / H;
  return (Rgb{18, 40, 100} * (1 - f) + Rgb{3, 5, 16} * f) * (.85f - .45f * f);
}
template <class Put>
inline void planktonDraw(int n, int W, int H, const Speck *s, Put put) {
  auto at = [&](int px, int py) {
    Rgb sum = water(py, H);
    for (int i = 0; i < n; i++) {
      const float dx = W > 1 ? px + .5f - s[i].x : 0, dy = py + .5f - s[i].y;
      if (dx * dx + dy * dy < 1.71f * 1.71f)
        sum = sum + Rgb{float(s[i].c[0]), float(s[i].c[1]), float(s[i].c[2])} * cover(dx, dy, 1, 1, W > 1 ? 4 : 1, 4);
    }
    return sum;
  };
  for (int py = 0; py < H; py++) {
    const Rgb c = water(py, H);
    for (int px = 0; px < W; px++) put(px, py, c);
  }
  // only the LEDs within a speck's reach differ from the water; each gets the sum of every speck near it
  for (int i = 0; i < n; i++) {
    const int ya = std::max(0, int(std::floor(s[i].y - 2))), yb = std::min(H - 1, int(std::floor(s[i].y + 1)));
    const int xa = W > 1 ? std::max(0, int(std::floor(s[i].x - 2))) : 0, xb = W > 1 ? std::min(W - 1, int(std::floor(s[i].x + 1))) : 0;
    for (int py = ya; py <= yb; py++)
      for (int px = xa; px <= xb; px++) put(px, py, at(px, py));
  }
}

}  // namespace tycfx
