"""_Calf 시계열 로더 (.txt / .csv / .xlsx 통합).

세 형식 모두 동일한 컬럼 구조를 가진다:
    mm-dd, hh:mm:ss, SmO2 Live, SmO2 Averaged, THb, Lap, Session Ct

`.txt` / `.csv` 변형:
    (A) 콤마 구분 + us-ascii  (예: NOR, HYPER)
        SensorID: 5498,
        Firmware Version: 1.5.5,
                                        (빈 줄)
        mm-dd,hh:mm:ss,SmO2 Live,...
        2-3,13:1:24,62,62,13.31,10,251,

    (B) 탭 구분 + cp949 + 한국어 날짜  (예: HYPO)
        SensorID: 5498<TAB><TAB>...
        Firmware Version: 1.5.5<TAB>...
                                        (빈 줄, 탭만)
        mm-dd<TAB>hh:mm:ss<TAB>SmO2 Live<TAB>...
        02월 24일<TAB>12:06:26<TAB>69<TAB>...

`.xlsx` 변형:
    셀 그대로:
        A1: 'SensorID: 5498'
        A2: 'Firmware Version: 1.5.5'
        A3: (빈 행)
        A4..G4: 'mm-dd' 'hh:mm:ss' 'SmO2 Live' ...
        A5: datetime, B5: time(...), C5: 62 ...

확장자에 따라 자동 분기.
샘플링 레이트: 약 2 Hz (동일 timestamp 가 연속 2회 등장).
"""

from __future__ import annotations
import re
from pathlib import Path

import pandas as pd

DEFAULT_YEAR = 2025

# "02월 24일", "2-24", "02-24", "2/24" 모두 매칭
_DATE_RE = re.compile(r"(\d{1,2})\s*[월\-/]\s*(\d{1,2})\s*일?")

_TEXT_EXTS = {".txt", ".csv"}
_XLSX_EXTS = {".xlsx", ".xlsm"}

_RENAME_MAP = {
    "mm-dd": "mm_dd",
    "Date": "mm_dd",
    "hh:mm:ss": "time_str",
    "Time": "time_str",
    "SmO2 Live": "SmO2_live",
    "SmO2 Averaged": "SmO2_avg",
    "THb": "THb",
    "Lap": "Lap",
    "Session Ct": "Session_Ct",
}

_DATE_HEADER_TOKENS = ("mm-dd", "Date")

_OUTPUT_COLS = ["datetime_raw", "SmO2_live", "SmO2_avg", "THb", "Lap", "Session_Ct"]
_REQUIRED_COLS = ("mm_dd", "time_str", "SmO2_live")
_OPTIONAL_COLS = ("SmO2_avg", "THb", "Lap", "Session_Ct")


# ─────────────────────────────────────────────────────────────
#  공통 유틸
# ─────────────────────────────────────────────────────────────
def _normalize_mmdd(raw) -> str | None:
    """다양한 날짜 표기를 'MM-DD' (zero-padded)로 통일.

    pandas.Timestamp / datetime / str 어떤 것이라도 받는다.
    """
    if raw is None:
        return None
    if hasattr(raw, "month") and hasattr(raw, "day"):
        return f"{int(raw.month):02d}-{int(raw.day):02d}"
    m = _DATE_RE.search(str(raw))
    if not m:
        return None
    return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"


def _normalize_time_str(raw) -> str | None:
    """시간 표기를 'HH:MM:SS'로 통일. datetime.time / str 모두 처리."""
    if raw is None:
        return None
    if hasattr(raw, "hour") and hasattr(raw, "minute"):
        sec = int(getattr(raw, "second", 0) or 0)
        return f"{int(raw.hour):02d}:{int(raw.minute):02d}:{sec:02d}"
    s = str(raw).strip()
    parts = s.split(":")
    if len(parts) == 3 and all(p.strip().isdigit() for p in parts):
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
    return s


def _finalize_dataframe(df: pd.DataFrame, year: int, source_meta: dict) -> pd.DataFrame:
    """rename / dtype / datetime 변환 / 결측 제거 — 세 입력 경로 공통 후처리."""
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"필수 컬럼 누락: {missing}  (실제 컬럼: {list(df.columns)})"
        )
    for col in _OPTIONAL_COLS:
        if col not in df.columns:
            df[col] = pd.NA

    df = df.dropna(subset=["mm_dd", "time_str", "SmO2_live"])
    df["mm_dd"] = df["mm_dd"].map(_normalize_mmdd)
    df["time_str"] = df["time_str"].map(_normalize_time_str)
    df = df.dropna(subset=["mm_dd", "time_str"])

    datetime_str = f"{year}-" + df["mm_dd"].astype(str) + " " + df["time_str"].astype(str)
    df["datetime_raw"] = pd.to_datetime(
        datetime_str, format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    df = df.dropna(subset=["datetime_raw"])
    df["datetime_raw"] = df["datetime_raw"].dt.tz_localize("Asia/Seoul")

    for col in ("SmO2_live", "SmO2_avg", "THb"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["SmO2_live"]).reset_index(drop=True)
    if df.empty:
        raise ValueError(
            "유효한 시계열 행이 0개 (날짜/시간 파싱 또는 SmO2 결측 제거 후 모두 사라짐)"
        )
    for k, v in source_meta.items():
        df.attrs[k] = v
    return df[_OUTPUT_COLS]


# ─────────────────────────────────────────────────────────────
#  텍스트 (.txt / .csv) 경로
# ─────────────────────────────────────────────────────────────
def _sniff(path: Path) -> tuple[str, str]:
    """파일 앞부분으로 인코딩과 구분자를 탐지."""
    with open(path, "rb") as f:
        raw = f.read(4096)

    for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            text = raw.decode(enc)
            encoding = enc
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover
        text = raw.decode("latin-1")
        encoding = "latin-1"

    header_line = ""
    for line in text.splitlines():
        s = line.lstrip()
        if any(s.startswith(tok) for tok in _DATE_HEADER_TOKENS):
            header_line = line
            break
    sep = "\t" if header_line.count("\t") > header_line.count(",") else ","
    return encoding, sep


def _load_text(path: Path, year: int) -> pd.DataFrame:
    encoding, sep = _sniff(path)
    df = pd.read_csv(
        path,
        skiprows=3,
        header=0,
        sep=sep,
        encoding=encoding,
        skip_blank_lines=True,
        dtype=str,
        engine="python",
    )
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns=_RENAME_MAP)
    return _finalize_dataframe(df, year, {"source_encoding": encoding, "source_sep": sep})


