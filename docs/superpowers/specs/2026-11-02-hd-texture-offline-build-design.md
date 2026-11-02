# HD texture pack, offline build – design

Status: draft 2026-11-02, user questions answered, waiting for the user's approval of the whole document. Spike findings: `CLAUDE.md`, section "HD-Texturen" (rounds 1–8).

## Goal
Players get sharper textures without anyone shipping game art. Like Hercules Recompiled, the launcher builds the HD pack in the background from the player's own disc. Until the pack is ready the game runs with the original textures ("erstmal orginal dann hd"). The look is "like the original, only sharper", and it has to work in every level, not only W1/L1.

## Goals
- A build tool that turns the player's disc into a DuckStation-format pack under `<build>/mods/texture-packs/SCES-01000/replacements`. The framework mod `psx.enhancement.hd-textures` loads it, so the runtime needs no change.
- The look the user chose in the spike:
  - ground, items and everything else: **M60**
  - UI (HUD, fruits, keys, font): **M60R**
  - sky: **H-M2**
- Starting it, showing progress and stopping it from the launcher, with no terminal.
- Every step can resume. An interrupted build continues on the next start, and the pack is installed as a whole, never half-written.

## Non-goals
- **No pack for download.** No prebuilt pack from a release or any other server. This differs from Hercules, which downloads its own pack first. That conflicts with the hard rule, so it is out.
- **No change to the runtime or the framework.** If the build cannot do without one, raise it with the user first.
- **No video or `vram-write-` replacements**, so no `WARNING.TIM` and no FMV.
- **Other regions** (US/JP) are out for now. Only SCES-01000.

## Anti-goals (a failure even if it technically works)
- Game bytes, extracted assets, upscaled images or models end up in git or in a release.
- A model is downloaded without the player knowing about it, or its licence is ignored.
- Visible artefacts the spike already removed come back: boxes around HUD and font, sky lines, blue spots around the sun, frayed UI edges.
- The game stutters while the pack is being built. One CPU core is left free, as in Hercules.

## Constraints
- **Legal:** see `CLAUDE.md`, "Rechtliches". The repo may hold code, coordinates, hashes and UV tables, never pixel data.
- **Models:**
  - IllustrationJaNai V1 DAT2 is CC BY-NC-SA. It may not be shipped and is downloaded on the player's machine from the author's release, checked against a fixed SHA-256.
  - The HDcube licence is unchecked. The chosen look does not use HDcube, so it stays out.
- **Platforms:** Linux, Windows, macOS. CPU is the baseline. MPS (Apple) and CUDA are optional speed-ups.
- **Measured build times** (union pack, all worlds, about 2500 files):
  - MPS: model 591 s
  - CPU: about 18 min, a rough extrapolation from 20 files, so not reliable
  - Lanczos and mixing: seconds
- **Performance** (M1 Pro, W1/L1, one run each): 50 fps. `scene_gpu` is 9.5 ms against 12.2 ms for the original.
  - With the HD sky, `gl_evictions` reach about 550 in 20 s and about 1150 after a route, still without a fps drop.
  - Whether the cache budget holds on weaker GPUs is unknown.

## Decided by the user (spike, 2026-10-30)
- The pack is built in the background on the player's machine (Hercules model, minus the prebuilt download).
- **M60:** 60 % IllustrationJaNai + 40 % Lanczos on the colours, 4x. Alpha nearest in the exact classes 0/143/255.
- **M60R for the UI:** like M60, plus a rounded contour.
  - The 4x mask is Gaussian-blurred and cut at 0.5.
  - Near the edge the colour comes from Lanczos only.
  - The radius is chosen per file: the largest of 4 / 2 / 1.5 that keeps the number of connected regions unchanged, so the font does not break.
  - A UI file is a texture hash seen in at least 9 worlds that is STP or has alpha 0.
- **H-M for the sky,** built as H-M2: each band segment is upscaled on its own and mixed 60 % model + 40 % Lanczos per quad.
  - The user picked H-M live. H-M2 is the same method without the CLUT filter and looked nearly identical. The user has not seen H-M2 live.
- **Full palette range for everything.** Only names like `P0-15`/`P0-255`, never reduced ranges (`ReducePaletteRange: false`).
  - Reason: the hash covers the first N palette entries, not min…max. Reduced ranges collide (round 7b).

## How it works

### Steps
1. **extract:** Read `<WORLD>.TGI`, `HIRO/HIRO.TGI`, `HIRO/HIRO.GGI` (and whatever else holds textures or palettes) from the CUE/BIN via `tools/psxdisc.py`, below a work dir outside the repo.
2. **identify:** Rebuild for each texture the exact name the runtime looks up:
   - `texupload-<P4|P8|STP4|STP8>-<TexHash>-<PalHash>-<WxH words>-<X>-<Y>-<WxH texels>-P0-<15|255>.png`
   - `TexHash` is XXH3-64 (unseeded) over the uploaded words, `PalHash` the hash over the full palette.
   - Rules: `psxrecomp/docs/DUCKSTATION_TEXTURE_FORMAT.md`, code `psxrecomp/runtime/src/duckstation_texture_pack.cpp`.
