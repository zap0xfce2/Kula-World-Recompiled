# Build on macOS (Apple Silicon)

Native build on the Mac. psxrecomp supports macOS officially (`psxrecomp/docs/BUILDING.md`).
Not yet verified for this project on real hardware.

## Prerequisites
```sh
xcode-select --install
brew install cmake ninja pkg-config sdl3 python@3.12
```
Python 3.11+ is required (the CLT Python 3.9 is too old).

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
python3 psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . \
    --disc disc/SCES01000.CUE --bios bios/SCPH1001.BIN --no-toolchain-download
(cd psxrecomp && bash tools/regen_bios.sh --config bios/SCPH1001.toml)
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release
```
- `--no-toolchain-download` keeps the CLI on Apple Clang instead of fetching a toolchain pack and writing PATH hooks into the shell rc files.
- `regen_bios.sh` writes the BIOS stamp that `generate --bios` leaves out; without it CMake reports the BIOS as STALE.
- Unlike Alpine/musl, no `libucontext` flags are needed (`psx_fiber.c` has an `__APPLE__` path).

## Run
```sh
./build-release/Kula_World_Recompiled
```
If the recomp-ui launcher misbehaves, skip it:
```sh
./build-release/Kula_World_Recompiled --no-launcher --bios bios/SCPH1001.BIN --disc disc/SCES01000.CUE
```

## What to check
- Boot reaches the main menu, the attract demo starts after about 40 s idle.
- Steady 50 fps (under Linux/llvmpipe only 35 to 44 fps were reached).
- XA music, SFX and the ending FMV (`XA/FINAL.STR`) play; memory card save/load works.
- For tests with the debug server, configure an extra tree with `-DPSX_DEBUG_TOOLS=ON` and start with `--debug-port 4370`, then run `python3 tools/smoke_boot.py`.
