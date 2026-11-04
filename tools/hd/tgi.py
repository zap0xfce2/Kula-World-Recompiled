"""Theme files <WORLD>.TGI (layout: wiki.kula.quest, graphics/tgi; decomp src/tgi.c).

Section lengths in the header count 16-bit halfwords.
"""

import struct

from hd.assets import Clut, Pairing, SkyQuad, Upload

WORD_BYTES = 2
RECT_BYTES = 8  # x, y, w, h as i16
HEADER_SIZE = 0x190
DEPTH_CUE_COUNT_OFFSET = 0x108
SECTION_LENGTHS_OFFSET = 0x164
SECTIONS_BEFORE_TIM = 8
SECTIONS_BEFORE_SKY = 9
PART_MIPMAP_CLUTS = 0
PART_TEXTURE_RANGES = 5
PART_TEXTURE_ENTRIES = 6
PART_VRAM_BLOCKS = 10

SKY_QUADS = 1152
SKY_QUAD_BYTES = 14
QUADS_PER_BAND = 48
SKY_CLUTS = 24
SKY_CLUT_COLORS = 256
SKY_PAGE_X = 640
SKY_DEPTH = 8
TEXELS_PER_WORD_8BPP = 2

TIM_MAGIC = 0x10
TIM_HAS_CLUT = 0x8
TIM_DEPTH_MASK = 0x7
TIM_DEPTH = {0: 4, 1: 8}
TIM_HEADER_BYTES = 8
TIM_BLOCK_HEADER_BYTES = 12

SHORTS_PER_LEVEL = 5  # dark, neutral and light CLUT, then VRAM x, y
FIELD_X, FIELD_Y = 3, 4
TEXTURE_LEVELS = 4  # full 64x64 P8, then three P4 mipmaps
FULL_LEVEL = 0
BRIGHTNESS_LEVELS = 3
VRAM_WIDTH = 1024
VRAM_HEIGHT = 512
CLUT_X_MASK, CLUT_X_SHIFT, CLUT_Y_SHIFT, CLUT_Y_MASK = 0x3F, 4, 6, 0x1FF

TileKey = tuple[int, int, int, int]  # level, x, y, clut id
Blocks = dict[tuple[int, int], tuple[int, int]]


def section_offset(data: bytes, sections_before: int) -> int:
    lengths = struct.unpack_from(f"<{sections_before}i", data, SECTION_LENGTHS_OFFSET)
    return HEADER_SIZE + WORD_BYTES * sum(lengths)


def part(data: bytes, index: int) -> bytes:
    start = section_offset(data, index)
    (length,) = struct.unpack_from("<i", data, SECTION_LENGTHS_OFFSET + 4 * index)
    return data[start : start + WORD_BYTES * length]


def shorts(raw: bytes) -> tuple[int, ...]:
    return struct.unpack(f"<{len(raw) // WORD_BYTES}h", raw)


def read_sky(data: bytes) -> tuple[Upload, list[Clut], list[SkyQuad]]:
    """Sky atlas upload, its 24 CLUTs and the 1152 quads in band order."""
    pos = section_offset(data, SECTIONS_BEFORE_SKY)
    quads = [read_sky_quad(data, pos + SKY_QUAD_BYTES * i, i) for i in range(SKY_QUADS)]
    pos += SKY_QUAD_BYTES * SKY_QUADS
    clut_bytes = SKY_CLUT_COLORS * WORD_BYTES
    cluts = []
    for _ in range(SKY_CLUTS):
        x, y, _w, _h = struct.unpack_from("<4h", data, pos)
        cluts.append(Clut(x, y, data[pos + RECT_BYTES : pos + RECT_BYTES + clut_bytes]))
        pos += RECT_BYTES + clut_bytes
    x, y, width, height = struct.unpack_from("<4h", data, pos)
    words = data[pos + RECT_BYTES : pos + RECT_BYTES + width * height * WORD_BYTES]
    return Upload(x, y, width, height, SKY_DEPTH, words, "sky"), cluts, quads


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
    mode = flags & TIM_DEPTH_MASK
    if magic != TIM_MAGIC or not flags & TIM_HAS_CLUT or mode not in TIM_DEPTH:
        return []
    pos += TIM_HEADER_BYTES
    clut_len, cx, cy, cw, ch = struct.unpack_from("<I4H", data, pos)
    row_bytes = cw * WORD_BYTES
    first = pos + TIM_BLOCK_HEADER_BYTES
    cluts = [
        Clut(
            cx, cy + row, data[first + row * row_bytes : first + (row + 1) * row_bytes]
        )
        for row in range(ch)
    ]
    pos += clut_len
    _len, x, y, w, h = struct.unpack_from("<I4H", data, pos)
    start = pos + TIM_BLOCK_HEADER_BYTES
    upload = Upload(
        x, y, w, h, TIM_DEPTH[mode], data[start : start + w * h * WORD_BYTES], kind
    )
    return [Pairing(upload, clut) for clut in cluts]


