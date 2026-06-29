"""HRV Frequency-Domain 탭 — Kubios "Frequency-Domain Results"와 동일 레이아웃.

좌측 (35%): Variable / VLF / LF / HF / LF/HF 통계 테이블
우측 (65%): 위 FFT spectrum (큰 그래프), 아래 대역 막대 차트
"""

from __future__ import annotations

import numpy as np
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


VLF_COLOR = "#90CAF9"
LF_COLOR  = "#81C784"
HF_COLOR  = "#EF5350"


class HrvFreqDomainTab(QWidget):
    def __init__(self, controller: HrvController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        self.placeholder = QLabel("Frequency-Domain Results")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet(
            f"color: {Color.TEXT_MUTED}; font-size: 13pt; padding: 30px;"
        )
        root.addWidget(self.placeholder)

        self.splitter = QSplitter(Qt.Horizontal)

        # 좌측: 통계 테이블 (Kubios 처럼 VLF/LF/HF 컬럼)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Frequency-Domain Results")
        title.setStyleSheet("font-weight: bold; font-size: 11pt; padding: 4px 2px;")
        ll.addWidget(title)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Variable", "VLF", "LF", "HF", "LF/HF"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2, 3, 4):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        ll.addWidget(self.table)
        self.splitter.addWidget(left)

        # 우측: 위 PSD, 아래 대역 막대
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        self.canvas_psd  = MplCanvas(figsize=(8, 4.5), show_toolbar=False)
        self.canvas_bars = MplCanvas(figsize=(8, 2.6), show_toolbar=False)
        rl.addWidget(self.canvas_psd,  stretch=3)
        rl.addWidget(self.canvas_bars, stretch=2)
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
        fd = self.ctrl.fd

        # ── 좌측 표 (VLF/LF/HF 가로, 행은 Peak/Power/Power(log)/Power(%)/n.u./Total/LF/HF)
        rows: list[tuple[str, str, str, str, str]] = [
            ("Peak frequency (Hz)",
             f"{fd.vlf.peak_hz:.4f}",
             f"{fd.lf.peak_hz:.4f}",
             f"{fd.hf.peak_hz:.4f}",
             ""),
            ("Power (ms²)",
             f"{fd.vlf.power_ms2:.2f}",
             f"{fd.lf.power_ms2:.2f}",
             f"{fd.hf.power_ms2:.2f}",
             ""),
            ("Power (log)",
             f"{fd.vlf.power_log:.3f}",
             f"{fd.lf.power_log:.3f}",
             f"{fd.hf.power_log:.3f}",
             ""),
            ("Power (%)",
             f"{fd.vlf.power_pct:.2f}",
             f"{fd.lf.power_pct:.2f}",
             f"{fd.hf.power_pct:.2f}",
             ""),
            ("Power (n.u.)",
             "—",
             f"{fd.lf.power_nu:.2f}",
             f"{fd.hf.power_nu:.2f}",
             ""),
            ("Total power (ms²)",
             f"{fd.total_power_ms2:.2f}",
             "", "", ""),
            ("LF/HF ratio",
             "", "", "",
             f"{fd.lf_hf_ratio:.3f}"),
        ]
        self.table.setRowCount(len(rows))
        for r, items in enumerate(rows):
            for c, txt in enumerate(items):
                it = QTableWidgetItem(txt)
                if c > 0:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, it)

        # ── 우측 위: FFT spectrum 큰 그래프
        f = self.canvas_psd.figure; f.clear()
        ax = f.add_subplot(111)
        mask = fd.freqs <= 0.45
        ax.plot(fd.freqs[mask], fd.psd[mask], color="#FF6F00", linewidth=1.5)
        ax.fill_between(fd.freqs[mask], 0, fd.psd[mask],
                        where=(fd.freqs[mask] >= 0.0) & (fd.freqs[mask] <= 0.04),
                        color=VLF_COLOR, alpha=0.5)
        ax.fill_between(fd.freqs[mask], 0, fd.psd[mask],
                        where=(fd.freqs[mask] >= 0.04) & (fd.freqs[mask] <= 0.15),
                        color=LF_COLOR, alpha=0.5)
        ax.fill_between(fd.freqs[mask], 0, fd.psd[mask],
                        where=(fd.freqs[mask] >= 0.15) & (fd.freqs[mask] <= 0.40),
                        color=HF_COLOR, alpha=0.5)
        for x, lab in [(0.04, "0.04"), (0.15, "0.15"), (0.40, "0.40")]:
            ax.axvline(x, color="#888", linestyle=":", linewidth=0.8)
        ax.scatter([fd.lf.peak_hz], [np.interp(fd.lf.peak_hz, fd.freqs, fd.psd)],
                   color="#1B5E20", s=60, zorder=5)
        ax.scatter([fd.hf.peak_hz], [np.interp(fd.hf.peak_hz, fd.freqs, fd.psd)],
                   color="#B71C1C", s=60, zorder=5)
        ax.set_title(
            f"FFT spectrum (Welch's periodogram)   ·   "
            f"VLF {fd.vlf.power_ms2:.0f}   LF {fd.lf.power_ms2:.0f}   HF {fd.hf.power_ms2:.0f}   "
            f"·   LF/HF {fd.lf_hf_ratio:.2f}",
            fontsize=10, loc="left",
        )
        ax.set_xlabel("Frequency (Hz)", fontsize=9)
        ax.set_ylabel("PSD (ms²/Hz)", fontsize=9)
        ax.tick_params(labelsize=8)
        ax.grid(True, alpha=0.3)
        self.canvas_psd.canvas.draw_idle()

        # ── 우측 아래: 대역 막대
        f2 = self.canvas_bars.figure; f2.clear()
        ax2 = f2.add_subplot(111)
        labels = ["VLF", "LF", "HF"]
        vals = [fd.vlf.power_pct, fd.lf.power_pct, fd.hf.power_pct]
        bars = ax2.bar(labels, vals, color=[VLF_COLOR, LF_COLOR, HF_COLOR],
                       edgecolor="#333", linewidth=0.6)
        for bar, v in zip(bars, vals):
            ax2.text(bar.get_x() + bar.get_width() / 2, v + 0.8, f"{v:.1f}%",
                     ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax2.set_ylabel("Relative power (%)", fontsize=8)
        ax2.set_ylim(0, max(vals) * 1.20)
        ax2.tick_params(labelsize=8)
        ax2.set_title("Band relative powers", fontsize=10, loc="left")
        ax2.grid(True, axis="y", alpha=0.3)
        self.canvas_bars.canvas.draw_idle()
