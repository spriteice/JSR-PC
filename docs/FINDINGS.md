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
  EH support.
- Not yet checked: run-time code generation or self-patching. Watch for writes to `.text`
  and calls into heap memory during M2.

## Open questions (assign as found)

- [ ] Where does the game read `setup.dat` from, and what is its format?
- [ ] Which codec feeds `PShader_YUV` (in-house, or a linked library)?
- [ ] Are the `paddw` functions near 0x5CF000 game code or a linked library?
- [ ] Is `sub_0044B320`'s `cli` path reachable?
- [ ] Does `SteamRemoteStorage` hold the only copy of saves (cloud), or is there a local file too?
