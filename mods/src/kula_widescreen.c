/* Kula World widescreen: selects psxrecomp's native-wide view. 16:9 shapes the
 * first window, then the view follows the window up to 2:1. The sky mesh only
 * covers the 4:3 view, so it is stretched by the widening. The key HUD moves to
 * the left wide corner and the fruit HUD to the right one, together with their
 * pickup sparkles. Still screens on the
 * PS-button background (loading, high scores, memory card) fill the side bands
 * with more of that background, and the score table's shade and flying cubes
 * reach into them too. The pill's motion trail continues into the bands. */
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
    VAR_FRUIT_BONUS_TEXT_SPRITES = 0x800adfa4u, /* TSprite fruitBonusTextSprites[2][5][2] */
    TSPRITE_SIZE = 28,
    KEY_SPRITE_COUNT = 2 * 4 * 2,
    FRUIT_SPRITE_COUNT = 2 * 5 * 2,
};
/* Particle particles[2][16] = { POLY_FT4 prims[2][2]; SVECTOR pos; ParticleType*
 * animData; ... } (184 bytes); pos.vz < 0 marks a screen-space HUD sparkle. */
enum {
    FN_PROCESS_PARTICLES = 0x00012918u,
    VAR_PARTICLES = 0x800ab014u,
    VAR_NUM_PARTICLES = 0x800a3db0u,
    VAR_CAMERA_INDEX = 0x800a2e68u,
    PARTICLE_SIZE = 184,
    PARTICLES_PER_CAMERA = 16,
    PARTICLE_POS_X = 160,
    PARTICLE_POS_Z = 164,
    PARTICLE_ANIM_DATA = 168,
    PARTICLE_PRIM_SIZE = 40,
    PARTICLE_PRIMS_PER_ENV = 2,
};
enum { HUD_EDGE_LEFT = -1, HUD_EDGE_RIGHT = 1 };
/* Pill trail: TSprite lethargyEffectSprite[2][2], drawn while lethargyMode != 0. */
enum {
    FN_DRAW_LETHARGY = 0x00020b30u,
    VAR_LETHARGY_SPRITES = 0x800a3ee4u,
    VAR_LETHARGY_MODE = 0x800a52b8u,
    LETHARGY_SPRITES_PER_ENV = 2,
    /* POLY_FT4 lethargyEffectPoly[2]: the full-screen flash at pickup and the
     * fade at the end, hard-wired to 0..displayWidth+1. */
    VAR_LETHARGY_POLY = 0x800a3e94u,
    POLY_FT4_X0 = 8, POLY_FT4_X1 = 16, POLY_FT4_X2 = 24, POLY_FT4_X3 = 32,
    LETHARGY_POLY_RIGHT_PAD = 1,
};

/* DrawPsxButtonBackground runs only on still screens (loading callback, high
 * scores, memory card); RenderBackground only in the main game loop. */
enum {
    FN_DRAW_BUTTON_BG = 0x0001d9b4u,
    FN_RENDER_BACKGROUND = 0x0002aa7cu,
    FN_DRAW_SCORE_GRAPH = 0x0002224cu,
    FN_ROT_SMD_FT4 = 0x000621b0u,
    FN_LOAD_SAVE_MENU = 0x00043348u,
    FN_MEMCARD_UI = 0x00043f04u,
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
    MIPS_REG_A0 = 4,
    MIPS_REG_A1 = 5,
    MIPS_REG_A2 = 6,
    MIPS_REG_A3 = 7,
    MIPS_REG_SP = 29,
    MIPS_REG_RA = 31,
};
/* ScoreGraph.polys3[env][1]: the table's POLY_G4 shade, hard-wired to 0..320
 * in high-score mode (vertex 2 at x 0), at x+8 under a memory-card graph. */
