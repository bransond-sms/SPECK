@echo off
setlocal enabledelayedexpansion
title SPECK Uninstaller

echo ============================================
echo   SPECK Uninstaller
echo ============================================
echo.

set "ENV_NAME=speck"
set "FOUND_CONDA="

echo [1/4] Looking for the Conda/Miniforge installation...
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

if not defined FOUND_CONDA (
    echo       No Conda/Miniforge installation found - nothing to remove there.
) else (
    echo       Found installation at !FOUND_CONDA!
    echo.
    echo [2/4] Removing the speck environment...
    call "!FOUND_CONDA!\condabin\conda.bat" env remove -n !ENV_NAME! -y
)

echo.
echo [3/4] Removing the launch shortcut...
for %%I in ("%~dp0..") do set "PARENT_DIR=%%~fI"
if exist "!PARENT_DIR!\SPECK.lnk" (
    del "!PARENT_DIR!\SPECK.lnk"
    echo       Shortcut removed.
) else (
    echo       No shortcut found next to the SPECK folder - skipping.
)

echo.
echo [4/4] Miniforge itself...
if not defined FOUND_CONDA (
    echo       Nothing to do - no Conda/Miniforge installation was found.
) else if exist "!FOUND_CONDA!\.installed_by_speck" (
    echo       This Miniforge installation was installed by the SPECK installer
    echo       and is not used by any other software you set up yourself.
    choice /C YN /M "      Remove Miniforge entirely as well"
    if !errorlevel! equ 1 (
        if exist "!FOUND_CONDA!\Uninstall-Miniforge3.exe" (
            start /wait "" "!FOUND_CONDA!\Uninstall-Miniforge3.exe" /S _?=!FOUND_CONDA!
        )
        if exist "!FOUND_CONDA!" (
            rmdir /s /q "!FOUND_CONDA!"
        )
        echo       Miniforge removed.
    ) else (
        echo       Leaving Miniforge installed.
    )
) else (
    echo       This Conda/Miniforge installation already existed on this machine
    echo       before SPECK was installed, so it is being left alone - removing it
    echo       could break other software that depends on it.
)

echo.
echo ============================================
echo   Uninstall complete.
echo   The SPECK folder itself (including any saved
echo   sessions or exports) has not been touched.
echo   Delete it manually once you've backed up
echo   anything you want to keep.
echo ============================================
echo.
pause
