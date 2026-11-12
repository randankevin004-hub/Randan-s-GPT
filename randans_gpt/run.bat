@echo off
REM Quick start after setup_and_run.bat has been run once.
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  call setup_and_run.bat
  exit /b
)
call "venv\Scripts\activate.bat"
python main.py
if errorlevel 1 pause
