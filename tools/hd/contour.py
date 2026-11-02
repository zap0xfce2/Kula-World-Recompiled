"""Rounded UI contour (M60R): a smoother cutout edge without splitting or
merging glyph strokes. Alpha stays in the runtime's classes 0/143/255."""

from collections import deque

from PIL import Image, ImageFilter

from hd.upscale import SCALE, Upscaler, lanczos4

ALPHA_CLASSES = {0, 143, 255}
RADII = (4, 2, 1.5)
CUT = 128
EDGE_PX = 4
FILL_STEPS = 8


def upscale_alpha_nearest(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    return alpha.resize(
        (image.width * SCALE, image.height * SCALE), Image.Resampling.NEAREST
    )


def binary(mask: Image.Image) -> Image.Image:
    return mask.point(lambda v: 255 if v >= CUT else 0)


def region_count(image: Image.Image) -> int:
    """4-connected regions of non-zero alpha (or of a single-band mask)."""
    # ponytail: pure-Python BFS, fine for UI sprites; numpy/scipy if large images get here
    band = image.getchannel("A") if image.mode == "RGBA" else image
    width, height = band.size
    pixels = band.tobytes()
    seen = bytearray(len(pixels))
    count = 0
    for start, value in enumerate(pixels):
        if value and not seen[start]:
            count += 1
            flood(pixels, seen, start, width, height)
    return count


def flood(pixels: bytes, seen: bytearray, start: int, width: int, height: int) -> None:
    queue = deque([start])
    seen[start] = 1
    while queue:
        index = queue.popleft()
        x, y = index % width, index // width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            neighbour = ny * width + nx
            if (
                0 <= nx < width
                and 0 <= ny < height
                and pixels[neighbour]
                and not seen[neighbour]
            ):
                seen[neighbour] = 1
                queue.append(neighbour)


def contour_mask(image: Image.Image, radius: float) -> Image.Image:
    mask = binary(image.getchannel("A").point(lambda v: 255 if v else 0))
    size = (image.width * SCALE, image.height * SCALE)
    smooth = mask.resize(size, Image.Resampling.LANCZOS).filter(
        ImageFilter.GaussianBlur(radius)
    )
    return binary(smooth)


def pick_mask(image: Image.Image) -> Image.Image:
    """The roundest mask that keeps the region count, else the nearest one."""
    nearest = binary(upscale_alpha_nearest(image).point(lambda v: 255 if v else 0))
    wanted = region_count(nearest)
    for radius in RADII:
        mask = contour_mask(image, radius)
        if region_count(mask) == wanted:
            return mask
    return nearest


def class_alpha(image: Image.Image, mask: Image.Image) -> Image.Image:
    """Inside the mask: the class of a nearby visible texel; outside: cutout."""
    nearest = upscale_alpha_nearest(image)
    filled = nearest
    for _ in range(FILL_STEPS):
        filled = filled.filter(ImageFilter.MaxFilter(3))
    # Composite masks must be strictly 0/255, else they blend the classes.
    visible = nearest.point(lambda v: 255 if v else 0)
    inside = Image.composite(nearest, filled, visible)
    return Image.composite(inside, Image.new("L", mask.size, 0), mask)


def round_ui(image: Image.Image, upscale: Upscaler) -> Image.Image:
    mask = pick_mask(image)
    edge = Image.composite(
        Image.new("L", mask.size, 0),
        mask,
        mask.filter(ImageFilter.MinFilter(2 * EDGE_PX + 1)),
    )
    colour = Image.composite(lanczos4(image), upscale(image), edge)
    out = colour.convert("RGBA")
    out.putalpha(class_alpha(image, mask))
    return out


def check_classes(image: Image.Image) -> None:
    histogram = image.getchannel("A").histogram()
    stray = [
        value for value, n in enumerate(histogram) if n and value not in ALPHA_CLASSES
    ]
    if stray:
        raise ValueError(f"alpha outside 0/143/255: {stray[:5]}")
