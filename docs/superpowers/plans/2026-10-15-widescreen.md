# Widescreen Mod Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A launcher mod `kula.widescreen` (on by default) shows Kula World wider than 4:3, following the window up to 2:1, without the edge culling the spike showed.

**Architecture:**
- A trusted static plugin selects psxrecomp's native-wide view: 16:9 for the first window, then fit to window, capped at 2:1.
- `game.toml [widescreen]` enables the 3D gameplay detector.
- `[widescreen.cull] branch_keep_sites` forces the game's screen-X reject branches (`beq` after the compare against `screenOffsetX`) not taken while widened.
- The site list comes from a small finder script that scans the user's own EXE, so only addresses are committed.

**Tech Stack:** C (psxrecomp trusted plugin API `mod_plugins.h`), TOML config, Python 3.11+ (finder, unittest, ruff, black), go-task, Xvfb + debug server for verification.

**Spec:** `docs/superpowers/specs/2026-10-15-widescreen-design.md`

## Global Constraints
- Mod `kula.widescreen`, feature `widescreen`, group "Graphics", `default_enabled = true`, `format_version = 7`, `game_id = "SCES-01000"`.
- View: `psx_mod_set_fixed_display_aspect(16, 9)` for the first window, then fit to window, **capped at 2:1** (approved by the user on 2026-10-15). The spec gives the reason: the sky is only generated for about 1.7x the 4:3 width.
- Never commit game data: no instruction words, no bytes from the EXE. `game.toml` gets addresses only. The finder reads `disc/SCES_010.00` at run time (`python3 -I`).
- Never hand-edit generated code. Config change → `task generate`.
- No printf debugging. Use the debug server (`gpu_state`, `screenshot`, `ws_aspect`).
- Python: type hints, no `Any`, ruff + black, one assert per test.
- Code addresses in KUSEG form (`0x000xxxxx`) like the existing `mod_function_entry_funcs`.

## Review Focus
1. **A kept branch that guards more than X:** if a listed `beq` also skips a y or z test, polygons above/below or behind the camera get drawn. Expect no new artefacts at the top/bottom edges and none when the camera turns. The Task 2 screenshots cover top and bottom while turning.
2. **The mod off has to give exactly 4:3:** the sites must be identity at `x_margin = 0`. Covered by `smoke_boot` with the mod disabled and the Demo timer end value of 3603 (Task 3).
3. **Window narrower than 16:9 or at the 2:1 cap:** the view must not stretch, and the black side bars appear only beyond 2:1. Mac check (Task 3).
4. **The finder on a different EXE** (wrong region or modified): it must refuse instead of printing garbage. Unit test `test_rejects_wrong_exe_size` (Task 1).
5. **Particles** (only `bne` sites): they can still vanish at the wide edges. This is a known limitation, documented as a ruling, not a bug.

## Rulings in this plan
- `ProcessAndRenderParticles` only has `bne` (keep) branches. `branch_keep_sites` can only force a branch *not taken*, and forcing a compare result (`[[widescreen.cull.keep]]`) needs the instruction word in `game.toml`, which is original game bytes. → Particles stay vanilla (they may pop at the wide edges).
- HUD in the wide corners: `nw_hud_corners` also moves sky sprites (spec). It is not part of this plan and stays a follow-up. The HUD stays at its 4:3 position.
- `[widescreen] auto_ui_squash/auto_ui_anchor` from the spike are dropped: according to `psxrecomp/docs/WIDESCREEN.md` they act only on the projection path, and native-wide does not squash the HUD.
- `gpu_state.ws.configured/active = 0` is expected. Both report the GTE squash of the projection path (`gpu.c:251` `ws_configured() = ws_xnum != ws_xden`). Native-wide shows up in `mode = 2`, `x_margin`, `game_mode`, `present_native_43`.

---

### Task 1: Cull-site finder

**Files:**
- Create: `tools/find_ws_cull_sites.py`
- Create: `tests/test_find_ws_cull_sites.py`
- Modify: `Taskfile.yaml` (lint lists)

**Interfaces:**
- Produces:
  - `find_reject_branches(words: Sequence[int], base: int) -> SiteScan`
  - `SiteScan(reject: list[int], keep: list[int])` (frozen dataclass)
  - `scan_exe(exe: bytes) -> dict[str, SiteScan]`
  - CLI `python3 -I tools/find_ws_cull_sites.py disc/SCES_010.00` prints the TOML lines for `branch_keep_sites`.

- [ ] **Step 1: Write the failing tests**

