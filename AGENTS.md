# Agent brief: Jet Set Radio (PC, 2013) native port via pcrecomp

Read this file first, then `docs/MILESTONES.md` for your task. Everything here was
verified on 2026-11-04 against the exact build in `data/inputs.sha256`.

## Mission

Turn the 2013 Steam release of Jet Set Radio (`jetsetradio.exe`, 32-bit x86, MSVC 2010)
into a native program for **Windows and Linux**, with **Vulkan and OpenGL** renderers,
by static recompilation with [pcrecomp](https://github.com/sp00nznet/pcrecomp).
No emulator, no Wine, no Proton.

## Hard rules

1. **No game material or lifted output leaves the user's machine.** Never commit, upload,
   paste or quote: the game binaries, extracted assets (`.AFS`, `.ADX`, PNG UI art),
   or anything under `work/` — the generated C is a derivative of SEGA's code.
   Metadata is fine: addresses, function names like `sub_005CF8EB`, import names,
   counts, logs that do not contain instruction text. Run
   `python third_party/pcrecomp/tools/audit_repo.py .` before every push.
2. **Bring your own game.** Every run starts with `scripts/00_verify_inputs.sh`. A file
   that does not match the hash is a different build: stop and report it.
3. **Never hand-edit generated C.** Fix the lifter (in a pcrecomp fork, with a difftest
   case), add a manual override in host code, or seed a missed function
   (`tools/disasm/seed_from_log.py`). Regenerate; do not patch `work/gen/`.
4. **Pin the toolchain.** pcrecomp is pinned to `ef3f0da`. Moving the pin is its own
   change: rerun `scripts/02_lift.sh` and `03_check.sh`, and update `data/baseline.json`.
5. **No copy protection to remove, and none to add.** This build has no SteamStub.
   If you meet a protected build, stop.
6. **Report numbers, not adjectives.** Every milestone report states the commands run,
   the counts produced, and the diff against `data/baseline.json`.

## State on hand-off

| Stage | Result |
| --- | --- |
| Inputs | 4 files verified by SHA-256 (game exe, .NET launcher, `steam_api.dll`, `steam_w.dll`) |
| Function recovery | 18,102 functions (2,460 thunks, 6,832 leaves); 77.2% byte coverage (most of the rest is 362 KB of int3 padding) |
| Lift | 19 C files + dispatch table + header, 4.04 M lines, in 175 s; 4,639 indirect-call sites, all through an 18,102-entry dispatch table |
| Unlifted | 7 instructions in 4 functions: `paddw` x2 in each of `sub_005CF8EB`, `sub_005CF92E`, `sub_005CFBE6`; `cli` x1 in `sub_0044B320` |
| Compile | All 20 `.c` files pass `gcc -fsyntax-only` with 0 errors. **Not yet linked or run.** |
| Lifter self-test | `difftest.py`: 374/374 cases match hardware (needs `RECOMP_CC=scripts/gcc-lm` on Linux) |

Reproduce it: `00_verify_inputs.sh <game dir>`, `01_fetch_pcrecomp.sh`, `02_lift.sh`, `03_check.sh`.

## What the binary is (one paragraph)

The original Dreamcast C codebase (742 C objects) compiled for x86, running on a
hand-written emulation of the Dreamcast SDK — SEGA's Ninja graphics library (`nj*`),
the GD-ROM file system (`gdFs*`) and CRI ADX/AFS — that sits on Direct3D 9, XAudio2
and Win32. A C++ layer (143 objects, 58 RTTI classes) adds the PC menus, options,
subtitles, achievements, leaderboards and cloud saves. It ships its full relocation
table (68,163 entries), which is why the lift is clean. Details: `docs/FINDINGS.md`.

## Hosts

- **Windows → `native32`** (MSVC x86, 32-bit process): forwards every import, COM call
  and callback to real Windows. C++ exceptions are handled by `eh32`. The fastest path
  to a first boot, and the reference for every later comparison.
- **Linux → `win32hle`** (x86-64 with based guest memory, or `-m32` flat): pcrecomp's
  implemented Win32 on libc + SDL2. It lacks D3D9, D3DX, XAudio2, XInput, DInput8,
  Steam, and guest C++ exceptions. Those are this project's work
  (`docs/RUNTIME_SURFACE.md`).

## Layout

```
AGENTS.md             this brief
README.md             human quickstart
docs/FINDINGS.md      facts about the binary; read before touching the runtime
docs/MILESTONES.md    the work, split into milestones and parallel workstreams
docs/RUNTIME_SURFACE.md  all 150 imports and who answers them on each host
data/                 metadata only: hashes, pe_analysis.json, functions.json.gz,
                      identifiers.json, unimplemented_sites.json, baseline.json
scripts/              00-03 reproduce the baseline; gcc-lm is a difftest wrapper
tools/                analysis helpers (pe_info, code_stats, fn_estimate,
                      unimplemented_report, runtime_surface)
work/                 (gitignored) input copies, logs, generated C
third_party/pcrecomp  (gitignored) pinned toolchain
```

## Conventions

- Host code lives in `src/host_win32/` (native32) and `src/host_linux/` (win32hle);
  shared shims in `src/shims/`, the renderer in `src/render/{vk,gl}/`.
- Build with CMake, starting from `third_party/pcrecomp/templates/CMakeLists.txt.template`
  (no ASLR, 8 MB stack, image base 0x00400000, entry VA 0x005D7D92).
- Bring-up builds use `-DRECOMP_TRACE` with `runtime/recomp32/recomp_trace.c`
  (`--calltrace`, `--firsthit`, `--watch`, `--poison`, `--poke`).
- Reference screenshots and traces from the Windows host go in `docs/reference/`
  (your own captures only; see rule 1 for anything that is game art).
