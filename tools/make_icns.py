"""Pack square PNG renders into a macOS .icns (PNG-compressed entries, stdlib only).

Usage: make_icns.py OUT.icns 16.png 32.png 128.png 256.png 512.png 1024.png
"""

import struct
import sys
from pathlib import Path

# OSType per pixel size for PNG payloads (1024 is the 512@2x slot)
ICNS_TYPES = {16: b"icp4", 32: b"icp5", 128: b"ic07", 256: b"ic08", 512: b"ic09", 1024: b"ic10"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
HEADER_BYTES = 8


def png_size(data: bytes) -> int:
    """Width of a square PNG, from its IHDR chunk."""
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    if width != height:
        raise ValueError(f"PNG is not square: {width}x{height}")
    return width


def build_icns(pngs: list[bytes]) -> bytes:
    entries = b""
    for data in pngs:
        size = png_size(data)
        if size not in ICNS_TYPES:
            raise ValueError(f"no icns slot for {size}px")
        entries += ICNS_TYPES[size] + struct.pack(">I", HEADER_BYTES + len(data)) + data
    return b"icns" + struct.pack(">I", HEADER_BYTES + len(entries)) + entries


def main() -> None:
    out, *sources = sys.argv[1:]
    Path(out).write_bytes(build_icns([Path(src).read_bytes() for src in sources]))


if __name__ == "__main__":
    main()
