@echo off
rem Build the Windows host (build\win32\jsr-pc.exe) with MSVC x86 and Ninja.
rem Needs Visual Studio or its Build Tools with the x86 compiler; finds them with
rem vswhere and uses their CMake and Ninja. Extra arguments go to CMake's
rem configure step, e.g.  scripts\build_win32.cmd -DJSR_TRACE=ON
setlocal
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (echo build_win32: no vswhere.exe; install Visual Studio Build Tools & exit /b 1)
set "VSROOT="
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSROOT=%%i"
if not defined VSROOT (echo build_win32: no MSVC x86 compiler found & exit /b 1)
call "%VSROOT%\VC\Auxiliary\Build\vcvars32.bat" >nul || exit /b 1
set "ROOT=%~dp0.."
cmake -S "%ROOT%" -B "%ROOT%\build\win32" -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo %* || exit /b 1
cmake --build "%ROOT%\build\win32" || exit /b 1
echo build_win32: %ROOT%\build\win32\jsr-pc.exe
