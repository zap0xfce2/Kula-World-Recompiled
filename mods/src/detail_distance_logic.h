/* Pure thresholds for the Kula World detail-distance mod.
 * No guest access here so it can be unit tested on the host. */
#pragma once

/* tgi->lodDistance[7] in ordering-table steps (8 per block):
 * [0] draw range, [1..3] cube texture bands (full / 32 / 16 / 8 px),
 * [4] unknown, [5..6] item model steps (full / simple / disc). */
enum { DD_LOD_COUNT = 7, DD_BLUR_PHASES = 9 };

extern const int DD_DETAIL_LODS[DD_LOD_COUNT];

/* turningMotionBlurTable: phase 0 is the resting value, the later phases
 * blend towards the game's turn targets like InitTurningMotionBlur does. */
void dd_blur_table(const int base[DD_LOD_COUNT], int out[DD_BLUR_PHASES * DD_LOD_COUNT]);
