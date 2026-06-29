@echo off
REM physical_analysis - emergency cache cleanup
REM run.bat already does this automatically; use this to force clean.

setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === Cleaning Python __pycache__ ===
for /d /r "scripts" %%d in (__pycache__) do (
    if exist "%%d" (
        echo   Remove: %%d
        rmdir /s /q "%%d"
    )
)

echo.
echo === Cleaning .pyc files ===
del /s /q "scripts\*.pyc" 2>nul

echo.
echo Done. Now run run.bat again.
echo.
pause
endlocal
