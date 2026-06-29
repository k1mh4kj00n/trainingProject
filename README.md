# trainingProject

HRV와 NIRS-VOT 생리 데이터를 분석하고, Windows 실행 파일로 배포 가능한 분석 도구를 만들기 위한 private 프로젝트입니다.

## 프로젝트 개요

이 프로젝트는 실험/훈련 데이터 분석을 위해 HRV 지표와 NIRS-VOT 지표를 계산하고, GUI 기반 분석 흐름과 문서화된 사용법을 제공하는 것을 목표로 합니다.

핵심 범위는 다음과 같습니다.

- HRV 시간영역, 주파수영역, 비선형 지표 계산 모듈
- NIRS-VOT 데이터 전처리, 앵커 탐지, 지표 계산, 시각화 모듈
- PySide/Qt 기반 GUI 앱과 Windows 실행 파일 빌드 스크립트
- 검증 리포트, 데이터 모델, GUI 설계, 사용법 문서
- 연구/검증에 필요한 참고자료와 샘플 분석 자료

## 주요 실행 파일과 스크립트

| 경로 | 내용 |
| --- | --- |
| `run_app.py` | GUI 앱 실행 진입점 |
| `scripts/hrv_analysis/` | HRV 분석 모듈 |
| `scripts/nirs_vot/` | NIRS-VOT 분석 모듈 |
| `scripts/nirs_vot_gui/` | GUI 앱 구현 |
| `scripts/v2/` | v2 앱/대시보드 실험 코드 |
| `requirements-win.txt` | Windows 실행 환경 의존성 |
| `build_exe.spec`, `build_exe.bat` | Windows 실행 파일 빌드 설정 |

## 산출물 보관 정책

소스코드, 문서, 참고자료는 private repo에 포함합니다. `.venv/`, `dist/`, `.exe`, `.zip`은 Git 히스토리에 넣지 않고 GitHub Releases에 첨부합니다.

Release 첨부 대상:

- `dist/physical_analysis.exe`
- `전달용.zip`
- `physical_analysis_build_kit*.zip`

## 원본 템플릿 설명

# MVP 기획 워크스페이스 템플릿 (범용)

Claude Code로 MVP 기획 업무를 표준화해서 돌리기 위한 범용 워크스페이스 템플릿입니다. 아이디어 발굴부터 PRD까지 같은 프레임으로 진행할 수 있게 슬래시 명령(Skill), 서브에이전트(Agent), 프로젝트 규칙(CLAUDE.md)을 한 벌로 묶었습니다.

## 구성물 한 줄 요약

| 파일 | 역할 |
|------|------|
| `CLAUDE.md` | Claude Code가 세션 시작 시 읽는 프로젝트 규칙 (언어, 원칙, 저장 규칙) |
| `.claude/settings.json` | 권한 모드와 허용 명령 기본값 |
| `.claude/settings.local.json.example` | 프로젝트별 로컬 권한 예시 |
| `.claude/agents/idea-validator.md` | VC 시점 아이디어 평가 서브에이전트 |
| `.claude/agents/market-researcher.md` | 시장 규모·트렌드·규제 심층 조사 서브에이전트 |
| `.claude/skills/lean-canvas/SKILL.md` | `/lean-canvas` 린 캔버스 9블록 |
| `.claude/skills/validate-idea/SKILL.md` | `/validate-idea` 7차원 검증 + 판정 |
| `.claude/skills/competitor-analysis/SKILL.md` | `/competitor-analysis` 경쟁사 5~8개 분석 |
| `.claude/skills/persona/SKILL.md` | `/persona` 유저 페르소나 3~5명 |
| `.claude/skills/prd/SKILL.md` | `/prd` MVP PRD 작성 |
| `docs/progress.md` | 세션 간 진행 이력 누적 저장소 |
| `docs/사용법-가이드-usage.md` | 상세 사용법 (이 파일의 상위 버전) |
| `scripts/build-pdf.py` | 마크다운 → PDF 변환 스크립트 (한글 폰트 대응) |

## 30초 설치

```bash
# 1) 새 프로젝트 폴더에 템플릿 풀기
unzip mvp-workspace-template.zip -d my-project/
cd my-project/

# 2) Claude Code 실행
claude

# 3) 세션 안에서 CLAUDE.md 의 {{플레이스홀더}} 를 실제 값으로 치환하도록 요청
```

처음 실행한 Claude Code 세션에 아래처럼 던지면 됩니다.

```
CLAUDE.md 의 {{PROJECT_NAME}}, {{TARGET_MARKET}} 같은 플레이스홀더를
내 프로젝트에 맞게 바꿔줘. 내 프로젝트는 "AI 기반 반려동물 건강 기록 앱"이고,
타겟은 한국 30~40대 반려인이야.
```

## 표준 기획 흐름

다음 순서로 슬래시 명령을 돌리면 `docs/` 폴더에 산출물이 쌓입니다.

1. `/validate-idea <아이디어>` → `docs/검증-{날짜}-validation.md`
2. `/lean-canvas <아이디어>` → `docs/린캔버스-lean-canvas.md`
3. `/persona <제품 설명>` → `docs/페르소나-persona.md`
4. `/competitor-analysis <카테고리>` → `docs/경쟁사분석-competitors.md`
5. 시장 데이터가 더 필요하면 서브에이전트 `market-researcher` 호출
6. `/prd <제품명>` → `docs/mvp-prd.md`

`docs/progress.md` 는 세션 간 기억 역할을 합니다. 매 세션 끝에 한 줄씩 남기세요.

## 상세 설명서

첨부된 PDF `사용법-설명서-usage-guide.pdf` 를 참고하세요. 설치부터 실전 기획 흐름, 커스터마이징, 문제 해결까지 포함되어 있습니다.
