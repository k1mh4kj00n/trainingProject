"""파라미터 패널 상태 ↔ xlsx/csv/txt 직렬화.

ParameterPanel 의 모든 input 위젯 값을 평문(plain) 키-값 트리플 ``(section, key, value)``
로 추상화한 뒤, 사용자가 선택한 확장자에 따라 xlsx/csv/txt 로 저장한다. 로드는 그 역.

설계 원칙
~~~~~~~~~
* **단일 스키마 — 3 가지 표현**: 같은 트리플 시퀀스를 xlsx 3 컬럼 / csv 3 컬럼 / txt INI
  로 모두 표현. 어떤 형식으로 저장하든 동일하게 round-trip.
* **부분 로드 허용**: 파일에 일부 키만 있어도 그 키만 패널에 반영. 빠진 키는 기존 값 유지.
* **빈 문자열 = unset**: 시각/날짜/숫자 모두 빈 문자열은 "값 없음 → 0 또는 미설정" 으로 처리.

키 명세
~~~~~~~
* ``Subject`` — ParameterPanel._INFO_FIELDS 의 19 필드 (key 그대로)
* ``NIRS_VOT`` (v0.7) — ``count`` + indexed 키 ``1.name``, ``1.start``, ``1.end``, ``1.lead``, ``1.tail``,
                          ``2.name``, ``2.start`` ... 사용자가 추가한 모든 timepoint 직렬화
* ``HRV`` — ``Baseline.start``, ``Baseline.end``, ``Recovery2.start``, ``Recovery2.end`` (HH:MM:SS, display 전용)
* ``Exercise`` — ``TTE1``, ``TTE2`` (HH:MM:SS — 분/초 단위 시간), ``TTE_maintenance_rate`` (float, %)
* ``Lock`` — ``baseline_enabled`` (bool), ``baseline_value`` (float, %),
              ``min_time``, ``peak_time`` (HH:MM:SS, 00:00:00 = unset)

backward-compat:
  - 옛 ``Override`` 섹션 → ``Lock`` 으로 정규화.
  - 옛 ``NIRS_VOT`` 의 ``Baseline.start/.end``, ``Recovery2.start/.end`` 4 키 → 2 행 list 로 변환,
    lead/tail 은 옛 ``Anchor.lead_sec``/``tail_sec`` 키 또는 default(60/180) 사용.
  - 옛 ``Anchor`` 섹션은 모든 NIRS_VOT 행에 동일 lead/tail 적용 후 deprecated.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QDate, QTime


# ─────────────────────────────────────────────────────────────
#  스키마
# ─────────────────────────────────────────────────────────────
SUBJECT_KEYS: tuple[str, ...] = (
    "ID(Protocol)", "Name", "D.O.B", "Age", "Gender",
    "Weight(kg)", "Height(cm)",
    "Wattmax", "VO2max", "W/kg", "FTP", "AT(VT1)", "RC(VT2)",
    "Wattmax(90%)", "Wattmax(40%)", "Wattmax(110%)",
    "안장 높이", "안정시 심박수",
)
TIMEPOINT_KEYS: tuple[str, ...] = (
    "Baseline.start", "Baseline.end",
    "Recovery2.start", "Recovery2.end",
)  # HRV 만 사용 (NIRS_VOT 는 v0.7 부터 indexed)
EXERCISE_KEYS: tuple[str, ...] = ("TTE1", "TTE2", "TTE_maintenance_rate")
LOCK_KEYS: tuple[str, ...] = (
    "baseline_enabled", "baseline_value", "min_time", "peak_time",
)

SECTIONS_ORDER: tuple[str, ...] = (
    "Subject", "NIRS_VOT", "HRV", "Exercise", "Lock",
)

# 템플릿용 인라인 코멘트 — 비어있을 때도 사람이 어떻게 채울지 알 수 있도록.
_HINT: dict[tuple[str, str], str] = {
    ("Subject", "D.O.B"):           "YYYY-MM-DD",
    ("Subject", "Gender"):          "Male / Female / Other",
    ("NIRS_VOT", "count"):          "timepoint 행 수",
    ("HRV", "Baseline.start"):      "HH:MM:SS  (분석 미사용)",
    ("HRV", "Baseline.end"):        "HH:MM:SS  (분석 미사용)",
    ("HRV", "Recovery2.start"):     "HH:MM:SS  (분석 미사용)",
    ("HRV", "Recovery2.end"):       "HH:MM:SS  (분석 미사용)",
    ("Exercise", "TTE1"):           "HH:MM:SS  Ex1 인터벌 Time To Exhaustion",
    ("Exercise", "TTE2"):           "HH:MM:SS  Ex2 인터벌 Time To Exhaustion",
    ("Exercise", "TTE_maintenance_rate"): "% (목표 와트 유지율, 70% 미만 = 경고)",
    ("Lock", "baseline_enabled"): "true 일 때만 baseline_value 잠금 (Apply 후에도 유지)",
    ("Lock", "baseline_value"):   "% (0~100)",
    ("Lock", "min_time"):         "HH:MM:SS (빈 칸이면 자동검출)",
    ("Lock", "peak_time"):        "HH:MM:SS (빈 칸이면 자동검출)",
}


# ─────────────────────────────────────────────────────────────
#  값 → 문자열 / 문자열 → 값
# ─────────────────────────────────────────────────────────────
def _fmt(v) -> str:
    """파이썬 값 → 평문 문자열 (txt/csv/xlsx 공통)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, dt.datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, dt.date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, dt.time):
        return v.strftime("%H:%M:%S")
    if isinstance(v, float):
        if v == int(v):
            return f"{int(v)}"
        return f"{v:g}"
    return str(v)


