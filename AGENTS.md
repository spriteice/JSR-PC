# Agent brief: Jet Set Radio (PC, 2013) native port via pcrecomp

Read this file first, then `docs/MILESTONES.md` for your task. The rules for every change
are in `docs/project-rules.md` and `docs/build-and-test-reference.md`. Everything here was
verified on 2026-11-04 against the exact build in `data/inputs.sha256`.

## Mission

Turn the 2013 Steam release of Jet Set Radio (`jetsetradio.exe`, 32-bit x86, MSVC 2010)
into a native program for **Windows and Linux**, with **Vulkan and OpenGL** renderers,
by static recompilation with [pcrecomp](https://github.com/sp00nznet/pcrecomp).
No emulator, no Wine, no Proton.

## Hard rules

1. **Game material and lifted output stay where they are.** They stay on the user's PC,
   or in the cloud sandbox that holds them for its own work, and are never sent anywhere
   else. Never commit, upload, paste or quote: the game binaries, extracted assets (`.AFS`,
   `.ADX`, PNG UI art), screenshots of the game, or anything under `work/` — the generated
   C is a derivative of SEGA's code. Metadata is fine: addresses, function names like
   `sub_005CF8EB`, import names, counts, logs that do not contain instruction text.
   Hand-written C that reimplements a game function is ours, under the rules in
   `docs/project-rules.md` ("Game code"). Run
   `python third_party/pcrecomp/tools/audit_repo.py .` before every commit.
2. **Bring your own game.** Every new checkout and every lift starts with
   `scripts/00_verify_inputs.sh`. A file that does not match the hash is a different
   build: stop and report it.
3. **Never hand-edit generated C.** Fix the lifter (in a pcrecomp fork, with a difftest
   case), add a named override or reimplementation in `src/game/`, or seed a missed function
   (`tools/disasm/seed_from_log.py`). Regenerate; do not patch `work/gen/`.
4. **Pin the toolchain.** pcrecomp comes from the JSR-PC fork
   ([spriteice/pcrecomp](https://github.com/spriteice/pcrecomp)), pinned to `2290a86`. Moving the pin is its own
   change: rerun `scripts/02_lift.sh` and `03_check.sh`, and update `data/baseline.json`.
5. **No copy protection to remove, and none to add.** This build has no SteamStub.
   If you meet a protected build, stop.
6. **Report numbers, not adjectives.** Every milestone report states the commands run,
   the counts produced, and the diff against `data/baseline.json`.

## Current state

| Stage | Result |
| --- | --- |
| Inputs | 4 files verified by SHA-256 (game exe, .NET launcher, `steam_api.dll`, `steam_w.dll`) |
| Function recovery | 18,102 entries: 8,772 function starts, 4,376 aliases (labels inside another body), 4,912 incremental-linking stubs and 42 other thunks; 77.2% byte coverage (most of the rest is 362 KB of int3 padding) |
| Function map | `data/function_map.tsv`: 547 of the 8,772 starts named (292 from RTTI vtables, 143 constructors and destructors from the vtable they store, 103 from their own log strings, 9 by hand), and 607 stubs and thunks, each named after the function it reaches; 249 starts placed in 24 source files. The Dreamcast game code (5,126 starts) has 2 |
| Lift | 19 C files + dispatch table + header, 4.10 M lines; 4,639 indirect-call sites, all through an 18,102-entry dispatch table. The 1,154 entries the map names carry that name in the C, each with a header that counts its callers |
| Unimplemented | 0 at `2290a86`. At the original pin (`ef3f0da`) there were 7 in 4 functions: SSE2 `paddw` (xmm) x2 in each of `sub_005CF8EB`, `sub_005CF92E`, `sub_005CFBE6`, and `cli` x1 in `sub_0044B320` |
| Compile | All 20 `.c` files pass `gcc -fsyntax-only` with implicit declarations as errors: 0 errors, 0 warnings. At `4bbe636`, MSVC 19.51 rejected 10 files (C2371: a call before the callee's declaration) and the link failed on one call to an address outside the image (`sub_CD0CE8FE`); both are fixed in the lifter |
| Lifter self-test | `difftest.py`: 392/392 cases match hardware (needs `RECOMP_CC=scripts/gcc-lm` on Linux) |
| Windows run | M2 is done at `10f62e5` (MSVC 19.51). The game reaches gameplay, writes saves and loads them back; a 20.9-minute session exited with code 0, with no unresolved calls and no crash dumps |

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
LICENSE, NOTICE       MIT for our own work; what it doesn't cover, and pcrecomp's credit
docs/FINDINGS.md      facts about the binary; read before touching the runtime
docs/MILESTONES.md    the work, split into milestones and parallel workstreams
docs/RUNTIME_SURFACE.md  all 150 imports and who answers them on each host
docs/project-rules.md    where code goes, how it's written, the checks before a commit
docs/build-and-test-reference.md  building, running the game, tests, the review pack
docs/release-checklist.md  the critical-bug gate and the release steps
CMakeLists.txt        the Windows host's build (MSVC x86)
src/host_win32/       the native32 host: main(), the guest-module shims
data/                 metadata only: hashes, pe_analysis.json, functions.json.gz,
                      identifiers.json, unimplemented_sites.json, baseline.json,
                      function_map.tsv (generated), names_manual.tsv (by hand)
scripts/              00-03 reproduce the baseline (PYTHON picks the interpreter);
                      gcc-lm is a difftest wrapper; build_win32.cmd builds the host;
                      ci_checks.sh and ci_win32.cmd are CI's two jobs
.github/workflows/    ci.yml: CI on every push to main, with no game files
tools/                analysis helpers (pe_info, code_stats, fn_estimate,
                      unimplemented_report, runtime_surface, map_functions)
work/                 (gitignored) input copies, logs, generated C
third_party/pcrecomp  (gitignored) pinned toolchain
```

## Naming functions

- `data/function_map.tsv` has one row per catalogue entry: address, kind, name, source
  file, evidence, target, and for a function that is to be replaced, its calling
  convention and argument count. `tools/map_functions.py` writes it from the verified
  exe; never edit it by hand. Rerun it after a change to `data/names_manual.tsv` or to
  the catalogue (a pin move), and commit the result with the change.
  `scripts/02_lift.sh` stops if the committed map is out of date.
- The lifted C takes its names from the map and nowhere else: `02_lift.sh`'s last step
  runs pcrecomp's `name_lift.py --known-only`. The C name is the map's name with `::`
  as `__` (`AudioPlayback__OggPlay`) and `~` as `destructor_`; a name used twice gets
  `_` and the address. Above each function, a header says how many places call it,
  counting calls through its incremental-linking stub.
- To name a function, add a row to `data/names_manual.tsv`: address, name, source file
  if known, and a note saying what the function does that earns the name and where
  you saw it (a call, a constant, a trace). Before a function is reimplemented or
  overridden, its row also gets `call` (cdecl, stdcall, thiscall or fastcall) and
  `args` (its 4-byte stack arguments, not counting `this` in ecx or a fastcall's ecx
  and edx), and the note says what shows them. A manual name replaces an RTTI slot name
  (`Class::vfN`) or a constructor or destructor name; one that differs from the name
  a function's own string gives stops the script with an error.
- A function that stores a class's vtable into the object it is given is that class's
  `Class::constructor` or `Class::destructor`: a constructor calls its base's first and
  then stores its own vtable, a destructor stores its own and then calls its base's.
  When the order doesn't tell, the name is `Class::constructor_or_destructor`.
- Names the exe spells out keep its spelling (`njCnkDrawModel`, `AudioPlayback::OggPlay`).
  Names we assign are `Area_Verb` in CamelCase (`File_ReadAsync`, `Input_Init`). Never
  give an SDK name (`nj`, `gdFs`, `ADX`, `bu`, `pd`) unless a string or a match proves it;
  put the likely SDK name in the note instead.
- Notes describe behaviour. They never quote code, and never quote a string from the
  exe other than a name or a path (rule 1).
- A `mentions=` row is a name string the script could not attribute. Settle it by hand.

## Conventions

- Host code lives in `src/host_win32/` (native32) and `src/host_linux/` (win32hle);
  shared shims in `src/shims/`, the renderer in `src/render/{vk,gl}/`, and hand-written
  game code (overrides and reimplementations) in `src/game/`.
- Build with CMake (`CMakeLists.txt`, from pcrecomp's template): no ASLR, the host at
  a fixed 0x30000000 with a 256 KB first-thread stack so the image's range at
  0x00400000 stays free (`native32_hold_image`), and the game on a thread with a
  64 MB stack. Entry VA 0x005D7D92.
- The game allocates 16 MB at exactly 0x20000000 for its Dreamcast-era main RAM
  (`sub_00578EF0`) and maps 0x8C000000-based addresses into it (`sub_00597A30`).
  Nothing of the host may be there; the host holds the range until the game runs.
- Bring-up builds use `-DRECOMP_TRACE` with `runtime/recomp32/recomp_trace.c`
  (`--calltrace`, `--firsthit`, `--watch`, `--poison`, `--poke`).
- Reference screenshots and traces from the Windows host stay on the PC, in
  `Building\reference\` (`docs/build-and-test-reference.md`, "Running the game"). The repo
  holds only what's drawn from them: counts, addresses and stage lists.
