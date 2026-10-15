# Level Select Mod Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An arcade submenu (START / WORLD 1-10 / LEVEL 1-15) that starts the one-player game at any level. It ships as a launcher mod that is on by default.

**Architecture:** A trusted static psxrecomp plugin linked into the runtime.
- **Menu hook:** a function filter on `SinglePlayerMenu` replaces the menu body while the submenu is open. On confirm, it calls the original body so the game's real start path runs, then redirects the load the same way the game's own "Load Game" path does.
- **High-score hook:** a second filter on `HighScoreUi` turns the game-over entry (`a0 = 1`) into the plain score table (`a0 = 0`) after a non-1/1 start.
- **Testable core:** the decision logic is pure C with a unit test.

**Tech Stack:** C99 (runtime plugin), psxrecomp mod API (`psxrecomp/runtime/include/mod_plugins.h`), CMake/Ninja, go-task, Python 3 stdlib (integration check over the debug server).

**Spec:** `docs/superpowers/specs/2026-10-15-level-select-design.md`

## Global Constraints
- Never commit game data: no BIOS, no `.bin`/`.cue`, no `SCES_*`, no extracted assets, no `generated/`.
- Never hand-edit generated code. Hooks are enabled only through `game.toml [recompiler] mod_function_entry_funcs` plus a regenerate.
- No printf/fprintf debugging. Inspect through debug-server commands and `psx_mod_counter_add`.
- Package id `kula.level-select`, version `1.0.0`, plugin id `kula.level-select`, feature id `level-select`, group "Quality of Life", `default_enabled = true`.
- World 1-10 and level 1-15 are shown 1-based and stored 0-based in guest RAM (`curWorld` 0-9, `curLevel` 0-14).
- A start at 1/1 must behave exactly like the original arcade start.
- Python: type hints, no `Any`, ruff + black clean.
- Code comments: short, explain the why, no decorative blocks.
- Conventional commits in English, no AI attribution lines.

## Review Focus
- **Submenu left without confirming** (the attract demo starts after 2000 idle frames, or the player backs out): reopening the one-player menu must show the original menu, not a stale submenu. Pinned by the frame-gap reset test in Task 1 and the `ls_on_vblank` behaviour in Task 2.
- **Final world unlocked** (`finalUnlocked == 1`): arcade is cursor entry 1, not 0. Choosing "Final" (entry 0) must still work unchanged. Pinned by `test_arcade_index_*` in Task 1 and checked in Task 4 by setting `finalUnlocked` over the debug server.
- **Time trial after a cheated arcade game:** time trial must keep its normal high-score entry. Pinned by `test_strict_applies_only_in_arcade` in Task 1.
- **Same world as the backdrop** (world 1 picked, level ≠ 1): `skipNextLoad` must be set, otherwise the world is reloaded needlessly. Pinned by `test_skip_reload_when_same_world` in Task 1.
- **Mod disabled in the launcher:** the original menu must be untouched and the demo must still run. Checked in Task 4 through `mods/state.toml`.

---

### Task 1: Pure level-select logic with unit test

**Files:**
- Create: `mods/src/level_select_logic.h`
- Create: `mods/src/level_select_logic.c`
- Create: `tests/test_level_select_logic.c`
- Modify: `Taskfile.yaml` (task `test` also builds and runs the C test)

**Interfaces:**
- Produces (used by Task 2):
```c
enum { LS_WORLD_COUNT = 10, LS_LEVEL_COUNT = 15 };
enum { LS_PAD_U = 0x0010, LS_PAD_R = 0x0020, LS_PAD_D = 0x0040, LS_PAD_L = 0x0080,
       LS_PAD_TRIANGLE = 0x1000, LS_PAD_CROSS = 0x4000 };
typedef enum { LS_ITEM_START, LS_ITEM_WORLD, LS_ITEM_LEVEL, LS_ITEM_COUNT } LsItem;
typedef enum { LS_ACT_NONE, LS_ACT_MOVE, LS_ACT_BACK, LS_ACT_CONFIRM } LsAction;
typedef struct { int open; int cursor; int world; int level; int seen_this_frame; } LsState;
void ls_reset(LsState* s);
int ls_arcade_index(int final_unlocked);
LsAction ls_menu_input(LsState* s, uint32_t pressed);
int ls_is_cheated_start(const LsState* s);
int ls_skip_reload(const LsState* s, int loaded_world);
int ls_strict_applies(int strict_armed, int game_mode, int highscore_arg);
void ls_on_vblank(LsState* s);
```

