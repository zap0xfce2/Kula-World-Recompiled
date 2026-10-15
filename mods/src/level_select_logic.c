#include "level_select_logic.h"

/* gameMode value of the one-player arcade game (time trial is 2). */
enum { GAME_MODE_ARCADE = 0 };
/* HighScoreUi argument: 1 = game-over name entry, 0 = plain table. */
enum { HIGHSCORE_ENTRY = 1 };

static int wrap(int value, int count) { return (value % count + count) % count; }

void ls_reset(LsState* s) {
    s->open = 0;
    s->cursor = LS_ITEM_START;
    s->world = 0;
    s->level = 0;
    s->missed_vblanks = 0;
}

/* With the Final world unlocked the menu gains "Final" as entry 0. */
int ls_arcade_index(int final_unlocked) { return final_unlocked ? 1 : 0; }

static void step_value(LsState* s, int delta) {
    if (s->cursor == LS_ITEM_WORLD) s->world = wrap(s->world + delta, LS_WORLD_COUNT);
    if (s->cursor == LS_ITEM_LEVEL) s->level = wrap(s->level + delta, LS_LEVEL_COUNT);
}

LsAction ls_menu_input(LsState* s, uint32_t pressed) {
    if (pressed & LS_PAD_TRIANGLE) {
        s->open = 0;
        return LS_ACT_BACK;
    }
    if ((pressed & LS_PAD_CROSS) && s->cursor == LS_ITEM_START) return LS_ACT_CONFIRM;
    if (pressed & LS_PAD_U) s->cursor = wrap(s->cursor - 1, LS_ITEM_COUNT);
    if (pressed & LS_PAD_D) s->cursor = wrap(s->cursor + 1, LS_ITEM_COUNT);
    if (pressed & LS_PAD_L) step_value(s, -1);
    if (pressed & LS_PAD_R) step_value(s, +1);
    return (pressed & (LS_PAD_U | LS_PAD_D | LS_PAD_L | LS_PAD_R)) ? LS_ACT_MOVE : LS_ACT_NONE;
}

int ls_is_cheated_start(const LsState* s) { return s->world != 0 || s->level != 0; }

/* The game's Load Game path skips the reload when the world is already resident. */
int ls_skip_reload(const LsState* s, int loaded_world) { return s->world == loaded_world; }

int ls_strict_applies(int strict_armed, int game_mode, int highscore_arg) {
    return strict_armed && game_mode == GAME_MODE_ARCADE && highscore_arg == HIGHSCORE_ENTRY;
}

/* The menu filter runs every menu frame; a longer gap means the menu was left
 * (attract demo, quit), so the submenu must not reappear later. */
void ls_on_vblank(LsState* s) {
    if (++s->missed_vblanks >= LS_MAX_MISSED_VBLANKS) s->open = 0;
}
