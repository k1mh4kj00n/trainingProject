"""Kubios HRV Scientific CSV 리포트 파서.

파일 구조:
    L1           : 'sep=,'
    L2~          : 메타 헤더, 분석 파라미터
    L66~         : 지표 결과 (Results Overview, Time-Domain 등)
    L272~        : 'RR INTERVAL DATA, SPECTRUM ESTIMATES AND ECG-WAVEFORM' 헤더
    L275~        : 다중 시리즈 테이블 (Time, RR interval, Frequency/PSD FFT&AR,
                   VLF/LF/HF components, ECG 등)

loader의 역할:
    1) 메타 + 파라미터 + Kubios 계산 지표값을 dict로 반환 (검증 기준값)
    2) RR 시계열(초 단위)을 numpy 배열로 반환 (분석 입력)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


RR_DATA_HEADER_PREFIX = "RR INTERVAL DATA"


@dataclass
class KubiosReport:
    """Kubios CSV에서 추출한 ground-truth 정보."""
    file_path: Path
    meta: dict = field(default_factory=dict)        # 측정 메타 (date, duration, …)
    parameters: dict = field(default_factory=dict)  # 분석 파라미터 (bands, windows, …)
    sample_info: dict = field(default_factory=dict) # 샘플 구간, beat correction 등
    metrics: dict = field(default_factory=dict)     # Kubios가 계산한 모든 지표
    rr_times_s: np.ndarray = field(default_factory=lambda: np.array([]))  # 절대 시간 (s)
    rr_intervals_s: np.ndarray = field(default_factory=lambda: np.array([]))  # RR (s)
    ecg_times_s: np.ndarray = field(default_factory=lambda: np.array([]))
    ecg_mv: np.ndarray = field(default_factory=lambda: np.array([]))
    psd_fft: Optional[pd.DataFrame] = None  # columns: freq, power (ms²/Hz)
    psd_ar: Optional[pd.DataFrame] = None
    # Kubios 의 슬라이딩 윈도우 시계열 분석 결과 (TIME-VARYING RESULTS 섹션)
    # 각 행 = 1분 step (300s 윈도우 default), 컬럼 = SDNN/RMSSD/LF/HF/DFA 등 ~50개 지표
    time_varying: Optional[pd.DataFrame] = None

    @property
    def rr_ms(self) -> np.ndarray:
        """RR intervals in milliseconds."""
        return self.rr_intervals_s * 1000.0

    def time_varying_at(self, clock_hms: str, tolerance_sec: int = 90) -> Optional[pd.Series]:
        """주어진 시계 시각 (HH:MM:SS) 에 가장 가까운 time-varying 행을 반환.

        ``tolerance_sec`` 이내 매칭이 없으면 None. 외부 xlsx HRV_Baseline 시각 같은
        입력으로 그 시점의 SDNN/LF/HF/DFA 등을 즉시 조회할 때 사용.
        """
        if self.time_varying is None or self.time_varying.empty:
            return None
        if "Time" not in self.time_varying.columns:
            return None

        try:
            target_sec = _hms_to_sec(clock_hms)
        except ValueError:
            return None

        rows = self.time_varying
        time_secs = rows["Time"].apply(_hms_to_sec_safe)
        deltas = (time_secs - target_sec).abs()
        idx = int(deltas.idxmin())
        if deltas.iloc[idx] > tolerance_sec:
            return None
        return rows.iloc[idx]


def _as_float(x) -> float:
    try:
        return float(str(x).strip())
    except Exception:
        return np.nan


def _hms_to_sec(s: str) -> int:
    parts = s.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"not HH:MM:SS — {s!r}")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def _hms_to_sec_safe(s) -> float:
    try:
        return float(_hms_to_sec(str(s)))
    except (ValueError, TypeError):
        return float("nan")


def load_kubios_csv(path: str | Path) -> KubiosReport:
    """Kubios가 생성한 HRV 리포트 CSV를 읽어 KubiosReport 객체로 반환."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    rep = KubiosReport(file_path=path)

    # 섹션 경계 찾기
    rr_header_line_idx: Optional[int] = None
    for i, line in enumerate(lines):
        if line.startswith(RR_DATA_HEADER_PREFIX):
            rr_header_line_idx = i
            break
    if rr_header_line_idx is None:
        raise ValueError("RR INTERVAL DATA 섹션을 찾지 못함")

    # ── 1) 지표 / 메타 / 파라미터 파싱 (L1 ~ RR header 직전) ──
    header_lines = lines[: rr_header_line_idx]
    _parse_header_section(rep, header_lines)
    # TIME-VARYING RESULTS 섹션 (있으면) — 슬라이딩 윈도우 시계열 표
    rep.time_varying = _parse_time_varying(header_lines)

    # ── 2) RR/PSD/ECG 직접 필드 인덱스로 파싱 ──
    # 컬럼 순서 (L275):
    #   [0]=빈    [1]=Time(s)  [2]=RR interval(s)
    #   [3]=Freq  [4]=PSD FFT  [5]=Freq  [6]=PSD AR
    #   [7]=VLF comp  [8]=LF comp  [9]=HF comp
    #   [10]=Time.1(s)  [11]=ECG(mV)  [12]=Marker
    #
    # pandas.read_csv로 처리하려 했으나 빈 컬럼과 혼합 dtype 때문에 매핑이
    # 어긋나는 사례가 있어 직접 split으로 파싱한다.
    data_start = rr_header_line_idx + 5  # header 4줄 뒤 첫 데이터
    rr_t, rr_s = [], []
    fft_f, fft_p = [], []
    ar_f, ar_p = [], []
    ecg_t, ecg_v = [], []

    def _num(x: str):
        x = x.strip()
        if not x:
            return None
        try:
            return float(x)
        except ValueError:
            return None

    for raw_line in lines[data_start:]:
        if "," not in raw_line:
            continue
        fields = [f for f in raw_line.split(",")]
        # Kubios 형식에는 최소 13개 필드. 짧으면 무시.
        if len(fields) < 13:
            continue
        t  = _num(fields[1])   # Time (s)
        r  = _num(fields[2])   # RR interval (s)
        ff = _num(fields[3])   # FFT freq
        fp = _num(fields[4])   # FFT PSD
        af = _num(fields[5])   # AR freq
        ap = _num(fields[6])   # AR PSD
        et = _num(fields[10])  # ECG time
        ev = _num(fields[11])  # ECG mV

        if t is not None and r is not None:
            rr_t.append(t); rr_s.append(r)
        if ff is not None and fp is not None:
            fft_f.append(ff); fft_p.append(fp)
        if af is not None and ap is not None:
            ar_f.append(af); ar_p.append(ap)
        if et is not None and ev is not None:
            ecg_t.append(et); ecg_v.append(ev)

    rep.rr_times_s = np.asarray(rr_t, dtype=float)
    rep.rr_intervals_s = np.asarray(rr_s, dtype=float)
    if fft_f:
        rep.psd_fft = pd.DataFrame({"freq": fft_f, "power": fft_p})
    if ar_f:
        rep.psd_ar = pd.DataFrame({"freq": ar_f, "power": ar_p})
    # ECG 시계열은 attrs에 저장 (대용량일 수 있음)
    rep.ecg_times_s = np.asarray(ecg_t, dtype=float)
    rep.ecg_mv = np.asarray(ecg_v, dtype=float)

    return rep


