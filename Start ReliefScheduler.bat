@echo off
title ReliefScheduler
cd /d "%~dp0"
if exist "python_app" cd python_app

:: Determine best Python executable
set "PYTHON_CMD="

:: Check Python 3.13 (known working install with PySide6)
if exist "C:\Python313\python.exe" (
    set "PYTHON_CMD=C:\Python313\python.exe"
    goto :run_app
)

:: Check py launcher with 3.13
py -3.13 -c "import sys" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=py -3.13"
    goto :run_app
)

:: Check py launcher default
py -c "import sys" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=py"
    goto :run_app
)

:: Check python in PATH
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python"
    goto :run_app
)

:not_found
echo.
echo ========================================================
echo  [ERROR] Python was not found on your system.
echo  Please install Python (3.10+) and ensure it is in PATH.
echo ========================================================
echo.
pause
exit /b 1

:run_app
echo Starting ReliefScheduler...
%PYTHON_CMD% main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo ========================================================
    echo  ReliefScheduler exited with code %ERRORLEVEL%.
    echo ========================================================
    echo.
    pause
)
