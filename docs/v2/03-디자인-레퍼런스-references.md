# v2 디자인 레퍼런스 — 비주얼/인터랙션

작성: 2026-05-10
전제: **기능은 v1 그대로**, 디자인 언어와 인터랙션만 새로.

이 문서는 "보러 갈 곳" 의 큐레이션입니다. 각 레퍼런스는:
- **무엇을 볼지** (구체 화면/요소)
- **v1 의 어느 기능에 매핑** 되는지
- **차용할 패턴**

---

## 0. 한 페이지 요약 — v2 가 가져갈 다섯 가지

| # | 디자인 결정 | 출처 (1차) | v1 어디에 적용 |
|---|---|---|---|
| 1 | **다크 우선 + 모노크롬 + 1 accent color** | Linear / Vercel / Arc | 전 화면 톤 |
| 2 | **사이드바 navigation + 메인 캔버스 1개** | Linear / Hex / Notion Calendar | 페이지 전환 (도크 ↓) |
| 3 | **Properties/Inspector 우측 슬라이드** | Figma / Blender 4 | ParameterPanel |
| 4 | **타임라인 = waveform 패턴** | Audacity / Logic Pro / Praat | NIRS-VOT 그래프 + anchor drag |
| 5 | **명령 팔레트 (Cmd+K)** | Linear / Raycast / Arc | + Add timepoint, Analyze, Export |

---

## 1. 🎨 모던 SaaS 비주얼 — "톤" 의 기준선

### Linear (linear.app)
- **무엇을 볼지**: 모노크롬 dark theme, 4-5단계 grayscale, 1 accent (보라/형광 그린), 14px 본문/13px UI, 8px grid
- **v1 매핑**: 전체 색·간격·폰트 시스템 (style.py / theme/)
- **차용**: `--bg-1, --bg-2, --bg-3` 단계적 배경 + `--accent` 1개. 그라데이션·shadow 거의 없음. 테두리는 1px `--border-subtle`.

### Vercel Dashboard (vercel.com)
- **무엇을 볼지**: 카드 안의 차트, 미니 sparkline, 큰 숫자 + 변화량 작게, 모든 카드가 같은 corner-radius (8px) + 같은 padding
- **v1 매핑**: ParameterTable (Ours vs Ground truth) 의 metric 카드화
- **차용**: 한 metric = 한 카드. 색은 차트 대신 숫자 옆 작은 colored dot 으로.

### Arc Browser (arc.net)
- **무엇을 볼지**: spaces (작업 컨텍스트 분리), 좌측 sidebar 가 "현재 작업" 만 보여줌, 명령 팔레트
- **v1 매핑**: NIRS / HRV / 비교 / Export 모드를 "spaces" 처럼 분리
- **차용**: 사용자가 "지금 뭘 하는지" 가 sidebar 첫 줄로 명확. 모드 안에서는 도구가 단순.

### Raycast (raycast.com)
- **무엇을 볼지**: Cmd-Space 로 모든 액션, fuzzy search, 키보드 우선
- **v1 매핑**: + Add timepoint / Apply / Analyze / Export 등 잦은 액션
- **차용**: Cmd+K → 입력하면 액션 + 매개변수까지 한 줄로 (예: `> add timepoint Recovery5 14:30 14:35 lead 90 tail 240`)

---

## 2. 🔬 과학·분석 도구 — "정확한 정보 밀도"

### GraphPad Prism 10 (recent redesign)
- **무엇을 볼지**: 출판 그래프 + 통계 결과 + 데이터를 "워크북" 으로 묶음. 좌측에 sheet tree, 메인은 한 개 그래프 정밀 편집.
- **v1 매핑**: condition (HYPER/HYPO/NOR) 비교 워크북 패턴
- **차용**: "한 실험 = 한 워크북, 여러 sheet" 구조. 각 sheet 가 다른 분석 단계.

### JMP (jmp.com)
- **무엇을 볼지**: "Graph Builder" — 데이터 컬럼을 drag 해서 그래프 즉시 빌드. 변환 후 다시 drag 가능.
- **v1 매핑**: Multi-session 비교에 유용. 사용자가 condition × session × metric 을 선택해 즉시 차트.
- **차용**: drag-to-axis 인터랙션 1 개 살리면 v2 의 차별화 포인트.

### Observable HQ / notebook (observablehq.com)
- **무엇을 볼지**: 셀별 미니 차트, 변수 변경 시 즉시 dependency 재계산, hover 로 값 표시
- **v1 매핑**: lead/tail spinbox 변경 → anchor 즉시 반영 (현재도 됨, 시각화 강화)
- **차용**: 변경 사항이 어디에 영향 미치는지 시각적 피드백 (예: spinbox 변경하면 그래프의 해당 영역이 1초간 highlight)

