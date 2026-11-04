/* Kula World HD textures: on the first VBlank, if the installed pack does not
 * match the launcher options, copy the builder's source files from the mounted
 * disc to hd-auto/source and start tools/hd/hd_auto.py in the background. A
 * worker thread first fetches the portable Python (OS curl and tar, SHA-256
 * from tools/hd/python.lock). The pack is used from the next start; the runner
 * stops with the game (--parent-pid) and resumes on the next one. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <SDL3/SDL.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif
#include "mod_plugins.h"
#include "psx_sha256.h"
#include "hd_textures_logic.h"

#define PLUGIN_ID "kula.hd-textures"
#define FEATURE_ID "hd-textures"
#define PACK_DIR "mods/texture-packs/SCES-01000"
#define DATA_DIR "hd-auto"
#ifdef _WIN32
#define PYTHON_EXE "python/python/python.exe"
#else
#define PYTHON_EXE "python/python/bin/python3"
#endif

enum { PATH_SIZE = 1024, URL_SIZE = 1024, SHA_BYTES = 32, SHA_HEX_SIZE = 2 * SHA_BYTES + 1 };

/* Counters are emulation-thread state, so the worker hands its result over. */
enum {
    EV_NONE,
    EV_NO_PLATFORM,
    EV_DOWNLOAD_FAILED,
    EV_CHECKSUM_FAILED,
    EV_UNPACK_FAILED,
    EV_RUNNER_STARTED,
    EV_RUNNER_FAILED,
    EV_COUNT
};
static const char* const EVENT_NAMES[EV_COUNT] = {
    "",
    "kula.hd-textures.no_platform",
    "kula.hd-textures.download_failed",
    "kula.hd-textures.checksum_failed",
    "kula.hd-textures.unpack_failed",
    "kula.hd-textures.runner_started",
    "kula.hd-textures.runner_failed",
};

static int g_checked;
static int g_with_model;
static SDL_AtomicInt g_event;

/* <exe dir>/<relative>; 0 when it does not fit. */
static int beside_exe(char* out, const char* relative) {
    const char* base = SDL_GetBasePath();
    const int n = snprintf(out, PATH_SIZE, "%s%s", base ? base : "", relative);
    return n > 0 && n < PATH_SIZE;
}

static int data_path(char* out, const char* relative) {
    char joined[PATH_SIZE];
    return snprintf(joined, sizeof joined, DATA_DIR "/%s", relative) < PATH_SIZE &&
           beside_exe(out, joined);
}

static int option_model(void) {
    char value[8];
    return psx_mod_option_value(PLUGIN_ID, FEATURE_ID, "model", value, sizeof value) &&
           strcmp(value, "true") == 0;
}

static int pack_is_current(void) {
    char path[PATH_SIZE];
    if (!beside_exe(path, PACK_DIR "/hd-pack.json")) return 0;
    char* marker = SDL_LoadFile(path, NULL);
    const int current =
        hd_marker_matches(marker, g_with_model, KULA_HD_TOOL_VERSION, KULA_HD_MODEL_SHA256);
    SDL_free(marker);
    return current;
}

/* Written beside the target first, so a crash never leaves a short file. */
static int save_atomic(const char* path, const void* data, size_t size) {
    char tmp[PATH_SIZE];
    if (snprintf(tmp, sizeof tmp, "%s.tmp", path) >= PATH_SIZE) return 0;
    return SDL_SaveFile(tmp, data, size) && SDL_RenamePath(tmp, path);
}

static int make_parent(const char* path) {
    char dir[PATH_SIZE];
    snprintf(dir, sizeof dir, "%s", path);
    char* slash = strrchr(dir, '/');
    if (slash) *slash = '\0';
    return SDL_CreateDirectory(dir);
}

static int extract_file(const char* disc_path) {
    char relative[PATH_SIZE], target[PATH_SIZE];
    uint32_t size = 0;
    if (snprintf(relative, sizeof relative, "source/%s", disc_path) >= PATH_SIZE ||
        !data_path(target, relative) || !psx_mod_read_disc_file(disc_path, NULL, 0, &size))
        return 0;
    void* data = malloc(size);
    const int ok = data && psx_mod_read_disc_file(disc_path, data, size, &size) &&
                   make_parent(target) && save_atomic(target, data, size);
    free(data);
    return ok;
}

static int extract_sources(void) {
    for (int i = 0; i < HD_SOURCE_FILE_COUNT; i++)
        if (!extract_file(HD_SOURCE_FILES[i])) return 0;
    return 1;
}

static int run_and_wait(const char* const* args) {
    SDL_Process* process = SDL_CreateProcess(args, false);
    int code = -1;
    if (!process) return 0;
    SDL_WaitProcess(process, true, &code);
    SDL_DestroyProcess(process);
    return code == 0;
}

static int file_has_sha256(const char* path, const char* want_hex) {
    size_t size = 0;
    uint8_t digest[SHA_BYTES];
    char hex[SHA_HEX_SIZE];
    void* data = SDL_LoadFile(path, &size);
    if (!data) return 0;
    psx_sha256_compute(data, size, digest);
    SDL_free(data);
    for (int i = 0; i < SHA_BYTES; i++) snprintf(hex + 2 * i, 3, "%02x", digest[i]);
    return strcmp(hex, want_hex) == 0;
}

