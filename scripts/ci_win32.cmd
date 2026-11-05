@echo off
rem CI's Windows job: compile the host and pcrecomp's native32 runtime with MSVC
rem x86, with and without the bring-up diagnostics (JSR_TRACE), without linking.
rem It needs none of the game's files, so the lifted C is not compiled: that
rem takes the full build, scripts\build_win32.cmd. Run it after
rem scripts/01_fetch_pcrecomp.sh. The files and flags follow CMakeLists.txt;
rem keep them in step with it. Objects go to build\ci, which is not tracked.
rem Needs Visual Studio or its Build Tools with the x86 compiler; finds them
rem with vswhere, as build_win32.cmd does.
setlocal
set "VSINSTALLER=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
set "VSWHERE=%VSINSTALLER%\vswhere.exe"
if not exist "%VSWHERE%" (echo ci_win32: no vswhere.exe; install Visual Studio Build Tools & exit /b 1)
set "VSROOT="
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSROOT=%%i"
if not defined VSROOT (echo ci_win32: no Visual Studio with the MSVC x86 compiler & exit /b 1)
set "PATH=%VSINSTALLER%;%PATH%"
call "%VSROOT%\VC\Auxiliary\Build\vcvars32.bat" >nul || exit /b 1
set "ROOT=%~dp0.."
set "RT=%ROOT%\third_party\pcrecomp\runtime"
if not exist "%RT%\native32\native32.c" (echo ci_win32: no pcrecomp; run scripts/01_fetch_pcrecomp.sh & exit /b 1)
set "SRCS="%ROOT%\src\host_win32\main.c" "%RT%\native32\native32.c" "%RT%\recomp32\image_loader.c" "%RT%\recomp32\recomp_trace.c" "%RT%\recomp32\crash_report.c""
set "FLAGS=/nologo /c /std:c17 /W3 /bigobj /D_CRT_SECURE_NO_WARNINGS /I"%RT%\recomp32" /I"%RT%\native32""
if not exist "%ROOT%\build\ci\plain" mkdir "%ROOT%\build\ci\plain"
if not exist "%ROOT%\build\ci\trace" mkdir "%ROOT%\build\ci\trace"
echo ci_win32: [1/2] without JSR_TRACE
cl %FLAGS% /Fo"%ROOT%\build\ci\plain\\" %SRCS% || exit /b 1
echo ci_win32: [2/2] with JSR_TRACE (RECOMP_TRACE)
cl %FLAGS% /DRECOMP_TRACE /Fo"%ROOT%\build\ci\trace\\" %SRCS% || exit /b 1
echo ci_win32: all compiled
