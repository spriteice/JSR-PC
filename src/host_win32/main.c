/*
 * JSR-PC Windows host: runs the lifted jetsetradio.exe on pcrecomp's native32.
 *
 * native32 maps the original exe at its own base, forwards every import, COM
 * call and callback to real Windows, and runs the lifted C in place of the
 * exe's machine code (third_party/pcrecomp/runtime/native32/native32.h has
 * the model). This file is the rest of what a native32 host provides: main(),
 * the game's location, the few imports that must answer for the guest rather
 * than for this host, and recomp_lookup_manual() for hand-written overrides
 * (none yet).
 *
 *   jsr-pc.exe [--game DIR] [recomp trace options]
 *
 * DIR is the folder holding jetsetradio.exe and its DATA\ and CUSTOM\
 * folders; by default, the folder this host is in. The game runs with DIR as
 * its current directory, as Steam starts it. --help lists the trace options
 * (runtime/recomp32/recomp_trace.h); they need a -DJSR_TRACE=ON build.
 */
#define WIN32_LEAN_AND_MEAN
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "native32.h"
#include "recomp_trace.h"
#include "crash_report.h"

/* jetsetradio.exe, the 2013 Steam build in data/inputs.sha256. */
#define JSR_EXE_NAME   "jetsetradio.exe"
#define JSR_IMAGE_BASE 0x00400000u   /* its preferred base (data/pe_analysis.json) */
#define JSR_ENTRY_VA   0x005D7D92u   /* its entry point: the MSVC CRT start-up */

/* The game's main RAM, as on the Dreamcast it came from: sub_00578EF0
 * allocates exactly this range, and sub_00597A30 maps 0x8C000000-based
 * addresses into it. If something else is there, the allocation fails, the
 * game carries on, and its overlapped reads into the range fail where it never
 * looks: the first boots waited on the Loading screen for one of them, with
 * the host itself linked at 0x20000000. So the host is linked elsewhere
 * (CMakeLists.txt) and holds the range while it starts, so no DLL lands there,
 * then hands it back as the game starts. */
#define JSR_DCRAM_BASE 0x20000000u
#define JSR_DCRAM_SIZE (16u << 20)
static void* g_dcram_hold;

/* The lifted code runs on a thread of its own with this much stack reserved.
 * A lifted frame is several times the original's, and the host itself is
 * linked with a small /STACK so its first thread's stack stays below the
 * image (native32_hold_image). */
#define GUEST_THREAD_STACK (64u << 20)

/* Exit codes of the host itself, before the game runs. */
#define EXIT_USAGE    2
#define EXIT_NO_GAME  3
#define EXIT_NO_MAP   4
#define EXIT_UNBOUND  5
#define EXIT_THREAD   6

static char    g_game_dir[MAX_PATH];
static char    g_game_exe[MAX_PATH];
static wchar_t g_game_exe_w[MAX_PATH];

/* No hand-written overrides yet: every guest function runs as lifted. */
recomp_func_t recomp_lookup_manual(uint32_t va) {
    (void)va;
    return NULL;
}

/* ------------------------------------------------------------------ shims
 *
 * To Windows, the main module of this process is the host, so asked for "the
 * module that started the process" it answers with the host's handle and path.
 * The guest asks the same question and means jetsetradio.exe: the CRT start-up
 * passes GetModuleHandle(NULL) to WinMain as its hInstance, and a path taken
 * from GetModuleFileName(NULL) points at the game's folder. These answer for
 * the guest: NULL, or the guest's own handle or name, is the mapped exe, and
 * anything else goes to Windows as before.
 *
 * Each runs inside the lifted model (native32.h): its stdcall arguments are
 * at g_esp + 4, and it pops them and the return address itself. */

#define STDCALL_ARG(i) (((const uint32_t*)(uintptr_t)(g_esp + 4))[i])
#define STDCALL_RETURN(nargs) (g_esp += 4 + 4 * (nargs))

static uint32_t guest_module(const char* name) {
    return name ? native32_module(name) : JSR_IMAGE_BASE;
}

static void shim_GetModuleHandleA(void) {
    const char* name = (const char*)(uintptr_t)STDCALL_ARG(0);
    uint32_t m = guest_module(name);
    g_eax = m ? m : (uint32_t)(uintptr_t)GetModuleHandleA(name);
    STDCALL_RETURN(1);
}

