"""HRV 분석 페이지 (top-level 탭).

자체 toolbar + RrSignalView + 5개 sub-tab(Overview/Time/Freq/Nonlinear/Time-Varying).

(α) 모드: _Calf 데이터에는 RR 가 없어 HRV 자체 계산 불가능.
        외부 결과 카드(설정 xlsx Coded Data) 가 우측 패널에 표시됨.
(legacy/β) 모드: Kubios 가 export 한 HRV CSV 를 로드하면
        실제 시간/주파수/비선형 분석 결과가 sub-tab 들에 표시됨.

이 페이지는 toolbar 의 'Open Kubios HRV CSV' 버튼으로 legacy 모드 진입.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..hrv_state import HrvController
from ..sizing import lh
from ..style import Color
from .hrv_freq_domain_tab import HrvFreqDomainTab
from .hrv_nonlinear_tab import HrvNonlinearTab
from .hrv_overview_tab import HrvOverviewTab
from .hrv_time_domain_tab import HrvTimeDomainTab
from .placeholder import PlaceholderTab
from ..widgets.rr_signal_view import RrSignalView


# sub-tab idx → CompareTable 카테고리
SUBTAB_TO_CATEGORY = {
    0: "all",        # Overview
    1: "time",       # Time-domain
    2: "freq",       # Frequency-domain
    3: "nonlinear",  # Nonlinear
    4: None,         # Time-Varying placeholder
}


class HrvAnalysisPage(QWidget):
    """HRV 분석 모드 전체를 묶은 페이지."""

    # 외부 (MainWindow) 가 우측 도크/메뉴 동기화에 사용하는 시그널
    subtab_changed = Signal(int)
    file_load_requested = Signal(str)  # path (HrvController 가 컨트롤러 단에서 처리)

    def __init__(self, controller: HrvController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── toolbar ─────────────────────────────
        bar = self._build_toolbar()
        root.addWidget(bar)

        # ── 본문 splitter (RR signal + sub-tabs) ─
        self.signal_view = RrSignalView(self.controller)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tab_overview  = HrvOverviewTab(self.controller)
        self.tab_time      = HrvTimeDomainTab(self.controller)
        self.tab_freq      = HrvFreqDomainTab(self.controller)
        self.tab_nonlinear = HrvNonlinearTab(self.controller)
        self.tab_timevar   = PlaceholderTab("Time-varying", "v0.7 — sliding window")
        self.tabs.addTab(self.tab_overview,  "Results overview")
        self.tabs.addTab(self.tab_time,      "Time-Domain")
        self.tabs.addTab(self.tab_freq,      "Frequency-Domain")
        self.tabs.addTab(self.tab_nonlinear, "Nonlinear")
        self.tabs.addTab(self.tab_timevar,   "Time-Varying")
        self.tabs.currentChanged.connect(self.subtab_changed.emit)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.signal_view)
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 5)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(max(4, lh() // 3))
        self._user_moved = False
        self.splitter.splitterMoved.connect(
            lambda *_: setattr(self, "_user_moved", True)
        )
        root.addWidget(self.splitter, stretch=1)

        # toolbar 의 상태 표시 라벨을 controller 신호와 연결
        self.controller.file_loaded.connect(self._on_file_loaded)
        self.controller.cleared.connect(self._on_cleared)

    # ──────────────────────────────────────────
    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)

        self.open_btn = QPushButton("📂  Open Kubios HRV CSV…")
        self.open_btn.setStyleSheet(
            f"background-color: {Color.ACCENT}; color: white; "
            "font-weight: bold; padding: 6px 14px;"
        )
        self.open_btn.clicked.connect(self._on_open_csv)
        lay.addWidget(self.open_btn)

        self.close_btn = QPushButton("🗙  Close")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.controller.clear)
        lay.addWidget(self.close_btn)

        lay.addStretch()

        self.info_label = QLabel(
            "(α) _Calf 데이터에는 RR 이 없어 HRV 자체 계산 불가. "
            "외부 분석 결과는 우측 패널에 자동 표시됩니다.  "
            "Kubios CSV 가 있으면 위 버튼으로 로드하세요."
        )
        self.info_label.setStyleSheet(f"color: {Color.TEXT_MUTED};")
        self.info_label.setWordWrap(True)
        lay.addWidget(self.info_label, stretch=1)

        return bar

    # ──────────────────────────────────────────
    def _on_open_csv(self) -> None:
        default_dir = "참고자료/Kubios 프로그램"
        if not Path(default_dir).exists():
            default_dir = ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Kubios HRV CSV", default_dir,
            "Kubios HRV CSV (*.csv);;All files (*.*)",
        )
        if not path:
            return
        ok = self.controller.load_file(path)
        if ok:
            self.tabs.setCurrentWidget(self.tab_overview)

    def _on_file_loaded(self, rep) -> None:
        self.close_btn.setEnabled(True)
        n = len(rep.rr_intervals_s)
        limits = rep.sample_info.get("limits", "?")
        path_name = self.controller.path.name if self.controller.path else "—"
        self.info_label.setText(
            f"Loaded: <b>{path_name}</b>  ·  {n} beats  ·  sample {limits}"
        )
        self.info_label.setStyleSheet("color: #24292E;")

    def _on_cleared(self) -> None:
        self.close_btn.setEnabled(False)
        self.info_label.setText(
            "(α) _Calf 데이터에는 RR 이 없어 HRV 자체 계산 불가. "
            "외부 분석 결과는 우측 패널에 자동 표시됩니다.  "
            "Kubios CSV 가 있으면 위 버튼으로 로드하세요."
        )
        self.info_label.setStyleSheet(f"color: {Color.TEXT_MUTED};")

    # ──────────────────────────────────────────
    def current_subtab_index(self) -> int:
        return self.tabs.currentIndex()

    def current_category(self) -> str | None:
        return SUBTAB_TO_CATEGORY.get(self.tabs.currentIndex())

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if not self._user_moved:
            total = self.splitter.height()
            if total > 0:
                top = int(total * 4 / 9)
                bot = total - top
                self.splitter.setSizes([top, bot])
