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


DEPTH_CUE_COUNT_OFFSET = 0x108
PART_MIPMAP_CLUTS = 0
PART_TEXTURE_RANGES = 5
PART_TEXTURE_ENTRIES = 6
PART_VRAM_BLOCKS = 10
SHORTS_PER_LEVEL = 5  # dark, neutral and light CLUT, then VRAM x, y
TEXTURE_LEVELS = 4  # full 64x64 P8, then three P4 mipmaps
BRIGHTNESS_LEVELS = 3
VRAM_WIDTH = 1024
VRAM_HEIGHT = 512


def part(data: bytes, index: int) -> bytes:
    start = section_offset(data, index)
    (length,) = struct.unpack_from("<i", data, SECTION_LENGTHS_OFFSET + 4 * index)
    return data[start : start + 2 * length]


def shorts(raw: bytes) -> tuple[int, ...]:
    return struct.unpack(f"<{len(raw) // 2}h", raw)


def clut_position(clut_id: int) -> tuple[int, int]:
    """GPU CLUT id to VRAM position: x in 16-word steps, y in rows."""
    return (clut_id & 0x3F) << 4, (clut_id >> 6) & 0x1FF


def vram_blocks(
    data: bytes,
) -> tuple[bytearray, dict[tuple[int, int], tuple[int, int]]]:
    """Every block of part 10 placed in a VRAM image; block sizes keyed by position."""
    vram = bytearray(VRAM_WIDTH * VRAM_HEIGHT * 2)
    sizes = {}
    raw, pos = part(data, PART_VRAM_BLOCKS), 0
    while pos < len(raw):
        x, y, w, h = struct.unpack_from("<4h", raw, pos)
        for row in range(h):
            src = pos + 8 + row * w * 2
            dst = ((y + row) * VRAM_WIDTH + x) * 2
            vram[dst : dst + w * 2] = raw[src : src + w * 2]
        sizes[(x, y)] = (w, h)
        pos += 8 + w * h * 2
    return vram, sizes


def read_tiles(data: bytes) -> list[Pairing]:
    """Block textures with every CLUT the game draws them with (decomp InitCubeTextureMetadata)."""
    vram, sizes = vram_blocks(data)
    mip_cluts = shorts(part(data, PART_MIPMAP_CLUTS))
    (fog_count,) = struct.unpack_from("<i", data, DEPTH_CUE_COUNT_OFFSET)
    entries = shorts(part(data, PART_TEXTURE_ENTRIES))
    ranges = shorts(part(data, PART_TEXTURE_RANGES))
    wanted: set[tuple[int, int, int, int]] = set()
    for first, count in zip(ranges[0::2], ranges[1::2]):
        for entry in range(first, first + count):
            for level in range(TEXTURE_LEVELS):
                base = (entry * TEXTURE_LEVELS + level) * SHORTS_PER_LEVEL
                fields = entries[base : base + SHORTS_PER_LEVEL]
                for brightness in range(BRIGHTNESS_LEVELS):
                    ids = (
                        [fields[brightness]]
                        if level == 0
                        else mip_cluts[
                            fields[brightness]
                            * fog_count : (fields[brightness] + 1)
                            * fog_count
                        ]
                    )
                    wanted.update(
                        (level, fields[3], fields[4], clut_id) for clut_id in ids
                    )
    return [pair for key in sorted(wanted) if (pair := tile_pair(vram, sizes, *key))]


def tile_pair(
    vram: bytearray,
    sizes: dict[tuple[int, int], tuple[int, int]],
    level: int,
    x: int,
    y: int,
    clut_id: int,
) -> Pairing | None:
    if (x, y) not in sizes:
        return None
    w, h = sizes[(x, y)]
    depth = 8 if level == 0 else 4
    words = b"".join(
        vram[((y + row) * VRAM_WIDTH + x) * 2 : ((y + row) * VRAM_WIDTH + x + w) * 2]
        for row in range(h)
    )
    cx, cy = clut_position(clut_id)
    start = (cy * VRAM_WIDTH + cx) * 2
    clut = Clut(cx, cy, bytes(vram[start : start + (1 << depth) * 2]))
    return Pairing(Upload(x, y, w, h, depth, words, "tile"), clut)
