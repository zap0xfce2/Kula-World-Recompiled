"""The model upscaler (M60): IllustrationJaNai mixed 60/40 with Lanczos.

torch and spandrel are imported only when a model is loaded, so the Lanczos
build runs without them."""

import hashlib
import os
from pathlib import Path
from types import ModuleType

from PIL import Image

from hd.upscale import SCALE, Upscaler, lanczos4

MODEL_WEIGHT = 0.6  # user's pick in the spike (M60)
TILE = 256  # keeps the sky panorama (784x360) within CPU memory
OVERLAP = 16  # source pixels of context around each tile
CHANNEL_MAX = 255.0


def mix(model: Upscaler, weight: float = MODEL_WEIGHT) -> Upscaler:
    def mixed(image: Image.Image) -> Image.Image:
        return Image.blend(lanczos4(image), model(image).convert("RGB"), weight)

    return mixed


def tile_boxes(width: int, height: int, tile: int) -> list[tuple[int, int, int, int]]:
    return [
        (x, y, min(x + tile, width), min(y + tile, height))
        for y in range(0, height, tile)
        for x in range(0, width, tile)
    ]


def tiled(model: Upscaler, tile: int = TILE, overlap: int = OVERLAP) -> Upscaler:
    """Large images in tiles with context; only each tile's core is kept."""

    def run(image: Image.Image) -> Image.Image:
        image = image.convert("RGB")
        if image.width <= tile and image.height <= tile:
            return model(image)
        out = Image.new("RGB", (image.width * SCALE, image.height * SCALE))
        for x0, y0, x1, y1 in tile_boxes(image.width, image.height, tile):
            cx0, cy0 = max(0, x0 - overlap), max(0, y0 - overlap)
            cx1, cy1 = min(image.width, x1 + overlap), min(image.height, y1 + overlap)
            hd = model(image.crop((cx0, cy0, cx1, cy1)))
            core = ((x0 - cx0), (y0 - cy0), (x1 - cx0), (y1 - cy0))
            out.paste(hd.crop(tuple(v * SCALE for v in core)), (x0 * SCALE, y0 * SCALE))
        return out

    return run


def disk_cached(model: Upscaler, directory: Path) -> Upscaler:
    """One model run per distinct RGB image, also across resumed builds."""
    directory.mkdir(parents=True, exist_ok=True)

    def cached(image: Image.Image) -> Image.Image:
        rgb = image.convert("RGB")
        key = hashlib.sha1(f"{rgb.width}x{rgb.height}".encode() + rgb.tobytes())
        path = directory / f"{key.hexdigest()}.png"
        if path.exists():
            return Image.open(path).convert("RGB")
        out = model(rgb)
        tmp = path.with_suffix(".tmp.png")
        out.save(tmp)
        os.replace(tmp, path)
        return out

    return cached


def pick_device(torch_module: ModuleType, device: str | None) -> str:
    if device:
        return device
    if torch_module.cuda.is_available():
        return "cuda"
    if torch_module.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_model(path: Path, device: str | None = None) -> Upscaler:
    import numpy as np  # noqa: PLC0415 - only with the model packages installed
    import spandrel  # noqa: PLC0415
    import torch  # noqa: PLC0415

    torch.set_num_threads(
        max(1, (os.cpu_count() or 2) - 1)
    )  # one core stays for the game
    target = pick_device(torch, device)
    print(f"model device: {target}", flush=True)  # goes to the runner's log
    descriptor = spandrel.ModelLoader(target).load_from_file(path).eval()
    if descriptor.scale != SCALE:  # tiled() and mix() assume 4x
        raise ValueError(f"{path.name}: scale {descriptor.scale}, need {SCALE}")

    def run(image: Image.Image) -> Image.Image:
        array = np.asarray(image.convert("RGB"), dtype=np.float32) / CHANNEL_MAX
        tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).to(target)
        with torch.inference_mode():
            result = descriptor(tensor)
        pixels = result.squeeze(0).permute(1, 2, 0).mul(CHANNEL_MAX).round()
        return Image.fromarray(pixels.byte().cpu().numpy(), "RGB")

    return run


def model_upscaler(path: Path, cache: Path, device: str | None = None) -> Upscaler:
    return mix(disk_cached(tiled(load_model(path, device)), cache))
