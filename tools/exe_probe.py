"""Voranalyse eines PS-X EXE: Header, Funktions-Seeds, BIOS-Calls, Strings, Indizien für Overlays."""
import re
import struct
import sys
from collections import Counter

HEADER_SIZE = 0x800
JR_RA = 0x03E00008
RAM_END = 0x80200000


def load(path: str):
    data = open(path, "rb").read()
    assert data[:8] == b"PS-X EXE"
    pc, gp, text_addr, text_size = struct.unpack_from("<4I", data, 0x10)
    bss_addr, bss_size, sp_base, sp_off = struct.unpack_from("<4I", data, 0x28)
    region = data[0x4C:0x80].split(b"\0")[0].decode(errors="replace")
    body = data[HEADER_SIZE:HEADER_SIZE + text_size]
    return dict(pc=pc, gp=gp, text=text_addr, size=text_size, bss=bss_addr,
                bss_size=bss_size, sp=sp_base, region=region, body=body)


def words(body: bytes):
    return struct.unpack(f"<{len(body) // 4}I", body[:len(body) // 4 * 4])


def jal_targets(ws, base: int, size: int) -> Counter:
    targets = Counter()
    for w in ws:
        if w >> 26 == 3:  # jal
            t = (base & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
            if base <= t < base + size:
                targets[t] += 1
    return targets


def prologue_starts(ws, base: int) -> set[int]:
    """addiu sp,sp,-N nach jr ra (+Delay-Slot) = typischer GCC-Funktionsanfang."""
    starts = set()
    for i, w in enumerate(ws):
        is_stack_alloc = (w & 0xFFFF0000) == 0x27BD0000 and (w & 0x8000)
        if is_stack_alloc and i >= 2 and ws[i - 2] == JR_RA:
            starts.add(base + i * 4)
    return starts


def bios_calls(ws) -> Counter:
    """li t1, N ; jr t2  mit t2 = 0xA0/0xB0/0xC0 -> PsyQ-BIOS-Stubs."""
    calls = Counter()
    for i in range(len(ws) - 2):
        a, b, c = ws[i], ws[i + 1], ws[i + 2]
        if (a & 0xFFFF0000) == 0x240A0000 and b == 0x01400008 and (c & 0xFFFF0000) == 0x24090000:
            calls[f"{a & 0xFF:02X}h:{c & 0xFF:02X}h"] += 1
    return calls


def lui_ram_refs(ws) -> Counter:
    """Obere Adresshälften aus lui -> zeigt, welche RAM-Bereiche der Code anfasst."""
    his = Counter()
    for w in ws:
        if w >> 26 == 0x0F:
            imm = w & 0xFFFF
            if 0x8000 <= imm <= 0x801F:
                his[imm] += 1
    return his


def strings(body: bytes, min_len: int = 6):
    return [(m.start(), m.group().decode()) for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, body)]


def main(path: str) -> None:
    exe = load(path)
    ws = words(exe["body"])
    base, size = exe["text"], exe["size"]
    end = base + size
    print(f"Region     : {exe['region']}")
    print(f"Entry PC   : 0x{exe['pc']:08X}   GP: 0x{exe['gp']:08X}")
    print(f"Text       : 0x{base:08X}-0x{end:08X} ({size / 1024:.0f} KB)")
    print(f"BSS        : 0x{exe['bss']:08X} +0x{exe['bss_size']:X}   SP: 0x{exe['sp']:08X}")
    print(f"Frei RAM   : 0x{max(end, exe['bss'] + exe['bss_size']):08X}-0x{RAM_END:08X}")

    jals = jal_targets(ws, base, size)
    pro = prologue_starts(ws, base)
    print(f"\njr ra      : {sum(1 for w in ws if w == JR_RA)}")
    print(f"JAL-Ziele  : {len(jals)}  Prolog-Starts: {len(pro)}  Union: {len(set(jals) | pro)}")
    print("Top-Callees:", ", ".join(f"0x{a:08X}x{n}" for a, n in jals.most_common(12)))

    print("\nBIOS-Stubs (Tabelle:Funktion -> Anzahl):", dict(bios_calls(ws)))

    his = lui_ram_refs(ws)
    print("\nlui-Hi-Words (RAM-Bereiche, die der Code adressiert):")
    print("  " + ", ".join(f"0x{h:04X}:{n}" for h, n in sorted(his.items())))

    jalr = sum(1 for w in ws if (w & 0xFC1FFFFF) == 0x00000009 or (w & 0xFC00003F) == 0x00000009)
    print(f"\njalr (indirekte Calls): {jalr}   jr <reg≠ra> (Switch/Tailcalls): "
          f"{sum(1 for w in ws if (w & 0xFC1FFFFF) == 0x00000008 and w != JR_RA)}")

    strs = strings(exe["body"])
    print(f"\nStrings: {len(strs)}")
    keys = re.compile(r"(?i)psy|sony|lib|ver|\.c\b|cdrom|\.pak|\.tgi|\.ggi|\.sfx|\.xa|\.str|\.exe|\.bin|"
                      r"error|inflate|deflate|zlib|copyright|level|load|ovl|over")
    for off, s in strs:
        if keys.search(s):
            print(f"  0x{base + off:08X}  {s[:90]}")

    with open(path + ".seeds.txt", "w") as out:
        out.write("# JAL-Ziele + Prolog-Heuristik (Rohkandidaten, nicht verifiziert)\n")
        out.writelines(f"0x{a:08X}\n" for a in sorted(set(jals) | pro))


if __name__ == "__main__":
    main(sys.argv[1])
