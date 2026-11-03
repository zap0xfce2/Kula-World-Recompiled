/* Pure decisions for the Kula World HD texture build plugin.
 * No host or guest access here so it can be unit tested. */
#pragma once

#include <stddef.h>

/* Disc files the pack builder reads (tools/hd/build_pack.py wanted()). */
enum { HD_SOURCE_FILE_COUNT = 12 };
extern const char* const HD_SOURCE_FILES[HD_SOURCE_FILE_COUNT];

/* 1 when hd-pack.json is what a build for these options would write. */
int hd_marker_matches(const char* marker, int with_model, int tool_version,
                      const char* model_sha256);

/* URL and SHA-256 of the portable Python for a platform from python.lock text. */
int hd_python_lock_find(const char* lock_text, const char* platform, char* url,
                        size_t url_size, char* sha256, size_t sha_size);

/* Key as in python.lock, or NULL when no portable Python exists for this build. */
const char* hd_platform_key(void);
