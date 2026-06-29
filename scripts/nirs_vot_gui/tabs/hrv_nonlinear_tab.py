"""HRV Nonlinear 탭 — Kubios "Nonlinear Results"와 동일 레이아웃.

좌측 (35%): Variable / Value 통계 테이블 (Poincaré, ApEn, SampEn, DFA, ...)
우측 (65%): 위 Poincaré 큰 그래프, 아래 DFA log-log 그래프
"""

from __future__ import annotations

import numpy as np
from matplotlib.patches import Ellipse
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

try:
    from ...hrv_analysis.nonlinear import _dfa_fluctuation  # type: ignore
    from ...hrv_analysis.detrend import smoothness_priors_detrend  # type: ignore
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from hrv_analysis.nonlinear import _dfa_fluctuation  # type: ignore
    from hrv_analysis.detrend import smoothness_priors_detrend  # type: ignore


class HrvNonlinearTab(QWidget):
    def __init__(self, controller: HrvController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        self.placeholder = QLabel("Nonlinear Results")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet(
            f"color: {Color.TEXT_MUTED}; font-size: 13pt; padding: 30px;"
        )
        root.addWidget(self.placeholder)

        self.splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Nonlinear Results")
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

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        self.canvas_poin = MplCanvas(figsize=(8, 4.5), show_toolbar=False)
        self.canvas_dfa  = MplCanvas(figsize=(8, 3.0), show_toolbar=False)
        rl.addWidget(self.canvas_poin, stretch=3)
        rl.addWidget(self.canvas_dfa,  stretch=2)
        self.splitter.addWidget(right)

        self.splitter.setSizes([380, 720])
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
        nl = self.ctrl.nl
        rr_ms = self.ctrl.report.rr_ms

        # ── 좌측 통계 테이블
        rows = [
            ("SD1 (ms)",                  f"{nl.sd1_ms:.3f}"),
            ("SD2 (ms)",                  f"{nl.sd2_ms:.3f}"),
            ("SD2/SD1",                   f"{nl.sd2_sd1:.3f}"),
            ("Approximate entropy (ApEn)",f"{nl.apen:.4f}"),
            ("Sample entropy (SampEn)",   f"{nl.sampen:.4f}"),
            ("DFA α1 (4-12 beats)",       f"{nl.dfa_alpha1:.4f}"),
            ("DFA α2 (13-64 beats)",      f"{nl.dfa_alpha2:.4f}"),
        ]
        self.table.setRowCount(len(rows))
        for r, (var, val) in enumerate(rows):
            it1 = QTableWidgetItem(var)
            it2 = QTableWidgetItem(val)
            it2.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 0, it1)
            self.table.setItem(r, 1, it2)

        # ── 우측 위: Poincaré 큰 그래프
        f = self.canvas_poin.figure; f.clear()
        ax = f.add_subplot(111)
        rr1, rr2 = rr_ms[:-1], rr_ms[1:]
        ax.scatter(rr1, rr2, s=10, color="#2E7DCA", alpha=0.6)
        mean_rr = float(np.mean(rr_ms))
        ell = Ellipse(xy=(mean_rr, mean_rr),
                      width=2 * nl.sd2_ms, height=2 * nl.sd1_ms,
                      angle=45, edgecolor="#FF6F00", facecolor="none", linewidth=2.0)
        ax.add_patch(ell)
        c, s = np.cos(np.deg2rad(45)), np.sin(np.deg2rad(45))
        ax.plot([mean_rr - nl.sd2_ms * c, mean_rr + nl.sd2_ms * c],
                [mean_rr - nl.sd2_ms * s, mean_rr + nl.sd2_ms * s],
                color="#FF6F00", linewidth=1.5)
        ax.plot([mean_rr + nl.sd1_ms * s, mean_rr - nl.sd1_ms * s],
                [mean_rr - nl.sd1_ms * c, mean_rr + nl.sd1_ms * c],
                color="#1B5E20", linewidth=1.5)
        lim_lo = float(min(rr1.min(), rr2.min()) - 30)
        lim_hi = float(max(rr1.max(), rr2.max()) + 30)
        ax.plot([lim_lo, lim_hi], [lim_lo, lim_hi], "--", color="#888", linewidth=0.7)
        ax.set_xlim(lim_lo, lim_hi); ax.set_ylim(lim_lo, lim_hi)
        ax.set_aspect("equal")
        ax.set_title(
            f"Poincaré plot   ·   "
            f"SD1 {nl.sd1_ms:.2f} ms   SD2 {nl.sd2_ms:.2f} ms   "
            f"SD2/SD1 {nl.sd2_sd1:.3f}",
            fontsize=10, loc="left",
        )
        ax.set_xlabel("RR(n)  (ms)", fontsize=9)
        ax.set_ylabel("RR(n+1)  (ms)", fontsize=9)
        ax.tick_params(labelsize=8)
        ax.grid(True, alpha=0.3)
        self.canvas_poin.canvas.draw_idle()

        # ── 우측 아래: DFA log-log
        f2 = self.canvas_dfa.figure; f2.clear()
        ax2 = f2.add_subplot(111)
        rr_used = smoothness_priors_detrend(np.asarray(rr_ms, dtype=float), lam=100.0)
        y = np.cumsum(rr_used - np.mean(rr_used))
        scales = np.arange(4, 65)
        fns = np.array([_dfa_fluctuation(y, n) for n in scales])
        mask = np.isfinite(fns) & (fns > 0)
        log_n = np.log10(scales[mask])
        log_f = np.log10(fns[mask])
        ax2.scatter(log_n, log_f, color="#2E7DCA", s=18, alpha=0.7)
        m1 = (scales[mask] >= 4) & (scales[mask] <= 12)
        if m1.sum() >= 2:
            p1 = np.polyfit(log_n[m1], log_f[m1], 1)
            xs = np.linspace(log_n[m1].min(), log_n[m1].max(), 30)
            ax2.plot(xs, np.polyval(p1, xs), color="#FF6F00", linewidth=1.8,
                     label=f"α1 = {nl.dfa_alpha1:.3f}")
        m2 = (scales[mask] >= 13) & (scales[mask] <= 64)
        if m2.sum() >= 2:
            p2 = np.polyfit(log_n[m2], log_f[m2], 1)
            xs = np.linspace(log_n[m2].min(), log_n[m2].max(), 30)
            ax2.plot(xs, np.polyval(p2, xs), color="#C62828", linewidth=1.8,
                     label=f"α2 = {nl.dfa_alpha2:.3f}")
        ax2.set_xlabel(r"$\log_{10}\, n$  (beats)", fontsize=8)
        ax2.set_ylabel(r"$\log_{10}\, F(n)$", fontsize=8)
        ax2.tick_params(labelsize=7)
        ax2.set_title("Detrended Fluctuation Analysis", fontsize=10, loc="left")
        ax2.legend(fontsize=8, loc="lower right")
        ax2.grid(True, alpha=0.3)
        self.canvas_dfa.canvas.draw_idle()
