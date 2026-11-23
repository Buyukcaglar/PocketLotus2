@echo off
rem PocketLotus2 builder for Windows.
rem Installs MSYS2 (through winget) and the compilers the build needs, then runs
rem build_core.py with the same arguments. Without arguments it uses the game
rem files in the "Lotus" folder next to this file.
setlocal
set "MSYS=C:\msys64"

if not exist "%MSYS%\usr\bin\bash.exe" (
    where winget >nul 2>nul || (
        echo MSYS2 is needed. Install it from https://www.msys2.org/ into C:\msys64 and run this again.
        goto :fail
    )
    echo Installing MSYS2 ...
    winget install -e --id MSYS2.MSYS2 --accept-source-agreements --accept-package-agreements || goto :fail
)
if not exist "%MSYS%\usr\bin\bash.exe" (
    echo MSYS2 was not found in %MSYS%.
    goto :fail
)

echo Installing the compilers (only the first time) ...
"%MSYS%\usr\bin\bash.exe" -lc "pacman -S --needed --noconfirm make mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-riscv64-unknown-elf-gcc mingw-w64-ucrt-x86_64-riscv64-unknown-elf-binutils mingw-w64-ucrt-x86_64-riscv64-unknown-elf-newlib" || goto :fail

set "PATH=%MSYS%\ucrt64\bin;%MSYS%\usr\bin;%PATH%"
"%MSYS%\ucrt64\bin\python.exe" "%~dp0build_core.py" %*
if errorlevel 1 goto :fail
if "%~1"=="" pause
exit /b 0

:fail
if "%~1"=="" pause
exit /b 1
