"""Tests for the GGI sprite reader (synthetic files built with struct only)."""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.ggi import read_sprites

HEADER_INTS = 15
SPRITES_RAW_INDEX = 11  # rawOffsetSprites, the 6th entry of the offset chain
CHAIN_ANCHOR = 0x34


def ggi(sprite_sheet: bytes) -> bytes:
    """Header whose offset chain points the sprite sheet right after the header."""
    header = [0] * HEADER_INTS
    header[SPRITES_RAW_INDEX] = (HEADER_INTS * 4 - CHAIN_ANCHOR) // 2
    return struct.pack(f"<{HEADER_INTS}i", *header) + sprite_sheet


def p4_sprite(reuse: bool) -> bytes:
    clut = struct.pack("<4h", 0, 480, int(reuse), 0) + (b"" if reuse else bytes(32))
    texture = struct.pack("<4h", 512, 0, 4, 2) + bytes(4)
    return struct.pack("<2h", 4, 0) + clut + texture


def ggi_with_two_p4_sprites(second_reuses: bool) -> bytes:
    return ggi(struct.pack("<i", 2) + p4_sprite(False) + p4_sprite(second_reuses))


def ggi_with_16bpp_sprite() -> bytes:
    sprite = struct.pack("<2h", 16, 0) + struct.pack("<4h", -1, -1, -1, -1)
    sprite += struct.pack("<4h", 0, 0, 2, 1) + bytes(4)
    return ggi(struct.pack("<i", 1) + sprite)


class ReadSpritesTest(unittest.TestCase):
    def test_read_sprites_reuses_previous_clut(self) -> None:
        pairs = read_sprites(ggi_with_two_p4_sprites(second_reuses=True))
        self.assertIs(pairs[1].clut, pairs[0].clut)

    def test_read_sprites_skips_16bpp(self) -> None:
        self.assertEqual(len(read_sprites(ggi_with_16bpp_sprite())), 0)

    def test_read_sprites_upload_in_words(self) -> None:
        pairs = read_sprites(ggi_with_two_p4_sprites(second_reuses=False))
        self.assertEqual((pairs[0].upload.width_words, pairs[0].upload.height), (1, 2))


if __name__ == "__main__":
    unittest.main()
