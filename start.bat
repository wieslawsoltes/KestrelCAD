@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 tools\serve.py --open %*
) else (
  python tools\serve.py --open %*
)
if errorlevel 1 pause
