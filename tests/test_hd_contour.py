"""Tests for the rounded UI contour (synthetic images only)."""

import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.contour import check_classes, region_count, round_ui
from hd.upscale import lanczos4

WHITE = (255, 255, 255, 255)


def one_pixel_wide_letter_i() -> Image.Image:
    """A dot above a stem, one texel apart: two regions that rounding must not merge."""
    image = Image.new("RGBA", (5, 9), (0, 0, 0, 0))
    image.putpixel((2, 1), WHITE)
    for y in range(3, 8):
        image.putpixel((2, y), WHITE)
    return image


def blob_with_stp_texels() -> Image.Image:
    image = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
    image.paste((200, 100, 50, 255), (1, 1, 5, 5))
    image.paste((200, 100, 50, 143), (2, 2, 4, 4))
    return image


class ContourTest(unittest.TestCase):
    def test_contour_radius_keeps_thin_stroke(self) -> None:
        self.assertEqual(region_count(round_ui(one_pixel_wide_letter_i(), lanczos4)), 2)

    def test_round_ui_alpha_classes_only(self) -> None:
        check_classes(round_ui(blob_with_stp_texels(), lanczos4))

    def test_round_ui_is_4x(self) -> None:
        self.assertEqual(round_ui(blob_with_stp_texels(), lanczos4).size, (24, 24))

    def test_check_classes_rejects_128(self) -> None:
        with self.assertRaises(ValueError):
            check_classes(Image.new("RGBA", (1, 1), (0, 0, 0, 128)))


if __name__ == "__main__":
    unittest.main()
