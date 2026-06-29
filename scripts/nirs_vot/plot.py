"""세션별 NIRS-VOT 시각화.

R 스크립트 그래프를 그대로 재현:
    - Raw 라인 (회색, 반투명)
    - Smoothed 라인 (검정, 굵게)
    - Oxygen Deficit 영역 (빨강, baseline 아래, occlusion 구간)
    - Reperfusion AUC 영역 (초록, baseline 위, deflation 이후)
    - Baseline hline (점선)
    - 4개 앵커 vline (점선)
    - Min/Peak 마커
"""

from __future__ import annotations
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .metrics import MetricsResult


def plot_session(
    df_smooth: pd.DataFrame,
    result: MetricsResult,
    save_path: str | Path | None = None,
    figsize: tuple[float, float] = (12, 5),
) -> plt.Figure:
    """한 세션 분석 결과를 그림으로 출력."""
    s = result.anchors_abs["s"]
    i = result.anchors_abs["i"]
    d = result.anchors_abs["d"]
    e = result.anchors_abs["e"]

    seg = df_smooth[(df_smooth["datetime"] >= s) & (df_smooth["datetime"] <= e)].copy()

    fig, ax = plt.subplots(figsize=figsize)

    # Oxygen Deficit ribbon (빨강, base 아래만)
    occ = seg[(seg["datetime"] >= i) & (seg["datetime"] <= d)]
    if not occ.empty:
        ax.fill_between(
            occ["datetime"],
            np.minimum(occ["SmO2_smooth"], result.baseline_smo2),
            result.baseline_smo2,
            where=(occ["SmO2_smooth"] < result.baseline_smo2),
            color="red", alpha=0.3, label="Oxygen Deficit",
        )

    # Hyperemia ribbon (초록, base 위만, deflation 이후)
    rep = seg[(seg["datetime"] >= d) & (seg["datetime"] <= e)]
    if not rep.empty:
        ax.fill_between(
            rep["datetime"],
            result.baseline_smo2,
            np.maximum(rep["SmO2_smooth"], result.baseline_smo2),
            where=(rep["SmO2_smooth"] > result.baseline_smo2),
            color="green", alpha=0.3, label="Hyperemia (AUC 3min)",
        )

    # Raw 와 Smoothed
    ax.plot(seg["datetime"], seg["SmO2_raw"],
            color="grey", alpha=0.35, linewidth=1, label="Raw")
    ax.plot(seg["datetime"], seg["SmO2_smooth"],
            color="black", linewidth=1.6, label="Smoothed (5s)")

    # Baseline hline
    ax.axhline(result.baseline_smo2, color="black", linestyle="--", linewidth=0.9,
               alpha=0.7, label=f"Baseline {result.baseline_smo2:.1f}%")

    # Anchor vlines
    for label, t in [("start", s), ("inflate", i), ("deflate", d), ("end", e)]:
        ax.axvline(t, color="grey", linestyle=":", linewidth=0.9, alpha=0.7)
        ax.text(t, ax.get_ylim()[1], label,
                rotation=90, ha="right", va="top", fontsize=8, color="grey")

    # Min / Peak 마커
    if pd.notna(result.min_time):
        ax.scatter([result.min_time], [result.min_smo2],
                   color="blue", s=70, zorder=5, label=f"Min {result.min_smo2:.1f}%")
    if pd.notna(result.peak_time):
        ax.scatter([result.peak_time], [result.peak_smo2],
                   color="red", s=70, zorder=5, label=f"Peak {result.peak_smo2:.1f}%")

    ax.set_title(
        f"NIRS-VOT  |  {result.condition}  |  {result.session}\n"
        f"Magnitude {result.magnitude:.1f}%  "
        f"Slope1(0-60s) {result.slope1_0_60:.3f}%/s  "
        f"Slope2(0-10s) {result.slope2_0_10:.3f}%/s  "
        f"T50 {result.t50_sec:.1f}s  T95 {result.t95_sec:.1f}s"
    )
    ax.set_xlabel("Time")
    ax.set_ylabel("SmO2 (%)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S", tz=s.tz))
    ax.legend(loc="lower right", fontsize=8, ncol=2)
    fig.autofmt_xdate()
    fig.tight_layout()

    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=130)
    return fig
