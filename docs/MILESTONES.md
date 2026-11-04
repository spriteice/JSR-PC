# Milestones and workstreams

Each milestone has a goal, tasks, and an acceptance check an agent can run. Milestones
on the same row of the dependency list can run in parallel.

```
M0 Reproduce
 ├─ M1 Lifter gaps ─────────────┐
 ├─ M2 Windows boot (native32) ─┼─ M3 Recovery cross-check (uses M2 traces)
 └─ M4a Linux shim stubs ───────┘
                 M2 ─► M4b Linux boot (win32hle) ─► M5 Renderer ─► M6 Audio/input/Steam ─► M7 Ship
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

## M2: First boot on Windows with native32 (Windows agent; MSVC x86)

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

## M3: Cross-check function recovery (analysis agent; needs Ghidra 11+)

- Run pcrecomp's `tools/ghidra/ExportFunctions.java` headless on the exe and score the
  result against `data/functions.json.gz` with `tools/disasm/score_recovery.py`.
- Feed every unresolved dispatch target from M2 runs back through `seed_from_log.py`,
  then relift.
- **Accept:** a written list of every function present in one catalog and missing from
  the other, each explained, and zero dispatch misses in M2's session after relifting.

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
