# Build on macOS (Apple Silicon)

Native build on the Mac. psxrecomp supports macOS officially (`psxrecomp/docs/BUILDING.md`).
Verified on an M1 Pro, see [Verified on](#verified-on).

## Prerequisites
```sh
xcode-select --install
brew install cmake ninja pkg-config sdl3 python@3.12
```
Python 3.11+ is required. The default `python3` (CLT) is 3.9, so the steps below call `python3.12` explicitly.

## Get the repo
There is no remote yet; the repo travels as a git bundle. Submodules come from GitHub.
```sh
git clone kula.bundle kula-world-recompiled
cd kula-world-recompiled
git submodule update --init --recursive
```
Copy your own game data next to it (never committed):
- `disc/SCES01000.BIN` + `disc/SCES01000.CUE`
- `bios/SCPH1001.BIN` (MD5 `924e392ed05558ffdb115408c263dccf`)

## Build
```sh
./psxrecomp/tools/ci/build_emitters.sh
python3.12 psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . \
    --disc disc/SCES01000.CUE --bios bios/SCPH1001.BIN --no-toolchain-download
(cd psxrecomp && PSXRECOMP_BIOS_BUILD=../build-recompiler bash tools/regen_bios.sh --config bios/SCPH1001.toml)
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DPSX_PYTHON="$(command -v python3.12)"
cmake --build build-release
```
Times on an M1 Pro: emitters 15 s, generate 25 s, runtime build 2:35 min.
- `--no-toolchain-download` keeps the CLI on Apple Clang instead of fetching a toolchain pack and writing PATH hooks into the shell rc files.
- `regen_bios.sh` writes the BIOS stamp that `generate --bios` leaves out; without it CMake reports the BIOS as STALE. It only looks for `psxrecomp/recompiler/build*`, so point it at the `build-recompiler/` tree from `build_emitters.sh` (path relative to `psxrecomp/`).
- `PSX_PYTHON`: `runtime.cmake` searches `python` before `python3`. A Python 2 `python` in `PATH` breaks `embed_spirv.py` with `SyntaxError: Non-ASCII character`.
- No `libucontext` flags are needed, unlike Alpine/musl (`psx_fiber.c` has an `__APPLE__` path).

## Run
```sh
./build-release/Kula_World_Recompiled
```
If the recomp-ui launcher misbehaves, skip it:
```sh
./build-release/Kula_World_Recompiled --no-launcher --bios bios/SCPH1001.BIN --disc disc/SCES01000.CUE
```
For tests with the debug server, configure an extra tree with `-DPSX_DEBUG_TOOLS=ON`, start with `--debug-port 4370`, then run `python3.12 tools/smoke_boot.py`.

## Troubleshooting
`fatal error: 'string' file not found` while building the emitters: an orphaned `/Library/Developer/CommandLineTools/usr/include/c++/v1/` from an old CLT install shadows the SDK headers (clang prefers it over the sysroot).
```sh
echo '#include <string>' | c++ -x c++ -fsyntax-only -v -   # shows which c++/v1 wins
sudo rm -rf /Library/Developer/CommandLineTools/usr/include/c++
rm -rf build-recompiler
```

## Verified on
macOS 27.0.1 (26A434), Apple M1 Pro (10 cores), cmake 4.4.4, Apple clang 21.0.0, SDL 3.4.18, Python 3.12 (2026-10-15).

| Check | Result |
|---|---|
| Build (Release and `PSX_DEBUG_TOOLS=ON`) | ok |
| Launcher (recomp-ui) | ok |
| Boot → menu → attract demo | ok, `smoke_boot.py`: `demo_gameplay_reached` |
| Frame rate | 49.5 fps over 60 s (50 Hz pacer; 120 Hz and 57 Hz panels), OpenGL 4.1 on Metal |
| XA music and SFX | ok |
| Keyboard input | ok |
| Controller | not tested |
| Memory card | not tested |
| Ending FMV | not tested |

The launcher run used the BIOS call-HLE tier (`bios_backend=HLE (LLE fallback)`). The Linux runs used `--no-launcher` and therefore LLE (default `bios_hle = false`). For A/B against Beetle, force LLE with `PSX_BIOS_HLE=0`.