- [ ] **Step 1: Write the failing test** at `tests/test_level_select_logic.c`:

```c
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

static void test_reset_starts_at_world1_level1(void) {
    LsState s;
    ls_reset(&s);
    assert(s.world == 0 && s.level == 0 && s.cursor == LS_ITEM_START && !s.open);
}

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

static void test_left_right_ignored_on_start(void) {
    LsState s = opened();
    ls_menu_input(&s, LS_PAD_R);
    assert(s.world == 0 && s.level == 0);
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

static void test_vblank_closes_unseen_submenu(void) {
    LsState s = opened();
    ls_on_vblank(&s); /* frame where the menu filter did not run */
    assert(!s.open);
}

static void test_vblank_keeps_seen_submenu(void) {
    LsState s = opened();
    s.seen_this_frame = 1;
    ls_on_vblank(&s);
    assert(s.open);
}

int main(void) {
    test_reset_starts_at_world1_level1();
    test_down_wraps_after_level();
    test_up_wraps_before_start();
    test_world_left_wraps_to_10();
    test_level_right_wraps_to_1();
    test_left_right_ignored_on_start();
    test_cross_on_start_confirms();
    test_cross_on_world_does_not_confirm();
    test_triangle_closes();
    test_default_start_not_cheated();
    test_level_change_is_cheated();
    test_skip_reload_when_same_world();
    test_reload_when_other_world();
    test_arcade_index_normal();
    test_arcade_index_final_unlocked();
    test_strict_applies_only_in_arcade();
    test_strict_applies_to_gameover_entry();
    test_strict_ignores_score_table_view();
    test_vblank_closes_unseen_submenu();
    test_vblank_keeps_seen_submenu();
    puts("level_select_logic: all tests passed");
    return 0;
}
```

- [ ] **Step 2: Wire it into `task test` and run it, expecting a compile failure.**

In `Taskfile.yaml`, replace the `test` task with:
```yaml
  test:
    desc: Unit tests (Python and C)
    cmds:
      - '{{.PYTHON}} -m unittest discover -s tests'
      - mkdir -p build-tests
      - cc -std=c99 -Wall -Wextra -Werror -Imods/src -o build-tests/test_level_select_logic tests/test_level_select_logic.c mods/src/level_select_logic.c
      - ./build-tests/test_level_select_logic
```
Run: `go-task test`
Expected: FAIL, `level_select_logic.h: No such file or directory`.

- [ ] **Step 3: Write `mods/src/level_select_logic.h`.**

```c
/* Pure state and decisions for the Kula World arcade level-select submenu.
 * No guest access here so it can be unit tested on the host. */
#pragma once
#include <stdint.h>

enum { LS_WORLD_COUNT = 10, LS_LEVEL_COUNT = 15 };
/* Pad bits as the game stores them in controllerButtons (active-high). */
enum { LS_PAD_U = 0x0010, LS_PAD_R = 0x0020, LS_PAD_D = 0x0040, LS_PAD_L = 0x0080,
       LS_PAD_TRIANGLE = 0x1000, LS_PAD_CROSS = 0x4000 };

typedef enum { LS_ITEM_START, LS_ITEM_WORLD, LS_ITEM_LEVEL, LS_ITEM_COUNT } LsItem;
typedef enum { LS_ACT_NONE, LS_ACT_MOVE, LS_ACT_BACK, LS_ACT_CONFIRM } LsAction;

typedef struct {
    int open;            /* submenu replaces the one-player menu */
    int cursor;          /* LsItem */
    int world;           /* 0-based */
    int level;           /* 0-based */
    int seen_this_frame; /* menu filter ran since the last VBlank */
} LsState;

void ls_reset(LsState* s);
int ls_arcade_index(int final_unlocked);
LsAction ls_menu_input(LsState* s, uint32_t pressed);
int ls_is_cheated_start(const LsState* s);
int ls_skip_reload(const LsState* s, int loaded_world);
int ls_strict_applies(int strict_armed, int game_mode, int highscore_arg);
void ls_on_vblank(LsState* s);
```

