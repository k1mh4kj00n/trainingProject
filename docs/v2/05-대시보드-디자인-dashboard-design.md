# v2 대시보드 디자인 — 카드 기반 + 분석 확장 가능

작성: 2026-05-10
관련: `04-비주얼-목업-wireframe.md` 의 메인 분석 화면을 **대시보드 모델** 로 재설계
원칙: **기능은 v1 100% 그대로**, **새 분석법을 플러그-인 처럼 추가 가능** 한 구조.

---

## 0. 결론 먼저

```
대시보드 = 카드 그리드 + 컨텍스트 (subject·condition·timepoint) + 카드 등록 API

   사용자가 새 분석을 추가 = 카드 1개 등록 (50줄 내외)
                           → 자동으로 + Add card 팔레트에 등장
                           → 사용자 드래그로 그리드에 추가
                           → 컨텍스트 변경 시 자동 재계산
```

핵심 3가지:
1. **대시보드** = 12-column responsive 그리드, 카드 drag·resize·add·remove (Grafana 패턴)
2. **분석 카드** = 입력(컨텍스트) → 계산(엔진 호출) → 렌더(차트/표/숫자) 3단 분리
3. **확장 API** = `@register_analysis_card` 데코레이터 1개로 카드 1개 등록 끝

---

## 1. 우리 서비스 톤 — 어디 영감 받을지

서비스 정체성 정리:
- **사용자**: 1인 연구자/개발자 (스포츠과학 + 임상 인근)
- **데이터**: NIRS-VOT 시계열 + ground truth + 운동 메타
- **작업 흐름**: 측정 → 분석 → 비교 → 보고
- **디자인 톤**: 과학적 정확성 > 화려함, but 답답하지 않게 — Datadog 정도의 모던함

→ **"전문가의 데이터 도구" 톤** (소비자 앱 아님, 그렇다고 1990년대 LabView 도 아님)

### 우리 서비스에 맞는 5개 1차 레퍼런스

| 앱 | 왜 우리와 어울림 | 가져갈 패턴 |
|---|---|---|
| **Grafana** | 과학·인프라 지표 dashboard 표준. 패널 = 카드, plugin 생태계, 시계열 + table + stat 한 화면 | 카드 그리드 + drag/resize, panel plugin 아키텍처, 좌측 nav `Home/Dashboards/Explore/...` |
| **Datadog** | 모던한 dark, 과학적이면서 답답하지 않음. Crosshair sync (여러 차트 hover 동기화) | Hover crosshair, anomaly highlight, 작은 sparkline 카드 |
| **intervals.icu** | 스포츠 도메인 + 1인 사용. 차분한 톤, FTP/HRV/recovery 모듈식 카드 | "오늘의 분석" 단일 페이지 + 비교 모드, 대시보드 카드 패턴 |
| **Apple Health (iOS)** | 바이오메트릭 카드의 모범. 큰 숫자 + 작은 컨텍스트 + 미니 sparkline | 카드 위계 (헤더/큰 값/추세/링크) |
| **Stripe Dashboard** | 정확성 강조하면서도 모던. 좌측 nav + 메인 카드 그리드 + 우측 detail drawer | 좌 nav 카테고리화, 카드 클릭 → 우측 drawer 자동 |

### 추가 레퍼런스 — 분석 모듈러 / 플러그인 아키텍처

| 앱 | 무엇을 볼지 |
|---|---|
| **Streamlit / Marimo** | `@app.cell` / 위젯 → 즉시 UI. 새 분석 = 함수 1개 |
| **Plotly Dash** | 컴포넌트 + 콜백 = 카드. callback 그래프 = 카드 간 의존성 |
| **Obsidian / Notion** | 블록/플러그인 모델 — 추가 = 클릭 한 번 |
| **VS Code** | 패널 + 명령 + 확장. "Activity bar" = 우리 좌측 icon-bar |
| **Figma plugin** | 외부 플러그인이 메인 캔버스에 자연스럽게 통합 |

### 의도적으로 피할 톤

- ❌ **소비자 헬스 앱 (Whoop / Oura)** — 너무 "보여주기", 정밀 분석 X
- ❌ **Excel / Origin / Prism (legacy)** — 정보 밀도 ↑, 톤 답답
- ❌ **Tableau / PowerBI** — BI 색채 강함, 우리 도메인엔 과함

