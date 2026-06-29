"""설정 xlsx 파서 — 한 measurement session 의 메타·구간·외부 결과를 로드.

설정 파일 패턴: ``{이름}_{cond}.xlsx``  (e.g., 이찬민_HYPER.xlsx)

3 시트 구조 (자세한 내용은 docs/데이터모델-data-model.md):

* ``Info,GXT``           — 환자 메타 1행
* ``Timepoint``          — NIRS_VOT / HRV / 운동 구간 시각
* ``Coded Data``         — 시점별 종합 결과 (외부 ground truth)

(원 xlsx 의 ``SpO2,BP,TQR,La`` 시트는 분석에서 사용되지 않아 파싱 생략.)

반환 객체 ``SessionConfig`` 는 GUI 와 분석 코드 양쪽에서 사용한다.

* `subject_info`  — `Info,GXT` 한 행을 dict 로
* `timepoints`    — { 'NIRS_VOT': list[Timepoint],     # 이름·구간·lead·tail (사용자 정의)
                      'HRV':      dict[str, TimeWindow],  # Baseline/Recovery2 고정 (display)
                      'exercise': dict — Ex1/Ex2 + TTE 메타 }
                  - 시각은 datetime.time, 단순 시간만 (날짜는 _Calf 데이터에서 결정).
* `coded_data`    — `Coded Data` 시트 (DataFrame)
* `vot_truth`     — VOT_Baseline / VOT_Post 행에서 추출한 NIRS-VOT 검증 dict
* `hrv_truth`     — HRV_Baseline / HRV_Post 행에서 추출한 HRV 검증 dict (HrvParameterPanel 사용)

v0.7 (2026-05) 부터 NIRS_VOT timepoints 는 list 기반 — 사용자가 자유롭게 추가/삭제 가능.
``Timepoint`` 시트의 두 가지 형식을 모두 읽는다:
  - 구버전: R0~R3 grid (NIRS_VOT/HRV 가로 2 section, 각 section 안에 Baseline/Recovery2 2 칸)
  - 신버전: 'NIRS_VOT' 헤더 행 다음 (Name | Start | End | Lead | Tail) long-table
신버전이 감지되면 우선 사용. 둘 다 없으면 빈 list.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


# ─────────────────────────────────────────────────────────────
#  데이터클래스
# ─────────────────────────────────────────────────────────────
_DEFAULT_LEAD_SEC = 60     # NIRS-VOT baseline lead (커프 팽창 1분 전)
_DEFAULT_TAIL_SEC = 180    # NIRS-VOT reperfusion tail (커프 해제 3분 후)


@dataclass
class TimeWindow:
    """한 측정 구간 (단순 시각, 날짜 없음). HRV / Exercise 에서 사용."""
    start: dt.time
    end: dt.time

    def to_clock_strs(self) -> tuple[str, str]:
        """('HH:MM:SS', 'HH:MM:SS') 튜플 — Anchor 와 호환."""
        return _t2s(self.start), _t2s(self.end)


@dataclass
class Timepoint:
    """NIRS_VOT 한 구간의 분석 단위 — 이름·시각·lead·tail 묶음.

    사용자가 자유롭게 추가/삭제 가능. anchor 4점은 lead·tail 적용해서 산출:
      - start   = inflate − lead
      - inflate = Timepoint.start (= xlsx Start(Occ))
      - deflate = Timepoint.end   (= xlsx Fin(Def))
      - end     = deflate + tail
    """
    name: str
    start: dt.time
    end: dt.time
    lead: int = _DEFAULT_LEAD_SEC
    tail: int = _DEFAULT_TAIL_SEC

    def to_window(self) -> "TimeWindow":
        """기존 TimeWindow API 와 호환되는 (start, end) 묶음."""
        return TimeWindow(self.start, self.end)


@dataclass
class SessionConfig:
    """한 condition 설정 파일의 모든 정보."""
    file_path: Path
    condition: str  # 파일명에서 추정 (HYPER/HYPO/NOR)
    subject_info: dict = field(default_factory=dict)
    timepoints: dict = field(default_factory=dict)
    coded_data: pd.DataFrame | None = None
    vot_truth: dict = field(default_factory=dict)   # NIRS-VOT ground truth
    hrv_truth: dict = field(default_factory=dict)   # HRV ground truth

    # ─── 편의 접근자 ────────────────────────────
    def nirs_timepoints(self) -> list["Timepoint"]:
        """NIRS-VOT timepoint 리스트 (이름 순서 보존). 없으면 빈 리스트."""
        return self.timepoints.get("NIRS_VOT", []) or []

    def nirs_timepoint(self, name: str) -> "Timepoint | None":
        """이름으로 timepoint 단건 조회. 없으면 None."""
        for tp in self.nirs_timepoints():
            if tp.name == name:
                return tp
        return None

    def nirs_vot_window(self, session: str) -> TimeWindow | None:
        """구버전 호환: 이름으로 (start, end) TimeWindow 반환."""
        tp = self.nirs_timepoint(session)
        return tp.to_window() if tp is not None else None

    def hrv_window(self, session: str) -> TimeWindow | None:
        """session ∈ {'Baseline', 'Recovery2'} 의 HRV 구간 (display 전용)."""
        return self.timepoints.get("HRV", {}).get(session)

    def exercise(self) -> dict:
        return self.timepoints.get("exercise", {})


# ─────────────────────────────────────────────────────────────
#  유틸
# ─────────────────────────────────────────────────────────────
def _t2s(t) -> str:
    """datetime.time → 'HH:MM:SS'."""
    if t is None:
        return ""
    if isinstance(t, dt.time):
        return f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}"
    if isinstance(t, dt.datetime):
        return f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}"
    return str(t)


def _coerce_time(v) -> dt.time | None:
    """xlsx 셀 값을 datetime.time 으로. None / 잘못된 값은 None."""
    if v is None:
        return None
    if isinstance(v, dt.time) and not isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.datetime):
        return v.time()
    if isinstance(v, str):
        # 'HH:MM' / 'HH:MM:SS'
        try:
            parts = [int(p) for p in v.strip().split(":")]
            if len(parts) == 2:
                return dt.time(parts[0], parts[1])
            if len(parts) == 3:
                return dt.time(parts[0], parts[1], parts[2])
        except ValueError:
            return None
    return None


def _condition_from_name(path: Path) -> str:
    """파일명 stem 에서 condition 추정. 못 찾으면 빈 문자열."""
    stem = path.stem
    for cond in ("HYPER", "HYPO", "NOR"):
        # 단순 substring 매칭 (HYPER 가 NOR 보다 먼저). 'HYPO' 가 'HYPER' 의 부분이 아니므로 안전.
        if cond in stem:
            return cond
    return ""


# ─────────────────────────────────────────────────────────────
#  시트별 파서
# ─────────────────────────────────────────────────────────────
def _parse_info_gxt(rows: list[tuple]) -> dict:
    """1행 헤더, 2행 데이터. dict 로 반환."""
    if len(rows) < 2:
        return {}
    headers = [str(c).strip() if c is not None else "" for c in rows[0]]
    values = list(rows[1])
    out: dict = {}
    for h, v in zip(headers, values):
        if not h:
            continue
        out[h] = v
    return out


def _parse_timepoint(rows: list[tuple]) -> dict:
    """Timepoint 시트 → {'NIRS_VOT': list[Timepoint], 'HRV': dict, 'exercise': dict}.

    두 형식을 모두 읽음 — 신버전 long-table 우선, 없으면 구버전 grid.

    구버전 grid (R0~R3):
        R0: (None, 'NIRS_VOT', None, 'HRV', None, None, None)
        R1: (None, 'Baseline', 'Recovery2', 'Baseline', 'Recovery2', None, None)
        R2: ('Start(Occ)', t, t, t, t, None, None)
        R3: ('Fin(Def)',   t, t, t, t, None, None)

    신버전 long-table (R0 어딘가에 'NIRS_VOT' 헤더 후 다음 행이 컬럼 라벨):
        Rk:   ('NIRS_VOT', None, None, None, None)
        Rk+1: ('Name', 'Start', 'End', 'Lead', 'Tail')
        Rk+2: ('Baseline',  t, t, 60,  180)
        Rk+3: ('Recovery2', t, t, 60,  180)
        Rk+4: ('Recovery5', t, t, 90,  240)  ← 자유 추가
        ...
    'HRV' 헤더가 등장하면 그 이후 행은 HRV section 으로 분기.

    Exercise / TTE 블록 (R6~R8) 위치는 두 형식 공통.
    """
    out: dict = {"NIRS_VOT": [], "HRV": {}, "exercise": {}}

    def cell(r: int, c: int):
        if r < 0 or r >= len(rows):
            return None
        if c < 0 or c >= len(rows[r]):
            return None
        return rows[r][c]

    # 신버전 long-table 감지 — 'Name' 컬럼 라벨이 있으면 신버전
    new_format = _detect_long_table(rows)
    if new_format:
        out["NIRS_VOT"] = _parse_long_table(rows, "NIRS_VOT")
        # HRV 도 long-table 일 수 있음 (lead/tail 컬럼은 무시 — display)
        hrv_list = _parse_long_table(rows, "HRV")
        out["HRV"] = {tp.name: TimeWindow(tp.start, tp.end) for tp in hrv_list}
    else:
        # 구버전 grid — NIRS_VOT 컬럼 1·2, HRV 컬럼 3·4
        nv_b_start = _coerce_time(cell(2, 1))
        nv_b_end   = _coerce_time(cell(3, 1))
        nv_r_start = _coerce_time(cell(2, 2))
        nv_r_end   = _coerce_time(cell(3, 2))
        hv_b_start = _coerce_time(cell(2, 3))
        hv_b_end   = _coerce_time(cell(3, 3))
        hv_r_start = _coerce_time(cell(2, 4))
        hv_r_end   = _coerce_time(cell(3, 4))

        if nv_b_start and nv_b_end:
            out["NIRS_VOT"].append(
                Timepoint("Baseline", nv_b_start, nv_b_end,
                          lead=_DEFAULT_LEAD_SEC, tail=_DEFAULT_TAIL_SEC)
            )
        if nv_r_start and nv_r_end:
            out["NIRS_VOT"].append(
                Timepoint("Recovery2", nv_r_start, nv_r_end,
                          lead=_DEFAULT_LEAD_SEC, tail=_DEFAULT_TAIL_SEC)
            )
        if hv_b_start and hv_b_end:
            out["HRV"]["Baseline"] = TimeWindow(hv_b_start, hv_b_end)
        if hv_r_start and hv_r_end:
            out["HRV"]["Recovery2"] = TimeWindow(hv_r_start, hv_r_end)

    # 운동 구간 (R6/R7 = 'Time' 행, R8 = TTE 행) — 두 형식 공통
    ex1_start = _coerce_time(cell(7, 1))
    ex1_end   = _coerce_time(cell(7, 2))
    ex2_start = _coerce_time(cell(7, 3))
    ex2_end   = _coerce_time(cell(7, 4))
    if ex1_start and ex1_end:
        out["exercise"]["Ex1"] = TimeWindow(ex1_start, ex1_end)
    if ex2_start and ex2_end:
        out["exercise"]["Ex2"] = TimeWindow(ex2_start, ex2_end)

    tte1 = _coerce_time(cell(8, 2))
    tte2 = _coerce_time(cell(8, 4))
    if tte1:
        out["exercise"]["TTE1"] = tte1
    if tte2:
        out["exercise"]["TTE2"] = tte2

    # TTE_Maintenance_rate (열 5 또는 6 — 시트마다 미세히 다름)
    maint = cell(8, 5)
    if maint is None:
        maint = cell(7, 6)
    if isinstance(maint, (int, float)):
        out["exercise"]["TTE_maintenance_rate"] = float(maint)

    return out


def _detect_long_table(rows: list[tuple]) -> bool:
    """Timepoint 시트 상단에 'Name' 컬럼 라벨이 보이면 신버전 long-table 로 판정."""
    for r in rows[:6]:
        for c in r:
            if c is None:
                continue
            if str(c).strip().lower() == "name":
                return True
    return False


def _parse_long_table(rows: list[tuple], section: str) -> list[Timepoint]:
    """``section`` 이름의 헤더 행을 찾아 그 다음 컬럼 라벨 행 → 데이터 행들을 Timepoint 리스트로.

    section 헤더 행 = 첫 컬럼이 ``section`` 인 행. 이후 컬럼 라벨 행은
    'Name' / 'Start' / 'End' / 'Lead' / 'Tail' 의 순서이며, 데이터 행은
    Name 셀이 비어 있거나 다음 section 헤더 (e.g. 'HRV', 'Exercise') 가 나올 때까지.
    Lead / Tail 셀이 비면 default (60 / 180) 사용.
    """
    section_lower = section.strip().lower()
    other_sections = {"nirs_vot", "hrv", "exercise"} - {section_lower}

    # section 헤더 행 인덱스 찾기 (첫 컬럼 또는 어느 컬럼이든)
    header_row = -1
    for i, r in enumerate(rows):
        for c in r:
            if c is None:
                continue
            if str(c).strip().lower() == section_lower:
                header_row = i
                break
        if header_row >= 0:
            break
    if header_row < 0:
        return []

    # 컬럼 라벨 행 — section 헤더 바로 다음 또는 그 다음 (한 줄 띄어 있을 수 있음)
    label_row = -1
    for i in range(header_row + 1, min(header_row + 3, len(rows))):
        if i >= len(rows):
            break
        r = rows[i]
        if any(c is not None and str(c).strip().lower() == "name" for c in r):
            label_row = i
            break
    if label_row < 0:
        return []

    # 컬럼 인덱스 매핑 (Name / Start / End / Lead / Tail)
    label_cells = [str(c).strip().lower() if c is not None else "" for c in rows[label_row]]
    col_idx = {}
    for key in ("name", "start", "end", "lead", "tail"):
        for ci, label in enumerate(label_cells):
            if label == key:
                col_idx[key] = ci
                break
    if "name" not in col_idx or "start" not in col_idx or "end" not in col_idx:
        return []

    out: list[Timepoint] = []
    for i in range(label_row + 1, len(rows)):
        r = rows[i]
        # 다른 section 헤더가 나오면 종료
        first_nonempty = next(
            (str(c).strip() for c in r if c is not None and str(c).strip()), ""
        )
        if first_nonempty.lower() in other_sections:
            break
        name_cell = r[col_idx["name"]] if col_idx["name"] < len(r) else None
        if name_cell is None or not str(name_cell).strip():
            # 빈 행 — 다음 행이 다른 section 일 수도 있어 skip 만 하고 계속
            continue
        start_t = _coerce_time(r[col_idx["start"]] if col_idx["start"] < len(r) else None)
        end_t   = _coerce_time(r[col_idx["end"]]   if col_idx["end"]   < len(r) else None)
        if start_t is None or end_t is None:
            continue
        lead = _coerce_int(r[col_idx["lead"]] if "lead" in col_idx and col_idx["lead"] < len(r) else None,
                           default=_DEFAULT_LEAD_SEC)
        tail = _coerce_int(r[col_idx["tail"]] if "tail" in col_idx and col_idx["tail"] < len(r) else None,
                           default=_DEFAULT_TAIL_SEC)
        out.append(Timepoint(str(name_cell).strip(), start_t, end_t, lead=lead, tail=tail))
    return out


def _coerce_int(v, *, default: int) -> int:
    if v is None:
        return default
    try:
        f = float(v)
        if f != f:  # NaN
            return default
        return max(0, int(round(f)))
    except (TypeError, ValueError):
        return default


def _parse_coded_data(rows: list[tuple]) -> pd.DataFrame:
    """Coded Data 시트 → DataFrame (R1 헤더, R2~ 데이터)."""
    if not rows:
        return pd.DataFrame()
    headers = [str(c).strip() if c is not None else f"_c{i}"
               for i, c in enumerate(rows[0])]
    body = [list(r) + [None] * (len(headers) - len(r)) if len(r) < len(headers)
            else list(r[: len(headers)]) for r in rows[1:]]
    df = pd.DataFrame(body, columns=headers)
    return df


# ─────────────────────────────────────────────────────────────
#  ground-truth 추출
# ─────────────────────────────────────────────────────────────
_VOT_TRUTH_COLS = [
    "Calf_SmO2_Base", "Calf_SmO2_Min", "Calf_SmO2_Peak",
    "VOT_Slope1_30_150", "VOT_Slope2_0_10", "VOT_T50", "AUC_3min",
]

_HRV_TRUTH_COLS = [
    "HRV_SDNN", "HRV_RMSSD", "HRV_LF", "HRV_HF", "HRV_LF/HF",
]


def _row_dict(coded: pd.DataFrame, timepoint: str, columns: list[str]) -> dict:
    """coded_data 에서 Timepoint == timepoint 인 행을 찾아 columns 만 dict 로."""
    if coded is None or coded.empty or "Timepoint" not in coded.columns:
        return {}
    mask = coded["Timepoint"].astype(str).str.strip() == timepoint
    if not mask.any():
        return {}
    row = coded.loc[mask].iloc[0]
    out: dict = {}
    for col in columns:
        if col not in coded.columns:
            continue
        v = row[col]
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        try:
            out[col] = float(v)
        except (TypeError, ValueError):
            out[col] = v
    return out


def _extract_vot_truth(coded: pd.DataFrame) -> dict:
    """VOT_Baseline / VOT_Post 두 행의 ground truth 묶음."""
    return {
        "Baseline": _row_dict(coded, "VOT_Baseline", _VOT_TRUTH_COLS),
        "Post":     _row_dict(coded, "VOT_Post",     _VOT_TRUTH_COLS),
    }


def _extract_hrv_truth(coded: pd.DataFrame) -> dict:
    return {
        "Baseline": _row_dict(coded, "HRV_Baseline", _HRV_TRUTH_COLS),
        "Post":     _row_dict(coded, "HRV_Post",     _HRV_TRUTH_COLS),
    }


# ─────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────
def load_session_config(path: str | Path) -> SessionConfig:
    """설정 xlsx 파일을 SessionConfig 로 파싱."""
    import openpyxl

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    cfg = SessionConfig(file_path=path, condition=_condition_from_name(path))

    sheet_map: dict[str, list[tuple]] = {}
    for sname in wb.sheetnames:
        ws = wb[sname]
        sheet_map[sname] = list(ws.iter_rows(values_only=True))
    wb.close()

    if "Info,GXT" in sheet_map:
        cfg.subject_info = _parse_info_gxt(sheet_map["Info,GXT"])
    if "Timepoint" in sheet_map:
        cfg.timepoints = _parse_timepoint(sheet_map["Timepoint"])
    if "Coded Data" in sheet_map:
        cfg.coded_data = _parse_coded_data(sheet_map["Coded Data"])
        cfg.vot_truth = _extract_vot_truth(cfg.coded_data)
        cfg.hrv_truth = _extract_hrv_truth(cfg.coded_data)

    return cfg


# ─────────────────────────────────────────────────────────────
#  Calf 시계열 ↔ 설정 페어링
# ─────────────────────────────────────────────────────────────
_CALF_EXTS = (".txt", ".csv", ".xlsx", ".xlsm")


def find_calf_for_config(config_path: str | Path) -> Path | None:
    """`{stem}.xlsx` 옆의 `{stem}_Calf.{txt,csv,xlsx}` 를 찾는다.

    여러 형식이 있으면 우선순위: .csv > .txt > .xlsx (가장 단순한 형식 우선).
    """
    config_path = Path(config_path)
    folder = config_path.parent
    stem = config_path.stem  # 예: '이찬민_HYPER'
    candidates: list[Path] = []
    for ext in (".csv", ".txt", ".xlsx", ".xlsm"):
        c = folder / f"{stem}_Calf{ext}"
        if c.exists():
            candidates.append(c)
    return candidates[0] if candidates else None


def find_config_for_calf(calf_path: str | Path) -> Path | None:
    """`{stem}_Calf.{ext}` 옆의 `{stem}.xlsx` 를 찾는다.

    `_Calf` / `_calf` 접미사 대소문자를 가리지 않는다.
    """
    calf_path = Path(calf_path)
    folder = calf_path.parent
    stem = calf_path.stem  # 예: '이찬민_HYPER_Calf'
    if stem.lower().endswith("_calf"):
        config_stem = stem[: -len("_calf")]
    else:
        config_stem = stem
    for ext in (".xlsx", ".xlsm"):
        c = folder / f"{config_stem}{ext}"
        if c.exists():
            return c
    return None


def discover_sessions(folder: str | Path) -> list[tuple[Path, Path | None]]:
    """폴더에서 (config xlsx, calf 시계열 path) 쌍 목록을 수집.

    설정 xlsx 가 기준 — 옆에 `_Calf` 시계열이 있으면 함께, 없으면 (xlsx, None).
    `_Calf` 가 들어간 xlsx 는 시계열로 분류되어 설정에서 제외.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []
    out: list[tuple[Path, Path | None]] = []
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() not in (".xlsx", ".xlsm"):
            continue
        if "_Calf" in p.stem:
            continue
        calf = find_calf_for_config(p)
        out.append((p, calf))
    return out
