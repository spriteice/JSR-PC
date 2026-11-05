#!/usr/bin/env python3
"""Cross-check the function catalogue against Ghidra's, address by address (M3).

pcrecomp's tools/disasm/score_recovery.py scores data/functions.json.gz, the
catalogue the lift uses, against another tool's functions and reports counts.
This writes the list behind the counts: every address that is a function start
in one catalogue and not in the other, with what each side has there and why.

It holds metadata only, like data/function_map.tsv: addresses, kinds, reference
counts and how each entry was found. It never holds instruction bytes or text.

Three steps, run from the repository root after 00_verify_inputs.sh and
01_fetch_pcrecomp.sh (scripts/ghidra_crosscheck.sh runs all three):

  1. Ghidra analyses the exe and writes each function's bounds, with pcrecomp's
     tools/ghidra/DumpBounds.java.
  2. This script lists the addresses Ghidra must describe (--addresses), and
     tools/ghidra/RecoveryFacts.java says what Ghidra has at each one.
  3. This script reads both and writes the list (-o).

    python3 -I tools/recovery_crosscheck.py work/input/jetsetradio.exe \\
        --bounds work/ghidra/bounds.csv --addresses work/ghidra/addresses.txt
    python3 -I tools/recovery_crosscheck.py work/input/jetsetradio.exe \\
        --bounds work/ghidra/bounds.csv --facts work/ghidra/facts.tsv \\
        -o data/recovery_crosscheck.tsv

Ghidra's ends are walked back over trailing 0xCC and 0x90 before anything is
compared, as score_recovery asks, and "inside a Ghidra function" means what it
means there: after a Ghidra start and before that function's end.

Rows, by category (the same split as score_recovery's):
  ours: split        our function start inside a Ghidra function
  ours: invented     our function start outside every Ghidra function
  ours: alias-outside  our alias entry outside every Ghidra function
  ghidra: alias      a Ghidra function start that we have as an alias entry
  ghidra: missing    a Ghidra function start that is no entry of ours at all

Columns:
  address   the VA
  side      ours or ghidra: the catalogue that has a function start here
  category  as above
  reason    a short code; the summary in the header says what each one means
  ours      our map kind (start, alias, ilt, thunk), or - when we have no entry
  ghidra    what Ghidra has: instr, midinstr, data:TYPE or undef, then "in X"
            for the Ghidra function holding it, then its reference counts
  evidence  what we find pointing at the address, from the exe:
            slot        a slot of an incremental-linking (ILT) table
            ilt-target  an ILT slot jumps here
            called:N    N of our functions call it (not counting itself)
            self-call   it calls itself
            rel32       an E8 or E9 byte reads as a call or jump here (the
                        linear scan disasm32 seeds from; it does not say a
                        decoded instruction does)
            prologue    it opens with push ebp; mov ebp, esp
            data-ptr    its address is a 4-byte value in a data section
            code-imm    its address is a 4-byte value in the code section
            eh-stub     a C++ EH handler stub (it loads a FuncInfo and jumps
                        to the frame handler), which a function's prologue pushes
            eh          a C++ EH table (FuncInfo) names it: an unwind action or
                        a catch block
            seh         an SEH scope table (_except_handler4's) names it: a
                        filter, an __except block or a __finally block
  parent    for an alias, the function it is an entry of
"""
import argparse
import bisect
import collections
import csv
import gzip
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PCRECOMP = os.path.join(ROOT, "third_party", "pcrecomp")