`tests/test_find_ws_cull_sites.py`. The words are synthetic, built by encoders in the test, never taken from the game:
```python
"""Tests for the widescreen cull-site finder (synthetic MIPS words only)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from find_ws_cull_sites import EXE_SIZE, SiteScan, find_reject_branches, scan_exe

A0, V0, V1, AT, ZERO = 4, 2, 3, 1, 0
BASE = 0x00050000


def lui(rt: int, imm: int) -> int:
    return (0x0F << 26) | (rt << 16) | imm


def addiu(rt: int, rs: int, imm: int) -> int:
    return (0x09 << 26) | (rs << 21) | (rt << 16) | imm


def lw(rt: int, rs: int, imm: int) -> int:
    return (0x23 << 26) | (rs << 21) | (rt << 16) | imm


def sltu(rd: int, rs: int, rt: int) -> int:
    return (rs << 21) | (rt << 16) | (rd << 11) | 0x2B


def beq(rs: int, rt: int, off: int) -> int:
    return (0x04 << 26) | (rs << 21) | (rt << 16) | (off & 0xFFFF)


def bne(rs: int, rt: int, off: int) -> int:
    return (0x05 << 26) | (rs << 21) | (rt << 16) | (off & 0xFFFF)


NOP = 0
BOUND_VIA_POINTER = [lui(A0, 0x000A), addiu(A0, A0, 0x2E80), lw(A0, A0, 0)]
BOUND_DIRECT = [lui(A0, 0x000A), lw(A0, A0, 0x2E80)]


class FindRejectBranchesTest(unittest.TestCase):
    def test_beq_after_x_compare_is_reject_site(self) -> None:
        words = BOUND_VIA_POINTER + [sltu(AT, V0, A0), beq(AT, ZERO, 8), NOP]
        self.assertEqual(find_reject_branches(words, BASE).reject, [BASE + 16])

    def test_direct_load_is_recognised(self) -> None:
        words = BOUND_DIRECT + [sltu(AT, V0, A0), beq(AT, ZERO, 8), NOP]
        self.assertEqual(find_reject_branches(words, BASE).reject, [BASE + 12])

    def test_bne_after_x_compare_is_keep_site(self) -> None:
        words = BOUND_VIA_POINTER + [sltu(AT, V0, A0), bne(AT, ZERO, 8), NOP]
        self.assertEqual(find_reject_branches(words, BASE).keep, [BASE + 16])

    def test_compare_against_y_bound_is_ignored(self) -> None:
        words = [lui(V1, 0x000A), lw(V1, V1, 0x2E84), sltu(AT, V0, V1), beq(AT, ZERO, 8)]
        self.assertEqual(find_reject_branches(words, BASE), SiteScan([], []))

    def test_overwritten_bound_is_forgotten(self) -> None:
        words = BOUND_DIRECT + [addiu(A0, ZERO, 5), sltu(AT, V0, A0), beq(AT, ZERO, 8)]
        self.assertEqual(find_reject_branches(words, BASE).reject, [])

    def test_branch_far_from_compare_is_ignored(self) -> None:
        words = BOUND_DIRECT + [sltu(AT, V0, A0), NOP, NOP, NOP, beq(AT, ZERO, 8)]
        self.assertEqual(find_reject_branches(words, BASE).reject, [])


class ScanExeTest(unittest.TestCase):
    def test_rejects_wrong_exe_size(self) -> None:
        with self.assertRaises(ValueError):
            scan_exe(bytes(EXE_SIZE - 4))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_find_ws_cull_sites -v`
Expected: ERROR `ModuleNotFoundError: No module named 'find_ws_cull_sites'`

- [ ] **Step 3: Write the implementation**

