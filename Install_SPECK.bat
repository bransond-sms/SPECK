@echo off
setlocal enabledelayedexpansion
title SPECK Installer

echo ============================================
echo   SPECK Installer
echo ============================================
echo.

set "ENV_NAME=speck"
set "FOUND_CONDA="

echo [1/5] Checking for an existing Conda/Miniforge installation...
for %%P in (
    "%USERPROFILE%\miniforge3"
    "%USERPROFILE%\Miniconda3"
    "%USERPROFILE%\Anaconda3"
    "%USERPROFILE%\mambaforge"
    "C:\ProgramData\miniforge3"
    "C:\ProgramData\Miniconda3"
) do (
    if exist "%%~P\condabin\conda.bat" (
        if not defined FOUND_CONDA set "FOUND_CONDA=%%~P"
    )
)

if defined FOUND_CONDA (
    echo       Found existing installation at !FOUND_CONDA!
    set "MINIFORGE_DIR=!FOUND_CONDA!"
) else (
    echo       None found. We'll install Miniforge now - this only happens once.
    set "MINIFORGE_DIR=%USERPROFILE%\miniforge3"
    echo.
    echo [2/5] Downloading Miniforge - this may take a few minutes...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe' -OutFile '%TEMP%\miniforge_installer.exe'"

    if not exist "%TEMP%\miniforge_installer.exe" (
        echo.
        echo       ERROR: Download failed. Check your internet connection and try again.
        echo       If this keeps happening, copy this message and send it to Drake.
        pause
        exit /b 1
    )

    echo       Installing Miniforge silently to !MINIFORGE_DIR! ...
    start /wait "" "%TEMP%\miniforge_installer.exe" /S /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /D=!MINIFORGE_DIR!
    del "%TEMP%\miniforge_installer.exe"

    if not exist "!MINIFORGE_DIR!\condabin\conda.bat" (
        echo.
        echo       ERROR: Miniforge install did not complete as expected.
        echo       Copy this message and send it to Drake.
        pause
        exit /b 1
    )
    echo       Miniforge installed successfully.
    echo This file marks that the SPECK installer installed Miniforge on this machine, so Uninstall_SPECK.bat knows it is safe to remove. Do not delete this file manually. > "!MINIFORGE_DIR!\.installed_by_speck"
)

echo.
echo [3/5] Setting up the SPECK environment...
call "!MINIFORGE_DIR!\condabin\conda.bat" env list | findstr /B /C:"!ENV_NAME! " >nul
if !errorlevel! equ 0 (
    echo       Existing SPECK environment found - updating it to match the latest requirements...
    call "!MINIFORGE_DIR!\condabin\conda.bat" env update -n !ENV_NAME! -f "%~dp0environment.yml" --prune
) else (
    echo       Creating the SPECK environment for the first time - this takes a few minutes...
    call "!MINIFORGE_DIR!\condabin\conda.bat" env create -n !ENV_NAME! -f "%~dp0environment.yml"
)

if !errorlevel! neq 0 (
    echo.
    echo       ERROR: Environment setup failed. Copy the messages above and send them to Drake.
    pause
    exit /b 1
)

echo.
echo [4/5] Creating a shortcut next to the SPECK folder...
for %%I in ("%~dp0..") do set "PARENT_DIR=%%~fI"
powershell -Command ^
    "$s = (New-Object -COM WScript.Shell).CreateShortcut('!PARENT_DIR!\SPECK.lnk');" ^
    "$s.TargetPath = '%~dp0SPECK.bat';" ^
    "$s.WorkingDirectory = '%~dp0';" ^
    "$s.Save()"

echo.
echo [5/5] All done!
echo ============================================
echo   SPECK is installed. Use the "SPECK" shortcut
echo   next to the SPECK folder to launch it from now on.
echo   You will not need to run this installer again
echo   unless Drake sends you an update.
echo ============================================
echo.
pause
