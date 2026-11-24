# Build for Windows (x64)

Cross build on Linux with MinGW-w64, using the toolchain file that psxrecomp ships
(`psxrecomp/cmake/toolchain-mingw-w64.cmake`). A native build on Windows with MSYS2
works too, see `psxrecomp/docs/BUILDING.md` and `psxrecomp/docs/WINDOWS_TOOLCHAIN_TRAPS.md`.
Verified so far only under Wine, see [Verified on](#verified-on).

## Prerequisites (Linux host)
Everything from the Linux build (emitters, `generate`), plus the cross compiler. Wine is only
needed to test on Linux.
```sh
# Alpine
sudo apk add mingw-w64-gcc wine
# Debian/Ubuntu
sudo apt install g++-mingw-w64-x86-64 wine64
```

## Build
`generated/` is the same for every platform. Run `task emitters` and `task generate` first
if it is missing, then:
```sh
task build:win
```
This configures `build-win/` with:
- `-DCMAKE_TOOLCHAIN_FILE=psxrecomp/cmake/toolchain-mingw-w64.cmake`
- `-DPSXRECOMP_BIOS_STEMS=OpenBIOS`: only the bundled OpenBIOS, no retail BIOS backend.
- `-DPSX_DEBUG_TOOLS=ON`: the debug server, for the smoke test. Leave it out for a player build.

CMake downloads SDL3 3.4.10, zlib and libwebp and builds them for Windows. Later builds use ccache.

The result is `build-win/Kula_World_Recompiled.exe` (about 46 MB). It links SDL and the GCC
runtime statically and imports only system DLLs (UCRT `api-ms-win-crt-*`, `OPENGL32`, …),
so it runs without extra DLLs. Next to it the build stages `bios/openbios.bin`, `game.toml`,
the mods (`mods/bundled/`), the launcher assets and `tools/hd/` (HD texture runner).

The window and file icon `assets/launcher/kula.ico` is embedded through `windres`
(`APP_ICON`, configure prints `APP_ICON=… (RC=x86_64-w64-mingw32-windres)`). Check it with:
```sh
x86_64-w64-mingw32-windres --input build-win/Kula_World_Recompiled.exe --output-format=rc | grep -i icon
```

Box art: if `assets/launcher/original/boxart.tga` exists (`task boxart`, copyrighted, gitignored),
CMake uses it. A build you hand out must use the own cover, so remove that folder and reconfigure first.

## Run under Wine (Linux)
```sh
task run:win                                                  # launcher
RUNNER="xvfb-run -a" task run:win -- --no-launcher --debug-port 4390
python3 tools/smoke_boot.py --port 4390 --duration 420
```
The Wine prefix lives in `.wine-kula/` (gitignored). Under Xvfb/llvmpipe start headless runs with
`PSX_INTERNAL_RESOLUTION=native PSX_DYNRES=0` and `SDL_AUDIO_DRIVER=dummy`, as for the Linux build.
Stop a Wine run with `WINEPREFIX=$PWD/.wine-kula wineserver -k`.

## On Windows
Copy the whole `build-win/` folder, put the disc next to it and start `Kula_World_Recompiled.exe`.
The HD texture plugin downloads Python with the `curl.exe` and `tar.exe` that Windows 10 (1803)
and later ship.

## Verified on
2026-11-24, Alpine Linux, MinGW-w64 GCC 15.2, Wine 11.0 under Xvfb (llvmpipe):
- Build without errors, exe imports only system DLLs, icon embedded (6 sizes).
- `smoke_boot.py`: `demo_gameplay_reached`, demo 1 ends with timer 3603 as on Linux and macOS,
  then demo 2 starts. 0 dispatch misses. Widescreen 16:9 and HUD anchoring active.
- Launcher: box art, brand mark, Kula colors, font, only memory card 1, disc verified.

Not verified yet (needs a real Windows PC): fps on a real GPU, audio, controller, the
HD texture background build (Python download, model), launcher PLAY into the game.
