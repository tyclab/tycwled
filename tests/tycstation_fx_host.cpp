// Renders usermods/tycstation_fx/tycstation_core.h on the host for tests/test_tycstation_fx.py, with the TycStation
// palette as the usermod's default draws it.
// usage: tycstation_fx_host arms|skin|plankton W H t0 dt frames lampGamma strength slider  -> raw RGB frames on stdout
//        tycstation_fx_host palette lampGamma                                              -> the 20 palette bytes
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "../usermods/tycstation_fx/tycstation_core.h"

int main(int argc, char **argv) {
  if (argc == 3 && !strcmp(argv[1], "palette")) {
    uint8_t b[20];
    tycfx::paletteBytes(atoi(argv[2]) != 0, b);
    fwrite(b, 1, sizeof b, stdout);
    return 0;
  }
  if (argc != 10) return 2;
  const char *fx = argv[1];
  const int W = atoi(argv[2]), H = atoi(argv[3]), frames = atoi(argv[6]), slider = atoi(argv[9]);
  const float t0 = float(atof(argv[4])), dt = float(atof(argv[5])), strength = float(atof(argv[8]));
  const bool lampGamma = atoi(argv[7]) != 0;
  std::vector<uint8_t> px(size_t(W) * H * 3);
  auto put = [&](int x, int y, tycfx::Rgb c) { tycfx::encode(c, lampGamma, &px[(size_t(y) * W + x) * 3]); };
  const tycfx::SkinGrid grid = tycfx::skinGrid(W, H, 2 + slider * 6 / 255.f);
  std::vector<tycfx::SkinCell> cells(size_t(grid.nx) * grid.ny);
  tycfx::skinInit(grid, cells.data());
  // a strip is the plankton's water column
  const int pw = H > 1 ? W : 1, ph = H > 1 ? H : W, n = tycfx::speckCount(pw, ph, slider / 32.f);
  std::vector<tycfx::Speck> specks(n);
  tycfx::planktonInit(n, pw, ph, specks.data());
  for (int f = 0; f < frames; f++) {
    const float t = t0 + f * dt;
    if (!strcmp(fx, "arms")) {
      for (int x = 0; x < W; x++) {
        const tycfx::Rgb c = tycfx::armsColumn(x, W, t, 1 + slider / 64.f, strength, tycfx::gradient);
        for (int y = 0; y < H; y++) put(x, y, c);
      }
    } else if (!strcmp(fx, "skin")) {
      tycfx::skinFrame(grid, cells.data(), t, strength, tycfx::gradient);
      tycfx::skinDraw(grid, cells.data(), W, H, put);
    } else if (!strcmp(fx, "plankton")) {
      tycfx::planktonFrame(n, pw, specks.data(), t, strength, tycfx::speckMark);
      tycfx::planktonDraw(n, pw, ph, specks.data(), [&](int x, int y, tycfx::Rgb c) { put(H > 1 ? x : y, H > 1 ? y : 0, c); });
    } else {
      return 2;
    }
    fwrite(px.data(), 1, px.size(), stdout);
  }
  return 0;
}
