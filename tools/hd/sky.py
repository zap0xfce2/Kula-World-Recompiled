"""Sky: the 24 bands form one panorama (48 sectors on the same azimuths each), so
the filter runs over the whole sky once and no band edge shows as a seam (W2,
Mac). Only quad texels enter it, so other palettes never bleed in (spike round 3)."""

from itertools import groupby

from PIL import Image

from hd.assets import SkyQuad
from hd.names import Rect
from hd.upscale import SCALE, Upscaler, clear_cutout, fill_transparent

USED_ROWS = 15  # row 16 of each band is never sampled
BAND_ROWS = 16
TEXELS_PER_WORD_8BPP = 2  # sub-rect offset and width must be whole words
INCLUSIVE_EDGE = 1
PANORAMA_WIDTH = 768  # 48 sectors at the widest stride, 16 texels
WRAP = 8  # columns from the other end: the panorama is a full circle
LANCZOS = Image.Resampling.LANCZOS


def bands(quads: list[SkyQuad]) -> list[list[SkyQuad]]:
    return [list(band) for _, band in groupby(quads, key=lambda q: q.band)]


def band_strip(atlases: dict[int, Image.Image], band: list[SkyQuad]) -> Image.Image:
    """One band's quads side by side, each in its own palette."""
    strip = Image.new("RGB", (sum(q.stride for q in band), USED_ROWS))
    x = 0
    for q in band:
        box = (q.atlas_x, q.atlas_y, q.atlas_x + q.stride, q.atlas_y + USED_ROWS)
        strip.paste(atlases[q.clut_y].crop(box), (x, 0))
        x += q.stride
    return strip


def hd_panorama(
    atlases: dict[int, Image.Image], quads: list[SkyQuad], upscale: Upscaler
) -> list[Image.Image]:
    """Every band stretched to one width, stacked, filtered once; back as 4x band rows."""
    rows = bands(quads)
    if not rows:
        return []
    panorama = Image.new("RGB", (PANORAMA_WIDTH + 2 * WRAP, USED_ROWS * len(rows)))
    for index, band in enumerate(rows):
        stretched = band_strip(atlases, band).resize(
            (PANORAMA_WIDTH, USED_ROWS), LANCZOS
        )
        y = index * USED_ROWS
        panorama.paste(stretched, (WRAP, y))
        panorama.paste(
            stretched.crop((PANORAMA_WIDTH - WRAP, 0, PANORAMA_WIDTH, USED_ROWS)),
            (0, y),
        )
        panorama.paste(
            stretched.crop((0, 0, WRAP, USED_ROWS)), (WRAP + PANORAMA_WIDTH, y)
        )
    hd = upscale(panorama)
    height = USED_ROWS * SCALE
    return [
        hd.crop(
            (
                WRAP * SCALE,
                i * height,
                (WRAP + PANORAMA_WIDTH) * SCALE,
                (i + 1) * height,
            )
        ).resize((sum(q.stride for q in band) * SCALE, height), LANCZOS)
        for i, band in enumerate(rows)
    ]


def build_sky(
    atlases: dict[int, Image.Image], quads: list[SkyQuad], upscale: Upscaler
) -> dict[int, Image.Image]:
    """Each palette's atlas at 4x: nearest base, every quad cut from the filtered panorama."""
    filled = {y: fill_transparent(a).convert("RGB") for y, a in atlases.items()}
    out = {
        y: a.resize((a.width * SCALE, a.height * SCALE), Image.Resampling.NEAREST)
        for y, a in atlases.items()
    }
    alphas = {y: image.getchannel("A") for y, image in out.items()}
    for band, row in zip(bands(quads), hd_panorama(filled, quads, upscale)):
        x = 0
        for q in band:
            width = q.stride * SCALE
            out[q.clut_y].paste(
                row.crop((x, 0, x + width, row.height)),
                (q.atlas_x * SCALE, q.atlas_y * SCALE),
            )
            x += width
    for y, image in out.items():
        image.putalpha(alphas[y])
    return {y: clear_cutout(image) for y, image in out.items()}


def band_rects(quads: list[SkyQuad], clut_y: int) -> list[Rect]:
    """Per atlas row, the texel span of the quads drawn with clut_y.

    Keyed by row, not band: a band can wrap into the next row, and a draw outside
    every rect falls back to native pixels (blocky patches in the W2 sky)."""
    spans: dict[int, tuple[int, int]] = {}
    for quad in quads:
        if quad.clut_y != clut_y:
            continue
        x0, x1 = spans.get(quad.atlas_y, (quad.atlas_x, quad.atlas_x))
        spans[quad.atlas_y] = (
            min(x0, quad.atlas_x),
            max(x1, quad.atlas_x + quad.stride),
        )
    rects = []
    for y0, (x0, x1) in spans.items():
        x1 += INCLUSIVE_EDGE  # the runtime's query includes a polygon's largest U
        x0 -= x0 % TEXELS_PER_WORD_8BPP
        x1 += x1 % TEXELS_PER_WORD_8BPP
        rects.append((x0, y0, x1 - x0, BAND_ROWS))
    return rects