---

## 2. 메인 화면 — 대시보드 와이어프레임

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ⌘ physical_analysis    ⌘K Search     [📊 Dashboard] [Compare] [Export]   ⚙ Settings │
├──┬───────────────────────────────────────────────────────────────────────────────┤
│  │ ① Context bar                                                                  │
│🩸│   김찬민  ▾  HYPER ▾  Recovery2 ▾                  ▶ Analyze   ⊕ Add card    │  ← Stripe drawer
│  │   38 / Male / 71kg · Wattmax 370W                                              │   영감
│❤ │ ───────────────────────────────────────────────────────────────────────────── │
│  │                                                                                │
│⚖ │  ┌───────────────────────────┬───────────────────────────────────────────┐   │
│  │  │ Baseline SmO2             │ NIRS-VOT trace                          ⋮ │   │  ← 카드들
│📥│  │  61.2 %                   │  85% ┊       ╱╲                          │   │     Datadog
│  │  │  GT 63.1 %  Δ −1.9        │      ┊      ╱  ╲___                       │   │     Grafana
│⚙ │  │  ▁▆█▃ (3 conditions)      │  60% ┊─────╱      ╲___                    │   │
│  │  └───────────────────────────┤      ┊                ╲╱╲╱                │   │
│  │  ┌───────────────────────────┤  35% ┊                                    │   │
│  │  │ Min · Peak                │      └─┬─────┬───────┬─────┬─────────────┘ │   │
│  │  │  Min  28.4  @ 15:08:42    │      start  inf    def   end                │   │
│  │  │  Peak 72.9  @ 15:13:15    │   I·O 키 = inflate/deflate                  │   │
│  │  │  Δ 44.5 %                 ├───────────────────────────────────────────┤   │
│  │  └───────────────────────────┤ Slope1 30-150s        T50                 │   │
│  │  ┌───────────────────────────┤  0.43 %/s              12.3 s              │   │
│  │  │ AUC 3 min                 │  GT 0.51   Δ −0.08    GT 11.7   Δ +0.6     │   │
│  │  │  82.4 %·min               │  ▁▇▁▆                  ▆▆██                │   │
│  │  │  GT 87.6   Δ −5.2         └───────────────────────────────────────────┘   │
│  │  │  ▆█▃▆ (3 conditions)                                                       │
│  │  └───────────────────────────┐                                                │
│  │  ┌───────────────────────────┤                                                │
│  │  │ Exercise · TTE            │                                                │
│  │  │  TTE1  45 s   TTE2  42 s  │                                                │
│  │  │  Maint 87.2% ✓             │                                                │
│  │  └───────────────────────────┘                                                │
│  │                                                                                │
└──┴───────────────────────────────────────────────────────────────────────────────┘
   Icon bar           ─── 12-column 그리드, 카드 drag/resize/add/remove ───
   44px (VS Code)
```

**카드 anatomy** (Grafana / Apple Health 영감):
```
┌────────────────────────────┐
│ Title           ⋮ menu     │  ← 12px 헤더
│                            │
│  대표 값 (24-32px bold)    │  ← 핵심 정보
│  컨텍스트 (12px muted)     │  ← GT/델타/단위
│  ───                       │
│  미니 시각화 (sparkline    │  ← 추세/분포
│   / chart / heat)          │
└────────────────────────────┘
```

---

## 3. 새 분석법 추가 — 확장성 아키텍처

### 3.1 데이터 흐름

```
     LoadedFile (v1 그대로)
            │
            ▼
   ┌──────────────────┐
   │  AnalysisContext │  ← {subject, condition, timepoint, anchor, overrides}
   └──────┬───────────┘
          │
          ▼
   ┌──────────────────┐
   │  AnalysisCard    │  ← Protocol — 모든 카드가 구현
   │   .compute(ctx)  │     (계산은 엔진 분리)
   │   .render(ctx,r) │     (결과 → Qt 위젯)
   │   .meta          │     (이름·아이콘·기본 사이즈)
   └──────────────────┘
          │
          ▼
       Card widget (메인 그리드 안 한 칸)
```

### 3.2 등록 API (목표 모양)

```python
# scripts/v2/analysis/baseline_smo2_card.py
from v2.cards import register, AnalysisCard, CardMeta

