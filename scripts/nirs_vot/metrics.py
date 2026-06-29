"""NIRS-VOT 표준 지표 12종 산출.

R 스크립트 NIRS_VOT_분석용.R 의 지표 로직을 1:1 포팅했다.

산출 지표:
    1.  Baseline SmO2        (%, start~inflate의 0-60초 평균)
    2.  Slope1 (0-60s)       (%/s, occlusion 초반 desaturation slope)
    3.  Slope1 (30-150s)     (%/s, occlusion 중반 desaturation slope)
    4.  Oxy Deficit (%·s)    (occlusion 구간에서 baseline 아래 AUC)
    5.  Min SmO2 (%)         (occlusion 구간 최소값)
    6.  Peak SmO2 (%)        (reperfusion 구간 최대값)
    7.  Magnitude (%)        (Peak - Min)
    8.  Slope2 (0-10s)       (%/s, deflation 직후 10초 resaturation slope)
    9.  Slope2 (0-30s)       (%/s, deflation 직후 30초 resaturation slope)
    10. T50 (s)              (min 이후 magnitude의 50% 회복까지 소요 시간)
    11. T95 (s)              (min 이후 magnitude의 95% 회복까지 소요 시간)
    12. AUC 3min (%·min)     (deflation 이후 3분간 baseline 초과 AUC)
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional
import math

import numpy as np
import pandas as pd

from .anchors import Anchor

# NumPy 2.0에서 trapz가 trapezoid로 개명됨. 1.x 호환 shim.
if not hasattr(np, "trapezoid"):
    np.trapezoid = np.trapz  # type: ignore[attr-defined]


@dataclass
class MetricsResult:
    condition: str
    session: str
    baseline_smo2: float
    slope1_0_60: float
    slope1_30_150: float
    oxy_deficit: float
    min_smo2: float
    peak_smo2: float
    magnitude: float
    slope2_0_10: float
    slope2_0_30: float
    t50_sec: float
    t95_sec: float
    auc_3min: float
    # 추가 맥락 (그래프용)
    anchors_abs: dict
    min_time: pd.Timestamp
    peak_time: pd.Timestamp

    def as_table(self) -> pd.DataFrame:
        rows = [
            ("Baseline SmO2 (%)",       self.baseline_smo2),
            ("Slope1 0-60s (%/s)",      self.slope1_0_60),
            ("Slope1 30-150s (%/s)",    self.slope1_30_150),
            ("Oxy Deficit (%·s)",       self.oxy_deficit),
            ("Min SmO2 (%)",            self.min_smo2),
            ("Peak SmO2 (%)",           self.peak_smo2),
            ("Magnitude (%)",           self.magnitude),
            ("Slope2 0-10s (%/s)",      self.slope2_0_10),
            ("Slope2 0-30s (%/s)",      self.slope2_0_30),
            ("T50 (s)",                 self.t50_sec),
            ("T95 (s)",                 self.t95_sec),
            ("AUC 3min (%·min)",        self.auc_3min),
        ]
        return pd.DataFrame(rows, columns=["Item", "Value"])


def _parse_clock(anchor_date: pd.Timestamp, clock: str) -> pd.Timestamp:
    ts = pd.to_datetime(f"{anchor_date.date()} {clock}")
    return ts.tz_localize("Asia/Seoul")


def _linreg_slope(x_sec: np.ndarray, y: np.ndarray) -> float:
    if len(x_sec) < 2:
        return math.nan
    m, _ = np.polyfit(x_sec, y, 1)
    return float(m)


def _resolve_anchors(df: pd.DataFrame, anchor: Anchor) -> dict:
    anchor_date = df["datetime"].iloc[0]
    return {
        "s": _parse_clock(anchor_date, anchor.start),
        "i": _parse_clock(anchor_date, anchor.inflate),
        "d": _parse_clock(anchor_date, anchor.deflate),
        "e": _parse_clock(anchor_date, anchor.end),
    }


def _slice(df: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp) -> pd.DataFrame:
    return df[(df["datetime"] >= t0) & (df["datetime"] <= t1)]


def _interp_crossing(
    t_arr: np.ndarray, y_arr: np.ndarray, target: float, after_t: float, end_t: float
) -> Optional[float]:
    mask = (t_arr >= after_t) & (t_arr <= end_t)
    tx, ty = t_arr[mask], y_arr[mask]
    if len(tx) < 2:
        return None
    for k in range(len(tx) - 1):
        y0, y1 = ty[k], ty[k + 1]
        if y0 <= target <= y1:
            if y1 == y0:
                return float(tx[k])
            frac = (target - y0) / (y1 - y0)
            return float(tx[k] + frac * (tx[k + 1] - tx[k]))
    return None


def _trapz_under_baseline(x: np.ndarray, y: np.ndarray, base: float) -> float:
    """baseline 아래 영역의 양수 면적(Oxygen Deficit)."""
    deficit = np.clip(base - y, a_min=0, a_max=None)
    if len(x) < 2:
        return 0.0
    return float(np.trapezoid(deficit, x))


def _trapz_above_baseline(x: np.ndarray, y: np.ndarray, base: float) -> float:
    """baseline 초과 영역 면적(Hyperemia AUC). 단위는 sec 기반."""
    surplus = np.clip(y - base, a_min=0, a_max=None)
    if len(x) < 2:
        return 0.0
    return float(np.trapezoid(surplus, x))


def _smoothed_at(df_smooth: pd.DataFrame, t: pd.Timestamp) -> float:
    """주어진 시점에서 ``SmO2_smooth`` 의 선형 보간 값."""
    if t is None or pd.isna(t):
        return math.nan
    x_all = df_smooth["datetime"].astype("int64").to_numpy() / 1e9
    y_all = df_smooth["SmO2_smooth"].to_numpy()
    if len(x_all) == 0:
        return math.nan
    return float(np.interp(float(t.timestamp()), x_all, y_all))


def find_extremum_by_gradient(
    df_smooth: pd.DataFrame,
    t_start: pd.Timestamp,
    t_end: pd.Timestamp,
    kind: str = "min",
    *,
    lr: float = 1.0,
    max_iter: int = 300,
    h_sec: float = 0.5,
    tol: float = 1e-3,
) -> tuple[Optional[pd.Timestamp], float]:
    """[t_start, t_end] 구간에서 SmO2_smooth 의 local extremum 을 gradient 기반 탐색.

    절차:
        1) 그리드 argmin (또는 argmax) 위치를 초기 추정점 t0 로 잡음.
        2) 매 iteration:
             grad ≈ (y(t+h) - y(t-h)) / (2h)         # finite difference
             t  ←  t  -  sign · lr · grad             # min: descent, max: ascent
           (sign=+1 for min, sign=-1 for max).
        3) 변화량 < tol 또는 max_iter 도달 시 종료. 구간 밖 이탈 시 클램프.

    SmO2 가 5초 이동평균으로 이미 smooth 되어 있어 단순 argmin/argmax 와 거의 동일하지만,
    gradient 기반은 보간 곡선 위에서 더 정밀한 시점을 산출 (격자 해상도 약 0.5 s ).

    반환: (timestamp 또는 None, value)
    """
    seg = df_smooth[(df_smooth["datetime"] >= t_start)
                    & (df_smooth["datetime"] <= t_end)]
    if seg.empty or len(seg) < 3:
        return None, math.nan

    x = seg["datetime"].astype("int64").to_numpy() / 1e9  # epoch seconds
    y = seg["SmO2_smooth"].to_numpy()

    # 초기 위치 — 그리드 argmin/argmax
    if kind == "min":
        idx0 = int(np.argmin(y))
        sign = +1.0  # gradient descent
    elif kind in ("max", "peak"):
        idx0 = int(np.argmax(y))
        sign = -1.0  # gradient ascent (= -grad 방향)
    else:
        raise ValueError(f"unknown kind: {kind!r}")

    t_curr = float(x[idx0])
    x_lo, x_hi = float(x[0]), float(x[-1])

    for _ in range(max_iter):
        # finite difference (양옆 ±h_sec). 경계 클램프.
        t_plus = min(t_curr + h_sec, x_hi)
        t_minus = max(t_curr - h_sec, x_lo)
        if t_plus == t_minus:
            break
        y_plus = float(np.interp(t_plus, x, y))
        y_minus = float(np.interp(t_minus, x, y))
        grad = (y_plus - y_minus) / (t_plus - t_minus)

        # learning rate 동적 조정 — 그라디언트 단위가 %/s 라 lr=1 정도가 적정
        step = sign * lr * grad
        t_new = t_curr - step
        # 구간 밖 이탈 방지
        t_new = max(x_lo, min(x_hi, t_new))
        if abs(t_new - t_curr) < tol:
            t_curr = t_new
            break
        t_curr = t_new

    y_final = float(np.interp(t_curr, x, y))
    tz = df_smooth["datetime"].iloc[0].tz
    ts = pd.Timestamp(int(round(t_curr * 1e9)), tz=tz)
    return ts, y_final


def find_extremum_by_sgd(
    df_smooth: pd.DataFrame,
    t_start: pd.Timestamp,
    t_end: pd.Timestamp,
    kind: str = "min",
    *,
    n_starts: int = 12,
    max_iter: int = 200,
    lr: float = 1.5,
    noise_sigma: float = 0.6,
    h_sec: float = 0.5,
    seed: int | None = 42,
) -> tuple[Optional[pd.Timestamp], float]:
    """확률적 경사 하강법 (SGD) — multi-start + Gaussian noise 주입.

    동작:
        for s in range(n_starts):
            구간 내 균등 분포에서 random 초기점 t0 ~ Uniform(t_start, t_end).
            for it in range(max_iter):
                grad ≈ (y(t+h) - y(t-h)) / (2h)
                noise ~ N(0, σ²) · (1 − it/max_iter)        # noise decay
                lr_t = lr · (1 − 0.5 · it/max_iter)          # lr decay
                t  ←  t  -  sign · lr_t · grad  -  sign · noise
                t  ←  clamp(t, t_start, t_end)
            기록 (t_final, y_final).
        모든 시작점 결과 중 best (min 의 경우 가장 작은 y, max 의 경우 가장 큰 y) 선택.

    GD 단일 시작점이 noise 또는 평탄 구간에 갇히는 케이스를 multi-start + 확률적 jump 로
    탈출. Gaussian noise 는 초기엔 크고 후반에 작아져 simulated annealing 효과.

    seed 를 None 으로 주면 매 호출마다 다른 결과 (truly stochastic). 기본 42 — 재현성.
    """
    seg = df_smooth[(df_smooth["datetime"] >= t_start)
                    & (df_smooth["datetime"] <= t_end)]
    if seg.empty or len(seg) < 3:
        return None, math.nan

    x = seg["datetime"].astype("int64").to_numpy() / 1e9
    y = seg["SmO2_smooth"].to_numpy()
    x_lo, x_hi = float(x[0]), float(x[-1])

    if kind == "min":
        sign = +1.0
        best_y = math.inf
    elif kind in ("max", "peak"):
        sign = -1.0
        best_y = -math.inf
    else:
        raise ValueError(f"unknown kind: {kind!r}")

    rng = np.random.default_rng(seed)
    best_t: Optional[float] = None

    for _ in range(n_starts):
        # 균등 분포 random 시작점 + 그리드 argmin 도 한 번 포함 (좋은 초기치 보장)
        t_curr = float(rng.uniform(x_lo, x_hi))

        for it in range(max_iter):
            t_plus = min(t_curr + h_sec, x_hi)
            t_minus = max(t_curr - h_sec, x_lo)
            if t_plus == t_minus:
                break
            y_plus = float(np.interp(t_plus, x, y))
            y_minus = float(np.interp(t_minus, x, y))
            grad = (y_plus - y_minus) / (t_plus - t_minus)

            decay = 1.0 - it / max_iter
            lr_t = lr * (1.0 - 0.5 * it / max_iter)
            noise = float(rng.normal(0.0, noise_sigma)) * decay

            step = sign * lr_t * grad + sign * noise
            t_new = t_curr - step
            t_new = max(x_lo, min(x_hi, t_new))
            t_curr = t_new

        y_final = float(np.interp(t_curr, x, y))
        if kind == "min" and y_final < best_y:
            best_y = y_final
            best_t = t_curr
        elif kind in ("max", "peak") and y_final > best_y:
            best_y = y_final
            best_t = t_curr

    # 그리드 argmin/argmax 를 한 번 더 비교 (최후의 안전망)
    if kind == "min":
        idx0 = int(np.argmin(y))
        if y[idx0] < best_y:
            best_y = float(y[idx0])
            best_t = float(x[idx0])
    else:
        idx0 = int(np.argmax(y))
        if y[idx0] > best_y:
            best_y = float(y[idx0])
            best_t = float(x[idx0])

    if best_t is None:
        return None, math.nan
    tz = df_smooth["datetime"].iloc[0].tz
    ts = pd.Timestamp(int(round(best_t * 1e9)), tz=tz)
    return ts, best_y


def find_extremum_by_de(
    df_smooth: pd.DataFrame,
    t_start: pd.Timestamp,
    t_end: pd.Timestamp,
    kind: str = "min",
    *,
    maxiter: int = 200,
    tol: float = 1e-7,
    seed: int | None = 42,
) -> tuple[Optional[pd.Timestamp], float]:
    """Differential Evolution global optimizer (scipy).

    1D 시계열에서 진짜 global extremum 을 찾는 가장 robust 한 알고리즘. 여러 후보
    population 을 유지하며 mutation/crossover 로 진화 → local minimum 에 갇히지 않음.
    SciPy 의 ``differential_evolution`` 은 마지막에 polish=True 로 L-BFGS-B 로 미세 조정도 수행.
    """
    seg = df_smooth[(df_smooth["datetime"] >= t_start)
                    & (df_smooth["datetime"] <= t_end)]
    if seg.empty or len(seg) < 3:
        return None, math.nan

    x = seg["datetime"].astype("int64").to_numpy() / 1e9
    y = seg["SmO2_smooth"].to_numpy()

    if kind == "min":
        def obj(t):
            return float(np.interp(float(t[0]), x, y))
    elif kind in ("max", "peak"):
        def obj(t):
            return -float(np.interp(float(t[0]), x, y))
    else:
        raise ValueError(f"unknown kind: {kind!r}")

    try:
        from scipy.optimize import differential_evolution
    except ImportError:
        return None, math.nan

    bounds = [(float(x[0]), float(x[-1]))]
    try:
        result = differential_evolution(
            obj, bounds=bounds,
            maxiter=maxiter, tol=tol, seed=seed,
            polish=True,
            popsize=20,
            mutation=(0.5, 1.5),
            recombination=0.85,
        )
    except Exception:  # noqa: BLE001
        return None, math.nan

    t_best = float(result.x[0])
    y_best = float(np.interp(t_best, x, y))
    tz = df_smooth["datetime"].iloc[0].tz
    ts = pd.Timestamp(int(round(t_best * 1e9)), tz=tz)
    return ts, y_best


def find_extremum_robust(
    df_smooth: pd.DataFrame,
    t_start: pd.Timestamp,
    t_end: pd.Timestamp,
    kind: str = "min",
) -> tuple[Optional[pd.Timestamp], float, str]:
    """GD + SGD + DE 모두 시도해 가장 정확한 결과 반환.

    Differential Evolution 은 1D global optimization 의 표준으로 quasi-convex 가정 없이
    진짜 global extremum 을 찾는다. SGD multi-start 는 빠른 보조, GD 는 baseline.
    SmO2 시계열은 smoothed 되어있어도 multi-modal 일 수 있어 (deflation 직후 dip 등),
    DE 가 가장 robust.

    반환: (timestamp, value, method)  — method ∈ {"GD", "SGD", "DE"}
    """
    gd_t, gd_v = find_extremum_by_gradient(df_smooth, t_start, t_end, kind=kind)
    sgd_t, sgd_v = find_extremum_by_sgd(df_smooth, t_start, t_end, kind=kind)
    de_t, de_v = find_extremum_by_de(df_smooth, t_start, t_end, kind=kind)

    candidates = []
    if gd_t is not None and not math.isnan(gd_v):
        candidates.append(("GD", gd_t, gd_v))
    if sgd_t is not None and not math.isnan(sgd_v):
        candidates.append(("SGD", sgd_t, sgd_v))
    if de_t is not None and not math.isnan(de_v):
        candidates.append(("DE", de_t, de_v))

    if not candidates:
        return None, math.nan, "NONE"

    # min 은 작은 v, max 는 큰 v 우선. 동일하면 DE > SGD > GD 순 (정확도 우선)
    priority = {"DE": 0, "SGD": 1, "GD": 2}
    if kind == "min":
        candidates.sort(key=lambda c: (c[2], priority[c[0]]))
    else:
        candidates.sort(key=lambda c: (-c[2], priority[c[0]]))
    method, t_best, v_best = candidates[0]
    return t_best, v_best, method


def compute_metrics(
    df_smooth: pd.DataFrame,
    anchor: Anchor,
    condition: str,
    session: str,
    *,
    override_baseline: float | None = None,
    override_min_time: pd.Timestamp | None = None,
    override_peak_time: pd.Timestamp | None = None,
) -> MetricsResult:
    """스무딩된 전체 DataFrame과 세션 앵커로 12개 지표를 계산한다.

    인자 ``override_*`` 가 주어지면 자동 검출 대신 그 값을 사용 (사용자가 그래프에서
    드래그해 직접 지정한 값을 반영). Min/Peak time 은 그 시각의 ``SmO2_smooth`` 보간으로
    값(y) 도 자동 결정. 의존 지표(magnitude·T50·T95·oxy_deficit·AUC) 모두 재계산.
    """
    anchors_abs = _resolve_anchors(df_smooth, anchor)
    s, i, d, e = anchors_abs["s"], anchors_abs["i"], anchors_abs["d"], anchors_abs["e"]

    res = _slice(df_smooth, s, e).copy()
    if res.empty:
        raise ValueError(
            f"세션 구간에 데이터가 없음: {condition}/{session} "
            f"(앵커 {s} ~ {e}, 파일 범위 {df_smooth['datetime'].min()} ~ {df_smooth['datetime'].max()})"
        )
    res["t_rel_sec"] = np.where(
        res["datetime"] < i,
        (res["datetime"] - s).dt.total_seconds(),
        np.where(
            res["datetime"] < d,
            (res["datetime"] - i).dt.total_seconds(),
            (res["datetime"] - d).dt.total_seconds(),
        ),
    )

    # ---- Baseline SmO2: start->inflate 첫 60초 평균 (또는 사용자 override)
    if override_baseline is not None and np.isfinite(override_baseline):
        base_val = float(override_baseline)
    else:
        pre = res[(res["datetime"] >= s) & (res["datetime"] < i)]
        pre60 = pre[pre["t_rel_sec"] <= 60]
        base_val = float(pre60["SmO2_smooth"].mean()) if not pre60.empty else math.nan

    # ---- 전체 배열 (보간용)
    x_all = res["datetime"].astype("int64").to_numpy() / 1e9   # 초 단위 epoch
    y_all = res["SmO2_smooth"].to_numpy()

    i_sec = i.timestamp()
    d_sec = d.timestamp()
    e_sec = e.timestamp()

    # ---- Slope1 (desaturation)
    def slope1(offset: float, duration: float) -> float:
        t0 = i + pd.to_timedelta(offset, unit="s")
        t1 = i + pd.to_timedelta(offset + duration, unit="s")
        sub = _slice(res, t0, t1)
        if len(sub) < 2:
            return math.nan
        x = (sub["datetime"] - i).dt.total_seconds().to_numpy()
        y = sub["SmO2_smooth"].to_numpy()
        return _linreg_slope(x, y)

    slope1_0_60 = slope1(0, 60)
    slope1_30_150 = slope1(30, 120)  # 30~150s

    # ---- Oxygen Deficit: occlusion 구간 (i~d) baseline 아래 AUC
    occ_mask = (x_all >= i_sec) & (x_all <= d_sec)
    x_occ = x_all[occ_mask]
    y_occ = y_all[occ_mask]
    # 경계점 보간으로 추가
    x_grid = np.unique(np.concatenate(([i_sec], x_occ, [d_sec])))
    y_grid = np.interp(x_grid, x_all, y_all)
    oxy_deficit = _trapz_under_baseline(x_grid, y_grid, base_val)

    # ---- Min / Peak / Magnitude (override 시 그 시점의 보간 값 사용)
    occ = res[(res["datetime"] >= i) & (res["datetime"] < d)]
    rep = res[(res["datetime"] >= d) & (res["datetime"] <= e)]

    if override_min_time is not None and not pd.isna(override_min_time):
        min_time = pd.Timestamp(override_min_time)
        min_smo2 = _smoothed_at(df_smooth, min_time)
    elif not occ.empty:
        min_smo2 = float(occ["SmO2_smooth"].min())
        min_time = occ.loc[occ["SmO2_smooth"].idxmin(), "datetime"]
    else:
        min_smo2 = math.nan
        min_time = pd.NaT

    if override_peak_time is not None and not pd.isna(override_peak_time):
        peak_time = pd.Timestamp(override_peak_time)
        peak_smo2 = _smoothed_at(df_smooth, peak_time)
    elif not rep.empty:
        peak_smo2 = float(rep["SmO2_smooth"].max())
        peak_time = rep.loc[rep["SmO2_smooth"].idxmax(), "datetime"]
    else:
        peak_smo2 = math.nan
        peak_time = pd.NaT

    magnitude = peak_smo2 - min_smo2 if (not math.isnan(peak_smo2) and not math.isnan(min_smo2)) else math.nan

    # ---- Slope2 (resaturation) - deflation 직후
    def slope2(duration: float) -> float:
        t1 = d + pd.to_timedelta(duration, unit="s")
        sub = _slice(res, d, t1)
        if len(sub) < 2:
            return math.nan
        x = (sub["datetime"] - d).dt.total_seconds().to_numpy()
        y = sub["SmO2_smooth"].to_numpy()
        return _linreg_slope(x, y)

    slope2_0_10 = slope2(10)
    slope2_0_30 = slope2(30)

    # ---- T50 / T95: min 이후 min+k*magnitude 선에 도달하는 시각
    if not pd.isna(min_time) and not math.isnan(magnitude):
        min_sec = min_time.timestamp()
        t50_target = min_smo2 + 0.5 * magnitude
        t95_target = min_smo2 + 0.95 * magnitude
        t50_abs = _interp_crossing(x_all, y_all, t50_target, min_sec, e_sec)
        t95_abs = _interp_crossing(x_all, y_all, t95_target, min_sec, e_sec)
        # R 스크립트는 'deflation 기준' 경과초. 우리도 그렇게.
        t50_sec = t50_abs - d_sec if t50_abs is not None else math.nan
        t95_sec = t95_abs - d_sec if t95_abs is not None else math.nan
    else:
        t50_sec = math.nan
        t95_sec = math.nan

    # ---- Reperfusion AUC (3분, baseline 초과)
    auc_end_sec = min(d_sec + 180, e_sec)
    rep_mask = (x_all >= d_sec) & (x_all <= auc_end_sec)
    x_rep = x_all[rep_mask]
    y_rep = y_all[rep_mask]
    x_rep_grid = np.unique(np.concatenate(([d_sec], x_rep, [auc_end_sec])))
    y_rep_grid = np.interp(x_rep_grid, x_all, y_all)
    auc_sec = _trapz_above_baseline(x_rep_grid, y_rep_grid, base_val)
    auc_3min = auc_sec / 60.0  # %·min 단위

    return MetricsResult(
        condition=condition,
        session=session,
        baseline_smo2=base_val,
        slope1_0_60=slope1_0_60,
        slope1_30_150=slope1_30_150,
        oxy_deficit=oxy_deficit,
        min_smo2=min_smo2,
        peak_smo2=peak_smo2,
        magnitude=magnitude,
        slope2_0_10=slope2_0_10,
        slope2_0_30=slope2_0_30,
        t50_sec=t50_sec,
        t95_sec=t95_sec,
        auc_3min=auc_3min,
        anchors_abs=anchors_abs,
        min_time=min_time,
        peak_time=peak_time,
    )
