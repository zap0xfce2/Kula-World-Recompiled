# HD texture pack, part 3: launcher opt-in – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Kula mod package `kula.hd-textures` lets the player switch HD on in the launcher; the game then builds the pack in the background from the mounted disc.

**Architecture:** A trusted plugin reads the 12 source files from the mounted disc on its first VBlank and writes them to `hd-auto/source/`. A detached SDL thread fetches the portable Python if it is missing (OS `curl`, SHA-256, `tar`) and then starts `tools/hd/hd_auto.py` as an SDL background process. The builder accepts that folder in place of a CUE. A `[[requirement]]` switches on the framework's `psx.enhancement.hd-textures`.

**Tech Stack:** C99 plugin (psxrecomp mod API, SDL3 process/thread API, `psx_sha256.h`), Python 3.9+ runner, CMake staging.

**Spec:** `docs/superpowers/specs/2026-11-03-hd-texture-launcher-design.md`

## Global Constraints
- Never commit game data. That covers the extracted source files, packs, dumps, Python tarballs, wheels and the model. `hd-auto*/` is gitignored already.
- Commits and pushes only after asking the user. Tasks end without a commit, and one commit request comes at the end.
- Feature `default_enabled = false`. Option "AI model" is a boolean, default `false`, and its label names the licence CC BY-NC-SA 4.0 and about 1.5 GB of download.
- Paths beside the executable (`SDL_GetBasePath()`): runner at `tools/hd/hd_auto.py` (staged by CMake together with `tools/psxdisc.py`), data at `hd-auto/`, pack at `mods/texture-packs/SCES-01000`.
- The game must never stall: emulation-thread work is limited to reading 12 files (7.5 MB). Downloads and process starts run on a detached thread.
- Every failure leaves the game running normally. Report failures with a `kula.hd-textures.<event>` counter and one `stderr` line starting with `kula.hd-textures:`.
- Launcher texts in English. Code comments in English, in the style of the other plugins.
- Manifest `format_version = 7`, like the sibling packages.

## Review Focus
1. **Pack already current.** With an unchanged option, the plugin must neither extract nor download nor start anything (marker check, Task 3 test `marker_matches_written_marker`).
2. **The option changes after a finished pack** (m60 → off, or off → on). Expected: a rebuild in the new mode (marker mismatch, Task 3 tests for both directions).
3. **The lock file holds no line for the platform**, for example musl or Intel Mac. Expected: no download, a `no_platform` counter, and the game keeps running (Task 3 test `lock_without_platform_returns_zero`).
4. **A download that is interrupted or has the wrong hash.** Expected: the file is deleted, no `.ok` is written, and the next start tries again (Task 5 Linux check with a broken hash).
5. **The game closes during the Python download.** Expected: curl dies with the process or finishes, and nothing half-unpacked counts as ready, because `.ok` is only written after `tar` (Task 5, manual).

---

### Task 1: Builder reads a source folder

**Files:**
- Modify: `tools/hd/build_pack.py` (`disc_files`, `main`)
- Modify: `tools/hd/hd_auto.py` (`cleanup` also removes `source`)
- Test: `tests/test_hd_build_pack.py`, `tests/test_hd_auto.py`

**Interfaces:**
- Produces: `source_files(folder: Path) -> dict[str, bytes]`, with the same keys as `disc_files` (`"/SCES_010.00"`, `"/HIRO/HIRO.GGI"`, `"/<W>/<W>.TGI"`). `build_pack.py DISC_OR_FOLDER WORK …` takes a folder. `hd_auto --disc <folder>` passes it through unchanged.
- Shared predicate: `wanted(path: str) -> bool`, used by both `disc_files` and `source_files`.

- [ ] Step 1: Tests. `test_source_files_keys_match_disc_paths` writes `SCES_010.00`, `HIRO/HIRO.GGI` and `HIRO/HIRO.TGI` plus a decoy `HIRO/HIRO.SFX` into a temp folder and asserts `sorted(source_files(tmp)) == ["/HIRO/HIRO.GGI", "/HIRO/HIRO.TGI", "/SCES_010.00"]`. `test_cleanup_removes_source` asserts that `source/` is gone after `cleanup`.
- [ ] Step 2: `python3 -m unittest tests.test_hd_build_pack tests.test_hd_auto`. Expected: FAIL, because `source_files` does not exist and `source` remains.
- [ ] Step 3: Implement. In `main`, a folder argument skips `image_of`/`check_raw_image` and uses `source_files`. `check_disc` keeps validating the EXE.
- [ ] Step 4: Run the tests again. Expected: PASS. Then run `task lint`.

### Task 2: One Python lock for the runner and the plugin