- [ ] **Step 4: Write `mods/src/level_select_logic.c`.**

```c
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
    s->seen_this_frame = 0;
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

/* The menu filter runs every menu frame; a frame without it means the menu
 * was left (attract demo, quit), so the submenu must not reappear later. */
void ls_on_vblank(LsState* s) {
    if (!s->seen_this_frame) s->open = 0;
    s->seen_this_frame = 0;
}
```

- [ ] **Step 5: Run the tests.**

Run: `go-task test`
Expected: Python `OK` and `level_select_logic: all tests passed`.

- [ ] **Step 6: Commit.**

```bash
git add mods/src/level_select_logic.h mods/src/level_select_logic.c tests/test_level_select_logic.c Taskfile.yaml
git commit -m "feat: add level select submenu logic with unit tests"
```
Also add `/build-tests/` is already covered by `/build-*/` in `.gitignore`; verify with `git check-ignore build-tests/x`.

---

### Task 2: Plugin glue, manifest, hooks and regenerate (spike first)

**Files:**
- Create: `mods/src/kula_level_select.c`
- Create: `mods/preloaded/packages/kula.level-select/1.0.0/manifest.toml`
- Modify: `CMakeLists.txt` (after `psxrecomp_add_game_runtime(...)`)
- Modify: `game.toml` (`[recompiler]`)

**Interfaces:**
- Consumes: everything from Task 1 (`level_select_logic.h`).
- Produces:
  - Debug-visible counters `kula.level-select.opened`, `.confirmed`, `.strict_skipped`, readable with the debug-server command `{"cmd":"mod_counters"}`.
  - Guest RAM effects checked by Task 3.

Guest addresses (EU, dezgeg decomp `config/eu-SCES_010.00`). Functions use the KUSEG code identity, data uses KSEG0:

| Symbol | Address |
|---|---|
| `SetTextParams` | 0x00014c10 |
| `DrawTextCrappyFont` | 0x00014c90 |
| `SinglePlayerMenu` | 0x000491a8 |
| `HighScoreUi` | 0x0004c09c |
| `SndPlaySfx` | 0x0004eb6c |
| `ZERO_SVECTOR_a3340` | 0x800a3340 |
| `curLevel` | 0x800a2ea0 |
| `curWorld` | 0x800a2ea4 |
| `curWorld2` | 0x800a2ea8 |
| `loadNewWorld` | 0x800a2eac |
| `skipNextLoad` | 0x800a2eb0 |
| `gameState` | 0x800a2ec0 |
| `gameMode` | 0x800a2e48 |
| `finalUnlocked` | 0x800a2ed8 |
| `cheated` | 0x800a4e0c |
| `cursorPosInMenu` | 0x800a4f20 (int[8], one-player menu is index 3) |
| `controllerButtons` | 0x800a5530 |
| `prevControllerButtons` | 0x800a50bc |
| `scoreText` | 0x800a4ab0 (128 bytes) |

- [ ] **Step 1: Enable the hooks in `game.toml`.** Under `[recompiler]`, after `strict = true`, add:

```toml
# Kula level-select mod hooks (mods/src/kula_level_select.c): SinglePlayerMenu, HighScoreUi
mod_function_entry_funcs = ["0x000491a8", "0x0004c09c"]
```

- [ ] **Step 2: Write the manifest** `mods/preloaded/packages/kula.level-select/1.0.0/manifest.toml`:

