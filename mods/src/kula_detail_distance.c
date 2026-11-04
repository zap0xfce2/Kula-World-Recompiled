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
    WORD = 4,
    KSEG0 = 0x80000000u,
    PHYS_MASK = 0x001fffffu,
};

static int g_table[DD_BLUR_PHASES * DD_LOD_COUNT];

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

PSX_MOD_CONSTRUCTOR(register_kula_detail_distance) {
    dd_blur_table(DD_DETAIL_LODS, g_table);
    (void)psx_mod_register_vblank_plugin(PLUGIN_ID, on_vblank);
}
