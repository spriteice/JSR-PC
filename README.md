# Jet Set Radio PC: pcrecomp handoff package

This is a starting kit for statically recompiling the 2013 Steam release of Jet Set Radio
into native Windows and Linux builds, with Vulkan and OpenGL renderers, using
[pcrecomp](https://github.com/sp00nznet/pcrecomp).

**No game files or generated code are included.** You need your own copy of the
game from Steam. The scripts verify it by hash and regenerate everything from it locally.

## Quickstart (Linux, Python 3.10+, gcc, git)

```bash
scripts/00_verify_inputs.sh "/path/to/steamapps/common/Jet Set Radio"
scripts/01_fetch_pcrecomp.sh     # the JSR-PC fork, pinned to 2290a86
scripts/02_lift.sh               # ~6 min: analyse, recover 18,102 functions, lift to C, name them
scripts/03_check.sh              # syntax check + pcrecomp difftest, vs data/baseline.json
```

## Building on Windows (the native32 host)

Needs Visual Studio 2022 or later, or its Build Tools, with the x86 C compiler and
the C++ CMake tools; Git for Windows; and Python 3.10+ (a venv keeps pcrecomp's
packages to itself). `build_win32.cmd` uses Visual Studio's own CMake and Ninja,
ahead of any other cmake on PATH such as MSYS2's or devkitPro's. From Git Bash:

```bash
py -3.12 -m venv work/venv && export PYTHON="$PWD/work/venv/Scripts/python.exe"
scripts/00_verify_inputs.sh "/c/Program Files (x86)/Steam/steamapps/common/Jet Set Radio"
scripts/01_fetch_pcrecomp.sh
scripts/02_lift.sh
cmd //c 'scripts\build_win32.cmd'       # build\win32\jsr-pc.exe
```

Run it with Steam running: `build\win32\jsr-pc.exe --game "<game folder>"`. The game
runs with its own folder as the current directory, so it finds `steam_api.dll`,
`steam_appid.txt` and its data there. `scripts\build_win32.cmd -DJSR_TRACE=ON`
builds in pcrecomp's bring-up diagnostics (`jsr-pc --help` lists them).

## Read next

- `AGENTS.md`: the brief for any agent working on this. Rules, current state, hosts, layout.
- `docs/MILESTONES.md`: the work, M0 to M7, with acceptance checks and a dependency graph.
- `docs/FINDINGS.md`: what is inside the exe.
- `docs/RUNTIME_SURFACE.md`: all 150 imports, and what each host must provide.

## Licence

MIT (`LICENSE`), for this repository's own work. `NOTICE` says what it doesn't
cover (the game, and the C lifted from it) and credits pcrecomp.

## Status (2026-11-05)

The whole exe lifts with every instruction translated (M1 is done), and the Windows
build plays: it reaches gameplay, writes saves and loads them back (M2 is done at
`10f62e5`). Next is mapping and naming the exe's functions, then Linux (M4a, M4b).

The case study with the full analysis is a Claude doc: "Jet Set Radio PC:
Reverse-Engineering Case Study".