3. **decode:** Render each texture with its palette to RGBA, the same way the dumper does: 5-bit to 8-bit rounding, alpha 0/143/255 by class.
4. **classify:**
   - sky: P8 with `384x256`. This rule holds in all 10 worlds, level 1 only.
   - UI: see M60R above.
   - everything else: M60.
5. **upscale:**
   - Model inference once per source image.
   - Lanczos and the mix per class.
   - The sky goes per band segment with edge-replicated padding, cut back, and Lanczos per quad.
   - Never read across a segment edge. Use `crop()` then `resize()`; Pillow's `resize(box=…)` reads outside the box, and that caused the false negative in round 3.
6. **verify:** Every output has alpha exactly 0/143/255 and the source size times 4. A failure stops the build.
7. **install:** Write the pack to a temp dir next to the target, then swap it in. Keep a marker with the tool version and the model SHA-256, so a newer tool rebuilds.

### Sky quad table
- The sky atlas uses only a few quads per band, and the filter must not cross their edges.
- Spike data:
  - W1 600, W4 725, W9 1152 rectangles, captured from frames, none of them converged.
  - The sets nest almost perfectly, which suggests one table for all worlds.
- Rectangles are 16-texel bands, 15 rows used. Within a band they run continuously in U.
- The build needs a complete table. Preferred: derive it from the game's sky mesh data (`RenderNonSpecialBackground` 0x563C4, dezgeg decomp). Fallback: a table in the repo (numbers only) built from captures until it stops growing.
- Texels outside the table fall back to whole-segment upscaling, never to nearest.

### Background run
- The launcher starts the tool as a separate process with low priority and one core left free. It shows the progress from a JSON file, the same idea as Hercules' `progress.json`.
  - Once the player has opted in, any start with a missing or stale pack starts the build.
  - Stopping the launcher stops the build, and the next start resumes it.
- **Tools on the player's machine:**
  - A pinned portable Python plus pinned packages (torch CPU, spandrel, numpy, Pillow, xxhash), each checked by SHA-256, as in Hercules `port/hd/hd_auto.py`.
  - If the game already ships a usable Python, that one is used.
- **The pack goes live on the next game start.** The runtime scans packs only at start, and live loading would need a framework change.

## Decided by the user (2026-11-02)
- **Opt-in:** The player enables HD in the launcher. Before the download, the launcher shows the model licence and the download size (about 1–2 GB for Python, torch and the model). Only then does the build start in the background.
- **Without the model** (no consent, offline, download failed): build a Lanczos-only pack. It uses the same classes, alpha handling, UI contour and sky segmentation, with Lanczos instead of the model. When the model becomes available later, the full pack replaces it.
- **The pack goes live on the next game start.** No framework change. The launcher says so once the build is done.
- **Hash/coordinate table allowed:** If the disc data cannot pair textures with palettes or upload rectangles, a table of hashes and coordinates may go into the repo. No pixel data, same as the address lists in `game.toml`.

## Left to the builder
- How TGI and GGI map textures to palettes and upload rectangles (wiki.kula.quest, `RetroAtlas/KulaWorldMap` docs). If the disc data cannot pair them, a hash/coordinate table in the repo is the fallback (allowed, see above).
- Where the dumper's used rectangle (`-X-Y-WxH-`) comes from offline. Dumps record the used area, the disc has the whole upload. Check whether a full-upload file matches the same draws, or whether the build needs the used rectangles.
- The four STP4 textures (88x79, 68x82) that were not found raw in TGI/GGI.
- The 10 sky files that matched none of the 19 captured CLUTs.
- How the launcher starts and watches the tool. Check recomp-ui and the Hercules launcher code. Changes to recomp-ui go upstream as a PR, like recomp-ui#110 and #114.
- Batch size and tiling for model inference on CPU, as long as the output matches the spike's chain.

## Acceptance
- **Name check:** For every world, the offline pack's file names cover the runtime dumps of that world (full range, all 15 levels, bonus levels, menus).
  - Target: 100 % of the dumped names, or every gap listed with its reason.
- **Pixel check:** Offline-decoded sources equal the runtime dumps, compared per file.
- **Mac, all worlds:** 50 fps, `scene_gpu`, `gl_evictions` after a route, and the user's live verdict for each world.
  - In particular: sky lines, spots around the sun, UI edges, font.
  - Then the remaining levels, as the user asked for all levels.
- **Linux:** `task smoke` unchanged (3603, 0 misses), `task test` and `task lint` pass.
- **Licence and opt-in:** Without the opt-in nothing is downloaded or built. The licence and the download size are shown before the download.
- **Fallback:** Without the model, a Lanczos pack is built. It shows no box, line or spot artefacts in W1/L1 on the Mac.
- **Git:** `git status` before every commit shows no PNG, dump, model or disc file.

## Open risks
- **Cache:** `gl_evictions` with the HD sky; the budget is unknown on weaker GPUs.
- **CPU build time:** only extrapolated from 20 files.
- **Test flakes:** `level_select_failed` hits test runs now and then and passes on a second try, cause unknown.
