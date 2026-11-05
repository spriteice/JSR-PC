#!/usr/bin/env python3
"""Write data/function_map.tsv, which records what is known about each function in jetsetradio.exe.

There is one row for each entry in data/functions.json.gz, the catalogue the lift
uses, keyed by address, so every sub_XXXXXXXX in the generated C has a row. It
holds metadata only: addresses, names, source-file paths and how each was found.
It never holds instruction bytes or any string other than a name or a path
(AGENTS rule 1).

Columns:
  address   the entry's VA, as in sub_XXXXXXXX
  kind      start   a function begins here
            alias   a dispatchable label inside another function's body (a shared
                    epilogue, a switch arm, a C++ EH funclet); target is the parent
            ilt     an incremental-linking stub: one `jmp` to the real function
            thunk   a bare `jmp` to another function
            import  `jmp [IAT]` to an imported function
  name      the best name known, or empty
  module    the source file, as the exe spells it with '/' for '\\', or empty
  evidence  how the name and module were found, strongest first:
            manual  data/names_manual.tsv: a name someone assigned, with a reason. It
                    may replace an RTTI slot name, never a name the function's own
                    string gives (that stops the script)
            self    the function passes its own name (__FUNCTION__) to a log or an
                    assert, and no other function passes that name
            rtti    slot N of the class's vtable: Class::vfN (RTTI names classes,
                    not members)
            vtable-store  it stores a class's vtable into `this`:
                    Class::constructor, ::destructor or ::constructor_or_destructor
                    (name_lift.py's rules)
            file    the function passes this source path (__FILE__)
            between the function lies between two functions of the same file, with
                    no other file's function between them
            mentions=A|B  name strings the function passes that could not be
                    attributed (several functions pass them, or it passes several)
  target    for ilt, thunk and import, where it jumps; for alias, the parent

Empty fields at the end of a row are left off, so a row can have fewer than six.

Names for ilt and thunk rows are j_ plus the target's name. Import rows are named
j_ plus the import, so a name never collides with the real Windows function.

Names a person or agent assigns go in data/names_manual.tsv
(address, name, module, note), never in this file: rerunning the script
regenerates it and merges them in.

    python3 -I tools/map_functions.py <game dir or jetsetradio.exe> [-o data/function_map.tsv]
                                      [--known work/known_names.txt]

--known also writes every name as a C identifier, one "VA NAME" per line, for
pcrecomp's tools/lift/name_lift.py --known-file: `::` becomes `__` and `~` becomes
`destructor_`, as name_lift spells its own, and a name already taken gets the
address appended.
"""
import argparse
import bisect
import collections
import gzip
import hashlib
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCRECOMP = os.path.join(ROOT, "third_party", "pcrecomp")

ILT_START = 0x00401005          # first stub; the run of `jmp rel32` ends at the padding

# Strings a function passes as its own name. Only these shapes are trusted, because
# the exe also holds names of APIs that the CRT looks up at run time (FlsAlloc,
# MessageBoxW) and words that are only data (stage and save names).
NAME_RES = [
    re.compile(r"[A-Z][A-Za-z0-9_]*::~?[A-Za-z_][A-Za-z0-9_]*"),        # Class::method
    re.compile(r"(?:nj|gdFs|ADX[FT]_|bu|pd|ntInf)[A-Z_][A-Za-z0-9_]*"),  # Dreamcast SDK
    re.compile(r"(?:asm|_jt)[A-Z][A-Za-z0-9_]*"),                        # the game's asm helpers
    re.compile(r"markGraffitiUsed|ninja2D3DFMT|Backup_LoadSlot"),        # seen once each, checked by hand
]
PATH_RE = re.compile(r"[A-Za-z0-9_]+(?:\\[A-Za-z0-9_]+)*\\[A-Za-z0-9_]+\.(?:c|cpp)", re.I)
MANUAL_NAME_RE = re.compile(r"[A-Za-z_~][A-Za-z0-9_:~]*")

