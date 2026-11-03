#!/usr/bin/env python3
"""Build the Kula World HD texture pack from the player's own disc.

    python3 -I tools/hd/build_pack.py DISC.cue WORK_DIR --install PACK_DIR [--progress FILE]

Reads only the disc image and writes below WORK_DIR; finished PNGs are kept
there, so an interrupted run continues. The pack is swapped in as a whole.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from hd.assets import Pairing  # noqa: E402
from hd.classify import classify, upscale_file  # noqa: E402
from hd.contour import check_classes  # noqa: E402
from hd.decode import decode, keys_for  # noqa: E402
from hd.ggi import read_sprites  # noqa: E402
from hd.names import Rect, TextureKey, format_name  # noqa: E402
from hd.sky import band_rects, build_sky  # noqa: E402
from hd.tgi import read_bonus_sky, read_sky, read_tiles  # noqa: E402
from hd.upscale import SCALE, Upscaler, lanczos4  # noqa: E402
from psxdisc import PVD_LBA, RAW_SECTOR, USER_DATA_OFFSET, Disc, parse_dir  # noqa: E402

TOOL_VERSION = 7
UPSCALER_NAME = "lanczos"
EXE_NAME = "/SCES_010.00"
EXE_SIZE = 604160
EXE_SHA256 = "28c8f46d28f971038ccd68135de4d5dfc0f7a1c00285748aea98276a5d37bf75"
GGI_NAME = "/HIRO/HIRO.GGI"
CUE_FILE = re.compile(r'FILE\s+"?(.+?)"?\s+\w+$', re.IGNORECASE)
ISO_MAGIC = b"CD001"
ROOT_RECORD, ROOT_RECORD_SIZE = 156, 34  # root directory record in the PVD (ISO 9660)
EXTENT_LBA, EXTENT_SIZE = 2, 10
UNSUPPORTED_FORMAT = "Disc-Format nicht unterstützt: benötigt wird ein Raw-Image (BIN/CUE, 2352 Byte pro Sektor)."
CONFIG_YAML = "ReducePaletteRange: false\n"
PROGRESS_EVERY = 25
KEPT_ON_INSTALL = "dumps"

Job = tuple[str, Callable[[], Image.Image]]


def check_disc(exe: bytes) -> None:
    if len(exe) != EXE_SIZE or hashlib.sha256(exe).hexdigest() != EXE_SHA256:
        raise SystemExit(
            "Diese Disc wird nicht unterstützt: erwartet Kula World PAL (SCES-01000)."
        )


def image_of(path: Path) -> Path:
    """The raw image behind a CUE sheet (quoted or not), else the path itself."""
    if path.suffix.lower() != ".cue":
        return path
    for line in path.read_text(errors="replace").splitlines():
        match = CUE_FILE.match(line.strip())
        if match:
            return path.parent / match[1]
    raise SystemExit(f"Keine FILE-Zeile in {path}")


def check_raw_image(image: Path) -> None:
    """Only raw 2352-byte-sector images are readable by tools/psxdisc.py."""
    with open(image, "rb") as f:
        f.seek(PVD_LBA * RAW_SECTOR + USER_DATA_OFFSET + 1)
        if f.read(len(ISO_MAGIC)) != ISO_MAGIC:
            raise SystemExit(UNSUPPORTED_FORMAT)


def disc_files(image: Path) -> dict[str, bytes]:
    """The EXE, the GGI and every TGI of the disc."""
    disc = Disc(str(image))
    root = disc.sector(PVD_LBA)[ROOT_RECORD : ROOT_RECORD + ROOT_RECORD_SIZE]
    root_lba = struct.unpack_from("<I", root, EXTENT_LBA)[0]
    root_size = struct.unpack_from("<I", root, EXTENT_SIZE)[0]
    wanted = {}
    for path, lba, size, is_dir in parse_dir(disc, root_lba, root_size):
        if not is_dir and (path in (EXE_NAME, GGI_NAME) or path.endswith(".TGI")):
            wanted[path] = disc.read(lba, size)
    return wanted


def pair_job(pair: Pairing, key: TextureKey, upscale: Upscaler) -> Job:
    def render() -> Image.Image:
        image = decode(pair.upload, pair.clut, key.semi)
        return upscale_file(image, classify(pair, image), upscale)

    return format_name(key), render


@lru_cache(maxsize=1)  # jobs run sorted by name, one world's sky after the other
def world_sky(tgi: bytes, upscale: Upscaler) -> dict[int, Image.Image]:
    """The world's filtered sky, one 4x atlas per palette (keyed by CLUT row)."""
    upload, cluts, quads = read_sky(tgi)
    # Sky is never drawn semi-transparent (decode.ST_KINDS), so plain decodes only.
    return build_sky({c.y: decode(upload, c, False) for c in cluts}, quads, upscale)