`tools/find_ws_cull_sites.py`:
```python
#!/usr/bin/env python3
"""List Kula World's screen-X reject branches for [widescreen.cull] branch_keep_sites.

The game rejects screen points with `slt/sltu at, x, W` + `beq at, zero, reject`,
where W was loaded from screenOffsetX (0x800A2E80). Only addresses are printed,
so nothing of the game's code ends up in the repo.
Usage: python3 -I tools/find_ws_cull_sites.py disc/SCES_010.00
"""

import struct
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

EXE_HEADER = 0x800
LOAD_ADDRESS = 0x00011000
EXE_SIZE = 0x93800  # header + text_size from game.toml; guards against other regions
SCREEN_OFFSET_X_HI = 0x000A
SCREEN_OFFSET_X_LO = 0x2E80
MAX_BRANCH_DISTANCE = 12  # bytes between the compare and its branch (delay-slot scheduling)

# Renderers that cull against screenOffsetX (EU addresses, dezgeg/kula-world-decomp).
CULL_FUNCTIONS: tuple[tuple[str, int, int], ...] = (
    ("ProcessAndRenderParticles", 0x00012918, 0x000139C8),
    ("DrawLensFlares", 0x00015B54, 0x000164DC),
    ("SubdivideLevelGeometryPolys", 0x0005054C, 0x00050790),
    ("DrawLasers", 0x00052504, 0x00052AB8),
    ("RenderDispList", 0x00053DF8, 0x00055A0C),
    ("RenderBonusBackgroundPart1", 0x00055A0C, 0x000563C4),
    ("RenderNonSpecialBackground", 0x000563C4, 0x00056D7C),
    ("RenderStarfield", 0x00056F48, 0x00057374),
    ("RenderLevelGeometryQuads", 0x00057374, 0x00057834),
)

OP_SPECIAL, OP_BEQ, OP_BNE, OP_ADDIU, OP_LUI, OP_LW = 0x00, 0x04, 0x05, 0x09, 0x0F, 0x23
FN_SLT, FN_SLTU = 0x2A, 0x2B
# SPECIAL functions without a destination register (jr, jalr link aside, syscall, mult/div).
FN_NO_DEST = frozenset({0x08, 0x0C, 0x0D, 0x18, 0x19, 0x1A, 0x1B})
OPS_WRITING_RT = frozenset(range(0x08, 0x10)) | frozenset(range(0x20, 0x27))


@dataclass(frozen=True)
class SiteScan:
    reject: list[int] = field(default_factory=list)  # beq at,zero after an x compare
    keep: list[int] = field(default_factory=list)  # bne at,zero: cannot be kept by address


@dataclass
class _Regs:
    upper: set[int] = field(default_factory=set)  # hold lui 0x000A
    pointer: set[int] = field(default_factory=set)  # hold &screenOffsetX
    bound: set[int] = field(default_factory=set)  # hold screenOffsetX
    compare_pc: dict[int, int] = field(default_factory=dict)  # x-compare result -> pc

    def forget(self, reg: int) -> None:
        for regs in (self.upper, self.pointer, self.bound):
            regs.discard(reg)
        self.compare_pc.pop(reg, None)


def _fields(word: int) -> tuple[int, int, int, int, int, int]:
    return word >> 26, (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31, word & 0xFFFF, word & 63


def _destination(op: int, rt: int, rd: int, fn: int) -> int | None:
    if op == OP_SPECIAL:
        return None if fn in FN_NO_DEST else rd
    return rt if op in OPS_WRITING_RT else None


def _track_bound(regs: _Regs, op: int, rs: int, rt: int, imm: int) -> bool:
    """Follow lui/addiu/lw towards screenOffsetX; True when the word was consumed."""
    if op == OP_LUI and imm == SCREEN_OFFSET_X_HI:
        regs.forget(rt)
        regs.upper.add(rt)
        return True
    if op == OP_ADDIU and rs in regs.upper and imm == SCREEN_OFFSET_X_LO:
        regs.forget(rt)
        regs.pointer.add(rt)
        return True
    loads_bound = (rs in regs.pointer and imm == 0) or (rs in regs.upper and imm == SCREEN_OFFSET_X_LO)
    if op == OP_LW and loads_bound:
        regs.forget(rt)
        regs.bound.add(rt)
        return True
    return False


def _branch_after_compare(regs: _Regs, op: int, rs: int, rt: int, pc: int, scan: SiteScan) -> bool:
    if op not in (OP_BEQ, OP_BNE) or rt != 0 or rs not in regs.compare_pc:
        return False
    if pc - regs.compare_pc[rs] > MAX_BRANCH_DISTANCE:
        return False
    (scan.reject if op == OP_BEQ else scan.keep).append(pc)
    return True


def find_reject_branches(words: Sequence[int], base: int) -> SiteScan:
    """Linear scan of one function; renderers keep the bound in a register across loops."""
    regs, scan = _Regs(), SiteScan()
    for index, word in enumerate(words):
        pc = base + index * 4
        op, rs, rt, rd, imm, fn = _fields(word)
        if _track_bound(regs, op, rs, rt, imm) or _branch_after_compare(regs, op, rs, rt, pc, scan):
            continue
        dest = _destination(op, rt, rd, fn)
        if dest:
            regs.forget(dest)
        if op == OP_SPECIAL and fn in (FN_SLT, FN_SLTU) and rt in regs.bound and rd:
            regs.compare_pc[rd] = pc
    return scan


def scan_exe(exe: bytes) -> dict[str, SiteScan]:
    if len(exe) != EXE_SIZE:
        raise ValueError(f"unexpected EXE size {len(exe):#x}, expected {EXE_SIZE:#x} (EU SCES_010.00)")
    result: dict[str, SiteScan] = {}
    for name, start, end in CULL_FUNCTIONS:
        offset = EXE_HEADER + start - LOAD_ADDRESS
        words = struct.unpack_from(f"<{(end - start) // 4}I", exe, offset)
        result[name] = find_reject_branches(words, start)
    return result


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    scans = scan_exe(Path(sys.argv[1]).read_bytes())
    print("branch_keep_sites = [")
    for name, scan in scans.items():
        if scan.reject:
            sites = ", ".join(f'"0x{pc:08X}"' for pc in scan.reject)
            print(f"    # {name}\n    {sites},")
    print("]")
    for name, scan in scans.items():
        if scan.keep and not scan.reject:
            print(f"# {name}: only keep-branches ({len(scan.keep)}), left vanilla", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
Before the step is done, check `EXE_SIZE` against `stat -c %s disc/SCES_010.00`. If it differs, adapt the constant (it is a size, not a game byte) and note the measured value in the commit message.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_find_ws_cull_sites -v`
Expected: 7 tests OK

