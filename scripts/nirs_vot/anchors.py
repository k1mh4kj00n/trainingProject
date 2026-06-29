"""세션별 시간 앵커 (설명서.txt 기반).

각 세션은 start -> inflate -> deflate -> end 4지점으로 구성된다.
- start  : baseline 측정 시작 (1분)
- inflate: 커프 팽창 (occlusion 시작, 5분)
- deflate: 커프 해제 (reperfusion 시작, 3분)
- end    : 측정 종료

타임존은 Asia/Seoul, 날짜는 각 파일 데이터에서 추론한다.

v0.6 부터는 설정 xlsx 의 ``Timepoint`` 시트에서 동적으로 anchor 를 만든다.
* `Timepoint` 의 `Start(Occ)` → `inflate`
* `Timepoint` 의 `Fin(Def)` → `deflate`
* `start = inflate − BASELINE_LEAD_SEC` (1분 default)
* `end   = deflate + REPERFUSION_TAIL_SEC` (3분 default)

설정 파일이 없을 때를 위한 구버전 하드코딩(`SESSION_ANCHORS`) 도 fallback 으로 보존한다.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# 기본 lead/tail (초). NIRS-VOT 표준 프로토콜.
BASELINE_LEAD_SEC = 60      # 커프 팽창 1분 전부터 baseline 관찰
REPERFUSION_TAIL_SEC = 180  # 커프 해제 3분 후까지 hyperemia 관찰


@dataclass(frozen=True)
class Anchor:
    start: str
    inflate: str
    deflate: str
    end: str


# ─────────────────────────────────────────────────────────────
#  하드코딩 fallback (구버전 호환)
# ─────────────────────────────────────────────────────────────
SESSION_ANCHORS: dict[str, dict[str, Anchor]] = {
    "NOR": {
        "Baseline":  Anchor("13:02:00", "13:03:00", "13:08:00", "13:11:00"),
        "Recovery2": Anchor("14:04:40", "14:05:40", "14:10:40", "14:13:40"),
    },
    "HYPO": {
        "Baseline":  Anchor("12:14:30", "12:15:30", "12:20:30", "12:23:30"),
        "Recovery2": Anchor("13:12:00", "13:13:00", "13:18:00", "13:21:00"),
    },
    "HYPER": {
        "Baseline":  Anchor("14:00:00", "14:01:00", "14:06:00", "14:09:00"),
        "Recovery2": Anchor("15:06:00", "15:07:00", "15:12:00", "15:15:00"),
    },
}


def get_anchors(condition: str, session: str) -> Anchor:
    """조건(NOR/HYPO/HYPER)과 세션(Baseline/Recovery2)으로 fallback 앵커 조회."""
    try:
        return SESSION_ANCHORS[condition][session]
    except KeyError as exc:
        valid_cond = list(SESSION_ANCHORS.keys())
        valid_sess = list(next(iter(SESSION_ANCHORS.values())).keys())
        raise KeyError(
            f"알 수 없는 조건/세션: {condition}/{session}. "
            f"유효 조건={valid_cond}, 유효 세션={valid_sess}"
        ) from exc


# ─────────────────────────────────────────────────────────────
#  동적 anchor (설정 xlsx 기반)
# ─────────────────────────────────────────────────────────────
def _t2clock(t: dt.time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}"


def _shift_clock(t: dt.time, delta_sec: int) -> str:
    """datetime.time 에 delta_sec 를 더해 'HH:MM:SS' 로. 자정 wrap-around 주의."""
    base = dt.datetime(2000, 1, 1, t.hour, t.minute, t.second)
    shifted = base + dt.timedelta(seconds=delta_sec)
    return f"{shifted.hour:02d}:{shifted.minute:02d}:{shifted.second:02d}"


def anchor_from_window(
    inflate_t: dt.time,
    deflate_t: dt.time,
    *,
    baseline_lead_sec: int = BASELINE_LEAD_SEC,
    reperfusion_tail_sec: int = REPERFUSION_TAIL_SEC,
) -> Anchor:
    """`Timepoint` 시트의 (Start(Occ), Fin(Def)) 한 쌍에서 Anchor 4지점을 산출.

    - inflate = Start(Occ)
    - deflate = Fin(Def)
    - start   = inflate − baseline_lead_sec
    - end     = deflate + reperfusion_tail_sec
    """
    return Anchor(
        start=_shift_clock(inflate_t, -baseline_lead_sec),
        inflate=_t2clock(inflate_t),
        deflate=_t2clock(deflate_t),
        end=_shift_clock(deflate_t, +reperfusion_tail_sec),
    )


def anchors_from_session_config(session_config) -> dict[str, Anchor]:
    """`SessionConfig` → {timepoint_name: Anchor} 매핑.

    각 timepoint 의 자체 ``lead`` / ``tail`` 값으로 4점 anchor 산출. 사용자가
    ParameterPanel 에서 추가한 timepoint 도 자동 반영. 구버전 SessionConfig
    (timepoints['NIRS_VOT'] 가 dict) 와도 호환되도록 fallback 유지.
    """
    out: dict[str, Anchor] = {}
    # 신버전: list[Timepoint] 가 있으면 우선 사용
    if hasattr(session_config, "nirs_timepoints"):
        for tp in session_config.nirs_timepoints():
            out[tp.name] = anchor_from_window(
                tp.start, tp.end,
                baseline_lead_sec=int(tp.lead),
                reperfusion_tail_sec=int(tp.tail),
            )
        if out:
            return out

    # 구버전 fallback (dict 인 경우)
    nv = session_config.timepoints.get("NIRS_VOT") if hasattr(session_config, "timepoints") else None
    if isinstance(nv, dict):
        for name, win in nv.items():
            if win is None:
                continue
            out[name] = anchor_from_window(win.start, win.end)
    return out


# ─────────────────────────────────────────────────────────────
#  SmO2 신호에서 anchor 자동 추정 (cfg 없는 raw 데이터 템플릿)
# ─────────────────────────────────────────────────────────────
def auto_window_from_signal(
    df_smooth,
    *,
    min_dip_pct: float = 5.0,
    min_dur_sec: int = 60,
    max_dur_sec: int = 600,
) -> "tuple[dt.time, dt.time] | None":
    """SmO2_smooth 시계열에서 VOT occlusion 으로 보이는 구간을 자동 추정.

    파일에 운동 구간(완만하고 긴 dip)이 함께 들어 있을 수 있으므로 단순 글로벌 최저점이
    아니라 **prominence + duration 제약**이 있는 dip 후보 중 가장 깊은 것을 선택한다.

    알고리즘 (scipy.signal.find_peaks 기반):
        1. 신호 역수 ``-y`` 에 대해 prominence>=min_dip_pct 인 peak 후보 추출
        2. 각 peak 의 ``peak_widths`` (left_ips, right_ips) 로 dip 시작·끝 추정
        3. 시작~끝 간격(초)이 ``min_dur_sec ~ max_dur_sec`` 인 후보 중 prominence 최대 채택

    검출 실패 시 None 반환.
    """
    import numpy as np
    try:
        from scipy.signal import find_peaks, peak_widths
    except ImportError:
        return None
    if df_smooth is None or len(df_smooth) < 60:
        return None
    y = df_smooth["SmO2_smooth"].to_numpy(dtype=float)
    t = df_smooth["datetime"]
    n = len(y)

    t_sec = t.astype("int64").to_numpy() / 1e9
    dt_arr = np.diff(t_sec)
    dt_pos = dt_arr[dt_arr > 0]
    if len(dt_pos) == 0:
        return None
    median_dt = float(np.median(dt_pos))
    if median_dt <= 0:
        return None
    sps = 1.0 / median_dt  # 다일 측정에도 강건한 실측 샘플링 레이트

    min_w_samples = max(2, int(min_dur_sec * sps * 0.3))
    max_w_samples = max(min_w_samples + 1, int(max_dur_sec * sps * 1.5))

    peaks, props = find_peaks(
        -y,
        prominence=min_dip_pct,
        width=(min_w_samples, max_w_samples),
    )
    if len(peaks) == 0:
        return None

    # 너비를 rel_height=0.5 (절반 깊이) 에서 다시 측정 → VOT 모양 (날카로운 하강·회복) 에 맞음
    widths, _, lefts, rights = peak_widths(-y, peaks, rel_height=0.5)

    best = None  # (prominence, peak_idx, left_idx, right_idx)
    for i, peak_idx in enumerate(peaks):
        l = int(round(lefts[i]))
        r = int(round(rights[i]))
        l = max(0, min(n - 1, l))
        r = max(0, min(n - 1, r))
        if r <= l:
            continue
        dur_sec = float(t_sec[r] - t_sec[l])
        if dur_sec < min_dur_sec or dur_sec > max_dur_sec:
            continue
        prom = float(props["prominences"][i])
        if best is None or prom > best[0]:
            best = (prom, peak_idx, l, r)

    if best is None:
        return None

    _, _, inflate_idx, deflate_idx = best
    inflate_t = t.iloc[inflate_idx].to_pydatetime().time().replace(microsecond=0)
    deflate_t = t.iloc[deflate_idx].to_pydatetime().time().replace(microsecond=0)
    return inflate_t, deflate_t


def auto_anchors_from_signal(df_smooth) -> dict[str, Anchor]:
    """`auto_window_from_signal` 결과로 ``{"Baseline": Anchor}`` 산출.

    Recovery2 는 한 파일 안에 등장한다는 보장이 없어 자동 산출하지 않는다.
    """
    win = auto_window_from_signal(df_smooth)
    if win is None:
        return {}
    inflate_t, deflate_t = win
    return {"Baseline": anchor_from_window(inflate_t, deflate_t)}
