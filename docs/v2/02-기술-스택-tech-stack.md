# 기술 스택 — v2 선택지 비교

작성: 2026-05-10
제약 조건 (v1 부터 확정):
- 단일 Windows .exe 배포 가능해야 함 (사용자가 더블클릭으로 실행)
- 한국어 UI / 폰트 깨짐 없음
- matplotlib (또는 동급) 의 SmO2 시계열 + dragabbel handle 가능
- xlsx 입출력 (openpyxl 호환)
- 오프라인 동작 (네트워크 의존 X)
- 1인 개발 유지보수

---

## 후보 매트릭스

| 항목 | PySide6 (현재) | Tkinter + ttk | Electron + JS | Tauri + Web | FastAPI + React (web) | Streamlit |
|---|---|---|---|---|---|---|
| **단일 .exe** | ✅ PyInstaller | ✅ PyInstaller (작음) | ✅ 큼 (~150MB) | ✅ 작음 (~10MB) | ❌ 서버 필요 | ❌ 서버 필요 |
| **GUI 표현력** | ★★★★★ | ★★ | ★★★★★ | ★★★★★ | ★★★★★ | ★★ |
| **시계열 차트 + drag** | matplotlib (검증됨) | tkinter canvas (수동) | Recharts/D3/uPlot | 동일 | 동일 | plotly (제한적) |
| **한국어 폰트** | 자동 감지 OK (v1 검증) | 폰트 설정 수동 | OS font OK | OS font OK | OS font OK | OK |
| **파일 다이얼로그** | QFileDialog (네이티브) | OK | dialog API | OS API | 브라우저 한계 | 업로드만 |
| **xlsx 처리** | openpyxl (Python) | openpyxl | xlsx-js (별도) | 백엔드 분리 | openpyxl | openpyxl |
| **개발 속도 (1인)** | ★★★★ (v1 자산) | ★★★ | ★★★ (학습) | ★★ (학습 큼) | ★★★ (분리) | ★★★★★ |
| **분석 엔진 (Python) 재사용** | ✅ 직접 | ✅ 직접 | ❌ 재구현/IPC | △ Python sidecar | ✅ 백엔드 | ✅ |
| **빌드 안정성** | ✅ v1 검증 | ✅ | △ 큰 번들 | △ 비교적 신생 | n/a | n/a |
| **외부 의존 라이선스** | LGPL (Qt) | PSF | MIT/MPL | MIT | MIT | Apache |
| **재배포 사이즈** | ~100MB (PyInstaller --onefile) | ~30MB | ~150MB | ~15MB | n/a | n/a |
| **디자인 자유도** | QSS + custom paint | 매우 제한 | CSS 무한 | CSS 무한 | CSS 무한 | 제한 |

---

## 옵션별 종합 평가

### A) PySide6 (현재 — 점진 발전)
**장점**: v1 코드/엔진 그대로 재사용 (분석은 Python 모듈), 검증된 빌드, 네이티브 LookAndFeel, 한국어 폰트 자동 처리, 1인 개발 유리
**단점**: QSS 기반 스타일링은 모던 웹 만큼 자유롭지 않음, 도크/시그널 모델의 함정 누적 (v1 회고 참조)
**v2 가능성**: v1 의 GUI 적층 문제를 풀려면 Qt 안에서도 QML / QtQuick 으로 전환 가능 (선언형 + 모던 UI)

### B) Tkinter
**장점**: Python 표준, 가장 작은 .exe
**단점**: 디자인 자유도 매우 낮음, drag 핸들·매끈한 차트 구현 부담 큼
**판정**: ⛔ v1 보다 후퇴. 제외.

### C) Electron
**장점**: 디자인 자유도 무한, JS 생태계 (Recharts/D3/Plotly/uPlot 풍부)
**단점**: 분석 엔진 (Python) 을 IPC 로 호출 (sidecar) — 1인이 두 언어 + 빌드 파이프라인 유지 부담, 번들 큼
**판정**: ❌ 1인 + 작은 사용자층에 과함

### D) Tauri (Rust 코어 + Web frontend)
**장점**: Electron 보다 훨씬 작은 번들 (~15MB), 모던 웹 디자인
**단점**: Rust 학습 + Python 분석을 sidecar 또는 PyOxidizer 결합, 한국어 환경 안정성 검증 부족, 신생
**판정**: △ 미래 옵션. 지금은 부담.

### E) FastAPI + React (브라우저)
**장점**: 디자인·차트 무한, 분석 엔진은 백엔드 그대로 Python
**단점**: **단일 .exe 배포 불가** (서버 + 브라우저 필요) → 제약 조건 위배
**판정**: ⛔ 배포 모델 안 맞음. 제외.

### F) Streamlit
**장점**: 가장 빠른 prototype
**단점**: 단일 .exe 배포 불가, drag 핸들 같은 정밀 인터랙션 한계, 디자인 통제 약함
**판정**: ⛔ 제외.

---

## 권장: **PySide6 유지 (현 v1 자산 보존), 단 QML 또는 declarative pattern 도입 검토**

근거:
1. 제약 조건 (단일 .exe + 오프라인) 을 만족하는 후보가 PySide6 / Tkinter / Tauri 셋뿐
2. 분석 엔진이 이미 Python 으로 분리되어 있어 GUI 만 갈아끼우면 됨 — PySide6 가 가장 자연스러움
3. v1 의 GUI 문제는 **프레임워크 탓이 아니라 IA·상태관리 설계 탓** — 같은 PySide6 안에서도 다음 둘 중 하나로 풀 수 있음:
   - (a) **Widgets + 명시적 store** (현 위젯 트리 + Redux-스타일 단방향 데이터 흐름)
   - (b) **QtQuick/QML** (선언형 declarative UI + JS-like 바인딩)

### 차선 (시간이 충분하다면): Tauri + Python sidecar
- v3 후보로 메모. 모던 UI 가 절실해질 때.

---

## 확정해야 할 후속 결정 (v2 시작 전)

- [ ] **PySide6 유지** ↔ Tauri 검토
- [ ] (PySide6 라면) **Widgets + store** ↔ **QtQuick/QML**
- [ ] **차트 라이브러리**: matplotlib (현재) 유지 ↔ pyqtgraph (성능 ↑) ↔ QtCharts (네이티브)
- [ ] **상태 관리 패턴**: 명시적 store 도입 ↔ signals/slots 정밀 설계
- [ ] **디자인 시스템**: QSS 토큰화 ↔ qt-material / PyQtDarkTheme 등 외부 라이브러리

---

## 사용자 의견 / 추가 후보

(여기에 덧붙이실 내용 자유롭게)

- 
