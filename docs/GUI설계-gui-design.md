# physical_analysis GUI 설계 메모

## 목표

Kubios HRV Scientific의 UI/UX 규약을 그대로 승계하면서, 첫 분석 모듈로 **NIRS-VOT(SmO2)** 분석을 전면에 배치한 데스크톱 GUI. 추후 HRV·FMD 모듈을 같은 레이아웃 위에 탭으로 얹는다.

## 프레임워크

- **PySide6 6.11** (Qt 6, LGPL → 상업용도 가능)
- **matplotlib 3.10** (기존 분석 파이프라인과의 일관성)
- **pyqtgraph 0.14** (성능 필요한 인터랙티브 그래프 대비)

## 윈도우 레이아웃 (모든 탭 공통)

```
┌──────────────────────────────────────────────────────────────┐
│  MenuBar: File | Edit | View | Tools | Help                  │
├──────────────────────────────────────────────────────────────┤
│  ToolBar: [Open][Save][Print][Report][Prefs] ... [Zoom±][?]  │
├──────────┬─────────────────────────────────────┬─────────────┤
│          │  QTabWidget                         │             │
│  Data    │  ┌─Overview ─ NIRS-VOT ─ Time ─...│ Parameters  │
│  Browser │  │                                 │ & Results   │
│  (Tree)  │  │    메인 그래프 영역              │ (12지표)    │
│  15%     │  │                                 │ 20%         │
│          │  │                                 │             │
│          │  │  ──────────────────────────── │             │
│          │  │  TimeRangeSlider  [Fit][-][+]  │             │
│          │  └─────────────────────────────────┘             │
├──────────┴─────────────────────────────────────┴─────────────┤
│  StatusBar: 현재 파일 · 세션 · 분석 상태                      │
└──────────────────────────────────────────────────────────────┘
```

- 좌/우 패널은 **QDockWidget** 으로 구성 → 드래그 이동, 숨김 가능
- 중앙은 **QTabWidget** (상단 가로 탭)

## 탭 구성 (v0.1)

| # | 탭 이름 | 상태 | 설명 |
|---|---|---|---|
| 1 | **NIRS-VOT** | ✅ 완성 | 현재 분석 엔진 연결. 조건/세션 선택 → 12지표 + 그래프 |
| 2 | Overview | 🔜 placeholder | 추후 세션 요약 대시보드 자리 |
| 3 | Time-domain | 🔜 placeholder | HRV 추가 시 활성 |
| 4 | Frequency-domain | 🔜 placeholder | HRV 추가 시 활성 |
| 5 | Nonlinear | 🔜 placeholder | HRV 추가 시 활성 |
| 6 | Time-varying | 🔜 placeholder | HRV 추가 시 활성 |

Placeholder 탭은 중앙에 "Coming in next iteration" 텍스트 + 진행 로드맵 일러두기.

## Data Browser (좌측)

QTreeView 기반. 모델은 `QStandardItemModel`.

```
📁 이찬민 (Subject)
├─ 🫁 NOR (Normoxia)
│  ├─ 📍 Baseline     (13:02:00 → 13:11:00)
│  └─ 📍 Recovery2    (14:04:40 → 14:13:40)
├─ 🫁 HYPO (Hypoxia)
│  ├─ 📍 Baseline     (12:14:30 → 12:23:30)
│  └─ 📍 Recovery2    (13:12:00 → 13:21:00)
└─ 🫁 HYPER (Hyperoxia)
   ├─ 📍 Baseline     (14:00:00 → 14:09:00)
   └─ 📍 Recovery2    (15:06:00 → 15:15:00)
```

세션 노드를 더블클릭 → NIRS-VOT 탭에 해당 세션 로드·분석·렌더.

## Parameter Table (우측)

`QTableWidget`, 2열(Item/Value), 교대 행 색상. 12개 지표 + 세션 메타(anchors, 파일 이름).

하단 버튼:
- 🔽 **Export CSV** (현재 세션)
- 📄 **Export PDF Report** (v0.2 예정 - 현재는 grey out)

## 메뉴바 항목 (Kubios 원문 유지)

| 메뉴 | 하위 |
|---|---|
| **File** | Open data file... / Save results / Export CSV / Export PDF Report / Quit |
| **Edit** | Preferences... |
| **View** | Toggle Data Browser / Toggle Parameter Table / Markers |
| **Tools** | Run batch on all sessions / About data |
| **Help** | User Guide / About |

v0.1에서는 File → Open data file, Export CSV, Quit / Help → About 만 동작. 나머지는 비활성.

## 색상 팔레트 (constants)

```python
# 배경
WINDOW_BG       = "#FFFFFF"
PANEL_BG        = "#F4F4F4"
TABLE_ALT_BG    = "#E8F4FF"

# 데이터 라인
SMO2_SMOOTH     = "#000000"     # 검정 (Smoothed)
SMO2_RAW        = "#9E9E9E"     # 회색 (Raw)
BASELINE_LINE   = "#424242"     # 진한 회색 점선

# Occlusion/Reperfusion 영역
OXY_DEFICIT     = "#D32F2F"     # 빨강 ribbon (alpha 0.3)
HYPEREMIA_AUC   = "#2E7D32"     # 초록 ribbon (alpha 0.3)

# 마커
MIN_MARKER      = "#1F77B4"     # 파랑
PEAK_MARKER     = "#D32F2F"     # 빨강

# 강조
ACCENT          = "#2E7DCA"     # 탭 활성, 버튼
WARNING         = "#FFA000"
```

## 파일 구조

```
scripts/nirs_vot_gui/
├── __init__.py
├── main.py               # 엔트리
├── app.py                # MainWindow
├── style.py              # 색상/폰트 상수 + QSS
├── widgets/
│   ├── __init__.py
│   ├── data_browser.py   # QTreeView + 모델
│   ├── parameter_table.py
│   └── mpl_canvas.py     # matplotlib FigureCanvasQTAgg 래퍼
└── tabs/
    ├── __init__.py
    ├── nirs_vot_tab.py   # ★ 메인 탭
    └── placeholder.py    # "Coming Soon" 탭
```

분석 엔진은 기존 `scripts/nirs_vot/` 를 그대로 재사용 (Kubios 철학 — UI와 분석 엔진 분리).

## 실행

```bash
# WSL (WSLg)
.venv/bin/python -m scripts.nirs_vot_gui.main

# Windows
python -m scripts.nirs_vot_gui.main
```

## 단계별 로드맵

| 단계 | 내용 |
|---|---|
| **v0.1 (이번 반복)** | Main window 레이아웃 + Data Browser + NIRS-VOT 탭 + Parameter Table + CSV Export |
| v0.2 | PDF 리포트 생성 (reportlab), 아티팩트 플래그 마커, TimeRangeSlider 상호작용 |
| v0.3 | Preferences 다이얼로그 (baseline 윈도우, 스무딩 초, 슬로프 윈도우 사용자화) |
| v0.4 | HRV 모듈 추가 (Kubios 프로그램 폴더 CSV 인식) → Time-domain/Frequency/Nonlinear 탭 활성 |
| v0.5 | FMD 동시 측정 연동 (논문 핵심 가치) |

## Kubios에서 의도적으로 빼는 것 (MVP)

- Kubios Cloud 동기화, 계정 매니저
- ANS 기능 테스트(Valsalva/HUT), Training analytics (VT/VO2)
- ECG waveform QRS delineation
- Polar/FIT/Biopac 파서 전체 세트 (현재는 Moxy Calf.txt/xlsx만)
- Recurrence plot, D2