@register
class BaselineSmO2Card(AnalysisCard):
    meta = CardMeta(
        id="baseline_smo2",
        name="Baseline SmO2",
        category="NIRS",
        icon="droplet",
        default_size=(3, 2),  # 12-column grid 기준 width=3, height=2
        description="기저 SmO2 평균값과 GT 비교"
    )

    def compute(self, ctx: AnalysisContext) -> dict:
        # v1 의 분석 엔진 그대로 import
        from nirs_vot.metrics import compute_metrics
        result = compute_metrics(ctx.smoothed, ctx.anchor, ...)
        return {
            "value": result.baseline_smo2,
            "gt": ctx.gt.get("Calf_SmO2_Base"),
            "history": ctx.all_conditions_baseline,
        }

    def render(self, parent, data):
        # KPI 카드 위젯 (큰 값 + 컨텍스트 + sparkline)
        from v2.widgets.kpi_card import KpiCard
        return KpiCard(
            parent,
            value=f"{data['value']:.1f} %",
            comparison=("GT", f"{data['gt']:.1f}"),
            spark=data["history"],
        )
```

### 3.3 새 분석 추가 = 파일 1개

```
scripts/v2/analysis/
  ├── __init__.py            (자동 import 모든 *.py)
  ├── baseline_smo2_card.py
  ├── min_peak_card.py
  ├── slope1_card.py
  ├── slope2_card.py
  ├── t50_card.py
  ├── auc_card.py
  ├── tte_card.py
  ├── trace_card.py          ← 메인 시계열 + 핸들 (큰 카드)
  ├── comparison_card.py     ← multi-condition Δ 표
  └── 사용자_새카드.py       ← 사용자가 추가하면 끝
```

`+ Add card` 팔레트가 자동으로 모든 등록된 카드를 카테고리별로 보여줌:

```
┌─ Add card  ──────────────────────────────────┐
│  Search... 🔍                                 │
│  ─────────                                    │
│  📊 NIRS                                      │
│    □ Baseline SmO2          (3×2)            │
│    □ Min · Peak             (3×2)            │
│    □ NIRS-VOT trace         (8×4)            │
│    □ Slope1 / Slope2        (3×2)            │
│    □ T50 · AUC              (3×2)            │
│  ❤ HRV                                        │
│    □ SDNN · RMSSD           (3×2)            │
│    □ LF/HF spectrum         (6×3)            │
│    □ Poincaré plot          (4×4)            │
│  ⚖ Compare                                    │
│    □ Multi-condition table  (12×3)           │
│    □ Pareto / radar         (4×4)            │
│  📥 Custom                                    │
│    □ + New blank card                        │
└──────────────────────────────────────────────┘
```

---

## 4. 인터랙션 디테일

### 4.1 카드 그리드 행동

| 액션 | 단축키 | 결과 |
|---|---|---|
| 카드 추가 | Cmd+N | 팔레트 열림 |
| 카드 이동 | drag 헤더 | 그리드 snap |
| 카드 리사이즈 | drag 우하단 모서리 | 12-col grid snap |
| 카드 삭제 | Backspace 또는 ⋮ menu | 즉시 (Undo Cmd+Z) |
| 레이아웃 저장 | 자동 (선택 condition 별) | 다음에 같은 컨텍스트 시 복원 |
| 레이아웃 export | Cmd+Shift+S | json 파일 |

### 4.2 컨텍스트 변경 시

- 상단 context bar (subject / condition / timepoint) 변경
- 모든 카드가 **자기 자신의 compute** 만 재호출 (Marimo / Plotly Dash 영감)
- 변경 안 된 입력의 카드는 캐시 사용 (성능)
- 변경 중 시각: skeleton fade (Linear 영감)

### 4.3 카드 → 상세

- 카드 더블클릭 → 우측 drawer 가 그 카드의 detail 표시 (Stripe 영감)
- detail = 큰 차트 + 파라미터 spinbox + 메모

---

## 5. v1 기능 → v2 카드 매핑 (전부 보존)

| v1 컴포넌트 | v2 카드 |
|---|---|
| ParameterTable 의 12 metrics | KPI 카드 12개 (Baseline / Min / Peak / Slope1 / Slope2 / T50 / T95 / Magnitude / Oxy deficit / AUC 3min / Min time / Peak time) |
| NIRS-VOT 시계열 그래프 | TraceCard (핸들 드래그 그대로) |
| Session context 라벨 4개 | ContextCard (subject 메타) |
| TTE comparison 그리드 | ComparisonCard (multi-condition) |
| Auto detect 버튼 | TraceCard 안의 도구바 |
| Save/Load params | settings ⚙ 안 |
| Apply 버튼 | 카드 = 라이브 (자동 재계산), 명시 Apply 는 조건 변경에만 |
| HRV 5탭 | HRV 카드 묶음 (사용자가 dashboard 에 추가/제거) |

→ **새 통계 1개 추가 = 카드 1개 (50줄)**, **새 분석 도메인 추가 = 카드 묶음 1개**.

---

## 6. 디자인 토큰 (theme/) 1차 제안

### 색

```
[Dark]
  bg-0       #0A0C10    페이지
  bg-1       #11141A    카드
  bg-2       #161A22    카드 hover
  bg-3       #1F242E    nav active
  border     #232934    1px line
  text-0     #E8EBF1    제목·KPI 큰 값
  text-1     #A4ACB9    본문
  text-2     #6F7783    muted/legend
  
  accent     #4ADE80    primary (형광 그린, intervals 영감)
  accent-2   #38BDF8    secondary (시안)
  warn       #F59E0B
  error      #EF4444
  
  data-1~10  Datadog 팔레트  (시계열 multi-line)