```toml
format_version = 7
id = "kula.level-select"
version = "1.0.0"
name = "Level Select"
author = "Kula World Recompiled"
description = "Arcade opens a submenu to start at any world and level."
resolver = "declarative"
save_compatibility = "shared"

[[target]]
game_id = "SCES-01000"

[[feature]]
id = "level-select"
name = "Level Select"
description = "Choosing Arcade opens START / WORLD / LEVEL. Starting anywhere but world 1, level 1 counts as cheated: no save points and no high-score entry."
group = "Quality of Life"
default_enabled = true

[[plugin]]
feature = "level-select"
id = "kula.level-select"
```
Check `game_id` against an existing title-specific manifest under `psxrecomp/mods/builtin` or the docs in `psxrecomp/docs/MOD_PACKAGES.md` ("Feature manifest"). If the serial format differs (for example `SCES_010.00`), use the documented form.

- [ ] **Step 3: Write the spike version of `mods/src/kula_level_select.c`.** This is the final file; the spike is just running it before Task 3.

```c
/* Kula World arcade level select: a function filter on SinglePlayerMenu draws
 * a START/WORLD/LEVEL submenu and redirects the arcade start; a filter on
 * HighScoreUi drops the name entry after a non-1/1 start.
 * Guest addresses: EU SCES-01000, from the dezgeg/kula-world-decomp config. */
#include <stdio.h>
#include "cpu_state.h"
#include "mod_plugins.h"
#include "level_select_logic.h"

#define PLUGIN_ID "kula.level-select"

enum {
    FN_SET_TEXT_PARAMS = 0x00014c10u,
    FN_DRAW_TEXT_CRAPPY = 0x00014c90u,
    FN_SINGLE_PLAYER_MENU = 0x000491a8u,
    FN_HIGHSCORE_UI = 0x0004c09cu,
    FN_SND_PLAY_SFX = 0x0004eb6cu,
};
enum {
    VAR_ZERO_SVECTOR = 0x800a3340u,
    VAR_CUR_LEVEL = 0x800a2ea0u,
    VAR_CUR_WORLD = 0x800a2ea4u,
    VAR_CUR_WORLD2 = 0x800a2ea8u,
    VAR_LOAD_NEW_WORLD = 0x800a2eacu,
    VAR_SKIP_NEXT_LOAD = 0x800a2eb0u,
    VAR_GAME_STATE = 0x800a2ec0u,
    VAR_GAME_MODE = 0x800a2e48u,
    VAR_FINAL_UNLOCKED = 0x800a2ed8u,
    VAR_CHEATED = 0x800a4e0cu,
    VAR_SINGLE_PLAYER_CURSOR = 0x800a4f20u + 3u * 4u,
    VAR_CONTROLLER_BUTTONS = 0x800a5530u,
    VAR_PREV_CONTROLLER_BUTTONS = 0x800a50bcu,
    VAR_SCORE_TEXT = 0x800a4ab0u,
};
enum { SFX_MENU_SELECTION_2 = 109, SFX_VOLUME = 8000 };
enum { SCORE_TEXT_SIZE = 128, MIPS_REG_A0 = 4, MIPS_REG_SP = 29, MIPS_REG_RA = 31 };
/* Layout in the 320x256 PAL menu space, centred like the game's menus. */
enum { TEXT_CENTER_X = 160, TEXT_TOP_Y = 104, TEXT_LINE_STEP = 18, TEXT_ALIGN_CENTER = 1 };
enum { COLOR_FULL = 128, COLOR_DIM = 64 };

static LsState g_state;
static int g_strict_armed;
static int g_calling_original;

static uint32_t newly_pressed(void) {
    return psx_mod_read_word(VAR_CONTROLLER_BUTTONS) &
           ~psx_mod_read_word(VAR_PREV_CONTROLLER_BUTTONS);
}

static void play_menu_sfx(struct CPUState* cpu) {
    psx_mod_call_guest(cpu, FN_SND_PLAY_SFX, cpu->gpr[MIPS_REG_RA], SFX_MENU_SELECTION_2, 0,
                       VAR_ZERO_SVECTOR, SFX_VOLUME);
}

/* SetTextParams takes six ints; o32 passes args 5 and 6 at sp+16/sp+20 of the
 * caller, so reserve a fresh frame below the live stack for them. */
static void set_text_params(struct CPUState* cpu, int x, int y, int r, int g, int b) {
    const uint32_t frame = 24;
    const uint32_t sp = cpu->gpr[MIPS_REG_SP];
    cpu->gpr[MIPS_REG_SP] = sp - frame;
    psx_mod_write_word(sp - frame + 16, (uint32_t)g);
    psx_mod_write_word(sp - frame + 20, (uint32_t)b);
    psx_mod_call_guest(cpu, FN_SET_TEXT_PARAMS, cpu->gpr[MIPS_REG_RA], (uint32_t)x, (uint32_t)y,
                       TEXT_ALIGN_CENTER, (uint32_t)r);
    cpu->gpr[MIPS_REG_SP] = sp;
}

static void draw_line(struct CPUState* cpu, int line, int selected, const char* text) {
    const int dim = selected ? COLOR_FULL : COLOR_DIM;
    set_text_params(cpu, TEXT_CENTER_X, TEXT_TOP_Y + line * TEXT_LINE_STEP, COLOR_FULL, COLOR_FULL, dim);
    for (uint32_t i = 0; i < SCORE_TEXT_SIZE; ++i) {
        psx_mod_write_byte(VAR_SCORE_TEXT + i, (uint8_t)text[i]);
        if (!text[i]) break;
    }
    psx_mod_call_guest(cpu, FN_DRAW_TEXT_CRAPPY, cpu->gpr[MIPS_REG_RA], VAR_SCORE_TEXT, 0, 0, 0);
}

static void draw_submenu(struct CPUState* cpu) {
    char line[32];
    draw_line(cpu, 0, g_state.cursor == LS_ITEM_START, "START");
    snprintf(line, sizeof line, "WORLD  < %d >", g_state.world + 1);
    draw_line(cpu, 1, g_state.cursor == LS_ITEM_WORLD, line);
    snprintf(line, sizeof line, "LEVEL  < %d >", g_state.level + 1);
    draw_line(cpu, 2, g_state.cursor == LS_ITEM_LEVEL, line);
}

/* Run the original menu body with Cross still pressed on Arcade, so the game's
 * own start path does every reset; then redirect the load like Load Game. */
static void start_arcade(struct CPUState* cpu, uint32_t address) {
    g_calling_original = 1;
    psx_mod_call_guest(cpu, address, cpu->gpr[MIPS_REG_RA], 0, 0, 0, 0);
    g_calling_original = 0;
    const int cheated_start = ls_is_cheated_start(&g_state);
    g_strict_armed = cheated_start;
    g_state.open = 0;
    psx_mod_counter_add("kula.level-select.confirmed", 1);
    if (!cheated_start) return;
    const int loaded_world = (int)psx_mod_read_word(VAR_CUR_WORLD2);
    psx_mod_write_word(VAR_CUR_WORLD, (uint32_t)g_state.world);
    psx_mod_write_word(VAR_CUR_LEVEL, (uint32_t)g_state.level);
    psx_mod_write_word(VAR_SKIP_NEXT_LOAD, (uint32_t)ls_skip_reload(&g_state, loaded_world));
    psx_mod_write_word(VAR_LOAD_NEW_WORLD, 1);
    psx_mod_write_word(VAR_CHEATED, 1);
}

static int open_submenu_if_arcade_chosen(struct CPUState* cpu, uint32_t pressed) {
    const int arcade = ls_arcade_index((int)psx_mod_read_word(VAR_FINAL_UNLOCKED));
    if (!(pressed & LS_PAD_CROSS) || (int)psx_mod_read_word(VAR_SINGLE_PLAYER_CURSOR) != arcade) return 0;
    ls_reset(&g_state);
    g_state.open = 1;
    g_state.seen_this_frame = 1;
    play_menu_sfx(cpu);
    psx_mod_counter_add("kula.level-select.opened", 1);
    return 1;
}

static int on_single_player_menu(struct CPUState* cpu, uint32_t address) {
    if (g_calling_original) return 0;
    const uint32_t pressed = newly_pressed();
    if (!g_state.open) return open_submenu_if_arcade_chosen(cpu, pressed);
    g_state.seen_this_frame = 1;
    const LsAction action = ls_menu_input(&g_state, pressed);
    if (action == LS_ACT_CONFIRM) {
        start_arcade(cpu, address);
        return 1;
    }
    if (action != LS_ACT_NONE) play_menu_sfx(cpu);
    if (g_state.open) draw_submenu(cpu);
    return 1;
}

/* After a non-1/1 arcade start, show the score table instead of the entry. */
static int on_highscore_ui(struct CPUState* cpu, uint32_t address) {
    (void)address;
    const int game_mode = (int)psx_mod_read_word(VAR_GAME_MODE);
    if (!ls_strict_applies(g_strict_armed, game_mode, (int)cpu->gpr[MIPS_REG_A0])) return 0;
    cpu->gpr[MIPS_REG_A0] = 0;
    g_strict_armed = 0;
    psx_mod_counter_add("kula.level-select.strict_skipped", 1);
    return 0;
}

static void on_vblank(void) {
    if (psx_mod_read_word(VAR_GAME_STATE) != 0) g_state.seen_this_frame = 0;
    ls_on_vblank(&g_state);
}

static void on_activate(void) {
    ls_reset(&g_state);
    g_strict_armed = 0;
    g_calling_original = 0;
}

PSX_MOD_CONSTRUCTOR(register_kula_level_select) {
    (void)psx_mod_register_activation_plugin(PLUGIN_ID, on_activate);
    (void)psx_mod_register_vblank_plugin(PLUGIN_ID, on_vblank);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_SINGLE_PLAYER_MENU, on_single_player_menu);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_HIGHSCORE_UI, on_highscore_ui);
}
```
Note for the implementer: `on_highscore_ui` changes `a0` and returns 0, so the original body runs with the new argument. `mod_plugins.h` says a filter "may update registers" only for instruction plugins. If the filter path restores registers, switch to calling the original via `psx_mod_call_guest(cpu, FN_HIGHSCORE_UI, ra, 0, 0, 0, 0)` behind a `g_calling_original` guard and return 1.

