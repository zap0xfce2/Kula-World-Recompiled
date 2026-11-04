cmake_minimum_required(VERSION 3.20)
set(PSXRECOMP_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/psxrecomp" CACHE PATH
    "Path to psxrecomp")
if(NOT EXISTS "${PSXRECOMP_ROOT}/runtime/runtime.cmake")
    message(FATAL_ERROR
        "PSXRecomp runtime is missing: ${PSXRECOMP_ROOT}/runtime/runtime.cmake\n"
        "This project expects the psxrecomp framework checkout at ${PSXRECOMP_ROOT}.\n"
        "Run: git submodule update --init --recursive\n"
        "If psxrecomp/ is not a submodule, set -DPSXRECOMP_ROOT=<path-to-psxrecomp>.")
endif()

project(Kula_World_Recompiled LANGUAGES C CXX)

# --- Opt-in product surfaces (OFF by default in the framework) -------------
# Scaffold prompts / flags fill these. Without recomp-ui, PSX_RECOMP_UI is OFF.
# The wizard (WIZARD_CMAKE_BLOCK / ENABLE_SETUP_WIZARD) is the first-run disc
# picker; releases are compiled from the committed generated/ C, so it never
# needs to generate or rebuild anything on a player's machine.
# recomp-ui submodule present (PSX_RECOMP_UI defaults ON).
# Full netplay UI — enable after adding recomp-ui + testing:
# if(EXISTS "${PSXRECOMP_ROOT}/lib/recomp-net/CMakeLists.txt")
#     set(PSX_NETPLAY ON CACHE BOOL "…" FORCE)
# endif()
set(PSX_SETUP_WIZARD ON CACHE BOOL
    "Advertise first-run setup wizard + Generate & rebuild in recomp-ui" FORCE)
include("${PSXRECOMP_ROOT}/runtime/runtime.cmake")

# This project's own mod catalog. The FRAMEWORK stages it -- together with its
# builtin psx.* packages -- into <exe-dir>/mods/bundled, and refuses to
# configure if a catalog exists here but is not declared. Never copy it by
# hand: five titles did, and framework 4cc04be3's rename of the staged
# directory broke all five silently (bead beads-eio.3.101).
set(PSX_PRELOADED_MODS "${CMAKE_CURRENT_SOURCE_DIR}/mods/preloaded")
if(NOT IS_DIRECTORY "${PSX_PRELOADED_MODS}")
    set(PSX_PRELOADED_MODS "NONE")
endif()

# The original cover is copyrighted and only fetched locally (task boxart);
# without it the launcher shows our own box art.
set(KULA_BOXART "${CMAKE_CURRENT_SOURCE_DIR}/assets/launcher/original/boxart.tga")
if(NOT EXISTS "${KULA_BOXART}")
    set(KULA_BOXART "${CMAKE_CURRENT_SOURCE_DIR}/assets/launcher/boxart.tga")
endif()
message(STATUS "Launcher box art: ${KULA_BOXART}")

# PGXP hook flavor: the psx.enhancement.pgxp override in mods/preloaded turns it
# on by default; without the hook build its coverage drops (ENHANCEMENTS.md G1.11).
psxrecomp_add_game_runtime(psx-runtime
    PGXP
    PRELOADED_MODS_DIR "${PSX_PRELOADED_MODS}"
    # ENABLE_NETPLAY_IF_PRESENT
    # NETPLAY_LOBBY_URL "ws://netplay.retcomm.net:8765"
    ENABLE_SETUP_WIZARD
    WINDOW_TITLE "Kula World Recompiled"
    DEFAULT_GAME_CONFIG_PATH "game.toml"
    MAX_PLAYERS 2
    # Kula only uses memory card port 1 (decomp: MemCardAccept(0)).
    MEMCARD_SLOTS 1
    # Own launcher art, rendered from assets/launcher/*.svg (task launcher-art).
    LAUNCHER_BOXART "${KULA_BOXART}"
    LAUNCHER_BRAND "${CMAKE_CURRENT_SOURCE_DIR}/assets/launcher/brand.tga"
    APP_ICON "${CMAKE_CURRENT_SOURCE_DIR}/assets/launcher/kula.ico"
    # Committed game C (psxrecomp_cli.py generate; git add generated). Release
    # CI configures with -DPSXRECOMP_REQUIRE_GAME_C=ON so a checkout without
    # it fails instead of building a setup host.
    GEN_MARKER "generated/SCES_010.00_dispatch.c"
    GEN_FULL_GLOB "generated/SCES_010.00_full_*.c"
    CODEGEN_SETUP_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/codegen_setup.c"
)

