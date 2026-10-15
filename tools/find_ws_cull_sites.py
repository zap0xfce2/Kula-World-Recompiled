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
MAX_BRANCH_DISTANCE = (
    12  # bytes between the compare and its branch (delay-slot scheduling)
)

REG_A3 = 7
NO_SEED: frozenset[int] = frozenset()

# Renderers that cull against screenOffsetX (EU addresses, dezgeg/kula-world-decomp),
# with the registers that already hold the bound on entry.
CULL_FUNCTIONS: tuple[tuple[str, int, int, frozenset[int]], ...] = (
    ("ProcessAndRenderParticles", 0x00012918, 0x000139C8, NO_SEED),
    ("DrawLensFlares", 0x00015B54, 0x000164DC, NO_SEED),
    # SubdivideLevelGeometryPolys loads the bound into a3 and branches here.
    ("DoSubdivide", 0x00050790, 0x00051964, frozenset({REG_A3})),
    ("DrawLasers", 0x00052504, 0x00052AB8, NO_SEED),
    ("RenderDispList", 0x00053DF8, 0x00055A0C, NO_SEED),
    ("RenderBonusBackgroundPart1", 0x00055A0C, 0x000563C4, NO_SEED),
    ("RenderNonSpecialBackground", 0x000563C4, 0x00056D7C, NO_SEED),
    ("RenderStarfield", 0x00056F48, 0x00057374, NO_SEED),
    ("RenderLevelGeometryQuads", 0x00057374, 0x00057834, NO_SEED),
)

OP_SPECIAL, OP_BEQ, OP_BNE, OP_ADDIU, OP_LUI, OP_LW = 0x00, 0x04, 0x05, 0x09, 0x0F, 0x23
FN_SLT, FN_SLTU = 0x2A, 0x2B
# SPECIAL functions without a destination register (jr, jalr link aside, syscall, mult/div).
FN_NO_DEST = frozenset({0x08, 0x0C, 0x0D, 0x18, 0x19, 0x1A, 0x1B})
OPS_WRITING_RT = frozenset(range(0x08, 0x10)) | frozenset(range(0x20, 0x27))


@dataclass(frozen=True)
class SiteScan:
    reject: list[int] = field(default_factory=list)  # beq at,zero after an x compare
    keep: list[int] = field(
        default_factory=list
    )  # bne at,zero: cannot be kept by address


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
    return (
        word >> 26,
        (word >> 21) & 31,
        (word >> 16) & 31,
        (word >> 11) & 31,
        word & 0xFFFF,
        word & 63,
    )


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
    loads_bound = (rs in regs.pointer and imm == 0) or (
        rs in regs.upper and imm == SCREEN_OFFSET_X_LO
    )
    if op == OP_LW and loads_bound:
        regs.forget(rt)
        regs.bound.add(rt)
        return True
    return False


def _branch_after_compare(
    regs: _Regs, op: int, rs: int, rt: int, pc: int, scan: SiteScan
) -> bool:
    if op not in (OP_BEQ, OP_BNE) or rt != 0 or rs not in regs.compare_pc:
        return False
    if pc - regs.compare_pc[rs] > MAX_BRANCH_DISTANCE:
        return False
    (scan.reject if op == OP_BEQ else scan.keep).append(pc)
    return True


def find_reject_branches(
    words: Sequence[int], base: int, seed_bound: frozenset[int] = NO_SEED
) -> SiteScan:
    """Linear scan of one function; renderers keep the bound in a register across loops."""
    regs, scan = _Regs(bound=set(seed_bound)), SiteScan()
    for index, word in enumerate(words):
        pc = base + index * 4
        op, rs, rt, rd, imm, fn = _fields(word)
        if _track_bound(regs, op, rs, rt, imm) or _branch_after_compare(
            regs, op, rs, rt, pc, scan
        ):
            continue
        dest = _destination(op, rt, rd, fn)
        if dest:
            regs.forget(dest)
        if op == OP_SPECIAL and fn in (FN_SLT, FN_SLTU) and rt in regs.bound and rd:
            regs.compare_pc[rd] = pc
    return scan


def scan_exe(exe: bytes) -> dict[str, SiteScan]:
    if len(exe) != EXE_SIZE:
        raise ValueError(
            f"unexpected EXE size {len(exe):#x}, expected {EXE_SIZE:#x} (EU SCES_010.00)"
        )
    result: dict[str, SiteScan] = {}
    for name, start, end, seed in CULL_FUNCTIONS:
        offset = EXE_HEADER + start - LOAD_ADDRESS
        words = struct.unpack_from(f"<{(end - start) // 4}I", exe, offset)
        result[name] = find_reject_branches(words, start, seed)
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
        if not scan.reject:
            note = (
                f"only keep-branches ({len(scan.keep)})"
                if scan.keep
                else "no sites found"
            )
            print(f"# {name}: {note}, left vanilla", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