enum {
    VAR_SCORE_GRAPH_PRIMS = 0x800a4068u,
    POLY_G4_SIZE = 36,
    SCORE_SHADE_OFFSET = 69704 + POLY_G4_SIZE,
    SCORE_SHADE_ENV_STRIDE = 3 * POLY_G4_SIZE,
    POLY_G4_X0 = 8, POLY_G4_X1 = 16, POLY_G4_X2 = 24, POLY_G4_X3 = 32,
};
/* RotSMD_FT4(pa, ot, otlen, id, sclip, hclip, vclip, nclip) keeps a face only
 * while one corner lies in 0..hclip. pa = { long count; { POLY_FT4 polys[2];
 * SVECTOR v[4]; } faces[] }, id picks the POLY_FT4. */
enum {
    SMD_HCLIP_ARG_OFFSET = 0x14,
    SMD_FACE_SIZE = 0x70,
    SMD_FIRST_FACE = 4,
    POLY_FT4_SIZE = 40,
    GTE_OFX = 24,
    GTE_FRACTION_BITS = 16,
};
/* RenderNonSpecialBackground(ot) scales its rotation matrix's X row by
 * gteXScale; the sky mesh behind it only reaches the 4:3 corners. */
enum {
    FN_RENDER_SKY = 0x000563c4u,
    VAR_GTE_X_SCALE = 0x800a2e70u,
};
static const uint32_t POLY_FT4_X_OFFSETS[] = { 8, 16, 24, 32 };
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
    anchor_pool(VAR_FRUIT_BONUS_TEXT_SPRITES, FRUIT_SPRITE_COUNT, HUD_EDGE_RIGHT);
}

/* Sparkles spawn at fixed 4:3 HUD spots (keys left, fruits right, hourglass
 * centred), so they follow the side of the screen they were placed on. */
static int hud_edge_of(int x, int width) {
    if (x < width / 2) return HUD_EDGE_LEFT;
    if (x > width / 2) return HUD_EDGE_RIGHT;
    return 0;
}

static void anchor_hud_particles(void) {
    const uint32_t camera = psx_mod_read_word(VAR_CAMERA_INDEX);
    const uint32_t env = psx_mod_read_word(VAR_WHICH_DRAW_ENV);
    const int width = (int)psx_mod_read_word(VAR_DISPLAY_WIDTH);
    const int count = (int)psx_mod_read_word(VAR_NUM_PARTICLES + camera * 4u);
    for (int i = 0; i < count; ++i) {
        const uint32_t particle = VAR_PARTICLES + (camera * PARTICLES_PER_CAMERA + (uint32_t)i) * PARTICLE_SIZE;
        if ((int16_t)psx_mod_read_half(particle + PARTICLE_POS_Z) >= 0) continue;
        const int edge = hud_edge_of((int16_t)psx_mod_read_half(particle + PARTICLE_POS_X), width);
        const int prims = (int16_t)psx_mod_read_half(psx_mod_read_word(particle + PARTICLE_ANIM_DATA));
        for (int j = 0; j < prims && j < PARTICLE_PRIMS_PER_ENV; ++j)
            psx_mod_anchor_hud_primitive(particle + (env * PARTICLE_PRIMS_PER_ENV + (uint32_t)j) * PARTICLE_PRIM_SIZE, edge);
    }
}

/* Runs the hooked function itself; its filter then lets this call through. */
static void call_original(struct CPUState* cpu, uint32_t address) {
    g_calling_original = 1;
    psx_mod_call_guest(cpu, address, cpu->gpr[MIPS_REG_RA], 0, 0, 0, 0);
    g_calling_original = 0;
}

/* The packets are rebuilt every frame, so tag them right after the game did. */
static int on_process_particles(struct CPUState* cpu, uint32_t address) {
    if (g_calling_original) return 0;
    call_original(cpu, address);
    anchor_hud_particles();
    return 1;
}

