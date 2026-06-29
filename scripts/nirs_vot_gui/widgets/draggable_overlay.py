"""matplotlib Axes 위의 anchor·baseline·marker 핸들 드래그 매니저.

다섯 가지 핸들 종류를 지원한다:

* ``vline`` — 세로 점선 (start / inflate / deflate / end). x(시각) 만 변경.
* ``hline`` — 가로 점선 (baseline). y(SmO2 %) 만 변경.
* ``marker`` — 점 (Min / Peak). x 만 변경되며 y 는 SmO2_smooth 보간 곡선을 따라간다.

사용법::

    overlay = DraggableOverlay(ax, on_drag_end=callback)
    overlay.add_vline("inflate", inflate_ts, color="...")
    overlay.add_hline("baseline", base_val, color="...")
    overlay.add_marker("min", min_ts, min_val, ...)

    # 드래그 종료 시 callback(kind, name, value) 호출
    #   ('vline',   'inflate', pd.Timestamp)
    #   ('hline',   'baseline', float)
    #   ('marker',  'min',      pd.Timestamp)   # Y 는 호출자가 보간으로 다시 계산

다른 zoom·pan 조작과 충돌하지 않게: matplotlib NavigationToolbar 가 ``zoom``/``pan`` 모드일 때는
드래그를 무시 (``canvas.toolbar.mode != ''``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import matplotlib.dates as mdates
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.lines import Line2D


HandleKind = str  # 'vline' | 'hline' | 'marker'
DragCallback = Callable[[HandleKind, str, object], None]


@dataclass
class _Handle:
    kind: HandleKind                 # 'vline' / 'hline' / 'marker'
    name: str                        # 's', 'i', 'd', 'e', 'baseline', 'min', 'peak'
    artist: object                   # Line2D / PathCollection
    pick_radius_px: float = 10.0     # 클릭 hit-test 반경 (px)


def _is_datetime(x) -> bool:
    return isinstance(x, (pd.Timestamp,)) or (hasattr(x, "tzinfo") and hasattr(x, "year"))


def _to_xfloat(x) -> float:
    """matplotlib x축 좌표(float) 로 변환. nanosecond 부분은 잘라낸다 (UserWarning 회피)."""
    if isinstance(x, pd.Timestamp):
        return mdates.date2num(x.replace(nanosecond=0).to_pydatetime())
    if hasattr(x, "year"):  # datetime.datetime
        return mdates.date2num(x)
    return float(x)


def _from_xfloat_to_ts(xf: float, tz=None) -> pd.Timestamp:
    """matplotlib x축 float → pandas.Timestamp (tz aware) 으로 변환."""
    py_dt = mdates.num2date(xf, tz=tz)
    return pd.Timestamp(py_dt)


class DraggableOverlay:
    """``Axes`` 한 개의 핸들 모음. 마우스 이벤트로 드래그 + 콜백.

    두 가지 콜백:
        on_drag_motion(kind, name, value)  — 드래그 중 매 motion 마다 (실시간 미리보기용)
        on_drag_end(kind, name, value)     — 마우스 떼는 순간 (commit 용)
    """

    def __init__(
        self,
        ax: Axes,
        on_drag_end: Optional[DragCallback] = None,
        on_drag_motion: Optional[DragCallback] = None,
    ) -> None:
        self.ax = ax
        self.on_drag_end = on_drag_end
        self.on_drag_motion = on_drag_motion
        self.handles: dict[tuple[str, str], _Handle] = {}
        self._dragging: Optional[tuple[str, str]] = None
        self._last_xy: tuple[float, float] | None = None
        self._tz = None  # x축이 datetime 일 때 timezone 보존

        canvas = ax.figure.canvas
        self._canvas = canvas
        # 새 객체마다 connect. ``fig.clear()`` 는 mpl_connect 을 정리하지 않으므로
        # 호출자가 ``disconnect()`` 를 명시적으로 호출해야 누수가 없다.
        self._cid_press = canvas.mpl_connect("button_press_event", self._on_press)
        self._cid_motion = canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._cid_release = canvas.mpl_connect("button_release_event", self._on_release)

    # ─────────────────────────────────────────────
    def disconnect(self) -> None:
        """모든 mpl_connect 해제. _render() 가 새 overlay 를 만들기 전에 호출 권장."""
        for cid in (self._cid_press, self._cid_motion, self._cid_release):
            try:
                self._canvas.mpl_disconnect(cid)
            except Exception:  # noqa: BLE001
                pass
        self._cid_press = self._cid_motion = self._cid_release = None  # type: ignore

    # ─────────────────────────────────────────────
    #  핸들 추가
    # ─────────────────────────────────────────────
    def add_vline(self, name: str, x, **kwargs) -> Line2D:
        """세로 점선 추가. ``x`` 가 datetime 이면 자동으로 변환."""
        if _is_datetime(x):
            self._tz = getattr(x, "tz", None) or self._tz
        line = self.ax.axvline(_to_xfloat(x), **kwargs)
        self.handles[("vline", name)] = _Handle("vline", name, line)
        return line

    def add_hline(self, name: str, y: float, **kwargs) -> Line2D:
        line = self.ax.axhline(float(y), **kwargs)
        self.handles[("hline", name)] = _Handle("hline", name, line)
        return line

    def add_marker(self, name: str, x, y: float, **kwargs):
        """점(Scatter) 추가. ``x`` 가 datetime 이면 변환."""
        if _is_datetime(x):
            self._tz = getattr(x, "tz", None) or self._tz
        artist = self.ax.scatter([_to_xfloat(x)], [float(y)], **kwargs)
        self.handles[("marker", name)] = _Handle("marker", name, artist)
        return artist

    # ─────────────────────────────────────────────
    #  hit-test (가장 가까운 핸들 찾기)
    # ─────────────────────────────────────────────
    def _hit_test(self, event) -> Optional[tuple[str, str]]:
        if event.xdata is None or event.ydata is None:
            return None

        ax = self.ax
        # 데이터 → 픽셀 변환
        x_px, y_px = ax.transData.transform((event.xdata, event.ydata))

        best_key: Optional[tuple[str, str]] = None
        best_dist = float("inf")

        for key, h in self.handles.items():
            radius = h.pick_radius_px
            if h.kind == "vline":
                hx_data = h.artist.get_xdata()[0]
                hx_px, _ = ax.transData.transform((hx_data, event.ydata))
                d = abs(x_px - hx_px)
            elif h.kind == "hline":
                hy_data = h.artist.get_ydata()[0]
                _, hy_px = ax.transData.transform((event.xdata, hy_data))
                d = abs(y_px - hy_px)
            elif h.kind == "marker":
                offs = h.artist.get_offsets()
                if len(offs) == 0:
                    continue
                hx_data, hy_data = float(offs[0][0]), float(offs[0][1])
                hx_px, hy_px = ax.transData.transform((hx_data, hy_data))
                d = ((x_px - hx_px) ** 2 + (y_px - hy_px) ** 2) ** 0.5
                radius = max(radius, h.pick_radius_px)
            else:
                continue
            if d <= radius and d < best_dist:
                best_dist = d
                best_key = key

        return best_key

    # ─────────────────────────────────────────────
    #  마우스 이벤트
    # ─────────────────────────────────────────────
    def _toolbar_active(self) -> bool:
        """NavigationToolbar 의 zoom/pan 모드면 드래그 차단.

        Qt 임베디드 캔버스에선 ``canvas.manager`` 가 None 일 수 있어 단계별로
        getattr 로 안전 체크한다.
        """
        canvas = self._canvas
        manager = getattr(canvas, "manager", None)
        if manager is None:
            return False
        toolbar = getattr(manager, "toolbar", None)
        if toolbar is None:
            return False
        mode = getattr(toolbar, "mode", "")
        return bool(mode)

    def _on_press(self, event) -> None:
        if event.button != 1 or event.inaxes != self.ax:
            return
        if self._toolbar_active():
            return  # zoom/pan 모드일 때는 드래그 차단
        key = self._hit_test(event)
        if key is None:
            return
        self._dragging = key
        self._last_xy = (event.xdata, event.ydata)

    def _on_motion(self, event) -> None:
        if self._dragging is None or event.inaxes != self.ax:
            return
        if event.xdata is None or event.ydata is None:
            return
        kind, name = self._dragging
        h = self.handles[self._dragging]
        artist = h.artist
        if kind == "vline":
            artist.set_xdata([event.xdata, event.xdata])
            value = (_from_xfloat_to_ts(event.xdata, tz=self._tz)
                     if self._tz else event.xdata)
        elif kind == "hline":
            artist.set_ydata([event.ydata, event.ydata])
            value = float(event.ydata)
        elif kind == "marker":
            # 시각만 드래그. y 는 호출자가 보간으로 결정하지만, 드래그 중에는
            # 마우스 위치로 잠시 따라가게 해 시각적 피드백 제공.
            artist.set_offsets([[event.xdata, event.ydata]])
            value = (_from_xfloat_to_ts(event.xdata, tz=self._tz)
                     if self._tz else event.xdata)
        else:
            return

        # 실시간 콜백 (fill 동기화·ParameterPanel 갱신 등)
        if self.on_drag_motion is not None:
            try:
                self.on_drag_motion(kind, name, value)
            except Exception:  # noqa: BLE001
                pass

        self.ax.figure.canvas.draw_idle()

    # ─────────────────────────────────────────────
    #  외부에서 핸들 위치를 강제로 갱신 (재분석 후 update 용)
    # ─────────────────────────────────────────────
    def update_handle(self, kind: str, name: str, *args) -> None:
        """artist 의 위치만 갱신. fig.clear() 없이 빠르게."""
        h = self.handles.get((kind, name))
        if h is None:
            return
        if kind == "vline":
            xf = _to_xfloat(args[0])
            h.artist.set_xdata([xf, xf])
        elif kind == "hline":
            y = float(args[0])
            h.artist.set_ydata([y, y])
        elif kind == "marker":
            xf = _to_xfloat(args[0])
            y = float(args[1])
            h.artist.set_offsets([[xf, y]])

    def has(self, kind: str, name: str) -> bool:
        return (kind, name) in self.handles

    def _on_release(self, event) -> None:
        if self._dragging is None:
            return
        kind, name = self._dragging
        self._dragging = None
        h = self.handles[(kind, name)]
        artist = h.artist

        if kind == "vline":
            x_data = float(artist.get_xdata()[0])
            value = _from_xfloat_to_ts(x_data, tz=self._tz) if self._tz else x_data
        elif kind == "hline":
            value = float(artist.get_ydata()[0])
        elif kind == "marker":
            offs = artist.get_offsets()[0]
            x_data = float(offs[0])
            value = _from_xfloat_to_ts(x_data, tz=self._tz) if self._tz else x_data
        else:
            return

        if self.on_drag_end is not None:
            try:
                self.on_drag_end(kind, name, value)
            except Exception:  # noqa: BLE001
                # 콜백 오류는 드래그 자체를 막지 않게 swallow
                pass
