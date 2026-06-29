# 데이터 모델 (data model)

작성: 2026-04-30
대상: physical_analysis 프로젝트 v0.6 데이터 흐름 재정의

---

## 1. 한 측정 세션 = (시계열 1개) + (설정 파일 1개)

한 환자가 한 가지 측정 상태(condition)에서 측정한 **한 세션**은 다음 두 파일로 구성된다:

| 파트 | 파일 패턴 | 역할 | 형식 |
| --- | --- | --- | --- |
| 시계열 (load 데이터) | `{이름}_{cond}_Calf.{txt,csv,xlsx}` | NIRS-VOT 실측 SmO2 시계열 | 3종 동일 구조 |
| 설정 파일 (config) | `{이름}_{cond}.xlsx` | 환자 메타·시간 구간·외부 결과 | xlsx 4 시트 |

`{cond}` ∈ {`HYPER`, `HYPO`, `NOR`} — 측정 상태(저산소·정상·과산소).

같은 폴더 안에 한 condition 당 이 두 파일이 짝으로 존재한다.

---

## 2. `_Calf` 시계열 파일

### 2.1 공통 컬럼 (3종 형식 모두 동일)

```
mm-dd, hh:mm:ss, SmO2 Live, SmO2 Averaged, THb, Lap, Session Ct
```

- 샘플링 ≈ 2 Hz (동일 timestamp 가 두 번 등장)
- `SmO2 Live` / `SmO2 Averaged` : 단위 %
- `THb` : 총 헤모글로빈 (단위 g/dL 추정)
- `Lap`, `Session Ct` : 디바이스 카운터

### 2.2 형식별 차이

- `.txt` / `.csv` : 헤더 2줄 (`SensorID:`, `Firmware Version:`) + 빈 줄 + 컬럼명 + 데이터.
  구분자는 `,` (us-ascii) 또는 `\t` (cp949, 한국어 날짜) 두 가지 변형 존재 → 자동 감지.
- `.xlsx` : 동일 헤더가 셀 그대로 들어있음. 4행이 컬럼명, 5행부터 데이터.

### 2.3 적용

NIRS-VOT 분석은 이 시계열을 입력으로 받는다.
HRV 분석은 이 시계열만으로는 **불가능** (RR 간격이 없음).

---

## 3. 설정 파일 (xlsx 4 시트)

### 3.1 `Info,GXT` 시트 — 환자 메타

1행 헤더, 2행 데이터 (한 명).

| 키 | 의미 |
| --- | --- |
| `ID(Protocol)` | 프로토콜 ID (예: `JH_08`) |
| `Name` | 이름 |
| `D.O.B`, `Age`, `Gender`, `Weight(kg)`, `Height(cm)` | 신상 |
| `Wattmax`, `VO2max`, `W/kg`, `FTP` | GXT 결과 |
| `AT(VT1)`, `RC(VT2)` | 환기 역치 |
| `Wattmax(90%)`, `Wattmax(40%)`, `Wattmax(110%)` | 운동 강도 처방 (90%/40%/110% Wattmax) |
| `안장 높이`, `안정시 심박수` | 자전거 셋팅 / 안정 HR |

### 3.2 `Timepoint` 시트 — **시간 구간 정의 (가장 중요)**

#### 구버전 형식 (v0.6 까지 — 자동 감지·읽기 가능)

```
                NIRS_VOT                    HRV
            Baseline   Recovery2     Baseline   Recovery2
Start(Occ)   14:01      15:07         14:07      15:13
Fin(Def)     14:06      15:12         14:17      15:23
```

NIRS_VOT 가 (Baseline, Recovery2) 2개 고정, lead/tail 은 코드 상수(60s/180s).

#### 신버전 long-table (v0.7 — 사용자 자유 추가)

```
NIRS_VOT
Name        Start       End         Lead   Tail
Baseline    14:01:00    14:06:00    60     180
Recovery2   15:07:00    15:12:00    60     180
Recovery5   15:30:00    15:35:00    90     240    ← 임의 추가 가능

HRV
Name        Start       End
Baseline    14:07:00    14:17:00
Recovery2   15:13:00    15:23:00
```

