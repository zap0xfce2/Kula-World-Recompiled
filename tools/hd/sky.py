"""Sky atlas: each run of adjacent quads is filtered on its own so no filter
crosses into a neighbouring strip (the cause of the sky lines, spike round 3)."""

from PIL import Image

from hd.assets import SkyQuad
from hd.names import Rect
from hd.upscale import SCALE, Upscaler, clear_cutout, fill_transparent

USED_ROWS = 15  # row 16 of each band is never sampled
BAND_ROWS = 16
TEXELS_PER_WORD_8BPP = 2  # sub-rect offset and width must be whole words


def segments(quads: list[SkyQuad]) -> list[tuple[int, int, int, int, int]]:
    """Runs of adjacent quads in one band and CLUT: (clut_y, x0, x1, y0, y1), half-open."""
    runs: list[tuple[int, int, int, int, int]] = []
    previous: SkyQuad | None = None
    for quad in quads:
        joins = (
            previous is not None
            and (quad.band, quad.clut_y) == (previous.band, previous.clut_y)
            and quad.atlas_x == runs[-1][2]
        )
        if joins:
            runs[-1] = runs[-1][:2] + (quad.atlas_x + quad.stride,) + runs[-1][3:]
        else:
            y0 = quad.atlas_y
            runs.append(
                (
                    quad.clut_y,
                    quad.atlas_x,
                    quad.atlas_x + quad.stride,
                    y0,
                    y0 + USED_ROWS,
                )
            )
        previous = quad
    return runs


def build_sky(
    atlas: Image.Image, quads: list[SkyQuad], clut_y: int, upscale: Upscaler
) -> Image.Image:
    """The atlas in one palette at 4x: nearest base, every segment of clut_y filtered from its own crop.

    Per segment, not per quad: quads are often one texel wide, alone they get no
    horizontal filtering and the sky breaks into columns (W2, Mac acceptance)."""
    size = (atlas.width * SCALE, atlas.height * SCALE)
    out = atlas.resize(size, Image.Resampling.NEAREST)
    alpha = out.getchannel("A")
    atlas = fill_transparent(atlas)
    for segment_clut, x0, x1, y0, y1 in segments(quads):
        if segment_clut != clut_y:
            continue
        out.paste(upscale(atlas.crop((x0, y0, x1, y1))), (x0 * SCALE, y0 * SCALE))
    out.putalpha(alpha)
    return clear_cutout(out)


def band_rects(quads: list[SkyQuad], clut_y: int) -> list[Rect]:
    """Per band, the texel span of the quads drawn with clut_y."""
    spans: dict[int, tuple[int, int, int]] = {}
    for quad in quads:
        if quad.clut_y != clut_y:
            continue
        x0, x1, y0 = spans.get(quad.band, (quad.atlas_x, quad.atlas_x, quad.atlas_y))
        spans[quad.band] = (
            min(x0, quad.atlas_x),
            max(x1, quad.atlas_x + quad.stride),
            y0,
        )
    rects = []
    for x0, x1, y0 in spans.values():
        x0 -= x0 % TEXELS_PER_WORD_8BPP
        x1 += x1 % TEXELS_PER_WORD_8BPP
        rects.append((x0, y0, x1 - x0, BAND_ROWS))
    return rects
