"""Kompakter R3000A-Disassembler (häufige Opcodes) für schnelle Sichtprüfungen."""
import struct
import sys

REGS = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
        "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]
I_OPS = {0x08: "addi", 0x09: "addiu", 0x0A: "slti", 0x0B: "sltiu", 0x0C: "andi", 0x0D: "ori", 0x0E: "xori"}
MEM_OPS = {0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu", 0x28: "sb", 0x29: "sh", 0x2B: "sw",
           0x32: "lwc2", 0x3A: "swc2", 0x22: "lwl", 0x26: "lwr", 0x2A: "swl", 0x2E: "swr"}
BR_OPS = {0x04: "beq", 0x05: "bne", 0x06: "blez", 0x07: "bgtz"}
R_OPS = {0x20: "add", 0x21: "addu", 0x22: "sub", 0x23: "subu", 0x24: "and", 0x25: "or", 0x26: "xor",
         0x27: "nor", 0x2A: "slt", 0x2B: "sltu", 0x04: "sllv", 0x06: "srlv", 0x07: "srav"}


def simm(w: int) -> int:
    return (w & 0xFFFF) - 0x10000 if w & 0x8000 else w & 0xFFFF


def disasm(w: int, pc: int) -> str:
    op, rs, rt, rd = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
    sa, fn = (w >> 6) & 31, w & 63
    if w == 0:
        return "nop"
    if op == 0:
        if fn in (0x00, 0x02, 0x03):
            return f"{['sll', '', 'srl', 'sra'][fn]} {REGS[rd]}, {REGS[rt]}, {sa}"
        if fn == 0x08:
            return f"jr {REGS[rs]}"
        if fn == 0x09:
            return f"jalr {REGS[rd]}, {REGS[rs]}"
        if fn in (0x10, 0x12):
            return f"{'mfhi' if fn == 0x10 else 'mflo'} {REGS[rd]}"
        if fn in (0x18, 0x19, 0x1A, 0x1B):
            return f"{['mult', 'multu', 'div', 'divu'][fn - 0x18]} {REGS[rs]}, {REGS[rt]}"
        if fn == 0x0C:
            return "syscall"
        if fn in R_OPS:
            return f"{R_OPS[fn]} {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
    if op in (2, 3):
        return f"{'j' if op == 2 else 'jal'} 0x{(pc & 0xF0000000) | ((w & 0x3FFFFFF) << 2):08X}"
    if op in BR_OPS:
        return f"{BR_OPS[op]} {REGS[rs]}, {REGS[rt]}, 0x{pc + 4 + simm(w) * 4:08X}"
    if op == 1:
        return f"{['bltz', 'bgez'][rt & 1]} {REGS[rs]}, 0x{pc + 4 + simm(w) * 4:08X}"
    if op == 0x0F:
        return f"lui {REGS[rt]}, 0x{w & 0xFFFF:04X}"
    if op in I_OPS:
        imm = w & 0xFFFF if op >= 0x0C else simm(w)
        return f"{I_OPS[op]} {REGS[rt]}, {REGS[rs]}, {imm:#x}"
    if op in MEM_OPS:
        return f"{MEM_OPS[op]} {REGS[rt]}, {simm(w):#x}({REGS[rs]})"
    if op == 0x12:
        return f"cop2 0x{w & 0x1FFFFFF:07X}" if w & (1 << 25) else f"{['mfc2', '', 'cfc2', '', 'mtc2', '', 'ctc2'][rs]} {REGS[rt]}, ${rd}"
    if op == 0x10:
        return f"{['mfc0', '', '', '', 'mtc0'][rs] if rs in (0, 4) else 'cop0'} {REGS[rt]}, ${rd}"
    return f".word 0x{w:08X}"


def main(path: str, base: int, start: int, count: int) -> None:
    data = open(path, "rb").read()[0x800:]
    for i in range(count):
        pc = start + i * 4
        w = struct.unpack_from("<I", data, pc - base)[0]
        print(f"{pc:08X}: {w:08X}  {disasm(w, pc)}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16), int(sys.argv[4]))
