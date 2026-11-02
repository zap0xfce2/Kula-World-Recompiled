"""Tests for decoding textures like the runtime dumper (synthetic data only)."""

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.assets import Clut, Pairing, Upload
from hd.decode import decode, keys_for


def p4_upload(indices: list[int]) -> Upload:
    """One row of P4 texels, four per word, low nibble first."""
    padded = indices + [0] * (-len(indices) % 4)
    words = [
        sum(padded[i + n] << (4 * n) for n in range(4))
        for i in range(0, len(padded), 4)
    ]
    return Upload(
        0, 0, len(words), 1, 4, struct.pack(f"<{len(words)}H", *words), "sprite"
    )


def clut_with(index: int, color: int) -> Clut:
    colors = [0] * 16
    colors[index] = color
    return Clut(0, 480, struct.pack("<16H", *colors))


def pair_with_clut(color: int, kind: str = "sprite", texels: int = 16) -> Pairing:
    """A square P4 upload of the given edge length in texels."""
    words = texels // 4
    upload = Upload(0, 0, words, texels, 4, bytes(words * texels * 2), kind)
    return Pairing(upload, clut_with(1, color))


class DecodeTest(unittest.TestCase):
    def test_decode_rounds_5bit(self) -> None:
        image = decode(p4_upload([1]), clut_with(1, 0x7FFF), False)
        self.assertEqual(image.getpixel((0, 0)), (255, 255, 255, 255))

    def test_decode_zero_is_cutout(self) -> None:
        image = decode(p4_upload([0]), clut_with(0, 0x0000), False)
        self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_decode_stp_alpha_143_only_in_st(self) -> None:
        image = decode(p4_upload([1]), clut_with(1, 0x8001), True)
        self.assertEqual(image.getpixel((0, 0))[3], 143)

    def test_decode_reads_low_nibble_first(self) -> None:
        image = decode(p4_upload([0, 1]), clut_with(1, 0x7FFF), False)
        self.assertEqual(image.getpixel((1, 0))[3], 255)

    def test_st_variant_when_palette_has_stp_bit(self) -> None:
        self.assertEqual(
            [k.semi for k in keys_for(pair_with_clut(0x8001))], [False, True]
        )

    def test_no_st_variant_without_stp_bit(self) -> None:
        self.assertEqual(len(keys_for(pair_with_clut(0x7FFF))), 1)

    def test_st_variant_for_tiles(self) -> None:
        # Fading, crumbling and glass-level cubes are drawn semi-transparent (decomp level_init.c).
        self.assertEqual(len(keys_for(pair_with_clut(0x8001, kind="tile"))), 2)

    def test_no_keys_below_dump_threshold(self) -> None:
        self.assertEqual(keys_for(pair_with_clut(0x7FFF, kind="tile", texels=8)), [])


if __name__ == "__main__":
    unittest.main()
