/* Kula World widescreen: selects psxrecomp's native-wide view. 16:9 shapes the
 * first window, then the view follows the window up to 2:1, the widest the
 * game's generated sky covers (about 1.7x the 4:3 width). */
#include "mod_plugins.h"

#define PLUGIN_ID "kula.widescreen"

enum { FIRST_WINDOW_NUM = 16, FIRST_WINDOW_DEN = 9, MAX_ASPECT_NUM = 2, MAX_ASPECT_DEN = 1 };

static void on_activate(void) {
    (void)psx_mod_set_fixed_display_aspect(FIRST_WINDOW_NUM, FIRST_WINDOW_DEN);
    (void)psx_mod_set_adaptive_display_aspect(MAX_ASPECT_NUM, MAX_ASPECT_DEN);
}

PSX_MOD_CONSTRUCTOR(register_kula_widescreen) {
    (void)psx_mod_register_activation_plugin(PLUGIN_ID, on_activate);
}
