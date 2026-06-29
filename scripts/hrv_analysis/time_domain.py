"""HRV Time-Domain 지표 (Kubios User's Guide 2026 Appendix A 기준).

입력:
    rr_ms : RR intervals (ms), 1-D ndarray

계산 지표:
    Mean RR, SDNN, Mean HR, SD HR, Min HR, Max HR (N-beat moving average),
    RMSSD, NN50, pNN50 (threshold=50ms 기본),
    HRV triangular index, TINN (히스토그램 기반),
    Stress index (Baevsky's SI의 제곱근),
    DC / AC / DCmod / ACmod (Phase-Rectified Signal Averaging)

Kubios 기본 파라미터:
    - NNxx threshold: 50 ms
    - Min/Max HR: 5-beat moving average
    - Histogram bin width: 7.8125 ms (1/128 s, Kubios 관례)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd

from .detrend import smoothness_priors_detrend


HISTOGRAM_BIN_MS = 7.8125  # Kubios 관례 (1/128 초)

# Kubios가 CSV에 보고하는 λ=500은 내부 구현 스케일이 다르다.
# 경험적 캘리브레이션 결과 우리 공식 (I + λ² D₂ᵀ D₂)⁻¹ 에서
# λ=100 일 때 Kubios λ=500 의 smoothing 강도와 가장 잘 일치한다.
# (이찬민 NOR Sample 1 벤치마크 기준 SDNN 오차 2.6% 이내)
DETREND_LAMBDA_DEFAULT = 100.0
NNXX_DEFAULT_MS = 50.0
HR_WINDOW_DEFAULT = 5
PRSA_T_DEFAULT = 1   # DC/AC: 인접 beat 비교
PRSA_WIN_DEFAULT = 2 # DC/AC: 앞뒤 2 beat (총 5 샘플)
PRSA_WIN_MOD_DEFAULT = 5  # DCmod/ACmod: 앞뒤 5 beat (총 11 샘플)


@dataclass
class TimeDomainResult:
    mean_rr_ms: float
    sdnn_ms: float
    mean_hr_bpm: float
    sd_hr_bpm: float
    min_hr_bpm: float
    max_hr_bpm: float
    rmssd_ms: float
    nn50_count: int
    pnn50_pct: float
    hrv_triangular_index: float
    tinn_ms: float
    stress_index: float
    dc_ms: float
    ac_ms: float
    dc_mod_ms: float
    ac_mod_ms: float

    def as_table(self) -> pd.DataFrame:
        rows = [
            ("Mean RR (ms)",            self.mean_rr_ms),
            ("SDNN (ms)",               self.sdnn_ms),
            ("Mean HR (bpm)",           self.mean_hr_bpm),
            ("SD HR (bpm)",             self.sd_hr_bpm),
            ("Min HR (bpm)",            self.min_hr_bpm),
            ("Max HR (bpm)",            self.max_hr_bpm),
            ("RMSSD (ms)",              self.rmssd_ms),
            ("NN50 (beats)",            self.nn50_count),
            ("pNN50 (%)",               self.pnn50_pct),
            ("HRV triangular index",    self.hrv_triangular_index),
            ("TINN (ms)",               self.tinn_ms),
            ("Stress index",            self.stress_index),
            ("DC (ms)",                 self.dc_ms),
            ("AC (ms)",                 self.ac_ms),
            ("DCmod (ms)",              self.dc_mod_ms),
            ("ACmod (ms)",              self.ac_mod_ms),
        ]
        return pd.DataFrame(rows, columns=["Item", "Value"])


# ──────────────────────────────────────────────
#  내부 함수
# ──────────────────────────────────────────────

def _moving_average(x: np.ndarray, n: int) -> np.ndarray:
    """길이 보존 N-beat moving average (앞/뒤 잘림 처리: np.convolve 'valid')."""
    if n <= 1:
        return x
    kernel = np.ones(n) / n
    return np.convolve(x, kernel, mode="valid")


def _triangular_index_and_tinn(rr_ms: np.ndarray, bin_ms: float = HISTOGRAM_BIN_MS):
    """히스토그램 기반 HRV triangular index + TINN (ms).

    - HRV triangular index = total beats / height of the modal bin
    - TINN = best triangle fit의 base (N, M) width 차
    """
    lo = float(np.floor(np.min(rr_ms) / bin_ms) * bin_ms)
    hi = float(np.ceil(np.max(rr_ms) / bin_ms) * bin_ms)
    if hi <= lo:
        hi = lo + bin_ms
    bins = np.arange(lo, hi + bin_ms, bin_ms)
    counts, edges = np.histogram(rr_ms, bins=bins)
    counts = counts.astype(float)
    if counts.max() == 0:
        return np.nan, np.nan

    tri_idx = counts.sum() / counts.max()

    # TINN: 삼각형 피팅. 모드(Mo) 중심으로 N<Mo<M 을 찾아
    # triangle (N, Mo, M) 와 히스토그램 간 제곱오차 최소화.
    mode_idx = int(np.argmax(counts))
    mode_height = counts[mode_idx]
    n_bins = len(counts)

    best_err = np.inf
    best_N = 0
    best_M = n_bins - 1
    # 범위 탐색 (왼쪽: 0..mode_idx, 오른쪽: mode_idx..end)
    for N_idx in range(0, mode_idx + 1):
        for M_idx in range(mode_idx, n_bins):
            # 삼각형 값
            tri = np.zeros(n_bins)
            # 왼쪽 사면
            if mode_idx > N_idx:
                for k in range(N_idx, mode_idx + 1):
                    tri[k] = mode_height * (k - N_idx) / (mode_idx - N_idx)
            else:
                tri[mode_idx] = mode_height
            # 오른쪽 사면
            if M_idx > mode_idx:
                for k in range(mode_idx, M_idx + 1):
                    tri[k] = mode_height * (M_idx - k) / (M_idx - mode_idx)
            err = float(np.sum((counts - tri) ** 2))
            if err < best_err:
                best_err = err
                best_N = N_idx
                best_M = M_idx
    # 기저 폭 (ms)
    center_left = edges[best_N] + bin_ms / 2.0
    center_right = edges[best_M] + bin_ms / 2.0
    tinn = float(center_right - center_left)
    return float(tri_idx), tinn


def _stress_index(rr_ms: np.ndarray, bin_ms: float = HISTOGRAM_BIN_MS) -> float:
    """Baevsky's Stress Index의 제곱근 (Kubios가 보고하는 값).

    Baevsky's SI = AMo / (2 * Mo[s] * MxDMn[s])
        AMo  : 모드 bin의 상대빈도 (%)
        Mo   : 모드 (초, RR)
        MxDMn: RR_max - RR_min (초)

    Kubios는 sqrt(Baevsky SI) 를 보고한다 (PDF Appendix A).
    """
    rr_s = rr_ms / 1000.0
    lo = float(np.floor(np.min(rr_ms) / bin_ms) * bin_ms)
    hi = float(np.ceil(np.max(rr_ms) / bin_ms) * bin_ms)
    bins = np.arange(lo, hi + bin_ms, bin_ms)
    counts, edges = np.histogram(rr_ms, bins=bins)
    total = counts.sum()
    if total == 0:
        return np.nan
    amo_pct = counts.max() / total * 100.0
    mode_idx = int(np.argmax(counts))
    mo_s = (edges[mode_idx] + bin_ms / 2.0) / 1000.0
    mxdmn_s = float(rr_s.max() - rr_s.min())
    if mo_s <= 0 or mxdmn_s <= 0:
        return np.nan
    baevsky = amo_pct / (2.0 * mo_s * mxdmn_s)
    return float(np.sqrt(baevsky))


def _prsa(rr_ms: np.ndarray, T: int, L: int, anchor: str) -> float:
    """Phase-Rectified Signal Averaging.

    anchor='dec' → RR[i] > RR[i-T] (감속 시점) → Deceleration Capacity
    anchor='acc' → RR[i] < RR[i-T] (가속 시점) → Acceleration Capacity

    PRSA 값:  x_tilde(k) = mean over anchors of RR[anchor+k]
    DC or AC = ( x_tilde(0) + x_tilde(1) - x_tilde(-1) - x_tilde(-2) ) / 4
    (윈도우 2L 샘플을 4등분한 PRSA 표준식. Bauer et al. 2006)

    For DCmod/ACmod (Kubios 변형), 더 긴 윈도우(L)로 같은 공식.
    """
    n = len(rr_ms)
    if n < 2 * L + 2:
        return np.nan
    anchors = []
    for i in range(T, n):
        if anchor == "dec" and rr_ms[i] > rr_ms[i - T]:
            anchors.append(i)
        elif anchor == "acc" and rr_ms[i] < rr_ms[i - T]:
            anchors.append(i)
    valid = [i for i in anchors if (i - L) >= 0 and (i + L) < n]
    if len(valid) == 0:
        return np.nan
    segs = np.array([rr_ms[i - L : i + L] for i in valid])  # shape (K, 2L)
    x_tilde = segs.mean(axis=0)
    # DC / AC 표준 공식 (Bauer 2006):
    # [x0 + x1 - x-1 - x-2] / 4 where x0 at index L
    idx0 = L
    val = (x_tilde[idx0] + x_tilde[idx0 + 1]
           - x_tilde[idx0 - 1] - x_tilde[idx0 - 2]) / 4.0
    return float(val)


# ──────────────────────────────────────────────
#  메인 함수
# ──────────────────────────────────────────────

def compute_time_domain(
    rr_ms: np.ndarray,
    nnxx_threshold_ms: float = NNXX_DEFAULT_MS,
    hr_window_beats: int = HR_WINDOW_DEFAULT,
    detrend_lambda: float = DETREND_LAMBDA_DEFAULT,
) -> TimeDomainResult:
    """RR 시계열(ms)로부터 Kubios 호환 Time-domain 지표를 산출.

    Kubios 규약: Mean/Min/Max HR과 Mean RR은 non-detrended 원본으로,
    그 외 통계 지표(SDNN, SD HR, RMSSD, Stress index, DC/AC, 히스토그램 지표)는
    smoothness priors detrending 적용 후 계산한다.
    """
    rr_ms = np.asarray(rr_ms, dtype=float)
    rr_ms = rr_ms[np.isfinite(rr_ms) & (rr_ms > 0)]
    if len(rr_ms) < 2:
        raise ValueError(f"RR 시계열이 너무 짧음: n={len(rr_ms)}")

    # Detrended RR (평균 보존). Kubios는 다수 지표를 이것 기반으로 계산.
    rr_det = smoothness_priors_detrend(rr_ms, lam=detrend_lambda)

    # ── non-detrended 통계 (Mean/Min/Max HR, Mean RR)
    mean_rr = float(np.mean(rr_ms))
    hr_bpm = 60000.0 / rr_ms
    mean_hr = float(np.mean(hr_bpm))

    # Min/Max HR: N-beat moving average (non-detrended)
    hr_ma = _moving_average(hr_bpm, hr_window_beats)
    min_hr = float(np.min(hr_ma))
    max_hr = float(np.max(hr_ma))

    # ── detrended 기반 변동성 지표
    sdnn = float(np.std(rr_det, ddof=1))
    hr_det = 60000.0 / rr_det
    sd_hr = float(np.std(hr_det, ddof=1))

    # RMSSD (detrended)
    d = np.diff(rr_det)
    rmssd = float(np.sqrt(np.mean(d ** 2)))

    # NN50 / pNN50 (detrended)
    nnxx = int(np.sum(np.abs(d) > nnxx_threshold_ms))
    pnnxx = 100.0 * nnxx / len(d) if len(d) > 0 else 0.0

    # Triangular index, TINN (detrended)
    tri_idx, tinn = _triangular_index_and_tinn(rr_det)

    # Stress index (detrended)
    si = _stress_index(rr_det)

    # DC, AC (detrended RR 기반)
    dc = _prsa(rr_det, T=PRSA_T_DEFAULT, L=PRSA_WIN_DEFAULT, anchor="dec")
    ac = _prsa(rr_det, T=PRSA_T_DEFAULT, L=PRSA_WIN_DEFAULT, anchor="acc")
    dc_mod = _prsa(rr_det, T=PRSA_T_DEFAULT, L=PRSA_WIN_MOD_DEFAULT, anchor="dec")
    ac_mod = _prsa(rr_det, T=PRSA_T_DEFAULT, L=PRSA_WIN_MOD_DEFAULT, anchor="acc")

    return TimeDomainResult(
        mean_rr_ms=mean_rr,
        sdnn_ms=sdnn,
        mean_hr_bpm=mean_hr,
        sd_hr_bpm=sd_hr,
        min_hr_bpm=min_hr,
        max_hr_bpm=max_hr,
        rmssd_ms=rmssd,
        nn50_count=nnxx,
        pnn50_pct=float(pnnxx),
        hrv_triangular_index=float(tri_idx),
        tinn_ms=float(tinn),
        stress_index=float(si),
        dc_ms=dc,
        ac_ms=ac,
        dc_mod_ms=dc_mod,
        ac_mod_ms=ac_mod,
    )
