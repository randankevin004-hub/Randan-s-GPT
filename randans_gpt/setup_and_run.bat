@echo off
REM Double-click me: installs everything the first time, then starts Randan's GPT.
REM It always works from the folder this file is in, so it can't "lose" requirements.txt.
cd /d "%~dp0"
title Randan's GPT - setup

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 - 3.12 from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during setup, then double-click this file again.
  pause
  exit /b 1
)
if not exist "requirements.txt" (
  echo Can't find requirements.txt next to this file. Make sure you EXTRACTED the whole zip
  echo ^(right-click the zip -^> Extract All^) and run this from inside the randans_gpt folder.
  pause
  exit /b 1
)
if not exist "venv\Scripts\python.exe" (
  echo Creating a private Python environment...
  python -m venv venv
)
call "venv\Scripts\activate.bat"
echo Installing / updating packages (first run takes a minute)...
python -m pip install --upgrade pip >nul
python -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
  echo.
  echo Package installation failed - see the message above.
  pause
  exit /b 1
)
echo.
echo Starting Randan's GPT...
python main.py
if errorlevel 1 pause
