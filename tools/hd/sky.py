"""Sky atlas: each quad is filtered on its own so no filter crosses into a
neighbouring strip (the cause of the sky lines, spike round 3)."""

from PIL import Image

from hd.assets import SkyQuad
from hd.upscale import SCALE, Upscaler

USED_ROWS = 15  # row 16 of each band is never sampled


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
    """The atlas in one palette at 4x: nearest base, every quad of clut_y filtered from its own crop."""
    size = (atlas.width * SCALE, atlas.height * SCALE)
    out = atlas.resize(size, Image.Resampling.NEAREST)
    alpha = out.getchannel("A")
    for quad in quads:
        if quad.clut_y != clut_y:
            continue
        box = (
            quad.atlas_x,
            quad.atlas_y,
            quad.atlas_x + quad.stride,
            quad.atlas_y + USED_ROWS,
        )
        out.paste(upscale(atlas.crop(box)), (box[0] * SCALE, box[1] * SCALE))
    out.putalpha(alpha)
    return out
