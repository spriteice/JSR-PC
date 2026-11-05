# Milestones and workstreams

Each milestone has a goal, tasks, and an acceptance check an agent can run. Milestones
on the same row of the dependency list can run in parallel.

```
M0 Reproduce
 ├─ M1 Lifter gaps ─────────────┐
 ├─ M2 Windows boot (native32) ─┼─ M3 Recovery cross-check (uses M2 traces)
 └─ M4a Linux shim stubs ───────┘
                 M2 ─► M4b Linux boot (win32hle) ─► M5 Renderer ─► M6 Audio/input/Steam ─► M7 Ship
                 M0 ─► M3b Function map and names (ongoing; feeds every later milestone)
```

---

## M0: Reproduce the baseline (any agent, ~10 min)

- Run `scripts/00_verify_inputs.sh <game dir>`, `01_fetch_pcrecomp.sh`, `02_lift.sh`,
  `03_check.sh`.
- **Accept:** the numbers match `data/baseline.json`: 18,102 functions, 0 unimplemented
  instructions, 0 syntax errors, difftest 392/392. A different count
  means a different input or pin; report it before going further.

## M1: Close the lifter gaps (lifter agent) — done at `4bbe636`

- `paddw` in `sub_005CF8EB`, `sub_005CF92E` and `sub_005CFBE6` is the SSE2 xmm form,
  not MMX: lift32 already lifted MMX `paddw`, and `lift32_sse` covered wrapping packed
  add and sub for the d and q lanes only. The fork covers every lane width (b, w, d, q).
- `cli` in `sub_0044B320` lifts as `recomp_privileged()`, a host trap that logs the
  address and stops, never a silent no-op (so do `sti` and `hlt` in Win32 code).
  Whether its path is reachable is still open (`docs/FINDINGS.md`); if it is, the trap
  names it on the first run.
- 18 new difftest cases and `tools/lift/test_privileged.py` in the fork.
- **Accept:** `tools/unimplemented_report.py work/gen` reports 0, and difftest passes with
  the new cases included.

## M2: First boot on Windows with native32 (Windows agent; MSVC x86) — done at `10f62e5`

- Create `src/host_win32/` from the CMake template: `main()` calls `native32_init()`,
  `native32_map()` and `native32_bind()` for the exe, then `native32_call_guest(0x005D7D92)`.
  Keep the real `steam_api.dll` next to the build, and Steam running, for the first
  boot. Write `setup.dat` by running the original launcher once.
- Bring-up order and evidence to capture at each stage: CRT start-up, `WinMain`, window
  created, `Direct3DCreate9` and device creation, the first `Present`, the SEGA logo,
  the title screen, the first playable area, save and load.
- At each stage, capture reference screenshots and a `--calltrace` of the original exe.
  M4b and M5 compare against them.
- **Accept:** the recompiled exe reaches gameplay and saves. A 10-minute session shows
  no dispatch misses (`recomp_lookup` logging) and no VEH crash dumps.
- **First boot (2026-11-04, desktop, MSVC 19.51, a test build at `3990a89` with the
  two lifter fixes stood in by `CL=/FIrecomp_funcs.h` and `LINK=/FORCE:UNRESOLVED`):**
  all 150 imports bound (143 native, 7 shimmed, 0 unresolved). The lifted CRT
  start-up ran 1,352 indirect calls, then crashed after 5.7 s reading 0x455F5245 in
  `sub_00591590`, the input set-up, before any window showed. It passes the guest's
  hInstance (0x00400000) to `DirectInput8Create`, which refuses a module Windows
  didn't load, and reads the interface pointer without checking the result. The
  host now shims `DirectInput8Create` with its own handle. The game folder was
  unchanged.
- **Second boot (`39a6334`, no stand-ins):** the game window opens and shows the
  Loading screen, and stays there: no new code is reached after 10 s, reads stop at
  22.9 MB, and the load state machine (`sub_004B9210`) waits for an overlapped read
  that never finishes. The game allocates its 16 MB main RAM at exactly 0x20000000
  (`sub_00578EF0`), where the host was linked, so the allocation failed and the
  read into that range failed with its OVERLAPPED still pending. The host now
  links at 0x30000000 and holds the range for the game until it runs.
- **Third boot (`10f62e5`, 2026-11-04):** the SEGA logo, the title, the menus, stage
  select and gameplay. A 20.9-minute session loaded an existing save, played, wrote
  two saves through Steam Remote Storage (`SAVE/0/JETSET___SYS` changed,
  `SAVE/9/JETSET___SYS` new) and exited with code 0, with no unresolved-call lines
  and no crash dumps, in 233 to 268 MB of private memory. A second session, 68 s,
  loaded the save the first one wrote and played on. Steam showed the game as
  being played. The game folder was unchanged after both.
