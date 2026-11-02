"""Texture data as the game uploads it to VRAM, read from the disc."""

from dataclasses import dataclass

BITS_PER_WORD = 16


@dataclass(frozen=True)
class Upload:
    x: int
    y: int
    width_words: int
    height: int
    depth: int  # 4 or 8 bits per texel
    words: bytes  # little-endian 16-bit words, row-major
    kind: str  # "sky" | "sprite" | "tile" | "bonus_sky"


@dataclass(frozen=True)
class Clut:
    x: int
    y: int
    colors: bytes  # 16 or 256 little-endian 16-bit colours


@dataclass(frozen=True)
class Pairing:
    upload: Upload
    clut: Clut


@dataclass(frozen=True)
class SkyQuad:
    band: int
    clut_y: int
    atlas_x: int  # texel column in the 768x256 sky atlas
    atlas_y: int
    stride: int


def words_for_texels(texels: int, depth: int) -> int:
    return texels * depth // BITS_PER_WORD