def clut_position(clut_id: int) -> tuple[int, int]:
    """GPU CLUT id to VRAM position: x in 16-word steps, y in rows."""
    x = (clut_id & CLUT_X_MASK) << CLUT_X_SHIFT
    return x, (clut_id >> CLUT_Y_SHIFT) & CLUT_Y_MASK


def vram_blocks(data: bytes) -> tuple[bytearray, Blocks]:
    """Every block of part 10 placed in a VRAM image; block sizes keyed by position."""
    vram = bytearray(VRAM_WIDTH * VRAM_HEIGHT * WORD_BYTES)
    sizes: Blocks = {}
    raw, pos = part(data, PART_VRAM_BLOCKS), 0
    while pos < len(raw):
        x, y, w, h = struct.unpack_from("<4h", raw, pos)
        for row in range(h):
            src = pos + RECT_BYTES + row * w * WORD_BYTES
            dst = ((y + row) * VRAM_WIDTH + x) * WORD_BYTES
            vram[dst : dst + w * WORD_BYTES] = raw[src : src + w * WORD_BYTES]
        sizes[(x, y)] = (w, h)
        pos += RECT_BYTES + w * h * WORD_BYTES
    return vram, sizes


def level_keys(
    fields: tuple[int, ...], level: int, mip_cluts: tuple[int, ...], fog_count: int
) -> set[TileKey]:
    """The full tile uses one CLUT per brightness, a mipmap a whole fog range of them."""
    keys = set()
    for brightness in range(BRIGHTNESS_LEVELS):
        group = fields[brightness]
        ids = (
            [group]
            if level == FULL_LEVEL
            else mip_cluts[group * fog_count : (group + 1) * fog_count]
        )
        keys.update(
            (level, fields[FIELD_X], fields[FIELD_Y], clut_id) for clut_id in ids
        )
    return keys


def read_tiles(data: bytes) -> list[Pairing]:
    """Block textures with every CLUT the game draws them with (decomp InitCubeTextureMetadata)."""
    vram, sizes = vram_blocks(data)
    mip_cluts = shorts(part(data, PART_MIPMAP_CLUTS))
    (fog_count,) = struct.unpack_from("<i", data, DEPTH_CUE_COUNT_OFFSET)
    entries = shorts(part(data, PART_TEXTURE_ENTRIES))
    ranges = shorts(part(data, PART_TEXTURE_RANGES))
    wanted: set[TileKey] = set()
    for first, count in zip(ranges[0::2], ranges[1::2]):
        for index in range(first * TEXTURE_LEVELS, (first + count) * TEXTURE_LEVELS):
            fields = entries[index * SHORTS_PER_LEVEL : (index + 1) * SHORTS_PER_LEVEL]
            wanted |= level_keys(fields, index % TEXTURE_LEVELS, mip_cluts, fog_count)
    return [pair for key in sorted(wanted) if (pair := tile_pair(vram, sizes, *key))]


def tile_pair(
    vram: bytearray, sizes: Blocks, level: int, x: int, y: int, clut_id: int
) -> Pairing | None:
    if (x, y) not in sizes:
        return None
    w, h = sizes[(x, y)]
    depth = 8 if level == FULL_LEVEL else 4
    words = b"".join(
        vram[
            ((y + row) * VRAM_WIDTH + x)
            * WORD_BYTES : ((y + row) * VRAM_WIDTH + x + w)
            * WORD_BYTES
        ]
        for row in range(h)
    )
    cx, cy = clut_position(clut_id)
    start = (cy * VRAM_WIDTH + cx) * WORD_BYTES
    clut = Clut(cx, cy, bytes(vram[start : start + (1 << depth) * WORD_BYTES]))
    return Pairing(Upload(x, y, w, h, depth, words, "tile"), clut)
