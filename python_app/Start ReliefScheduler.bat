@echo off
title ReliefScheduler
cd /d "%~dp0"

:: Try to run with pythonw to hide the console window
start "" pythonw main.py

:: If pythonw isn't associated or fails immediately, we can catch it and run normal python to show the error
if %ERRORLEVEL% neq 0 (
    echo "pythonw" failed. Trying regular python so you can see any errors...
    python main.py
    pause
)
