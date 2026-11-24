"""Textures the game builds at runtime from data in its EXE (SCES_010.00).

Addresses from the dezgeg decomp (config/eu-SCES_010.00/variable_addrs.txt);
no EXE bytes live in this repository, they are read from the player's disc.
"""

import struct
import zlib

from hd.assets import Clut, Pairing, Upload
from hd.names import hash_words

EXE_LOAD_ADDRESS = 0x11000
EXE_HEADER_BYTES = 0x800
ADDRESS_MASK = 0x1FFFFF  # KSEG0 pointer to EXE address

# MENU_DEFLATED_SPRITES1/2_PTR: zlib TIMs for menu and level-end graphics (menu_widgets.c, level_end_screen.c)
MENU_ARCHIVES = (0x74C48, 0x74C4C)
TIM_FLAGS, TIM_CLUT, TIM_SIZE, TIM_PIXELS = 0x04, 0x14, 0x3C, 0x40
TIM_4BPP_CLUT = 8
P4_CLUT_BYTES = 32

# UpdateStaticHourglassClut (hud.c): the sand level is written into the first 60 CLUT entries
HOURGLASS_ANIM = 0xA2BE4  # HOURGLASS_ANIM_DATA, 58 colours
# The GGI sprite drawn with that CLUT (20x34 P8)
HOURGLASS_SOURCE_HASH = 0x3FF7BF27252612DA
HOURGLASS_ENTRIES = 60
HOURGLASS_STEPS = 28
HOURGLASS_PAIRS = 15
# amount = levelTimeLeft * 420 / 5000; 420 and up all draw a full glass
HOURGLASS_LEVELS = 421
WORD_BYTES = 2


def exe_offset(address: int) -> int:
    return address - EXE_LOAD_ADDRESS + EXE_HEADER_BYTES


def read_menu_sprites(exe: bytes) -> list[Pairing]:
    pairs: list[Pairing] = []
    for pointer in MENU_ARCHIVES:
        pairs += [tim_pairing(tim) for tim in archive_tims(exe, pointer)]
    return pairs


def archive_tims(exe: bytes, pointer: int) -> list[bytes]:
    """Archive: count, then (offset from the archive start, length) per zlib stream."""
    (address,) = struct.unpack_from("<I", exe, exe_offset(pointer))
    base = exe_offset(address & ADDRESS_MASK)
    (count,) = struct.unpack_from("<I", exe, base)
    tims = []
    for index in range(count):
        offset, length = struct.unpack_from("<2I", exe, base + 4 + index * 8)
        tim = zlib.decompress(exe[base + offset : base + offset + length])
        if struct.unpack_from("<I", tim, TIM_FLAGS)[0] == TIM_4BPP_CLUT:
            tims.append(tim)
    return tims


def tim_pairing(tim: bytes) -> Pairing:
    x, y, width_words, height = struct.unpack_from("<4h", tim, TIM_SIZE - 4)
    words = tim[TIM_PIXELS : TIM_PIXELS + width_words * height * WORD_BYTES]
    clut = Clut(0, 0, tim[TIM_CLUT : TIM_CLUT + P4_CLUT_BYTES])
    return Pairing(Upload(x, y, width_words, height, 4, words, "menu"), clut)


def hourglass_palette(exe: bytes, amount: int) -> list[int]:
    """The 60 entries the game uploads for one sand level, top half then bottom half."""
    anim = struct.unpack_from(
        f"<{HOURGLASS_STEPS * 2 + 2}H", exe, exe_offset(HOURGLASS_ANIM)
    )
    full, part = divmod(amount, HOURGLASS_STEPS)
    top = [anim[56:58]] * full + [anim[part * 2 : part * 2 + 2]]
    bottom = [anim[0:2]] * full + [anim[(27 - part) * 2 : (27 - part) * 2 + 2]]
    top += [anim[0:2]] * HOURGLASS_PAIRS
    bottom += [anim[56:58]] * HOURGLASS_PAIRS
    return flatten(top) + flatten(bottom)


def flatten(pairs: list[tuple[int, ...]]) -> list[int]:
    """The first 15 colour pairs; the game writes past them, but uploads only 60 entries."""
    return [color for pair in pairs[:HOURGLASS_PAIRS] for color in pair]


def hourglass_pairings(
    exe: bytes, sprites: list[Pairing], source_hash: int = HOURGLASS_SOURCE_HASH
) -> list[Pairing]:
    """The hourglass sprite once per sand level, its GGI CLUT behind the first 60 entries."""
    sprite = next(
        (p for p in sprites if hash_words(p.upload.words) == source_hash), None
    )
    if sprite is None:
        return []
    rest = sprite.clut.colors[HOURGLASS_ENTRIES * WORD_BYTES :]
    pairs = []
    for amount in range(HOURGLASS_LEVELS):
        head = struct.pack(f"<{HOURGLASS_ENTRIES}H", *hourglass_palette(exe, amount))
        pairs.append(
            Pairing(sprite.upload, Clut(sprite.clut.x, sprite.clut.y, head + rest))
        )
    return pairs
