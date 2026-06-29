"""Tarvainen smoothness priors detrending.

Reference: Tarvainen, Ranta-aho & Karjalainen (2002),
  "An advanced detrending method with application to HRV analysis",
  IEEE Trans Biomed Eng 49(2):172-175.

Kubios HRV Scientific 기본 λ=500 (CSV 파라미터 'Smoothn priors (lambda: 500)').

공식 (z: RR 시퀀스, 길이 N):
    trend_hat   = (I + λ² D₂ᵀ D₂)⁻¹ z
    stationary  = z - trend_hat

D₂ 는 2차 차분 연산자 (N-2, N) 행렬.
"""

from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve


def smoothness_priors_detrend(rr: np.ndarray, lam: float = 500.0) -> np.ndarray:
    """RR 시퀀스에서 long-term trend를 제거한다. 평균은 복원해 반환.

    Args:
        rr:  RR intervals (numpy array, 길이 N). ms 또는 s 어느 단위든 가능.
        lam: 정규화 강도 (Kubios 기본 500).

    Returns:
        detrended RR with preserved mean (같은 단위).
    """
    z = np.asarray(rr, dtype=float)
    n = len(z)
    if n < 4:
        return z.copy()

    # 2차 차분 연산자 D2: shape (n-2, n)
    # D2 row i: [0..0, 1, -2, 1, 0..0]
    diagonals = [
        np.ones(n - 2),
        -2 * np.ones(n - 2),
        np.ones(n - 2),
    ]
    D2 = sparse.diags(diagonals, offsets=[0, 1, 2], shape=(n - 2, n), format="csc")

    I = sparse.eye(n, format="csc")
    A = I + (lam ** 2) * (D2.T @ D2)

    trend = spsolve(A, z)
    return z - trend + float(np.mean(z))  # 평균 복원
