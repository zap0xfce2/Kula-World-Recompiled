"""DuckStation-format texture names as the psxrecomp runtime looks them up.

Format: duck_texture_format_name in psxrecomp/runtime/src/duckstation_texture_pack.cpp.
Only full-upload rects and full palette ranges are produced: reduced ranges
collide because the runtime hashes the first N palette entries, not min..max.
"""

import re
from dataclasses import dataclass

import xxhash

TEXELS_PER_WORD = {4: 4, 8: 2}
PALETTE_MAX = {4: 15, 8: 255}
NAME_PATTERN = re.compile(
    r"texupload-(ST)?P(4|8)-([0-9A-F]{16})-([0-9A-F]{16})-(\d+)x(\d+)"
    r"-(\d+)-(\d+)-(\d+)x(\d+)-P(\d+)-(\d+)(?:\.png)?"
)


@dataclass(frozen=True)
class TextureKey:
    depth: int  # 4 or 8 bits per texel
    semi: bool
    source_hash: int
    palette_hash: int
    width_words: int
    height: int


def hash_words(words: bytes) -> int:
    """Unseeded XXH3-64 over little-endian 16-bit words, as the runtime hashes."""
    return xxhash.xxh3_64_intdigest(words)


def texel_width(key: TextureKey) -> int:
    return key.width_words * TEXELS_PER_WORD[key.depth]


def format_name(key: TextureKey) -> str:
    """Name without extension, covering the whole upload."""
    mode = ("ST" if key.semi else "") + f"P{key.depth}"
    return (
        f"texupload-{mode}-{key.source_hash:016X}-{key.palette_hash:016X}"
        f"-{key.width_words}x{key.height}-0-0-{texel_width(key)}x{key.height}"
        f"-P0-{PALETTE_MAX[key.depth]}"
    )


def parse_name(name: str) -> TextureKey | None:
    """Key of a full-upload, full-range name, else None."""
    match = NAME_PATTERN.fullmatch(name)
    if not match:
        return None
    key = TextureKey(
        depth=int(match[2]),
        semi=match[1] is not None,
        source_hash=int(match[3], 16),
        palette_hash=int(match[4], 16),
        width_words=int(match[5]),
        height=int(match[6]),
    )
    return key if format_name(key) == name.removesuffix(".png") else None
