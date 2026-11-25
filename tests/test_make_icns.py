"""Tests for the .icns packer (synthetic PNG headers, no image library)."""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from make_icns import PNG_SIGNATURE, build_icns, png_size


def fake_png(width: int, height: int) -> bytes:
    return PNG_SIGNATURE + struct.pack(">I4sII", 13, b"IHDR", width, height) + bytes(5)


class MakeIcnsTest(unittest.TestCase):
    def test_png_size_reads_ihdr(self) -> None:
        self.assertEqual(png_size(fake_png(256, 256)), 256)

    def test_non_square_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            png_size(fake_png(256, 128))

    def test_header_length_covers_file(self) -> None:
        icns = build_icns([fake_png(128, 128), fake_png(1024, 1024)])
        self.assertEqual(struct.unpack(">I", icns[4:8])[0], len(icns))

    def test_1024_goes_to_retina_slot(self) -> None:
        icns = build_icns([fake_png(1024, 1024)])
        self.assertEqual(icns[8:12], b"ic10")

    def test_unknown_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_icns([fake_png(48, 48)])


if __name__ == "__main__":
    unittest.main()