NIRS_VOT 는 임의 개수, 각 row 가 자체 lead/tail. 'Name' 컬럼 라벨 감지 시 신버전으로 파싱.

- **NIRS_VOT timepoint** (occlusion 측정):
  - `Start` = 커프 팽창 시각 → `Anchor.inflate`
  - `End` = 커프 해제 시각 → `Anchor.deflate`
  - `Lead` (default 60s) — inflate **이전**의 baseline 측정 구간 길이.  → `Anchor.start = inflate − Lead`
  - `Tail` (default 180s) — deflate **이후**의 reperfusion 관찰 구간.  → `Anchor.end = deflate + Tail`
  - Name 은 자유 입력. `Baseline` / `Recovery2` 는 Coded Data 의 ground truth (`VOT_Baseline` / `VOT_Post`) 와 자동 매칭, 그 외 이름은 GT 비교 빈 값.

- **HRV 그룹** (안정 측정):
  - `Start(Occ)` / `Fin(Def)` (열 이름은 같으나 의미 다름) = HRV 측정 시작/종료 시각.
  - 보통 10분 구간.

- **운동 구간** (GXT 후속 운동 프로토콜):
  - `Ex1 start` / `Ex1 Fin` / `Ex2 start` / `Ex2 Fin` : 두 차례 고강도 인터벌.
  - `TTE_Maintenance_rate` : 목표 와트 유지율 (%).
  - `TTE1` / `TTE2` (mm:ss) : Time To Exhaustion 1·2회차.

### 3.3 `SpO2,BP,TQR,La` 시트 — 시점별 측정값

행: `Baseline`, `R1 30s`, `R1 150s`, `R1 270s`, `R2 30s`, `R2 150s`, `R2 270s`, `R2 600s`, `R2 900s`, `R2 1200s` (운동 후 회복 시점).

열 그룹: `BP` (수축기/이완기), `SpO2` (%), `TQR` (자각피로도, 6-20), `La` (lactate, mmol/L) — 일부 시점만 lactate 측정.

### 3.4 `Coded Data` 시트 — **종합 결과 (외부 ground truth)**

행 = (subject × condition × timepoint), 열 = 측정 메타 + 모든 분석 결과.

가장 중요한 행:

| 행 | 들어있는 값 | 우리 분석과의 관계 |
| --- | --- | --- |
| `Baseline`/`R1_30s`/.../`R2_1200s` | SBP/DBP/SpO2/TQR/La/HR | 시점별 raw 측정값 |
| `HRR_Summary_S1`, `HRR_Summary_S2` | HR / HR_End / HRR_60s/120s/300s | 운동 후 심박 회복 |
| `VOT_Baseline`, `VOT_Post` | Calf_SmO2_Base/Min/Peak / VOT_Slope1_30_150 / VOT_Slope2_0_10 / VOT_T50 / AUC_3min | **NIRS-VOT 검증 ground truth** |
| `R1_Summary`, `R2_Summary` | TTE / TTE_Maintenance_rate / Thigh_Time_to_Base / Thigh_Time_to_Half / Thigh_SmO2_Base/Min/Peak | 허벅지(Thigh) NIRS 결과 (현재 미구현) |
| `HRV_Baseline`, `HRV_Post` | HRV_SDNN / HRV_RMSSD / HRV_LF / HRV_HF / HRV_LF/HF | **HRV 검증 ground truth** |

---

## 4. 변경 영향 (현 코드 → v0.6)

