/* Kula World widescreen: selects psxrecomp's native-wide view. 16:9 shapes the
 * first window, then the view follows the window up to 2:1, the widest the
 * game's generated sky covers (about 1.7x the 4:3 width). The key HUD moves to
 * the left wide corner and the fruit HUD to the right one. Still screens on the
 * PS-button background (loading, high scores, memory card) fill the side bands
 * with more of that background. */
#include <stdint.h>
#include "cpu_state.h"
#include "mod_plugins.h"
#include "widescreen_logic.h"

#define PLUGIN_ID "kula.widescreen"

enum { FIRST_WINDOW_NUM = 16, FIRST_WINDOW_DEN = 9, MAX_ASPECT_NUM = 2, MAX_ASPECT_DEN = 1 };

/* HUD sprite pools (EU addresses, dezgeg/kula-world-decomp): TSprite is a
 * merged DR_TPAGE + SPRT packet of 28 bytes, double buffered. */
enum {
    VAR_KEY_SPRITES = 0x800adbb4u,   /* TSprite keySprites[2][4][2] */
    VAR_FRUIT_SPRITES = 0x800add74u, /* TSprite fruitSprites[2][5][2] */
    TSPRITE_SIZE = 28,
    KEY_SPRITE_COUNT = 2 * 4 * 2,
    FRUIT_SPRITE_COUNT = 2 * 5 * 2,
};
enum { HUD_EDGE_LEFT = -1, HUD_EDGE_RIGHT = 1 };

/* DrawPsxButtonBackground runs only on still screens (loading callback, high
 * scores, memory card); RenderBackground only in the main game loop. */
enum {
    FN_DRAW_BUTTON_BG = 0x0001d9b4u,
    FN_RENDER_BACKGROUND = 0x0002aa7cu,
};
/* PsxButtonBackground { TSprite sprites[2][200]; short buttons[200]; }. The
 * game sets every tile's XY but links only tiles within -48..W+48 into
 * otag[env][0][1024 - (button + 1)]. */
enum {
    VAR_BUTTON_BG_PTR = 0x800a5968u,
    VAR_OTAG = 0x800d2668u,
    VAR_WHICH_DRAW_ENV = 0x800a52bcu,
    VAR_DISPLAY_WIDTH = 0x800a2e6cu,
    BG_TILES = 200,
    BG_SPRT_X_OFFSET = 16, /* DR_TPAGE (8) + SPRT tag and colour (8) */
    BG_BUTTONS_OFFSET = 2 * BG_TILES * TSPRITE_SIZE,
    OT_LEN = 1026,
    OT_BUTTON_BG_BASE = 1024,
    MIPS_REG_RA = 31,
};
enum { PRIM_LEN_MASK = 0xff000000u, PRIM_ADDR_MASK = 0x00ffffffu };

static int g_still_screen;
static int g_calling_original;

/* The anchor API wants the word before the GP0 colour command; in a merged
 * TSprite that is the SPRT's own (now NOP) tag word at +8. */
enum { SPRT_TAG_OFFSET = 8 };

static void anchor_pool(uint32_t base, int count, int edge) {
    for (int i = 0; i < count; ++i)
        psx_mod_anchor_hud_primitive(base + (uint32_t)(i * TSPRITE_SIZE) + SPRT_TAG_OFFSET, edge);
}

/* Anchors are guarded by the packet words, so re-tag every frame after the
 * game may have rebuilt them. Inert at 4:3. */
static void on_vblank(void) {
    anchor_pool(VAR_KEY_SPRITES, KEY_SPRITE_COUNT, HUD_EDGE_LEFT);
    anchor_pool(VAR_FRUIT_SPRITES, FRUIT_SPRITE_COUNT, HUD_EDGE_RIGHT);
}

/* The GTE classifier would drop these screens to 4:3 once the cubes stop or
 * the load runs long; with filled bands they stay wide like the rest. */
static int is_still_screen(void) { return g_still_screen; }

/* addPrim() on a guest ordering-table entry. */
static void link_prim(uint32_t ot_entry, uint32_t prim) {
    const uint32_t tag = psx_mod_read_word(prim);
    psx_mod_write_word(prim, (tag & PRIM_LEN_MASK) | (psx_mod_read_word(ot_entry) & PRIM_ADDR_MASK));
    psx_mod_write_word(ot_entry, prim & PRIM_ADDR_MASK);
}

/* Unlinked tiles are free this frame: the game rewrites every XY each call. */
static void link_band_tiles(void) {
    const int margin = psx_mod_widescreen_view_x_margin();
    const uint32_t base = psx_mod_read_word(VAR_BUTTON_BG_PTR);
    const uint32_t env = psx_mod_read_word(VAR_WHICH_DRAW_ENV);
    const int width = (int)psx_mod_read_word(VAR_DISPLAY_WIDTH);
    for (uint32_t i = 0; i < BG_TILES; ++i) {
        const uint32_t prim = base + (env * BG_TILES + i) * TSPRITE_SIZE;
        int x = 0;
        if (!ws_band_tile_x((int16_t)psx_mod_read_half(prim + BG_SPRT_X_OFFSET), width, margin, &x)) continue;
        psx_mod_write_half(prim + BG_SPRT_X_OFFSET, (uint16_t)(int16_t)x);
        const int button = (int16_t)psx_mod_read_half(base + BG_BUTTONS_OFFSET + i * 2u);
        link_prim(VAR_OTAG + (env * OT_LEN + OT_BUTTON_BG_BASE - (uint32_t)(button + 1)) * 4u, prim);
    }
}

static int on_draw_button_bg(struct CPUState* cpu, uint32_t address) {
    if (g_calling_original) return 0;
    g_calling_original = 1;
    psx_mod_call_guest(cpu, address, cpu->gpr[MIPS_REG_RA], 0, 0, 0, 0);
    g_calling_original = 0;
    g_still_screen = 1;
    link_band_tiles();
    return 1;
}

static int on_render_background(struct CPUState* cpu, uint32_t address) {
    (void)cpu;
    (void)address;
    g_still_screen = 0;
    return 0;
}

static void on_activate(void) {
    g_still_screen = 0;
    g_calling_original = 0;
    psx_mod_set_world_scene_predicate(is_still_screen);
    (void)psx_mod_set_fixed_display_aspect(FIRST_WINDOW_NUM, FIRST_WINDOW_DEN);
    (void)psx_mod_set_adaptive_display_aspect(MAX_ASPECT_NUM, MAX_ASPECT_DEN);
}

PSX_MOD_CONSTRUCTOR(register_kula_widescreen) {
    (void)psx_mod_register_activation_plugin(PLUGIN_ID, on_activate);
    (void)psx_mod_register_vblank_plugin(PLUGIN_ID, on_vblank);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_DRAW_BUTTON_BG, on_draw_button_bg);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_RENDER_BACKGROUND, on_render_background);
}