COLUMNS = ["address", "kind", "name", "module", "evidence", "target"]


def is_name(s):
    return not s.startswith("std::") and any(r.fullmatch(s) for r in NAME_RES)


def find_exe(path):
    exe = os.path.join(path, "jetsetradio.exe") if os.path.isdir(path) else path
    if not os.path.isfile(exe):
        sys.exit(f"no jetsetradio.exe at {path}")
    return exe


def check_hash(exe):
    want = None
    with open(os.path.join(ROOT, "data", "inputs.sha256")) as f:
        for line in f:
            h, _, name = line.strip().partition("  ")
            if name == "jetsetradio.exe":
                want = h
    with open(exe, "rb") as f:
        got = hashlib.sha256(f.read()).hexdigest()
    if got != want:
        sys.exit(f"{exe}: sha256 {got[:8]} is not the build in data/inputs.sha256 ({want[:8]}); stop (rule 2)")


class Image:
    """The exe's sections, base relocations and imports, read straight from the file."""

    def __init__(self, exe):
        import pefile
        self.pe = pe = pefile.PE(exe)
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.img = pe.get_memory_mapped_image()
        self.text = next((self.base + s.VirtualAddress, self.base + s.VirtualAddress + s.Misc_VirtualSize)
                         for s in pe.sections if s.Name.rstrip(b"\0") == b".text")
        self.iat = {}
        for d in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            for imp in d.imports:
                self.iat[imp.address] = imp.name.decode() if imp.name else f"{d.dll.decode()}#{imp.ordinal}"

    def u8(self, va):
        return self.img[va - self.base]

    def u32(self, va):
        return struct.unpack_from("<I", self.img, va - self.base)[0]

    def in_text(self, va):
        return self.text[0] <= va < self.text[1]

    def jmp(self, va):
        """(kind, target) if `va` holds `jmp rel32` or `jmp [IAT]`, else None."""
        if self.u8(va) == 0xE9:
            return "thunk", (va + 5 + struct.unpack_from("<i", self.img, va + 1 - self.base)[0]) & 0xFFFFFFFF
        if self.u8(va) == 0xFF and self.u8(va + 1) == 0x25 and self.u32(va + 2) in self.iat:
            return "import", self.u32(va + 2)
        return None

    def ilt(self):
        """{stub: target} for the incremental-linking table at the start of .text."""
        out, va = {}, ILT_START
        while self.u8(va) == 0xE9:
            out[va] = self.jmp(va)[1]
            va += 5
        return out

    def cstr(self, va):
        off = va - self.base
        if not 0 <= off < len(self.img):
            return None
        end = self.img.find(b"\0", off, off + 256)
        if end - off < 3:
            return None
        s = self.img[off:end]
        return s.decode("ascii") if all(32 <= c < 127 for c in s) else None

    def string_refs(self):
        """[(site, string)] for each relocated word in .text that points at a C string."""
        out = []
        for blk in self.pe.DIRECTORY_ENTRY_BASERELOC:
            for e in blk.entries:
                site = self.base + e.rva
                if e.type == 3 and self.in_text(site):
                    s = self.cstr(self.u32(site))
                    if s is not None:
                        out.append((site, s))
        return out


