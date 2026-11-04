@echo off
rem Build the Windows host (build\win32\jsr-pc.exe) with MSVC x86 and Ninja.
rem Needs Visual Studio or its Build Tools with the x86 compiler and the C++ CMake
rem tools; finds them with vswhere. Extra arguments go to CMake's configure step,
rem e.g.  scripts\build_win32.cmd -DJSR_TRACE=ON
rem Visual Studio's CMake and Ninja are put first on PATH: vcvars appends them, so
rem another cmake earlier on PATH (MSYS2's, for one) would win and mangle the paths.
rem No path is echoed inside a ( ) block: "Program Files (x86)" would end the block.
setlocal
set "VSINSTALLER=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
set "VSWHERE=%VSINSTALLER%\vswhere.exe"
if not exist "%VSWHERE%" (echo build_win32: no vswhere.exe; install Visual Studio Build Tools & exit /b 1)
set "VSROOT="
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 Microsoft.VisualStudio.Component.VC.CMake.Project -property installationPath`) do set "VSROOT=%%i"
if not defined VSROOT (echo build_win32: no Visual Studio with the MSVC x86 compiler and the C++ CMake tools & exit /b 1)
rem vcvars runs vswhere by name
set "PATH=%VSINSTALLER%;%PATH%"
call "%VSROOT%\VC\Auxiliary\Build\vcvars32.bat" >nul || exit /b 1
set "VSCMAKE=%VSROOT%\Common7\IDE\CommonExtensions\Microsoft\CMake"
if not exist "%VSCMAKE%\CMake\bin\cmake.exe" (echo build_win32: Visual Studio's cmake.exe is missing & exit /b 1)
if not exist "%VSCMAKE%\Ninja\ninja.exe" (echo build_win32: Visual Studio's ninja.exe is missing & exit /b 1)
set "PATH=%VSCMAKE%\CMake\bin;%VSCMAKE%\Ninja;%PATH%"
set "ROOT=%~dp0.."
cmake -S "%ROOT%" -B "%ROOT%\build\win32" -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo %* || exit /b 1
cmake --build "%ROOT%\build\win32" || exit /b 1
echo build_win32: %ROOT%\build\win32\jsr-pc.exe
