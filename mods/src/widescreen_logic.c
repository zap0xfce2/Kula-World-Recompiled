#include "widescreen_logic.h"

/* Same bounds test the game uses for its own tile cull (exclusive). */
static int in_open_range(int x, int lo, int hi) { return x > lo && x < hi; }

int ws_band_tile_x(int x, int width, int margin, int* out_x) {
    if (margin <= 0 || in_open_range(x, -WS_BG_TILE_SIZE, width + WS_BG_TILE_SIZE)) return 0;
    const int lo = -WS_BG_TILE_SIZE - margin;
    const int hi = width + WS_BG_TILE_SIZE + margin;
    /* The field is wider than any band span, so at most one wrap position fits;
     * it never overlaps a real tile because the field itself is contiguous. */
    const int candidates[] = {x, x + WS_BG_FIELD_WIDTH, x - WS_BG_FIELD_WIDTH};
    for (unsigned i = 0; i < sizeof candidates / sizeof candidates[0]; ++i) {
        if (!in_open_range(candidates[i], lo, hi)) continue;
        *out_x = candidates[i];
        return 1;
    }
    return 0;
}
