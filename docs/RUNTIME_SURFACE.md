# Runtime surface: every import jetsetradio.exe binds

150 imports across 11 DLLs, from `data/pe_analysis.json`. On Windows, `native32` forwards all of them to the real DLLs, so a first boot needs no new code. On Linux, `win32hle` answers them itself; rows marked NEW are this project's work.

| DLL | Imports | win32hle today | Work for this project |
| --- | --- | --- | --- |
| d3d9.dll | 1 | Not implemented (win32hle d3d.c is DirectX 6 Direct3D, software) | NEW: IDirect3D9/IDirect3DDevice9 over the Vulkan + OpenGL renderer interface |
| d3dx9_43.dll | 3 | Not implemented | NEW: texture-from-file (PNG/DDS), texture-from-memory, and CompileShader replaced by precompiled shaders |
| XINPUT1_3.dll | 1 | Not implemented | NEW: ordinal 2 = XInputGetState on SDL2 gamepad |
| DINPUT8.dll | 1 | Not implemented | NEW: DirectInput8Create keyboard device on SDL2 keyboard |
| steam_api.dll | 13 | Not implemented | NEW: stub (offline) or forward to real Steamworks; 13 imports |
| WINMM.dll | 1 | Implemented (winmm.c) | timeGetTime only |
| KERNEL32.dll | 98 | Implemented (kernel32.c, kernel32_ext.c, kernel32_crt.c) | Check each import against win32hle; ~80% are MSVC CRT start-up calls |
| USER32.dll | 26 | Implemented (user32.c, screen.c) | One window, a message pump, cursor; SDL2 window must also own the Vulkan/GL surface |
| GDI32.dll | 1 | Implemented (gdi32.c) | CreateBrushIndirect only |
| ADVAPI32.dll | 3 | Implemented: in-memory registry (advapi32.c) | Registry writes only; persist or drop |
| ole32.dll | 2 | Implemented: COM bookkeeping + host-served class factories (ole32.c) | Register an XAudio2 class factory that CoCreateInstance can return |

## Full list

**d3d9.dll** (1): `Direct3DCreate9`

**d3dx9_43.dll** (3): `D3DXCreateTextureFromFileExA`, `D3DXCreateTextureFromFileInMemoryEx`, `D3DXCompileShader`

**XINPUT1_3.dll** (1): `#2`

**DINPUT8.dll** (1): `DirectInput8Create`

**steam_api.dll** (13): `SteamApps`, `SteamUtils`, `SteamFriends`, `SteamAPI_RegisterCallResult`, `SteamUserStats`, `SteamRemoteStorage`, `SteamAPI_UnregisterCallResult`, `SteamAPI_UnregisterCallback`, `SteamAPI_RunCallbacks`, `SteamAPI_RegisterCallback`, `SteamAPI_Shutdown`, `SteamUser`, `SteamAPI_Init`

**WINMM.dll** (1): `timeGetTime`

**KERNEL32.dll** (98): `GetLocaleInfoA`, `EnumSystemLocalesA`, `GetUserDefaultLCID`, `FlushFileBuffers`, `SetStdHandle`, `GetCurrentProcessId`, `GetTickCount`, `QueryPerformanceCounter`, `GetEnvironmentStringsW`, `FreeEnvironmentStringsW`, `GetModuleFileNameA`, `GetConsoleMode`, `GetConsoleCP`, `GetStringTypeW`, `GetLocaleInfoW`, `FreeLibrary`, `FatalAppExitA`, `LoadLibraryW`, `CloseHandle`, `GetOverlappedResult`, `ReadFile`, `GetFileSizeEx`, `CreateFileA`, `WaitForSingleObject`, `Sleep`, `CreateThread`, `InterlockedCompareExchange`, `InterlockedExchange`, `GetUserDefaultLangID`, `VirtualAlloc`, `VirtualFree`, `CreateDirectoryA`, `IsValidLocale`, `GetProcessHeap`, `FindNextFileA`, `QueryPerformanceFrequency`, `GetCurrentDirectoryA`, `ExitProcess`, `OutputDebugStringA`, `GetModuleHandleA`, `SetConsoleCtrlHandler`, `LCMapStringW`, `IsValidCodePage`, `GetOEMCP`, `GetACP`, `GetCPInfo`, `GetTimeZoneInformation`, `WideCharToMultiByte`, `HeapSize`, `MultiByteToWideChar`, `LeaveCriticalSection`, `EnterCriticalSection`, `SetFilePointer`, `DeleteCriticalSection`, `InitializeCriticalSectionAndSpinCount`, `SetHandleCount`, `HeapDestroy`, `HeapCreate`, `WriteFile`, `GetCurrentThread`, `InterlockedDecrement`, `GetCurrentThreadId`, `SetLastError`, `InterlockedIncrement`, `TlsFree`, `TlsSetValue`, `TlsGetValue`, `FindFirstFileA`, `SetEndOfFile`, `CreateFileW`, `CompareStringW`, `SetEnvironmentVariableA`, `FindClose`, `TlsAlloc`, `IsProcessorFeaturePresent`, `GetCurrentProcess`, `HeapAlloc`, `RtlUnwind`, `RaiseException`, `EncodePointer`, `DecodePointer`, `WriteConsoleW`, `GetFileType`, `GetStdHandle`, `GetModuleFileNameW`, `GetLastError`, `HeapFree`, `HeapReAlloc`, `GetProcAddress`, `GetModuleHandleW`, `GetSystemTimeAsFileTime`, `GetCommandLineA`, `HeapSetInformation`, `GetStartupInfoW`, `UnhandledExceptionFilter`, `SetUnhandledExceptionFilter`, `IsDebuggerPresent`, `TerminateProcess`

**USER32.dll** (26): `DefWindowProcA`, `MessageBoxW`, `SetCursor`, `LoadIconA`, `LoadCursorA`, `RegisterClassA`, `MessageBoxA`, `CreateWindowExA`, `ShowCursor`, `MoveWindow`, `ShowWindow`, `GetSystemMetrics`, `SetWindowLongA`, `SetWindowPos`, `AdjustWindowRect`, `GetDesktopWindow`, `RedrawWindow`, `UpdateWindow`, `SetFocus`, `PeekMessageA`, `DispatchMessageA`, `TranslateMessage`, `InvalidateRect`, `BeginPaint`, `EndPaint`, `PostQuitMessage`

**GDI32.dll** (1): `CreateBrushIndirect`

**ADVAPI32.dll** (3): `RegCreateKeyExA`, `RegSetValueExA`, `RegCloseKey`

**ole32.dll** (2): `CoCreateInstance`, `CoInitialize`

## Not imported but needed

- `steam_w.dll` is NOT used by the game: the exe never names it. The .NET launcher `jsrsetup.exe` P/Invokes its one export, `SteamUserDataPath`, to find where to write `setup.dat`. A port replaces the launcher, so the host must write `setup.dat` itself where the game looks for it (find that path in M2 with `--firsthit` / file-open tracing).
- XAudio2 2.7 has no import: it is created through `CoCreateInstance`, so it lands on ole32.

