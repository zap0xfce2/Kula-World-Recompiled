#include "hd_textures_logic.h"

#include <stdio.h>
#include <string.h>

enum { MARKER_MAX = 256, LOCK_FIELD_MAX = 1024 };

const char* const HD_SOURCE_FILES[HD_SOURCE_FILE_COUNT] = {
    "SCES_010.00",       "HIRO/HIRO.GGI",     "HIRO/HIRO.TGI",
    "ARCTIC/ARCTIC.TGI", "ATLANT/ATLANT.TGI", "COWBOY/COWBOY.TGI",
    "FIELD/FIELD.TGI",   "HAZE/HAZE.TGI",     "HELL/HELL.TGI",
    "HILLS/HILLS.TGI",   "INCA/INCA.TGI",     "MARS/MARS.TGI",
};

static int only_space(const char* s) {
    while (*s == ' ' || *s == '\n' || *s == '\r' || *s == '\t') s++;
    return *s == '\0';
}

/* The marker is written by build_pack.stage with json.dumps defaults. */
int hd_marker_matches(const char* marker, int with_model, int tool_version,
                      const char* model_sha256) {
    char want[MARKER_MAX];
    if (!marker) return 0;
    if (with_model)
        snprintf(want, sizeof want,
                 "{\"tool\": %d, \"upscaler\": \"m60\", \"model_sha256\": \"%s\"}",
                 tool_version, model_sha256);
    else
        snprintf(want, sizeof want,
                 "{\"tool\": %d, \"upscaler\": \"lanczos\", \"model_sha256\": null}",
                 tool_version);
    const size_t len = strlen(want);
    return strncmp(marker, want, len) == 0 && only_space(marker + len);
}

static int copy_field(const char* value, char* out, size_t size) {
    if (strlen(value) >= size) return 0;
    memcpy(out, value, strlen(value) + 1);
    return 1;
}

int hd_python_lock_find(const char* lock_text, const char* platform, char* url,
                        size_t url_size, char* sha256, size_t sha_size) {
    char key[LOCK_FIELD_MAX], link[LOCK_FIELD_MAX], digest[LOCK_FIELD_MAX];
    for (const char* line = lock_text; line && *line;) {
        const char* end = strchr(line, '\n');
        if (*line != '#' && sscanf(line, "%1023s %1023s %1023s", key, link, digest) == 3 &&
            strcmp(key, platform) == 0)
            return copy_field(link, url, url_size) && copy_field(digest, sha256, sha_size);
        line = end ? end + 1 : NULL;
    }
    return 0;
}

const char* hd_platform_key(void) {
#if defined(_WIN32) && (defined(_M_X64) || defined(__x86_64__))
    return "windows-x86_64";
#elif defined(__APPLE__) && defined(__aarch64__)
    return "macos-aarch64";
#elif defined(__linux__) && defined(__x86_64__) && defined(__GLIBC__)
    return "linux-x86_64";
#else
    return NULL; /* e.g. musl: the portable Python needs glibc */
#endif
}