# Game-owned trusted mod plugins (manifests in mods/preloaded).
target_sources(psx-runtime PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/src/kula_level_select.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/src/level_select_logic.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/src/kula_widescreen.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/src/widescreen_logic.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/src/kula_hd_textures.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/src/hd_textures_logic.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/src/kula_detail_distance.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/mods/src/detail_distance_logic.c")
target_include_directories(psx-runtime PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/mods/src")

# The HD plugin compares hd-pack.json with what the runner would build now;
# both values come from the Python sources so they never drift apart.
set(_KULA_HD_TOOLS "${CMAKE_CURRENT_SOURCE_DIR}/tools/hd")
file(STRINGS "${_KULA_HD_TOOLS}/build_pack.py" _KULA_HD_TOOL_LINE REGEX "^TOOL_VERSION = [0-9]+$")
file(STRINGS "${_KULA_HD_TOOLS}/hd_auto.py" _KULA_HD_MODEL_LINE REGEX "^MODEL_SHA256 = \"[0-9a-f]+\"$")
string(REGEX REPLACE "^TOOL_VERSION = " "" KULA_HD_TOOL_VERSION "${_KULA_HD_TOOL_LINE}")
string(REGEX REPLACE "^MODEL_SHA256 = \"([0-9a-f]+)\"$" "\\1" KULA_HD_MODEL_SHA256 "${_KULA_HD_MODEL_LINE}")
if(NOT KULA_HD_TOOL_VERSION OR NOT KULA_HD_MODEL_SHA256)
    message(FATAL_ERROR "TOOL_VERSION or MODEL_SHA256 not found in tools/hd")
endif()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${_KULA_HD_TOOLS}/build_pack.py" "${_KULA_HD_TOOLS}/hd_auto.py")
set_source_files_properties("${CMAKE_CURRENT_SOURCE_DIR}/mods/src/kula_hd_textures.c"
    PROPERTIES COMPILE_DEFINITIONS
    "KULA_HD_TOOL_VERSION=${KULA_HD_TOOL_VERSION};KULA_HD_MODEL_SHA256=\"${KULA_HD_MODEL_SHA256}\"")

# The runner and builder beside the exe, where the plugin starts them. A target
# of its own, not POST_BUILD: a change to tools/hd alone does not relink.
add_custom_target(kula-hd-tools ALL
    COMMAND ${CMAKE_COMMAND} -E copy_directory "${_KULA_HD_TOOLS}" "$<TARGET_FILE_DIR:psx-runtime>/tools/hd"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_SOURCE_DIR}/tools/psxdisc.py"
        "$<TARGET_FILE_DIR:psx-runtime>/tools/psxdisc.py"
    COMMAND ${CMAKE_COMMAND} -E rm -rf "$<TARGET_FILE_DIR:psx-runtime>/tools/hd/__pycache__"
    COMMENT "Staging the HD texture runner"
    VERBATIM)

# Stage runtime configs next to the exe for direct build/ launches. Only copy
# files that exist — never fail POST_BUILD when game_options.toml is absent.
foreach(_PSX_RUNTIME_CONFIG game.toml game_options.toml)
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${_PSX_RUNTIME_CONFIG}")
        add_custom_command(TARGET psx-runtime POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${CMAKE_CURRENT_SOURCE_DIR}/${_PSX_RUNTIME_CONFIG}"
                "$<TARGET_FILE_DIR:psx-runtime>/${_PSX_RUNTIME_CONFIG}"
            COMMENT "Staging ${_PSX_RUNTIME_CONFIG}"
            VERBATIM)
    endif()
endforeach()