- [ ] **Step 5: Run against the real EXE**

Run: `python3 -I tools/find_ws_cull_sites.py disc/SCES_010.00`
Expected:
- 47 reject sites across DrawLensFlares (2), DrawLasers (1), RenderDispList (12), RenderBonusBackgroundPart1 (14), RenderNonSpecialBackground (14), RenderStarfield (3), RenderLevelGeometryQuads (1)
- stderr: "ProcessAndRenderParticles: only keep-branches (4), left vanilla"

These are the prototype numbers from 2026-10-15. Look at three sites by hand with `python3 -I tools/mips.py disc/SCES_010.00 0x11000 <addr-8> 4`, e.g. one in RenderDispList, one in the sky, one in LevelGeometryQuads: `sltu/slt` against the x-bound register, then `beq …, zero`.

- [ ] **Step 6: Lint and commit**

In `Taskfile.yaml`, add `tools/find_ws_cull_sites.py` to `ruff check` and `black --check` under `lint`.
Run: `go-task lint && go-task test`
Expected: everything green.
```bash
git add tools/find_ws_cull_sites.py tests/test_find_ws_cull_sites.py Taskfile.yaml
git commit -m "feat(widescreen): finder for screen-x reject branches"
```

---

### Task 2: Mod `kula.widescreen` with cull sites

**Files:**
- Create: `mods/src/kula_widescreen.c`
- Create: `mods/preloaded/packages/kula.widescreen/1.0.0/manifest.toml`
- Modify: `CMakeLists.txt` (`target_sources`, next to `kula_level_select.c`)
- Modify: `game.toml` (`[widescreen]`, `[widescreen.cull]`)

**Interfaces:**
- Consumes: the output of `tools/find_ws_cull_sites.py` (Task 1).
- Produces: feature `kula.widescreen/widescreen`, which the Mac test and the docs refer to.

- [ ] **Step 1: Plugin**

`mods/src/kula_widescreen.c`:
```c
/* Kula World widescreen: selects psxrecomp's native-wide view. 16:9 shapes the
 * first window, then the view follows the window up to 2:1, the widest the
 * game's generated sky covers (about 1.7x the 4:3 width). */
#include "mod_plugins.h"

#define PLUGIN_ID "kula.widescreen"

enum { FIRST_WINDOW_NUM = 16, FIRST_WINDOW_DEN = 9, MAX_ASPECT_NUM = 2, MAX_ASPECT_DEN = 1 };

static void on_activate(void) {
    (void)psx_mod_set_fixed_display_aspect(FIRST_WINDOW_NUM, FIRST_WINDOW_DEN);
    (void)psx_mod_set_adaptive_display_aspect(MAX_ASPECT_NUM, MAX_ASPECT_DEN);
}

PSX_MOD_CONSTRUCTOR(register_kula_widescreen) {
    (void)psx_mod_register_activation_plugin(PLUGIN_ID, on_activate);
}
```

- [ ] **Step 2: Manifest**

`mods/preloaded/packages/kula.widescreen/1.0.0/manifest.toml`:
```toml
format_version = 7
id = "kula.widescreen"
version = "1.0.0"
name = "Widescreen"
author = "Kula World Recompiled"
description = "Shows the world wider than 4:3, following the window up to 2:1."
resolver = "declarative"
save_compatibility = "shared"

[[target]]
game_id = "SCES-01000"

[[feature]]
id = "widescreen"
name = "Widescreen"
description = "Wider view of the world, following the window up to 2:1. Menus and the warning screen stay 4:3."
group = "Graphics"
default_enabled = true

[[plugin]]
feature = "widescreen"
id = "kula.widescreen"
```