# reason code -> what it means. The header of the output repeats these.
REASONS = {
    # ours: split and invented
    "ilt-unused": "an ILT stub that nothing calls, jumps to or points at. Ghidra decodes "
                  "only the stubs it reaches; the lift keeps every slot",
    "ilt-data": "an ILT stub whose address is stored in data (a vtable or a callback "
                "table). Ghidra decoded it but made no function of it",
    "ilt-jump": "an ILT stub reached by a jump. Ghidra decoded it but made no function of it",
    "ilt-unseen-pointer": "an ILT stub named only by a 4-byte value (in data or code) "
                          "or an E8 or E9 byte, where Ghidra made no reference; Ghidra "
                          "never decoded it",
    "ilt-target-unreached": "reached through ILT stubs that nothing reaches: code the "
                            "linker kept and the program never calls",
    "ilt-target-no-function": "reached through an ILT stub that data points at. Ghidra "
                              "decoded it from there but made no function of it",
    "seh-funclet": "an SEH filter, __except block or __finally block in the C runtime, "
                   "named by its scope table. Ghidra decodes none of them",
    "jump-label": "a label inside Ghidra's function that only an unconditional jump "
                  "reaches, after a ret, jmp or call. disasm32 keeps such a target as a "
                  "start on purpose, since a tail call looks the same. The lifted "
                  "function before it runs through it",
    "false-start-data-ptr": "a 4-byte value in data equals the address of an instruction "
                            "inside Ghidra's function, and the data scan took it. The "
                            "lifted function before it runs through it, so nothing is "
                            "lost; it is no function, and the map must not name it as one",
    "false-start-rel32": "an E8 or E9 byte elsewhere reads as a call or jump to an "
                         "instruction inside Ghidra's function, where Ghidra has no "
                         "reference: a coincidence of the linear scan. The lifted "
                         "function before it runs through it",
    "false-start-prologue": "a push ebp; mov ebp, esp at an instruction inside Ghidra's "
                            "function, where Ghidra has no reference to it. The lifted "
                            "function before it runs through it",
    "false-start-selfcall": "an E8 byte inside one of Ghidra's instructions reads as a "
                            "call to itself, which kept it. Nothing else reaches it, and "
                            "the lifted function around it runs through the real "
                            "instructions",
    "data-as-code": "Ghidra has data here (a switch table, a constant), which we decoded "
                    "because a 4-byte value or an E8 or E9 byte elsewhere names it. "
                    "Nothing decoded calls it, so nothing runs it",
    "pointer-no-function": "its address is an immediate in code (a callback pushed or "
                           "stored) or a value in data. Ghidra records the reference "
                           "but made no function there",
    "called-by-ours-only": "called only by functions Ghidra doesn't have either (their "
                           "own rows say why)",
    "data-ptr-only": "named only by a 4-byte value in data where Ghidra made no "
                     "reference; it decodes as code, and nothing decoded calls it",
    "rel32-only": "found only by an E8 or E9 byte the linear scan read as a call or a "
                  "jump; nothing decoded calls it, so nothing runs it",
    "prologue-only": "found only by its push ebp; mov ebp, esp: code that nothing "
                     "calls, jumps to or points at",
    # ours: alias entries outside every Ghidra function
    "eh-stub": "a C++ EH handler stub placed after its function, which its prologue "
               "pushes: by design an entry of that function. Ghidra decodes it but makes "
               "no function of it",
    "alias-of-ours-only": "an entry of a function of ours that Ghidra doesn't have (that "
                          "function's own row says why)",
    "beyond-ghidra-end": "an entry in the part of the parent's body past where Ghidra "
                         "ends that function; Ghidra decoded nothing here",
    "other-owner": "Ghidra holds it in another function's body, outside that function's "
                   "range; we hold it in the parent's",
    # ghidra: alias and missing
    "eh-funclet": "a C++ EH funclet (an unwind action or a catch block): by design an "
                  "entry of the function that installs it, where Ghidra makes each one a "
                  "function",
    "label-in-body": "a label inside the parent, which runs through it. Ghidra starts a "
                     "function at the label",
    "eh-funclet-no-entry": "a C++ catch block inside another function's body, named only "
                           "by its EH table, with no entry of its own: a throw that "
                           "reaches it would find no lifted funclet",
    "unreferenced": "nothing calls, jumps to or points at it, and no ILT stub names it, "
                    "so nothing can reach it. Ghidra found it by its shape",
}


