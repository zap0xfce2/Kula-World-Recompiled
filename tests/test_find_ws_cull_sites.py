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
        words = [
            lui(V1, 0x000A),
            lw(V1, V1, 0x2E84),
            sltu(AT, V0, V1),
            beq(AT, ZERO, 8),
        ]
        self.assertEqual(find_reject_branches(words, BASE), SiteScan([], [], []))

    def test_overwritten_bound_is_forgotten(self) -> None:
        words = BOUND_DIRECT + [addiu(A0, ZERO, 5), sltu(AT, V0, A0), beq(AT, ZERO, 8)]
        self.assertEqual(find_reject_branches(words, BASE).reject, [])

    def test_branch_far_from_compare_is_ignored(self) -> None:
        words = BOUND_DIRECT + [sltu(AT, V0, A0), NOP, NOP, NOP, beq(AT, ZERO, 8)]
        self.assertEqual(find_reject_branches(words, BASE).reject, [])

    def test_bound_load_is_recorded_as_load_site(self) -> None:
        words = BOUND_VIA_POINTER + [sltu(AT, V0, A0), beq(AT, ZERO, 8)]
        self.assertEqual(find_reject_branches(words, BASE).loads, [BASE + 8])

    def test_seeded_bound_register_is_recognised(self) -> None:
        words = [sltu(AT, V0, A0), beq(AT, ZERO, 8), NOP]
        scan = find_reject_branches(words, BASE, seed_bound=frozenset({A0}))
        self.assertEqual(scan.reject, [BASE + 4])


class ScanExeTest(unittest.TestCase):
    def test_rejects_wrong_exe_size(self) -> None:
        with self.assertRaises(ValueError):
            scan_exe(bytes(EXE_SIZE - 4))


if __name__ == "__main__":
    unittest.main()
