/* Kula World detail distance: keeps far cubes on their full texture and items
 * on their full model (no plain yellow discs). Only the thresholds change; the
 * game's short blur while turning stays, rebuilt from the raised values. */
#include <stdint.h>
#include "detail_distance_logic.h"
#include "mod_plugins.h"

#define PLUGIN_ID "kula.detail-distance"

/* EU addresses (dezgeg/kula-world-decomp). */
enum {
    VAR_TGI = 0x800a52f0u,                  /* TgiFile* tgi */
    TGI_LOD_DISTANCE = 0x110,               /* int lodDistance[7] */
    VAR_BLUR_TABLE = 0x800d0430u,           /* int turningMotionBlurTable[9 * 7] */
    VAR_BLUR_ENABLED = 0x800a55c0u,         /* int turningMotionBlurEnabled */
    VAR_PRIMS_PTR = 0x800a4cecu,            /* void* renderedPrimsBuf */
    VAR_PRIM_USAGE = 0x800a2cb8u,           /* int primBufUsage, of the last frame */
    VAR_WHICH_DRAW_ENV = 0x800a52bcu,       /* int whichDrawDispEnv */
    FN_AFTER_PRIMS_RESET = 0x000431b8u,     /* UnusedProcessDisplayModeChange, main loop only */
    GAME_PRIMS_BUF = 0x00179000u,           /* RENDERED_PRIMS_BUF */
    GAME_PRIMS_ENV_BYTES = 0xc000,          /* 48 KB per env, QUAD_BUF follows */
    PRIMS_ENV_BYTES = 0x80000,              /* ~57 KB measured in Demo 2, ample headroom */
    WORD = 4,
    KSEG0 = 0x80000000u,
    PHYS_MASK = 0x001fffffu,
    GPU_ADDR_MASK = 0x00ffffffu, /* the game keeps the pointer unsegmented */
};

static int g_table[DD_BLUR_PHASES * DD_LOD_COUNT];
static uint32_t g_prims;     /* our arena, both envs; 0 = game buffer stays */
static uint32_t g_max_prims; /* largest frame seen, mirrored into a counter */
static uint32_t g_last_usage;
static uint32_t g_last_env;

/* The game rebuilds the table from the TGI on every world load. */
static void keep_blur_table(void) {
    if ((int)psx_mod_read_word(VAR_BLUR_TABLE + WORD) == g_table[1]) return;
    for (int i = 0; i < DD_BLUR_PHASES * DD_LOD_COUNT; ++i)
        psx_mod_write_word(VAR_BLUR_TABLE + (uint32_t)i * WORD, (uint32_t)g_table[i]);
}

/* Each level start copies phase 0 into lodDistance, possibly before this VBlank. */
static void keep_resting_lods(uint32_t tgi) {
    if (psx_mod_read_word(VAR_BLUR_ENABLED) != 0) return;
    const uint32_t lods = tgi + TGI_LOD_DISTANCE;
    for (int i = 0; i < DD_LOD_COUNT; ++i) {
        if ((int)psx_mod_read_word(lods + (uint32_t)i * WORD) != g_table[i])
            psx_mod_write_word(lods + (uint32_t)i * WORD, (uint32_t)g_table[i]);
    }
}

static void on_vblank(void) {
    const uint32_t tgi = psx_mod_read_word(VAR_TGI);
    if (tgi == 0) return; /* no world loaded yet */
    keep_blur_table();
    keep_resting_lods((tgi & PHYS_MASK) | KSEG0);
}

/* primBufUsage is measured against the game's buffer; turn it back into bytes
 * of our arena. It belongs to the env this hook set last: around level loads
 * the game also flips the env outside the main loop. */
static void track_prim_usage(void) {
    const uint32_t usage = psx_mod_read_word(VAR_PRIM_USAGE);
    if (usage == g_last_usage) return; /* no level frame drawn since */
    g_last_usage = usage;
    const uint32_t end = usage + GAME_PRIMS_BUF + g_last_env * GAME_PRIMS_ENV_BYTES;
    const uint32_t used = (end - (g_prims + g_last_env * PRIMS_ENV_BYTES)) & GPU_ADDR_MASK;
    if (used > PRIMS_ENV_BYTES || used <= g_max_prims) return;
    psx_mod_counter_add("kula.detail-distance.max_prim_bytes", used - g_max_prims);
    g_max_prims = used;
}

/* The far detail overflows the game's 48 KB primitive buffer into the level
 * quads; the main loop just set the pointer, so move it into our arena. */
static int on_prims_reset(struct CPUState* cpu, uint32_t address) {
    (void)cpu;
    (void)address;
    if (!g_prims) return 0;
    const uint32_t env = psx_mod_read_word(VAR_WHICH_DRAW_ENV) & 1u;
    track_prim_usage();
    g_last_env = env;
    psx_mod_write_word(VAR_PRIMS_PTR, g_prims + env * PRIMS_ENV_BYTES);
    return 0;
}

/* GPU-DMA memory: linked-list tags reach it with their 24-bit addresses. */
static void on_activate(void) {
    g_prims = psx_mod_alloc_gpu_dma_memory(2 * PRIMS_ENV_BYTES, WORD);
    g_max_prims = 0;
    g_last_usage = 0;
    g_last_env = 0;
}

PSX_MOD_CONSTRUCTOR(register_kula_detail_distance) {
    dd_blur_table(DD_DETAIL_LODS, g_table);
    (void)psx_mod_register_activation_plugin(PLUGIN_ID, on_activate);
    (void)psx_mod_register_vblank_plugin(PLUGIN_ID, on_vblank);
    (void)psx_mod_register_function_filter_plugin(PLUGIN_ID, FN_AFTER_PRIMS_RESET, on_prims_reset);
}
