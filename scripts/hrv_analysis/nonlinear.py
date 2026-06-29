"""HRV Nonlinear 지표 (Kubios 호환).

구현 범위 (1차):
    - Poincaré plot: SD1, SD2, SD2/SD1
    - Approximate Entropy (ApEn, m=2, r=0.2·SD)
    - Sample Entropy (SampEn, m=2, r=0.2·SD)
    - Detrended Fluctuation Analysis (DFA)
        α1 : 단기, 4~12 beats
        α2 : 장기, 13~64 beats

Kubios 설정 (CSV 기록):
    Entropy m = 2, tolerance = 0.2 × SD
    DFA short-term: 4-12 beats, long-term: 13-64 beats
    Apply detrending for nonlinear analysis: 1

향후 (v2): D2, Recurrence Plot Analysis(RPA), Multiscale Entropy(MSE).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd

from .detrend import smoothness_priors_detrend


ENTROPY_M_DEFAULT = 2
ENTROPY_R_SD_DEFAULT = 0.2
DFA_SHORT = (4, 12)
DFA_LONG  = (13, 64)
DETREND_LAMBDA_NONLINEAR = 100.0  # time-domain과 동일 캘리브레이션


@dataclass
class NonlinearResult:
    sd1_ms: float
    sd2_ms: float
    sd2_sd1: float
    apen: float
    sampen: float
    dfa_alpha1: float
    dfa_alpha2: float

    def as_table(self) -> pd.DataFrame:
        rows = [
            ("SD1 (ms)",      self.sd1_ms),
            ("SD2 (ms)",      self.sd2_ms),
            ("SD2/SD1",       self.sd2_sd1),
            ("ApEn",          self.apen),
            ("SampEn",        self.sampen),
            ("DFA α1",        self.dfa_alpha1),
            ("DFA α2",        self.dfa_alpha2),
        ]
        return pd.DataFrame(rows, columns=["Item", "Value"])


# ──────────────────────────────────────────────
#  Poincaré
# ──────────────────────────────────────────────

def _poincare_sd(rr_ms: np.ndarray) -> Tuple[float, float]:
    """SD1, SD2 계산.

    SD1² = 0.5 × Var(RR_{n+1} - RR_n)
    SD2² = 2·SDNN² - 0.5·Var(diff RR) = 2·SDNN² - SD1²
    """
    d = np.diff(rr_ms)
    sd1 = float(np.sqrt(0.5 * np.var(d, ddof=1)))
    sdnn = float(np.std(rr_ms, ddof=1))
    sd2_sq = 2.0 * sdnn ** 2 - sd1 ** 2
    sd2 = float(np.sqrt(max(sd2_sq, 0.0)))
    return sd1, sd2


# ──────────────────────────────────────────────
#  Entropy (ApEn, SampEn)
# ──────────────────────────────────────────────

def _phi(x: np.ndarray, m: int, r: float) -> float:
    """ApEn의 보조 함수 Φ^m(r)."""
    n = len(x)
    if n - m + 1 <= 0:
        return 0.0
    # 벡터들 생성 (n-m+1, m)
    X = np.array([x[i:i + m] for i in range(n - m + 1)])
    # Chebyshev distance (max abs diff) 를 각 쌍에 대해 계산
    # Broadcasting: (N, 1, m) vs (1, N, m)
    d = np.max(np.abs(X[:, None, :] - X[None, :, :]), axis=2)
    C = np.mean(d <= r, axis=1)  # self-match 포함
    C = np.where(C > 0, C, np.finfo(float).tiny)
    return float(np.mean(np.log(C)))


def approximate_entropy(rr: np.ndarray, m: int = ENTROPY_M_DEFAULT,
                        r_factor: float = ENTROPY_R_SD_DEFAULT) -> float:
    r = r_factor * float(np.std(rr, ddof=1))
    return float(_phi(rr, m, r) - _phi(rr, m + 1, r))


def sample_entropy(rr: np.ndarray, m: int = ENTROPY_M_DEFAULT,
                   r_factor: float = ENTROPY_R_SD_DEFAULT) -> float:
    n = len(rr)
    r = r_factor * float(np.std(rr, ddof=1))
    def _count_matches(mm: int) -> int:
        if n - mm <= 0:
            return 0
        X = np.array([rr[i:i + mm] for i in range(n - mm + 1)])
        d = np.max(np.abs(X[:, None, :] - X[None, :, :]), axis=2)
        # self-match 제외 (대각선)
        np.fill_diagonal(d, np.inf)
        return int(np.sum(d <= r) // 2)  # 대칭 쌍
    B = _count_matches(m)
    A = _count_matches(m + 1)
    if B == 0 or A == 0:
        return float("nan")
    return float(-np.log(A / B))


# ──────────────────────────────────────────────
#  DFA
# ──────────────────────────────────────────────

def _dfa_fluctuation(integ: np.ndarray, n: int) -> float:
    """스케일 n에서의 DFA fluctuation F(n)."""
    N = len(integ)
    if n < 4 or n > N // 2:
        return float("nan")
    k = N // n
    F_total = 0.0
    count = 0
    for v in range(k):
        seg = integ[v * n:(v + 1) * n]
        x_idx = np.arange(n)
        p = np.polyfit(x_idx, seg, 1)
        trend = np.polyval(p, x_idx)
        F_total += float(np.mean((seg - trend) ** 2))
        count += 1
    if count == 0:
        return float("nan")
    return float(np.sqrt(F_total / count))


def dfa(rr: np.ndarray,
        short_range: Tuple[int, int] = DFA_SHORT,
        long_range:  Tuple[int, int] = DFA_LONG) -> Tuple[float, float]:
    """DFA α1 (short), α2 (long) 계산.

    Kubios 기본: α1 4-12 beats, α2 13-64 beats.
    """
    x = np.asarray(rr, dtype=float)
    y = np.cumsum(x - np.mean(x))   # integrated profile

    def _alpha(lo: int, hi: int) -> float:
        scales = np.arange(lo, hi + 1)
        fns = np.array([_dfa_fluctuation(y, n) for n in scales])
        mask = np.isfinite(fns) & (fns > 0)
        if mask.sum() < 3:
            return float("nan")
        log_n = np.log10(scales[mask])
        log_f = np.log10(fns[mask])
        slope, _ = np.polyfit(log_n, log_f, 1)
        return float(slope)

    return _alpha(*short_range), _alpha(*long_range)


# ──────────────────────────────────────────────
#  메인
# ──────────────────────────────────────────────

def compute_nonlinear(
    rr_ms: np.ndarray,
    apply_detrend: bool = True,
    detrend_lambda: float = DETREND_LAMBDA_NONLINEAR,
) -> NonlinearResult:
    """Nonlinear HRV 지표 산출.

    Kubios 기본 설정 'Apply detrending for nonlinear analysis: 1' 에 따라
    기본적으로 detrending 적용.
    """
    rr = np.asarray(rr_ms, dtype=float)
    rr = rr[np.isfinite(rr) & (rr > 0)]
    if len(rr) < 20:
        raise ValueError(f"RR 시계열이 너무 짧음: n={len(rr)}")

    rr_used = smoothness_priors_detrend(rr, lam=detrend_lambda) if apply_detrend else rr

    sd1, sd2 = _poincare_sd(rr_used)
    sd2_sd1 = sd2 / sd1 if sd1 > 0 else float("nan")

    apen = approximate_entropy(rr_used)
    sampen = sample_entropy(rr_used)

    alpha1, alpha2 = dfa(rr_used)

    return NonlinearResult(
        sd1_ms=sd1,
        sd2_ms=sd2,
        sd2_sd1=sd2_sd1,
        apen=apen,
        sampen=sampen,
        dfa_alpha1=alpha1,
        dfa_alpha2=alpha2,
    )