| 항목 | 현재 (v0.5) | 변경 후 (v0.6) |
| --- | --- | --- |
| NIRS 시계열 입력 | `.txt`, `.xlsx` | + `.csv` 추가 (3종) |
| Anchor 시간 | `nirs_vot/anchors.py` 하드코딩 | 설정 xlsx `Timepoint` 시트에서 동적 로드. 하드코딩은 fallback 으로만. |
| HRV 입력 | Kubios export CSV (RR + 메타) | _Calf 데이터에는 RR 가 없음 → 옵션 (α) 또는 (β) 결정 필요 (아래) |
| 검증 ground truth | Kubios CSV 의 metrics dict | 설정 xlsx `Coded Data` 의 `VOT_*` / `HRV_*` 컬럼 |
| GUI 데이터 단위 | HRV CSV 1개 + NIRS 폴더 | (시계열 + 설정 xlsx) 한 쌍 = 한 condition |

### 4.1 HRV 처리 옵션

**(α) HRV 분석 폐기·외부 결과 표시** — 추천 (확정 전 기본값)
- `Coded Data` 의 `HRV_Baseline` / `HRV_Post` 행에서 `HRV_SDNN/RMSSD/LF/HF/LF·HF` 5개 값을 카드로 표시.
- HRV 탭은 "외부 분석 결과 뷰어" 로 단순화.
- `scripts/hrv_analysis/` 코드는 보존 (GUI 와 분리).
- 장점: _Calf 데이터만으로 일관, 즉시 동작.
- 단점: 시간/주파수/비선형 그래프(Poincaré, PSD, DFA) 가 사라짐.

**(β) HRV 분석 유지·RR 입력 별도 추가**
- 같은 측정 세션에 RR/ECG 파일을 추가로 받음 (예: `이찬민_HYPER_RR.csv`).
- 현재 `hrv_analysis/` 엔진 그대로 RR 입력에 적용.
- 장점: 모든 HRV 그래프·지표 보존.
- 단점: 새 입력 형식·로더·스펙 필요. _Calf 와 별도 흐름.

**(γ) 하이브리드** — α 기본 + β 수동 import
- 기본 화면은 α (외부 결과 표시).
- 사용자가 "RR import" 메뉴로 별도 RR CSV 를 로드하면 β 모드 활성화 → Ours vs ground truth 비교 테이블이 채워짐.

→ **결정 보류**. 사용자 확정 전까지 (α) 로 구현하고, (β)·(γ) 로의 확장이 가능하도록 모듈 분리를 유지한다.

---

## 5. 모듈 매핑

```
scripts/
├── nirs_vot/
│   ├── loader.py          ← .txt / .csv / .xlsx 모두 처리 (현재 .csv 미지원)
│   ├── preprocess.py      ← 변경 없음
│   ├── anchors.py         ← Anchor 데이터클래스 + Timepoint→Anchor 변환 함수 추가
│   └── metrics.py         ← 변경 없음
│
├── config_loader.py       ← 신규: 설정 xlsx 4 시트를 SessionConfig 로 파싱
│
├── hrv_analysis/          ← 보존 (GUI 와 분리, β 옵션 활성화 시 다시 연결)
│
└── nirs_vot_gui/
    ├── app.py             ← 파일 로드 흐름 변경, ground truth 출처 변경
    ├── tabs/
    │   ├── nirs_vot_tab.py    ← (시계열 + 설정 xlsx) 쌍을 받음
    │   └── hrv_*.py           ← α: 외부 결과 카드 뷰로 단순화
    └── widgets/
        ├── data_browser.py     ← 트리: 폴더 → condition (시계열+설정 자동 페어링)
        └── compare_table.py    ← 비교 기준값 출처: Kubios → Coded Data
```

---

## 6. 임시 의사결정 요약

- **NIRS 시계열 .csv 지원**: 즉시 추가 (`.txt` 와 동일 파서).
- **anchor 동적화**: 설정 xlsx 가 있으면 우선, 없으면 하드코딩 fallback.
- **검증 ground truth**: 설정 xlsx `Coded Data` 의 `VOT_*` / `HRV_*` 로 통합.
- **HRV 시각화**: α 가정으로 카드 뷰 + Time/Freq/Nonlinear 탭은 "데이터 없음" 안내. 사용자 확정 후 β/γ 로 확장.
