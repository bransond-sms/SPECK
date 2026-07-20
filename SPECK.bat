@echo off
setlocal enabledelayedexpansion
title SPECK

set "ENV_NAME=speck"
set "FOUND_CONDA="

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
    echo Could not find a Conda/Miniforge installation.
    echo Please run Install_SPECK.bat first.
    pause
    exit /b 1
)

call "!FOUND_CONDA!\condabin\conda.bat" activate !ENV_NAME!
cd /d "%~dp0"
python main.py

if !errorlevel! neq 0 (
    echo.
    echo SPECK exited with an error. Copy the messages above and send them to Drake.
    pause
)