/* Rewritten each frame so the flash and fade follow window resizes. */
static void widen_lethargy_flash(void) {
    const int margin = psx_mod_widescreen_view_x_margin();
    const int right = (int)psx_mod_read_word(VAR_DISPLAY_WIDTH) + LETHARGY_POLY_RIGHT_PAD + margin;
    for (uint32_t env = 0; env < 2; ++env) {
        const uint32_t poly = VAR_LETHARGY_POLY + env * POLY_FT4_SIZE;
        psx_mod_write_half(poly + POLY_FT4_X0, (uint16_t)(int16_t)-margin);
        psx_mod_write_half(poly + POLY_FT4_X2, (uint16_t)(int16_t)-margin);
        psx_mod_write_half(poly + POLY_FT4_X1, (uint16_t)(int16_t)right);
        psx_mod_write_half(poly + POLY_FT4_X3, (uint16_t)(int16_t)right);
    }
}

/* The pill's trail copies the previous frame through two sprites; native-wide
 * continues them into the bands from that frame's wide surface. The pickup
 * flash must cover the bands too: it sets bit 15 that keeps the copies
 * blending instead of overwriting (darkening) frame after frame. */
static int on_draw_lethargy(struct CPUState* cpu, uint32_t address) {
    if (g_calling_original) return 0;
    call_original(cpu, address);
    if (!psx_mod_read_word(VAR_LETHARGY_MODE)) return 1;
    widen_lethargy_flash();
    const uint32_t env = psx_mod_read_word(VAR_WHICH_DRAW_ENV);
    for (uint32_t i = 0; i < LETHARGY_SPRITES_PER_ENV; ++i)
        psx_mod_tag_feedback_rect(VAR_LETHARGY_SPRITES +
                                  (env * LETHARGY_SPRITES_PER_ENV + i) * TSPRITE_SIZE + SPRT_TAG_OFFSET);
    return 1;
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
    call_original(cpu, address);
    g_still_screen = 1;
    link_band_tiles();
    return 1;
}

/* The shade is redrawn from these words every frame, so the margin can follow
 * window resizes. */
static int on_draw_score_graph(struct CPUState* cpu, uint32_t address) {
    (void)cpu;
    (void)address;
    const int margin = psx_mod_widescreen_view_x_margin();
    const int width = (int)psx_mod_read_word(VAR_DISPLAY_WIDTH);
    const uint32_t shade = psx_mod_read_word(VAR_SCORE_GRAPH_PRIMS) + SCORE_SHADE_OFFSET;
    if ((int16_t)psx_mod_read_half(shade + POLY_G4_X2) > 0) return 0;
    for (uint32_t env = 0; env < 2; ++env) {
        const uint32_t poly = shade + env * SCORE_SHADE_ENV_STRIDE;
        psx_mod_write_half(poly + POLY_G4_X0, (uint16_t)(int16_t)-margin);
        psx_mod_write_half(poly + POLY_G4_X2, (uint16_t)(int16_t)-margin);
        psx_mod_write_half(poly + POLY_G4_X1, (uint16_t)(int16_t)(width + margin));
        psx_mod_write_half(poly + POLY_G4_X3, (uint16_t)(int16_t)(width + margin));
    }
    return 0;
}

static void shift_smd_corners(uint32_t model, uint32_t poly_offset, int dx) {
    const uint32_t faces = psx_mod_read_word(model);
    for (uint32_t f = 0; f < faces; ++f) {
        const uint32_t poly = model + SMD_FIRST_FACE + f * SMD_FACE_SIZE + poly_offset;
        for (int c = 0; c < 4; ++c) {
            const uint32_t at = poly + POLY_FT4_X_OFFSETS[c];
            psx_mod_write_half(at, (uint16_t)(int16_t)((int16_t)psx_mod_read_half(at) + dx));
        }
    }
}

/* Projects the cubes as if the screen started at the left band edge, then
 * moves the written corners back. Faces that stay culled keep stale corners,
 * but they are not linked. */