def type_name(decorated):
    """MSVC's decorated type name as C++ spells it: .?AVbad_alloc@std@@ -> std::bad_alloc.

    Covers what this exe holds: nested names, and class templates whose arguments
    are classes, structs or integers (CCallback<SteamWrapper,GameOverlayActivated_t,0>).
    """
    s = decorated[4:]                                   # drop .?AV / .?AU

    def qualified(i):
        parts = []
        while s[i] != "@":
            if s.startswith("?$", i):
                j = s.index("@", i + 2)
                tname, i, args = s[i + 2:j], j + 1, []
                while s[i] != "@":
                    if s[i] in "VU":
                        sub, i = qualified(i + 1)
                        args.append(sub)
                    elif s.startswith("$0", i) and s[i + 2].isdigit():
                        args.append(str(int(s[i + 2]) + 1))
                        i += 3
                    elif s.startswith("$0", i):
                        j = s.index("@", i + 2)
                        args.append(str(int("".join("%X" % (ord(c) - 65) for c in s[i + 2:j]) or "0", 16)))
                        i = j + 1
                    else:
                        raise ValueError(decorated)
                parts.append(f"{tname}<{','.join(args)}>")
                i += 1
            else:
                j = s.index("@", i)
                parts.append(s[i:j])
                i = j + 1
        return "::".join(reversed(parts)), i + 1

    return qualified(0)[0]


def rtti_names(exe):
    """({function: (Class::vfN or None, evidence)}, the recovery, C++ spellings).

    From pcrecomp's RTTI recovery."""
    sys.path.insert(0, os.path.join(PCRECOMP, "tools", "cpp"))
    import rtti
    r = rtti.recover(exe)
    owners = rtti.owning_class(r)
    thunks = r["thunks"]
    spelled = {}                                # rtti's short name -> C++ spelling
    for _va, name, _sub, _ms in r["vtables"]:
        try:
            spelled[rtti.demangle(name)] = type_name(name)
        except (ValueError, IndexError):
            spelled[rtti.demangle(name)] = rtti.demangle(name)
    slot = {}                                   # (class, function) -> slot in its primary vtable
    for va, name, sub, methods in r["vtables"]:
        if sub == 0 and r["primary_va"].get(name) == va:
            for i, m in enumerate(methods):
                slot.setdefault((rtti.demangle(name), thunks.get(m, m)), i)
    out = {}
    for fn, classes in rtti.methods_by_class(r).items():
        owner = owners.get(fn)
        if owner is None:
            out[fn] = (None, "rtti=" + "|".join(sorted(spelled.get(c, c) for c in classes)))
            continue
        n = slot.get((owner, fn))
        out[fn] = (f"{spelled.get(owner, owner)}::vf{n}" if n is not None else None, "rtti")
    return out, r, spelled


def reachable(md, img, f, end):
    """The instructions reachable from `f` without leaving [f, end): fall-through and
    jumps, not calls. A linear sweep would run past a `ret` into whatever follows."""
    from capstone import x86
    seen, work, out = set(), [f], []
    while work:
        va = work.pop()
        while f <= va < end and va not in seen:
            insn = next(md.disasm(img.img[va - img.base:end - img.base], va, 1), None)
            if insn is None:
                break
            seen.add(va)
            out.append(insn)
            ops = insn.operands
            if insn.group(x86.X86_GRP_JUMP) and ops and ops[0].type == x86.X86_OP_IMM:
                work.append(ops[0].imm)
            if insn.id in (x86.X86_INS_RET, x86.X86_INS_JMP, x86.X86_INS_INT3):
                break
            va += insn.size
    return sorted(out, key=lambda i: i.address)