def sky_jobs(tgi: bytes, upscale: Upscaler) -> list[Job]:
    """One file per atlas row and palette: whole-atlas files overflow the runtime's decode budget."""
    upload, cluts, quads = read_sky(tgi)
    jobs: list[Job] = []
    for clut in cluts:
        for key in keys_for(Pairing(upload, clut)):
            for rect in band_rects(quads, clut.y):
                jobs.append(
                    (
                        format_name(key, rect),
                        lambda y=clut.y, r=rect: world_sky(tgi, upscale)[y].crop(
                            scaled(r)
                        ),
                    )
                )
    return jobs


def scaled(rect: Rect) -> tuple[int, int, int, int]:
    x, y, width, height = rect
    return x * SCALE, y * SCALE, (x + width) * SCALE, (y + height) * SCALE


def collect_jobs(
    files: dict[str, bytes], upscale: Upscaler
) -> dict[str, Callable[[], Image.Image]]:
    """Every file of the pack by name; worlds share names, so duplicates collapse."""
    pairs = read_sprites(files[GGI_NAME])
    jobs: list[Job] = []
    for path in sorted(p for p in files if p.endswith(".TGI")):
        pairs += read_tiles(files[path]) + read_bonus_sky(files[path])
        jobs += sky_jobs(files[path], upscale)
    jobs += [pair_job(pair, key, upscale) for pair in pairs for key in keys_for(pair)]
    return dict(jobs)


def cache_dir(work: Path, upscaler: str) -> Path:
    """Finished images per tool version and upscaler, so an update never reuses stale ones."""
    return work / f"out-v{TOOL_VERSION}-{upscaler}"


def write_progress(path: Path, step: str, done: int, total: int, state: str) -> None:
    data = {
        "step": step,
        "done": done,
        "total": total,
        "fraction": done / total if total else 1.0,
        "state": state,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


def render_all(
    jobs: dict[str, Callable[[], Image.Image]], out: Path, progress: Path | None
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for done, (name, render) in enumerate(sorted(jobs.items()), 1):
        target = out / f"{name}.png"
        if not target.exists():
            image = render()
            check_classes(image)
            image.save(target.with_suffix(".tmp.png"))
            os.replace(target.with_suffix(".tmp.png"), target)
        if progress and (done % PROGRESS_EVERY == 0 or done == len(jobs)):
            write_progress(progress, "upscale", done, len(jobs), "running")


def install(staging: Path, target: Path) -> None:
    """Swap staging in as target; the old pack stays if anything fails."""
    if not staging.is_dir():
        raise FileNotFoundError(staging)
    old = target.with_name(target.name + ".old")
    shutil.rmtree(old, ignore_errors=True)
    if target.exists():
        if (target / KEPT_ON_INSTALL).is_dir() and not (
            staging / KEPT_ON_INSTALL
        ).exists():
            shutil.copytree(target / KEPT_ON_INSTALL, staging / KEPT_ON_INSTALL)
        target.rename(old)
    try:
        staging.rename(target)
    except OSError:
        old.rename(target)
        raise
    shutil.rmtree(old, ignore_errors=True)


def stage(out: Path, staging: Path, names: list[str]) -> None:
    """Copy only this build's files; out may hold files of an older tool version."""
    shutil.rmtree(staging, ignore_errors=True)
    (staging / "replacements").mkdir(parents=True)
    for name in names:
        shutil.copy2(out / f"{name}.png", staging / "replacements" / f"{name}.png")
    (staging / "config.yaml").write_text(CONFIG_YAML)
    (staging / "hd-pack.json").write_text(
        json.dumps({"tool": TOOL_VERSION, "upscaler": UPSCALER_NAME})
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cue", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("--install", type=Path, required=True)
    parser.add_argument("--progress", type=Path)
    args = parser.parse_args()
    image = image_of(args.cue)
    try:
        check_raw_image(image)
        files = disc_files(image)
    except (OSError, struct.error, IndexError) as error:
        raise SystemExit(f"{UNSUPPORTED_FORMAT} ({error})") from error
    check_disc(files.get(EXE_NAME, b""))
    jobs = collect_jobs(files, lanczos4)
    print(f"{len(jobs)} Dateien")
    out = cache_dir(args.work, UPSCALER_NAME)
    render_all(jobs, out, args.progress)
    staging = args.install.with_name(args.install.name + ".new")
    stage(out, staging, sorted(jobs))
    install(staging, args.install)
    if args.progress:
        write_progress(args.progress, "done", len(jobs), len(jobs), "done")


if __name__ == "__main__":
    main()
