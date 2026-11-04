"""Tests for colour fill under cutout texels (synthetic images only)."""

import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.upscale import fill_transparent


def red_then_cutout() -> Image.Image:
    image = Image.new("RGBA", (3, 1), (0, 0, 0, 0))
    image.putpixel((0, 0), (255, 0, 0, 255))
    return image


class UpscaleTest(unittest.TestCase):
    def test_fill_takes_nearest_visible_colour(self) -> None:
        self.assertEqual(
            fill_transparent(red_then_cutout()).getpixel((2, 0)), (255, 0, 0, 0)
        )

    def test_fill_keeps_visible_texels(self) -> None:
        self.assertEqual(
            fill_transparent(red_then_cutout()).getpixel((0, 0)), (255, 0, 0, 255)
        )

    def test_fill_leaves_fully_transparent_image(self) -> None:
        empty = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
        self.assertEqual(fill_transparent(empty).getpixel((1, 1)), (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