def structors(img, r, spelled, starts, stubs, skip):
    """{function: Class::constructor | Class::destructor | Class::constructor_or_destructor}.

    A function that stores a class's vtable into `this` (`mov dword ptr [reg], vtable`)
    builds or tears down an object. These are name_lift.py's rules, so the map names
    what name_lift would, and the lift's names all come from here:
      - it stores several classes' vtables: a constructor stores its bases' first and
        its own last; a destructor its own first, then its bases';
      - it stores one class's vtable, and the class has a base with a vtable: a call
        before the store makes it a constructor (the base's), a call after it a
        destructor; no call at all leaves it undecided;
      - the same with no base: undecided.
    Only primary vtables count, and functions that are vtable slots are left alone.
    """
    import capstone
    from capstone import x86
    sys.path.insert(0, os.path.join(PCRECOMP, "tools", "cpp"))
    import rtti
    vt = {va: rtti.demangle(name) for name, va in r["primary_va"].items()}
    bases = {rtti.demangle(k): [rtti.demangle(b) for b in v[1:]] for k, v in r["hierarchy"].items()}
    with_vtable = set(vt.values())

    def owner(va):
        i = bisect.bisect_right(starts, va) - 1
        return starts[i] if i >= 0 else None

    cand = set()
    for blk in img.pe.DIRECTORY_ENTRY_BASERELOC:
        for e in blk.entries:
            site = img.base + e.rva
            if e.type == 3 and img.in_text(site) and img.u32(site) in vt:
                o = owner(site)
                if o is not None and o not in skip:
                    cand.add(o)

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    start_set = set(starts) | set(stubs)
    out = {}
    for f in sorted(cand):
        i = bisect.bisect_right(starts, f)
        end = starts[i] if i < len(starts) else img.text[1]
        stores, calls = [], []                      # (address, class), address
        for insn in reachable(md, img, f, end):
            ops = insn.operands
            if insn.id == x86.X86_INS_MOV and len(ops) == 2 and ops[0].type == x86.X86_OP_MEM \
                    and ops[0].size == 4 and ops[1].type == x86.X86_OP_IMM and ops[1].imm in vt \
                    and ops[0].mem.base not in (0, x86.X86_REG_ESP) and ops[0].mem.index == 0 \
                    and ops[0].mem.disp == 0:
                stores.append((insn.address, vt[ops[1].imm]))
            elif insn.id in (x86.X86_INS_CALL, x86.X86_INS_JMP) and ops \
                    and ops[0].type == x86.X86_OP_IMM \
                    and (insn.id == x86.X86_INS_CALL or ops[0].imm in start_set):
                calls.append(insn.address)          # a call, or a tail jump to another function
        if not stores:
            continue
        stores.sort()
        first_store = stores[0][0]
        first_call = min(calls) if calls else None
        stores = [c for _, c in stores]
        first, last = stores[0], stores[-1]
        if len(set(stores)) > 1 and first in bases.get(last, []):
            name, why = last, "constructor"
        elif len(set(stores)) > 1 and last in bases.get(first, []):
            name, why = first, "destructor"
        elif len(set(stores)) == 1:
            has_base = any(b in with_vtable for b in bases.get(first, []))
            if has_base and first_call is not None and first_call < first_store:
                name, why = first, "constructor"
            elif has_base and first_call is not None:
                name, why = first, "destructor"
            else:
                name, why = first, "constructor_or_destructor"
        else:
            continue
        out[f] = f"{spelled.get(name, name)}::{why}"
    return out


def self_names(passes, who):
    """{function: name} for functions that pass their own name.

    A function that logs or asserts passes its own name. A caller that inlines it
    passes that name too, alongside its own, so a name passed by several functions
    is not proof by itself. Three rules, applied until nothing changes:
      1. F passes exactly one name, and no other function passes it.
      2. F passes exactly one name N, and every other function passing N also
         passes other names (they inline F; F is the only plain copy).
      3. Once the names that other functions own are set aside, F passes exactly
         one name left, and no function without a name passes it.
    """
    names_of = {o: {s for s in ss if is_name(s)} for o, ss in passes.items()}
    names_of = {o: ns for o, ns in names_of.items() if ns}
    owned = {}                                          # name -> function
    changed = True
    while changed:
        changed = False
        for o, ns in sorted(names_of.items()):
            if o in owned.values():
                continue
            left = ns - set(owned)
            if len(left) != 1:
                continue
            n = next(iter(left))
            others = who[n] - {o}
            if (len(ns) == 1 and all(len(names_of[x]) > 1 for x in others)) or \
               all(x in owned.values() for x in others):
                owned[n] = o
                changed = True
    return {o: n for n, o in owned.items()}


