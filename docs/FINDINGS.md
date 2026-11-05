# Findings: jetsetradio.exe (Steam, 2013-03-12)

These are facts about the binary, gathered by static inspection on 2026-11-04. No game code
is reproduced here. Raw metadata is in `data/`.

## Files

| File | SHA-256 (prefix) | What it is | Port needs it? |
| --- | --- | --- | --- |
| jetsetradio.exe | 26f0ab97 | The game. PE32 i386, MSVC 2010 SP1 (Rich build 40219), PDB `D:\Repos\Sega\JetSetRadio\trunk\Release\jetsetradio.pdb` | Yes: the lift input |
| jsrsetup.exe | b1e1006d | WPF .NET launcher. Writes `setup.dat` (resolution, windowed, MSAA, key bindings) under the folder from `steam_w!SteamUserDataPath`; shows "Steam is not running" | No: the host writes `setup.dat` |
| steam_api.dll | 901f65de | Stock Valve Steamworks client API (2011), Authenticode-signed | Windows bring-up only; stubbed later |
| steam_w.dll | 6091b7c9 | One export, `SteamUserDataPath`. The PDB shows it was built for SEGA's Sonic CD port. Used **only by the launcher** | No |

## Image layout

| Item | Value |
| --- | --- |
| Image base / entry | 0x00400000 / 0x005D7D92 (RVA 0x1D7D92) |
| DllCharacteristics | 0x8140: dynamic base, NX, terminal-server aware |
| .text | VA 0x401000, 2.09 MB, entropy 5.85; about 362 KB is int3 padding in 1,773 runs |
| .rdata / .data | 1.92 MB / 6.08 MB virtual (1.22 MB on disk: about 4.9 MB of zero-filled statics) |
| .reloc | 68,163 base relocations: 9,711 point into code; 2,939 are code pointers stored in data (1,746 distinct targets) |
| Protection | None: no `.bind` (SteamStub), no packer, no `SteamAPI_RestartAppIfNecessary` import |
| Objects | 742 C units (the Dreamcast game), 143 C++ units (PC layer) |
| Floating point | Scalar SSE in game code (about 64k SSE instructions); x87 (about 8.5k) mostly in the CRT; some MMX |

## Architecture

1. **Dreamcast game code (C).** Loads 127 named `.AFS` archives (`data/identifiers.json`)
   and many `.ADX` voice and SFX files by name.
2. **Dreamcast SDK shim.** Reimplements 45 named SDK entry points (`njCnkDrawModel`,
   `njDrawSprite2D`, `njSetFadeColor`, `njWaitVSync`, `gdFsOpen`, `ADXT_FilenameSetup`, …)
   on D3D9, XAudio2 and Win32 files. Audio goes through an `AudioPlayback::` module
   (Ogg Vorbis streams, MIDI banks via `MidPlay`, one-shot SFX with reverb).
3. **PC layer (C++).** `CApplication`, `CSoundXAudio2`, `CVideoWin32`, `CVorbisDecoder`
   and `XFont`, plus a widget toolkit (`DlgBase`, `BtnBase`, `MsgBox`, `Popup`, `Fader`)
   used by `MainMenu`, `PauseMenu`, `SaveLoadMenu`, `DlgOptions*`, `Leaderboards`,
   `Achievements`, `Subtitles`, `UpsellScreen` and `StoreView`.

## Graphics

- `Direct3DCreate9`; D3DX 9.43: texture from file and from memory, and `D3DXCompileShader`
  at run time.
- One embedded HLSL source blob (about 7 KB, 191 lines) holds **7 pixel shaders and no
  vertex shaders**: `PShader_Tex`, `PShader_Tex2`, `PShader_Tex_Toon`, `PShader_Fill`,
  `PShader_Fill2`, `PShader_Fill_Toon`, `PShader_YUV`. The toon pair is the cel shading;
  YUV is the video path.
- Open question: fixed-function vertex transform or pre-transformed vertices? Answer it
  from the device calls (`SetTransform`, `SetFVF`, `SetVertexDeclaration`) during M2.

## Control flow (for the lifter)

- 1,652 indirect calls and 655 indirect jumps found by a linear sweep. pcrecomp routes
  4,639 `RECOMP_ICALL` sites through its dispatch table.
- 414 C++ EH stubs and funclets: the PC layer uses C++ exceptions, so Linux needs guest
  EH support. Their tables name 128 handler stubs and 288 funclets. One funclet, the
  `catch (...)` block at 0x005E0178 in a C runtime function, sits inside its function's
  body and has no catalogue entry (M3). One handler stub, the C runtime's at
  0x00613FC2, checks the /GS cookie before it loads its FuncInfo; native32's eh32
  recognises a C++ frame only by a handler that loads it first, so it would pass over
  that frame.
- SEH: 80 `_except_handler4` scope tables name 105 filters and `__except` and
  `__finally` blocks, all in the C runtime, and all are catalogue entries. eh32
  handles C++ frames only.
- Not yet checked: run-time code generation or self-patching. Watch for writes to `.text`
  and calls into heap memory during M2.
- The exe was linked incrementally. `.text` starts with a table of 4,912 five-byte
  `jmp` stubs (0x401005 to 0x406FF0, in no useful order), and direct calls and vtable
  slots go through them. Of the catalogue's 18,102 entries, 4,912 are these stubs,
  4,376 are aliases (labels inside another body: shared epilogues, switch arms, EH
  funclets), 42 are other thunks and 8,772 are function starts.

## Where the code lives

From the functions that pass a `__FILE__` path or their own name (`data/function_map.tsv`):

| Range | What | Anchors |
| --- | --- | --- |
| 0x40CFF0 to 0x544000 | the Dreamcast game code (C) as far as the anchors show, 5,126 starts | `JET\SRCGAME\GAMECLEAR.C` at 0x4C2530 |
| 0x544320 to 0x544BC0 | the game's asm helpers | `JET\OTHERS\asmfuncs.cpp` |
| 0x544E70 to 0x58DA30 | Katana framework: audio, saves, Steam, subtitles, system, video, Vorbis, fonts | `KATANA\FRAMEWORK\*.cpp` (9 files) |
| 0x594C60 to 0x596970 | Shinobi: ADX files and streams, saves, GD-ROM, pads | `KATANA\SHINOBI\*.cpp` (5 files) |
| 0x598CB0 to 0x5B9D50 | Ninja: chunk models, sprites, textures, stubs | `KATANA\NINJA\*.cpp` (7 files) |
| 0x5BA1A0 to 0x5CF340 | the C++ UI (menus, dialogs, leaderboards) | `UI\DlgBase.cpp`, RTTI |
| 0x5CF380 on | import thunks, then the C runtime | `CorExitProcess`, `FlsAlloc` lookups |

## Open questions (assign as found)

- [ ] Where does the game read `setup.dat` from, and what is its format?
- [ ] Which codec feeds `PShader_YUV` (in-house, or a linked library)?
- [ ] Are the `paddw` functions near 0x5CF000 game code or a linked library?
- [x] Is `sub_0044B320`'s `cli` path reachable? No: 0x0044B320 is the first entry of a
  switch table, decoded as code because a value in `.data` equals its address, and
  nothing calls it (M3).
- [ ] Does `SteamRemoteStorage` hold the only copy of saves (cloud), or is there a local file too?
