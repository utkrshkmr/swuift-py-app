@echo off
REM ==========================================================================
REM build_windows.bat  --  Build SWUIFT.exe for Windows (x86_64 or ARM64)
REM
REM Usage (run from the project root):
REM   build_windows.bat
REM
REM Prerequisites:
REM   - Python 3.10+ installed and on PATH (or specify PYTHON_EXE below)
REM   - A virtualenv at .venv (create with:
REM       python -m venv .venv
REM       .venv\Scripts\pip install -r requirements_app.txt)
REM   - Optional: InnoSetup 6 installed for creating an installer
REM
REM PyInstaller detects the host architecture automatically.
REM Run this script on an x86_64 Windows machine for an x86_64 build,
REM or on a Windows ARM64 machine for an ARM64 build.
REM ==========================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /D "%SCRIPT_DIR%"

set "VENV=.venv\Scripts"
set "PYINSTALLER=%VENV%\pyinstaller.exe"
set "PYTHON=%VENV%\python.exe"
set "SPEC=swuift_app.spec"

echo ========================================
echo  SWUIFT Windows build
echo ========================================

REM -- Generate SWUIFT.ico if not present -----------------------------------
if not exist "SWUIFT.ico" (
    echo Generating SWUIFT.ico from SWUIFT.icns ...
    "%PYTHON%" -c "from PIL import Image; img = Image.open('SWUIFT.icns'); img.save('SWUIFT.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
    if errorlevel 1 (
        echo WARNING: Could not generate SWUIFT.ico. SWUIFT.icns may not be present.
    ) else (
        echo   SWUIFT.ico created.
    )
)

REM -- Run PyInstaller -------------------------------------------------------
echo.
echo Running PyInstaller ...
"%PYINSTALLER%" "%SPEC%" --noconfirm --clean
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo.
echo Build complete: dist\SWUIFT\SWUIFT.exe

REM -- Optional: InnoSetup installer ----------------------------------------
if exist "swuift_setup.iss" (
    echo.
    echo Creating Windows installer with InnoSetup ...
    set "INNO_COMPILER=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    if not exist "!INNO_COMPILER!" (
        set "INNO_COMPILER=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    )
    if exist "!INNO_COMPILER!" (
        "!INNO_COMPILER!" swuift_setup.iss
        if errorlevel 1 (
            echo WARNING: InnoSetup build failed.
        ) else (
            echo InnoSetup installer created in dist\
        )
    ) else (
        echo NOTE: InnoSetup not found, skipping installer creation.
        echo       Install InnoSetup 6 from https://jrsoftware.org/isdl.php
    )
)

echo.
echo ========================================
echo  Build finished.
echo ========================================
endlocal
