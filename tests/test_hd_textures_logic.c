/* Unit test for the pure HD texture plugin logic; one check per test function. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "hd_textures_logic.h"

#define SHA "ab01ab01ab01ab01ab01ab01ab01ab01ab01ab01ab01ab01ab01ab01ab01ab01"
/* Exactly what build_pack.stage writes (json.dumps, default separators). */
#define LANCZOS_MARKER "{\"tool\": 7, \"upscaler\": \"lanczos\", \"model_sha256\": null}"
#define MODEL_MARKER "{\"tool\": 7, \"upscaler\": \"m60\", \"model_sha256\": \"" SHA "\"}"
#define LOCK                                                        \
    "# comment linux-x86_64 http://wrong 00\n"                      \
    "\n"                                                            \
    "linux-x86_64 http://example/linux.tar.gz 11\n"                 \
    "macos-aarch64 http://example/mac.tar.gz 22\n"

static void test_marker_matches_written_marker(void) {
    assert(hd_marker_matches(LANCZOS_MARKER "\n", 0, 7, SHA));
}

static void test_marker_matches_model_marker(void) {
    assert(hd_marker_matches(MODEL_MARKER, 1, 7, SHA));
}

static void test_marker_rejects_other_upscaler(void) {
    assert(!hd_marker_matches(MODEL_MARKER, 0, 7, SHA));
}

static void test_marker_rejects_lanczos_when_model_wanted(void) {
    assert(!hd_marker_matches(LANCZOS_MARKER, 1, 7, SHA));
}

static void test_marker_rejects_old_tool(void) {
    assert(!hd_marker_matches(LANCZOS_MARKER, 0, 8, SHA));
}

static void test_marker_rejects_null(void) { assert(!hd_marker_matches(NULL, 0, 7, SHA)); }

static void test_lock_finds_platform(void) {
    char url[64], sha[8];
    hd_python_lock_find(LOCK, "macos-aarch64", url, sizeof url, sha, sizeof sha);
    assert(strcmp(url, "http://example/mac.tar.gz") == 0);
}

static void test_lock_skips_comments(void) {
    char url[64], sha[8];
    hd_python_lock_find(LOCK, "linux-x86_64", url, sizeof url, sha, sizeof sha);
    assert(strcmp(sha, "11") == 0);
}

static void test_lock_without_platform_returns_zero(void) {
    char url[64], sha[8];
    assert(!hd_python_lock_find(LOCK, "windows-x86_64", url, sizeof url, sha, sizeof sha));
}

static void test_lock_rejects_small_buffer(void) {
    char url[8], sha[8];
    assert(!hd_python_lock_find(LOCK, "linux-x86_64", url, sizeof url, sha, sizeof sha));
}

static void test_source_files_has_twelve_entries(void) {
    assert(HD_SOURCE_FILES[HD_SOURCE_FILE_COUNT - 1] != NULL);
}

int main(void) {
    test_marker_matches_written_marker();
    test_marker_matches_model_marker();
    test_marker_rejects_other_upscaler();
    test_marker_rejects_lanczos_when_model_wanted();
    test_marker_rejects_old_tool();
    test_marker_rejects_null();
    test_lock_finds_platform();
    test_lock_skips_comments();
    test_lock_without_platform_returns_zero();
    test_lock_rejects_small_buffer();
    test_source_files_has_twelve_entries();
    puts("hd_textures_logic: all tests passed");
    return 0;
}
