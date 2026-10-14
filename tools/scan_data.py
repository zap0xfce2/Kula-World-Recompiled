"""Durchsucht Disc-Dateien (inkl. entpackter PAK-Einträge) nach MIPS-Code-Signaturen."""
import os
import struct
import sys
import zlib

JR_RA = 0x03E00008
STACK_ALLOC_MASK, STACK_ALLOC = 0xFFFF8000, 0x27BD8000  # addiu sp, sp, -N


def code_score(blob: bytes) -> tuple[int, int]:
    n = len(blob) // 4
    ws = struct.unpack(f"<{n}I", blob[:n * 4])
    return sum(w == JR_RA for w in ws), sum((w & STACK_ALLOC_MASK) == STACK_ALLOC for w in ws)


def pak_entries(blob: bytes):
    count = struct.unpack_from("<I", blob, 0)[0]
    if not 0 < count < 1000:
        return
    for i in range(count):
        off, size = struct.unpack_from("<II", blob, 4 + i * 8)
        name_off = struct.unpack_from("<I", blob, 4 + count * 8 + i * 4)[0]
        name = blob[name_off:blob.index(b"\n", name_off)].decode(errors="replace")
        yield name, zlib.decompress(blob[off:off + size])


def main(root: str) -> None:
    for dirpath, _, files in sorted(os.walk(root)):
        for fn in sorted(files):
            path = os.path.join(dirpath, fn)
            if fn.endswith((".XA", ".STR")) or fn == "3.00" or fn.startswith("SCES"):
                continue
            blob = open(path, "rb").read()
            jr, alloc = code_score(blob)
            flag = "  <-- CODE?" if jr > 5 and alloc > 5 else ""
            print(f"{os.path.relpath(path, root):24s} {len(blob):8d}  jr_ra={jr:4d} stack_alloc={alloc:4d}{flag}")
            if fn.endswith(".PAK"):
                for name, data in pak_entries(blob):
                    jr, alloc = code_score(data)
                    if jr or alloc or len(data) != 0x13310 + 0:
                        pass
                    if jr > 2 and alloc > 2:
                        print(f"    {name:16s} {len(data):7d}  jr_ra={jr} stack_alloc={alloc}  <-- CODE?")


if __name__ == "__main__":
    main(sys.argv[1])