### Marimo (marimo.io)
- **무엇을 볼지**: reactive notebook. 한 셀 변경 → 의존 셀 자동 재실행. UI 위젯과 코드가 자연스럽게 연결.
- **v1 매핑**: parameter 변경 → 분석 자동 재실행 (v1 도 함, 하지만 어느 부분이 갱신되는지 시각적으로 약함)
- **차용**: "갱신 중" 시각화 — skeleton loader 또는 fade transition.

---

## 3. 📊 데이터 대시보드 — "정보 밀도와 깊이"

### Datadog (datadog.com)
- **무엇을 볼지**: 시계열 + annotation 레이어, hover 시 crosshair + 모든 시리즈 값, 좌측 facet filter
- **v1 매핑**: NIRS-VOT 그래프 hover 정보, 좌측 데이터 트리
- **차용**: hover crosshair + 우상단 floating 값 박스 (현재 v1 은 hover 정보 약함)

### Grafana 11 (grafana.com — 최근 리디자인)
- **무엇을 볼지**: scenes editor, 좌측 nav 통합, 더 차분한 dark theme
- **v1 매핑**: 페이지 전환 IA
- **차용**: 좌측 nav 의 "icon-only collapsed" / "label expanded" 토글 패턴.

### Hex.tech (hex.tech)
- **무엇을 볼지**: 데이터 + 코드 + 차트가 한 페이지에 자연스럽게. 드래그로 블록 재배열.
- **v1 매핑**: Export 가 단순 파일이 아니라 페이지 자체가 "공유 가능한 보고서"
- **차용**: v2 의 결과를 "클릭하면 PDF/PNG export 되는 라이브 페이지" 로 (Notion 식)

### Linear Insights (linear.app/insights)
- **무엇을 볼지**: "View" 단위로 차트 저장, 빠른 필터, 미니 통계 카드
- **v1 매핑**: "내 분석 view" 저장 (현재 없음)
- **차용**: 자주 쓰는 분석 조합을 "view" 로 저장 → 다음 세션에서 한 클릭 복원.

---

## 4. 🎵 시계열 편집 — "anchor drag 의 진화"

이 카테고리가 v1 의 핵심 인터랙션 (NIRS-VOT 4점 anchor drag) 과 가장 가까움.

### Audacity (recent UI refresh)
- **무엇을 볼지**: waveform 위의 region selector (drag 로 시작·끝 잡기), 키보드로 미세 조정
- **v1 매핑**: NIRS-VOT 의 inflate / deflate vline drag
- **차용**: drag 외에 키보드로 ±1초 단위 ([·] 키), Shift+drag 로 ±0.1초 정밀.

### Logic Pro / Reaper (DAW)
- **무엇을 볼지**: 트랙 위에 region 을 클릭하면 우측 inspector 가 region 속성을 표시 (start/end/length/level 등)
- **v1 매핑**: timepoint 클릭 → 우측 panel 이 그 timepoint 의 속성만 보여주기
- **차용**: 컨텍스트 인스펙터 = "선택한 객체에 따라 내용 자동 변경"

### Praat (음성 분석)
- **무엇을 볼지**: spectrogram 위에 boundary marker, drag 로 세분화, label 편집
- **v1 매핑**: timepoint 이름 + 시각 동시 편집
- **차용**: 그래프 위에서 직접 timepoint 이름 클릭 → 인라인 편집 (현재 v1 은 Parameters 패널에서만 가능)

### Adobe Premiere — Source Monitor in/out points
- **무엇을 볼지**: I (in) / O (out) 단축키로 즉시 마킹, 마킹된 구간이 timeline 에 색상 띠로 표시
- **v1 매핑**: 그래프 hover 상태에서 단축키 한 번에 inflate/deflate 마크
- **차용**: keyboard-first 마킹 → 마우스 안 옮기고 작업.

---

## 5. 💪 헬스·바이오 — "도메인 친근감"

### intervals.icu
- **무엇을 볼지**: 운동 세션 비교 (이번 vs 평소), powerload curve, FTP 변화 시각화
- **v1 매핑**: TTE comparison 그리드, condition 별 비교
- **차용**: "현재 vs 이전" 자동 비교 토글 — TTE/Wattmax 등에 적용.

### Whoop App
- **무엇을 볼지**: 한 화면 = 하나의 핵심 metric (recovery, strain), drill-down 으로 detail
- **v1 매핑**: 한 condition × session 의 12 metrics 카드 표시
- **차용**: 큰 숫자 + 작은 컨텍스트 (예: `42.3% Min SmO2  •  GT 41.8%  •  +1.2%`)

### Oura Ring App
- **무엇을 볼지**: 오늘/어제/주/월 스파크라인, 색으로 좋음·보통·나쁨 즉시 표현
- **v1 매핑**: ground truth 대비 색 (현재 ✓ ≈ ✗ 기호 + 색)
- **차용**: 색·아이콘만으로 한눈에 "OK / 의심 / 이상" 분류.

