"""TraceCard — NIRS-VOT 시계열 + 4점 anchor 음영.

Stateful: 카드 인스턴스가 자기 ``QWidget + Figure + Canvas`` 를 한 번만 만들고
이후 render 에서는 axes 만 갱신. 매번 새 canvas 를 만들면 matplotlib backend 의
이전 canvas 가 deleteLater 후에도 update_screen 시그널을 발사해
``Internal C++ object already deleted`` RuntimeError 발생.
"""

from __future__ import annotations

import datetime as dt

import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from ..cards import AnalysisCard, AnalysisContext, CardMeta, register
from ..theme.tokens import COLOR


def _is_widget_alive(w) -> bool:
    """Qt 위젯의 C++ side 가 살아있는지. shiboken6 우선, 안 되면 try/except."""
    if w is None:
        return False
    try:
        from shiboken6 import isValid  # type: ignore
        return bool(isValid(w))
    except ImportError:
        pass
    try:
        # 살아있는 위젯은 metaObject() 호출 가능
        w.metaObject()
        return True
    except RuntimeError:
        return False


@register
class TraceCard:
    meta = CardMeta(
        id="trace",
        name="NIRS-VOT trace",
        category="NIRS",
        icon="∿",
        description="SmO2 시계열 + start/inflate/deflate/end 4점 anchor 음영",
        default_size=(8, 4),
        min_size=(6, 3),
    )

    def __init__(self) -> None:
        self._widget: QWidget | None = None
        self._fig: Figure | None = None
        self._canvas: FigureCanvasQTAgg | None = None
        self._ax = None

    def compute(self, ctx: AnalysisContext) -> dict:
        if not ctx.is_ready:
            return {"empty": True}
        df = ctx.smoothed
        smo2_col = df["SmO2_smooth"] if "SmO2_smooth" in df.columns else df.get("SmO2_raw")
        return {
            "datetime": df["datetime"],
            "smo2": smo2_col,
            "anchor": ctx.anchor,
            "empty": False,
        }

    def render(self, parent: QWidget, data: dict) -> QWidget:
        # 이전 위젯이 살아있으면 재사용. 죽었으면 (또는 처음이면) 새로 생성.
        if not _is_widget_alive(self._widget):
            self._widget = self._build_widget()

        self._draw(data)
        # 부모 자식 관계는 set_body 가 처리 — 여기는 widget 만 반환.
        return self._widget

    def _build_widget(self) -> QWidget:
        """위젯 + figure + canvas 1회 생성."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._fig = Figure(figsize=(8, 3), facecolor=COLOR.bg_1, layout="constrained")
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v.addWidget(self._canvas)

        self._ax = self._fig.add_subplot(111)
        self._style_axes()
        return w

    def _style_axes(self) -> None:
        ax = self._ax
        if ax is None:
            return
        ax.set_facecolor(COLOR.bg_1)
        for spine in ax.spines.values():
            spine.set_color(COLOR.border)
        ax.tick_params(colors=COLOR.text_2, labelsize=8)
        ax.grid(True, color=COLOR.border, alpha=0.3, linewidth=0.5)
        ax.set_ylabel("SmO2 (%)", color=COLOR.text_1, fontsize=9)

    def _draw(self, data: dict) -> None:
        if self._ax is None:
            return
        ax = self._ax
        ax.clear()
        self._style_axes()

        if data.get("empty"):
            ax.text(
                0.5, 0.5, "Load data to view trace",
                ha="center", va="center",
                transform=ax.transAxes, color=COLOR.text_2, fontsize=10,
            )
            ax.set_xticks([])
            ax.set_yticks([])
            self._safe_draw()
            return

        df_t = data["datetime"]
        df_y = data["smo2"]

        # 라인
        ax.plot(df_t, df_y, color=COLOR.accent, linewidth=1.4, label="SmO2")

        # anchor 음영
        a = data.get("anchor")
        if a is not None and len(df_t) > 0:
            anchor_date = df_t.iloc[0]
            try:
                t_s = _to_ts(anchor_date, a.start)
                t_i = _to_ts(anchor_date, a.inflate)
                t_d = _to_ts(anchor_date, a.deflate)
                t_e = _to_ts(anchor_date, a.end)
                ax.axvspan(t_s, t_i, color=COLOR.text_2, alpha=0.08)
                ax.axvspan(t_i, t_d, color=COLOR.accent_2, alpha=0.18)
                ax.axvspan(t_d, t_e, color=COLOR.accent, alpha=0.12)
                for t, lab in [(t_s, "start"), (t_i, "inf"), (t_d, "def"), (t_e, "end")]:
                    ax.axvline(t, color=COLOR.text_2, linestyle=":", linewidth=0.7, alpha=0.6)
                    ax.text(
                        t, 1.0, lab, rotation=90, ha="right", va="top",
                        fontsize=7, color=COLOR.text_2,
                        transform=ax.get_xaxis_transform(),
                    )
            except Exception:  # noqa: BLE001
                pass

        try:
            tz = df_t.iloc[0].tz
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S", tz=tz))
        except Exception:  # noqa: BLE001
            pass

        self._safe_draw()

    def _safe_draw(self) -> None:
        """canvas 가 죽었을 가능성에 대비한 안전 draw."""
        if self._canvas is None:
            return
        try:
            self._canvas.draw_idle()
        except RuntimeError:
            # canvas C++ side 가 죽었으면 다음 render 에서 재생성
            self._canvas = None
            self._fig = None
            self._ax = None
            self._widget = None


def _to_ts(anchor_date, time_value):
    """``datetime.time`` or ``HH:MM:SS`` → tz-aware Timestamp."""
    import pandas as pd

    if hasattr(time_value, "hour"):
        t = dt.time(int(time_value.hour), int(time_value.minute),
                    int(getattr(time_value, "second", 0) or 0))
    else:
        s = str(time_value).strip()
        parts = [int(p) for p in s.split(":")]
        if len(parts) == 2:
            t = dt.time(parts[0], parts[1])
        else:
            t = dt.time(parts[0], parts[1], parts[2])
    py_dt = dt.datetime.combine(anchor_date.date(), t)
    ts = pd.Timestamp(py_dt)
    if anchor_date.tz is not None:
        ts = ts.tz_localize(anchor_date.tz)
    return ts
