# MVP 기획 워크스페이스 템플릿 — 사용법 설명서

**버전**: v1.0
**작성일**: 2026-04-23
**대상**: Claude Code(클로드 코드)를 활용해 MVP 기획을 빠르게 돌리고 싶은 1인 창업자, 소규모 팀 PM, 비기술 배경 기획자

---

## 1. 이 템플릿이 무엇이고, 왜 필요한가

### 1.1 결론부터 (BLUF)

이 템플릿은 Claude Code를 "MVP 기획 도우미"로 고정 세팅해 주는 한 벌입니다. 압축 파일을 풀고 `claude` 를 실행하면, 같은 규칙·같은 산출물 양식으로 어떤 주제의 기획이든 굴릴 수 있습니다. 매번 프롬프트를 새로 짤 필요가 없어서, 아이디어 검증부터 PRD까지 걸리는 시간이 크게 줄어듭니다.

### 1.2 해결하려는 문제

Claude Code나 다른 AI 코딩 도구를 쓰다 보면 매번 같은 얘기를 반복하게 됩니다. "한국어로 답해", "수치와 출처를 넣어", "막연한 칭찬 금지" 같은 규칙이 세션마다 리셋됩니다. 또 린 캔버스, 페르소나, PRD처럼 반복적으로 쓰는 프레임워크를 그때그때 설명하는 것도 낭비입니다. 이 템플릿은 이런 반복 작업을 슬래시 명령(Skill)과 서브에이전트(Agent)로 고정해 둡니다.

### 1.3 누가 쓰면 좋은가

- 1인 또는 2~3인 스타트업 준비자
- 비기술 배경의 PO/PM으로서 제품 기획서나 PRD를 자주 만드는 사람
- Bolt, Lovable, v0 같은 AI 빌더에 바로 던질 수 있는 "정밀 스펙"이 필요한 사람
- 여러 아이디어를 동시에 검증하며 같은 기준으로 비교하고 싶은 사람

---

## 2. 사전 준비물

### 2.1 필수

