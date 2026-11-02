"""Tests for HD pack file names and hashes (synthetic values only)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.names import TextureKey, format_name, hash_words, parse_name


class NamesTest(unittest.TestCase):
    def test_format_name_matches_runtime_format(self) -> None:
        key = TextureKey(
            depth=8,
            semi=False,
            source_hash=0x39AD3C3DA790BFE9,
            palette_hash=0x07918AAE3CF149C6,
            width_words=384,
            height=256,
        )
        self.assertEqual(
            format_name(key),
            "texupload-P8-39AD3C3DA790BFE9-07918AAE3CF149C6-384x256-0-0-768x256-P0-255",
        )

    def test_format_name_st_p4(self) -> None:
        key = TextureKey(4, True, 1, 2, 8, 32)
        self.assertEqual(
            format_name(key),
            "texupload-STP4-0000000000000001-0000000000000002-8x32-0-0-32x32-P0-15",
        )

    def test_parse_name_round_trip(self) -> None:
        key = TextureKey(4, True, 1, 2, 8, 32)
        self.assertEqual(parse_name(format_name(key) + ".png"), key)

    def test_parse_name_rejects_reduced_range(self) -> None:
        name = "texupload-P8-0000000000000001-0000000000000002-4x4-0-0-8x4-P3-255.png"
        self.assertIsNone(parse_name(name))

    def test_hash_words_is_xxh3(self) -> None:
        self.assertEqual(hash_words(b""), 0x2D06800538D394C2)


if __name__ == "__main__":
    unittest.main()
