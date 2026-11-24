"""Tests for textures the game builds from its EXE (synthetic EXE images, struct and zlib only)."""

import struct
import sys
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from hd.assets import Clut, Pairing, Upload
from hd.exe import (
    HOURGLASS_ANIM,
    HOURGLASS_LEVELS,
    MENU_ARCHIVES,
    exe_offset,
    hourglass_pairings,
    hourglass_palette,
    read_menu_sprites,
)
from hd.names import hash_words

EXE_BYTES = 0xA4000
ARCHIVE_ADDRESS = 0x80000
TIM_4BPP = 8
ANIM_ENTRIES = 58


def tim(width_words: int, height: int) -> bytes:
    """4-bit TIM as the menu archives hold it: 16-colour CLUT, then the pixels."""
    clut = struct.pack("<3I", 0, 0, 0) + bytes(range(32))
    pixels = struct.pack("<I4h", 0, 704, 95, width_words, height) + bytes(
        width_words * height * 2
    )
    return struct.pack("<2I", 0x10, TIM_4BPP) + clut + pixels


def exe_with_menu_archive(tims: list[bytes]) -> bytes:
    exe = bytearray(EXE_BYTES)
    blobs = [zlib.compress(t) for t in tims]
    table = 4 + 8 * len(blobs)
    entries, offset = [], table
    for blob in blobs:
        entries += [offset, len(blob)]
        offset += len(blob)
    archive = struct.pack(f"<{1 + len(entries)}I", len(blobs), *entries) + b"".join(
        blobs
    )
    exe[exe_offset(ARCHIVE_ADDRESS) : exe_offset(ARCHIVE_ADDRESS) + len(archive)] = (
        archive
    )
    struct.pack_into(
        "<I", exe, exe_offset(MENU_ARCHIVES[0]), 0x80000000 | ARCHIVE_ADDRESS
    )
    struct.pack_into(
        "<I", exe, exe_offset(MENU_ARCHIVES[1]), 0x80000000 | ARCHIVE_ADDRESS
    )
    return bytes(exe)


def exe_with_anim() -> bytes:
    exe = bytearray(EXE_BYTES)
    anim = struct.pack(f"<{ANIM_ENTRIES}H", *range(1, ANIM_ENTRIES + 1))
    exe[exe_offset(HOURGLASS_ANIM) : exe_offset(HOURGLASS_ANIM) + len(anim)] = anim
    return bytes(exe)


def source_hash(pair: Pairing) -> int:
    return hash_words(pair.upload.words)


def hourglass_sprite() -> Pairing:
    upload = Upload(512, 314, 10, 34, 8, bytes(680), "sprite")
    return Pairing(upload, Clut(768, 217, bytes(512)))


class MenuSpritesTest(unittest.TestCase):
    def test_menu_sprite_size_in_words(self) -> None:
        pairs = read_menu_sprites(exe_with_menu_archive([tim(22, 79)]))
        self.assertEqual(
            (pairs[0].upload.width_words, pairs[0].upload.height), (22, 79)
        )

    def test_menu_sprite_is_p4(self) -> None:
        pairs = read_menu_sprites(exe_with_menu_archive([tim(4, 16)]))
        self.assertEqual(pairs[0].upload.depth, 4)

    def test_menu_sprite_clut_has_16_colours(self) -> None:
        pairs = read_menu_sprites(exe_with_menu_archive([tim(4, 16)]))
        self.assertEqual(pairs[0].clut.colors, bytes(range(32)))

    def test_menu_sprite_kind_is_menu(self) -> None:
        pairs = read_menu_sprites(exe_with_menu_archive([tim(4, 16)]))
        self.assertEqual(pairs[0].upload.kind, "menu")

    def test_both_archives_are_read(self) -> None:
        pairs = read_menu_sprites(exe_with_menu_archive([tim(4, 16), tim(8, 16)]))
        self.assertEqual(len(pairs), 4)


class HourglassTest(unittest.TestCase):
    def test_empty_glass_uses_first_and_last_step(self) -> None:
        palette = hourglass_palette(exe_with_anim(), 0)
        self.assertEqual(palette[0:2] + palette[30:32], [1, 2, 55, 56])

    def test_full_glass_has_sand_only_above(self) -> None:
        palette = hourglass_palette(exe_with_anim(), HOURGLASS_LEVELS - 1)
        self.assertEqual(palette[28:30] + palette[58:60], [57, 58, 1, 2])

    def test_palette_has_60_entries(self) -> None:
        self.assertEqual(len(hourglass_palette(exe_with_anim(), 200)), 60)

    def test_one_pairing_per_sand_level(self) -> None:
        sprite = hourglass_sprite()
        pairs = hourglass_pairings(exe_with_anim(), [sprite], source_hash(sprite))
        self.assertEqual(len(pairs), HOURGLASS_LEVELS)

    def test_pairing_keeps_entries_past_60(self) -> None:
        sprite = hourglass_sprite()
        pairs = hourglass_pairings(exe_with_anim(), [sprite], source_hash(sprite))
        self.assertEqual(pairs[0].clut.colors[120:], bytes(392))

    def test_other_sprites_get_no_variants(self) -> None:
        self.assertEqual(hourglass_pairings(exe_with_anim(), [hourglass_sprite()]), [])


if __name__ == "__main__":
    unittest.main()
