@echo off
REM physical_analysis - Windows initial setup (run once)
REM Creates .venv-win and installs packages from requirements-win.txt

setlocal
chcp 65001 >nul

REM Move to script folder
cd /d "%~dp0"

echo.
echo ============================================================
echo  physical_analysis  -  Windows initial setup
echo ============================================================
echo.

REM Check Python launcher
where py >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python launcher 'py' not found.
    echo         Install from https://www.python.org/downloads/windows/
    echo         IMPORTANT: check 'Add Python to PATH' during install.
    goto :end
)

REM Check Python version
echo [1/3] Checking Python version...
py -3 --version
if errorlevel 1 (
    echo [ERROR] Python 3 not installed.
    goto :end
)

REM Create venv (skip if exists)
if exist ".venv-win\Scripts\python.exe" (
    echo [2/3] .venv-win already exists - reusing
) else (
    echo [2/3] Creating .venv-win ...
    py -3 -m venv .venv-win
    if errorlevel 1 (
        echo [ERROR] venv creation failed.
        goto :end
    )
)

REM Install packages
echo [3/3] Installing packages (may take a few minutes) ...
call .venv-win\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-win.txt
if errorlevel 1 (
    echo [ERROR] Package install failed.
    goto :end
)

echo.
echo ============================================================
echo  Setup complete. Now double-click run.bat or build.bat.
echo ============================================================
echo.

:end
endlocal
pause
