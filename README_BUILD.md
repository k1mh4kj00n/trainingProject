# physical_analysis — Windows 빌드 가이드

이 ZIP 에는 **Windows 에서 단일 `.exe` 를 빌드하기 위한 모든 파일**이 들어있습니다.

## 사전 준비

- Windows 10/11
- **Python 3.10 이상** ([python.org](https://www.python.org/downloads/) 에서 다운로드, 설치 시 *Add Python to PATH* 체크)

## 빌드 절차 (3 단계)

### 1. ZIP 풀기

원하는 폴더에 압축 해제. 예: `C:\Users\<이름>\physical_analysis\`

### 2. `setup.bat` 더블클릭 (1 회만)

- `.venv-win` (Python 가상 환경) 자동 생성
- `requirements-win.txt` 의 패키지 설치 (PySide6 / matplotlib / scipy / pandas / numpy / openpyxl)
- 수 분 소요

### 3. `build.bat` 더블클릭

- PyInstaller 자동 설치 (없으면)
- 단일 `.exe` 빌드 (수 분 소요)
- 산출물: **`dist\physical_analysis.exe`**

## 실행

`dist\physical_analysis.exe` 더블클릭. 첫 실행 시 onefile 압축 해제로 수 초 소요됩니다 (정상).

## 배포

`dist\physical_analysis.exe` **이 한 파일만** 다른 PC 로 복사하면 됩니다 (Python·venv 없이 실행 가능).

## 데이터

`.exe` 에는 측정 데이터(`참고자료/...`)가 포함되지 않습니다. 사용자가 GUI 의 `[📁 Open folder]` 또는 `[📂 Open data file]` 로 직접 선택합니다.

## 추가 스크립트

| 파일 | 역할 |
| --- | --- |
| `setup.bat` | `.venv-win` 생성 + 의존성 설치 (1회) |
| `build.bat` | PyInstaller 로 단일 `.exe` 빌드 |
| `run.bat` | venv 의 Python 으로 직접 실행 (`.exe` 빌드 없이 개발용) |
| `clean.bat` | `__pycache__` / `.pyc` 캐시 정리 (긴급용) |

## 트러블슈팅

### `setup.bat` 에서 "Python 런처 'py' 를 찾지 못함"

Python 설치 시 *Add Python to PATH* 체크 안 한 케이스. Python 재설치 또는 환경 변수 수정.

### `build.bat` 빌드 실패

`build\warn-physical_analysis.txt` 의 missing module 목록 확인. 일반적으로 `--hidden-import` 추가로 해결.

### `.exe` 실행 시 한글 깨짐

`Malgun Gothic` 또는 `Noto Sans CJK KR` 같은 한글 폰트가 시스템에 있어야. Windows 10/11 에는 기본 포함.

### `_parse_clock` ModuleNotFoundError

옛 `.pyc` 캐시 stale. `clean.bat` 실행 후 다시 `build.bat`.

## 디렉토리 구조 (ZIP 풀고 난 후)

```
physical_analysis/
├── scripts/                 # 소스 코드
│   ├── nirs_vot/            # NIRS-VOT 분석 엔진 (loader, preprocess, metrics, anchors)
│   ├── hrv_analysis/        # HRV 분석 엔진 (loader, time_domain, freq_domain, nonlinear)
│   ├── nirs_vot_gui/        # GUI (app, main, tabs/, widgets/, assets/)
│   └── config_loader.py
├── docs/templates/          # 파라미터 스냅샷 템플릿
│   ├── parameters-template.xlsx
│   ├── parameters-template.csv
│   └── parameters-template.txt
├── setup.bat                # 1회 — venv 생성
├── build.bat                # .exe 빌드
├── run.bat                  # venv 직접 실행
├── clean.bat                # 캐시 정리
├── requirements-win.txt     # pip 패키지 목록
└── README_BUILD.md          # 본 문서
```

## 주요 기능

- **NIRS-VOT 분석**: SmO2 시계열에서 12 metrics (Baseline / Min / Peak / Slope / T50 / AUC) 자동 산출, ground truth 비교
- **HRV 분석**: Kubios CSV 로드 → 자체 td/fd/nl 33 metrics, Kubios time-varying 표 lookup
- **파라미터 스냅샷**: Subject info / NIRS_VOT timepoint / Anchor / Exercise (TTE) / Lock 을 xlsx/csv/txt 로 save·load
- **HRV 파라미터**: 분석 범위·주파수 밴드 별도 패널, xlsx/csv/txt 스냅샷
- **Results export**: 단일 세션 (메타 + 12 metrics + GT 비교) + 멀티 세션 (wide format) — 모두 xlsx/csv/txt
- **TTE comparison**: HYPER/NOR/HYPO 운동 결과 한눈에 비교 + maintenance < 70% 경고