def _parse_header_section(rep: KubiosReport, lines: list[str]) -> None:
    """Kubios CSV 상단(지표·메타·파라미터)을 정규식으로 뽑아낸다."""
    text = "\n".join(lines)

    # 메타
    for key in ("File name", "Measurement date", "File type", "Channel label",
                "Data length", "Measurement rate"):
        m = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
        if m:
            rep.meta[key] = m.group(1).strip()

    # 파라미터 블록 (줄 단위)
    param_patterns = {
        "Detrending": r"Detrending method:\s*(.+?)\s*$",
        "NNxx threshold": r"Threshold for NNxx/pNNxx:\s*(\d+)\s*ms",
        "Min/Max HR avg beats": r"Min/Max HR as average of:\s*(\d+)\s*beats",
        "Interp rate": r"Interpolation rate:\s*(\d+)\s*Hz",
        "VLF band": r"VLF:\s*([\d.]+)\s*-\s*([\d.]+)\s*Hz",
        "LF band": r"LF:\s*([\d.]+)\s*-\s*([\d.]+)\s*Hz",
        "HF band": r"HF:\s*([\d.]+)\s*-\s*([\d.]+)\s*Hz",
        "FFT window sec": r"Window width:\s*(\d+)\s*s",
        "FFT overlap": r"Window overlap:\s*(\d+)\s*%",
        "AR order": r"AR model order:\s*(\d+)",
        "DFA short": r"DFA,\s*short-term fluctuations:\s*(\d+)-(\d+)",
        "DFA long":  r"DFA,\s*long-term fluctuations:\s*(\d+)-(\d+)",
        "Entropy m": r"Entropy,\s*embedding dimension:\s*(\d+)",
        "Entropy r": r"Entropy,\s*tolerance:\s*([\d.]+)\s*x\s*SD",
    }
    for key, pat in param_patterns.items():
        m = re.search(pat, text, re.MULTILINE | re.IGNORECASE)
        if m:
            rep.parameters[key] = m.groups() if len(m.groups()) > 1 else m.group(1)

    # 샘플 정보
    m = re.search(r"Sample limits \(hh:mm:ss\):\s*,([^,]+),", text)
    if m:
        rep.sample_info["limits"] = m.group(1).strip()
    m = re.search(r"Beats total:\s*,\s*(\d+)", text)
    if m:
        rep.sample_info["beats_total"] = int(m.group(1))
    m = re.search(r"Beats corrected:\s*,\s*(\d+)", text)
    if m:
        rep.sample_info["beats_corrected"] = int(m.group(1))
    m = re.search(r"Effective data length \(s\):\s*,\s*([\d.]+)", text)
    if m:
        rep.sample_info["effective_length_s"] = float(m.group(1))

    # 지표 추출 — "  LABEL  (units):   ,  value," 형태의 반복 라인
    metric_line_re = re.compile(
        r"^\s*([A-Za-z][A-Za-z0-9 /\-\+\(\)\^\%\._,]+?)\s*:\s*,\s*([^,]+?)\s*,",
    )
    # 주파수 섹션은 FFT/AR 두 값이 있어 별도 처리
    freq_line_re = re.compile(
        r"^\s*([A-Za-z][A-Za-z0-9 /\-\+\(\)\^\%\._,]+?)\s*:\s*,\s*([^,]*?)\s*,\s*([^,]*?)\s*,",
    )

    current_section = "root"
    for line in lines:
        s = line.strip()
        if not s:
            continue
        # 섹션 감지
        if re.match(r"^(Results Overview|Time-Domain Results|"
                    r"Frequency-Domain Results|Nonlinear Results|"
                    r"ECG WAVEFORM RESULTS|TIME-VARYING RESULTS|"
                    r"Statistical parameters|Geometric parameters|"
                    r"Peak frequencies|Absolute powers|Relative powers|"
                    r"Normalized powers|Poincare plot|"
                    r"Detrended fluctuations|Recurrence plot analysis)", s):
            current_section = s.rstrip(":")
            continue

        # Frequency-domain 라인은 FFT, AR 두 값
        if current_section.startswith("Peak frequencies") or \
           current_section.startswith("Absolute powers") or \
           current_section.startswith("Relative powers") or \
           current_section.startswith("Normalized powers") or \
           s.startswith("LF/HF ratio") or s.startswith("Total power"):
            m = freq_line_re.match(line)
            if m:
                label = m.group(1).strip()
                v_fft = _as_float(m.group(2))
                v_ar = _as_float(m.group(3))
                rep.metrics[f"{label} (FFT)"] = v_fft
                if not np.isnan(v_ar):
                    rep.metrics[f"{label} (AR)"] = v_ar
                continue

        m = metric_line_re.match(line)
        if m:
            label = m.group(1).strip()
            val = _as_float(m.group(2))
            rep.metrics[label] = val


