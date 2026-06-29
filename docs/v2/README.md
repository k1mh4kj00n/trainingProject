# physical_analysis v2 — 설계 단계

작성: 2026-05-10
상태: 🚧 비주얼 1차 목업 완료 → 결정 + 디자인 합의 단계

**원칙**: **기능은 v1 100% 그대로**. 디자인 언어·인터랙션·IA 만 새로.
- v1 (`scripts/nirs_vot_gui/`) 은 그대로 운영
- v2 는 `scripts/v2/` 에서 별도 진행
- 분석 엔진 (`scripts/nirs_vot/`, `scripts/hrv_analysis/`, `scripts/config_loader.py`) 은 v2 에서 그대로 import 해 재사용

---

## 문서 지도

| # | 문서 | 목적 |
|---|---|---|
| 01 | [v1 회고](./01-v1-회고-retrospective.md) | v0.6.x 누적 변경에서 추출한 함정 + 유지할 강점 |
| 02 | [기술 스택](./02-기술-스택-tech-stack.md) | PySide6 / Tauri / Web 등 비교 + 권장 |
| 03 | [디자인 레퍼런스](./03-디자인-레퍼런스-references.md) | Linear/Vercel/Audacity/Logic Pro/Figma 등 8개 카테고리 → v1 기능별 매핑 |
| 04 | [비주얼 목업](./04-비주얼-목업-wireframe.md) | v1 기능을 새 톤·새 IA 로 재배치한 ASCII 와이어프레임 (메인/비교/Export/Cmd+K 4 화면) |
| 05 | **[대시보드 디자인](./05-대시보드-디자인-dashboard-design.md)** | **카드 기반 대시보드 + 분석 카드 등록 API + 우리 서비스 톤 5개 1차 레퍼런스. 새 분석 추가 = 파일 1개.** |
| 06 | **[의료·연구 디자인](./06-의료-연구-디자인-medical-research.md)** | **타겟 = 대학원/연구실/의료. Prism / JMP / MATLAB / 3D Slicer / Kubios 등 라이트 톤 표준 → v2 기본 테마 = 라이트 + 의료 블루 (#0284C7).** |

---

## 결정 트래커

코드 작성 시작 = 아래 모든 결정이 ✅ 가 되는 시점.

### 핵심 결정 (Critical Path)

| ID | 결정 | 상태 | 메모 |
|----|------|------|------|
| C-1 | 기술 스택: GUI 프레임워크 | 📌 대기 | 권장 = PySide6 유지 (회고+스택 문서 참조) |
| C-2 | UI 패턴: Widgets+store / QtQuick QML | 📌 대기 | C-1 = PySide6 일 때만 의미 |
| C-3 | 차트 라이브러리 | 📌 대기 | matplotlib (v1) / **pyqtgraph (대시보드 카드 다수 → 성능 권장)** / QtCharts |
| C-4 | IA: 모드 전환 / 도크 유지 / **대시보드 카드 그리드 (05 제안)** | 📌 대기 | 05 문서가 대시보드 권장 |
| C-5 | 디자인 시스템: 라이트/다크, 폰트, 토큰화 방식 | 📌 대기 | 05 문서에 1차 토큰값 (그린 accent) 제안 |
| C-6 | **분석 카드 등록 API** | 📌 대기 | 05 의 `@register_analysis_card` 데코레이터 ↔ entry_points |

### 부수 결정

| ID | 결정 | 상태 | 메모 |
|----|------|------|------|
| S-1 | v1 → v2 데이터 마이그레이션 정책 | 📌 대기 | xlsx 형식 그대로? Save params 호환? |
| S-2 | 명령 팔레트 (Ctrl+K) 도입 여부 | 📌 대기 | Linear 패턴 |
| S-3 | "Export 가 보고서 페이지" 패턴 도입 | 📌 대기 | Notion 패턴 |
| S-4 | NIRS / HRV 도메인 분리 강도 | 📌 대기 | 같은 앱 / 별 모드 / 별 앱 |
| S-5 | 빌드 모델: PyInstaller --onefile 유지 | 📌 대기 | v1 검증됨, 기본은 유지 |

### 범례

- 📌 **대기** — 결정 필요
- ✅ **확정** — 다음 단계 진행 가능
- ⛔ **폐기** — 검토했으나 채택 안 함 (대안 명시)

---

## 진행 단계 (Roadmap)

```
[현재] 설계 단계
   ├─ 01 회고      ✅ 작성됨 (사용자 관찰 추가 영역 비어있음)
   ├─ 02 스택      ✅ 작성됨 (사용자 결정 필요)
   └─ 03 레퍼런스  ✅ 작성됨 (사용자 관찰 추가 영역 비어있음)

[다음] 결정 단계
   ├─ C-1 ~ C-5 전체 ✅
   └─ S-1 ~ S-5 합의

[그 다음] 디자인 단계
   ├─ wireframe (저충실도) — 핵심 3 화면
   ├─ 컴포넌트 카탈로그 — 재사용 단위
   └─ 인터랙션 시나리오 — 자주 쓰는 흐름 5개

[그 다음] 구현 단계
   ├─ scripts/v2/ 채우기
   ├─ build_v2.bat 추가 (별도 .exe)
   └─ v1 사용자 마이그레이션 가이드
```

---

## scripts/v2/ 현재 상태

```
scripts/v2/
├── __init__.py    (placeholder)
├── app.py         (NotImplementedError — 결정 후 구현)
├── pages/
│   └── __init__.py
├── widgets/
│   └── __init__.py
└── theme/
    └── __init__.py
```

---

## 다음 액션 (사용자가 할 일)

**우선 검토: `05 대시보드 디자인`** — 이게 v2 의 메인 IA 제안.
1. 05 의 와이어프레임·카드 anatomy·등록 API 가 우리 서비스 흐름에 맞는지
2. 우리 서비스 톤 1차 5개 (Grafana / Datadog / intervals.icu / Apple Health / Stripe) 가 적절한지, 더 가까운 레퍼런스 있는지
3. 디자인 토큰 1차 제안 (다크 + 형광 그린) 톤 OK 인지

확정되면:
- C-3 (pyqtgraph), C-4 (대시보드), C-5 (디자인 토큰), C-6 (카드 등록 API) 가 한 번에 ✅
- → Phase 1 구현 시작 (theme + AnalysisCard Protocol + 12-col 그리드)

추가로 (선택, 시간 날 때):
- 04 와이어프레임의 다른 모드 (Compare/Export/Cmd+K) 의견
- 03 레퍼런스 8 카테고리에 추가하고 싶은 앱
- 01 회고의 "사용자 직접 작성 영역"
