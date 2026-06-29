"""상단 시그널 영역 — Kubios 스타일.

탭과 무관하게 항상 보이며 두 그래프로 구성:
    [위]  Overview: 전체 측정 길이의 RR 시계열 + 선택 범위 음영
    [아래] Zoomed:  선택 범위만 확대 (평균선 + ±SDNN)

상호작용:
    - Overview 그래프 위에서 마우스 드래그로 분석 범위 선택 (SpanSelector)
    - HH:MM:SS 또는 초 단위 입력으로도 범위 지정
    - Reset 버튼: 전체 범위로 복원
    - Time axis 토글: Relative (00:00:00~) 또는 Absolute (시계 시각)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.ticker import FuncFormatter
from matplotlib.widgets import SpanSelector
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator, QRegularExpressionValidator
from PySide6.QtCore import QRegularExpression
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..hrv_state import HrvController
from ..sizing import char_w, lh
from ..widgets.mpl_canvas import MplCanvas


# ──────────────────────────────────────────────
#  시간 파싱/포맷
# ──────────────────────────────────────────────
def parse_hms(s: str) -> Optional[float]:
    """'HH:MM:SS', 'MM:SS', 'SS' 또는 'SS.s' 를 초로 파싱. 실패 시 None."""
    s = s.strip()
    if not s:
        return None
    try:
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 2:
                m, sec = int(parts[0]), float(parts[1])
                return m * 60 + sec
            elif len(parts) == 3:
                h, m, sec = int(parts[0]), int(parts[1]), float(parts[2])
                return h * 3600 + m * 60 + sec
            else:
                return None
        return float(s)
    except ValueError:
        return None


def format_hms(seconds: float) -> str:
    if seconds < 0:
        return "00:00:00"
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


_HMS_RX = QRegularExpression(r"^\d{1,2}:\d{1,2}:\d{1,2}(\.\d+)?$|^\d{1,3}:\d{1,2}(\.\d+)?$|^\d+(\.\d+)?$")


# ──────────────────────────────────────────────
#  RrSignalView
# ──────────────────────────────────────────────
class RrSignalView(QWidget):
    def __init__(self, controller: HrvController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = controller

        self._t_origin: float = 0.0      # 데이터의 절대 시작 시각 (s)
        self._t_end_full: float = 0.0    # 데이터의 절대 종료 시각 (s)
        self._range_abs: tuple[float, float] | None = None  # 현재 선택 범위 (절대 s)
        self._span_selector: Optional[SpanSelector] = None
        self._time_mode: str = "relative"  # "relative" | "absolute"

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # 두 캔버스 (위/아래)
        line = lh()
        self.canvas_overview = MplCanvas(figsize=(10, 2.4), show_toolbar=False)
        self.canvas_zoom = MplCanvas(figsize=(10, 3.0), show_toolbar=False)
        self.canvas_overview.setMinimumHeight(line * 7)
        self.canvas_zoom.setMinimumHeight(line * 9)
        root.addWidget(self.canvas_overview, stretch=4)
        root.addWidget(self.canvas_zoom, stretch=5)
        self.setMinimumHeight(line * 18)

        # ─── 컨트롤 행 1: Sample Type / Show original / Time axis / Sample
        row1 = QHBoxLayout()
        row1.setContentsMargins(8, 0, 8, 0)
        row1.setSpacing(8)
        row1.addWidget(QLabel("Sample Analysis Type:"))
        self.sample_type = QComboBox()
        self.sample_type.addItems(["single sample"])
        self.sample_type.setMinimumWidth(char_w() * 18)
        row1.addWidget(self.sample_type)

        self.show_original_cb = QCheckBox("Show original RR")
        self.show_original_cb.setEnabled(False)
        row1.addWidget(self.show_original_cb)

        row1.addSpacing(int(char_w() * 2))
        row1.addWidget(QLabel("Time axis:"))
        self.time_axis_combo = QComboBox()
        self.time_axis_combo.addItems(["Relative (00:00:00)", "Absolute (clock)"])
        self.time_axis_combo.setMinimumWidth(char_w() * 22)
        self.time_axis_combo.currentIndexChanged.connect(self._on_time_axis_changed)
        row1.addWidget(self.time_axis_combo)

        row1.addStretch()

        row1.addWidget(QLabel("Sample:"))
        self.sample_combo = QComboBox()
        self.sample_combo.addItem("Sample 1")
        row1.addWidget(self.sample_combo)
        root.addLayout(row1)

        # ─── 컨트롤 행 2: Range (start - end) + Apply / Reset
        row2 = QHBoxLayout()
        row2.setContentsMargins(8, 0, 8, 0)
        row2.setSpacing(6)
        row2.addWidget(QLabel("Range:"))

        self.start_edit = QLineEdit()
        self.start_edit.setPlaceholderText("00:00:00")
        self.start_edit.setMinimumWidth(char_w() * 12)
        self.start_edit.setValidator(QRegularExpressionValidator(_HMS_RX, self))
        self.start_edit.returnPressed.connect(self._on_apply_range)
        row2.addWidget(self.start_edit)

        row2.addWidget(QLabel("→"))
        self.end_edit = QLineEdit()
        self.end_edit.setPlaceholderText("00:05:00")
        self.end_edit.setMinimumWidth(char_w() * 12)
        self.end_edit.setValidator(QRegularExpressionValidator(_HMS_RX, self))
        self.end_edit.returnPressed.connect(self._on_apply_range)
        row2.addWidget(self.end_edit)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._on_apply_range)
        row2.addWidget(self.apply_btn)

        self.reset_btn = QPushButton("Reset (full)")
        self.reset_btn.clicked.connect(self._on_reset_range)
        row2.addWidget(self.reset_btn)

        row2.addSpacing(int(char_w() * 2))
        self.range_status_label = QLabel("")
        self.range_status_label.setStyleSheet("color: #666;")
        row2.addWidget(self.range_status_label)

        row2.addStretch()
        root.addLayout(row2)

        # 컨트롤러 시그널 연결
        controller.file_loaded.connect(self._on_loaded)
        controller.cleared.connect(self._on_cleared)
        controller.range_changed.connect(self._on_range_changed)
        controller.analyzed.connect(self._refresh_after_analyze)

        # 입력/버튼 활성 상태
        self._set_controls_enabled(False)
        self._render_empty()

    # ──────────────────────────────────────────
    #  활성 상태 토글
    # ──────────────────────────────────────────
    def _set_controls_enabled(self, on: bool) -> None:
        for w in (self.start_edit, self.end_edit, self.apply_btn, self.reset_btn,
                  self.time_axis_combo):
            w.setEnabled(on)

    # ──────────────────────────────────────────
    #  컨트롤러 이벤트
    # ──────────────────────────────────────────
    def _on_cleared(self) -> None:
        self._range_abs = None
        self._t_origin = 0.0
        self._t_end_full = 0.0
        self._span_selector = None
        self.start_edit.clear()
        self.end_edit.clear()
        self.range_status_label.clear()
        self._set_controls_enabled(False)
        self._render_empty()

    def _on_loaded(self, report) -> None:
        t = report.rr_times_s
        if len(t) == 0:
            return
        self._t_origin = float(t[0])
        self._t_end_full = float(t[-1])
        self._range_abs = None  # 처음엔 전체 (analyzed 시그널에서 갱신)
        # 입력 박스 기본값 = 전체 범위 (relative)
        self.start_edit.setText(format_hms(0.0))
        self.end_edit.setText(format_hms(self._t_end_full - self._t_origin))
        self._set_controls_enabled(True)
        # _render는 controller.analyzed 시그널이 발생할 때 호출됨

    def _on_range_changed(self, t0_abs: float, t1_abs: float) -> None:
        full_lo = self._t_origin
        full_hi = self._t_end_full
        # 전체와 거의 같으면 'full'로 표시
        if abs(t0_abs - full_lo) < 0.5 and abs(t1_abs - full_hi) < 0.5:
            self._range_abs = None
        else:
            self._range_abs = (t0_abs, t1_abs)

        # 입력 박스 동기화 (relative 표기)
        self.start_edit.blockSignals(True)
        self.end_edit.blockSignals(True)
        self.start_edit.setText(format_hms(t0_abs - full_lo))
        self.end_edit.setText(format_hms(t1_abs - full_lo))
        self.start_edit.blockSignals(False)
        self.end_edit.blockSignals(False)

        # 상태 라벨
        rep = self.ctrl.report
        if rep is not None:
            t = rep.rr_times_s
            n = int(((t >= t0_abs) & (t <= t1_abs)).sum())
            tag = "(full)" if self._range_abs is None else "(custom)"
            self.range_status_label.setText(
                f"{tag}  {format_hms(t0_abs - full_lo)} → "
                f"{format_hms(t1_abs - full_lo)}  ·  {n} beats"
            )

    def _refresh_after_analyze(self) -> None:
        """controller.analyzed 시그널 받아서 그래프 다시 그림."""
        if self.ctrl.report is None:
            return
        self._render(self.ctrl.report)

    # ──────────────────────────────────────────
    #  사용자 액션
    # ──────────────────────────────────────────
    def _on_apply_range(self) -> None:
        s_rel = parse_hms(self.start_edit.text())
        e_rel = parse_hms(self.end_edit.text())
        if s_rel is None or e_rel is None:
            self.range_status_label.setText("⚠ 잘못된 시간 형식 (HH:MM:SS)")
            return
        if e_rel <= s_rel:
            self.range_status_label.setText("⚠ 종료 시간이 시작 이후여야 함")
            return
        # 범위 클램프
        full_dur = self._t_end_full - self._t_origin
        s_rel = max(0.0, min(s_rel, full_dur))
        e_rel = max(s_rel + 1.0, min(e_rel, full_dur))
        t0 = self._t_origin + s_rel
        t1 = self._t_origin + e_rel
        self.ctrl.analyze_range(t0, t1)

    def _on_reset_range(self) -> None:
        self.ctrl.analyze_range(None, None)

    def _on_time_axis_changed(self, idx: int) -> None:
        self._time_mode = "absolute" if idx == 1 else "relative"
        if self.ctrl.report is not None:
            self._render(self.ctrl.report)

    def _on_span_select(self, xmin: float, xmax: float) -> None:
        """SpanSelector onselect — overview의 x축 좌표(절대 s)."""
        if xmax - xmin < 1.0:  # 너무 짧으면 무시
            return
        self.ctrl.analyze_range(xmin, xmax)

    # ──────────────────────────────────────────
    #  렌더링
    # ──────────────────────────────────────────
    def _xfmt_for_axis(self):
        """x축 라벨 포매터. _t_origin은 절대 epoch에 해당하지 않을 수 있어
        Absolute 모드는 origin이 'HH:MM:SS' 형태로 시각 의미가 있을 때만 의미.
        일단 단순하게 Relative=초, Absolute=HH:MM:SS(t_origin 기준 시각)로.
        """
        if self._time_mode == "absolute":
            origin = self._t_origin
            def fmt(x, _pos):
                return format_hms(x % 86400) if origin > 86400 else format_hms(x)
            return FuncFormatter(fmt)
        else:
            origin = self._t_origin
            def fmt(x, _pos):
                return f"{x - origin:.0f}s"
            return FuncFormatter(fmt)

    def _render_empty(self) -> None:
        for canvas, label in [
            (self.canvas_overview, "Measurement overview"),
            (self.canvas_zoom, "RR interval (selected sample)"),
        ]:
            f = canvas.figure
            f.clear()
            ax = f.add_subplot(111)
            ax.text(0.5, 0.5, label, ha="center", va="center",
                    color="#AAAAAA", fontsize=10, transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
            for s in ax.spines.values():
                s.set_color("#DDDDDD")
            canvas.canvas.draw_idle()

    def _render(self, report) -> None:
        rr_ms = report.rr_ms
        t_abs = report.rr_times_s

        # 선택 범위 (절대)
        if self._range_abs is not None:
            t0_abs, t1_abs = self._range_abs
        else:
            t0_abs, t1_abs = self._t_origin, self._t_end_full

        # ── 위: Measurement overview (전체)
        f1 = self.canvas_overview.figure
        f1.clear()
        ax1 = f1.add_subplot(111)
        ax1.plot(t_abs, rr_ms, color="#1565C0", linewidth=0.6, alpha=0.85)
        # 선택 영역 음영
        ax1.axvspan(t0_abs, t1_abs, color="#FFA000", alpha=0.20, zorder=1)
        # 선택 경계
        ax1.axvline(t0_abs, color="#E65100", linewidth=1.0, zorder=3)
        ax1.axvline(t1_abs, color="#E65100", linewidth=1.0, zorder=3)
        ax1.set_xlim(self._t_origin, self._t_end_full)
        ax1.set_ylabel("RR (ms)", fontsize=8)
        ax1.tick_params(labelsize=7)
        ax1.xaxis.set_major_formatter(self._xfmt_for_axis())
        ax1.grid(True, alpha=0.25)
        ax1.set_title(
            f"Measurement overview  ·  Drag to select analysis range  "
            f"(total {format_hms(self._t_end_full - self._t_origin)})",
            fontsize=9, loc="left", color="#666",
        )

        # SpanSelector 재설치 (figure clear 후엔 새로 만들어야 함)
        self._span_selector = SpanSelector(
            ax1, self._on_span_select,
            direction="horizontal",
            useblit=True,
            props=dict(alpha=0.30, facecolor="#FF6F00"),
            interactive=True,
            drag_from_anywhere=True,
            ignore_event_outside=False,
            minspan=2.0,
        )
        # 이미 선택 범위가 있으면 SpanSelector에도 표시
        try:
            self._span_selector.extents = (t0_abs, t1_abs)
        except Exception:  # noqa: BLE001
            pass

        self.canvas_overview.canvas.draw_idle()

        # ── 아래: Zoomed RR (선택 sample 확대)
        mask = (t_abs >= t0_abs) & (t_abs <= t1_abs)
        t_sel = t_abs[mask]
        rr_sel = rr_ms[mask]

        f2 = self.canvas_zoom.figure
        f2.clear()
        ax2 = f2.add_subplot(111)
        if len(rr_sel) >= 2:
            try:
                from ..hrv_analysis.detrend import smoothness_priors_detrend  # type: ignore
                rr_det = smoothness_priors_detrend(rr_sel, lam=100.0)
                sdnn = float(np.std(rr_det, ddof=1))
            except Exception:  # noqa: BLE001
                sdnn = float(np.std(rr_sel, ddof=1))
            mean_rr = float(np.mean(rr_sel))
            ax2.fill_between(t_sel, mean_rr - sdnn, mean_rr + sdnn,
                             color="#1565C0", alpha=0.10)
            ax2.plot(t_sel, rr_sel, color="#0D47A1", linewidth=1.0)
            ax2.scatter(t_sel, rr_sel, color="#1976D2", s=4, alpha=0.55)
            ax2.axhline(mean_rr, color="#888", linestyle="--", linewidth=0.7)
            ax2.set_xlim(t0_abs, t1_abs)
            n = len(rr_sel)
            tag = "Sample 1 (full)" if self._range_abs is None else "Sample 1 (custom range)"
            ax2.set_title(
                f"{tag}  ·  {format_hms(t0_abs - self._t_origin)} → "
                f"{format_hms(t1_abs - self._t_origin)}  ·  {n} beats  "
                f"·  Mean RR {mean_rr:.1f} ms  ·  ±SDNN {sdnn:.2f} ms",
                fontsize=9, loc="left",
            )
        else:
            ax2.text(0.5, 0.5, "Not enough RR in selected range",
                     ha="center", va="center", transform=ax2.transAxes,
                     color="#C62828")
        ax2.set_xlabel("Time", fontsize=8)
        ax2.set_ylabel("RR (ms)", fontsize=8)
        ax2.tick_params(labelsize=7)
        ax2.xaxis.set_major_formatter(self._xfmt_for_axis())
        ax2.grid(True, alpha=0.25)
        self.canvas_zoom.canvas.draw_idle()
