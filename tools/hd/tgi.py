"""Theme files <WORLD>.TGI (layout: wiki.kula.quest, graphics/tgi).

Section lengths in the header count 16-bit halfwords.
"""

import struct

from hd.assets import Clut, Pairing, SkyQuad, Upload

HEADER_SIZE = 0x190
SECTION_LENGTHS_OFFSET = 0x164
SECTIONS_BEFORE_TIM = 8
SECTIONS_BEFORE_SKY = 9
SKY_QUADS = 1152
QUADS_PER_BAND = 48
SKY_CLUTS = 24
SKY_CLUT_COLORS = 256
SKY_PAGE_X = 640
TEXELS_PER_WORD_8BPP = 2
TIM_MAGIC = 0x10
TIM_HAS_CLUT = 0x8
TIM_DEPTH = {0: 4, 1: 8}


def section_offset(data: bytes, sections_before: int) -> int:
    lengths = struct.unpack_from(f"<{sections_before}i", data, SECTION_LENGTHS_OFFSET)
    return HEADER_SIZE + 2 * sum(lengths)


def read_sky(data: bytes) -> tuple[Upload, list[Clut], list[SkyQuad]]:
    """Sky atlas upload, its 24 CLUTs and the 1152 quads in band order."""
    pos = section_offset(data, SECTIONS_BEFORE_SKY)
    quads = [read_sky_quad(data, pos + 14 * i, i) for i in range(SKY_QUADS)]
    pos += 14 * SKY_QUADS
    cluts = []
    for _ in range(SKY_CLUTS):
        x, y, _w, _h = struct.unpack_from("<4h", data, pos)
        cluts.append(Clut(x, y, data[pos + 8 : pos + 8 + SKY_CLUT_COLORS * 2]))
        pos += 8 + SKY_CLUT_COLORS * 2
    x, y, width, height = struct.unpack_from("<4h", data, pos)
    words = data[pos + 8 : pos + 8 + width * height * 2]
    return Upload(x, y, width, height, 8, words, "sky"), cluts, quads


def read_sky_quad(data: bytes, pos: int, index: int) -> SkyQuad:
    _clut_x, clut_y, page_x, _page_y, tex_x, tex_y, stride = struct.unpack_from(
        "<7h", data, pos
    )
    atlas_x = (page_x - SKY_PAGE_X) * TEXELS_PER_WORD_8BPP + tex_x
    return SkyQuad(index // QUADS_PER_BAND, clut_y, atlas_x, tex_y, stride)


def read_bonus_sky(data: bytes) -> list[Pairing]:
    """Bonus-level sky TIM: its image paired with every CLUT row."""
    return read_tim(data, section_offset(data, SECTIONS_BEFORE_TIM), "bonus_sky")


def read_tim(data: bytes, pos: int, kind: str) -> list[Pairing]:
    magic, flags = struct.unpack_from("<2I", data, pos)
    if magic != TIM_MAGIC or not flags & TIM_HAS_CLUT or flags & 7 not in TIM_DEPTH:
        return []
    depth = TIM_DEPTH[flags & 7]
    pos += 8
    clut_len, cx, cy, cw, ch = struct.unpack_from("<I4H", data, pos)
    cluts = [
        Clut(
            cx, cy + row, data[pos + 12 + row * cw * 2 : pos + 12 + (row + 1) * cw * 2]
        )
        for row in range(ch)
    ]
    pos += clut_len
    _len, x, y, w, h = struct.unpack_from("<I4H", data, pos)
    upload = Upload(x, y, w, h, depth, data[pos + 12 : pos + 12 + w * h * 2], kind)
    return [Pairing(upload, clut) for clut in cluts]