- **Seen, not yet compared with the original exe:** the overlay shows 31 FPS in
  gameplay against 62 on the SEGA logo, and the main thread uses about 97% of a
  core. Some background buildings in cutscenes show poor LOD. In the extra-large
  graffiti picker, the selected icon does not light up as it does in the others.

## M3: Cross-check function recovery (analysis agent; needs Ghidra 11+)

- Run pcrecomp's `tools/ghidra/ExportFunctions.java` headless on the exe and score the
  result against `data/functions.json.gz` with `tools/disasm/score_recovery.py`.
- Feed every unresolved dispatch target from M2 runs back through `seed_from_log.py`,
  then relift.
- **Accept:** a written list of every function present in one catalog and missing from
  the other, each explained, and zero dispatch misses in M2's session after relifting.
- **Cross-check (2026-11-05, Ghidra 12.2):** `scripts/ghidra_crosscheck.sh <Ghidra dir>`
  redoes it in about 4 minutes. Ghidra analyses the exe, `ExportFunctions.java` and
  `DumpBounds.java` export its functions, and `score_recovery.py` scores the catalogue
  against them. `data/recovery_crosscheck.tsv` lists the 3,519 addresses where the two
  differ, each with what Ghidra has there, what in the exe points at it, and a reason;
  none is unexplained. Ghidra has 10,994 functions to our 13,726 starts, and 10,696
  agree: recall 97.3%, precision 77.9%. 97.4% of those end where Ghidra's do; the
  other 282 end short at our next start (155) or run on past Ghidra's end (127).
  - **Our 3,030 extra starts:** 2,058 incremental-linking stubs and 496 functions
    reached only through them (Ghidra decodes only the stubs it reaches, and makes a
    function of none); 77 SEH filters and `__except` and `__finally` blocks in the C
    runtime, named by scope tables Ghidra doesn't read; 150 functions named by a pushed
    address or a value in data, which Ghidra references without making a function; 168
    false starts inside Ghidra's functions (94 jump labels, 61 data values that equal an
    instruction's address, 12 chance E8 and E9 bytes and a prologue), each lifted inside
    the function before it too, as the lifted C shows, so the lift loses nothing; 67
    found only by our scans, or called only from such code; and 14 data decoded as
    code.
    `sub_0044B320` is one of the 14: its `cli` (M1) is the first byte of a switch
    table, so it never runs.
  - **Our 191 aliases outside Ghidra's functions:** 127 C++ EH handler stubs, 37
    entries of functions Ghidra doesn't have, and 27 in code Ghidra gives another
    function or leaves past a function's end.
  - **Ghidra's 298 starts that aren't ours:** 287 C++ EH funclets, which the catalogue
    keeps as entries of the function that installs them; 6 labels inside one of our
    bodies; 4 that nothing references; and one gap, 0x005E0178. It is a C runtime
    function's `catch (...)` block, straight after its `try` body and so inside that
    body's decode, and no entry was made for it: a throw caught there would stop on
    "funclet is not lifted". The other 287 C++ funclets and all 105 SEH ones are
    entries. disasm32 reads the tables already but only turned existing entries into
    aliases; a fork fix that adds such a funclet as an alias adds this one entry and
    changes nothing else in the catalogue.
  - **Dispatch misses:** none in M2's sessions or in this thread's runs, so nothing
    was seeded.
  - For naming (M3b): the 168 false starts are `start` rows in the map and are not
    functions, and 0x0045C2B0, which an incremental-linking stub names, is a function
    the catalogue keeps as an alias. Ghidra's Function ID names 805 functions, 94 of
    them ambiguous (`FID_conflict`), in `work/ghidra/jetsetradio_functions.txt`.
- Next: the disasm32 fix and a relift, after review.

## M3b: Map and name functions (any agent; ongoing)

- `tools/map_functions.py` writes `data/function_map.tsv` (see "Naming functions" in
  `AGENTS.md`). It takes names from the functions' own log and assert strings, RTTI
  vtables, the vtable a constructor or destructor stores, `__FILE__` paths, the
  incremental-linking table and the import thunks, and merges `data/names_manual.tsv`.
- **First pass (2026-11-05, the catalogue at `b4f1cda`):** 404 of 8,772 function starts
  named: 103 from their own strings, 292 from RTTI (`Class::vfN`; RTTI names classes,
  not members) and 9 by hand from what M2 found (the file reads, `MapDCAddress`,
  `Input_Init`). 249 entries are placed in 24 source files. Nearly all are in the
  Katana framework, Ninja, Shinobi and the PC layer, from 0x544000 on. The Dreamcast
  game code, 5,126 starts below 0x544000, has 2: `markGraffitiUsed` and `Load_Step`.