# ─────────────────────────────────────────────────────────────
#  .xlsx 경로
# ─────────────────────────────────────────────────────────────
def _load_xlsx(path: Path, year: int) -> pd.DataFrame:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        ws = wb.active
        if ws is None:
            raise ValueError(f"활성 시트가 없는 xlsx: {path}")
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    header_row_idx = None
    for i, r in enumerate(rows):
        if r and any(
            str(c).strip() in _DATE_HEADER_TOKENS for c in r if c is not None
        ):
            header_row_idx = i
            break
    if header_row_idx is None:
        raise ValueError(
            f"날짜 헤더({'/'.join(_DATE_HEADER_TOKENS)})를 찾지 못함: {path}"
        )

    header_row = rows[header_row_idx]
    header = [str(c).strip() if c is not None else f"_unnamed_{j}"
              for j, c in enumerate(header_row)]

    data_rows = []
    for r in rows[header_row_idx + 1:]:
        if not r:
            continue
        if r[0] is None and r[1] is None:
            continue
        # 헤더 길이만큼 자르기
        data_rows.append(list(r[: len(header)]))

    df = pd.DataFrame(data_rows, columns=header)
    df = df.loc[:, ~df.columns.astype(str).str.startswith("_unnamed_")]
    df = df.rename(columns=_RENAME_MAP)
    return _finalize_dataframe(df, year, {"source_format": "xlsx"})


# ─────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────
def load_calf(path: str | Path, year: int = DEFAULT_YEAR) -> pd.DataFrame:
    """`.txt`, `.csv`, `.xlsx` 의 _Calf 시계열을 통합 로드.

    반환 컬럼:
        - datetime_raw (tz=Asia/Seoul)
        - SmO2_live, SmO2_avg, THb, Lap, Session_Ct
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_dir():
        raise IsADirectoryError(f"파일이 아닌 디렉토리가 전달됨: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"빈 파일: {path}")

    suffix = path.suffix.lower()
    if suffix in _TEXT_EXTS:
        return _load_text(path, year)
    if suffix in _XLSX_EXTS:
        return _load_xlsx(path, year)
    raise ValueError(
        f"지원하지 않는 확장자: {suffix} (지원: {sorted(_TEXT_EXTS | _XLSX_EXTS)})"
    )


# 하위 호환 alias — 기존 import 코드 유지
def load_calf_csv(path: str | Path, year: int = DEFAULT_YEAR) -> pd.DataFrame:
    """`load_calf` 의 구버전 이름. 신규 코드에서는 `load_calf` 사용."""
    return load_calf(path, year)


# ─────────────────────────────────────────────────────────────
#  컬럼 기반 식별 (파일명·접미사 무관)
# ─────────────────────────────────────────────────────────────
def _has_calf_header_text(path: Path, max_lines: int = 64) -> bool:
    with open(path, "rb") as f:
        raw = f.read(8192)
    text = None
    for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return False
    for line in text.splitlines()[:max_lines]:
        s = line.lstrip()
        if any(s.startswith(tok) for tok in _DATE_HEADER_TOKENS) and "SmO2" in line:
            return True
    return False


def _has_calf_header_xlsx(path: Path, max_rows: int = 16) -> bool:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        ws = wb.active
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_rows:
                return False
            if not row:
                continue
            cells = [str(c).strip() if c is not None else "" for c in row]
            has_date = any(c in _DATE_HEADER_TOKENS for c in cells)
            has_smo2 = any(c.startswith("SmO2") for c in cells)
            if has_date and has_smo2:
                return True
        return False
    finally:
        wb.close()


def is_calf_timeseries(path: str | Path) -> bool:
    """파일명/접미사가 아닌 헤더 시그니처로 _Calf 시계열 여부를 판정.

    헤더의 첫 컬럼이 ``mm-dd`` 또는 ``Date`` 이고 같은 행에 ``SmO2`` 컬럼이 있으면 참.
    텍스트는 앞 ~64줄, xlsx는 앞 ~16행만 본다. 어떤 예외든 발생하면 False.
    """
    path = Path(path)
    if not path.is_file():
        return False
    suffix = path.suffix.lower()
    try:
        if suffix in _TEXT_EXTS:
            return _has_calf_header_text(path)
        if suffix in _XLSX_EXTS:
            return _has_calf_header_xlsx(path)
    except Exception:
        return False
    return False