- **Claude Code CLI**: `claude` 명령이 터미널에서 동작해야 합니다. 설치 안내는 [공식 문서](https://docs.anthropic.com/claude-code)를 참고하세요.
- **Anthropic API 키 또는 Claude 구독**: Claude Code를 쓰기 위한 인증.
- **터미널**: macOS/Linux의 기본 터미널, Windows에서는 WSL 권장.

### 2.2 선택 (PDF 변환 쓸 때만)

- Python 3.9+
- `markdown2`, `weasyprint` 파이썬 패키지
- 한글 폰트 (예: Noto Sans KR, Pretendard). 설치 명령은 6장 참고.

---

## 3. 설치와 초기 설정

### 3.1 압축 풀기

```bash
unzip mvp-workspace-template.zip -d my-new-project/
cd my-new-project/
```

풀고 나면 구조는 이렇습니다.

```
my-new-project/
├── CLAUDE.md                          # 프로젝트 규칙 (반드시 수정)
├── README.md                          # 간략 소개
├── .claude/
│   ├── settings.json                  # 권한 기본값
│   ├── settings.local.json.example    # 로컬 권한 예시
│   ├── agents/
│   │   ├── idea-validator.md
│   │   └── market-researcher.md
│   └── skills/
│       ├── lean-canvas/SKILL.md
│       ├── validate-idea/SKILL.md
│       ├── competitor-analysis/SKILL.md
│       ├── persona/SKILL.md
│       └── prd/SKILL.md
├── docs/
│   ├── progress.md                    # 세션 간 이력
│   └── 사용법-가이드-usage.md         # 이 문서의 원본
└── scripts/
    └── build-pdf.py                   # 마크다운 → PDF 변환
```

### 3.2 CLAUDE.md 플레이스홀더 치환

`CLAUDE.md` 상단에 `{{PROJECT_NAME}}` 같은 이중 중괄호 변수들이 있습니다. 에디터로 직접 바꿔도 되고, 첫 Claude Code 세션에서 Claude에게 시켜도 됩니다.

```text
CLAUDE.md 의 {{...}} 플레이스홀더를 아래 값으로 바꿔줘.
- PROJECT_NAME: 러닝 코스 공유 앱 "런메이트"
- ONE_LINER: 동네 러너들이 코스와 페이스를 공유하는 한국형 소셜 러닝 앱
- TARGET_MARKET: 한국 (수도권 우선)
- CUSTOMER_SEGMENT: 20~30대 도시 직장인 러너
- STAGE: 아이디어 검증
- USER_ROLE: 비개발 1인 창업자
- CODING_LEVEL: 없음
```

### 3.3 git 초기화 (선택)

기획 문서도 버전 관리하면 좋습니다.

```bash
git init
git add .
git commit -m "init: MVP 기획 워크스페이스 세팅"
```

`.gitignore` 에 `.claude/settings.local.json` 을 추가하면 로컬 권한 설정이 공유되지 않습니다.

### 3.4 Claude Code 실행

```bash
claude
```

첫 실행 시 Claude는 `CLAUDE.md`, `.claude/agents/*`, `.claude/skills/*` 를 모두 읽습니다. 응답 첫 줄에 🎯 이모지가 찍히면 규칙이 정상 로드된 것입니다.

---

## 4. 표준 기획 흐름

### 4.1 전체 그림

```
[아이디어]
    │
    ├─ /validate-idea  ── docs/검증-{날짜}-validation.md
    │       ↓ 빌드 판정이면 다음 단계
    ├─ /lean-canvas    ── docs/린캔버스-lean-canvas.md
    ├─ /persona        ── docs/페르소나-persona.md
    ├─ /competitor-analysis ── docs/경쟁사분석-competitors.md
    ├─ (필요 시) market-researcher 에이전트 ── docs/시장조사-{주제}-market.md
    └─ /prd            ── docs/mvp-prd.md  (AI 빌더용 프롬프트 포함)
```

### 4.2 단계별 호출 예시

**1단계 — 검증**

```text
/validate-idea "동네 러너들이 서로 러닝 코스를 공유하고 페이스를 맞춰
함께 뛸 사람을 찾는 앱"
```

출력: 점수 매트릭스, 차원별 분석, 🟢 빌드 / 🟡 피봇 / 🔴 포기 판정, 2주·50만원 내 검증 실험 3가지.

**2단계 — 린 캔버스**

```text
/lean-canvas "런메이트 — 동네 러너를 위한 소셜 러닝 앱"
```

출력: 9개 블록 표 + 검증이 필요한 상위 3가지 가정.

**3단계 — 페르소나**

```text
/persona "런메이트 앱의 메인 타겟은 20~30대 도시 직장인 러너"
```

출력: 3~5명의 한국식 페르소나 + 각자의 JTBD.

**4단계 — 경쟁사 분석**

```text
/competitor-analysis "한국 소셜 러닝 앱 카테고리"
```

출력: 5~8개 경쟁사 매트릭스, 포지셔닝 맵, 공격/회피/공백 영역.

**5단계 — 시장 심층 조사 (선택)**

```text
market-researcher 에이전트를 호출해서 한국 러닝 앱 시장 규모, 경쟁 구도,
규제 환경을 조사해줘.
```

출력: TAM/SAM/SOM, 주요 트렌드, 규제, 한국 특수 요인.

**6단계 — PRD 작성**

```text
/prd "런메이트 MVP"
```

출력: MoSCoW 기능 범위, 사용자 플로우, 기술 요구사항, KPI, AI 빌더용 영어 프롬프트.

### 4.3 세션 종료 시 루틴

```text
오늘 작업 내용을 progress.md 에 한 줄로 추가해줘.
```

---

## 5. 각 구성물 상세

### 5.1 CLAUDE.md (프로젝트 규칙)

Claude Code가 세션 시작 때 자동으로 읽는 파일. 여기에 적은 규칙은 이후 모든 응답에 적용됩니다. 주요 섹션:

- **응답 언어 규칙**: 한국어 고정, 번역투 금지.
- **기획 원칙**: 구체성, 가정/사실 분리, 건설적 도전, BLUF, 로컬 시장 우선.
- **파일 저장 규칙**: `docs/` 폴더, 한영 병기 파일명, 원화(₩) 표시.
- **카나리아**: 🎯 이모지로 컨텍스트 품질 점검.

### 5.2 서브에이전트 두 개

| 이름 | 모델 | 도구 | 용도 |
|------|------|------|------|
| `idea-validator` | opus | Read, Grep, Glob | 까다로운 VC 시점의 냉정 평가 |
| `market-researcher` | opus | Read, Grep, Glob, Bash, WebSearch, WebFetch | 시장 조사, 공개 자료 수집 |

서브에이전트는 메인 세션과 별도 컨텍스트로 돌며, 결과만 메인에 돌려줍니다. 긴 조사나 냉정한 평가가 필요할 때 호출하면 메인 세션의 컨텍스트 창을 아낄 수 있습니다.

### 5.3 슬래시 스킬 다섯 개

각 스킬은 `/<이름>` 으로 호출합니다. 출력 양식과 저장 위치가 고정되어 있어서 어떤 주제를 넣어도 동일한 구조로 산출물이 나옵니다.

---

## 6. PDF 변환 (선택)

`scripts/build-pdf.py` 는 마크다운 산출물을 보고서급 PDF로 바꿔 줍니다. 한글 폰트, 표, 코드 블록, 목차 없이도 깔끔한 인쇄본을 뽑을 수 있습니다.

### 6.1 의존성 설치

```bash
pip install markdown2 weasyprint
```

Ubuntu/WSL에서 한글이 깨지면 폰트 설치가 필요합니다.

```bash
sudo apt-get update
sudo apt-get install -y fonts-noto-cjk fonts-noto-cjk-extra
fc-cache -f
```

### 6.2 사용법

스크립트 상단의 `MD_PATH` 를 변환하려는 마크다운 경로로 바꾸고 실행합니다.

```bash
python3 scripts/build-pdf.py
```

HTML과 PDF가 같은 폴더에 생성됩니다.

---

## 7. 커스터마이징

### 7.1 언어 바꾸기

CLAUDE.md의 "응답 언어 규칙" 섹션을 고치면 됩니다. 영어로 진행하려면 "모든 응답은 영어로 작성한다"로 교체하세요. 슬래시 스킬 안의 "한국어로 작성" 문구도 바꿔야 합니다.

### 7.2 타겟 시장 바꾸기

CLAUDE.md의 `{{TARGET_MARKET}}` 을 바꾸면 대부분 반영됩니다. `market-researcher.md` 는 "한국 시장 전문 리서처" 문구가 박혀 있으니 다른 시장이 메인이라면 해당 줄을 직접 수정하세요.

### 7.3 스킬 추가

`.claude/skills/` 아래에 새 폴더를 만들고 `SKILL.md` 를 아래 형식으로 작성하면 `/새이름` 으로 호출됩니다.

```markdown
---
name: new-skill
description: (이 스킬이 언제 쓰여야 하는지 한 줄)
argument-hint: [사용자 입력 힌트]
---

# 새 스킬

(본문 프롬프트)

## 출력 규칙
- 한국어로 작성
- 결과를 `./docs/새결과.md` 로 저장
```

### 7.4 권한 기본값 조정

`settings.json` 의 `defaultMode` 를 `acceptEdits`(편집은 자동 승인, 쉘 실행만 물음) 대신 `plan`(계획만, 실행 금지)이나 `bypassPermissions`(전부 자동, 위험)로 바꿀 수 있습니다. 비기술 사용자는 기본값을 그대로 두는 걸 권장합니다.

---

## 8. 자주 생기는 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| 응답에 🎯 이모지가 안 보임 | 컨텍스트가 압축되었거나 CLAUDE.md를 못 읽음 | `/clear` 후 재시작. CLAUDE.md 파일이 프로젝트 루트에 있는지 확인 |
| `/lean-canvas` 가 인식 안 됨 | `.claude/skills/` 경로가 다름 | 프로젝트 루트에서 실행 중인지, 경로 철자 확인 |
| 서브에이전트가 인터넷 접근 못함 | `market-researcher` 권한 부족 | `.claude/settings.json` 또는 세션 허용 목록에 `WebSearch`, `WebFetch` 추가 |
| PDF에서 한글이 깨짐 | 시스템에 한글 폰트 없음 | `fonts-noto-cjk` 설치 후 `fc-cache -f` |
| 스킬 결과가 너무 일반적이다 | 입력이 짧음 | 아이디어·제품 설명을 3~5문장으로 상세히 넣기 |
| 중간에 컨텍스트가 꼬인다 | 한 세션에서 너무 많은 주제 진행 | 주제마다 `/clear` 로 세션을 끊고, `docs/progress.md` 로 이어서 |

---

## 9. 활용 팁

1. **한 주제 = 한 세션 원칙**. 아이디어 검증하던 세션에서 갑자기 PRD까지 가면 규칙이 흐릿해집니다. 단계마다 `/clear` 하세요.
2. **서브에이전트를 적극 활용**. 긴 시장 조사는 `market-researcher` 로 분리해야 메인 세션의 컨텍스트가 살아남습니다.
3. **산출물은 반드시 진본 확인**. Claude는 숫자를 그럴듯하게 만들어 냅니다. `[가정]`, `[추정]` 태그가 붙은 항목은 반드시 별도 검증하세요.
4. **progress.md는 한 줄 규칙**. 길게 적으면 아무도 안 읽습니다. "완료한 것 + 다음 할 것" 두 조각이면 충분합니다.
5. **PRD의 "Won't Have" 섹션을 아껴 쓰지 마세요**. MVP 스코프 폭주는 대부분 "안 만들 것"을 명시하지 않아서 생깁니다.

---

## 10. 라이선스와 면책

- 이 템플릿의 규칙·프롬프트는 자유롭게 복제·수정·상업적 활용이 가능합니다.
- Claude Code와 Anthropic의 이용 약관은 별도이며, 각자 확인해야 합니다.
- 산출물의 정확성·적합성은 사용자 책임입니다. 특히 시장 수치, 법률·규제 관련 내용은 반드시 원본 출처 확인을 권장합니다.