- **Names in the lift (2026-11-05, pcrecomp `84af660`):** `02_lift.sh` puts the map's
  names into the generated C with `name_lift.py --known-only`, so the C and the map
  agree: 1,154 of 18,102 entries. The map adds 143 constructors and destructors, found
  by the vtable they store (547 starts named, +143), and 146 more stubs and thunks named
  after the function they reach (607). Each function's header counts its callers through
  its incremental-linking stub, so `MapDCAddress` reads "called from 28 places" where it
  read "not called directly". One constructor or destructor (0x5C9030) is read short,
  because the catalogue has a false start inside it at 0x5C9067: M3's cross-check should
  find starts like that.
- Next, in order:
  1. A replacement path: a listed function is left out of the lift and written by hand
     in `src/game/`, then compared with the lifted version.
  2. The C runtime and other linked libraries by signature (Ghidra's Function ID, with M3).
     A guest name must not collide with a C library name the generated files declare
     (`memcpy`, `floor`).
  3. The game code by role: what each function calls (Ninja draws, file reads, sound)
     and the function-pointer tables it sits in (2,939 code pointers in data).
- **Accept (each pass):** the script runs on the verified exe, every manual name has a
  note, the counts are recorded here, and `audit_repo.py` reports CLEAN.

## M4a: Linux shim stubs (Linux agent; can start right after M0)

- In `src/host_linux/`, register win32hle modules for the DLLs it lacks (see
  `docs/RUNTIME_SURFACE.md`): `d3d9`, `d3dx9_43`, `XINPUT1_3#2`, `DINPUT8`,
  `steam_api` (13 calls), and an XAudio2 COM class for `CoCreateInstance`. Each starts
  as a logged stub that returns success with plausible out-parameters.
- **Accept:** the binary links on Linux x86-64 (based memory, `RECOMP_MEM_BASE`) and
  every import binds. `--firsthit` shows execution reaching the first
  `Direct3DCreate9`.

## M4b: Boot on Linux with win32hle (Linux agent; needs M2's reference)

- Port native32's guest C++ exception handling (`eh32.c`) to win32hle. The exe has 414
  C++ EH funclets, and pcrecomp's README lists guest exceptions as out of scope for
  win32hle.
- Find where the game reads `setup.dat` (file-open trace) and write it from the host.
- **Accept:** the same stage list as M2, reached on Linux, with the calltrace prefix
  matching the Windows reference up to the first `Present`.

## M5: Renderer (graphics agent; needs M4a, references from M2)

- One renderer interface (`src/render/`) with two backends: **Vulkan** (primary) and
  **OpenGL 3.3 core**. Present through the SDL2 window win32hle already owns.
- The `d3d9` shim translates `IDirect3DDevice9` calls into that interface. Later, an
  optional second front end at the Ninja shim (`nj*` functions in
  `data/identifiers.json`) can bypass D3D9 entirely.
- Shaders: the exe embeds one HLSL source blob (about 190 lines) with 7 pixel shaders
  (`PShader_Tex`, `_Tex2`, `_Tex_Toon`, `_Fill`, `_Fill2`, `_Fill_Toon`, `_YUV`), read
  from the user's exe at build time. Compile to SPIR-V (glslang) and to GLSL
  (SPIRV-Cross) at build time, and drop `D3DXCompileShader`. Never commit the source
  blob or its translation.
- Vertex stage: no vertex shaders are embedded. Confirm whether the game uses D3D9
  fixed-function transform or pre-transformed vertices, then generate the matching
  vertex shader per backend.
- `PShader_YUV` implies CPU-decoded video frames converted on the GPU. Find the
  decoder (`CVideoWin32`) and keep it lifted.
- Interim option for bring-up: forward the `d3d9` shim to DXVK built as a native Linux
  library, if a maintained build is available. Evaluate before relying on it.
- **Accept:** for each M2 reference scene, Vulkan and OpenGL frames differ from the
  Windows D3D9 capture by less than an agreed per-pixel tolerance (start at 2% of
  pixels over 8/255). Both backends run on Windows and Linux.

## M6: Audio, input and Steam (runtime agent; needs M4a)

- XAudio2 2.7 on FAudio, or on win32hle's SDL2 audio. The game's own Vorbis decoder
  and MIDI-bank code are lifted and stay as they are.
- XInput through the SDL2 gamepad API; DInput8 keyboard through SDL2 keyboard events.
  The default bindings come from the launcher (`Forward`, `Back`, `Left`, `Right`,
  `Jump`, `Dash`, `Graffiti`, camera keys).
- Steam: an offline stub that keeps achievements and stats in a local file, plus an
  optional real Steamworks path on both OSes.
- **Accept:** music, sound effects and voice play in sync on both hosts. A pad and a
  keyboard can complete the tutorial. Saves persist across runs with Steam stubbed.

## M7: Ship hygiene (any agent; last)

- `audit_repo.py` reports CLEAN, and no lifted file appears anywhere in git history
  (`docs/PUBLISHING.md` in pcrecomp has the checks).
- The README states "bring your own Steam copy" with the hashes, and a one-command build
  from a game directory on each OS.
- **Accept:** a fresh clone, plus a user's own game directory, builds and boots on
  Windows and Linux.
