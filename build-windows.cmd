@echo off
setlocal
cd /d "%~dp0"
py -3.13 -m venv .venv-windows
if errorlevel 1 py -3.12 -m venv .venv-windows
if errorlevel 1 goto failed
".venv-windows\Scripts\python.exe" -m pip install pyserial==3.5 pyinstaller==6.22.3
if errorlevel 1 goto failed
".venv-windows\Scripts\python.exe" build_windows.py
if errorlevel 1 goto failed
echo Build complete. See dist\windows.
pause
exit /b 0
:failed
echo Build failed. Install 64-bit Python 3.13 or 3.12 with the py launcher.
echo Review the error above and build\windows\tests.log if present.
pause
exit /b 1