static int on_rot_smd_ft4(struct CPUState* cpu, uint32_t address) {
    const int margin = psx_mod_widescreen_view_x_margin();
    if (g_calling_original || !g_still_screen || margin <= 0) return 0;
    const uint32_t model = cpu->gpr[MIPS_REG_A0];
    const uint32_t poly_offset = cpu->gpr[MIPS_REG_A3] ? POLY_FT4_SIZE : 0;
    const uint32_t hclip_slot = cpu->gpr[MIPS_REG_SP] + SMD_HCLIP_ARG_OFFSET;
    const uint32_t hclip = psx_mod_read_word(hclip_slot);
    const uint32_t ofx = gte_read_ctrl(cpu, GTE_OFX);
    psx_mod_write_word(hclip_slot, hclip + 2u * (uint32_t)margin);
    gte_write_ctrl(cpu, GTE_OFX, ofx + ((uint32_t)margin << GTE_FRACTION_BITS));
    g_calling_original = 1;
    psx_mod_call_guest(cpu, address, cpu->gpr[MIPS_REG_RA], model, cpu->gpr[MIPS_REG_A1],
                       cpu->gpr[MIPS_REG_A2], cpu->gpr[MIPS_REG_A3]);
    g_calling_original = 0;
    gte_write_ctrl(cpu, GTE_OFX, ofx);
    psx_mod_write_word(hclip_slot, hclip);
    shift_smd_corners(model, poly_offset, -margin);
    return 1;
}

/* Without the stretch the top corners of the bands stay unpainted: black, or
 * stale pixels from an earlier frame since the game never clears the screen.
 * gteXScale is shared with lens flares and the pill, so only this call sees it. */
static int on_render_sky(struct CPUState* cpu, uint32_t address) {
    const int margin = psx_mod_widescreen_view_x_margin();
    if (g_calling_original || margin <= 0) return 0;
    const uint32_t scale = psx_mod_read_word(VAR_GTE_X_SCALE);
    const int width = (int)psx_mod_read_word(VAR_DISPLAY_WIDTH);
    psx_mod_write_word(VAR_GTE_X_SCALE, (uint32_t)ws_sky_x_scale((int)scale, width, margin));
    g_calling_original = 1;
    psx_mod_call_guest(cpu, address, cpu->gpr[MIPS_REG_RA], cpu->gpr[MIPS_REG_A0], 0, 0, 0);
    g_calling_original = 0;
    psx_mod_write_word(VAR_GTE_X_SCALE, scale);
    return 1;
}

/* Both menus read the card before their first frame; without a GTE scene the
 * classifier would show that pause at 4:3. */
static int on_memcard_menu(struct CPUState* cpu, uint32_t address) {
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
    g_calling_original = 0;
    psx_mod_set_world_scene_predicate(is_still_screen);
    (void)psx_mod_set_fixed_display_aspect(FIRST_WINDOW_NUM, FIRST_WINDOW_DEN);
    (void)psx_mod_set_adaptive_display_aspect(MAX_ASPECT_NUM, MAX_ASPECT_DEN);
}

PSX_MOD_CONSTRUCTOR(register_kula_widescreen) {
    (void)psx_mod_register_activation_plugin(PLUGIN_ID, on_activate);
    (void)psx_mod_register_vblank_plugin(PLUGIN_ID, on_vblank);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_PROCESS_PARTICLES, on_process_particles);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_DRAW_LETHARGY, on_draw_lethargy);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_DRAW_BUTTON_BG, on_draw_button_bg);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_RENDER_BACKGROUND, on_render_background);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_DRAW_SCORE_GRAPH, on_draw_score_graph);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_ROT_SMD_FT4, on_rot_smd_ft4);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_RENDER_SKY, on_render_sky);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_LOAD_SAVE_MENU, on_memcard_menu);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_MEMCARD_UI, on_memcard_menu);
}
