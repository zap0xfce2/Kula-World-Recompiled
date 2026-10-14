# Draft: upstream reports for RetroPortingToolKit/psxrecomp

Not posted yet. Needs owner approval before anything leaves this repo.

## 1. KUSEG smoke: Kula World (SCES-01000) boots on segment-aware codegen

Closes the "KUSEG titles" item in `docs/SEGMENT_AWARE_CODE.md` §7 for Kula World.

- Framework `f9c287f5` (includes `d67f0f93`), retail SCPH-1001, stock probe seeds (727 JAL targets).
- Generate: 971 functions, 569 shards, 3570 dispatch entries.
- Headless run without input: BIOS → title → main menu → attract demo (world 0 level 4, then world 1 level 4).
- A/B against psx-beetle (same BIOS bytes): same demo sequence, same `levelTimeLeft` end value (3603) for demo 1, same score (2770) in demo 2.
- `dispatch_stats`: 2,043,749 static hits, 0 misses, 0 segment misses.
- Not covered yet: interactive play, ending FMV, memory card, XA.

## 2. Portability findings on Alpine/musl (x86_64)

1. `runtime/src/psx_fiber.c`: musl has no `getcontext`/`makecontext`/`swapcontext`. Linking `libucontext` works; CMake could detect musl and link it.
2. `runtime/src/beetle_debug_server.c:1761`: `u_short` is undeclared on musl (`netinet/in.h` does not pull `sys/types.h`). `uint16_t` would be portable.
3. `psxrecomp_cli.py generate` downloads the glibc `cmake-clang-v1` pack on musl, which cannot run there, writes PATH hooks into `~/.zshrc` and `~/.profile`, and keeps probing `~/.local/share/retcomm` even with `--no-toolchain-download`. A libc check before the download would avoid it.
4. `generate --bios` writes `generated/SCPH1001_*.c` but no `SCPH1001.emitter.sha`, so the next configure reports the BIOS as STALE. Running `tools/regen_bios.sh --config bios/SCPH1001.toml` writes the stamp.
