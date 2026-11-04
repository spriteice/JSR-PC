#!/usr/bin/env python3
"""Render docs/RUNTIME_SURFACE.md from pcrecomp's pe_analyze JSON.

Lists every import jetsetradio.exe binds, with who answers it on each host:
native32 (Windows, real APIs) and win32hle (Linux, pcrecomp's implemented Win32),
and what this project must add. Plan text lives in PLAN below; edit it there.

    python3 -I tools/runtime_surface.py data/pe_analysis.json > docs/RUNTIME_SURFACE.md
"""
import collections, json, sys

# dll (lower-case) -> (win32hle status today, work for this project)
PLAN = {
    'kernel32.dll': ('Implemented (kernel32.c, kernel32_ext.c, kernel32_crt.c)',
                     'Check each import against win32hle; ~80% are MSVC CRT start-up calls'),
    'user32.dll':   ('Implemented (user32.c, screen.c)',
                     'One window, a message pump, cursor; SDL2 window must also own the Vulkan/GL surface'),
    'gdi32.dll':    ('Implemented (gdi32.c)', 'CreateBrushIndirect only'),
    'advapi32.dll': ('Implemented: in-memory registry (advapi32.c)', 'Registry writes only; persist or drop'),
    'ole32.dll':    ('Implemented: COM bookkeeping + host-served class factories (ole32.c)',
                     'Register an XAudio2 class factory that CoCreateInstance can return'),
    'winmm.dll':    ('Implemented (winmm.c)', 'timeGetTime only'),
    'd3d9.dll':     ('Not implemented (win32hle d3d.c is DirectX 6 Direct3D, software)',
                     'NEW: IDirect3D9/IDirect3DDevice9 over the Vulkan + OpenGL renderer interface'),
    'd3dx9_43.dll': ('Not implemented',
                     'NEW: texture-from-file (PNG/DDS), texture-from-memory, and CompileShader replaced by precompiled shaders'),
    'xinput1_3.dll':('Not implemented', 'NEW: ordinal 2 = XInputGetState on SDL2 gamepad'),
    'dinput8.dll':  ('Not implemented', 'NEW: DirectInput8Create keyboard device on SDL2 keyboard'),
    'steam_api.dll':('Not implemented', 'NEW: stub (offline) or forward to real Steamworks; 13 imports'),
}


def main(path):
    a = json.load(open(path))
    by = collections.OrderedDict()
    for imp in a['imports']:
        name = imp['name'] or f"#{imp['ordinal']}"
        by.setdefault(imp['dll'], []).append(name)
    out = ['# Runtime surface: every import jetsetradio.exe binds', '',
           f"{sum(len(v) for v in by.values())} imports across {len(by)} DLLs, from `data/pe_analysis.json`. "
           'On Windows, `native32` forwards all of them to the real DLLs, so a first boot needs no new code. '
           'On Linux, `win32hle` answers them itself; rows marked NEW are this project\'s work.', '',
           '| DLL | Imports | win32hle today | Work for this project |', '| --- | --- | --- | --- |']
    for dll, names in by.items():
        st, work = PLAN.get(dll.lower(), ('Unknown', 'Check'))
        out.append(f'| {dll} | {len(names)} | {st} | {work} |')
    out += ['', '## Full list', '']
    for dll, names in by.items():
        out.append(f'**{dll}** ({len(names)}): ' + ', '.join(f'`{n}`' for n in names))
        out.append('')
    out += ['## Not imported but needed', '',
            '- `steam_w.dll` is NOT used by the game: the exe never names it. The .NET launcher `jsrsetup.exe` '
            'P/Invokes its one export, `SteamUserDataPath`, to find where to write `setup.dat`. '
            'A port replaces the launcher, so the host must write `setup.dat` itself where the game looks for it '
            '(find that path in M2 with `--firsthit` / file-open tracing).',
            '- XAudio2 2.7 has no import: it is created through `CoCreateInstance`, so it lands on ole32.',
            '']
    print('\n'.join(out))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data/pe_analysis.json')
