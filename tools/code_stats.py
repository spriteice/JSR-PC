"""Rough code-structure stats for a 32-bit PE: call targets, relocations, indirect branches, x87/SSE use."""
import sys, pefile, collections
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_GRP_JUMP
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

pe = pefile.PE(sys.argv[1])
base = pe.OPTIONAL_HEADER.ImageBase
text = next(s for s in pe.sections if s.Name.startswith(b".text"))
code = text.get_data()[: text.Misc_VirtualSize]
tva = base + text.VirtualAddress
tend = tva + len(code)

# relocations: which ones point into .text (function pointers / jump tables) vs data
rel_total = 0; rel_into_text = 0; rel_from_text = 0; rel_from_data_into_text = 0
for blk in pe.DIRECTORY_ENTRY_BASERELOC:
    for e in blk.entries:
        if e.type == 0: continue
        rel_total += 1
        val = pe.get_dword_at_rva(e.rva)
        from_text = text.contains_rva(e.rva)
        into_text = tva <= val < tend
        rel_from_text += from_text
        rel_into_text += into_text
        rel_from_data_into_text += (into_text and not from_text)
print(f"relocations={rel_total} from_text={rel_from_text} into_text={rel_into_text} data->text(fn ptrs/vtables/jumptables)={rel_from_data_into_text}")

md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True; md.skipdata = True
calls = set(); ninsn = 0; mn = collections.Counter(); ind_jmp = 0; ind_call = 0
x87 = sse = mmx = 0
for i in md.disasm(code, tva):
    ninsn += 1; m = i.mnemonic; mn[m] += 1
    if m == "call" and i.operands and i.operands[0].type == X86_OP_IMM:
        t = i.operands[0].imm
        if tva <= t < tend: calls.add(t)
    elif m == "call": ind_call += 1
    elif m == "jmp" and i.operands and i.operands[0].type != X86_OP_IMM: ind_jmp += 1
    if m.startswith("f") and m not in ("fxsave","fxrstor"): x87 += 1
    if m.endswith(("ps","ss","pd","sd")) and m not in ("cmpsd","movsd") or m in ("movaps","movups","xorps"): sse += 1
    if m.startswith(("paddb","pmull","movq","punpck","emms")): mmx += 1
print(f"text_bytes={len(code)} instructions~{ninsn} direct_call_targets={len(calls)} indirect_calls={ind_call} indirect_jmps={ind_jmp}")
print(f"x87_insns={x87} sse_insns~{sse} mmx_insns~{mmx}")
print("top mnemonics:", mn.most_common(25))