### TrainingPeaks
- **무엇을 볼지**: 시간축 위에 여러 zone 을 색상 띠로 (Z1~Z7)
- **v1 매핑**: occlusion / reperfusion / baseline 영역 음영
- **차용**: 영역마다 라벨 + 색 + alpha 일관 → v1 보다 정돈된 음영.

---

## 6. 🛠 도크·패널 모델 — "토글 함정 회피"

### VS Code (현 디자인)
- **무엇을 볼지**: 좌 sidebar (icon bar) + 좌 panel + 메인 + 우 panel + 하단 panel. 각 패널이 독립적으로 collapse.
- **v1 매핑**: 도크 4개의 토글 함정 (v1 회고 #1)
- **차용**: 좌측은 **icon bar 항상 보임 + panel 부분만 collapse**. 토글 = panel only, icon bar 는 안 사라짐.

### Blender 4
- **무엇을 볼지**: 영역 (area) 분할 모델 — 사용자가 화면을 N 등분하고 각 영역에 editor 할당
- **v1 매핑**: 분석/그래프/파라미터/결과 영역 분할
- **차용**: 영역 = "고정". 토글이 아니라 영역 안의 editor 만 전환.

### Figma — Properties 패널
- **무엇을 볼지**: 우측 패널이 선택한 객체 종류에 따라 자동 변경 (Frame / Text / Group …)
- **v1 매핑**: 사용자가 timepoint vs condition vs result 를 선택할 때 우측 panel 자동 변경
- **차용**: "선택 = 우측 컨텍스트 자동 갱신". 사용자가 토글 안 함.

---

## 7. 🩺 의료/과학 영상 + 주석 — "정밀 마킹 UX"

### OHIF Viewer (의료 DICOM 뷰어, 오픈소스)
- **무엇을 볼지**: 상단 툴바 + 메인 viewport + 우측 측정값 list. 측정마다 색상 자동 부여 + 라벨.
- **v1 매핑**: timepoint = 측정. 자동 색상.
- **차용**: timepoint 마다 자동 부여되는 팔레트 색이 그래프 + 트리 + 표 모두에서 일관되게 사용.

### Napari (영상 분석)
- **무엇을 볼지**: layer 모델 — 데이터/주석/계산 결과가 layer 로 쌓임, 각 layer 토글
- **v1 매핑**: 그래프 위 raw / smoothed / anchor 음영 / hover crosshair 등
- **차용**: 시각 요소를 layer 로 정리 → 사용자가 보고 싶은 것만 toggle.

### Label Studio
- **무엇을 볼지**: 키보드 단축키 중심의 빠른 라벨링, 한 화면에서 수십 개 인스턴스 처리
- **v1 매핑**: 여러 condition 빠른 일괄 검수
- **차용**: "다음 condition" / "이전 condition" 단축키 (현재 v1 은 콤보 클릭만).

---

## 8. 📓 모던 노트북 / 보고서 — "Export 가 결과물"

### Notion / Notion Calendar
- **무엇을 볼지**: 페이지 = 블록 조립. 차트·표·메모를 자유 배치.
- **v1 매핑**: 분석 결과를 "라이브 보고서 페이지" 로
- **차용**: 분석 종료 후 "📄 Open as report" → 자동 생성된 페이지 (제목·메타·차트·표·메모 영역)

### Posit Connect (rstudio.com)
- **무엇을 볼지**: 분석 결과를 그대로 공유 링크화
- **v1 매핑**: HTML/PDF Export
- **차용**: 단일 HTML 파일 export — 이메일 첨부 가능.

---

## 종합 — v2 비주얼 방향 (1차 제안, 수정 환영)

```
■ 톤        : 다크 우선 (라이트 스위치 가능). Linear/Vercel 모노크롬 + 형광 그린 1색
■ IA        : 좌 icon-bar (모드 전환) + 좌 panel (컨텍스트) + 메인 + 우 inspector
              (도크 4개 → 영역 4개. 토글 X. Inspector 가 컨텍스트 따라 자동.)
■ 차트      : pyqtgraph (PySide6 네이티브, fast). 스타일은 Datadog/Logic Pro 영감.
■ 인터랙션 : Cmd+K 명령 팔레트 + 그래프 위 키보드 마킹 (I/O/[/]) + drag
■ 결과     : 분석 끝 → 자동으로 "보고서 view" 생성. PDF/PNG 1-click export.
```

---

## 사용자 수정·추가 영역

다른 앱이 떠오르거나 톤이 안 맞으면 아래에 자유롭게:

| 앱 / 기준 | 좋은 점 | v2 어디에 |
|---|---|---|
|  |  |  |
|  |  |  |

---

## 참고: 화면 캡처 모으는 곳

`docs/v2/references/` 에 png/jpg 떨어뜨리고 파일명 `<app>-<feature>.png` 규칙. 본 문서에서 `![label](references/file.png)` 로 인용.
