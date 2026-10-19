/* Kula World widescreen: selects psxrecomp's native-wide view. 16:9 shapes the
 * first window, then the view follows the window up to 2:1, the widest the
 * game's generated sky covers (about 1.7x the 4:3 width). The key HUD moves to
 * the left wide corner and the fruit HUD to the right one. The loading screen
 * and the high-score table are flat 320-wide art, so they present at 4:3. */
#include <stdint.h>
#include "gpu.h"
#include "mod_plugins.h"

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

/* Still screens run their own loops (LoadingScreen via a VSync callback,
 * HighScoreUi inline); only the main game loop calls RenderBackground. */
enum {
    FN_RENDER_BACKGROUND = 0x0002aa7cu,
    FN_HIGHSCORE_UI = 0x0004c09cu,
    FN_LOADING_SCREEN = 0x0004dd78u,
};

static int g_still_screen;

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

/* The GTE-based classifier keeps these screens wide (load: ~45 frames of
 * hysteresis, scores: the flying cubes), showing stale VRAM in the bands. */
static int is_still_screen(void) { return g_still_screen; }

static int on_still_screen_entry(struct CPUState* cpu, uint32_t address) {
    (void)cpu;
    (void)address;
    g_still_screen = 1;
    return 0;
}

static int on_render_background(struct CPUState* cpu, uint32_t address) {
    (void)cpu;
    (void)address;
    g_still_screen = 0;
    return 0;
}

static void on_activate(void) {
    g_still_screen = 0;
    gpu_ws_set_native_scene_predicate(is_still_screen);
    (void)psx_mod_set_fixed_display_aspect(FIRST_WINDOW_NUM, FIRST_WINDOW_DEN);
    (void)psx_mod_set_adaptive_display_aspect(MAX_ASPECT_NUM, MAX_ASPECT_DEN);
}

PSX_MOD_CONSTRUCTOR(register_kula_widescreen) {
    (void)psx_mod_register_activation_plugin(PLUGIN_ID, on_activate);
    (void)psx_mod_register_vblank_plugin(PLUGIN_ID, on_vblank);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_LOADING_SCREEN, on_still_screen_entry);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_HIGHSCORE_UI, on_still_screen_entry);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_RENDER_BACKGROUND, on_render_background);
}