static void shim_GetModuleHandleW(void) {
    const wchar_t* name = (const wchar_t*)(uintptr_t)STDCALL_ARG(0);
    char narrow[MAX_PATH];
    uint32_t m = 0;
    if (!name) m = JSR_IMAGE_BASE;
    else if (WideCharToMultiByte(CP_ACP, 0, name, -1, narrow, sizeof narrow, NULL, NULL))
        m = guest_module(narrow);
    g_eax = m ? m : (uint32_t)(uintptr_t)GetModuleHandleW(name);
    STDCALL_RETURN(1);
}

/* Windows' rules for a short buffer: as much as fits, always terminated, the
 * size returned, and ERROR_INSUFFICIENT_BUFFER. */
static void shim_GetModuleFileNameA(void) {
    uint32_t h = STDCALL_ARG(0), size = STDCALL_ARG(2);
    char* buf = (char*)(uintptr_t)STDCALL_ARG(1);
    if (h && h != JSR_IMAGE_BASE) {
        g_eax = GetModuleFileNameA((HMODULE)(uintptr_t)h, buf, size);
    } else if (size) {
        uint32_t len = (uint32_t)strlen(g_game_exe);
        uint32_t n = len < size ? len : size - 1;
        memcpy(buf, g_game_exe, n);
        buf[n] = 0;
        g_eax = len < size ? len : size;
        SetLastError(len < size ? ERROR_SUCCESS : ERROR_INSUFFICIENT_BUFFER);
    } else {
        g_eax = 0;
        SetLastError(ERROR_INSUFFICIENT_BUFFER);
    }
    STDCALL_RETURN(3);
}

static void shim_GetModuleFileNameW(void) {
    uint32_t h = STDCALL_ARG(0), size = STDCALL_ARG(2);
    wchar_t* buf = (wchar_t*)(uintptr_t)STDCALL_ARG(1);
    if (h && h != JSR_IMAGE_BASE) {
        g_eax = GetModuleFileNameW((HMODULE)(uintptr_t)h, buf, size);
    } else if (size) {
        uint32_t len = (uint32_t)wcslen(g_game_exe_w);
        uint32_t n = len < size ? len : size - 1;
        memcpy(buf, g_game_exe_w, n * sizeof *buf);
        buf[n] = 0;
        g_eax = len < size ? len : size;
        SetLastError(len < size ? ERROR_SUCCESS : ERROR_INSUFFICIENT_BUFFER);
    } else {
        g_eax = 0;
        SetLastError(ERROR_INSUFFICIENT_BUFFER);
    }
    STDCALL_RETURN(3);
}

/* DirectInput8Create takes the caller's hInstance, which the guest gets from
 * GetModuleHandle(NULL) above. The mapped exe is not a module Windows loaded,
 * so DirectInput refuses that handle, and the game never checks the result:
 * on the first boot it read the interface pointer it was never given and
 * crashed in sub_00591590. The host's own handle stands in. DirectInput uses
 * it only to identify the caller. */
typedef HRESULT (WINAPI *dinput8_create_t)(HINSTANCE, DWORD, const void*, void**, void*);

static void shim_DirectInput8Create(void) {
    static dinput8_create_t real;
    HINSTANCE inst = (HINSTANCE)(uintptr_t)STDCALL_ARG(0);
    HRESULT hr;
    if (!real) {
        HMODULE dll = LoadLibraryA("dinput8.dll");
        if (dll) real = (dinput8_create_t)(void*)GetProcAddress(dll, "DirectInput8Create");
    }
    if ((uintptr_t)inst == JSR_IMAGE_BASE) inst = GetModuleHandleW(NULL);
    hr = real ? real(inst, STDCALL_ARG(1), (const void*)(uintptr_t)STDCALL_ARG(2),
                     (void**)(uintptr_t)STDCALL_ARG(3), (void*)(uintptr_t)STDCALL_ARG(4))
              : E_FAIL;
    if (FAILED(hr)) fprintf(stderr, "jsr-pc: DirectInput8Create failed (0x%08lX)\n", (unsigned long)hr);
    g_eax = (uint32_t)hr;
    STDCALL_RETURN(5);
}

static native32_shim_t g_shims[] = {
    { "GetModuleHandleA", shim_GetModuleHandleA },
    { "GetModuleHandleW", shim_GetModuleHandleW },
    { "GetModuleFileNameA", shim_GetModuleFileNameA },
    { "GetModuleFileNameW", shim_GetModuleFileNameW },
    { "DirectInput8Create", shim_DirectInput8Create },
};

/* ------------------------------------------------------------------- main */

static void usage(void) {
    fprintf(stderr,
            "usage: jsr-pc [--game DIR] [trace options]\n"
            "  --game DIR   the folder with " JSR_EXE_NAME " (default: this program's folder)\n");
    recomp_trace_help();
}

