/* Kula World arcade level select: a function filter on SinglePlayerMenu draws
 * a START/WORLD/LEVEL submenu and redirects the arcade start; a filter on
 * HighScoreUi drops the name entry after a non-1/1 start; a filter on
 * DrawWidgets hides the menu panel while the arcade start runs the original.
 * Guest addresses: EU SCES-01000, from the dezgeg/kula-world-decomp config. */
#include <stdio.h>
#include "cpu_state.h"
#include "mod_plugins.h"
#include "level_select_logic.h"

#define PLUGIN_ID "kula.level-select"

enum {
    FN_DRAW_WIDGETS = 0x00017ae8u,
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
    VAR_GAME_MODE = 0x800a2e48u,
    VAR_GAME_STATE = 0x800a2ec0u,
    VAR_FINAL_UNLOCKED = 0x800a2ed8u,
    VAR_CHEATED = 0x800a4e0cu,
    VAR_SINGLE_PLAYER_CURSOR = 0x800a4f20u + 3u * 4u,
    VAR_CONTROLLER_BUTTONS = 0x800a5530u,
    VAR_PREV_CONTROLLER_BUTTONS = 0x800a50bcu,
    VAR_SCORE_TEXT = 0x800a4ab0u,
    VAR_FONT_SPRITES = 0x800aa47cu,
};
enum { SFX_MENU_SELECTION_2 = 109, SFX_VOLUME = 8000 };
enum { SCORE_TEXT_SIZE = 128, MIPS_REG_A0 = 4, MIPS_REG_SP = 29, MIPS_REG_RA = 31 };
/* Layout in the 320x256 PAL menu space: START centred, labels right-aligned
 * to a shared edge; -, number and + each centred in their own fixed column,
 * so one- and two-digit values line up. */
enum { TEXT_CENTER_X = 160, TEXT_TOP_Y = 162, TEXT_LINE_STEP = 20 };
enum { LABEL_RIGHT_X = 158, MINUS_X = 174, NUMBER_X = 194, PLUS_X = 214 };
enum { TEXT_ALIGN_CENTER = 1, TEXT_ALIGN_RIGHT = 2 };
/* Pale blue tint instead of plain white; unselected rows at half brightness. */
enum { TINT_R = 96, TINT_G = 116, TINT_B = 128, TINT_DIM_SHIFT = 1 };
/* Light drop shadow one pixel down-right. The font blends additively, so a dark
 * copy would be invisible; the shadow pass switches the glyph templates
 * (fontSprites, 28-byte TSprite with DR_TPAGE first) to subtractive blending. */
enum { SHADOW_OFFSET = 1, SHADOW_SHADE = 40 };
enum { FONT_FIRST_CHAR = 0x20, TSPRITE_SIZE = 28, TSPRITE_TPAGE_CODE = 4 };
enum { TPAGE_ABR_MASK = 0x60u, TPAGE_ABR_SUBTRACT = 0x40u };

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
static void set_text_params(struct CPUState* cpu, int x, int y, int align, int r, int g, int b) {
    const uint32_t frame = 24;
    const uint32_t sp = cpu->gpr[MIPS_REG_SP];
    cpu->gpr[MIPS_REG_SP] = sp - frame;
    psx_mod_write_word(sp - frame + 16, (uint32_t)g);
    psx_mod_write_word(sp - frame + 20, (uint32_t)b);
    psx_mod_call_guest(cpu, FN_SET_TEXT_PARAMS, cpu->gpr[MIPS_REG_RA], (uint32_t)x, (uint32_t)y,
                       (uint32_t)align, (uint32_t)r);
    cpu->gpr[MIPS_REG_SP] = sp;
}

static void draw_glyphs(struct CPUState* cpu, int x, int y, int align, int r, int g, int b, const char* text) {
    set_text_params(cpu, x, y, align, r, g, b);
    for (uint32_t i = 0; i < SCORE_TEXT_SIZE; ++i) {
        psx_mod_write_byte(VAR_SCORE_TEXT + i, (uint8_t)text[i]);
        if (!text[i]) break;
    }
    psx_mod_call_guest(cpu, FN_DRAW_TEXT_CRAPPY, cpu->gpr[MIPS_REG_RA], VAR_SCORE_TEXT, 0, 0, 0);
}

static uint32_t glyph_tpage_address(char c) {
    return VAR_FONT_SPRITES + (uint32_t)(c - FONT_FIRST_CHAR) * TSPRITE_SIZE + TSPRITE_TPAGE_CODE;
}

