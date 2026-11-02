"""Tests for sky segmentation and per-segment filtering (synthetic images only)."""

import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.assets import SkyQuad
from hd.sky import band_rects, build_sky, segments
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

    def test_build_sky_filters_across_quads_of_one_segment(self) -> None:
        # Quads are often one texel wide; filtered alone, each column only stretches.
        atlas = two_colour_atlas(left=(0, 0, 255), right=(255, 255, 255), split_x=1)
        quads = [quad(0, 232, 0, 1), quad(0, 232, 1, 1)]
        out = build_sky(atlas, quads, 232, lanczos4)
        self.assertNotEqual(out.getpixel((3, 8)), out.getpixel((0, 8)))

    def test_build_sky_has_no_dark_fringe(self) -> None:
        atlas = Image.new("RGBA", ATLAS_SIZE, (0, 0, 0, 0))
        atlas.paste((255, 0, 0, 255), (4, 0, 12, 15))
        out = build_sky(atlas, [quad(0, 232, 0, 16)], 232, lanczos4).crop(
            (0, 0, 64, 60)
        )
        self.assertGreater(
            min(r for r, _g, _b, a in out.get_flattened_data() if a), 200
        )

    def test_build_sky_cutout_is_exact_zero(self) -> None:
        atlas = Image.new("RGBA", ATLAS_SIZE, (0, 0, 0, 0))
        atlas.paste((255, 0, 0, 255), (4, 0, 12, 15))
        out = build_sky(atlas, [quad(0, 232, 0, 16)], 232, lanczos4).crop(
            (0, 0, 64, 60)
        )
        self.assertEqual(
            {p for p in out.get_flattened_data() if p[3] == 0}, {(0, 0, 0, 0)}
        )

    def test_band_rects_cover_one_band_per_rect(self) -> None:
        # One small file per band keeps a world's 24 sky palettes inside the runtime's 64 MiB decode budget.
        quads = [quad(0, 232, 0, 3), quad(0, 232, 3, 3), SkyQuad(1, 232, 10, 16, 2)]
        self.assertEqual(band_rects(quads, 232), [(0, 0, 6, 16), (10, 16, 2, 16)])

    def test_band_rects_align_to_words(self) -> None:
        # The runtime rejects P8 names whose offset or width is odd.
        self.assertEqual(band_rects([quad(0, 232, 561, 191)], 232), [(560, 0, 192, 16)])

    def test_band_rects_skip_other_cluts(self) -> None:
        self.assertEqual(band_rects([quad(0, 233, 0, 3)], 232), [])

    def test_build_sky_keeps_size(self) -> None:
        self.assertEqual(build_sky(blank_atlas(), [], 232, lanczos4).size, (3072, 1024))


if __name__ == "__main__":
    unittest.main()
