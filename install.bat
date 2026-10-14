@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    python -m venv .venv
    if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Installation completed. Run start.bat.
pause
exit /b 0
:fail
echo Installation failed. Install Python 3.12 or newer, 64-bit, with Tcl/Tk and pip.
pause
exit /b 1
