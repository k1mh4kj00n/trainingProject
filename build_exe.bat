@echo off
REM physical_analysis Windows .exe 빌드 스크립트
REM
REM 전제:
REM   - Windows Python 3.10+ 설치되어 있을 것
REM   - PySide6, numpy, scipy, matplotlib, pandas, pyinstaller 가 설치되어 있을 것
REM     (없으면 다음 줄 주석 해제 후 한 번 실행)
REM     python -m pip install pyinstaller PySide6 numpy scipy matplotlib pandas openpyxl
REM
REM 실행: 이 파일이 있는 폴더에서 build_exe.bat 더블클릭 또는 cmd에서 실행
REM 산출물: dist\physical_analysis\physical_analysis.exe

setlocal
cd /d "%~dp0"

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pyinstaller 가 PATH에 없습니다.
    echo  python -m pip install pyinstaller 로 설치하세요.
    pause
    exit /b 1
)

pyinstaller build_exe.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] 빌드 실패. 로그를 확인하세요.
    pause
    exit /b 1
)

echo.
echo [OK] 빌드 완료: dist\physical_analysis\physical_analysis.exe
pause
