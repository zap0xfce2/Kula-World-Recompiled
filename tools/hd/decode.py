"""Paletted VRAM data to RGBA, exactly as the runtime dumper writes it.

Reference: finalize_source in psxrecomp/runtime/src/duckstation_texture_pack.cpp.
"""

import struct
from dataclasses import replace

from PIL import Image

from hd.assets import Clut, Pairing, Upload
from hd.names import TEXELS_PER_WORD, TextureKey, hash_words

STP_BIT = 0x8000
MIN_TEXELS = 16  # the runtime dumper's default threshold; smaller mipmaps gain nothing
ST_KINDS = {"sprite"}  # runtime dumps show ST draws only for GGI sprites
ALPHA_STP = 143
ALPHA_OPAQUE = 255
LOW_NIBBLE = bytes(b & 0x0F for b in range(256))
HIGH_NIBBLE = bytes(b >> 4 for b in range(256))


def channel(color: int, shift: int) -> int:
    """5-bit to 8-bit with the dumper's rounding."""
    return (((color >> shift) & 31) * 255 + 15) // 31


def rgba(color: int, semi: bool) -> tuple[int, int, int, int]:
    alpha = 0 if color == 0 else ALPHA_STP if semi and color & STP_BIT else ALPHA_OPAQUE
    return channel(color, 0), channel(color, 5), channel(color, 10), alpha


def indices(upload: Upload) -> bytes:
    """One byte per texel; P4 holds the low nibble first."""
    if upload.depth == 8:
        return upload.words
    out = bytearray(len(upload.words) * 2)
    out[0::2] = upload.words.translate(LOW_NIBBLE)
    out[1::2] = upload.words.translate(HIGH_NIBBLE)
    return bytes(out)


def colors_of(clut: Clut) -> list[int]:
    return list(struct.unpack(f"<{len(clut.colors) // 2}H", clut.colors))


def decode(upload: Upload, clut: Clut, semi: bool) -> Image.Image:
    width = upload.width_words * TEXELS_PER_WORD[upload.depth]
    image = Image.frombytes("P", (width, upload.height), indices(upload))
    palette = [part for color in colors_of(clut) for part in rgba(color, semi)]
    image.putpalette(palette, "RGBA")
    return image.convert("RGBA")


def needs_st(clut: Clut) -> bool:
    """A semi-transparent draw needs its own ST file to keep STP texels blended."""
    return any(color & STP_BIT for color in colors_of(clut))


def keys_for(pair: Pairing) -> list[TextureKey]:
    upload = pair.upload
    width = upload.width_words * TEXELS_PER_WORD[upload.depth]
    if min(width, upload.height) < MIN_TEXELS:
        return []
    base = TextureKey(
        upload.depth,
        False,
        hash_words(upload.words),
        hash_words(pair.clut.colors),
        upload.width_words,
        upload.height,
    )
    if upload.kind not in ST_KINDS or not needs_st(pair.clut):
        return [base]
    return [base, replace(base, semi=True)]