static int python_tarball(char* url, char* sha) {
    char lock_path[PATH_SIZE];
    const char* platform = hd_platform_key();
    if (!platform || !beside_exe(lock_path, "tools/hd/python.lock")) return 0;
    char* lock = SDL_LoadFile(lock_path, NULL);
    const int found = lock && hd_python_lock_find(lock, platform, url, URL_SIZE, sha, SHA_HEX_SIZE);
    SDL_free(lock);
    return found;
}

/* Fetches the portable Python unless an earlier start finished it (.ok). */
static int ensure_python(void) {
    char url[URL_SIZE], sha[SHA_HEX_SIZE], tar[PATH_SIZE], root[PATH_SIZE], ok[PATH_SIZE],
        exe[PATH_SIZE];
    if (!data_path(root, "python") || !data_path(ok, "python/.ok") ||
        !data_path(exe, PYTHON_EXE) || !data_path(tar, "downloads/python.tar.gz"))
        return EV_RUNNER_FAILED;
    if (SDL_GetPathInfo(ok, NULL) && SDL_GetPathInfo(exe, NULL)) return EV_NONE;
    if (!python_tarball(url, sha)) return EV_NO_PLATFORM;
    const char* curl[] = {"curl", "-fsSL", "--retry", "2", "-o", tar, url, NULL};
    if (!make_parent(tar) || !run_and_wait(curl)) {
        SDL_RemovePath(tar);
        return EV_DOWNLOAD_FAILED;
    }
    if (!file_has_sha256(tar, sha)) {
        SDL_RemovePath(tar);
        return EV_CHECKSUM_FAILED;
    }
    const char* untar[] = {"tar", "-xzf", tar, "-C", root, NULL};
    if (!SDL_CreateDirectory(root) || !run_and_wait(untar)) return EV_UNPACK_FAILED;
    SDL_RemovePath(tar);
    return SDL_SaveFile(ok, "", 0) ? EV_NONE : EV_UNPACK_FAILED;
}

static unsigned long own_pid(void) {
#ifdef _WIN32
    return (unsigned long)GetCurrentProcessId();
#else
    return (unsigned long)getpid();
#endif
}

/* Detached; the runner watches this process and stops with it (--parent-pid). */
static int start_runner(void) {
    char exe[PATH_SIZE], runner[PATH_SIZE], source[PATH_SIZE], pack[PATH_SIZE], data[PATH_SIZE],
        pid[24];
    if (!data_path(exe, PYTHON_EXE) || !beside_exe(runner, "tools/hd/hd_auto.py") ||
        !data_path(source, "source") || !beside_exe(pack, PACK_DIR) || !beside_exe(data, DATA_DIR))
        return EV_RUNNER_FAILED;
    snprintf(pid, sizeof pid, "%lu", own_pid());
    const char* args[] = {exe,  "-I",    runner,         "--disc", source, "--pack",
                          pack, "--data", data, "--parent-pid", pid, g_with_model ? "--with-model" : NULL,
                          NULL};
    SDL_PropertiesID props = SDL_CreateProperties();
    SDL_SetPointerProperty(props, SDL_PROP_PROCESS_CREATE_ARGS_POINTER, (void*)args);
    SDL_SetBooleanProperty(props, SDL_PROP_PROCESS_CREATE_BACKGROUND_BOOLEAN, true);
    SDL_Process* process = SDL_CreateProcessWithProperties(props);
    SDL_DestroyProperties(props);
    if (!process) return EV_RUNNER_FAILED;
    SDL_DestroyProcess(process); /* frees the handle only, the runner keeps going */
    return EV_RUNNER_STARTED;
}

static int SDLCALL setup_worker(void* unused) {
    (void)unused;
    const int python = ensure_python();
    SDL_SetAtomicInt(&g_event, python != EV_NONE ? python : start_runner());
    return 0;
}

static void report_worker(void) {
    const int event = SDL_SetAtomicInt(&g_event, EV_NONE);
    if (event <= EV_NONE || event >= EV_COUNT) return;
    psx_mod_counter_add(EVENT_NAMES[event], 1);
    if (event != EV_RUNNER_STARTED) fprintf(stderr, "%s\n", EVENT_NAMES[event]);
}

/* Disc reads need the emulation thread; downloads and process starts do not. */
static void start_build(void) {
    if (!extract_sources()) {
        psx_mod_counter_add("kula.hd-textures.extract_failed", 1);
        fprintf(stderr, "kula.hd-textures.extract_failed\n");
        return;
    }
    SDL_Thread* worker = SDL_CreateThread(setup_worker, "kula-hd-setup", NULL);
    if (!worker) {
        psx_mod_counter_add(EVENT_NAMES[EV_RUNNER_FAILED], 1);
        return;
    }
    SDL_DetachThread(worker);
}

static void on_vblank(void) {
    report_worker();
    if (g_checked) return;
    g_checked = 1;
    g_with_model = option_model();
    if (pack_is_current()) {
        psx_mod_counter_add("kula.hd-textures.up_to_date", 1);
        return;
    }
    start_build();
}

PSX_MOD_CONSTRUCTOR(register_kula_hd_textures) {
    (void)psx_mod_register_vblank_plugin(PLUGIN_ID, on_vblank);
}
