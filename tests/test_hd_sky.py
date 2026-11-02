"""Tests for sky segmentation and per-quad filtering (synthetic images only)."""

import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.assets import SkyQuad
from hd.sky import build_sky, segments
from hd.upscale import lanczos4

ATLAS_SIZE = (768, 256)


def quad(band: int, clut_y: int, atlas_x: int, stride: int) -> SkyQuad:
    return SkyQuad(band, clut_y, atlas_x, 0, stride)


def blank_atlas() -> Image.Image:
    return Image.new("RGBA", ATLAS_SIZE, (0, 0, 0, 255))


def two_colour_atlas(left: tuple, right: tuple, split_x: int) -> Image.Image:
    atlas = Image.new("RGBA", ATLAS_SIZE, right + (255,))
    atlas.paste(left + (255,), (0, 0, split_x, ATLAS_SIZE[1]))
    return atlas


class SkyTest(unittest.TestCase):
    def test_segments_split_on_clut_change(self) -> None:
        self.assertEqual(len(segments([quad(0, 232, 0, 1), quad(0, 233, 1, 1)])), 2)

    def test_segments_join_adjacent_quads(self) -> None:
        self.assertEqual(
            segments([quad(0, 232, 0, 3), quad(0, 232, 3, 3)]), [(232, 0, 6, 0, 15)]
        )

    def test_sky_quad_filter_does_not_read_outside_crop(self) -> None:
        atlas = two_colour_atlas(left=(0, 0, 255), right=(255, 255, 255), split_x=16)
        out = build_sky(atlas, [quad(0, 232, 0, 16)], 232, lanczos4)
        self.assertEqual(out.getpixel((63, 8))[:3], (0, 0, 255))

    def test_build_sky_keeps_size(self) -> None:
        self.assertEqual(build_sky(blank_atlas(), [], 232, lanczos4).size, (3072, 1024))


if __name__ == "__main__":
    unittest.main()
