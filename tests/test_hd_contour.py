"""Tests for the rounded UI contour (synthetic images only)."""

import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.contour import check_classes, hole_count, region_count, round_ui
from hd.upscale import fill_transparent, lanczos4

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


def ring_with_hole() -> Image.Image:
    """A 3x3 ring around one transparent texel, like a small 'o'."""
    image = Image.new("RGBA", (5, 5), (0, 0, 0, 0))
    image.paste(WHITE, (1, 1, 4, 4))
    image.putpixel((2, 2), (0, 0, 0, 0))
    return image


def thin_t() -> Image.Image:
    image = Image.new("RGBA", (7, 7), (0, 0, 0, 0))
    image.paste(WHITE, (1, 1, 6, 2))
    image.paste(WHITE, (3, 2, 4, 6))
    return image


DARK_STP = (8, 8, 8, 143)


def white_blob_with_dark_stp_rim() -> Image.Image:
    """Like the HUD fruits: an opaque body whose rim is dark STP (subtractive shadow)."""
    image = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    for y in range(1, 11):
        for x in range(1, 12 - y):
            image.putpixel((x, y), WHITE)
        image.putpixel((12 - y, y), DARK_STP)
    return image


def dark_opaque_grown(image: Image.Image, out: Image.Image) -> int:
    """Pixels rounding added outside the original that are opaque but dark."""
    source = image.load()
    pixels = out.load()
    return sum(
        1
        for y in range(out.height)
        for x in range(out.width)
        if not source[x // 4, y // 4][3]
        and pixels[x, y][3] == 255
        and sum(pixels[x, y][:3]) < 60
    )


def lit(image: Image.Image) -> int:
    return sum(1 for a in image.getchannel("A").tobytes() if a)


class ContourTest(unittest.TestCase):
    def test_round_ui_keeps_letter_hole(self) -> None:
        self.assertEqual(hole_count(round_ui(ring_with_hole(), lanczos4)), 1)

    def test_round_ui_keeps_thin_stroke_area(self) -> None:
        original = lit(thin_t()) * 16
        self.assertGreaterEqual(lit(round_ui(thin_t(), lanczos4)), original * 3 // 4)

    def test_contour_radius_keeps_thin_stroke(self) -> None:
        self.assertEqual(region_count(round_ui(one_pixel_wide_letter_i(), lanczos4)), 2)

    def test_grown_pixels_take_the_class_of_their_colour_source(self) -> None:
        image = fill_transparent(white_blob_with_dark_stp_rim())
        self.assertEqual(dark_opaque_grown(image, round_ui(image, lanczos4)), 0)

    def test_round_ui_alpha_classes_only(self) -> None:
        check_classes(round_ui(blob_with_stp_texels(), lanczos4))

    def test_round_ui_is_4x(self) -> None:
        self.assertEqual(round_ui(blob_with_stp_texels(), lanczos4).size, (24, 24))

    def test_check_classes_rejects_128(self) -> None:
        with self.assertRaises(ValueError):
            check_classes(Image.new("RGBA", (1, 1), (0, 0, 0, 128)))


if __name__ == "__main__":
    unittest.main()
