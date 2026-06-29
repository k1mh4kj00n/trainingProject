"""HRV Frequency-Domain 지표 (Kubios 호환).

파이프라인 (Kubios CSV 파라미터 기반):
    1. RR 시계열을 4 Hz로 cubic spline 보간
    2. Smoothness priors detrending (λ=100, Kubios λ=500 등가)
    3. Welch periodogram (window 300s, 50% overlap, Hann)
    4. 주파수 대역 전력 적분 (trapezoid)

기본 대역 (Kubios default):
    VLF : 0    - 0.04 Hz
    LF  : 0.04 - 0.15 Hz
    HF  : 0.15 - 0.4  Hz

산출 지표:
    - Peak frequency per band
    - Absolute power per band (ms², log)
    - Relative power per band (%)
    - Normalized units (LF/HF n.u.)
    - Total power (0~0.4 Hz)
    - LF/HF ratio
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd
from scipy import signal
from scipy.interpolate import CubicSpline

from .detrend import smoothness_priors_detrend


INTERP_RATE_HZ = 4.0
WELCH_WINDOW_SEC = 300.0
WELCH_OVERLAP = 0.5

# Frequency-domain은 smoothness priors detrending λ=500이 Kubios 보고값과
# 가장 잘 맞음 (LF/HF ratio 0.4% 오차, LF power 0.2% 오차).
# Time-domain의 λ=100과 다른 것은, 우리 detrend 구현이
# time/freq 잔차에 다른 영향을 주기 때문.
FREQ_DETREND_LAMBDA = 500.0

VLF_BAND = (0.0, 0.04)
LF_BAND  = (0.04, 0.15)
HF_BAND  = (0.15, 0.4)


@dataclass
class BandPower:
    name: str
    lo: float
    hi: float
    peak_hz: float
    power_ms2: float
    power_log: float
    power_pct: float    # 전체 전력 대비 %
    power_nu: float     # normalized units (LF/HF only)


@dataclass
class FreqDomainResult:
    vlf: BandPower
    lf: BandPower
    hf: BandPower
    total_power_ms2: float
    lf_hf_ratio: float
    freqs: np.ndarray
    psd: np.ndarray

    def as_table(self) -> pd.DataFrame:
        rows = [
            ("VLF peak (Hz)",  self.vlf.peak_hz),
            ("LF peak (Hz)",   self.lf.peak_hz),
            ("HF peak (Hz)",   self.hf.peak_hz),
            ("VLF power (ms²)",self.vlf.power_ms2),
            ("LF power (ms²)", self.lf.power_ms2),
            ("HF power (ms²)", self.hf.power_ms2),
            ("VLF log",        self.vlf.power_log),
            ("LF log",         self.lf.power_log),
            ("HF log",         self.hf.power_log),
            ("VLF (%)",        self.vlf.power_pct),
            ("LF (%)",         self.lf.power_pct),
            ("HF (%)",         self.hf.power_pct),
            ("LF (n.u.)",      self.lf.power_nu),
            ("HF (n.u.)",      self.hf.power_nu),
            ("Total power (ms²)", self.total_power_ms2),
            ("LF/HF ratio",    self.lf_hf_ratio),
        ]
        return pd.DataFrame(rows, columns=["Item", "Value"])


# ──────────────────────────────────────────────
#  보간
# ──────────────────────────────────────────────

def _interpolate_rr_uniform(
    t_s: np.ndarray, rr_s: np.ndarray, fs: float = INTERP_RATE_HZ
) -> Tuple[np.ndarray, np.ndarray]:
    """RR 시계열(불균등)을 균등 샘플 시계열로 cubic spline 보간.

    t_s:    RR 절대 시간 (초)
    rr_s:   RR 간격 (초)
    fs:     보간 후 샘플링 레이트 (Hz)

    Returns:
        (t_uniform, rr_interp_s) — 균등 간격 시계열
    """
    # 시작을 0부터로 정규화
    t0 = t_s[0]
    t_rel = t_s - t0

    n_samples = int(np.floor(t_rel[-1] * fs)) + 1
    t_uniform = np.arange(n_samples) / fs

    cs = CubicSpline(t_rel, rr_s, bc_type="natural")
    rr_interp = cs(t_uniform)
    return t_uniform, rr_interp


# ──────────────────────────────────────────────
#  Welch PSD + 대역 전력
# ──────────────────────────────────────────────

def _integrate_band(freqs: np.ndarray, psd: np.ndarray,
                    lo: float, hi: float) -> Tuple[float, float]:
    """대역 내 trapezoid 적분 + 피크 주파수."""
    mask = (freqs >= lo) & (freqs <= hi)
    if not np.any(mask):
        return 0.0, np.nan
    f_band = freqs[mask]
    p_band = psd[mask]
    if len(f_band) < 2:
        return 0.0, float(f_band[0]) if len(f_band) else np.nan
    power = float(np.trapezoid(p_band, f_band))
    peak = float(f_band[int(np.argmax(p_band))])
    return power, peak


def compute_freq_domain(
    rr_times_s: np.ndarray,
    rr_intervals_s: np.ndarray,
    vlf: Tuple[float, float] = VLF_BAND,
    lf: Tuple[float, float] = LF_BAND,
    hf: Tuple[float, float] = HF_BAND,
    interp_fs: float = INTERP_RATE_HZ,
    window_sec: float = WELCH_WINDOW_SEC,
    overlap_frac: float = WELCH_OVERLAP,
    detrend_lambda: float = FREQ_DETREND_LAMBDA,
) -> FreqDomainResult:
    """RR 시계열로부터 Kubios 호환 Frequency-domain 지표 산출.

    입력 RR은 초 단위. 내부적으로 ms²/Hz 스케일 PSD를 산출하기 위해
    *ms 단위 RR* 신호에 Welch를 적용한다.
    """
    t = np.asarray(rr_times_s, dtype=float)
    rr_s = np.asarray(rr_intervals_s, dtype=float)

    if len(t) != len(rr_s) or len(t) < 4:
        raise ValueError(f"invalid RR series: n={len(t)}")

    # 1) 보간 → 균등 4Hz 시계열 (초 단위) → ms
    t_uni, rr_uni_s = _interpolate_rr_uniform(t, rr_s, fs=interp_fs)
    rr_uni_ms = rr_uni_s * 1000.0

    # 2) Smoothness priors detrending (Kubios λ=500)
    rr_det_ms = smoothness_priors_detrend(rr_uni_ms, lam=detrend_lambda)

    # 3) Welch PSD. nperseg는 window_sec × fs, 너무 크면 데이터 길이에 맞춰 축소.
    nperseg = int(window_sec * interp_fs)
    nperseg = min(nperseg, len(rr_det_ms))
    noverlap = int(nperseg * overlap_frac)

    freqs, psd = signal.welch(
        rr_det_ms,
        fs=interp_fs,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        detrend="constant",
        scaling="density",
    )

    # 4) 대역 전력 및 피크
    vlf_pow, vlf_peak = _integrate_band(freqs, psd, *vlf)
    lf_pow,  lf_peak  = _integrate_band(freqs, psd, *lf)
    hf_pow,  hf_peak  = _integrate_band(freqs, psd, *hf)
    total_power = vlf_pow + lf_pow + hf_pow

    def pct(p: float) -> float:
        return 100.0 * p / total_power if total_power > 0 else 0.0

    def nu(p: float) -> float:
        denom = total_power - vlf_pow
        return 100.0 * p / denom if denom > 0 else 0.0

    def safe_log(p: float) -> float:
        return float(np.log(p)) if p > 0 else float("nan")

    vlf_bp = BandPower("VLF", *vlf, vlf_peak, vlf_pow, safe_log(vlf_pow),
                       pct(vlf_pow), 0.0)
    lf_bp  = BandPower("LF",  *lf,  lf_peak,  lf_pow,  safe_log(lf_pow),
                       pct(lf_pow),  nu(lf_pow))
    hf_bp  = BandPower("HF",  *hf,  hf_peak,  hf_pow,  safe_log(hf_pow),
                       pct(hf_pow),  nu(hf_pow))

    lf_hf = lf_pow / hf_pow if hf_pow > 0 else float("nan")

    return FreqDomainResult(
        vlf=vlf_bp, lf=lf_bp, hf=hf_bp,
        total_power_ms2=total_power,
        lf_hf_ratio=lf_hf,
        freqs=freqs,
        psd=psd,
    )
