"""전처리: 0.5초 격자 정렬 + 5초 center 이동평균 스무딩.

R 스크립트(NIRS_VOT_분석용.R) L82-L107 로직과 동일한 동작을 재현한다:
    - 같은 datetime에 여러 샘플이 있으면 0.5초씩 shift해 유일한 격자로 정렬
    - 샘플링 간격 추정 후 5초 윈도우 크기를 홀수로 계산
    - rolling(center=True) 평균을 'SmO2_smooth' 컬럼으로 기록
    - 양 끝의 결측(window 절반)은 제거
"""

from __future__ import annotations
import numpy as np
import pandas as pd

SMOOTH_WINDOW_SEC = 5.0


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """0.5초 격자 정렬 + 5초 스무딩을 적용한 새 DataFrame을 반환.

    입력 DataFrame은 load_calf_csv의 출력 형태여야 한다.
    """
    df = df.sort_values("datetime_raw").reset_index(drop=True).copy()

    # 같은 datetime이 여러 번 나오면 0, 0.5, 1.0 ... 초씩 오프셋
    dup_idx = df.groupby("datetime_raw").cumcount()
    df["datetime"] = df["datetime_raw"] + pd.to_timedelta(dup_idx * 0.5, unit="s")
    df = df.dropna(subset=["datetime"]).reset_index(drop=True)

    # 샘플링 간격 추정 (초)
    diffs = df["datetime"].diff().dt.total_seconds().dropna()
    avg_diff = float(diffs.mean()) if not diffs.empty else 1.0
    if not np.isfinite(avg_diff) or avg_diff <= 0:
        avg_diff = 1.0

    window_size = max(3, int(round(SMOOTH_WINDOW_SEC / avg_diff)))
    if window_size % 2 == 0:
        window_size += 1

    df["SmO2_raw"] = df["SmO2_live"].astype(float)
    df["SmO2_smooth"] = (
        df["SmO2_raw"]
        .rolling(window=window_size, center=True, min_periods=window_size)
        .mean()
    )
    df = df.dropna(subset=["SmO2_smooth"]).reset_index(drop=True)

    df.attrs["sampling_interval_sec"] = avg_diff
    df.attrs["smooth_window_samples"] = window_size
    return df