def read_manual(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for n, line in enumerate(f, 1):
            if not line.strip() or line.startswith("#") or line.startswith("address\t"):
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 4 or not cols[3].strip():
                sys.exit(f"{path}:{n}: need address, name, module, note (the note says why)")
            addr = int(cols[0], 16)
            if not MANUAL_NAME_RE.fullmatch(cols[1]):
                sys.exit(f"{path}:{n}: {cols[1]!r} is not a usable name")
            out[addr] = (cols[1], cols[2])
    return out


def build(exe, catalogue, manual):
    img = Image(exe)
    funcs = json.load(gzip.open(catalogue))["functions"]
    ilt = img.ilt()

    rows = {}
    for f in funcs:
        a = f["address"]
        row = dict(address=a, kind=f.get("entry_kind", "start"), name="", module="",
                   evidence=[], target=None)
        if a in ilt:
            row["kind"], row["target"] = "ilt", ilt[a]
        elif f.get("is_thunk"):
            j = img.jmp(a)
            if j:
                row["kind"], row["target"] = j
        rows[a] = row

    starts = sorted(a for a, r in rows.items() if r["kind"] == "start")

    def owner(va):
        i = bisect.bisect_right(starts, va) - 1
        return starts[i] if i >= 0 else None

    for a, r in rows.items():
        if r["kind"] == "alias":
            r["target"] = owner(a)

    # Strings each function passes: names and source paths.
    passes = collections.defaultdict(set)
    for site, s in img.string_refs():
        o = owner(site)
        if o is not None and (is_name(s) or PATH_RE.fullmatch(s)):
            passes[o].add(s)
    who = collections.defaultdict(set)
    for o, ss in passes.items():
        for s in ss:
            if is_name(s):
                who[s].add(o)

    for o, name in self_names(passes, who).items():
        rows[o]["name"] = name
        rows[o]["evidence"].append("self")
    for o, ss in passes.items():
        r = rows[o]
        names = sorted(s for s in ss if is_name(s))
        paths = sorted(s for s in ss if PATH_RE.fullmatch(s))
        if names and not r["name"]:
            r["evidence"].append("mentions=" + "|".join(names))
        if len(paths) == 1:
            r["module"] = paths[0].replace("\\", "/")
            r["evidence"].append("file")
        elif paths:
            r["evidence"].append("mentions=" + "|".join(p.replace("\\", "/") for p in paths))

    by_rtti, recovery, spelled = rtti_names(exe)
    for fn, (name, ev) in by_rtti.items():
        r = rows.get(fn)
        if r is None:
            continue
        if name and not r["name"]:
            r["name"] = name
        r["evidence"].append(ev)

    for fn, name in structors(img, recovery, spelled, starts, ilt, set(by_rtti)).items():
        r = rows[fn]
        if not r["name"]:
            r["name"] = name
        r["evidence"].append("vtable-store")

    # Between two functions of the same file, with no other file's in between.
    anchored = [(a, rows[a]["module"]) for a in starts if rows[a]["module"]]
    pos = {a: i for i, a in enumerate(starts)}
    for (a, m), (b, n) in zip(anchored, anchored[1:]):
        if m == n:
            for x in starts[pos[a] + 1:pos[b]]:
                if not rows[x]["module"]:
                    rows[x]["module"] = m
                    rows[x]["evidence"].append("between")

    for a, (name, module) in manual.items():
        r = rows.get(a)
        if r is None:
            sys.exit(f"data/names_manual.tsv: 0x{a:08X} is not in the catalogue")
        if "self" in r["evidence"] and r["name"] != name:
            # The exe names this function itself; a different name is a mistake.
            # (RTTI's Class::vfN is only a slot number, so a manual name may replace it.)
            sys.exit(f"data/names_manual.tsv: 0x{a:08X} is {r['name']} by its own string, not {name}")
        r["name"] = name
        if module:
            r["module"] = module
        r["evidence"].insert(0, "manual")

    # A stub is named after the first named entry its chain of jumps reaches
    # (ilt -> thunk -> ilt -> function), or the import at the end of it.
    own = {a for a, r in rows.items() if r["name"]}

    def final(r):
        for _ in range(8):
            if r["address"] in own or r["kind"] not in ("ilt", "thunk") or r["target"] not in rows:
                break
            r = rows[r["target"]]
        return r

    stub = {}
    for a, r in rows.items():
        if a in own:
            continue
        t = final(r) if r["kind"] in ("ilt", "thunk") else r
        if t["kind"] == "import":
            stub[a] = "j_" + img.iat[t["target"]]
        elif t is not r and t["address"] in own:
            stub[a] = "j_" + t["name"]
    for a, n in stub.items():
        rows[a]["name"] = n
    return [rows[a] for a in sorted(rows)]


def write(rows, out, exe_hash):
    with open(out, "w", newline="\n") as f:
        f.write(f"# Generated by tools/map_functions.py from jetsetradio.exe (sha256 {exe_hash[:8]}). "
                "Do not edit: add names to data/names_manual.tsv and rerun.\n")
        f.write("\t".join(COLUMNS) + "\n")
        for r in rows:
            f.write("\t".join([             # empty fields at the end are left off
                f"0x{r['address']:08X}", r["kind"], r["name"], r["module"],
                ";".join(r["evidence"]),
                f"0x{r['target']:08X}" if r["target"] is not None else "",
            ]).rstrip("\t") + "\n")


def c_names(rows):
    """[(va, C identifier)] for every named row, unique, in address order."""
    sys.path.insert(0, os.path.join(PCRECOMP, "tools", "pe"))
    from merge_names import sanitize
    out, taken = [], set()
    for r in rows:
        if not r["name"]:
            continue
        ident = "__".join(sanitize(p.replace("~", "destructor_")) or "unnamed"
                          for p in r["name"].split("::"))
        if ident in taken:
            ident = f"{ident}_{r['address']:08X}"
        taken.add(ident)
        out.append((r["address"], ident))
    return out


def summary(rows):
    kinds = collections.Counter(r["kind"] for r in rows)
    ev = collections.Counter(e.split("=")[0] for r in rows for e in r["evidence"])
    named = collections.Counter(r["kind"] for r in rows if r["name"])
    modules = {r["module"] for r in rows if r["module"]}
    print(f"[*] {len(rows)} entries: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    print(f"[*] named: " + ", ".join(f"{k} {v}" for k, v in sorted(named.items())))
    print(f"[*] evidence: " + ", ".join(f"{k} {v}" for k, v in sorted(ev.items())))
    print(f"[*] {sum(1 for r in rows if r['module'])} entries in {len(modules)} source files")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("game", help="the game folder, or jetsetradio.exe itself")
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "data", "function_map.tsv"))
    ap.add_argument("--catalogue", default=os.path.join(ROOT, "data", "functions.json.gz"))
    ap.add_argument("--manual", default=os.path.join(ROOT, "data", "names_manual.tsv"))
    ap.add_argument("--known", help="also write name_lift's --known-file here")
    a = ap.parse_args(argv)
    exe = find_exe(a.game)
    check_hash(exe)
    rows = build(exe, a.catalogue, read_manual(a.manual))
    with open(exe, "rb") as f:
        h = hashlib.sha256(f.read()).hexdigest()
    write(rows, a.out, h)
    summary(rows)
    print(f"[*] wrote {a.out}")
    if a.known:
        names = c_names(rows)
        with open(a.known, "w", newline="\n") as f:
            f.write("# C names for tools/lift/name_lift.py --known-file, from data/function_map.tsv\n")
            f.writelines(f"0x{va:08X}\t{n}\n" for va, n in names)
        print(f"[*] wrote {len(names)} C names to {a.known}")


if __name__ == "__main__":
    main()
