# v1 회고 — physical_analysis v0.6.x 가 알려준 교훈

작성: 2026-05-10
근거: progress.md 의 v0.1 ~ v0.6.27 내용 + 이번 세션의 audit + 사용자 피드백 누적

이 문서의 목적은 v2 가 **반복하지 말아야 할 함정** 을 명확히 하고, **유지할 강점** 을 추리는 것.

---

## 🔴 v1 에서 반복적으로 손보게 된 영역 (3회 이상 수정)

### 1. 도크 레이아웃 / 토글 동작
- v0.6.4 → 0.6.5: Session Parameters 도크가 Top → Right 영역으로 두 번 이동
- v0.6.5: tabify + setTabPosition(North) 으로 탭 라벨 위치 조정
- v0.6.18, 0.6.25: 토글 액션 lambda 수정 (PySide6 시그널 오버로드 ambiguity)
- v0.6.25: visibilityChanged 동기화 누락 → X 닫기 후 토글 stale
- v0.7 (최근): 사용자가 "토글 = 핀이 아니라 화면 전환처럼 보임" 지적 → splitDockWidget 시도 후 다시 tabify 로 복구

**원인**: QDockWidget 모델이 "탭 묶음 + visibility + raise + 사용자 드래그 재배치" 를 동시에 다룰 때 사용자 멘탈 모델과 어긋남. 코드로 매번 우회 패치.

**v2 시사점**: 도크 시스템 자체를 사용하지 않거나, 사용하더라도 도크 개수 ≤ 2 로 단순화. **사용자가 매번 토글하는 패널이 5개** 라는 사실 자체가 IA(정보 구조) 가 잘못됐다는 신호.

### 2. ParameterPanel 의 "show_for" 가 모든 걸 다시 그리기
- v0.6.6, 0.6.7: 매번 `fig.clear()` → setup/update 분리 (성능)
- v0.7 (이번): show_for 가 timepoint 행을 매번 destroy/recreate → diff-aware 패치
- 호출 경로가 너무 많음 (`_on_result_ready`, `_on_params_applied`, `_on_condition_changed`, `_on_session_changed`, `_refresh_panels_for`)

**원인**: "패널 = 한 cfg 의 view, 매번 통째 redraw" 라는 단순한 멘탈 모델로 시작했다가 부분 갱신 (Min/Peak only / row only / TTE only) 요구가 누적되며 호출 경로가 폭발. 명시적 reactive 모델 부재.

**v2 시사점**: 데이터 → 위젯 매핑을 **선언형 + diff-aware** 로 처음부터 설계. 한 곳에서 cfg 변경 → 영향받는 위젯만 자동 갱신. (Pattern: signals/slots 의 정밀한 설계 또는 reactive store)

### 3. 시각화 레이어의 하드코딩된 ("Baseline", "Recovery2")
- v0.6.0 부터 분석/UI/저장 모든 곳에 2개 fixed timepoint 가정
- v0.7 (이번): 사용자 요구로 동적 timepoint → 5+ 파일 동시 수정 (config_loader, anchors, parameter_panel, app, parameter_table, full_trace_tab, data_browser, parameter_io)

**원인**: 프로토콜 (Baseline / Recovery2 두 시점) 을 데이터 모델 깊숙히 박았음. 도메인이 살짝 변하자 모든 layer 가 흔들림.

**v2 시사점**: timepoint 는 **이름·시각·메타** 의 N개 list 가 데이터 모델의 시작점. UI/분석/저장 어디서도 fixed names 를 가정하지 않음.

### 4. 시그널 오버로드 / 인자 불일치 미니 버그
- v0.6.25: triggered 인자 ambiguous → lambda 처방
- v0.7 (이번): textChanged → Signal() emit 직접 연결 시 TypeError → lambda 처방
- 같은 패턴이 4곳 잠재 (clicked 는 우연히 0-arg 오버로드 있어 살아있음)

**원인**: PySide6 시그널 시스템의 알려진 함정. 매번 사람이 기억해야 함.

**v2 시사점**: 헬퍼 (예: `safe_connect(src_sig, dst_sig)`) 또는 다른 reactive 패턴 (Signal Bus / Event Loop) 도입 검토.

---

## 🟡 사용자가 자주 마주친 마찰 (이번 세션 + 누적)

| # | 증상 | 우회 방법 (v1) | 본질적 원인 |
|---|---|---|---|
| 1 | Export 버튼이 도크 짧을 때 화면 밖 | ScrollArea + 버튼 바닥 핀 (이번 세션) | 가변 컨텐츠 + 항상 보여야 할 액션의 충돌 |
| 2 | timepoint 추가 시 화면 깜빡임 | diff-aware show_for (이번 세션) | 위에 #2 |
| 3 | 폴더 로드 중 GUI 멈춤 | WaitCursor + processEvents (이번 세션) | 메인 스레드에서 I/O |
| 4 | + Add 행 후 무엇을 입력할지 모름 | 자동 이름 + selectAll + setFocus (이번 세션) | 입력 안내 부재 |
| 5 | 검증 실패 시 사용자가 모르고 Apply | QMessageBox 검증 (이번 세션) | 입력 즉시 검증 부재 |
| 6 | "토글 = 핀" 멘탈 모델 vs 탭 전환 | (해결되지 않음) | 도크 + 탭 묶음 모델 자체 한계 |
| 7 | 분석 탭 / 전체 데이터 탭 / HRV 5탭 / 도크 3개 — 어디 뭐 있나 헤맴 | (해결되지 않음) | IA 복잡도 |
| 8 | NIRS 와 HRV 가 같은 화면에 있는데 서로 무관 | (해결되지 않음) | 도메인 분리 부족 |
| 9 | "한 condition 1 파일 + 1 cfg" 페어링 자동 추론이 깨지면 디버깅 어려움 | (해결되지 않음) | 파일 명명 규칙 의존 |

---

## 🟢 유지할 강점 (v1 이 잘 한 것)

- **분석 엔진 분리** (`nirs_vot/`, `hrv_analysis/`) — GUI 와 독립, 그대로 재사용 가능
- **`SessionConfig` 데이터클래스** — 한 condition 의 메타·구간을 하나의 컨테이너로
- **xlsx 파서 양방향 호환** (구 grid + 신 long-table) — 파일 형식 변경 시 사용자 데이터 보호
- **그래프 위 드래그로 anchor 조정** — 복잡한 시각 윈도우 편집을 직관적으로
- **Min/Peak override + Auto detect** — 분석 로직과 사용자 판단의 균형
- **Save params / Load params (xlsx/csv/txt 3종)** — 파라미터 스냅샷 round-trip
- **Korean 폰트 자동 감지** (matplotlib + Qt) — 환경별 글리프 깨짐 방지
- **단일 .exe 빌드** (PyInstaller) — 사용자 배포 단순

→ **v2 는 이 7가지를 그대로 가져가거나 import 해서 재사용.**

---

## 핵심 진단 (1줄)

> v1 은 "엔진은 견고, GUI 는 적층" — 분석 로직은 분리됐지만 GUI 가 매 요구마다 한 layer 씩 더 쌓이며 IA·상태 관리·렌더 정책이 흐려졌다.

**v2 의 임무**: 이 GUI 적층을 처음부터 다시 — 명확한 IA, 선언형 데이터 → 위젯 매핑, 단순한 토글/패널 모델.

---

## v1 의 어떤 점이 불편했는지 — 사용자 직접 작성 영역

(아래는 사용자가 직접 추가/편집할 항목. 위 분석에 빠진 것 자유롭게 적기)

- [ ] 
- [ ] 
- [ ] 