- [ ] **Step 4: Link the sources.** In `CMakeLists.txt`, directly after the closing `)` of `psxrecomp_add_game_runtime(psx-runtime ...)`, add:

```cmake
# Game-owned trusted mod plugins (manifests in mods/preloaded).
target_sources(psx-runtime PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/src/kula_level_select.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/src/level_select_logic.c")
target_include_directories(psx-runtime PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/mods/src")
```

- [ ] **Step 5: Regenerate and build.**

Run: `go-task generate && go-task build:dev`
Expected:
- The generate log lists the two mod entry functions.
- The build ends with `Linking CXX executable Kula_World_Recompiled`.
- The CMake mod catalog line counts the new package.
- `grep -c 0x000491a8 generated/*dispatch*.c` or the shard containing `SinglePlayerMenu` shows a `psx_mod_function_entry` call. Only read the generated code, never edit it.

- [ ] **Step 6: Spike check** that the hook fires and drawing works. Start: `go-task run:dev RUNNER="xvfb-run -a -s '-screen 0 1280x960x24'" -- ` with OpenBIOS: `./build-dev/Kula_World_Recompiled --no-launcher --bios build-dev/bios/openbios.bin --disc disc/SCES01000.CUE --debug-port 4370`. Then, using the probe pattern from `tools/smoke_boot.py`:
  - Wait until `levelTimeLeft == 4950` (menu).
  - Press Cross: `{"cmd":"press","buttons":49151,"frames":4}` (0xFFFF ^ 0x4000, active-low).
  - Press Cross again for Arcade.
  - Take a screenshot to `analysis/level-select/submenu.png`.
  - Read `{"cmd":"mod_counters"}`.

  Expected:
  - `kula.level-select.opened` is 1.
  - The screenshot shows START / WORLD < 1 > / LEVEL < 1 > over the menu backdrop.

  If no text is visible, inspect with the debug server instead of printf: is `textCharIdx` at 0x800a3cbc growing? Adjust `TEXT_TOP_Y`/colours and re-check.

