"""Tests for texture classes and per-class upscaling (synthetic data only)."""

import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.assets import Clut, Pairing, Upload
from hd.classify import classify, upscale_file
from hd.upscale import lanczos4


def pair(kind: str) -> Pairing:
    return Pairing(Upload(0, 0, 1, 1, 4, bytes(2), kind), Clut(0, 0, bytes(32)))


def red_square_in_cutout() -> Image.Image:
    out = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    out.paste((255, 0, 0, 255), (2, 2, 6, 6))
    return out


def darkest_visible_red(image: Image.Image) -> int:
    return min(r for r, _g, _b, a in image.get_flattened_data() if a)


def colours_under_cutout(image: Image.Image) -> set[tuple[int, ...]]:
    return {p for p in image.get_flattened_data() if p[3] == 0}


def image(alpha: int) -> Image.Image:
    out = Image.new("RGBA", (4, 4), (10, 20, 30, 255))
    out.putpixel((0, 0), (0, 0, 0, alpha))
    return out


class ClassifyTest(unittest.TestCase):
    def test_sky_upload_is_sky(self) -> None:
        self.assertEqual(classify(pair("sky"), image(255)), "sky")

    def test_sprite_with_cutout_is_ui(self) -> None:
        self.assertEqual(classify(pair("sprite"), image(0)), "ui")

    def test_sprite_with_stp_is_ui(self) -> None:
        self.assertEqual(classify(pair("sprite"), image(143)), "ui")

    def test_opaque_sprite_is_other(self) -> None:
        self.assertEqual(classify(pair("sprite"), image(255)), "other")

    def test_tile_is_other(self) -> None:
        self.assertEqual(classify(pair("tile"), image(0)), "other")

    def test_upscale_file_other_is_4x(self) -> None:
        self.assertEqual(upscale_file(image(0), "other", lanczos4).size, (16, 16))

    def test_upscale_file_other_keeps_alpha_nearest(self) -> None:
        self.assertEqual(
            upscale_file(image(0), "other", lanczos4).getpixel((3, 3))[3], 0
        )

    def test_upscale_file_other_has_no_dark_fringe(self) -> None:
        out = upscale_file(red_square_in_cutout(), "other", lanczos4)
        self.assertGreater(darkest_visible_red(out), 200)

    def test_upscale_file_ui_has_no_dark_fringe(self) -> None:
        out = upscale_file(red_square_in_cutout(), "ui", lanczos4)
        self.assertGreater(darkest_visible_red(out), 200)

    def test_upscale_file_ui_cutout_is_exact_zero(self) -> None:
        # In ST files only RGBA (0,0,0,0) is cutout; alpha 0 with colour is drawn semi-transparent.
        out = upscale_file(red_square_in_cutout(), "ui", lanczos4)
        self.assertEqual(colours_under_cutout(out), {(0, 0, 0, 0)})

    def test_upscale_file_other_cutout_is_exact_zero(self) -> None:
        out = upscale_file(red_square_in_cutout(), "other", lanczos4)
        self.assertEqual(colours_under_cutout(out), {(0, 0, 0, 0)})

    def test_upscale_file_rejects_sky(self) -> None:
        with self.assertRaises(ValueError):
            upscale_file(image(255), "sky", lanczos4)


if __name__ == "__main__":
    unittest.main()
