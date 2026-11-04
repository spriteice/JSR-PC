import sys, pefile, re
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM
pe = pefile.PE(sys.argv[1]); base = pe.OPTIONAL_HEADER.ImageBase
t = next(s for s in pe.sections if s.Name.startswith(b".text")); code = t.get_data()[:t.Misc_VirtualSize]
tva = base + t.VirtualAddress; tend = tva + len(code)
md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True; md.skipdata = True
calls = set(); jmpt = set()
for i in md.disasm(code, tva):
    if i.mnemonic in ("call","jmp") and i.operands and i.operands[0].type == X86_OP_IMM and tva <= i.operands[0].imm < tend:
        (calls if i.mnemonic=="call" else jmpt).add(i.operands[0].imm)
ptrs = set()
for blk in pe.DIRECTORY_ENTRY_BASERELOC:
    for e in blk.entries:
        if e.type and not t.contains_rva(e.rva):
            v = pe.get_dword_at_rva(e.rva)
            if tva <= v < tend: ptrs.add(v)
pro = (b"\x55\x8b\xec", b"\x53", b"\x56", b"\x57", b"\x83\xec", b"\x81\xec", b"\x51", b"\x8b\x44\x24", b"\x8b\x4c\x24", b"\x6a", b"\x68", b"\xa1", b"\x0f\x57", b"\xf3\x0f", b"\xd9", b"\x8b\x0d", b"\xb8", b"\xe8", b"\xe9", b"\xc3", b"\x33\xc0", b"\x8b\x54\x24", b"\x8b\x81", b"\x8b\x41")
pad = set()
for m in re.finditer(rb"\xcc+", code):
    a = tva + m.end()
    if a % 16 == 0 and m.end() < len(code) and code[m.end():m.end()+3].startswith(pro): pad.add(a)
known = calls | ptrs
print("calls", len(calls), "fnptrs", len(ptrs), "known", len(known), "pad-starts w/ prologue", len(pad), "pad-only (no xref)", len(pad - known - jmpt), "total est", len(known | pad))