- [ ] **Step 3: CMake and game.toml**

In `CMakeLists.txt`, extend `target_sources(psx-runtime PRIVATE …)` with `"${CMAKE_CURRENT_SOURCE_DIR}/mods/src/kula_widescreen.c"`.

Append to `game.toml`. Paste the site list 1:1 from the Task 1 output:
```toml
# Widescreen mod (mods/src/kula_widescreen.c). Inert at 4:3 (x_margin 0).
[widescreen]
# Fully 3D, no sprite-tag helper: classify gameplay by GTE activity.
gte_game_mode = true

[widescreen.cull]
# Screen-X reject branches (beq after the compare against screenOffsetX),
# found by tools/find_ws_cull_sites.py. Not taken while widened.
branch_keep_sites = [
    # output of tools/find_ws_cull_sites.py, unchanged
]
```

- [ ] **Step 4: Generate and build**

Run: `go-task generate && go-task build:dev`
Expected:
- the generate log contains no `branch_keep` error (a wrong address would be a hard error that names the site)
- the build is clean

- [ ] **Step 5: Screenshots at 16:9 and at the cap**

Start runtime A (Xvfb `-screen 0 1920x1080x24`, OpenBIOS, `--debug-port 4370`) and run the spike script `ws_spike.py` / `ws_more.py` (scratchpad) again. Output goes to `analysis/widescreen-mod/{16x9}/`. Then do the same with a wider Xvfb window (`-screen 0 2560x1080x24`) to `analysis/widescreen-mod/wide/`.
Expected:
- **16:9:** sky closed at the edges, platforms and walls are not cut off at a fixed screen X
- **Wide window:** view at most 2:1 (`gpu_state.ws.x_margin` about 80; for comparison the Mac measured 54 at 16:9 = 428 px), black bars only beyond it
- **`gpu_state.ws`:** `mode 2`, `game_mode 1`, `present_native_43 0`
- **Top/bottom edges while turning** (Review Focus 1): no new shards

Compare A/B with `analysis/widescreen-spike/more/` (spike state).

- [ ] **Step 6: Commit**

```bash
git add mods/src/kula_widescreen.c mods/preloaded/packages/kula.widescreen CMakeLists.txt game.toml
git commit -m "feat(widescreen): kula.widescreen mod with screen-x cull sites"
```

---

### Task 3: Regression, docs, Mac

**Files:**
- Modify: `CLAUDE.md` (Mods section Widescreen, gotchas)
- Modify: `docs/BUILD_MACOS.md` (verified table, after the Mac result)
- Modify: `docs/superpowers/specs/2026-10-15-widescreen-design.md` (status, results)

- [ ] **Step 1: Regression on Linux**

- **Mod on:** `python3 tools/smoke_boot.py --port 4370` → `demo_gameplay_reached`. `python3 tools/check_level_select.py --world 3 --level 5` → `level_select_ok`.
- **Mod off** (`build-dev/mods/state.toml`: feature `kula.widescreen/widescreen` `enabled = false`): `smoke_boot.py` → `demo_gameplay_reached`, Demo timer end value 3603, screenshot 320 px wide (Review Focus 2).
- `go-task test && go-task lint` → green.

- [ ] **Step 2: Docs**

In `CLAUDE.md` under Mods/Widescreen:
- Mod name, default on, cap 2:1
- Finder script, and that sites only reach `game.toml` through it (no bytes)
- Particles stay vanilla
- HUD corners are a follow-up
- `ws.configured/active = 0` is expected for native-wide

Set the spec status to "implemented".
```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-15-widescreen-design.md
git commit -m "docs: widescreen mod"
git push -u origin feat/widescreen-mod
```

- [ ] **Step 3: Mac test**

`SendMessage` to `verify-macos-native-build` with branch `feat/widescreen-mod`:
- `generate` without `--bios`, then build and build:dev, then `task test`
- Smoke and Level Select with the mod on
- The user checks:
  - launcher toggle
  - resizing the window from 4:3 to 2:1 and wider (black bars only beyond 2:1)
  - edges in several worlds while turning and tipping
  - lasers, lens flares, starfield in the bonus worlds
  - fps at 16:9 and 2:1
  - FMV in 4:3

- [ ] **Step 4: After a clean Mac result**

- Add a widescreen row to the `docs/BUILD_MACOS.md` verified table.
- Merge to `main` (fast-forward), then delete `feat/widescreen-mod` and `spike/widescreen` locally and remotely.