- [ ] **Step 7: Commit.**

```bash
git add game.toml CMakeLists.txt mods/src/kula_level_select.c mods/preloaded/packages/kula.level-select/1.0.0/manifest.toml
git commit -m "feat: add level select submenu mod for arcade"
git push
```

---

### Task 3: Integration check script over the debug server

**Files:**
- Create: `tools/check_level_select.py`

**Interfaces:**
- Consumes: `DebugConnection`, `connect_with_retry`, `WATCHED_S32` from `tools/smoke_boot.py`, plus the counters from Task 2.
- Produces: exit code 0 when all checks pass. Used by Task 4 and by the Mac session.

- [ ] **Step 1: Write the script.**

```python
#!/usr/bin/env python3
"""Drive the level-select submenu over the debug server and verify the start.

Run against a dev build that sits in the main menu (fresh process).
Usage: check_level_select.py --world 7 --level 3 [--port 4370]
"""

import argparse
import sys
import time
from pathlib import Path

from smoke_boot import WATCHED_S32, DebugConnection, connect_with_retry

PAD_UP, PAD_RIGHT, PAD_DOWN, PAD_CROSS = 0x0010, 0x0020, 0x0040, 0x4000
ALL_RELEASED = 0xFFFF
MENU_TIMER = 4950
CHEATED_ADDR = 0x800A4E0C
PRESS_FRAMES = 4
SETTLE_S = 0.6
LOAD_WAIT_S = 20.0
MENU_WAIT_S = 120.0


def press(conn: DebugConnection, buttons: int) -> None:
    """The wire format is active-low."""
    conn.request(
        {"cmd": "press", "buttons": ALL_RELEASED ^ buttons, "frames": PRESS_FRAMES}
    )
    time.sleep(SETTLE_S)


def press_times(conn: DebugConnection, buttons: int, count: int) -> None:
    for _ in range(count):
        press(conn, buttons)


def wait_for_menu(conn: DebugConnection) -> None:
    deadline = time.monotonic() + MENU_WAIT_S
    while conn.read_s32(WATCHED_S32["levelTimeLeft"]) != MENU_TIMER:
        if time.monotonic() > deadline:
            raise TimeoutError("main menu not reached")
        time.sleep(0.5)


def select_and_start(conn: DebugConnection, world: int, level: int, shots: Path) -> None:
    press(conn, PAD_CROSS)  # main menu: 1 Player
    press(conn, PAD_CROSS)  # one-player menu: Arcade opens the submenu
    press(conn, PAD_DOWN)
    press_times(conn, PAD_RIGHT, world - 1)
    press(conn, PAD_DOWN)
    press_times(conn, PAD_RIGHT, level - 1)
    conn.request({"cmd": "screenshot", "path": str((shots / "submenu.png").resolve())})
    press(conn, PAD_UP)
    press(conn, PAD_UP)
    press(conn, PAD_CROSS)


def check_started(conn: DebugConnection, world: int, level: int) -> list[str]:
    time.sleep(LOAD_WAIT_S)
    expected = {
        "curWorld": world - 1,
        "curLevel": level - 1,
        "gameState": 1,
        "isDemoMode": 0,
    }
    failures = [
        f"{name}: expected {want}, got {conn.read_s32(WATCHED_S32[name])}"
        for name, want in expected.items()
        if conn.read_s32(WATCHED_S32[name]) != want
    ]
    want_cheated = 0 if (world, level) == (1, 1) else 1
    if conn.read_s32(CHEATED_ADDR) != want_cheated:
        failures.append(f"cheated: expected {want_cheated}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4370)
    parser.add_argument("--world", type=int, default=7, choices=range(1, 11))
    parser.add_argument("--level", type=int, default=3, choices=range(1, 16))
    parser.add_argument("--out", default="analysis/level-select")
    args = parser.parse_args()
    shots = Path(args.out)
    shots.mkdir(parents=True, exist_ok=True)
    conn = connect_with_retry("127.0.0.1", args.port, time.monotonic() + 60)
    wait_for_menu(conn)
    select_and_start(conn, args.world, args.level, shots)
    failures = check_started(conn, args.world, args.level)
    conn.request({"cmd": "screenshot", "path": str((shots / "level.png").resolve())})
    print(conn.request({"cmd": "mod_counters"}))
    for failure in failures:
        print("FAIL", failure)
    print("level_select_ok" if not failures else "level_select_failed")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Lint.**

Run: `ruff check tools/check_level_select.py && black --check tools/check_level_select.py`
Expected: both clean. Run `black tools/check_level_select.py` if needed. Also add the file to the `lint` task lists in `Taskfile.yaml`.

- [ ] **Step 3: Run the chosen-start case on a fresh runtime.**

Run, in the repo root, with the runtime from Task 2 Step 6 freshly started:
`python3 tools/check_level_select.py --world 7 --level 3`
Expected: `level_select_ok`. The screenshot `analysis/level-select/level.png` shows a level with a running timer.

- [ ] **Step 4: Run the default-start case** (fresh runtime): `python3 tools/check_level_select.py --world 1 --level 1`.
Expected: `level_select_ok` (`curWorld 0`, `curLevel 0`, `cheated 0`).

- [ ] **Step 5: Commit.**

```bash
git add tools/check_level_select.py Taskfile.yaml
git commit -m "test: add level select integration check over debug server"
git push
```

---

### Task 4: Edge cases, strict scoring, docs, Mac verification, merge

**Files:**
- Modify: `CLAUDE.md` (roadmap item 7, mods)
- Modify: `docs/BUILD_MACOS.md` (verified table)

- [ ] **Step 1: Run the edge-case runs from the Review Focus on fresh runtimes.**
  - **Mod disabled:** add to `build-dev/mods/state.toml`
    ```toml
    [[package]]
    id = "kula.level-select"

    [[feature]]
    package_id = "kula.level-select"
    id = "level-select"
    enabled = false
    ```
    Then `python3 tools/smoke_boot.py --duration 120` gives `demo_gameplay_reached`, and `mod_counters` shows no `kula.level-select.*`. Remove the block afterwards.
  - **Demo interrupts the submenu:** open the submenu, wait 45 s without input until the demo runs, return to the menu with Cross, press Cross on 1 Player. Expected: the original one-player menu, and `opened` unchanged until Arcade is chosen again.
  - **Final unlocked:** before entering the one-player menu, write `finalUnlocked = 1`: `{"cmd":"write_ram","addr":"0x800A2ED8","hex":"01000000"}`. Check the exact command name with `{"cmd":"help"}` or in `psxrecomp/runtime/src/debug_server.c`. Then cursor Down once to Arcade and press Cross. Expected: the submenu opens (`opened` is 1). Entry 0 (Final) with Cross must start Final, with `isFinal` 0x800a2edc at 1.

- [ ] **Step 2: Check strict scoring.** After a chosen start (world 7, level 3), let the timer run out:
  - Write `levelTimeLeft` 0x800A52C8 to 50: `"hex":"32000000"`.
  - Repeat until game over.
  - Expected: `kula.level-select.strict_skipped` is 1 and the screenshot shows the score table without the name-entry cursor.

  If Kula's timeout does not end the game, leave this to the Mac playtest (Step 4) and note that in the docs.

- [ ] **Step 3: Update the docs.**
  - `CLAUDE.md` roadmap item 7: mark "Levelauswahl-Mod" done, with package id, default on, hooks in `game.toml`, and checker `tools/check_level_select.py`.
  - Add one line under the Smoke-Test section on how to run the checker.
  - `docs/BUILD_MACOS.md` gets its row after the Mac result.

  Commit with `docs: record level select mod` and push.

- [ ] **Step 4: Mac verification.** Send the Mac session the branch `feat/level-select-mod` with this test order:
  1. Fetch, `task generate PYTHON=python3.12` (new hooks), then `task build` and `task build:dev`.
  2. Visual check of the submenu in the launcher build.
  3. Launcher toggle off and on.
  4. Playtest world 7/3.
  5. Final unlocked by playing to world 10 or via the debug server.
  6. Reach the ending FMV.
  7. Game over after a chosen start gives no name entry.

  Wait for the result.

- [ ] **Step 5: Merge.** When the Mac result is clean:

```bash
git switch main && git pull --ff-only && git merge --ff-only feat/level-select-mod && git push
git branch -d feat/level-select-mod && git push origin --delete feat/level-select-mod
```
