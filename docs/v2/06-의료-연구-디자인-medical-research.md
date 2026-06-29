# 의료·연구 도메인 디자인 — 전문가들이 쓰는 프로그램이 어떻게 생겼나

작성: 2026-05-10
배경: 타겟 사용자 = 대학원·연구실·의료업계 (연구원 / 병원 종사자 / 의사). 다크 톤은 "칙칙" 하다는 피드백 → 의료·연구 SW 표준 톤으로 재정의.

---

## 0. 결론 — v2 디자인 톤 변경

```
[Before — 회색·다크 우선]                    [After — 라이트 + 의료 블루]
  bg          #0A0C10 (다크)        →       #F7F9FB (페이지) / #FFFFFF (카드)
  text        #E8EBF1                       #0F172A (진한 slate, 가독성 ↑)
  accent      #4ADE80 (형광 그린)   →       #0284C7 (의료 블루 / sky-600)
  semantic    단색 시맨틱            →       임상 의미 색 (정상=녹/주의=황/위급=적)
  spacing     컴팩트                 →       약간 여유 (Prism 영감)
  typography  14/24 px                       14/26 px (또렷이)
```

**다크는 옵션으로 보존** — 야간/장시간 분석 시 사용자가 토글.

---

## 1. 의료·연구 도메인 표준 — "왜 라이트인가"

### 사용 환경
- 병원 외래 / 연구실 데스크 = **밝은 형광등 / 직사광 환경** → 다크 화면은 반사 ↑, 가독성 ↓
- 출판·보고서 작성 = 인쇄/PDF 가 최종 산출물 → 화면도 인쇄 결과와 가까운 라이트가 자연
- 임상 협업 = 모니터 공유 / 회진 / 컨퍼런스 → 멀리서 보는 데이터는 흰 배경이 또렷
- 신뢰감 = "병원 = 흰 가운 / 연구실 = 백색 표면" 시각 자산이 라이트와 결합

### 색맹·색약 친화 (의료에서 표준 요구)
- 의료 SW 는 색만으로 정보 전달 금지가 사실상 표준 (파랑/녹/적 + 아이콘·텍스트 병기)
- v2 의 임상 시맨틱 색도 + 텍스트/아이콘 라벨 같이 사용

---

## 2. 레퍼런스 — 실제 의료/연구 SW 가 어떻게 생겼나

### 2.1 통계·분석 (연구실 표준)

| 앱 | 톤 | 차용할 것 |
|---|---|---|
| **GraphPad Prism 10** | 흰 배경, 청회색 패널, 옅은 그리드 | 출판 그래프 같은 깔끔함, 카드/시트 모델 |
| **JMP** (SAS) | 흰색, 옅은 회색 패널, 짙은 텍스트 | "Graph Builder" — drag-to-axis 인터랙션 |
| **MATLAB R2024b** | 흰 + 청회 nav, 텍스트 검정 | Live Editor 의 셀 + 결과 nesting |
| **Origin Lab 2024** | 흰 배경, 통계 결과 + 차트 동시 표시 | 워크북 모델 |
| **JASP** | 흰 + 파스텔, 베이지안 통계 | 분석 = 카드, 결과 즉시 표 |
| **R Studio (Posit)** | 흰 (다크 옵션) | Source / Console / Help 4분할 |
| **JupyterLab** | 흰 기본 | 파일 트리 + 에디터 + 결과 |
| **STATA** | 흰 + 짙은 회색 텍스트 | Command + Variables + Properties |

### 2.2 의료 영상·기록 (임상)

| 앱 | 톤 | 차용할 것 |
|---|---|---|
| **3D Slicer** | 라이트 패널 + 다크 viewport (이미지) | 데이터 viewport 만 다크, UI 는 라이트 |
| **OsiriX / Horos** (DICOM) | 라이트 UI + 다크 이미지 영역 | 위와 동일 패턴 |
| **OHIF Viewer** | 다크/라이트 토글, 측정 자동 색상 | toolbar 미니멀, 우 패널 측정 list |
| **Epic Hyperspace** (EHR) | 흰 + 청회, 폼 위주 | 환자 컨텍스트 헤더 항상 표시 |
| **PACS 시스템 다수** | 흰 또는 라이트 그레이 | 환자 ID/검사 메타 always visible |
| **Cerner PowerChart** | 흰 + 청회 + 명확한 layered nav | 좌 nav + 본문 + 우 detail |
| **3M HIS** | 흰 + 회색 패널 | 표 위주, 인쇄 친화 |

### 2.3 헬스/스포츠 과학 (연구 + 임상)

| 앱 | 톤 | 차용할 것 |
|---|---|---|
| **Kubios HRV** (현 도메인 직접 경쟁) | 라이트 + 청회 패널, 결과 표 | 카테고리별 탭 + 좌 데이터 트리 |
| **LabChart** (ADInstruments) | 라이트, 채널별 색 구분 | 시계열 + 채널 패널 |
| **PolySpec / EEGLAB** | 라이트 (MATLAB 위) | 신호 + 마커 + 인스펙터 |
| **Polar Performance Center** | 흰 + 빨강 accent (Polar 브랜드) | 워크아웃 카드 + 추세 |
| **TrainingPeaks Pro** | 흰 + 차분한 파랑 | PMC 차트 + 메트릭 카드 |

