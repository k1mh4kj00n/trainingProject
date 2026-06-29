@echo off
REM physical_analysis - Windows single .exe build (PyInstaller)
REM Output: dist\physical_analysis.exe (single file)
REM
REM Usage:
REM   1. Run setup.bat first to create .venv-win.
REM   2. Double-click this build.bat.
REM   3. dist\physical_analysis.exe is the result. Copy that one file anywhere.

setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ============================================================
echo   physical_analysis  -  single .exe build (PyInstaller)
echo ============================================================
echo.

if not exist ".venv-win\Scripts\python.exe" (
    echo [ERROR] .venv-win not found.
    echo         Run setup.bat first.
    pause
    exit /b 1
)

REM Check / install PyInstaller
.venv-win\Scripts\python.exe -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [1/4] Installing PyInstaller ...
    .venv-win\Scripts\python.exe -m pip install --upgrade pyinstaller
    if errorlevel 1 (
        echo [ERROR] PyInstaller install failed.
        pause
        exit /b 1
    )
) else (
    echo [1/4] PyInstaller already installed
)

REM Clean previous build artifacts
echo [2/4] Cleaning old build / __pycache__ ...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "physical_analysis.spec" del /q "physical_analysis.spec"
for /d /r "scripts" %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)

REM Run PyInstaller
REM   --onefile      : single .exe (extracts to temp on first run)
REM   --windowed     : hide console window for Qt GUI
REM   --paths scripts: add scripts/ to import path
REM   --add-data     : bundle SVG icons
REM   --hidden-import: dynamic imports PyInstaller may miss
REM   --collect-data : Qt plugins, matplotlib data files
echo [3/4] Building (may take several minutes) ...
echo.
.venv-win\Scripts\python.exe -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name physical_analysis ^
    --paths "scripts" ^
    --add-data "scripts/nirs_vot_gui/assets/icons;nirs_vot_gui/assets/icons" ^
    --hidden-import scipy.optimize ^
    --hidden-import scipy.optimize._differentialevolution ^
    --hidden-import scipy.optimize._lbfgsb_py ^
    --hidden-import scipy.special ^
    --hidden-import openpyxl ^
    --hidden-import openpyxl.cell._writer ^
    --hidden-import matplotlib.backends.backend_qtagg ^
    --hidden-import nirs_vot.loader ^
    --hidden-import nirs_vot.preprocess ^
    --hidden-import nirs_vot.metrics ^
    --hidden-import nirs_vot.anchors ^
    --hidden-import hrv_analysis.loader ^
    --hidden-import hrv_analysis.time_domain ^
    --hidden-import hrv_analysis.freq_domain ^
    --hidden-import hrv_analysis.nonlinear ^
    --hidden-import hrv_analysis.detrend ^
    --hidden-import config_loader ^
    --collect-submodules nirs_vot ^
    --collect-submodules nirs_vot_gui ^
    --collect-submodules hrv_analysis ^
    --collect-data PySide6 ^
    --collect-data matplotlib ^
    --collect-submodules matplotlib ^
    --collect-submodules scipy ^
    "scripts/nirs_vot_gui/main.py"

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed.
    echo         See build\warn-physical_analysis.txt for missing modules.
    pause
    exit /b 1
)

REM Verify result
echo.
echo [4/4] Verifying build result ...
if not exist "dist\physical_analysis.exe" (
    echo [ERROR] dist\physical_analysis.exe was not created.
    pause
    exit /b 1
)

for %%f in ("dist\physical_analysis.exe") do set SIZE=%%~zf
set /a SIZE_MB=%SIZE% / 1048576

echo.
echo ============================================================
echo   Build complete
echo ============================================================
echo   Output:    dist\physical_analysis.exe
echo   Size:      about %SIZE_MB% MB
echo.
echo   Run:       double-click dist\physical_analysis.exe
echo              (single .exe extracts on first run, takes a few seconds)
echo.
echo   Distribute: copy dist\physical_analysis.exe to any Windows PC.
echo               Data folder is selected via [Open folder] in the GUI.
echo ============================================================
echo.
pause
endlocal
