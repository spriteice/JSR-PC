import sys, pefile, math, datetime, collections

def entropy(data):
    if not data: return 0.0
    c = collections.Counter(data); n = len(data)
    return -sum(v/n*math.log2(v/n) for v in c.values())

for path in sys.argv[1:]:
    pe = pefile.PE(path)
    print("=" * 70); print(path)
    fh, oh = pe.FILE_HEADER, pe.OPTIONAL_HEADER
    print("TimeDateStamp", hex(fh.TimeDateStamp), datetime.datetime.fromtimestamp(fh.TimeDateStamp, datetime.timezone.utc))
    print("Machine", hex(fh.Machine), "Characteristics", hex(fh.Characteristics))
    print("Linker", oh.MajorLinkerVersion, oh.MinorLinkerVersion, "OS", oh.MajorOperatingSystemVersion, oh.MinorOperatingSystemVersion,
          "Subsys", oh.Subsystem, oh.MajorSubsystemVersion, oh.MinorSubsystemVersion)
    print("ImageBase", hex(oh.ImageBase), "EntryRVA", hex(oh.AddressOfEntryPoint), "SizeOfImage", hex(oh.SizeOfImage),
          "DllChars", hex(oh.DllCharacteristics), "Checksum", hex(oh.CheckSum))
    ep = oh.AddressOfEntryPoint
    for s in pe.sections:
        name = s.Name.rstrip(b"\0").decode(errors="replace")
        d = s.get_data()
        flag = " <- EP" if s.contains_rva(ep) else ""
        print(f"  {name:8} VA={s.VirtualAddress:#010x} VS={s.Misc_VirtualSize:#09x} RS={s.SizeOfRawData:#09x} ch={s.Characteristics:#010x} H={entropy(d):.2f}{flag}")
    for i, dd in enumerate(oh.DATA_DIRECTORY):
        if dd.Size: print(f"  dir[{i:2}] {dd.name:40} rva={dd.VirtualAddress:#x} size={dd.Size:#x}")
    if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        for imp in pe.DIRECTORY_ENTRY_IMPORT:
            names = [ (i.name.decode() if i.name else f"#{i.ordinal}") for i in imp.imports]
            print(f"  IMPORT {imp.dll.decode()} ({len(names)}): {', '.join(names)}")
    if hasattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT"):
        for imp in pe.DIRECTORY_ENTRY_DELAY_IMPORT:
            print("  DELAY", imp.dll.decode(), [ (i.name.decode() if i.name else i.ordinal) for i in imp.imports])
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        ex = [ (e.name.decode() if e.name else f"#{e.ordinal}") for e in pe.DIRECTORY_ENTRY_EXPORT.symbols]
        print(f"  EXPORTS ({len(ex)}):", ", ".join(ex[:80]), "..." if len(ex) > 80 else "")
    if hasattr(pe, "DIRECTORY_ENTRY_DEBUG"):
        for d in pe.DIRECTORY_ENTRY_DEBUG:
            e = getattr(d, "entry", None)
            print("  DEBUG type", d.struct.Type, getattr(e, "PdbFileName", b"") if e else "")
    if hasattr(pe, "RICH_HEADER") and pe.RICH_HEADER:
        vals = pe.RICH_HEADER.values
        print("  RICH:", [(vals[i] >> 16, vals[i] & 0xffff, vals[i+1]) for i in range(0, len(vals), 2)])
    if hasattr(pe, "VS_FIXEDFILEINFO"):
        for fi in getattr(pe, "FileInfo", []):
            for e in fi:
                if hasattr(e, "StringTable"):
                    for st in e.StringTable:
                        for k, v in st.entries.items(): print("  VER", k.decode(), "=", v.decode(errors="replace"))
