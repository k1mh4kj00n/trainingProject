@echo off
REM physical_analysis - Windows run script
REM Uses .venv-win Python to launch the GUI.
REM Run setup.bat first if .venv-win does not exist.

setlocal
chcp 65001 >nul

REM Move to project root (relative-path data loading depends on cwd)
cd /d "%~dp0"

if not exist ".venv-win\Scripts\python.exe" (
    echo.
    echo [ERROR] .venv-win not found.
    echo         Run setup.bat first.
    echo.
    pause
    exit /b 1
)

REM Clean stale __pycache__ to avoid old .pyc imports (e.g. _parse_clock)
echo [info] Cleaning old .pyc cache ...
for /d /r "scripts" %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)

REM UTF-8 for safe Korean console / file names
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
REM Do not write .pyc files - prevents future stale cache
set PYTHONDONTWRITEBYTECODE=1

".venv-win\Scripts\python.exe" -m scripts.nirs_vot_gui.main
if errorlevel 1 (
    echo.
    echo [ERROR] An error occurred. See messages above.
    pause
)

endlocal