[Light] inverse
```

### 타이포

```
KPI 큰 값        24px / 600 weight / -0.5 letter-spacing
KPI 컨텍스트     12px / 400 / muted
카드 제목        13px / 600
본문             14px / 400
mono             12px / 400 (시각·anchor 표시)

폰트 fallback: Pretendard / Inter / SF Pro / system-ui
```

### 간격

```
4 / 8 / 12 / 16 / 24 / 32 / 48 px

카드 padding         16px
카드 내부 spacing    8px
그리드 gap           8px
nav padding          12px 8px
```

### 반경

```
카드          8px
버튼          6px
input         4px
모달/drawer   12px
```

### 그림자

```
카드            none (1px border 만)
hover           0 1px 2px rgba(0,0,0,0.4)
modal           0 8px 32px rgba(0,0,0,0.6)
```

---

## 7. 구현 단계 (제안)

```
Phase 1 (1~2일) — 기반
  □ scripts/v2/theme/ 토큰 (color/typography/spacing)
  □ scripts/v2/widgets/ 기본 컴포넌트 (KpiCard, ChartCard, Drawer)
  □ scripts/v2/cards/ AnalysisCard Protocol + register 헬퍼
  □ scripts/v2/dashboard.py 12-col 그리드 (QGridLayout 기반)

Phase 2 (2~3일) — 기존 분석 카드화
  □ trace_card.py (NIRS-VOT 시계열 + 핸들)
  □ baseline / min_peak / slope1 / slope2 / t50 / auc / tte 7개 KPI 카드
  □ comparison_card.py
  □ context_card.py (subject 메타)

Phase 3 (1~2일) — 인터랙션
  □ + Add card 팔레트
  □ 드래그 reorder / resize
  □ 레이아웃 자동 저장 (condition 별 json)
  □ Cmd+K 명령 팔레트

Phase 4 (1일) — 마감
  □ Compare 모드 (다른 dashboard preset)
  □ Export 모드 (보고서 페이지)
  □ build_v2.bat
```

---

## 8. 합의 필요 항목

- [ ] **카드 그리드 라이브러리**: 직접 구현 (QGridLayout + drag) ↔ 외부 (예: PyQtAdvancedDocking, GraphicsView 기반 custom)
- [ ] **색 액센트**: 형광 그린 (#4ADE80) ↔ 다른 색
- [ ] **레이아웃 자동 저장 위치**: appdata/ ↔ 프로젝트 폴더
- [ ] **카드 등록 방식**: 데코레이터 (제안) ↔ entry_points (setup.py 기반)
- [ ] **Phase 1 부터 진행**: 시작 OK ↔ 와이어프레임 더 다듬은 후

---

## 9. 사용자 추가 영역

(v2 대시보드 IA 에 대한 의견 / 카드 우선순위 / 새 분석 아이디어 등)

- 
- 
- 
