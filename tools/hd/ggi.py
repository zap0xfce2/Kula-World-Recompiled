"""Sprite sheet of HIRO.GGI (layout: wiki.kula.quest, graphics/ggi)."""

import struct

from hd.assets import Clut, Pairing, Upload, words_for_texels

CHAIN_ANCHOR = 0x34
CHAIN_START = 6  # first raw offset after the six sprite counts
SPRITES_IN_CHAIN = 5
DIRECT_COLOUR_BPP = 16
ALIGNMENT = 4


def sprite_sheet_offset(data: bytes) -> int:
    """Decode the half-delta offset chain up to the sprite sheet."""
    offset = CHAIN_ANCHOR
    for raw in struct.unpack_from(f"<{SPRITES_IN_CHAIN + 1}i", data, CHAIN_START * 4):
        offset += raw * 2
    return offset


def read_sprites(data: bytes) -> list[Pairing]:
    """Each paletted sprite with its own or the previous sprite's CLUT."""
    pos = sprite_sheet_offset(data)
    (count,) = struct.unpack_from("<i", data, pos)
    pos += 4
    pairs: list[Pairing] = []
    clut: Clut | None = None
    for _ in range(count):
        pos, clut, pair = read_sprite(data, pos, clut)
        if pair:
            pairs.append(pair)
    return pairs


def read_sprite(
    data: bytes, pos: int, previous: Clut | None
) -> tuple[int, Clut | None, Pairing | None]:
    bpp, _blend, clut_x, clut_y, reuse, _pad = struct.unpack_from("<6h", data, pos)
    pos += 12
    clut = previous
    if bpp != DIRECT_COLOUR_BPP and not reuse:
        size = (1 << bpp) * 2
        clut = Clut(clut_x, clut_y, data[pos : pos + size])
        pos += size
    x, y, width, height = struct.unpack_from("<4h", data, pos)
    pos += 8
    size = width * height * bpp // 8
    words = data[pos : pos + size]
    pos += size + (-size % ALIGNMENT)
    if bpp == DIRECT_COLOUR_BPP or clut is None:
        return pos, clut, None
    upload = Upload(x, y, words_for_texels(width, bpp), height, bpp, words, "sprite")
    return pos, clut, Pairing(upload, clut)
