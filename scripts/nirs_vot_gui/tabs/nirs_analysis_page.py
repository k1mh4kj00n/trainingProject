"""NIRS 분석 페이지 (top-level 탭).

내부에 두 개의 sub-tab:
    [0] 분석          — NirsVotTab (load + condition/session + Analyze + 분석 그래프)
    [1] 전체 데이터   — FullTraceTab (전체 측정 시계열 + anchor 영역, 구간 잡기 참고용)
"""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .full_trace_tab import FullTraceTab
from .nirs_vot_tab import NirsVotTab


class NirsAnalysisPage(QWidget):
    """NIRS-VOT 분석 페이지 — sub-tab 컨테이너."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.subtabs = QTabWidget()
        self.subtabs.setDocumentMode(True)

        self.nirs_tab = NirsVotTab()
        self.full_trace_tab = FullTraceTab(self.nirs_tab)

        self.subtabs.addTab(self.nirs_tab, "분석")
        self.subtabs.addTab(self.full_trace_tab, "전체 데이터")
        self.subtabs.currentChanged.connect(self._on_subtab_changed)

        root.addWidget(self.subtabs, stretch=1)

    def _on_subtab_changed(self, idx: int) -> None:
        """[전체 데이터] 탭으로 전환 시 visible 상태에서 다시 그림."""
        if idx == 1:
            self.full_trace_tab.refresh()
