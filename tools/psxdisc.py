"""Minimaler ISO9660-Reader für PS1-Raw-Images (MODE2/2352) mit Extraktion."""
import os
import struct
import sys

RAW_SECTOR = 2352
USER_DATA_OFFSET = 24  # 12 Sync + 4 Header + 8 Subheader (Mode 2 Form 1)
USER_DATA_SIZE = 2048
PVD_LBA = 16


class Disc:
    def __init__(self, path: str):
        self.f = open(path, "rb")

    def sector(self, lba: int) -> bytes:
        self.f.seek(lba * RAW_SECTOR + USER_DATA_OFFSET)
        return self.f.read(USER_DATA_SIZE)

    def read(self, lba: int, size: int) -> bytes:
        count = (size + USER_DATA_SIZE - 1) // USER_DATA_SIZE
        return b"".join(self.sector(lba + i) for i in range(count))[:size]

    def subheader(self, lba: int) -> bytes:
        self.f.seek(lba * RAW_SECTOR + 16)
        return self.f.read(8)


def parse_dir(disc: Disc, lba: int, size: int, prefix: str = ""):
    data = disc.read(lba, size)
    pos = 0
    while pos < len(data):
        rec_len = data[pos]
        if rec_len == 0:  # Rest des Sektors ist Padding
            pos = (pos // USER_DATA_SIZE + 1) * USER_DATA_SIZE
            continue
        ext_lba = struct.unpack_from("<I", data, pos + 2)[0]
        ext_size = struct.unpack_from("<I", data, pos + 10)[0]
        is_dir = bool(data[pos + 25] & 2)
        name_len = data[pos + 32]
        name = data[pos + 33:pos + 33 + name_len]
        pos += rec_len
        if name in (b"\x00", b"\x01"):  # "." und ".."
            continue
        path = prefix + "/" + name.decode("ascii").split(";")[0]
        yield path, ext_lba, ext_size, is_dir
        if is_dir:
            yield from parse_dir(disc, ext_lba, ext_size, path)


def main(image: str, out_dir: str | None) -> None:
    disc = Disc(image)
    pvd = disc.sector(PVD_LBA)
    assert pvd[1:6] == b"CD001", "kein ISO9660"
    root = pvd[156:156 + 34]
    root_lba, root_size = struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0]
    print(f"Volume: {pvd[40:72].decode().strip()}")
    for path, lba, size, is_dir in parse_dir(disc, root_lba, root_size):
        form2 = bool(disc.subheader(lba)[2] & 0x20) if not is_dir else False
        print(f"{'D' if is_dir else 'F'} LBA={lba:6d} {size:10d}  {path}{'  [Form2/XA]' if form2 else ''}")
        if out_dir and not is_dir and not form2:
            target = os.path.join(out_dir, path.lstrip("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as out:
                out.write(disc.read(lba, size))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
