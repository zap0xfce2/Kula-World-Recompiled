"""4x colour upscalers; part 2 adds the model and the M60 mix behind the same type."""

from collections import deque
from collections.abc import Callable

from PIL import Image

SCALE = 4

Upscaler = Callable[[Image.Image], Image.Image]


def lanczos4(image: Image.Image) -> Image.Image:
    """RGB in, RGB out, reading only pixels of the given image."""
    return image.convert("RGB").resize(
        (image.width * SCALE, image.height * SCALE), Image.Resampling.LANCZOS
    )


def fill_transparent(image: Image.Image) -> Image.Image:
    """Cutout texels take the colour of the nearest visible one, so filters don't pull black into edges."""
    # ponytail: pure-Python BFS per texel, fine for disc textures (at most 384x256)
    width, height = image.size
    pixels = list(image.get_flattened_data())
    queue = deque(i for i, p in enumerate(pixels) if p[3])
    if not queue or len(queue) == len(pixels):
        return image
    done = bytearray(1 if p[3] else 0 for p in pixels)
    while queue:
        index = queue.popleft()
        x, y = index % width, index // width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            neighbour = ny * width + nx
            if 0 <= nx < width and 0 <= ny < height and not done[neighbour]:
                done[neighbour] = 1
                pixels[neighbour] = pixels[index][:3] + (0,)
                queue.append(neighbour)
    out = Image.new("RGBA", image.size)
    out.putdata(pixels)
    return out


def clear_cutout(image: Image.Image) -> Image.Image:
    """Cutout must be exact RGBA zero: in ST files alpha 0 with colour is drawn semi-transparent."""
    visible = image.getchannel("A").point(lambda v: 255 if v else 0)
    return Image.composite(image, Image.new("RGBA", image.size, (0, 0, 0, 0)), visible)
