/* Pure decisions for the Kula World widescreen band fill.
 * No guest access here so it can be unit tested on the host. */
#pragma once

/* PsxButtonBackground: a scrolling field of 20x10 tiles, 48 px each. */
enum { WS_BG_TILE_SIZE = 48, WS_BG_FIELD_WIDTH = 20 * WS_BG_TILE_SIZE };

/* Where to draw a tile the game culled so it fills a side band; returns 0 when
 * the game draws it itself or no band position exists. */
int ws_band_tile_x(int x, int width, int margin, int* out_x);

/* gteXScale for the sky: RenderNonSpecialBackground's mesh only covers the 4:3
 * view, so stretch it by the widening (width + 2 * margin) / width. */
int ws_sky_x_scale(int scale, int width, int margin);
