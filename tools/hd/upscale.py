"""4x colour upscalers; part 2 adds the model and the M60 mix behind the same type."""

from collections.abc import Callable

from PIL import Image

SCALE = 4

Upscaler = Callable[[Image.Image], Image.Image]


def lanczos4(image: Image.Image) -> Image.Image:
    """RGB in, RGB out, reading only pixels of the given image."""
    return image.convert("RGB").resize(
        (image.width * SCALE, image.height * SCALE), Image.Resampling.LANCZOS
    )
