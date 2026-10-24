/* Unit test for the pure widescreen band logic; one check per test function. */
#include <assert.h>
#include <stdio.h>
#include "widescreen_logic.h"

enum { WIDTH = 320, MARGIN = 80 };

static int placed_x(int x) {
    int out = 0;
    ws_band_tile_x(x, WIDTH, MARGIN, &out);
    return out;
}

static void test_tile_in_4_3_view_left_to_game(void) {
    int out = 0;
    assert(!ws_band_tile_x(100, WIDTH, MARGIN, &out));
}

static void test_no_band_at_4_3(void) {
    int out = 0;
    assert(!ws_band_tile_x(-100, WIDTH, 0, &out));
}

static void test_left_band_tile_linked(void) {
    int out = 0;
    assert(ws_band_tile_x(-100, WIDTH, MARGIN, &out));
}

static void test_left_band_tile_keeps_x(void) { assert(placed_x(-100) == -100); }

static void test_right_band_tile_keeps_x(void) { assert(placed_x(400) == 400); }

static void test_tile_beyond_left_band_wraps_right(void) {
    assert(placed_x(-600) == -600 + WS_BG_FIELD_WIDTH);
}

static void test_tile_beyond_right_band_wraps_left(void) {
    assert(placed_x(900) == 900 - WS_BG_FIELD_WIDTH);
}

static void test_wrapped_tile_may_fill_field_seam(void) {
    assert(placed_x(-610) == 350);
}

static void test_tile_unreachable_by_wrap_skipped(void) {
    int out = 0;
    assert(!ws_band_tile_x(500, WIDTH, 10, &out));
}

/* The sky mesh covers the 4:3 view, so it is stretched by the widening. */
static void test_sky_scale_unchanged_at_4_3(void) { assert(ws_sky_x_scale(4096, WIDTH, 0) == 4096); }
static void test_sky_scale_widens_at_2_1(void) { assert(ws_sky_x_scale(4096, WIDTH, 80) == 6144); }
static void test_sky_scale_follows_game_scale(void) { assert(ws_sky_x_scale(2048, WIDTH, 80) == 3072); }

int main(void) {
    test_tile_in_4_3_view_left_to_game();
    test_no_band_at_4_3();
    test_left_band_tile_linked();
    test_left_band_tile_keeps_x();
    test_right_band_tile_keeps_x();
    test_tile_beyond_left_band_wraps_right();
    test_tile_beyond_right_band_wraps_left();
    test_wrapped_tile_may_fill_field_seam();
    test_tile_unreachable_by_wrap_skipped();
    test_sky_scale_unchanged_at_4_3();
    test_sky_scale_widens_at_2_1();
    test_sky_scale_follows_game_scale();
    puts("widescreen_logic: all tests passed");
    return 0;
}
