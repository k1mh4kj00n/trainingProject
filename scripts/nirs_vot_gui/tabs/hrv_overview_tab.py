"""HRV Results Overview 탭 — Kubios "Results overview"와 동일한 의미.

상단 시그널 영역(RrSignalView)이 별도로 보이므로, 이 탭은 PNS/SNS index와
주요 Time/Freq/Nonlinear 지표를 색상 박스 + 막대 형태로 요약한다.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..hrv_state import HrvController
from ..style import Color
from ..widgets.mpl_canvas import MplCanvas


PNS_COLOR = "#2E7D32"
SNS_COLOR = "#C62828"
NEUTRAL_COLOR = "#1F77B4"
ACCENT_BG = "#FAFAFA"
TILE_BORDER = "#E0E0E0"


def _tile(title: str, value: str, sub: str = "", color: str = NEUTRAL_COLOR) -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.StyledPanel)
    f.setStyleSheet(
        f"QFrame {{background-color: {ACCENT_BG};"
        f" border: 1px solid {TILE_BORDER}; border-radius: 4px;}}"
        " QLabel { border: none; background: transparent; }"
    )
    f.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    lay = QVBoxLayout(f)
    lay.setContentsMargins(8, 4, 8, 4)
    lay.setSpacing(0)
    t = QLabel(title)
    t.setStyleSheet("font-size: 8pt; color: #666;")
    v = QLabel(value)
    v.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {color};")
    lay.addWidget(t)
    lay.addWidget(v)
    if sub:
        s = QLabel(sub)
        s.setStyleSheet("font-size: 7pt; color: #888;")
        lay.addWidget(s)
    return f


class HrvOverviewTab(QWidget):
    def __init__(self, controller: HrvController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        self.placeholder = QLabel("Open a Kubios HRV CSV file to see results overview.")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet(
            f"color: {Color.TEXT_MUTED}; font-size: 13pt; padding: 30px;"
        )
        root.addWidget(self.placeholder)

        # 상단 색상 타일 영역 (4×4, 타일은 고정 높이 — 한 화면에 다 들어오도록)
        self.tile_grid = QGridLayout()
        self.tile_grid.setSpacing(4)
        self.tile_grid.setContentsMargins(0, 0, 0, 0)
        self.tile_widget = QWidget()
        self.tile_widget.setLayout(self.tile_grid)
        self.tile_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        root.addWidget(self.tile_widget)

        # 하단: 좌 통계 요약 텍스트 + 우 미니 그래프
        bottom = QWidget()
        bottom_lay = QGridLayout(bottom)
        bottom_lay.setContentsMargins(0, 4, 0, 0)
        bottom_lay.setSpacing(6)

        self.summary_text = QLabel("")
        self.summary_text.setStyleSheet(
            f"background-color: {ACCENT_BG}; border: 1px solid {TILE_BORDER};"
            " padding: 6px 8px; border-radius: 4px;"
        )
        self.summary_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.summary_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.summary_text.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)

        # 컨테이너 높이가 충분치 않을 때만 스크롤이 뜨도록 QScrollArea로 감싼다.
        self.summary_scroll = QScrollArea()
        self.summary_scroll.setWidget(self.summary_text)
        self.summary_scroll.setWidgetResizable(True)
        self.summary_scroll.setFrameShape(QFrame.NoFrame)
        self.summary_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.summary_scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.summary_scroll.viewport().setStyleSheet("background: transparent;")

        # 미니 그래프 — 세로를 슬림하게 잡아 타일 + 그래프가 한 화면에 들어오도록
        self.canvas_mini_psd = MplCanvas(figsize=(6, 2.4), show_toolbar=False)
        self.canvas_mini_poin = MplCanvas(figsize=(6, 2.4), show_toolbar=False)

        bottom_lay.addWidget(self.summary_scroll,  0, 0)
        bottom_lay.addWidget(self.canvas_mini_psd, 0, 1)
        bottom_lay.addWidget(self.canvas_mini_poin,0, 2)
        bottom_lay.setColumnStretch(0, 2)
        bottom_lay.setColumnStretch(1, 3)
        bottom_lay.setColumnStretch(2, 3)

        root.addWidget(bottom, stretch=1)

        self.tile_widget.hide()
        bottom.hide()
        self._bottom = bottom

        controller.analyzed.connect(self._on_analyzed)
        controller.cleared.connect(self._on_cleared)

    # ──────────────────────────────────────────
    def _on_cleared(self) -> None:
        self.placeholder.show()
        self.tile_widget.hide()
        self._bottom.hide()

    def _on_analyzed(self) -> None:
        self.placeholder.hide()
        self.tile_widget.show()
        self._bottom.show()
        self._render()

    def _clear_grid(self) -> None:
        while self.tile_grid.count():
            item = self.tile_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _render(self) -> None:
        td = self.ctrl.td
        fd = self.ctrl.fd
        nl = self.ctrl.nl
        kubios = self.ctrl.report.metrics if self.ctrl.report else {}

        # PNS/SNS index는 우리 엔진에 미구현이라 Kubios 값 사용
        pns_idx = kubios.get("PNS index", float("nan"))
        sns_idx = kubios.get("SNS index", float("nan"))

        # 타일 그리드 채우기 (3x4)
        self._clear_grid()
        tiles = [
            ("PNS index",   f"{pns_idx:+.2f}" if not np.isnan(pns_idx) else "—",
                "Parasympathetic", PNS_COLOR),
            ("SNS index",   f"{sns_idx:+.2f}" if not np.isnan(sns_idx) else "—",
                "Sympathetic",    SNS_COLOR),
            ("Stress index",f"{td.stress_index:.1f}",  "Baevsky's SI",   "#F57C00"),
            ("Mean HR",     f"{td.mean_hr_bpm:.1f}",   "bpm",            NEUTRAL_COLOR),

            ("Mean RR",     f"{td.mean_rr_ms:.1f}",    "ms",             NEUTRAL_COLOR),
            ("SDNN",        f"{td.sdnn_ms:.2f}",       "ms",             NEUTRAL_COLOR),
            ("RMSSD",       f"{td.rmssd_ms:.2f}",      "ms · vagal",     PNS_COLOR),
            ("pNN50",       f"{td.pnn50_pct:.2f}",     "%",              NEUTRAL_COLOR),

            ("LF/HF ratio", f"{fd.lf_hf_ratio:.3f}",   "balance",        "#7B1FA2"),
            ("LF (n.u.)",   f"{fd.lf.power_nu:.2f}",   "normalized",     NEUTRAL_COLOR),
            ("HF (n.u.)",   f"{fd.hf.power_nu:.2f}",   "normalized",     PNS_COLOR),
            ("Total power", f"{fd.total_power_ms2:.0f}", "ms²",           NEUTRAL_COLOR),

            ("SD1",         f"{nl.sd1_ms:.2f}",        "ms · short-term", PNS_COLOR),
            ("SD2",         f"{nl.sd2_ms:.2f}",        "ms · long-term",  NEUTRAL_COLOR),
            ("DFA α1",      f"{nl.dfa_alpha1:.3f}",    "scaling",         "#7B1FA2"),
            ("SampEn",      f"{nl.sampen:.3f}",        "complexity",      NEUTRAL_COLOR),
        ]
        cols = 4
        for i, (title, value, sub, color) in enumerate(tiles):
            self.tile_grid.addWidget(_tile(title, value, sub, color), i // cols, i % cols)

        # 하단 좌: 통계 텍스트 (간략 요약)
        rows = [
            "── Time-Domain ──",
            f"Mean RR    {td.mean_rr_ms:7.2f} ms     SDNN     {td.sdnn_ms:6.2f} ms",
            f"Mean HR    {td.mean_hr_bpm:7.2f} bpm   RMSSD    {td.rmssd_ms:6.2f} ms",
            f"Min HR     {td.min_hr_bpm:7.2f} bpm   Max HR   {td.max_hr_bpm:6.2f} bpm",
            f"NN50/pNN50  {td.nn50_count:>5d}      {td.pnn50_pct:5.2f} %",
            "",
            "── Frequency-Domain (FFT) ──",
            f"VLF  {fd.vlf.power_ms2:7.2f}  ms²     LF/HF  {fd.lf_hf_ratio:6.3f}",
            f"LF   {fd.lf.power_ms2:7.2f}  ms²     LF n.u.  {fd.lf.power_nu:5.2f}",
            f"HF   {fd.hf.power_ms2:7.2f}  ms²     HF n.u.  {fd.hf.power_nu:5.2f}",
            f"Total {fd.total_power_ms2:7.2f}  ms²",
            "",
            "── Nonlinear ──",
            f"SD1 {nl.sd1_ms:6.2f}      SD2     {nl.sd2_ms:6.2f}",
            f"ApEn {nl.apen:5.3f}     SampEn  {nl.sampen:5.3f}",
            f"DFA α1 {nl.dfa_alpha1:.3f}    α2 {nl.dfa_alpha2:.3f}",
        ]
        self.summary_text.setText(
            "<pre style='font-family: monospace; font-size: 8pt; line-height: 1.15;"
            " margin: 0;'>"
            + "\n".join(rows) + "</pre>"
        )

        # 하단 중: 미니 PSD
        f1 = self.canvas_mini_psd.figure; f1.clear()
        ax1 = f1.add_subplot(111)
        mask = fd.freqs <= 0.45
        ax1.plot(fd.freqs[mask], fd.psd[mask], color="#FF6F00", linewidth=1.2)
        ax1.axvspan(0, 0.04, alpha=0.25, color="#90CAF9")
        ax1.axvspan(0.04, 0.15, alpha=0.25, color="#81C784")
        ax1.axvspan(0.15, 0.40, alpha=0.25, color="#EF5350")
        ax1.set_title(f"Power spectrum   ·   LF/HF {fd.lf_hf_ratio:.2f}",
                      fontsize=9, loc="left")
        ax1.set_xlabel("Hz", fontsize=8)
        ax1.set_ylabel("PSD", fontsize=8)
        ax1.tick_params(labelsize=7)
        ax1.grid(True, alpha=0.3)
        self.canvas_mini_psd.canvas.draw_idle()

        # 하단 우: 미니 Poincaré
        from matplotlib.patches import Ellipse
        f2 = self.canvas_mini_poin.figure; f2.clear()
        ax2 = f2.add_subplot(111)
        rr_ms = self.ctrl.report.rr_ms
        rr1, rr2 = rr_ms[:-1], rr_ms[1:]
        ax2.scatter(rr1, rr2, s=6, color="#2E7DCA", alpha=0.55)
        mean_rr = float(np.mean(rr_ms))
        ell = Ellipse(xy=(mean_rr, mean_rr),
                      width=2 * nl.sd2_ms, height=2 * nl.sd1_ms,
                      angle=45, edgecolor="#FF6F00", facecolor="none", linewidth=1.6)
        ax2.add_patch(ell)
        lim_lo = float(min(rr1.min(), rr2.min()) - 30)
        lim_hi = float(max(rr1.max(), rr2.max()) + 30)
        ax2.plot([lim_lo, lim_hi], [lim_lo, lim_hi], "--", color="#888", linewidth=0.6)
        ax2.set_xlim(lim_lo, lim_hi); ax2.set_ylim(lim_lo, lim_hi)
        ax2.set_aspect("equal")
        ax2.set_title(f"Poincaré   ·   SD1 {nl.sd1_ms:.2f}   SD2 {nl.sd2_ms:.2f}",
                      fontsize=9, loc="left")
        ax2.tick_params(labelsize=7)
        ax2.grid(True, alpha=0.3)
        self.canvas_mini_poin.canvas.draw_idle()
