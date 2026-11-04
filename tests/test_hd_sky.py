"""Tests for the sky panorama and its band sub-rects (synthetic images only)."""

import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.assets import SkyQuad
from hd.sky import band_rects, build_sky
from hd.upscale import lanczos4

ATLAS_SIZE = (768, 256)
CLUT = 232
BLUE, WHITE = (0, 0, 255), (255, 255, 255)


def quad(band: int, clut_y: int, atlas_x: int, stride: int) -> SkyQuad:
    return SkyQuad(band, clut_y, atlas_x, 0, stride)


def blank_atlas() -> Image.Image:
    return Image.new("RGBA", ATLAS_SIZE, (0, 0, 0, 255))


def two_colour_atlas(left: tuple, right: tuple, split_x: int) -> Image.Image:
    atlas = Image.new("RGBA", ATLAS_SIZE, right + (255,))
    atlas.paste(left + (255,), (0, 0, split_x, ATLAS_SIZE[1]))
    return atlas


def red_in_cutout() -> Image.Image:
    atlas = Image.new("RGBA", ATLAS_SIZE, (0, 0, 0, 0))
    atlas.paste((255, 0, 0, 255), (4, 0, 12, 15))
    return atlas


def sky(atlas: Image.Image, quads: list[SkyQuad]) -> Image.Image:
    return build_sky({CLUT: atlas}, quads, lanczos4)[CLUT]


class SkyTest(unittest.TestCase):
    def test_sky_filter_does_not_read_texels_outside_quads(self) -> None:
        atlas = two_colour_atlas(left=BLUE, right=WHITE, split_x=16)
        self.assertEqual(sky(atlas, [quad(0, CLUT, 0, 16)]).getpixel((63, 8))[:3], BLUE)

    def test_build_sky_filters_across_quads_of_one_band(self) -> None:
        # Quads are often one texel wide; filtered alone, each column only stretches.
        atlas = two_colour_atlas(left=BLUE, right=WHITE, split_x=1)
        out = sky(atlas, [quad(0, CLUT, 0, 1), quad(0, CLUT, 1, 1)])
        self.assertNotEqual(out.getpixel((3, 8)), out.getpixel((0, 8)))

    def test_build_sky_filters_across_band_boundaries(self) -> None:
        # Bands filtered on their own leave a visible seam where they meet (W2, Mac).
        atlas = Image.new("RGBA", ATLAS_SIZE, WHITE + (255,))
        atlas.paste(BLUE + (255,), (0, 0, 16, 16))
        quads = [quad(0, CLUT, 0, 16), SkyQuad(1, CLUT, 0, 16, 16)]
        self.assertNotEqual(sky(atlas, quads).getpixel((32, 59))[:3], BLUE)

    def test_build_sky_has_no_dark_fringe(self) -> None:
        out = sky(red_in_cutout(), [quad(0, CLUT, 0, 16)]).crop((0, 0, 64, 60))
        self.assertGreater(
            min(r for r, _g, _b, a in out.get_flattened_data() if a), 200
        )

    def test_build_sky_cutout_is_exact_zero(self) -> None:
        out = sky(red_in_cutout(), [quad(0, CLUT, 0, 16)]).crop((0, 0, 64, 60))
        self.assertEqual(
            {p for p in out.get_flattened_data() if p[3] == 0}, {(0, 0, 0, 0)}
        )

    def test_band_rects_cover_one_band_per_rect(self) -> None:
        # One small file per band keeps a world's 24 sky palettes inside the runtime's 64 MiB decode budget.
        quads = [quad(0, 232, 0, 3), quad(0, 232, 3, 3), SkyQuad(1, 232, 10, 16, 2)]
        self.assertEqual(band_rects(quads, 232), [(0, 0, 8, 16), (10, 16, 4, 16)])

    def test_band_rects_split_a_band_that_wraps_to_the_next_atlas_row(self) -> None:
        # W2: a band runs from x 754 in row 32 on to x 0 in row 48.
        quads = [SkyQuad(2, 239, 754, 32, 12), SkyQuad(2, 239, 0, 48, 12)]
        self.assertEqual(band_rects(quads, 239), [(754, 32, 14, 16), (0, 48, 14, 16)])

    def test_band_rects_align_to_words(self) -> None:
        # The runtime rejects P8 names whose offset or width is odd.
        self.assertEqual(band_rects([quad(0, 232, 561, 191)], 232), [(560, 0, 194, 16)])

    def test_band_rects_include_the_texel_after_the_last_quad(self) -> None:
        # A polygon's largest U is inclusive in the runtime's query; without it the
        # draw is composed with native pixels (W2, Mac).
        self.assertEqual(band_rects([quad(0, 232, 0, 4)], 232), [(0, 0, 6, 16)])

    def test_band_rects_skip_other_cluts(self) -> None:
        self.assertEqual(band_rects([quad(0, 233, 0, 3)], 232), [])

    def test_build_sky_keeps_size(self) -> None:
        self.assertEqual(sky(blank_atlas(), []).size, (3072, 1024))


if __name__ == "__main__":
    unittest.main()
