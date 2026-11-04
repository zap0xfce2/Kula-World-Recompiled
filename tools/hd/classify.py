"""Which edge treatment a texture gets: sky (per quad), UI (rounded contour) or other."""

from PIL import Image

from hd.assets import Pairing
from hd.contour import round_ui, upscale_alpha_nearest
from hd.upscale import Upscaler, clear_cutout, fill_transparent

TRANSPARENT_CLASSES = (0, 143)


def classify(pair: Pairing, image: Image.Image) -> str:
    """GGI holds exactly the global sprites, so a sprite with cutout or STP is UI."""
    if pair.upload.kind == "sky":
        return "sky"
    histogram = image.getchannel("A").histogram()
    if pair.upload.kind == "sprite" and any(histogram[a] for a in TRANSPARENT_CLASSES):
        return "ui"
    return "other"


def upscale_file(image: Image.Image, cls: str, upscale: Upscaler) -> Image.Image:
    if cls == "sky":
        raise ValueError("sky files are built per palette by hd.sky.build_sky")
    image = fill_transparent(image)
    if cls == "ui":
        return clear_cutout(round_ui(image, upscale))
    out = upscale(image).convert("RGBA")
    out.putalpha(upscale_alpha_nearest(image))
    return clear_cutout(out)
