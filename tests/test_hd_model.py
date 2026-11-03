"""Tests for the model mix, tiling and disk cache (fake models, synthetic images only)."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.model import disk_cached, mix, tiled


def nearest4(image: Image.Image) -> Image.Image:
    return image.convert("RGB").resize(
        (image.width * 4, image.height * 4), Image.Resampling.NEAREST
    )


def white4(image: Image.Image) -> Image.Image:
    return Image.new("RGB", (image.width * 4, image.height * 4), (255, 255, 255))


def noise(width: int, height: int) -> Image.Image:
    return Image.effect_noise((width, height), 64).convert("RGB")


class ModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def test_mix_weights_model_sixty_percent(self) -> None:
        black = Image.new("RGB", (4, 4), (0, 0, 0))
        self.assertEqual(mix(white4)(black).getpixel((8, 8)), (153, 153, 153))

    def test_tiled_equals_whole_for_pointwise_model(self) -> None:
        image = noise(300, 40)
        self.assertEqual(
            tiled(nearest4, tile=64, overlap=8)(image).tobytes(),
            nearest4(image).tobytes(),
        )

    def test_disk_cache_runs_model_once_per_image(self) -> None:
        calls: list[int] = []

        def counting(image: Image.Image) -> Image.Image:
            calls.append(1)
            return nearest4(image)

        cached = disk_cached(counting, self.tmp)
        # Same RGB, different alpha: the ST and the plain variant of one texture.
        cached(Image.new("RGBA", (2, 2), (9, 9, 9, 143)))
        cached(Image.new("RGBA", (2, 2), (9, 9, 9, 255)))
        self.assertEqual(len(calls), 1)

    def test_module_imports_without_torch(self) -> None:
        self.assertNotIn("torch", sys.modules)


if __name__ == "__main__":
    unittest.main()
