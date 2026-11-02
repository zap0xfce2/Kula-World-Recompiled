"""Tests for tileset textures and their palettes (synthetic TGI parts only)."""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.tgi import clut_position, read_tiles

HEADER_SIZE = 0x190
DEPTH_CUE_COUNT_OFFSET = 0x108
SECTION_LENGTHS_OFFSET = 0x164
DEPTH_CUE_CLUTS = 2
FULL_CLUT = (768, 0)
MIP_CLUT = (784, 90)
TILE_AT = (0, 256)
MIP_AT = (448, 256)


def clut_id(x: int, y: int) -> int:
    return (y << 6) | (x >> 4)


def block(x: int, y: int, w: int, h: int) -> bytes:
    return struct.pack("<4h", x, y, w, h) + bytes(w * h * 2)


def tgi_with_tiles() -> bytes:
    """One texture entry: a 64x64 P8 tile and a 32x32 P4 mipmap with two fog CLUTs."""
    part0 = struct.pack("<2h", clut_id(*MIP_CLUT), clut_id(*MIP_CLUT) + 1)
    part5 = struct.pack("<2h", 0, 1)
    full = struct.pack("<5h", clut_id(*FULL_CLUT), clut_id(*FULL_CLUT), clut_id(*FULL_CLUT), *TILE_AT)
    mip = struct.pack("<5h", 0, 0, 0, *MIP_AT)
    part6 = full + mip + bytes(20)
    part10 = block(768, 0, 256, 1) + block(768, 90, 256, 1) + block(*TILE_AT, 32, 64) + block(*MIP_AT, 8, 32)
    parts = [part0, b"", b"", b"", b"", part5, part6, b"", b"", b"", part10]
    header = bytearray(HEADER_SIZE)
    struct.pack_into("<i", header, DEPTH_CUE_COUNT_OFFSET, DEPTH_CUE_CLUTS)
    struct.pack_into("<11i", header, SECTION_LENGTHS_OFFSET, *(len(p) // 2 for p in parts))
    return bytes(header) + b"".join(parts)


class TilesTest(unittest.TestCase):
    def test_mipmap_clut_position(self) -> None:
        self.assertEqual(clut_position(clut_id(784, 90)), (784, 90))

    def test_full_tile_pairs_with_full_clut(self) -> None:
        pairs = read_tiles(tgi_with_tiles())
        full = [p for p in pairs if p.upload.depth == 8]
        self.assertEqual([(p.clut.x, p.clut.y) for p in full], [FULL_CLUT])

    def test_mipmap_pairs_with_each_fog_clut(self) -> None:
        pairs = read_tiles(tgi_with_tiles())
        mips = sorted((p.clut.x, p.clut.y) for p in pairs if p.upload.depth == 4)
        self.assertEqual(mips, [(784, 90), (800, 90)])


if __name__ == "__main__":
    unittest.main()
