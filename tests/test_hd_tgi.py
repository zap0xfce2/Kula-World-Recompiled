"""Tests for the TGI reader (synthetic files built with struct only)."""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.tgi import read_bonus_sky, read_sky

HEADER_SIZE = 0x190
SECTION_LENGTHS_OFFSET = 0x164
SKY_QUADS = 1152
SKY_CLUTS = 24
SKY_WORDS = 384 * 256
SKYBOX_BYTES = 225224
LEADING_SECTION_BYTES = 8


def tgi_with_sky(page_x: int = 640, texture_x: int = 0) -> bytes:
    """Header with one 8-byte section before the skybox, then the skybox."""
    lengths = [LEADING_SECTION_BYTES // 2] + [0] * 8 + [SKYBOX_BYTES // 2]
    header = bytearray(HEADER_SIZE)
    struct.pack_into("<10i", header, SECTION_LENGTHS_OFFSET, *lengths)
    quads = struct.pack("<7h", 768, 232, page_x, 256, texture_x, 0, 1) * SKY_QUADS
    cluts = b"".join(
        struct.pack("<4h", 768, 232 + i, 256, 1) + bytes(512) for i in range(SKY_CLUTS)
    )
    texture = struct.pack("<4h", 640, 256, 384, 256) + bytes(SKY_WORDS * 2)
    return bytes(header) + bytes(LEADING_SECTION_BYTES) + quads + cluts + texture


def tgi_with_bonus_tim(clut_rows: int) -> bytes:
    """Header with the bonus TIM directly after it (all earlier sections empty)."""
    header = bytearray(HEADER_SIZE)
    clut = struct.pack("<I4H", 12 + clut_rows * 512, 0, 480, 256, clut_rows) + bytes(
        clut_rows * 512
    )
    image = struct.pack("<I4H", 12 + 8, 640, 0, 2, 2) + bytes(8)
    return bytes(header) + struct.pack("<2I", 0x10, 0x9) + clut + image


class ReadBonusSkyTest(unittest.TestCase):
    def test_read_bonus_sky_pairs_each_clut_row(self) -> None:
        pairs = read_bonus_sky(tgi_with_bonus_tim(clut_rows=2))
        self.assertEqual([p.clut.y for p in pairs], [480, 481])


class ReadSkyTest(unittest.TestCase):
    def test_read_sky_atlas_x(self) -> None:
        _, _, quads = read_sky(tgi_with_sky(page_x=768, texture_x=5))
        self.assertEqual(quads[0].atlas_x, 261)

    def test_read_sky_counts(self) -> None:
        upload, cluts, quads = read_sky(tgi_with_sky())
        self.assertEqual(
            (upload.width_words, upload.height, len(cluts), len(quads)),
            (384, 256, 24, 1152),
        )

    def test_read_sky_band_from_order(self) -> None:
        _, _, quads = read_sky(tgi_with_sky())
        self.assertEqual(quads[48].band, 1)


if __name__ == "__main__":
    unittest.main()
