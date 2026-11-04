"""Tests for checking an offline pack against runtime dump names (names only)."""

import sys
from dataclasses import replace
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.names import TextureKey
from hd.verify_pack import coverage, dump_key

FULL = TextureKey(8, False, 0x39AD3C3DA790BFE9, 0x07918AAE3CF149C6, 384, 256)
DUMP_SUBRECT = (
    "texupload-P8-39AD3C3DA790BFE9-07918AAE3CF149C6-384x256-52-0-436x16-P0-255.png"
)


class VerifyPackTest(unittest.TestCase):
    def test_dump_key_ignores_dump_rect(self) -> None:
        self.assertEqual(dump_key(DUMP_SUBRECT), FULL)

    def test_dump_key_skips_reduced_range(self) -> None:
        self.assertIsNone(dump_key(DUMP_SUBRECT.replace("P0-255", "P159-255")))

    def test_coverage_ignores_dump_rect(self) -> None:
        covered, _, _ = coverage({FULL}, {dump_key(DUMP_SUBRECT)})
        self.assertEqual(covered, {FULL})

    def test_coverage_reports_missing(self) -> None:
        other = TextureKey(4, True, 1, 2, 8, 32)
        _, _, missing = coverage({FULL}, {FULL, other})
        self.assertEqual(missing, {other})

    def test_coverage_counts_st_draw_without_st_file_as_fallback(self) -> None:
        # The runtime uses the plain file for an ST draw when no ST file exists.
        semi = replace(FULL, semi=True)
        _, fallback, _ = coverage({FULL}, {semi})
        self.assertEqual(fallback, {semi})


if __name__ == "__main__":
    unittest.main()
