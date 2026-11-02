#!/usr/bin/env python3
"""Check an offline HD pack against runtime dumps of the same disc.

    python3 -I tools/hd/verify_pack.py PACK_DIR DUMP_DIR

Dumps must be taken with `ReducePaletteRange: false`; reduced names are
counted but not compared, their palette hash covers only part of the palette.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hd.names import NAME_PATTERN, PALETTE_MAX, TextureKey, parse_name  # noqa: E402


def dump_key(name: str) -> TextureKey | None:
    """Key of a full-range dump name; its sub-rect is ignored (pack files cover the upload)."""
    match = NAME_PATTERN.fullmatch(name)
    if not match:
        return None
    depth = int(match[2])
    if (int(match[11]), int(match[12])) != (0, PALETTE_MAX[depth]):
        return None
    return TextureKey(
        depth,
        match[1] is not None,
        int(match[3], 16),
        int(match[4], 16),
        int(match[5]),
        int(match[6]),
    )


def coverage(
    pack: set[TextureKey], dumped: set[TextureKey]
) -> tuple[set[TextureKey], set[TextureKey]]:
    return dumped & pack, dumped - pack


def png_names(folder: Path) -> list[str]:
    return [p.name for p in folder.rglob("*.png")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pack", type=Path)
    parser.add_argument("dumps", type=Path)
    args = parser.parse_args()
    pack = {k for n in png_names(args.pack / "replacements") if (k := parse_name(n))}
    names = png_names(args.dumps)
    dumped = {k for n in names if (k := dump_key(n))}
    covered, missing = coverage(pack, dumped)
    print(
        f"Pack: {len(pack)} Dateien, Dumps: {len(names)} ({len(names) - len(dumped)} ohne vollen Palettenbereich)"
    )
    print(f"Abgedeckt: {len(covered)} von {len(dumped)}")
    for key in sorted(missing, key=lambda k: (k.depth, k.source_hash)):
        print(
            f"fehlt: {'ST' if key.semi else ''}P{key.depth} {key.source_hash:016X} {key.palette_hash:016X} {key.width_words}x{key.height}"
        )


if __name__ == "__main__":
    main()
