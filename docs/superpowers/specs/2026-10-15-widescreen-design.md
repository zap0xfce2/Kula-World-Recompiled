# Widescreen mod – design

Status: approved 2026-10-15 (cap 2:1), implemented on `feat/widescreen-mod`; Linux verified, Mac pending.

## Goal
Play Kula World in widescreen: the world is shown wider, not stretched, and the window can have any aspect from 4:3 up (16:9, 21:9, ...).
No ready-made Kula widescreen patch exists (DuckStation database, cheat lists and forums checked on 2026-10-15). psxrecomp's own widescreen support does most of the work.

## User decisions (2026-10-15)
- New launcher mod "Widescreen" (`kula.widescreen`), group "Graphics", **on by default**, can be switched off.
- **Fit to window**: the view follows the window's aspect, never narrower than 4:3, with no upper limit.
- **HUD in the wide corners**: the key on the left and the fruits on the right move to the outer edges.

## What the spike showed (local branch `spike/widescreen`, Linux, 16:9)
- A trusted plugin that calls `psx_mod_set_fixed_display_aspect(16, 9)` plus `[widescreen] gte_game_mode = true` engages native-wide.
  - Without `gte_game_mode` the runtime keeps presenting 4:3: Kula has no sprite-tag helper.
- World, ball, title, menu text and HUD keep correct proportions. The menu runs over a 3D level, so it goes wide too, and that looks right.
- **Sky gaps:** sky tiles are missing at the new left and right edges (jagged borders).
- **HUD:** it stays at its 4:3 position.
- **`nw_hud_corners = true` breaks the sky:** it also shifts sky pieces drawn as 2D sprites, which leaves dark jagged bands in the middle of the picture. HUD corners therefore need a narrower selection (e.g. the HUD packet range via `nw_left_hud_packet_lo/hi`, or a HUD-only hook). That is a separate task; until then the HUD stays at its 4:3 position.
- `auto_screen_x` finds no site. Its pattern is `sltiu …,0x140` with an NTSC height of `0xE0`. Kula is PAL and compares registers instead.

## Mac findings on the spike (2026-10-15, `7425c75`)
- **Stable:** smoke and level select pass, 0 FATAL. Fit to window works: the guest width follows the window (428 px at 16:9, 758 px at about 3:1).
- **The user's verdict: "not there yet, real artefacts".**
  - **Sky gaps** are worse than seen on Linux. At about 3:1 everything beyond roughly 1.7x the 4:3 width is black. The sky tiles the game generates cover only about 1.7x of 320 px.
  - **World geometry** ends hard at a fixed screen X, or sky shards are drawn over it (platforms, walls). This is the same `screenOffsetX` culling, and it hits the level as well, not only the sky.
  - **Foreign-coloured sky shards** (desert orange inside a blue sky) appear at the edge. Cause unknown, probably the same culling.
  - **HUD** stays in the 4:3 centre and looks lost at wide aspects.
- `gpu_state.ws.configured/active` read 0 in every scene, while `game_mode` is 1 and `present_native_43` is 0. To be clarified before the real mod (possibly fields of the older projection path).
- 2D screens (warning screen, memory card) show 4:3 with side bars: ok. Open: FMV, launcher toggle, fps.

Consequences for the design:
- The culling fix must cover all users listed below, not only the sky.
- The sky is authored for about 1.7x the 4:3 width (`RecalcSkyboxes01/2` generate the tiles). Beyond that only black is left, unless the generation is widened. **Cap the aspect until that is solved.** About 2:1 is safe (1.7 × 4/3 ≈ 2.27:1), so 16:9 and 2:1 are fine and 21:9 (2.33:1) already sits at the limit. This changes the user's "no upper limit" decision and needs the user's confirmation.

## Why the edges are culled
- The game rejects screen points against the RAM variables `screenOffsetX` (0x800A2E80, 320) and `screenOffsetY` (0x800A2E84, 256), with an unsigned test: `andi x, sxy, 0xffff; sltu at, x, a1; beq at, zero, outside`. That rejects both x < 0 and x >= 320.
- Users of the bound (EU addresses):
  - **Culling:** `ProcessAndRenderParticles`, `DrawLensFlares`, `SubdivideLevelGeometryPolys`, `DrawLasers`, `RenderDispList`, `RenderBonusBackgroundPart1`, `RenderNonSpecialBackground` (sky), `RenderStarfield`, `RenderLevelGeometryQuads`.
  - **Setup only:** `SetupDisplay`, `InitScreenFadePolys`.

## Architecture
- **Plugin** `mods/src/kula_widescreen.c`, activation callback:
  - `psx_mod_set_fixed_display_aspect(16, 9)`, which shapes the first window.
  - `psx_mod_set_adaptive_display_aspect(0, 0)`, which makes the view follow the window from 4:3 with no cap.
- **Manifest** `mods/preloaded/packages/kula.widescreen/1.0.0/manifest.toml`: feature `widescreen`, group "Graphics", `default_enabled = true`.
- **`game.toml`** `[widescreen]` (all of it is inert while the mod is off, i.e. at 4:3):
  - `gte_game_mode = true` (runtime only)
  - `nw_hud_corners = true` (runtime only)
  - `[widescreen.cull] branch_keep_sites`: the x-reject branches (`beq at, zero, …` right after the `sltu` against the x bound) in the culling functions above. While widened, they are not taken, so geometry in the revealed bands is drawn and the GPU clips at the wide surface. The y tests stay untouched.
  - This needs `task generate`. A listed address that does not hold the expected instruction is a hard build error, which guards against wrong sites.
- **CMake:** add the plugin to `target_sources`, like the level select mod.

Site discovery is a small script (`tools/find_ws_cull_sites.py`). It scans the EXE for the `andi …,0xffff` / `sltu at, x, <reg loaded from screenOffsetX>` / `beq at, zero` shape and prints the branch addresses. Its output is checked by hand against each function before it goes into `game.toml`. The script reads the user's own EXE, so no game bytes are committed, only addresses.

## Out of scope
- 60 fps (parked), HD textures.
- Changing the game's own 4:3 2D screens: the warning screen, FMV and memory card screens keep the framework's 4:3 pillarbox.

## Risks
- **Unclear branch targets:** a kept branch may lead into a clip/subdivide path instead of a plain reject. If so, an object in the band can look wrong instead of missing. Check each function with screenshots in the band.
- **Cost:** more primitives at wide aspects (sky tiles, particles). Measure fps on the Mac.
- **Very wide windows** (21:9 and up): the sky or level may simply end, because the game never authored coverage there. In that case cap the aspect in the plugin (fallback `psx_mod_set_adaptive_display_aspect(21, 9)`).
- **Licence:** only addresses and names are facts from the decomp. The release checklist covers asking dezgeg.

## Testing
- **Linux (Xvfb), `build-dev`, OpenBIOS:**
  - Screenshots at 16:9 and 21:9 of the menu, the demo and several worlds (sky and edge bands while turning).
  - A/B against the spike state, to confirm the gaps are gone.
  - `gpu_state.ws` shows `game_mode = 1`, `present_native_43 = 0`.
- **Regression:**
  - mod off → 4:3, `smoke_boot.py` reaches `demo_gameplay_reached`
  - `check_level_select.py` → `level_select_ok`
  - `task test`
- **Mac:** launcher toggle, window resizing (fit to window), fps at 16:9 and 21:9, HUD corners, warning screen and FMV in 4:3, a longer play test.
