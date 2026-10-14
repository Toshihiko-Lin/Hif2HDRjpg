@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m unittest -v test_converter
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m PyInstaller --noconfirm CanonHifHdr.spec
if errorlevel 1 goto fail
.venv\Scripts\python.exe package_portable.py
if errorlevel 1 goto fail
echo Portable ZIP created in release.
pause
exit /b 0
:fail
echo Build failed. See errors above.
pause
exit /b 1
