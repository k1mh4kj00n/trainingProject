"""HRV Time-Domain 탭 — Kubios "Time-Domain Results" 와 동일 레이아웃.

좌측 (35%): Variable / Value 통계 테이블
우측 (65%): 위 RR 분포 히스토그램, 아래 HR Deceleration/Acceleration Capacity
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..hrv_state import HrvController
from ..style import Color
from ..widgets.mpl_canvas import MplCanvas


HIST_BIN_MS = 7.8125


class HrvTimeDomainTab(QWidget):
    def __init__(self, controller: HrvController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        self.placeholder = QLabel("Time-Domain Results")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet(
            f"color: {Color.TEXT_MUTED}; font-size: 13pt; padding: 30px;"
        )
        root.addWidget(self.placeholder)

        self.splitter = QSplitter(Qt.Horizontal)
        # 좌측: 통계 테이블
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Time-Domain Results")
        title.setStyleSheet("font-weight: bold; font-size: 11pt; padding: 4px 2px;")
        ll.addWidget(title)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Variable", "Value"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        ll.addWidget(self.table)
        self.splitter.addWidget(left)

        # 우측: 그래프 두 개
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        self.canvas_hist = MplCanvas(figsize=(8, 3.6), show_toolbar=False)
        self.canvas_dc_ac = MplCanvas(figsize=(8, 3.6), show_toolbar=False)
        rl.addWidget(self.canvas_hist, stretch=1)
        rl.addWidget(self.canvas_dc_ac, stretch=1)
        self.splitter.addWidget(right)

        self.splitter.setSizes([350, 700])
        self.splitter.hide()
        root.addWidget(self.splitter, stretch=1)

        controller.analyzed.connect(self._on_analyzed)
        controller.cleared.connect(self._on_cleared)

    def _on_cleared(self) -> None:
        self.placeholder.show(); self.splitter.hide()

    def _on_analyzed(self) -> None:
        self.placeholder.hide(); self.splitter.show()
        self._render()

    def _render(self) -> None:
        td = self.ctrl.td
        rr_ms = self.ctrl.report.rr_ms

        # ── 좌측 통계 테이블 (Kubios 컬럼 순서)
        rows = [
            ("Mean RR (ms)",         f"{td.mean_rr_ms:.2f}"),
            ("SDNN (ms)",            f"{td.sdnn_ms:.2f}"),
            ("Mean HR (bpm)",        f"{td.mean_hr_bpm:.2f}"),
            ("SD HR (bpm)",          f"{td.sd_hr_bpm:.2f}"),
            ("Min HR (bpm)",         f"{td.min_hr_bpm:.2f}"),
            ("Max HR (bpm)",         f"{td.max_hr_bpm:.2f}"),
            ("RMSSD (ms)",           f"{td.rmssd_ms:.2f}"),
            ("NN50",                 f"{td.nn50_count}"),
            ("pNN50 (%)",            f"{td.pnn50_pct:.2f}"),
            ("HRV triangular index", f"{td.hrv_triangular_index:.3f}"),
            ("TINN (ms)",            f"{td.tinn_ms:.0f}"),
            ("Stress index",         f"{td.stress_index:.2f}"),
            ("DC (ms)",              f"{td.dc_ms:.2f}"),
            ("DCmod (ms)",           f"{td.dc_mod_ms:.2f}"),
            ("AC (ms)",              f"{td.ac_ms:.2f}"),
            ("ACmod (ms)",           f"{td.ac_mod_ms:.2f}"),
        ]
        self.table.setRowCount(len(rows))
        for r, (var, val) in enumerate(rows):
            it1 = QTableWidgetItem(var)
            it2 = QTableWidgetItem(val)
            it2.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 0, it1)
            self.table.setItem(r, 1, it2)

        # ── 우측 위: RR 분포 히스토그램 + Triangular fit
        f = self.canvas_hist.figure; f.clear()
        ax = f.add_subplot(111)
        lo = np.floor(rr_ms.min() / HIST_BIN_MS) * HIST_BIN_MS
        hi = np.ceil(rr_ms.max() / HIST_BIN_MS) * HIST_BIN_MS
        bins = np.arange(lo, hi + HIST_BIN_MS, HIST_BIN_MS)
        counts, edges, patches = ax.hist(
            rr_ms, bins=bins, color="#2E7DCA", edgecolor="#1B5FA3", alpha=0.85
        )
        # mode 강조
        if counts.size:
            mode_idx = int(np.argmax(counts))
            mode_center = (edges[mode_idx] + edges[mode_idx + 1]) / 2
            ax.axvline(mode_center, color="#FF6F00", linewidth=1.2,
                       label=f"Mode {mode_center:.1f} ms")
        ax.set_title(
            f"RR distribution   ·   HRV tri index {td.hrv_triangular_index:.3f}   ·   "
            f"TINN {td.tinn_ms:.0f} ms",
            fontsize=10, loc="left",
        )
        ax.set_xlabel("RR (ms)", fontsize=8)
        ax.set_ylabel("Count", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        self.canvas_hist.canvas.draw_idle()

        # ── 우측 아래: HR Deceleration / Acceleration Capacity 막대
        f2 = self.canvas_dc_ac.figure; f2.clear()
        ax2 = f2.add_subplot(111)
        labels = ["DC", "DCmod", "AC", "ACmod"]
        vals = [td.dc_ms, td.dc_mod_ms, td.ac_ms, td.ac_mod_ms]
        colors = ["#2E7D32", "#43A047", "#C62828", "#E53935"]
        bars = ax2.bar(labels, vals, color=colors, edgecolor="#333", linewidth=0.6)
        for bar, v in zip(bars, vals):
            ax2.text(bar.get_x() + bar.get_width() / 2,
                     v + (0.5 if v >= 0 else -1.0),
                     f"{v:+.2f}", ha="center",
                     va="bottom" if v >= 0 else "top",
                     fontsize=9, fontweight="bold")
        ax2.axhline(0, color="#888", linewidth=0.8)
        ax2.set_ylabel("ms", fontsize=8)
        ax2.tick_params(labelsize=8)
        ax2.set_title(
            f"HR Deceleration/Acceleration Capacity   ·   "
            f"Stress index {td.stress_index:.2f}",
            fontsize=10, loc="left",
        )
        ax2.grid(True, axis="y", alpha=0.3)
        self.canvas_dc_ac.canvas.draw_idle()
