/* Unit test for the pure level-select logic; one check per test function. */
#include <assert.h>
#include <stdio.h>
#include "level_select_logic.h"

static LsState opened(void) {
    LsState s;
    ls_reset(&s);
    s.open = 1;
    return s;
}

static LsState reset(void) {
    LsState s;
    ls_reset(&s);
    return s;
}

static void test_reset_starts_at_world1(void) { assert(reset().world == 0); }
static void test_reset_starts_at_level1(void) { assert(reset().level == 0); }
static void test_reset_cursor_on_start(void) { assert(reset().cursor == LS_ITEM_START); }
static void test_reset_closed(void) { assert(!reset().open); }

static void test_down_wraps_after_level(void) {
    LsState s = opened();
    s.cursor = LS_ITEM_LEVEL;
    ls_menu_input(&s, LS_PAD_D);
    assert(s.cursor == LS_ITEM_START);
}

static void test_up_wraps_before_start(void) {
    LsState s = opened();
    ls_menu_input(&s, LS_PAD_U);
    assert(s.cursor == LS_ITEM_LEVEL);
}

static void test_world_left_wraps_to_10(void) {
    LsState s = opened();
    s.cursor = LS_ITEM_WORLD;
    ls_menu_input(&s, LS_PAD_L);
    assert(s.world == LS_WORLD_COUNT - 1);
}

static void test_level_right_wraps_to_1(void) {
    LsState s = opened();
    s.cursor = LS_ITEM_LEVEL;
    s.level = LS_LEVEL_COUNT - 1;
    ls_menu_input(&s, LS_PAD_R);
    assert(s.level == 0);
}

static void test_right_on_start_keeps_world(void) {
    LsState s = opened();
    ls_menu_input(&s, LS_PAD_R);
    assert(s.world == 0);
}

static void test_right_on_start_keeps_level(void) {
    LsState s = opened();
    ls_menu_input(&s, LS_PAD_R);
    assert(s.level == 0);
}

static void test_dpad_returns_move(void) {
    LsState s = opened();
    assert(ls_menu_input(&s, LS_PAD_D) == LS_ACT_MOVE);
}

static void test_cross_on_start_confirms(void) {
    LsState s = opened();
    assert(ls_menu_input(&s, LS_PAD_CROSS) == LS_ACT_CONFIRM);
}

static void test_cross_on_world_does_not_confirm(void) {
    LsState s = opened();
    s.cursor = LS_ITEM_WORLD;
    assert(ls_menu_input(&s, LS_PAD_CROSS) == LS_ACT_NONE);
}

static void test_triangle_closes(void) {
    LsState s = opened();
    ls_menu_input(&s, LS_PAD_TRIANGLE);
    assert(!s.open);
}

static void test_triangle_returns_back(void) {
    LsState s = opened();
    assert(ls_menu_input(&s, LS_PAD_TRIANGLE) == LS_ACT_BACK);
}

static void test_circle_closes(void) {
    LsState s = opened();
    ls_menu_input(&s, LS_PAD_CIRCLE);
    assert(!s.open);
}

static void test_circle_returns_back(void) {
    LsState s = opened();
    assert(ls_menu_input(&s, LS_PAD_CIRCLE) == LS_ACT_BACK);
}

static void test_default_start_not_cheated(void) {
    LsState s = opened();
    assert(!ls_is_cheated_start(&s));
}

static void test_level_change_is_cheated(void) {
    LsState s = opened();
    s.level = 2;
    assert(ls_is_cheated_start(&s));
}

static void test_skip_reload_when_same_world(void) {
    LsState s = opened();
    s.level = 4;
    assert(ls_skip_reload(&s, 0));
}

static void test_reload_when_other_world(void) {
    LsState s = opened();
    s.world = 6;
    assert(!ls_skip_reload(&s, 0));
}

static void test_arcade_index_normal(void) { assert(ls_arcade_index(0) == 0); }
static void test_arcade_index_final_unlocked(void) { assert(ls_arcade_index(1) == 1); }

static void test_strict_applies_only_in_arcade(void) { assert(!ls_strict_applies(1, 2, 1)); }
static void test_strict_applies_to_gameover_entry(void) { assert(ls_strict_applies(1, 0, 1)); }
static void test_strict_ignores_score_table_view(void) { assert(!ls_strict_applies(1, 0, 0)); }

static void test_vblank_closes_abandoned_submenu(void) {
    LsState s = opened();
    for (int i = 0; i < LS_MAX_MISSED_VBLANKS; ++i) ls_on_vblank(&s);
    assert(!s.open);
}

/* The game may run its menu at half the VBlank rate; one gap is normal. */
static void test_vblank_keeps_submenu_over_short_gap(void) {
    LsState s = opened();
    ls_on_vblank(&s);
    assert(s.open);
}

/* A cheated game quit without game over must not taint a later Load Game. */
static void test_strict_cleared_in_main_menu(void) { assert(!ls_keep_strict(1, 0)); }
static void test_strict_kept_during_play(void) { assert(ls_keep_strict(1, 1)); }

int main(void) {
    test_reset_starts_at_world1();
    test_reset_starts_at_level1();
    test_reset_cursor_on_start();
    test_reset_closed();
    test_down_wraps_after_level();
    test_up_wraps_before_start();
    test_world_left_wraps_to_10();
    test_level_right_wraps_to_1();
    test_right_on_start_keeps_world();
    test_right_on_start_keeps_level();
    test_dpad_returns_move();
    test_cross_on_start_confirms();
    test_cross_on_world_does_not_confirm();
    test_triangle_closes();
    test_triangle_returns_back();
    test_circle_closes();
    test_circle_returns_back();
    test_default_start_not_cheated();
    test_level_change_is_cheated();
    test_skip_reload_when_same_world();
    test_reload_when_other_world();
    test_arcade_index_normal();
    test_arcade_index_final_unlocked();
    test_strict_applies_only_in_arcade();
    test_strict_applies_to_gameover_entry();
    test_strict_ignores_score_table_view();
    test_vblank_closes_abandoned_submenu();
    test_vblank_keeps_submenu_over_short_gap();
    test_strict_cleared_in_main_menu();
    test_strict_kept_during_play();
    puts("level_select_logic: all tests passed");
    return 0;
}
