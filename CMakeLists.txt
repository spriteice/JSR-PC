# JSR-PC: the Windows host (native32) for the lifted jetsetradio.exe.
#
# Build from an x86 MSVC environment (vcvars32), after scripts/00-02 have
# verified the game files and made the lifted C in work/gen:
#
#   scripts\build_win32.cmd
#
# The Linux host (win32hle) comes with M4a (docs/MILESTONES.md).

cmake_minimum_required(VERSION 3.20)
project(JSR-PC VERSION 0.0.1 LANGUAGES C)
set(CMAKE_C_STANDARD 17)

set(PCRECOMP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/third_party/pcrecomp" CACHE PATH
    "The pinned pcrecomp checkout (scripts/01_fetch_pcrecomp.sh)")
set(JSR_GEN_DIR "${CMAKE_CURRENT_SOURCE_DIR}/work/gen" CACHE PATH
    "The lifted C (scripts/02_lift.sh). Never committed: it is derived from the game")
option(JSR_TRACE "Build with pcrecomp's bring-up diagnostics (--calltrace, --firsthit, ...)" OFF)

if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
    message(FATAL_ERROR "The Windows host needs MSVC targeting x86 (run from vcvars32: "
                        "scripts\\build_win32.cmd). native32's bridge is MSVC x86 inline asm.")
endif()
if(NOT EXISTS "${PCRECOMP_DIR}/runtime/native32/native32.c")
    message(FATAL_ERROR "No pcrecomp at ${PCRECOMP_DIR}: run scripts/01_fetch_pcrecomp.sh")
endif()
if(NOT EXISTS "${JSR_GEN_DIR}/recomp_dispatch.c")
    message(FATAL_ERROR "No lifted C in ${JSR_GEN_DIR}: run scripts/00_verify_inputs.sh and scripts/02_lift.sh")
endif()

set(RT "${PCRECOMP_DIR}/runtime")
file(GLOB JSR_LIFTED "${JSR_GEN_DIR}/recomp_[0-9]*.c")
list(APPEND JSR_LIFTED "${JSR_GEN_DIR}/recomp_dispatch.c")

add_executable(jsr-pc
    src/host_win32/main.c
    "${RT}/native32/native32.c"      # includes eh32.c and x87crt.c
    "${RT}/recomp32/image_loader.c"
    "${RT}/recomp32/recomp_trace.c"
    "${RT}/recomp32/crash_report.c"
    ${JSR_LIFTED}
)
target_include_directories(jsr-pc PRIVATE "${RT}/recomp32" "${RT}/native32" "${JSR_GEN_DIR}")
target_compile_definitions(jsr-pc PRIVATE _CRT_SECURE_NO_WARNINGS $<$<BOOL:${JSR_TRACE}>:RECOMP_TRACE>)
target_compile_options(jsr-pc PRIVATE /bigobj /W3)
# The lifted C is correct but noisy; its warnings say nothing about our code.
set_source_files_properties(${JSR_LIFTED} PROPERTIES COMPILE_OPTIONS "/W0")

# The image is mapped at 0x00400000, so nothing of the host may be there:
# the host loads at a fixed base well above the image's span, and its first
# thread's stack is small so it fits below 0x00400000 (native32_hold_image).
# The game itself runs on a thread with a large stack (main.c).
target_link_options(jsr-pc PRIVATE /DYNAMICBASE:NO /BASE:0x20000000 /STACK:262144 /NXCOMPAT)
target_link_libraries(jsr-pc PRIVATE kernel32 user32)
