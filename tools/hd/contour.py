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


NEIGHBOURS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
NEIGHBOURS_8 = NEIGHBOURS_4 + ((-1, -1), (1, -1), (-1, 1), (1, 1))
MIN_AREA_SHARE = 0.75  # rounding may not eat more than a quarter of a glyph


def single_band(image: Image.Image) -> Image.Image:
    return image.getchannel("A") if image.mode == "RGBA" else image


def components(
    pixels: bytes, width: int, height: int, steps: tuple[tuple[int, int], ...]
) -> int:
    """Connected regions of non-zero pixels."""
    # ponytail: pure-Python BFS, fine for UI sprites; numpy/scipy if large images get here
    seen = bytearray(len(pixels))
    count = 0
    for start, value in enumerate(pixels):
        if value and not seen[start]:
            count += 1
            flood(pixels, seen, start, width, height, steps)
    return count


def flood(
    pixels: bytes,
    seen: bytearray,
    start: int,
    width: int,
    height: int,
    steps: tuple[tuple[int, int], ...],
) -> None:
    queue = deque([start])
    seen[start] = 1
    while queue:
        index = queue.popleft()
        x, y = index % width, index // width
        for dx, dy in steps:
            nx, ny = x + dx, y + dy
            neighbour = ny * width + nx
            inside = 0 <= nx < width and 0 <= ny < height
            if inside and pixels[neighbour] and not seen[neighbour]:
                seen[neighbour] = 1
                queue.append(neighbour)


def region_count(image: Image.Image) -> int:
    """4-connected regions of non-zero alpha (or of a single-band mask)."""
    band = single_band(image)
    return components(band.tobytes(), *band.size, NEIGHBOURS_4)


def hole_count(image: Image.Image) -> int:
    """Enclosed transparent areas, like the counter of an 'o'."""
    band = single_band(image)
    padded = Image.new("L", (band.width + 2, band.height + 2), 0)
    padded.paste(band, (1, 1))
    inverted = padded.point(lambda v: 0 if v else 255)
    return components(inverted.tobytes(), *padded.size, NEIGHBOURS_8) - 1


def lit_area(mask: Image.Image) -> int:
    return len(mask.tobytes()) - mask.tobytes().count(0)


def contour_mask(image: Image.Image, radius: float) -> Image.Image:
    mask = binary(image.getchannel("A").point(lambda v: 255 if v else 0))
    size = (image.width * SCALE, image.height * SCALE)
    smooth = mask.resize(size, Image.Resampling.LANCZOS).filter(
        ImageFilter.GaussianBlur(radius)
    )
    return binary(smooth)


def pick_mask(image: Image.Image) -> Image.Image:
    """The roundest mask that keeps regions, holes and most of the area, else nearest."""
    nearest = binary(upscale_alpha_nearest(image).point(lambda v: 255 if v else 0))
    wanted = (region_count(nearest), hole_count(nearest))
    min_area = lit_area(nearest) * MIN_AREA_SHARE
    for radius in RADII:
        mask = contour_mask(image, radius)
        if (region_count(mask), hole_count(mask)) == wanted and lit_area(
            mask
        ) >= min_area:
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