**Files:**
- Create: `tools/hd/python.lock`
- Modify: `tools/hd/hd_auto.py` (`PBS`/`PYTHON_TARBALLS` replaced by `python_tarball`)
- Test: `tests/test_hd_auto.py`

**Interfaces:**
- Produces: the format of `python.lock`. Lines starting with `#` and empty lines are ignored. Every other line is `<platform-key> <full-url> <sha256>`, separated by single spaces. Keys: `linux-x86_64`, `windows-x86_64`, `macos-aarch64`. The URLs and hashes are copied unchanged from today's `PYTHON_TARBALLS`.
- Produces: `python_tarball(key: str, lock: Path = PYTHON_LOCK) -> tuple[str, str]` (url, sha256). If the key is missing, it raises `Failed("platform", …)`.

- [ ] Step 1: Tests. `test_python_lock_has_macos` asserts that `python_tarball("macos-aarch64")[1] == "8b0f1fa71eab7ca644e482c631807a1116fa848491051cd1c8d9429491de63a6"`. `test_python_lock_unknown_platform_fails` asserts the code `"platform"`.
- [ ] Step 2: Run the tests. Expected: FAIL (ImportError).
- [ ] Step 3: Implement. `phase_python` uses `python_tarball(platform_key())`, and its target name is the last URL segment with `%2B` → `+`.
- [ ] Step 4: Tests and lint pass.

### Task 3: Plugin logic (pure C)

**Files:**
- Create: `mods/src/hd_textures_logic.h`, `mods/src/hd_textures_logic.c`
- Create: `tests/test_hd_textures_logic.c`
- Modify: `Taskfile.yaml` (`test` builds and runs the new C test)

**Interfaces:**
- Produces:
  - `extern const char* const HD_SOURCE_FILES[]; enum { HD_SOURCE_FILE_COUNT = 12 };` These are disc paths without a leading slash: `SCES_010.00`, `HIRO/HIRO.GGI`, `HIRO/HIRO.TGI`, and `<W>/<W>.TGI` for ARCTIC, ATLANT, COWBOY, FIELD, HAZE, HELL, HILLS, INCA, MARS.
  - `int hd_marker_matches(const char* marker, int with_model, int tool_version, const char* model_sha256);` It returns 1 if `marker` (the contents of `hd-pack.json`, trailing whitespace allowed) is exactly what `build_pack.stage` writes: `{"tool": 7, "upscaler": "m60", "model_sha256": "<sha>"}`, or `… "upscaler": "lanczos", "model_sha256": null}`. A NULL marker returns 0.
  - `int hd_python_lock_find(const char* lock_text, const char* platform, char* url, size_t url_size, char* sha256, size_t sha_size);` It returns 1 if a line is found and both values fit.
  - `const char* hd_platform_key(void);` It returns `"linux-x86_64"` (only with `__GLIBC__`), `"windows-x86_64"`, `"macos-aarch64"`, or NULL.

- [ ] Step 1: Tests in the style of `tests/test_widescreen_logic.c`, one assert per case:
  - `marker_matches_written_marker`: lanczos, with the exact string from Python `json.dumps`.
  - `marker_matches_model_marker`: m60 with a sha.
  - `marker_rejects_other_upscaler`: an m60 marker read with `with_model=0`.
  - `marker_rejects_lanczos_when_model_wanted`.
  - `marker_rejects_old_tool`: tool 6 against tool 7.
  - `marker_rejects_null`.
  - `lock_finds_platform`: the URL of the second line.
  - `lock_skips_comments`.
  - `lock_without_platform_returns_zero`.
  - `lock_rejects_small_buffer`.
  - `source_files_has_twelve_entries`: the last entry is non-NULL.
- [ ] Step 2: `task test`. Expected: compile error (functions missing).
- [ ] Step 3: Implement. `hd_marker_matches` builds the expected string with `snprintf` and compares it with `strncmp` plus trailing whitespace. The lock parser works line by line with `sscanf("%63s %1023s %64s")`.
- [ ] Step 4: `task test`. Expected: all C and Python tests pass.

### Task 4: Package, plugin and CMake

**Files:**
- Create: `mods/preloaded/packages/kula.hd-textures/1.0.0/manifest.toml`
- Create: `mods/src/kula_hd_textures.c`
- Modify: `CMakeLists.txt`. Add both sources to `target_sources`. Add compile definitions `KULA_HD_TOOL_VERSION`, parsed from `tools/hd/build_pack.py` (`^TOOL_VERSION = (\d+)$`), and `KULA_HD_MODEL_SHA256`, parsed from `tools/hd/hd_auto.py` (`^MODEL_SHA256 = "([0-9a-f]+)"$`). Register both files in `CMAKE_CONFIGURE_DEPENDS`. Add a POST_BUILD `copy_directory tools/hd` → `<exe>/tools/hd` and a `copy_if_different tools/psxdisc.py` → `<exe>/tools/psxdisc.py`.