# ─────────────────────────────────────────────────────────────
#  TIME-VARYING RESULTS 섹션 파서
# ─────────────────────────────────────────────────────────────
def _parse_time_varying(lines: list[str]) -> Optional[pd.DataFrame]:
    """``TIME-VARYING RESULTS`` 섹션의 슬라이딩 윈도우 시계열 표를 DataFrame 으로.

    Kubios CSV 의 해당 섹션 구조:
      L0  : ``TIME-VARYING RESULTS,``
      L1  : ``,WHOLE DATA,...`` (분석 단위 라벨)
      L2  : (블록 구분자)
      L3  : 그룹 라벨 (Overview / Time-Domain / Freq-Domain / Nonlinear) — 듬성듬성
      L4  : 컬럼명 (Time, Beats total, ..., DFA a2)
      L5  : 단위 ((hh:mm:ss), (count), ...)
      L6+ : 데이터 (각 행 = 한 윈도우)

    중복 컬럼 (예: 'Beats corrected' 가 (count)/(%) 두 번) 은 단위로 disambiguate.
    누락 시 ``None`` 반환.
    """
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("TIME-VARYING RESULTS"):
            start = i
            break
    if start is None:
        return None

    # 컬럼명 행 / 단위 행 / 첫 데이터 행 찾기
    cols_idx = None
    for i in range(start + 1, min(start + 12, len(lines))):
        cells = [c.strip() for c in lines[i].split(",")]
        # 'Time' + 'Beats total' 둘 다 들어있는 행을 컬럼명 행으로
        if "Time" in cells and "Beats total" in cells:
            cols_idx = i
            break
    if cols_idx is None:
        return None
    units_idx = cols_idx + 1

    raw_cols  = [c.strip() for c in lines[cols_idx].split(",")]
    raw_units = [c.strip() for c in lines[units_idx].split(",")]

    # 중복 컬럼명 disambiguate — 단위(괄호 포함) 를 suffix 로
    seen_count: dict[str, int] = {}
    final_cols: list[str] = []
    for c, u in zip(raw_cols, raw_units):
        if not c:
            final_cols.append("")
            continue
        if c in seen_count:
            seen_count[c] += 1
            unit_clean = u.strip().strip("()") or f"col{seen_count[c]}"
            final_cols.append(f"{c} ({unit_clean})")
        else:
            seen_count[c] = 1
            final_cols.append(c)

    # 데이터 행 수집 — 두 번째 셀이 HH:MM:SS 패턴
    import re as _re
    hms_re = _re.compile(r"^\s*\d{1,2}:\d{2}:\d{2}\s*$")
    data_rows: list[list[str]] = []
    for i in range(units_idx + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            # 빈 줄 — 보통 섹션 끝
            if data_rows:
                break
            continue
        cells = [c.strip() for c in line.split(",")]
        if len(cells) < 2 or not hms_re.match(cells[1]):
            # 데이터 행이 아닌 다른 섹션 시작
            if data_rows:
                break
            continue
        data_rows.append(cells)

    if not data_rows:
        return None

    # DataFrame 빌드 — 컬럼 길이를 데이터에 맞춤
    n_cols_data = len(data_rows[0])
    cols = final_cols[:n_cols_data] + [f"_extra{i}" for i in range(n_cols_data - len(final_cols))]
    cols = cols[:n_cols_data]
    df = pd.DataFrame(data_rows, columns=cols)

    # 빈 컬럼 (formatting padding) 드롭
    df = df.loc[:, [c for c in df.columns if c]]
    # Time 외 모든 컬럼 → numeric
    for c in df.columns:
        if c == "Time":
            continue
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
