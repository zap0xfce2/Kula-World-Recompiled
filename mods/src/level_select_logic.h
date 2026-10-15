/* Pure state and decisions for the Kula World arcade level-select submenu.
 * No guest access here so it can be unit tested on the host. */
#pragma once
#include <stdint.h>

enum { LS_WORLD_COUNT = 10, LS_LEVEL_COUNT = 15 };
/* Pad bits as the game stores them in controllerButtons (active-high). */
enum { LS_PAD_U = 0x0010, LS_PAD_R = 0x0020, LS_PAD_D = 0x0040, LS_PAD_L = 0x0080,
       LS_PAD_TRIANGLE = 0x1000, LS_PAD_CIRCLE = 0x2000, LS_PAD_CROSS = 0x4000 };

typedef enum { LS_ITEM_START, LS_ITEM_WORLD, LS_ITEM_LEVEL, LS_ITEM_COUNT } LsItem;
typedef enum { LS_ACT_NONE, LS_ACT_MOVE, LS_ACT_BACK, LS_ACT_CONFIRM } LsAction;

/* VBlanks without a menu-filter call after which the submenu counts as left. */
enum { LS_MAX_MISSED_VBLANKS = 8 };

typedef struct {
    int open;           /* submenu replaces the one-player menu */
    int cursor;         /* LsItem */
    int world;          /* 0-based */
    int level;          /* 0-based */
    int missed_vblanks; /* VBlanks since the menu filter last ran */
} LsState;

void ls_reset(LsState* s);
int ls_arcade_index(int final_unlocked);
LsAction ls_menu_input(LsState* s, uint32_t pressed);
int ls_is_cheated_start(const LsState* s);
int ls_skip_reload(const LsState* s, int loaded_world);
int ls_strict_applies(int strict_armed, int game_mode, int highscore_arg);
void ls_on_vblank(LsState* s);
int ls_keep_strict(int strict_armed, int game_state);