**Interfaces:**
- Consumes: Task 3 (`hd_marker_matches`, `hd_python_lock_find`, `hd_platform_key`, `HD_SOURCE_FILES`), and Task 1/2 (`hd_auto.py --disc <folder>`, `python.lock`).
- Manifest:
  - id `kula.hd-textures`, feature `hd-textures`, name "HD Textures", group "Visual", `default_enabled = false`
  - description: "Builds a 4x texture pack from your own disc in the background while you play; it is used from the next start. The first build takes a few minutes, 10–20 minutes with the AI model. Downloads a portable Python (about 50 MB)."
  - `[[option]]` id `model`, type boolean, default `"false"`, label "AI model (CC BY-NC-SA 4.0, about 1.5 GB download)", description "Sharper look with the IllustrationJaNai model, for non-commercial use only. Off: a Lanczos pack without the model."
  - `[[requirement]] feature = "hd-textures"`, `package = "psx.enhancement.hd-textures"`, `requires_feature = "hd-textures"`
  - `[[plugin]] feature = "hd-textures"`, `id = "kula.hd-textures"`
- Plugin flow:
  1. The VBlank callback runs once per process (static flag).
  2. It reads the `model` option and `<base>/mods/texture-packs/SCES-01000/hd-pack.json`. If the marker matches, it adds the counter `up_to_date` and does nothing more.
  3. Otherwise it reads each `HD_SOURCE_FILES` entry with `psx_mod_read_disc_file` (size query, then into a buffer) and writes it to `<base>/hd-auto/source/<path>` (`.tmp` + rename). Any read failure ends with the counter `extract_failed`.
  4. Then `SDL_CreateThread` + `SDL_DetachThread` start a worker:
     - If `<data>/python/.ok` is missing, download `<data>/downloads/python.tar.gz` (`curl -fsSL --retry 2 -o`), check its SHA-256, run `tar -xzf … -C <data>/python`, and write `.ok`.
     - Then start `python -I <base>/tools/hd/hd_auto.py --disc <data>/source --pack <pack> --data <data> --parent-pid <pid> [--with-model]` with `SDL_PROP_PROCESS_CREATE_BACKGROUND_BOOLEAN = true`.
  5. Counters: `download_failed`, `checksum_failed`, `unpack_failed`, `no_platform`, `runner_started`, `runner_failed`.

- [ ] Step 1: `cmake --build build-dev`. Expected: it builds without warnings in the new files, `build-dev/tools/hd/hd_auto.py` and `build-dev/tools/psxdisc.py` exist, and `build-dev/mods/preloaded/…/kula.hd-textures` (or the staged catalog) contains the manifest.
- [ ] Step 2: Start the dev runtime with `--no-launcher` and the feature off (default). Expected: no `build-dev/hd-auto/`, the smoke test passes with 3603 and 0 misses.

### Task 5: End-to-end on Linux

No code. These checks run against `build-dev` with `state.toml` (feature on, `model = "false"`).

- [ ] Step 1: First start without Python. Expected: 12 files under `build-dev/hd-auto/source/` (7,558,960 bytes in total), then `python/.ok` and `python/python/bin/python3` (glibc, which will not run on musl), then the counter `runner_failed` or a runner error in `hd-build.log`. The game keeps running throughout.
- [ ] Step 2: Use a broken hash in a copy of the lock (temporarily changed in `build-dev/tools/hd/python.lock`) with Python deleted. Expected: `checksum_failed`, no `.ok`, no tarball left. Then restore the lock.
- [ ] Step 3: Linux stand-in: link `.venv-hd/bin/python` as `hd-auto/python/python/bin/python3`, write the package stamp `.packages-base-linux-x86_64` with the lock hash, keep `.ok`. Start the game. Expected: `hd-build.log` shows the build from the folder, `progress.json` reaches `done`, and the pack has 48,867 files with marker `lanczos`.
- [ ] Step 4: Next start. Expected: counter `up_to_date`, no new process, `hd-auto/source` is gone. In W1/L1, `{"cmd":"hd_textures"}` shows `applied_draws` > 0.
- [ ] Step 5: Close the game during the build (Step 3 variant). Expected: `progress.json` `stopped`, and the next start resumes.

### Task 6: Docs, Mac order, commit request

- [ ] Step 1: Mark the spec "approved, plan …". Update the part 3 block in `CLAUDE.md` with the results from Task 5 and the gotchas.
- [ ] Step 2: `git status` (no game data). Ask the user for the commit and push. After approval, send the Mac order: launcher on/off, real Python download, Lanczos and model run, fps during the build (W1, 20 s), and the second start with the pack.
