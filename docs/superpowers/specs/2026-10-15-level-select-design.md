# Level select mod – design

Status: approved by the user on 2026-10-15.

## Goal
Let a single player start the arcade game at any world and level. The original always starts arcade at world 1, level 1. Its only selector is in two-player mode, which picks a world, not a level, and only up to `highestLevelReached`.
Side benefit: late levels and the ending FMV become testable.

## User-facing behaviour
- New launcher mod "Level Select" (`kula.level-select`), group "Quality of Life", on by default (needed for our own late-level and FMV tests). While off, the game is unchanged.
- While on, choosing "Arcade" in the one-player menu opens a submenu instead of starting right away. It works the same way as the time-trial difficulty menu:
  ```
  ARCADE
    > START
      WORLD   < 1 >    1-10, left/right, wraps
      LEVEL   < 1 >    1-15, left/right, wraps
  ```
  - Cross on START starts the arcade game at the chosen world and level.
  - Triangle or Circle goes back to the one-player menu (Circle only in this submenu; the original menus keep Triangle).
  - Up and down move the cursor; every move plays the game's menu sound.
- Look: all text in the game's small font, tinted pale blue instead of white; START centred, WORLD/LEVEL right-aligned to a shared edge with `- n +` centred in a fixed column so the values line up; the selected row at full brightness, the others at half. A glass-digit/menu-cursor variant was tried and rejected by the user (mixed fonts).
- All 10 worlds × 15 levels are selectable at once.
- START with 1/1 behaves exactly like the original arcade start.
- Any other start counts as cheated:
  - The mod sets the game's own `cheated` flag, so the original suppresses save points.
  - The mod also skips the high-score entry at game over.
- The same submenu appears in the variant of the one-player menu shown once the Final world is unlocked (there, arcade is entry 1).

## Facts from the decomp (dezgeg/kula-world-decomp, EU build)
Code identity is KUSEG `0x000xxxxx`. RAM addresses are `0x800xxxxx`. Addresses below are taken from `config/eu-SCES_010.00`.

| Symbol | Address | Use |
|---|---|---|
| `SinglePlayerMenu` | 0x491a8 | hook (arcade = entry 0) |
| `SinglePlayerMenuWhenFinalUnlocked` | 0x496ac | hook (arcade = entry 1) |
| `HighScoreUi` | from config | hook for strict scoring |
| `curLevel` | 0xa2ea0 | |
| `curWorld` | 0xa2ea4 | |
| `curWorld2` | 0xa2ea8 | |
| `loadNewWorld` | 0xa2eac | |
| `skipNextLoad` | 0xa2eb0 | |
| `gameState` | 0xa2ec0 | |
| `gameMode` | 0xa2e48 | |
| `isFinal` | 0xa2edc | |
| `cheated` | 0xa4e0c | |
| `curMenu` | 0xa3354 | |
| `cursorPosInMenu` | 0xa4f20 | |
| `controllerButtons` | 0xa5530 | |
| `prevControllerButtons` | 0xa50bc | |
| `scoreText` | 0xa4ab0 | 128-byte guest string buffer |

How the original behaves:
- **Starting arcade loads nothing.** The menu runs over the already loaded world 0, level 0. Arcade only unpauses it: `gameState++`, `gameMode = 0`, `cheated = 0`, and so on.
- **Reloading somewhere else** means setting `curWorld` and `curLevel`, plus `loadNewWorld = 1` and `skipNextLoad = (curWorld == curWorld2)`. The game's own "Load Game" path does exactly this (menu.c:545-560).
- **Button test:** `TestButton(b)` is `controllerButtons & ~prevControllerButtons & b`.

Text drawing:
- Letters (A-Z, 0-9): `SetTextParams(x, y, align, r, g, b)` followed by `DrawTextCrappyFont(str)`.
- Digits only: `DrawTextFancyFont(str, x, y)`.
- Menu panels: `DrawWidgets(menuId, cursor)`.

Ordering detail: `HighScoreUi(1)` runs at game over regardless of `cheated` (main.c:838).

## Architecture
The mod is a trusted static plugin, linked into the runtime, as provided by psxrecomp (`docs/MOD_PACKAGES.md`, "Trusted static plugins"). It does not touch generated code.

**Files:**
- `mods/preloaded/packages/kula.level-select/1.0.0/manifest.toml`
  - `format_version = 7`, one feature `level-select`, `[[plugin]] id = "kula.level-select"`
  - Staged by the existing `PRELOADED_MODS_DIR`.
- `mods/src/level_select_logic.{c,h}`: pure logic with no guest access. It covers the submenu state, cursor movement, world/level wrap and the strict decision. Unit-tested.
- `mods/src/kula_level_select.c`: the glue to `runtime/include/mod_plugins.h`.
  - **Function filter** (`psx_mod_register_function_filter_plugin`) on both one-player menu functions:
    - **Idle:** Cross on the arcade entry is consumed, and the submenu opens.
    - **Submenu:** the original body is skipped. The mod reads the pad, updates the logic and draws through guest calls (`psx_mod_call_guest`), writing strings into `scoreText`.
    - **Confirm:** the mod calls the original body with the cursor on arcade, so the real start path runs. It then writes `curWorld`/`curLevel`/`loadNewWorld`/`skipNextLoad`. When the start is not 1/1, it also sets `cheated = 1` and arms "strict".
  - **Function filter on `HighScoreUi`:** while strict is armed, the entry is skipped. The return contract is checked against the decomp first.
  - **VBlank callback:** clears submenu and strict once the game is back in the main menu (`gameState == 0` and `curMenu != 3`).
- `game.toml`, `[recompiler]`: the hooked function addresses go into the key that enables entry/filter hooks (`mod_function_entry_funcs`, to be confirmed in `psxrecomp/recompiler/src/config_loader.h`). Then regenerate.
- `CMakeLists.txt`: add the two C files to the runtime target via `target_sources`.

## Error handling
- Out-of-range values cannot occur: the logic clamps and wraps on every input.
- If a hook address does not match the build (wrong config), psxrecomp refuses to resolve the enabled plugin and fails before launch. Nothing is silently skipped.
- With the mod disabled, no hook is active (psxrecomp only activates plugins of enabled features).

## Testing
- **Unit test for the pure logic:**
  - cursor wrap
  - world 1-10 and level 1-15 wrap
  - strict only when the start is not 1/1
  - back/confirm transitions

  It runs in `task test`.
- **Integration on Linux** (`build-dev`, OpenBIOS, debug server), with a script `tools/check_level_select.py`:
  - **Chosen start:** navigate to world 7, level 3 and start. Expect `curWorld == 6`, `curLevel == 2`, `cheated == 1`, a running timer, and screenshots of the submenu and the level.
  - **Default start:** START without changes gives `curWorld == 0`, `curLevel == 0`, `cheated == 0`.
  - **Mod disabled** via `<build>/mods/state.toml`: original menu, `smoke_boot.py` reaches the demo.
- **Strict scoring:** after a chosen start, reach game over and check that no high-score entry appears.
- **macOS test station:** visual check of the submenu, the launcher toggle, and the final world / ending FMV.

## Risks
- `psx_mod_call_guest` plus drawing from a filter is untested in this project. A spike verifies it first, using a screenshot.
- Whether skipping `HighScoreUi` is clean depends on its return contract and on what the caller does afterwards. This is checked before implementing.
- Licence: addresses and names are single facts from an unlicensed decomp. The mod code is our own. This is covered by the release checklist (ask dezgeg before going public).
