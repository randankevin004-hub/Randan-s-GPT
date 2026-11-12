@echo off
REM Builds a standalone Windows executable: dist\RandansGPT.exe  (run setup_and_run.bat once first)
REM If supabase.json exists next to this file it is bundled into the app (accounts enabled).
setlocal
cd /d "%~dp0"
if errorlevel 1 (
  echo Could not switch to the project folder.
  pause
  exit /b 1
)
if not exist "venv\Scripts\python.exe" (
  echo Python environment not found. Run setup_and_run.bat first.
  pause
  exit /b 1
)
call "venv\Scripts\activate.bat"
python -m pip install --upgrade pyinstaller
if errorlevel 1 goto build_failed

python -m PyInstaller --noconfirm --clean RandansGPT.spec
if errorlevel 1 goto build_failed
if not exist "dist\RandansGPT.exe" goto build_failed

echo.
echo Build succeeded: dist\RandansGPT.exe
echo Next: compile installer.iss with Inno Setup.
pause
exit /b 0

:build_failed
echo.
echo Build failed. The executable was not created. Review the error above and try again.
pause
exit /b 1