/* Switch the blend mode of the glyph templates used by text (up to the newline);
 * returns how many words were saved. */
static int set_glyph_blend(const char* text, uint32_t abr, uint32_t* saved) {
    int count = 0;
    for (; text[count] >= FONT_FIRST_CHAR; ++count) {
        const uint32_t addr = glyph_tpage_address(text[count]);
        saved[count] = psx_mod_read_word(addr);
        psx_mod_write_word(addr, (saved[count] & ~TPAGE_ABR_MASK) | abr);
    }
    return count;
}

/* Reverse order, so a repeated glyph ends with its first, unpatched value. */
static void restore_glyph_blend(const char* text, const uint32_t* saved, int count) {
    while (count-- > 0) psx_mod_write_word(glyph_tpage_address(text[count]), saved[count]);
}

/* Primitives are prepended to the ordering table, so the shadow added after the
 * text is drawn underneath it. */
static void draw_text(struct CPUState* cpu, int x, int line, int align, int selected, const char* text) {
    uint32_t saved[SCORE_TEXT_SIZE];
    const int dim = selected ? 0 : TINT_DIM_SHIFT;
    const int y = TEXT_TOP_Y + line * TEXT_LINE_STEP;
    draw_glyphs(cpu, x, y, align, TINT_R >> dim, TINT_G >> dim, TINT_B >> dim, text);
    const int patched = set_glyph_blend(text, TPAGE_ABR_SUBTRACT, saved);
    draw_glyphs(cpu, x + SHADOW_OFFSET, y + SHADOW_OFFSET, align, SHADOW_SHADE, SHADOW_SHADE, SHADOW_SHADE, text);
    restore_glyph_blend(text, saved, patched);
}

static void draw_setting(struct CPUState* cpu, int item, const char* label, int value) {
    char number[8];
    const int selected = g_state.cursor == item;
    snprintf(number, sizeof number, "%d\n", value);
    draw_text(cpu, LABEL_RIGHT_X, item, TEXT_ALIGN_RIGHT, selected, label);
    draw_text(cpu, MINUS_X, item, TEXT_ALIGN_CENTER, selected, "-\n");
    draw_text(cpu, NUMBER_X, item, TEXT_ALIGN_CENTER, selected, number);
    draw_text(cpu, PLUS_X, item, TEXT_ALIGN_CENTER, selected, "+\n");
}

static void draw_submenu(struct CPUState* cpu) {
    /* DrawTextCrappyFont only emits a line when it reaches a newline;
     * '<' and '>' are pad-button glyphs in this font, hence - and +. */
    draw_text(cpu, TEXT_CENTER_X, LS_ITEM_START, TEXT_ALIGN_CENTER, g_state.cursor == LS_ITEM_START,
              "START\n");
    draw_setting(cpu, LS_ITEM_WORLD, "WORLD\n", g_state.world + 1);
    draw_setting(cpu, LS_ITEM_LEVEL, "LEVEL\n", g_state.level + 1);
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
    play_menu_sfx(cpu);
    psx_mod_counter_add("kula.level-select.opened", 1);
    return 1;
}

static int on_single_player_menu(struct CPUState* cpu, uint32_t address) {
    if (g_calling_original) return 0;
    const uint32_t pressed = newly_pressed();
    g_state.missed_vblanks = 0;
    if (!g_state.open) return open_submenu_if_arcade_chosen(cpu, pressed);
    const LsAction action = ls_menu_input(&g_state, pressed);
    if (action == LS_ACT_CONFIRM) {
        start_arcade(cpu, address);
        return 1;
    }
    if (action != LS_ACT_NONE) play_menu_sfx(cpu);
    if (g_state.open) draw_submenu(cpu);
    return 1;
}

/* The original menu draws its panel before testing Cross, so the confirm
 * frame would flash the one-player panel over the submenu. */
static int on_draw_widgets(struct CPUState* cpu, uint32_t address) {
    (void)cpu;
    (void)address;
    return g_calling_original;
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
    g_strict_armed = ls_keep_strict(g_strict_armed, (int)psx_mod_read_word(VAR_GAME_STATE));
    const int was_open = g_state.open;
    ls_on_vblank(&g_state);
    if (was_open && !g_state.open) psx_mod_counter_add("kula.level-select.closed_unseen", 1);
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
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_DRAW_WIDGETS, on_draw_widgets);
}
