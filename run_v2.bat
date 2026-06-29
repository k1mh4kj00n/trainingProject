@echo off
REM physical_analysis v2 — 개발 모드 실행 (Windows)
REM v1 과 별도. setup.bat 로 .venv-win 만들어둔 상태 가정.

setlocal
cd /d "%~dp0"

if not exist .venv-win\Scripts\python.exe (
    echo [v2] .venv-win 없음. setup.bat 먼저 실행하세요.
    exit /b 1
)

set PYTHONUTF8=1
set PYTHONPATH=%CD%\scripts;%PYTHONPATH%

.venv-win\Scripts\python.exe -m v2
exit /b %errorlevel%