/* g_game_dir and g_game_exe from --game, or from where this host is. */
static int find_game(const char* arg) {
    char dir[MAX_PATH];
    if (arg) {
        if (!GetFullPathNameA(arg, sizeof dir, dir, NULL)) return 0;
    } else {
        DWORD n = GetModuleFileNameA(NULL, dir, sizeof dir);
        if (!n || n == sizeof dir) return 0;
        char* slash = strrchr(dir, '\\');
        if (slash) *slash = 0;
    }
    size_t len = strlen(dir);
    while (len && (dir[len - 1] == '\\' || dir[len - 1] == '/')) dir[--len] = 0;
    if (_snprintf(g_game_dir, sizeof g_game_dir, "%s", dir) < 0 ||
        _snprintf(g_game_exe, sizeof g_game_exe, "%s\\%s", dir, JSR_EXE_NAME) < 0)
        return 0;
    g_game_dir[sizeof g_game_dir - 1] = g_game_exe[sizeof g_game_exe - 1] = 0;
    if (!MultiByteToWideChar(CP_ACP, 0, g_game_exe, -1, g_game_exe_w, MAX_PATH)) return 0;
    return GetFileAttributesA(g_game_exe) != INVALID_FILE_ATTRIBUTES;
}

static DWORD WINAPI run_guest(void* unused) {
    (void)unused;
    if (g_dcram_hold) VirtualFree(g_dcram_hold, 0, MEM_RELEASE);   /* the game's now */
    native32_call_guest(JSR_ENTRY_VA, 0, NULL);   /* the CRT start-up ends in ExitProcess */
    return 0;
}

int main(int argc, char** argv) {
    const char* game = NULL;
    for (int i = 1; i < argc; i++) {
        int n = recomp_trace_arg(argc, argv, i);
        if (n) { i += n - 1; continue; }
        if (!strcmp(argv[i], "--game") && i + 1 < argc) { game = argv[++i]; continue; }
        if (!strcmp(argv[i], "--help")) { usage(); return 0; }
        fprintf(stderr, "jsr-pc: unknown option %s\n", argv[i]);
        usage();
        return EXIT_USAGE;
    }
    if (!find_game(game)) {
        fprintf(stderr, "jsr-pc: no %s in %s (pass --game DIR)\n", JSR_EXE_NAME,
                g_game_dir[0] ? g_game_dir : "this program's folder");
        return EXIT_NO_GAME;
    }

    /* Starts this host again with the image's range reserved, and waits for
     * it: from here on only the child runs. */
    if (!native32_hold_image(g_game_exe, JSR_IMAGE_BASE))
        fprintf(stderr, "jsr-pc: could not reserve 0x%08X before start-up; mapping anyway\n",
                JSR_IMAGE_BASE);

    g_dcram_hold = VirtualAlloc((void*)(uintptr_t)JSR_DCRAM_BASE, JSR_DCRAM_SIZE, MEM_RESERVE,
                                PAGE_NOACCESS);
    if (!g_dcram_hold)
        fprintf(stderr, "jsr-pc: 0x%08X is taken (error %lu); the game's RAM will not map there\n",
                JSR_DCRAM_BASE, GetLastError());

    SetCurrentDirectoryA(g_game_dir);
    recomp_install_crash_handler();   /* before native32_init: its handler must run first */
    native32_init();
    if (!native32_map(g_game_exe, JSR_IMAGE_BASE)) {
        fprintf(stderr, "jsr-pc: cannot map %s at 0x%08X\n", g_game_exe, JSR_IMAGE_BASE);
        return EXIT_NO_MAP;
    }
    int unbound = native32_bind(JSR_IMAGE_BASE, g_shims, (int)(sizeof g_shims / sizeof g_shims[0]));
    if (unbound) {
        /* Each one would fault the first time the game calls it, wherever
         * that is. The [bind] lines above name them. */
        fprintf(stderr, "jsr-pc: %d import(s) unresolved; stopping\n", unbound);
        return EXIT_UNBOUND;
    }

    HANDLE t = CreateThread(NULL, GUEST_THREAD_STACK, run_guest, NULL,
                            STACK_SIZE_PARAM_IS_A_RESERVATION, NULL);
    if (!t) {
        fprintf(stderr, "jsr-pc: cannot start the game thread (error %lu)\n", GetLastError());
        return EXIT_THREAD;
    }
    WaitForSingleObject(t, INFINITE);
    DWORD code = 0;
    GetExitCodeThread(t, &code);
    return (int)code;
}
