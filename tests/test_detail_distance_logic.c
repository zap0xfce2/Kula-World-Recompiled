/* Unit test for the detail-distance thresholds; one check per test function. */
#include <assert.h>
#include <stdio.h>
#include "detail_distance_logic.h"

static int table[DD_BLUR_PHASES * DD_LOD_COUNT];

static int at(int phase, int lod) { return table[phase * DD_LOD_COUNT + lod]; }

static void build(void) { dd_blur_table(DD_DETAIL_LODS, table); }

static void test_first_phase_is_the_raised_detail(void) {
    build();
    assert(at(0, 1) == DD_DETAIL_LODS[1]);
}

static void test_last_phase_reaches_the_game_turn_target(void) {
    build();
    assert(at(DD_BLUR_PHASES - 1, 3) == 15);
}

/* Same integer math as InitTurningMotionBlur: 89 + (23 - 89) * 30 / 100. */
static void test_phase_blends_like_the_game(void) {
    build();
    assert(at(1, 1) == 70);
}

static void test_draw_range_stays_original(void) { assert(DD_DETAIL_LODS[0] == 90); }

static void test_texture_bands_stay_below_draw_range(void) {
    assert(DD_DETAIL_LODS[1] < DD_DETAIL_LODS[0]);
}

int main(void) {
    test_first_phase_is_the_raised_detail();
    test_last_phase_reaches_the_game_turn_target();
    test_phase_blends_like_the_game();
    test_draw_range_stays_original();
    test_texture_bands_stay_below_draw_range();
    puts("detail_distance_logic: all tests passed");
    return 0;
}
