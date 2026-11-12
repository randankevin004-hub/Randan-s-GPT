@echo off
REM Builds a standalone Windows executable: dist\RandansGPT.exe  (run setup_and_run.bat once first)
REM If supabase.json exists next to this file it is bundled into the app (accounts enabled).
cd /d "%~dp0"
call "venv\Scripts\activate.bat"
python -m pip install pyinstaller
set EXTRA=
if exist "supabase.json" set EXTRA=--add-data "supabase.json;."
pyinstaller --noconfirm --clean --noconsole --onefile --name RandansGPT ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --add-data "web;web" %EXTRA% ^
  --collect-all webview ^
  --collect-all customtkinter ^
  --collect-all keyring ^
  --copy-metadata keyring ^
  --hidden-import keyring.backends.Windows ^
  --collect-submodules pygments.lexers ^
  --collect-submodules mcp ^
  main.py
echo.
echo Done. Your app is at dist\RandansGPT.exe  (next: build the installer with installer.iss)
pause