def _parse_time(s: str) -> dt.time | None:
    s = (s or "").strip()
    if not s:
        return None
    parts = s.split(":")
    try:
        if len(parts) == 2:
            return dt.time(int(parts[0]), int(parts[1]), 0)
        if len(parts) == 3:
            return dt.time(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None
    return None


def _parse_date(s: str) -> dt.datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _parse_bool(s: str) -> bool:
    return (s or "").strip().lower() in {"true", "1", "yes", "y", "t", "on"}


def _safe_int(v, default: int) -> int:
    """문자열/숫자/None → int. 실패 시 default."""
    if v is None:
        return default
    try:
        f = float(v)
        if f != f:  # NaN
            return default
        return int(round(f))
    except (TypeError, ValueError):
        return default


def _seconds_to_dt_time(s: int) -> dt.time:
    """초 단위 정수 → dt.time. 24시간 초과 시 hour 모듈로(통상 TTE 는 1분 이내)."""
    s = max(0, int(s))
    h = (s // 3600) % 24
    m = (s % 3600) // 60
    sec = s % 60
    return dt.time(h, m, sec)


# ─────────────────────────────────────────────────────────────
#  Panel ↔ State (list of (section, key, value_str))
# ─────────────────────────────────────────────────────────────
def serialize(panel) -> list[tuple[str, str, str]]:
    """ParameterPanel 의 현재 input 값들을 평문 트리플 시퀀스로."""
    panel._commit_all_inputs()
    rows: list[tuple[str, str, str]] = []

    info = panel.collect_subject_info()
    for k in SUBJECT_KEYS:
        rows.append(("Subject", k, _fmt(info.get(k))))

    # NIRS_VOT — v0.7 indexed list (사용자가 추가/삭제한 모든 timepoint)
    nirs_tps = panel.collect_nirs_timepoints()
    rows.append(("NIRS_VOT", "count", _fmt(len(nirs_tps))))
    for i, tp in enumerate(nirs_tps, start=1):
        rows.append(("NIRS_VOT", f"{i}.name",  tp.name))
        rows.append(("NIRS_VOT", f"{i}.start", _fmt(tp.start)))
        rows.append(("NIRS_VOT", f"{i}.end",   _fmt(tp.end)))
        rows.append(("NIRS_VOT", f"{i}.lead",  _fmt(int(tp.lead))))
        rows.append(("NIRS_VOT", f"{i}.tail",  _fmt(int(tp.tail))))

    # HRV — display 전용, 고정 2칸
    hrv = panel.collect_hrv_windows()
    for sess in ("Baseline", "Recovery2"):
        w = hrv.get(sess)
        rows.append(("HRV", f"{sess}.start", _fmt(w.start) if w else ""))
        rows.append(("HRV", f"{sess}.end",   _fmt(w.end)   if w else ""))

    # Exercise / TTE — panel 의 정수 sec spinbox 를 HH:MM:SS 로 직렬화
    tte1_sec = int(panel.tte1_spin.value())
    tte2_sec = int(panel.tte2_spin.value())
    rows.append(("Exercise", "TTE1",
                 _fmt(_seconds_to_dt_time(tte1_sec)) if tte1_sec > 0 else ""))
    rows.append(("Exercise", "TTE2",
                 _fmt(_seconds_to_dt_time(tte2_sec)) if tte2_sec > 0 else ""))
    rows.append(("Exercise", "TTE_maintenance_rate",
                 _fmt(float(panel.maint_spin.value()))))

    rows.append(("Lock", "baseline_enabled",
                 _fmt(panel.baseline_override_chk.isChecked())))
    rows.append(("Lock", "baseline_value",
                 _fmt(float(panel.baseline_value_spin.value()))))

    mt = panel.min_time_edit.time()
    pt = panel.peak_time_edit.time()
    mt_t = dt.time(mt.hour(), mt.minute(), mt.second())
    pt_t = dt.time(pt.hour(), pt.minute(), pt.second())
    rows.append(("Lock", "min_time",
                 _fmt(mt_t) if mt_t != dt.time(0, 0, 0) else ""))
    rows.append(("Lock", "peak_time",
                 _fmt(pt_t) if pt_t != dt.time(0, 0, 0) else ""))

    return rows


def apply_to_panel(panel, state: Iterable[tuple[str, str, str]]) -> tuple[int, list[str]]:
    """평문 트리플을 패널 input 위젯에 반영.

    Returns
    -------
    (applied_count, warnings):
        ``applied_count`` — 실제 적용된 키 수 (스키마와 일치한 키만 카운트).
        ``warnings``      — 알 수 없는 (section, key) 또는 파싱 실패 메시지 리스트.
    """
    state_dict: dict[tuple[str, str], str] = {}
    for sect, key, val in state:
        s = str(sect).strip()
        # backward-compat: 옛 "Override" 섹션 → "Lock" 으로 정규화
        if s == "Override":
            s = "Lock"
        state_dict[(s, str(key).strip())] = "" if val is None else str(val)

    applied = 0
    warnings: list[str] = []

    # Subject ─────────────────────────────
    for k in SUBJECT_KEYS:
        v = state_dict.pop(("Subject", k), None)
        if v is None:
            continue
        if k not in panel._info_inputs:
            warnings.append(f"unknown subject key: {k}")
            continue
        kind, w = panel._info_inputs[k]
        if not _set_subject_widget(w, kind, v):
            warnings.append(f"Subject.{k}: 파싱 실패 → '{v}'")
        applied += 1

    # NIRS_VOT — v0.7 indexed list 우선, 없으면 옛 4-키 형식 + Anchor.lead/tail 호환
    legacy_lead_v = state_dict.pop(("Anchor", "lead_sec"), None)
    legacy_tail_v = state_dict.pop(("Anchor", "tail_sec"), None)
    legacy_lead = _safe_int(legacy_lead_v, 60)
    legacy_tail = _safe_int(legacy_tail_v, 180)

    nirs_tps_loaded: list = []
    count_str = state_dict.pop(("NIRS_VOT", "count"), None)
    if count_str is not None:
        # 신버전 indexed
        try:
            n = int(float(count_str))
        except ValueError:
            n = 0
        for i in range(1, n + 1):
            name_v = (state_dict.pop(("NIRS_VOT", f"{i}.name"), "") or "").strip()
            start_v = state_dict.pop(("NIRS_VOT", f"{i}.start"), "")
            end_v   = state_dict.pop(("NIRS_VOT", f"{i}.end"),   "")
            lead_v  = state_dict.pop(("NIRS_VOT", f"{i}.lead"),  "")
            tail_v  = state_dict.pop(("NIRS_VOT", f"{i}.tail"),  "")
            s_t = _parse_time(start_v)
            e_t = _parse_time(end_v)
            if not name_v or s_t is None or e_t is None:
                warnings.append(f"NIRS_VOT row {i}: 이름/시각 파싱 실패")
                continue
            nirs_tps_loaded.append({
                "name": name_v, "start": s_t, "end": e_t,
                "lead": _safe_int(lead_v, legacy_lead),
                "tail": _safe_int(tail_v, legacy_tail),
            })
            applied += 5
    else:
        # 구버전 4-키 형식 (Baseline/Recovery2 고정)
        for sess in ("Baseline", "Recovery2"):
            sv = state_dict.pop(("NIRS_VOT", f"{sess}.start"), None)
            ev = state_dict.pop(("NIRS_VOT", f"{sess}.end"),   None)
            if sv is None and ev is None:
                continue
            s_t = _parse_time(sv) if sv else None
            e_t = _parse_time(ev) if ev else None
            if s_t is None or e_t is None:
                continue
            nirs_tps_loaded.append({
                "name": sess, "start": s_t, "end": e_t,
                "lead": legacy_lead, "tail": legacy_tail,
            })
            applied += 2

    # 패널에 새 행으로 반영 (기존 행 제거 후 재구축)
    if nirs_tps_loaded:
        try:
            from config_loader import Timepoint  # type: ignore
        except ImportError:
            from ...config_loader import Timepoint  # type: ignore
        panel._clear_nirs_rows()
        for d in nirs_tps_loaded:
            panel._add_nirs_row(tp=Timepoint(
                name=d["name"], start=d["start"], end=d["end"],
                lead=int(d["lead"]), tail=int(d["tail"]),
            ))

    # HRV — display 전용 고정 2칸
    for sess in ("Baseline", "Recovery2"):
        for which in ("start", "end"):
            key = f"{sess}.{which}"
            v = state_dict.pop(("HRV", key), None)
            if v is None:
                continue
            t = _parse_time(v) or dt.time(0, 0, 0)
            panel._hrv_inputs[sess][which].setTime(QTime(t.hour, t.minute, t.second))
            applied += 1

    # Exercise / TTE ──────────────────────
    for which, spin_attr in (("TTE1", "tte1_spin"), ("TTE2", "tte2_spin")):
        v = state_dict.pop(("Exercise", which), None)
        if v is None:
            continue
        spin = getattr(panel, spin_attr)
        # HH:MM:SS / MM:SS / 정수초 / 빈문자열 모두 수용
        v = (v or "").strip()
        if not v:
            spin.setValue(0)
            applied += 1
            continue
        if ":" in v:
            t = _parse_time(v)
            if t is None:
                warnings.append(f"Exercise.{which}: 시간 파싱 실패 → '{v}'")
                continue
            spin.setValue(t.hour * 3600 + t.minute * 60 + t.second)
        else:
            try:
                spin.setValue(int(float(v)))
            except ValueError:
                warnings.append(f"Exercise.{which}: 정수 파싱 실패 → '{v}'")
                continue
        applied += 1

    if (v := state_dict.pop(("Exercise", "TTE_maintenance_rate"), None)) is not None:
        try:
            panel.maint_spin.setValue(float(v) if v else 0.0)
            applied += 1
        except ValueError:
            warnings.append(f"Exercise.TTE_maintenance_rate: 파싱 실패 → '{v}'")

    # 적용 후 quality label 즉시 갱신 (Apply 안 눌러도 경고가 보이도록)
    try:
        panel._update_tte_quality_label()
    except AttributeError:
        pass

    # Lock ────────────────────────────────
    if (v := state_dict.pop(("Lock", "baseline_enabled"), None)) is not None:
        panel.baseline_override_chk.setChecked(_parse_bool(v))
        applied += 1
    if (v := state_dict.pop(("Lock", "baseline_value"), None)) is not None:
        try:
            panel.baseline_value_spin.setValue(float(v) if v else 0.0)
            applied += 1
        except ValueError:
            warnings.append(f"Lock.baseline_value: 파싱 실패 → '{v}'")
    if (v := state_dict.pop(("Lock", "min_time"), None)) is not None:
        t = _parse_time(v) or dt.time(0, 0, 0)
        panel.min_time_edit.setTime(QTime(t.hour, t.minute, t.second))
        applied += 1
    if (v := state_dict.pop(("Lock", "peak_time"), None)) is not None:
        t = _parse_time(v) or dt.time(0, 0, 0)
        panel.peak_time_edit.setTime(QTime(t.hour, t.minute, t.second))
        applied += 1

    # 남은 키는 모두 unknown
    for (sect, key) in state_dict:
        warnings.append(f"unknown key: [{sect}] {key}")

    return applied, warnings


def _set_subject_widget(w, kind: str, raw: str) -> bool:
    """raw 문자열을 kind 에 맞춰 Subject input 에 set. 실패시 False."""
    raw = (raw or "").strip()
    if kind == "text":
        w.setText(raw)
        return True
    if kind == "gender":
        if raw == "":
            w.setCurrentIndex(0)
            return True
        # 대소문자 무시
        for i in range(w.count()):
            if w.itemText(i).strip().lower() == raw.lower():
                w.setCurrentIndex(i)
                return True
        # 없으면 그대로 추가하지 않고 0
        w.setCurrentIndex(0)
        return False
    if kind == "int":
        try:
            w.setValue(int(float(raw)) if raw else 0)
            return True
        except ValueError:
            w.setValue(0)
            return False
    if kind == "float":
        try:
            w.setValue(float(raw) if raw else 0.0)
            return True
        except ValueError:
            w.setValue(0.0)
            return False
    if kind == "date":
        if not raw:
            w.setDate(QDate(1900, 1, 1))
            return True
        d = _parse_date(raw)
        if d is None:
            w.setDate(QDate(1900, 1, 1))
            return False
        w.setDate(QDate(d.year, d.month, d.day))
        return True
    return False


# ─────────────────────────────────────────────────────────────
#  포맷별 입출력
# ─────────────────────────────────────────────────────────────
def save(path: str | Path, state: Iterable[tuple[str, str, str]]) -> None:
    """확장자로 포맷 자동 결정해서 저장."""
    p = Path(path)
    ext = p.suffix.lower()
    rows = list(state)
    if ext in (".xlsx", ".xls"):
        _save_xlsx(p, rows)
    elif ext == ".csv":
        _save_csv(p, rows)
    elif ext in (".txt", ".ini", ".cfg"):
        _save_txt(p, rows)
    else:
        raise ValueError(f"지원하지 않는 확장자: {ext}")


def load(path: str | Path) -> list[tuple[str, str, str]]:
    """확장자로 포맷 자동 결정해서 로드."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    ext = p.suffix.lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        return _load_xlsx(p)
    if ext == ".csv":
        return _load_csv(p)
    if ext in (".txt", ".ini", ".cfg"):
        return _load_txt(p)
    raise ValueError(f"지원하지 않는 확장자: {ext}")


# ───── xlsx ────────────────────────────────────────────────
def _save_xlsx(path: Path, rows: list[tuple[str, str, str]]) -> None:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Parameters"

    header = ("Section", "Key", "Value", "Hint")
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E5E7EB")
        cell.alignment = Alignment(horizontal="center")

    last_section = ""
    for sect, key, val in rows:
        hint = _HINT.get((sect, key), "")
        # 섹션이 바뀐 행만 Section 컬럼 표시 → 시각적 그룹화
        sect_disp = sect if sect != last_section else ""
        ws.append((sect_disp, key, val, hint))
        last_section = sect

    # 열 폭 자동 (대충)
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 36

    wb.save(path)


def _load_xlsx(path: Path) -> list[tuple[str, str, str]]:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    # 첫 시트 우선 — 있으면 'Parameters' 시트 우선
    sheet = wb["Parameters"] if "Parameters" in wb.sheetnames else wb.worksheets[0]

    rows: list[tuple[str, str, str]] = []
    last_section = ""
    first = True
    for r in sheet.iter_rows(values_only=True):
        if first:
            first = False
            # 헤더 행 (Section/Key/Value …) 이면 스킵
            head = [str(c).strip().lower() if c is not None else "" for c in r[:3]]
            if head[:3] == ["section", "key", "value"]:
                continue
        if r is None:
            continue
        # 최소 3 컬럼 필요
        sect = (str(r[0]).strip() if len(r) > 0 and r[0] is not None else "")
        key  = (str(r[1]).strip() if len(r) > 1 and r[1] is not None else "")
        val_raw = r[2] if len(r) > 2 else None
        if not sect:
            sect = last_section
        if not key:
            continue
        last_section = sect
        rows.append((sect, key, _xlsx_cell_to_str(val_raw)))
    wb.close()
    return rows


def _xlsx_cell_to_str(v) -> str:
    """openpyxl 셀 값을 직렬화용 문자열로 — datetime/time/숫자 모두 처리."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, dt.datetime):
        # 시간 부분만 있는 경우 (Excel 특이값) 도 안전 처리
        if v.year <= 1900 and v.month == 1 and v.day == 1:
            return v.strftime("%H:%M:%S")
        return v.strftime("%Y-%m-%d")
    if isinstance(v, dt.time):
        return v.strftime("%H:%M:%S")
    if isinstance(v, dt.date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float):
        if v == int(v):
            return f"{int(v)}"
        return f"{v:g}"
    return str(v).strip()


# ───── csv ─────────────────────────────────────────────────
def _save_csv(path: Path, rows: list[tuple[str, str, str]]) -> None:
    # utf-8-sig: Excel 한글 깨짐 방지
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(("Section", "Key", "Value", "Hint"))
        for sect, key, val in rows:
            w.writerow((sect, key, val, _HINT.get((sect, key), "")))


def _load_csv(path: Path) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    # BOM 자동 제거
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return out

    last_section = ""
    start_idx = 0
    head = [c.strip().lower() for c in rows[0][:3]] if len(rows[0]) >= 3 else []
    if head[:3] == ["section", "key", "value"]:
        start_idx = 1

    for r in rows[start_idx:]:
        if not r:
            continue
        sect = (r[0].strip() if len(r) > 0 else "")
        key  = (r[1].strip() if len(r) > 1 else "")
        val  = (r[2] if len(r) > 2 else "")
        if not sect:
            sect = last_section
        if not key:
            continue
        last_section = sect
        out.append((sect, key, val))
    return out


# ───── txt (INI-style) ─────────────────────────────────────
def _save_txt(path: Path, rows: list[tuple[str, str, str]]) -> None:
    lines: list[str] = [
        "# Physical Analysis — Parameter Snapshot",
        "# Format: INI-style.  '#' 또는 ';' 로 시작하는 줄은 코멘트.",
        "# 빈 값 = '미설정'  (시각·날짜·Lock 은 자동검출/기본값으로 동작).",
        "",
    ]
    by_section: dict[str, list[tuple[str, str]]] = {}
    for sect, key, val in rows:
        by_section.setdefault(sect, []).append((key, val))

    # 캐노니컬 순서로
    for sect in SECTIONS_ORDER:
        if sect not in by_section:
            continue
        lines.append(f"[{sect}]")
        for key, val in by_section[sect]:
            hint = _HINT.get((sect, key))
            if hint:
                lines.append(f"{key} = {val}    ; {hint}")
            else:
                lines.append(f"{key} = {val}")
        lines.append("")

    # 캐노니컬 외 섹션도 끝에 덧붙임
    for sect, kvs in by_section.items():
        if sect in SECTIONS_ORDER:
            continue
        lines.append(f"[{sect}]")
        for key, val in kvs:
            lines.append(f"{key} = {val}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _load_txt(path: Path) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    section = ""
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            # 빈 줄·코멘트
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                continue
            # 인라인 코멘트 (';' 이후) 분리
            if ";" in line:
                line = line.split(";", 1)[0]
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            out.append((section, key.strip(), val.strip()))
    return out


# ─────────────────────────────────────────────────────────────
#  템플릿 — 빈 값으로 모든 키를 가진 시퀀스 (Save 함수에 그대로 넣어 쓴다)
# ─────────────────────────────────────────────────────────────
def template_state() -> list[tuple[str, str, str]]:
    """모든 키가 빈 값(또는 합리적 기본값)으로 채워진 트리플 시퀀스."""
    rows: list[tuple[str, str, str]] = []
    for k in SUBJECT_KEYS:
        rows.append(("Subject", k, ""))
    # NIRS_VOT — 빈 템플릿은 Baseline/Recovery2 2 행으로 시작 (사용자가 자유 추가/삭제)
    rows.append(("NIRS_VOT", "count", "2"))
    for i, name in enumerate(("Baseline", "Recovery2"), start=1):
        rows.append(("NIRS_VOT", f"{i}.name",  name))
        rows.append(("NIRS_VOT", f"{i}.start", ""))
        rows.append(("NIRS_VOT", f"{i}.end",   ""))
        rows.append(("NIRS_VOT", f"{i}.lead",  "60"))
        rows.append(("NIRS_VOT", f"{i}.tail",  "180"))
    for k in TIMEPOINT_KEYS:
        rows.append(("HRV", k, ""))
    rows.append(("Exercise", "TTE1", ""))
    rows.append(("Exercise", "TTE2", ""))
    rows.append(("Exercise", "TTE_maintenance_rate", ""))
    rows.append(("Lock", "baseline_enabled", "false"))
    rows.append(("Lock", "baseline_value", "0"))
    rows.append(("Lock", "min_time", ""))
    rows.append(("Lock", "peak_time", ""))
    return rows