### 2.4 모던 SaaS — 라이트 톤의 모범 (의료/금융 등 신뢰업계 차용)

| 앱 | 차용할 것 |
|---|---|
| **Stripe Dashboard** | 흰 + 미세 elevation, 차트·표·시각 위계의 모범 |
| **Linear (Light mode)** | 흰 + 미니멀 + 키보드 우선 |
| **Notion** | 흰 + 블록 + 타이포 위계 |
| **Datadog (Light mode)** | 라이트 톤에서도 데이터 밀도 유지 |
| **Posit Connect** | 분석 결과 공유 페이지 |

---

## 3. 적용 — v2 토큰 변경

### 색

```
[Light — 기본]
  bg-0          #F7F9FB    페이지 (cool gray 미세)
  bg-1          #FFFFFF    카드 (순백)
  bg-2          #F1F5F9    hover
  bg-3          #E2E8F0    선택
  border        #E5E7EB
  border-strong #CBD5E1
  text-0        #0F172A    진한 slate (가독성 최우선)
  text-1        #475569
  text-2        #94A3B8    muted
  
  accent        #0284C7    ← 의료 블루 (sky-600)
  accent-2      #14B8A6    ← teal (보조)
  
  ─ 임상 시맨틱 ─
  normal        #16A34A    정상 범위 (green)
  warning       #D97706    주의 / 경계 (amber)
  critical      #DC2626    위급 / 즉각조치 (red)
  
  ─ 데이터 시각화 (10색 구분 + 색맹 친화) ─
  data-1  #0284C7  blue (1차 — Baseline / 정상 condition)
  data-2  #14B8A6  teal
  data-3  #7C3AED  violet
  data-4  #EA580C  orange
  data-5  #DB2777  pink
  data-6  #65A30D  lime green
  data-7  #0891B2  cyan
  data-8  #CA8A04  yellow
  data-9  #059669  emerald
  data-10 #9333EA  purple

[Dark — 옵션]
  같은 의미·역할로 슬레이트 어두운 톤
```

### 타이포

```
KPI 큰 값:   26px / weight 600 / -0.5 letter-spacing  ← 25→26 키움 (의료 가독성)
카드 제목:   14px / weight 600                         ← 13→14
본문:        14px / 400
캡션:        12px / 400 (muted)

family: Pretendard > Inter > Segoe UI > Malgun Gothic > system-ui
```

### 간격

```
xs 4 / sm 8 / md 12 / lg 16 / xl 24 / xxl 32  (4 step)
카드 padding 18px (16→18, 의료톤 여유)
카드 gap     12px (8→12)
그리드 gap   12px (8→12)
```

### Elevation (Light 톤이라 그림자 도입)

```
card_subtle    0 1px 3px rgba(15,23,42, 0.06)    카드 기본
hover          0 2px 6px rgba(15,23,42, 0.10)    호버 강조
modal          0 12px 32px rgba(15,23,42, 0.15)  모달
```

---

## 4. 임상 시맨틱 색의 의미

데이터 표시할 때 색만으로도 **즉시 의미 전달** 되도록:

| 의미 | 색 | 사용 예 |
|---|---|---|
| 정상 (Normal) | green `#16A34A` | GT 와의 차이 < 5% / Maintenance ≥ 70% |
| 주의 (Warning) | amber `#D97706` | GT 차이 5~15% / Maintenance 50~70% |
| 위급 (Critical) | red `#DC2626` | GT 차이 > 15% / Maintenance < 50% / 분석 실패 |

**색 + 텍스트/아이콘 병기 원칙** — 색맹/색약 사용자 고려:
- ✓ 정상  (✓ + green)
- ⚠ 주의  (⚠ + amber)
- ✗ 위급  (✗ + red)

---

## 5. 화면 구성 — 의료 SW 패턴 적용

### 환자 컨텍스트 항상 표시 (EHR 영감)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 김찬민 · 38 / Male · ID JH_08 · Wattmax 370W / VO2 67          ⓘ ⚙  │  ← 환자 헤더 항상
├──────────────────────────────────────────────────────────────────────┤
│ Condition: HYPER ▾   Timepoint: Recovery2 ▾    [▶ Analyze]   [⊕ Add] │  ← 분석 컨텍스트
├──┬───────────────────────────────────────────────────────────────────┤
│  │ [카드 그리드 — 흰 배경 / 미세 그림자 / 의료 블루 accent]            │
│🩸│                                                                     │
└──┴───────────────────────────────────────────────────────────────────┘
```

### 인쇄 친화 (의료 보고서 표준)

- 라이트 톤 = 인쇄 시 잉크 절약 + 가독성
- 차트 색 = 흑백 인쇄 시에도 패턴/스타일로 구분 가능 (점선/실선/대시)
- 표 = 그리드 명확 (현 컴파리슨 카드)

---

## 6. 사용자 추가 영역

(다른 의료/연구 SW 의견 자유 추가)

| 앱 | 좋은 점 | v2 에 가져갈 것 |
|---|---|---|
|  |  |  |
|  |  |  |