def load_catalogue(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        return json.load(f)["functions"]


def load_map(path):
    with open(path) as f:
        rows = csv.DictReader((line for line in f if not line.startswith("#")), delimiter="\t")
        return {int(r["address"], 16): r for r in rows}


def load_bounds(path, read):
    """Ghidra's [(start, end)], end walked back over trailing int3 and nop."""
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "," not in line:
                continue
            a, b = line.split(",")[:2]
            try:
                s, e = int(a, 16), int(b, 16)
            except ValueError:
                continue
            while e - 1 > s and read(e - 1, 1) in (b"\xcc", b"\x90"):
                e -= 1
            out.append((s, e))
    return sorted(out)


def load_facts(path):
    with open(path) as f:
        return {int(r["addr"], 16): r for r in csv.DictReader(f, delimiter="\t")}


def code_values(data, lo, hi):
    """Every 4-byte little-endian value at any offset of data that lies in [lo, hi)."""
    out = set()
    for k in range(4):
        n = (len(data) - k) // 4
        out.update(v for (v,) in struct.iter_unpack("<I", data[k:k + 4 * n]) if lo <= v < hi)
    return out


def scope_table_funclets(raw, va, lo, hi):
    """Filters and handlers named by _except_handler4 scope tables in raw (at va).

    A table is four cookie offsets, the GS one -2 when there is no GS cookie and
    the EH one a negative frame offset, then records of {enclosing level,
    filter, handler}: the first level is -2 (outermost) and each later one an
    earlier record's index; filter is 0 for a __finally block.
    """
    def d(o):
        return struct.unpack_from("<I", raw, o)[0]

    def neg(v, floor):
        return v >= 0x100000000 - floor and v != 0xFFFFFFFF

    out = set()
    for o in range(0, len(raw) - 28, 4):
        gs, eh = d(o), d(o + 8)
        if not ((gs == 0xFFFFFFFE or neg(gs, 0x1000)) and neg(eh, 0x1000) and d(o + 16) == 0xFFFFFFFE):
            continue
        k = 0
        while o + 28 + 12 * k <= len(raw):
            level, flt, handler = d(o + 16 + 12 * k), d(o + 20 + 12 * k), d(o + 24 + 12 * k)
            if not (level == 0xFFFFFFFE or level < k) or not lo <= handler < hi \
                    or not (flt in (0, 1) or lo <= flt < hi):
                break
            out.add(handler)
            if lo <= flt < hi:
                out.add(flt)
            k += 1
    return out


class Exe:
    """What the exe itself says about each address: the evidence column."""

    def __init__(self, exe_path, catalogue, fmap):
        sys.path.insert(0, os.path.join(PCRECOMP, "tools", "pe"))
        sys.path.insert(0, os.path.join(PCRECOMP, "tools", "disasm"))
        from pe_analyze import analyze_pe
        from disasm32 import Disassembler, eh_entries, prologue_starts, thunk_tables
        info = analyze_pe(exe_path)
        with open(exe_path, "rb") as f:
            self.dis = Disassembler(f.read(), info.image_base, info.sections)
        cs, ce = info.code_start, info.code_end
        self.code = (cs, ce)
        text = self.dis.read_bytes(cs, ce - cs)
        self.rel32 = self.dis.find_branch_targets(cs, ce)
        self.prologue = prologue_starts(text, cs)
        self.slots = {a for lo, hi in thunk_tables(text, cs) for a in range(lo, hi, 5)}
        eh = eh_entries(self.dis.read_bytes, cs, ce)
        self.eh_stub = {a for a in eh if self.read(a, 1) == b"\xb8" and self.read(a + 5, 1) == b"\xe9"}
        self.eh = eh - self.eh_stub
        self.seh = set()
        self.data_ptr = set()
        for s in info.sections:
            if not s.is_code:
                raw = self.dis.read_bytes(info.image_base + s.virtual_address, s.raw_size)
                if raw:
                    self.data_ptr |= code_values(raw, cs, ce)
                    self.seh |= scope_table_funclets(raw, info.image_base + s.virtual_address, cs, ce)
        self.code_imm = code_values(text, cs, ce)
        self._decoded = {}
        self.callers = collections.defaultdict(set)
        self.self_call = set()
        for fn in catalogue:
            for t in fn["calls_to"]:
                if t == fn["address"]:
                    self.self_call.add(t)
                else:
                    self.callers[t].add(fn["address"])
        self.ilt_target = collections.Counter(
            int(r["target"], 16) for r in fmap.values() if r["kind"] == "ilt" and r.get("target"))

    def read(self, va, n):
        return self.dis.read_bytes(va, n)

    def runs_through(self, starts, a, ghidra_start):
        """Whether one of our function starts from Ghidra's start up to a decodes
        on through a (an instruction starts there, or one holds it).

        The lifter emits every instruction that decode reaches, past the extent the
        catalogue gives the function, so then the code at a is lifted inside it too.
        """
        lo = bisect.bisect_left(starts, ghidra_start)
        hi = bisect.bisect_left(starts, a)
        for s in starts[lo:hi]:
            if s not in self._decoded:
                fn = self.dis.disassemble_function(s)
                self._decoded[s] = [(i.address, i.address + i.size)
                                    for b in fn.blocks.values() for i in b.instructions] if fn else []
            if any(x <= a < y for x, y in self._decoded[s]):
                return True
        return False

    def evidence(self, a):
        ev = []
        if a in self.slots:
            ev.append("slot")
        if self.ilt_target.get(a):
            ev.append("ilt-target")
        if self.callers.get(a):
            ev.append(f"called:{len(self.callers[a])}")
        if a in self.self_call:
            ev.append("self-call")
        if a in self.rel32:
            ev.append("rel32")
        if a in self.prologue:
            ev.append("prologue")
        if a in self.data_ptr:
            ev.append("data-ptr")
        if a in self.code_imm:
            ev.append("code-imm")
        if a in self.eh_stub:
            ev.append("eh-stub")
        if a in self.eh:
            ev.append("eh")
        if a in self.seh:
            ev.append("seh")
        return ev


def compare(catalogue, bounds):
    """score_recovery's split, as address lists: {category: [address]}."""
    ref_set = {s for s, _ in bounds}
    starts = sorted({f["address"] for f in catalogue if f.get("entry_kind", "start") != "alias"})
    aliases = sorted({f["address"] for f in catalogue if f.get("entry_kind") == "alias"} - set(starts))
    rs = [s for s, _ in bounds]

    def inside(a):
        i = bisect.bisect_right(rs, a) - 1
        return bounds[i][0] if i >= 0 and bounds[i][0] < a < bounds[i][1] else None

    entries = set(starts) | set(aliases)
    out = collections.defaultdict(list)
    for a in starts:
        if a not in ref_set:
            out["split" if inside(a) is not None else "invented"].append(a)
    for a in aliases:
        if a in ref_set:
            out["alias"].append(a)
        elif inside(a) is None:
            out["alias-outside"].append(a)
    for s in rs:
        if s not in entries:
            out["missing"].append(s)
    return out, inside


def ghidra_col(fa):
    if not fa:
        return "?"
    s = fa["listing"]
    if s == "data":
        s += ":" + fa["dtype"]
    if fa["func"] != "-":
        s += f" in 0x{int(fa['func'], 16):08X}"
    n = int(fa["refs"])
    if n:
        kinds = [f"{k} {fa[k]}" for k in ("call", "jump", "data", "other") if int(fa[k])]
        s += f"; refs {', '.join(kinds)}"
    else:
        s += "; no refs"
    return s


def reason_for(cat, kind, ev, fa, parent, ours_only, callers, ghidra_fn_of, through):
    """The reason code for one row (REASONS says what each means), or "unexplained"."""
    ev = set(e.split(":")[0] for e in ev)
    refs = int(fa["refs"])
    listing = fa["listing"]
    called = "called" in ev
    if cat in ("split", "invented"):
        if kind == "ilt" or "slot" in ev:
            if refs:
                return "ilt-data" if int(fa["data"]) else "ilt-jump"
            if ev == {"slot"}:
                return "ilt-unused"
            if called:
                return "called-by-ours-only" if callers <= ours_only else "unexplained"
            return "ilt-unseen-pointer"
        if "ilt-target" in ev and not called:
            return "ilt-target-unreached" if listing == "undef" else "ilt-target-no-function"
        if "seh" in ev:
            return "seh-funclet"
        if called and callers <= ours_only:
            return "called-by-ours-only"
        if cat == "split":
            if called:
                return "unexplained"
            if listing == "undef":
                return "data-ptr-only" if ev & {"data-ptr", "code-imm"} else "unexplained"
            # Each of these is harmless only if the lifted function before it
            # decodes on through it; through() checks that.
            if listing == "midinstr" and "self-call" in ev:
                code = "false-start-selfcall"
            elif "rel32" in ev and int(fa["jump"]) and fa["from"] != "-" \
                    and ghidra_fn_of(int(fa["from"], 16)) == int(fa["func"], 16):
                code = "jump-label"
            elif ev & {"data-ptr", "code-imm"}:
                code = "false-start-data-ptr"
            elif "rel32" in ev and refs == 0:
                code = "false-start-rel32"
            elif "prologue" in ev and refs == 0:
                code = "false-start-prologue"
            else:
                return "unexplained"
            return code if through() else "unexplained"
        if listing == "data":
            return "unexplained" if called else "data-as-code"
        if refs:
            return "pointer-no-function"
        if called:
            return "unexplained"
        if ev & {"data-ptr", "code-imm"}:
            return "data-ptr-only"
        if "rel32" in ev:
            return "rel32-only"
        if "prologue" in ev:
            return "prologue-only"
        return "unexplained"
    if cat == "alias-outside":
        if "eh-stub" in ev:
            return "eh-stub"
        if parent in ours_only:
            return "alias-of-ours-only"
        if fa["func"] != "-":
            return "other-owner"
        if listing == "undef" and refs == 0:
            return "beyond-ghidra-end"
        return "unexplained"
    if cat == "alias":
        return "eh-funclet" if "eh" in ev else "label-in-body"
    if cat == "missing":
        if "eh" in ev:
            return "eh-funclet-no-entry"
        if refs == 0 and not (ev - {"prologue"}):
            return "unreferenced"
        if parent is not None and int(fa["jump"]) == refs:
            return "label-in-body"
    return "unexplained"


def containing(catalogue_sorted, starts_sorted, a):
    """Our start-kind function whose extent holds a, or None."""
    i = bisect.bisect_right(starts_sorted, a) - 1
    while i >= 0 and i > bisect.bisect_right(starts_sorted, a) - 64:
        f = catalogue_sorted[i]
        if f["address"] < a < f["end"]:
            return f["address"]
        i -= 1
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("exe")
    ap.add_argument("--catalogue", default=os.path.join(ROOT, "data", "functions.json.gz"))
    ap.add_argument("--map", default=os.path.join(ROOT, "data", "function_map.tsv"))
    ap.add_argument("--bounds", required=True, help="DumpBounds.java's CSV")
    ap.add_argument("--addresses", help="write the addresses RecoveryFacts.java must describe, and stop")
    ap.add_argument("--facts", help="RecoveryFacts.java's TSV")
    ap.add_argument("-o", "--output", help="the list, as TSV")
    ap.add_argument("--reference-json", metavar="FILE",
                    help="also write Ghidra's functions, ends walked back, for score_recovery.py")
    ap.add_argument("--source", default="Ghidra", help="what made the bounds, for the header")
    a = ap.parse_args()

    catalogue = load_catalogue(a.catalogue)
    fmap = load_map(a.map)
    exe = Exe(a.exe, catalogue, fmap)
    bounds = load_bounds(a.bounds, exe.read)
    diff, inside = compare(catalogue, bounds)
    if a.reference_json:
        with open(a.reference_json, "w") as f:
            json.dump({"source": a.source + ", DumpBounds.java, ends walked back over int3 and nop",
                       "functions": [{"start": s, "end": e} for s, e in bounds]}, f)
    every = sorted(x for v in diff.values() for x in v)
    if a.addresses:
        with open(a.addresses, "w") as f:
            f.writelines(f"0x{x:08X}\n" for x in every)
        print(f"{len(every)} addresses -> {a.addresses}")
        return 0
    if not (a.facts and a.output):
        ap.error("--facts and -o, or --addresses")
    facts = load_facts(a.facts)
    lacking = [x for x in every if x not in facts]
    if lacking:
        sys.exit(f"{a.facts} has no row for {len(lacking)} addresses (0x{lacking[0]:08X} first): "
                 "run RecoveryFacts.java on this script's --addresses list again")

    by_addr = {f["address"]: f for f in catalogue}
    ours_sorted = sorted((f for f in catalogue if f.get("entry_kind", "start") != "alias"),
                         key=lambda f: f["address"])
    ours_starts = [f["address"] for f in ours_sorted]
    ours_only = set(diff["split"]) | set(diff["invented"]) | set(diff["alias-outside"])

    def inside_or_at(v):
        hit = inside(v)
        return v if hit is None and v in ref_starts else hit
    ref_starts = {s for s, _ in bounds}
    rows = []
    for cat in ("split", "invented", "alias-outside", "alias", "missing"):
        for x in diff[cat]:
            r = fmap.get(x, {})
            kind = r.get("kind", "-")
            ev = exe.evidence(x)
            parent = None
            if kind == "alias" and r.get("target"):
                parent = int(r["target"], 16)
            elif cat == "missing":
                parent = containing(ours_sorted, ours_starts, x)
            reason = reason_for(cat, kind, ev, facts[x], parent, ours_only,
                                exe.callers.get(x, set()), inside_or_at,
                                lambda: exe.runs_through(ours_starts, x, int(facts[x]["func"], 16)))
            side = "ghidra" if cat in ("alias", "missing") else "ours"
            rows.append((x, side, cat, reason, kind, ghidra_col(facts[x]), ",".join(ev) or "-",
                         f"0x{parent:08X}" if parent is not None else "-"))

    counts = collections.Counter((r[2], r[3]) for r in rows)
    unexplained = [r for r in rows if r[3] == "unexplained"]
    with open(a.output, "w", newline="\n") as f:
        f.write(f"# Generated by tools/recovery_crosscheck.py from jetsetradio.exe, "
                f"data/functions.json.gz ({len(catalogue)} entries) and {a.source}'s "
                f"{len(bounds)} functions. Do not edit: rerun scripts/ghidra_crosscheck.sh.\n")
        f.write("# The columns and how to rebuild it are in the script's docstring.\n")
        for (cat, reason), n in sorted(counts.items()):
            f.write(f"# {cat:<13} {reason:<22} {n:>5}  {REASONS.get(reason, 'not explained')}\n")
        f.write("address\tside\tcategory\treason\tours\tghidra\tevidence\tparent\n")
        for r in rows:
            f.write(f"0x{r[0]:08X}\t" + "\t".join(r[1:]) + "\n")
    for (cat, reason), n in sorted(counts.items()):
        print(f"{cat:<13} {reason:<22} {n:>5}")
    print(f"{len(rows)} rows -> {a.output}; {len(unexplained)} not explained")
    return 1 if unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
