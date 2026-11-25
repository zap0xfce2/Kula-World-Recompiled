"""Reproducible .tar.gz of a release stage (busybox tar has no --sort/--mtime).

Usage: make_release_tar.py STAGE_DIR OUT.tar.gz
Entries sorted, owner root, fixed mtime; only the exec bit survives from the source mode.
"""

import gzip
import sys
import tarfile
from pathlib import Path

FIXED_MTIME = 0
DIR_MODE = 0o755
EXEC_MODE = 0o755
FILE_MODE = 0o644


def normalized(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = FIXED_MTIME
    if info.isdir():
        info.mode = DIR_MODE
    elif info.isfile():
        info.mode = EXEC_MODE if info.mode & 0o111 else FILE_MODE
    return info


def write_tar(stage: Path, out: Path) -> None:
    paths = sorted(stage.rglob("*"), key=lambda p: p.relative_to(stage).as_posix())
    with out.open("wb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=FIXED_MTIME
        ) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path in paths:
                    arcname = path.relative_to(stage).as_posix()
                    tar.add(path, arcname=arcname, recursive=False, filter=normalized)


if __name__ == "__main__":
    write_tar(Path(sys.argv[1]), Path(sys.argv[2]))
