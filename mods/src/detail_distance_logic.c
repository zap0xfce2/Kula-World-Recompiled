#include "detail_distance_logic.h"

/* Raising [0] blurred the far cubes again in the spike, so it stays at 90.
 * Item steps beyond any level size keep the full model. */
const int DD_DETAIL_LODS[DD_LOD_COUNT] = {90, 89, 88, 87, 80, 200, 200};

/* turningMotionBlurTargetLods and LOD_THRESHOLDS from the decomp (tgi.c). */
static const int TURN_TARGET_LODS[DD_LOD_COUNT] = {28, 23, 22, 15, 40, 30, 20};
static const int BLEND_PERCENT[DD_BLUR_PHASES] = {0, 30, 43, 55, 66, 76, 85, 93, 100};

void dd_blur_table(const int base[DD_LOD_COUNT], int out[DD_BLUR_PHASES * DD_LOD_COUNT]) {
    for (int lod = 0; lod < DD_LOD_COUNT; ++lod) {
        const int span = TURN_TARGET_LODS[lod] - base[lod];
        for (int phase = 0; phase < DD_BLUR_PHASES; ++phase)
            out[phase * DD_LOD_COUNT + lod] = base[lod] + span * BLEND_PERCENT[phase] / 100;
    }
}
