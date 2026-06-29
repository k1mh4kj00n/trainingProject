"""MainWindow 및 전체 앱 조립.

우측 도크 ``Results`` / ``Session Parameters`` / ``HRV Parameters`` 는 같은 영역에
``tabifyDockWidget`` 으로 탭 묶음 — 사용자는 도크 상단 탭 라벨을 클릭해 전환.
``setTabPosition(RightDockWidgetArea, QTabWidget.North)`` 로 탭 라벨이 도크 상단 위치.

v0.6.3 → v0.6.4 변경:
- 데이터 로드 버튼(``📂 Open data file…`` / ``📁 Open folder…``) 을 NirsVotTab 본문에서
  좌측 ``DataBrowser`` (Sessions 패널) 헤더로 이동. NirsVotTab 본문 상단은 분석 컨텍스트
  (Condition / Session / Analyze / Close) 만 남겨 그래프 시야를 확보.
- ``ParameterPanel`` 헤더에 ``📂 Load preset…`` 버튼 추가. 외부 SessionConfig xlsx 파일을
  단독 불러와 모든 입력 위젯을 채울 수 있음 (측정 파일과 무관).

v0.6.2 → v0.6.3 변경:
- ParameterPanel 을 NirsVotTab 본문에서 떼어 별도 ``QDockWidget`` 으로 이동.
  (그래프가 메인. 파라미터는 토글 가능한 보조 패널.)
- 시작 시 자동 폴더 스캔/하드코딩 환자명("이찬민") 등 미리 박힌 정보 모두 제거.
  사용자가 직접 ``Open data file`` / ``Open folder`` 액션을 호출해야 데이터가 보임.
- ParameterPanel 의 모든 input 위젯이 편집 가능 (read-only QLabel 없음).

페이지:
    [0] 🩸 NIRS 분석   — NirsVotTab (그래프) + 좌측 DataBrowser (Sessions+Open) + 우측 ParameterTable
    [1] ❤ HRV 분석    — HrvAnalysisPage (Kubios CSV + 5 sub-tab) + 좌측 HrvDataBrowser
                          + 우측 ExternalHrvCard / CompareTable
    별도 도크: Session Parameters (Top 영역, 토글 가능, NIRS 페이지에서만 의미)
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QTabWidget,
    QToolBar,
)


_ICONS_DIR = Path(__file__).parent / "assets" / "icons"


def _icon(name: str) -> QIcon:
    """assets/icons/<name>.svg 를 QIcon 으로. 없으면 빈 아이콘."""
    p = _ICONS_DIR / f"{name}.svg"
    if p.exists():
        return QIcon(str(p))
    return QIcon()

from .hrv_state import HrvController
from .sizing import dock_width, lh, scaled_size
from .style import QSS
from .tabs.hrv_analysis_page import HrvAnalysisPage
from .tabs.nirs_analysis_page import NirsAnalysisPage
from .widgets.compare_table import CompareTable
from .widgets.data_browser import DataBrowser
from .widgets.external_hrv_card import ExternalHrvCard
from .widgets.hrv_data_browser import HrvDataBrowser
from .widgets.parameter_panel import ParameterPanel
from .widgets.parameter_table import ParameterTable


APP_TITLE = "physical_analysis  —  HRV + NIRS-VOT Analyzer  (v0.6.5)"

PAGE_NIRS = 0
PAGE_HRV  = 1


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        w, h = scaled_size(0.85, default=(1600, 920))
        self.resize(w, h)
        line = lh()
        self.setMinimumSize(line * 60, line * 38)
        self.setStyleSheet(QSS)

        self.controller = HrvController()

        self._build_central()
        self._build_docks()
        self._build_menubar()
        self._build_toolbar()
        self._build_statusbar()
        self._wire_signals()
        self._sync_panels()

    # ──────────────────────────────────────────
    def _build_central(self) -> None:
        self.pages = QTabWidget()
        self.pages.setObjectName("mainPages")
        # documentMode=False — 큰 탭 버튼으로 분석법 명시 구별 (NIRS vs HRV)
        self.pages.setDocumentMode(False)
        self.pages.setTabPosition(QTabWidget.North)

        self.nirs_page = NirsAnalysisPage()
        self.hrv_page  = HrvAnalysisPage(self.controller)

        self.pages.addTab(self.nirs_page, _icon("nirs"), "NIRS-VOT 분석")
        self.pages.addTab(self.hrv_page,  _icon("hrv"),  "HRV 분석")
        self.pages.currentChanged.connect(self._on_page_changed)

        self.setCentralWidget(self.pages)
        self.tab_nirs = self.nirs_page.nirs_tab  # alias

    # ──────────────────────────────────────────
    def _build_docks(self) -> None:
        # ── 좌측: Data tree (페이지에 따라 스택 전환)
        self.hrv_browser = HrvDataBrowser(self.controller)
        self.nirs_browser = DataBrowser()  # 빈 상태로 시작 (loaded dict 기반)
        self.left_stack = QStackedWidget()
        self.left_stack.addWidget(self.nirs_browser)  # 0
        self.left_stack.addWidget(self.hrv_browser)   # 1

        self.dock_browser = QDockWidget("Data", self)
        self.dock_browser.setWidget(self.left_stack)
        self.dock_browser.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.dock_browser.setMinimumWidth(dock_width("medium"))
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_browser)
        self.browser = self.nirs_browser  # 호환 alias

        # ── 우측: Results stack
        self.param_table   = ParameterTable()
        self.external_hrv  = ExternalHrvCard()
        self.compare_table = CompareTable()
        self.right_stack = QStackedWidget()
        self.right_stack.addWidget(self.param_table)    # 0
        self.right_stack.addWidget(self.external_hrv)   # 1
        self.right_stack.addWidget(self.compare_table)  # 2

        self.dock_right = QDockWidget("Results", self)
        self.dock_right.setWidget(self.right_stack)
        self.dock_right.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.dock_right.setMinimumWidth(dock_width("large"))
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_right)

        # ── 별도 도크: Session Parameters (우측, Results 와 tabify)
        # tabify: dock_right 와 같은 영역에 탭 묶음. 사용자가 상단 탭 라벨로 전환.
        self.param_panel = ParameterPanel()
        self.dock_params = QDockWidget("Session Parameters", self)
        self.dock_params.setWidget(self.param_panel)
        self.dock_params.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetFloatable
        )
        self.dock_params.setMinimumWidth(dock_width("large"))
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_params)
        # Results + Session Parameters 두 도크를 한 영역에 탭 묶음
        self.tabifyDockWidget(self.dock_right, self.dock_params)
        # 우측 도크 영역의 탭 라벨을 상단에 표시 (기본 South → North)
        self.setTabPosition(Qt.RightDockWidgetArea, QTabWidget.North)
        # 기본 활성 탭은 Results
        self.dock_right.raise_()
        # Session Parameters 는 시작 시 숨김 (사용자가 토글로 켜야 보임)
        self.dock_params.setVisible(False)
        # 도크 자체를 X 로 닫으면 메뉴 토글도 동기화
        self.dock_params.visibilityChanged.connect(
            lambda v: self.act_toggle_params.setChecked(v) if hasattr(self, "act_toggle_params") else None
        )

        # ── HRV 전용 파라미터 도크 (좌측 고정, HRV 페이지에서만 표시) ──
        from .widgets.hrv_parameter_panel import HrvParameterPanel
        self.hrv_param_panel = HrvParameterPanel(self.controller)
        self.dock_hrv_params = QDockWidget("HRV Parameters", self)
        self.dock_hrv_params.setWidget(self.hrv_param_panel)
        self.dock_hrv_params.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetFloatable
        )
        self.dock_hrv_params.setMinimumWidth(dock_width("large"))
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_hrv_params)
        # HRV dock 도 우측 영역에 tabify, 시작 시 hidden
        self.tabifyDockWidget(self.dock_right, self.dock_hrv_params)
        self.dock_hrv_params.setVisible(False)

    # ──────────────────────────────────────────
    def _build_menubar(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        act_quit = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        view_menu = mb.addMenu("&View")
        self.act_toggle_browser = QAction(_icon("data_tree"), "Toggle Sessions Browser", self,
                                          checkable=True, checked=True)
        self.act_toggle_browser.setToolTip("좌측 Sessions 패널 토글 (해제 시 그래프 영역 확장)")
        # PySide6 에서 triggered 가 () 와 (bool) 오버로드 ambiguous → lambda 로 명시.
        self.act_toggle_browser.triggered.connect(
            lambda checked: self.dock_browser.setVisible(checked)
        )
        # 도크의 X 버튼으로 닫혀도 액션 체크 상태 자동 동기화
        self.dock_browser.visibilityChanged.connect(
            lambda v: self.act_toggle_browser.setChecked(v)
        )
        view_menu.addAction(self.act_toggle_browser)

        self.act_toggle_results = QAction(_icon("results"), "Toggle Results Panel", self,
                                          checkable=True, checked=True)
        self.act_toggle_results.setToolTip("우측 Results 패널 토글 (해제 시 그래프 영역 확장)")
        self.act_toggle_results.triggered.connect(
            lambda checked: self.dock_right.setVisible(checked)
        )
        self.dock_right.visibilityChanged.connect(
            lambda v: self.act_toggle_results.setChecked(v)
        )
        view_menu.addAction(self.act_toggle_results)

        self.act_toggle_params = QAction(
            _icon("params"), "Toggle Session Parameters", self,
            checkable=True, checked=False
        )
        self.act_toggle_params.setToolTip("우측 Session Parameters 패널 토글 (Ctrl+P)")
        self.act_toggle_params.setShortcut("Ctrl+P")
        self.act_toggle_params.triggered.connect(self._toggle_params_dock)
        view_menu.addAction(self.act_toggle_params)

        view_menu.addSeparator()
        act_to_nirs = QAction("Show NIRS analysis", self)
        act_to_nirs.setShortcut("Ctrl+1")
        act_to_nirs.triggered.connect(lambda: self.pages.setCurrentIndex(PAGE_NIRS))
        view_menu.addAction(act_to_nirs)
        act_to_hrv = QAction("Show HRV analysis", self)
        act_to_hrv.setShortcut("Ctrl+2")
        act_to_hrv.triggered.connect(lambda: self.pages.setCurrentIndex(PAGE_HRV))
        view_menu.addAction(act_to_hrv)

        tools_menu = mb.addMenu("&Tools")
        act_reanalyze = QAction("Re-analyze HRV", self)
        act_reanalyze.triggered.connect(self.controller.analyze)
        tools_menu.addAction(act_reanalyze)
        act_batch = QAction("Run NIRS-VOT batch on all loaded sessions", self)
        act_batch.triggered.connect(self._run_nirs_batch)
        tools_menu.addAction(act_batch)

        help_menu = mb.addMenu("&Help")
        act_about = QAction("About", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _build_toolbar(self) -> None:
        from PySide6.QtCore import QSize
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.TopToolBarArea, tb)
        tb.addAction(self.act_toggle_browser)
        tb.addAction(self.act_toggle_results)
        tb.addAction(self.act_toggle_params)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        self.status_info = QLabel(
            "Ready  ·  상단 탭에서 NIRS 분석 또는 HRV 분석을 선택"
        )
        sb.addWidget(self.status_info)

    # ──────────────────────────────────────────
    def _wire_signals(self) -> None:
        # HRV 컨트롤러
        self.controller.analyzed.connect(self._on_hrv_analyzed)
        self.controller.cleared.connect(self._on_hrv_cleared)
        self.controller.status.connect(self.status_info.setText)
        self.controller.error.connect(self._on_error)
        self.controller.range_changed.connect(self._on_range_changed_status)
        self.hrv_page.subtab_changed.connect(self._on_hrv_subtab_changed)

        # NIRS 페이지(NirsVotTab)
        nv = self.tab_nirs
        self.nirs_browser.session_selected.connect(self._on_nirs_session_selected)
        self.nirs_browser.condition_selected.connect(self._on_browser_condition_selected)
        # v0.6.4: 좌측 Sessions 패널 헤더의 Open 버튼 → NirsVotTab 의 다이얼로그 핸들러 호출
        self.nirs_browser.open_file_clicked.connect(nv._on_open_file)
        self.nirs_browser.open_folder_clicked.connect(nv._on_open_folder)
        nv.status_message.connect(self.status_info.setText)
        nv.result_ready.connect(self._on_nirs_result_ready)
        nv.measurement_loaded.connect(self._on_measurement_loaded)
        nv.measurement_cleared.connect(self._on_nirs_cleared)
        nv.condition_combo.currentTextChanged.connect(self._on_condition_changed)
        nv.session_combo.currentTextChanged.connect(self._on_session_changed)
        nv.anchor_dragged.connect(self._on_anchor_dragged)
        nv.anchor_dragging.connect(self._on_anchor_dragging)

        # ParameterPanel (별도 도크) — Apply + Auto Detect 모두 panel 에서
        self.param_panel.params_applied.connect(self._on_params_applied)
        self.param_panel.auto_detect_requested.connect(self._on_auto_detect_requested)

        # ParameterTable — Export all sessions
        self.param_table.export_all_requested.connect(self._on_export_all_sessions)

    # ──────────────────────────────────────────
    #  페이지 / 도크 동기화
    # ──────────────────────────────────────────
    def _on_page_changed(self, idx: int) -> None:
        self._sync_panels()

    def _sync_panels(self) -> None:
        idx = self.pages.currentIndex()
        if idx == PAGE_NIRS:
            self.left_stack.setCurrentWidget(self.nirs_browser)
            self.dock_browser.setWindowTitle("NIRS-VOT  ·  Sessions")
            self.right_stack.setCurrentWidget(self.param_table)
            self.dock_right.setWindowTitle("Analysis Results")
            # NIRS 페이지: HRV dock 숨김
            self.dock_hrv_params.setVisible(False)
        else:
            self.left_stack.setCurrentWidget(self.hrv_browser)
            self.dock_browser.setWindowTitle("HRV  ·  Data")
            if self.controller.has_results:
                self.right_stack.setCurrentWidget(self.compare_table)
                self.dock_right.setWindowTitle("HRV  ·  Ours vs Kubios (legacy)")
            else:
                self.right_stack.setCurrentWidget(self.external_hrv)
                self.dock_right.setWindowTitle("HRV  ·  외부 분석 결과")
            # HRV 페이지: NIRS Session Params 숨김 + HRV Params 표시
            self.dock_params.setVisible(False)
            self.dock_hrv_params.setVisible(True)
            self.dock_hrv_params.raise_()

    def _toggle_params_dock(self, on: bool) -> None:
        if on:
            self.dock_params.show()
            self.dock_params.raise_()
        else:
            self.dock_params.hide()

    def _on_hrv_subtab_changed(self, _idx: int) -> None:
        cat = self.hrv_page.current_category()
        if cat is not None:
            self.compare_table.set_category(cat)

    # ──────────────────────────────────────────
    #  HRV 흐름
    # ──────────────────────────────────────────
    def _on_hrv_analyzed(self) -> None:
        self.compare_table.update_results(self.controller)
        if self.pages.currentIndex() == PAGE_HRV:
            self.right_stack.setCurrentWidget(self.compare_table)
            self.dock_right.setWindowTitle("HRV  ·  Ours vs Kubios (legacy)")

    def _on_hrv_cleared(self) -> None:
        self.compare_table.clear()
        if self.pages.currentIndex() == PAGE_HRV:
            self.right_stack.setCurrentWidget(self.external_hrv)
            self.dock_right.setWindowTitle("HRV  ·  외부 분석 결과")

    def _on_range_changed_status(self, t0: float, t1: float) -> None:
        from .widgets.rr_signal_view import format_hms
        full = self.controller.full_range_abs
        if full is None:
            return
        origin = full[0]
        is_full = (self.controller.range_abs is None)
        tag = "FULL" if is_full else "RANGE"
        self.status_info.setText(
            f"[{tag}] {format_hms(t0 - origin)} → {format_hms(t1 - origin)}  "
            f"·  {format_hms(t1 - t0)} duration"
        )

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "오류", msg)
        self.status_info.setText(msg)

    # ──────────────────────────────────────────
    #  NIRS 결과 / ParameterPanel 흐름
    # ──────────────────────────────────────────
    def _on_nirs_session_selected(self, subject, condition, session) -> None:
        self.pages.setCurrentIndex(PAGE_NIRS)
        self.tab_nirs.analyze_session(condition, session)

    def _on_browser_condition_selected(self, condition: str) -> None:
        """좌측 트리의 condition 노드 더블클릭 → 그 condition 으로 콤보 전환."""
        if condition in self.tab_nirs.loaded:
            self.tab_nirs.condition_combo.setCurrentText(condition)
            self.status_info.setText(f"Condition 전환: {condition}")

    def _on_nirs_result_ready(self, result, df) -> None:
        cond = getattr(result, "condition", None)
        lf = self.tab_nirs.loaded.get(cond) if cond else None
        cfg = lf.config if lf is not None else None
        self.param_table.show_result(result, df, session_config=cfg)
        if cfg is not None:
            self.external_hrv.show_for(cond, cfg)
            # ParameterPanel 의 Min/Peak 그룹도 새 결과로 갱신
            self.param_panel.show_for(cfg, last_result=result)

    def _on_measurement_loaded(self, condition: str, loaded_file) -> None:
        """파일 로드 직후: 좌측 Sessions 트리 + ParameterPanel 갱신.

        트리는 ``NirsVotTab.loaded`` (실제 로드된 condition dict) 와 1:1 동기화.
        폴더 스캔으로 자동 표시하지 않음 — 명시적으로 로드한 항목만 트리에 등장.
        """
        if loaded_file is None:
            return
        # (1) 좌측 Sessions 트리를 NirsVotTab.loaded 로 갱신
        self.nirs_browser.set_loaded(self.tab_nirs.loaded)
        # Export-all 활성화 — 1개 이상 로드되면 가능
        self.param_table.set_loaded_count(len(self.tab_nirs.loaded))
        # session_combo 를 새 cfg 의 timepoint 이름들로 갱신
        self.tab_nirs._sync_session_combo()

        # (2) ParameterPanel 동기화 (현재 콤보 condition 과 일치할 때만)
        if condition == self.tab_nirs.condition_combo.currentText():
            self._refresh_panels_for(condition)
        else:
            # 다른 condition 이 콤보에 있어도 TTE 비교 그리드는 새로 로드된 데이터 포함하도록 갱신
            cur = self.tab_nirs.condition_combo.currentText()
            self.param_panel.update_tte_comparison(self.tab_nirs.loaded, cur)

    def _on_nirs_cleared(self) -> None:
        """NirsVotTab.Close 버튼: 모든 표시 패널 + 트리 클리어."""
        self.param_panel.clear()
        self.param_table.clear()
        self.param_table.set_loaded_count(0)
        self.external_hrv.clear()
        self.nirs_browser.clear()
        self.param_panel.update_tte_comparison({}, None)

    def _on_condition_changed(self, condition: str) -> None:
        self._refresh_panels_for(condition)
        # 콤보 변경 시 자동 재분석 → 그래프 자동 갱신 (조용히, 데이터 없으면 무시)
        if condition in self.tab_nirs.loaded:
            sess = self.tab_nirs.session_combo.currentText()
            self.tab_nirs.analyze_session(condition, sess, silent=True)
            self.nirs_page.full_trace_tab.refresh()

    def _on_session_changed(self, session: str) -> None:
        """session combo 변경 시 panel·table·그래프 자동 갱신."""
        cond = self.tab_nirs.condition_combo.currentText()
        self._refresh_panels_for(cond)
        if cond in self.tab_nirs.loaded:
            self.tab_nirs.analyze_session(cond, session, silent=True)
            self.nirs_page.full_trace_tab.refresh()

    def _refresh_panels_for(self, condition: str) -> None:
        """선택된 condition 의 SessionConfig + 최근 결과로 우측·파라미터 패널 동기화.

        last_result 의 condition / session 이 현재 콤보 값과 다르면 panel min/peak 를
        비움 (잘못된 session 의 결과 표시 방지).

        Optimisation: 같은 condition 으로 반복 호출되면 external_hrv 갱신 skip
        (HRV 카드 자체가 condition 단위라 session 변경에는 변화 없음).
        """
        lf = self.tab_nirs.loaded.get(condition)
        if lf is not None and lf.config is not None:
            last_result = self.tab_nirs.last_result
            cur_sess = self.tab_nirs.session_combo.currentText()
            if last_result is not None and (
                getattr(last_result, "condition", None) != condition
                or getattr(last_result, "session", None) != cur_sess
            ):
                last_result = None
            self.param_panel.show_for(lf.config, last_result=last_result)
            # external_hrv 는 condition 이 실제로 바뀌었을 때만 갱신
            if getattr(self, "_last_hrv_condition", None) != condition:
                self.external_hrv.show_for(condition, lf.config)
                self._last_hrv_condition = condition
        else:
            self.param_panel.clear()
            if lf is None:
                self.external_hrv.clear()
                self._last_hrv_condition = None
        # TTE 비교 그리드 — 모든 로드된 condition 의 운동 결과 한눈에
        self.param_panel.update_tte_comparison(self.tab_nirs.loaded, condition)

    # ──────────────────────────────────────────
    #  그래프 핸들 드래그 처리 (v0.6.6 + v0.6.7)
    # ──────────────────────────────────────────
    def _on_anchor_dragging(self, kind: str, name: str, value) -> None:
        """드래그 중 (motion) 호출. 가벼운 작업만 — ParameterPanel input 즉시 갱신.

        무거운 재분석은 release 시점에 ``_on_anchor_dragged`` 가 처리.
        """
        from PySide6.QtCore import QTime
        sess = self.tab_nirs.session_combo.currentText()
        panel = self.param_panel

        try:
            if kind == "vline":
                # value 는 pandas.Timestamp
                qt = QTime(value.hour, value.minute, value.second)
                row = panel.get_nirs_row(sess) if hasattr(panel, "get_nirs_row") else None
                if name == "i" and row is not None:
                    row.start_edit.setTime(qt)
                elif name == "d" and row is not None:
                    row.end_edit.setTime(qt)
                elif name == "s" and row is not None:
                    # lead = inflate − new_start
                    cond = self.tab_nirs.condition_combo.currentText()
                    lf = self.tab_nirs.loaded.get(cond)
                    if lf and sess in lf.dynamic_anchors:
                        from datetime import time as dtime
                        inflate_t = _clock_to_time(lf.dynamic_anchors[sess].inflate)
                        new_start_t = dtime(value.hour, value.minute, value.second)
                        lead = max(0, min(600, int(_time_diff_sec(inflate_t, new_start_t))))
                        row.lead_spin.setValue(lead)
                elif name == "e" and row is not None:
                    cond = self.tab_nirs.condition_combo.currentText()
                    lf = self.tab_nirs.loaded.get(cond)
                    if lf and sess in lf.dynamic_anchors:
                        from datetime import time as dtime
                        deflate_t = _clock_to_time(lf.dynamic_anchors[sess].deflate)
                        new_end_t = dtime(value.hour, value.minute, value.second)
                        tail = max(0, min(1200, int(_time_diff_sec(new_end_t, deflate_t))))
                        row.tail_spin.setValue(tail)
            # hline / marker 는 ParameterPanel 에 표시 항목 없음 — skip
        except Exception:  # noqa: BLE001
            pass

    def _on_anchor_dragged(self, kind: str, name: str, value) -> None:
        """NirsVotTab 의 그래프 핸들이 드래그되면:
            - vline 's'/'i'/'d'/'e' → timepoint 또는 lead/tail 갱신
            - hline 'baseline'      → lf.overrides[sess]['baseline'] = y
            - marker 'min'/'peak'   → lf.overrides[sess]['min_time' or 'peak_time'] = t
        모두 ParameterPanel 동기화 + 재분석으로 마무리.
        """
        cond = self.tab_nirs.condition_combo.currentText()
        sess = self.tab_nirs.session_combo.currentText()
        lf = self.tab_nirs.loaded.get(cond)
        if lf is None:
            return

        ov = lf.overrides.setdefault(sess, {})

        try:
            if kind == "vline":
                self._handle_vline_drag(lf, sess, name, value)
            elif kind == "hline" and name == "baseline":
                ov["baseline"] = float(value)
            elif kind == "marker":
                if name == "min":
                    ov["min_time"] = value
                elif name == "peak":
                    ov["peak_time"] = value
        except Exception as exc:  # noqa: BLE001
            self.status_info.setText(f"드래그 처리 실패: {exc}")
            return

        # 재분석 (overrides 가 analyze_session 안에서 자동 적용됨)
        self.tab_nirs.analyze_session(cond, sess)
        # ParameterPanel 동기화 — last_result 의 새 min/peak 도 함께 표시
        if lf.config is not None:
            self.param_panel.show_for(lf.config, last_result=self.tab_nirs.last_result)
        # [전체 데이터] 탭 음영도 갱신 (visible 일 때만 실제 draw)
        self.nirs_page.full_trace_tab.refresh()
        # 좌측 Sessions 트리 — vline (i/d) 드래그로 timepoint 가 바뀌면 트리 라벨도 갱신
        if kind == "vline" and name in ("i", "d"):
            self.nirs_browser.refresh_times()
        self.status_info.setText(
            f"드래그 적용: {kind}/{name} → 재분석 ({cond}/{sess})"
        )

    def _handle_vline_drag(self, lf, session: str, name: str, ts) -> None:
        """vline (s/i/d/e) 드래그 — Timepoint(이름·시각·lead·tail) 갱신 + dynamic_anchors 재산출.

        v0.7: NIRS_VOT 가 list[Timepoint] 라 ``session`` 이름으로 lookup. 행이 없으면 신규 추가.
        """
        from datetime import time as dtime
        from nirs_vot.anchors import anchor_from_window
        try:
            from config_loader import Timepoint  # type: ignore
        except ImportError:
            from ...config_loader import Timepoint  # type: ignore

        # ts 는 pandas.Timestamp (tz-aware)
        new_t: dtime = ts.time().replace(microsecond=0)
        if lf.config is None:
            return
        nv_list = lf.config.timepoints.setdefault("NIRS_VOT", [])

        # 현재 세션의 Timepoint 찾기 (또는 신규)
        tp_idx = next((i for i, tp in enumerate(nv_list) if tp.name == session), -1)

        if name in ("i", "d"):
            # Start(Occ) / Fin(Def) 갱신
            if tp_idx >= 0:
                cur = nv_list[tp_idx]
                if name == "i":
                    nv_list[tp_idx] = Timepoint(cur.name, new_t, cur.end, cur.lead, cur.tail)
                else:
                    nv_list[tp_idx] = Timepoint(cur.name, cur.start, new_t, cur.lead, cur.tail)
            else:
                # 새 timepoint 생성 (lead/tail 은 default)
                nv_list.append(Timepoint(session, new_t, new_t))
                tp_idx = len(nv_list) - 1
            tp = nv_list[tp_idx]
            lf.dynamic_anchors[session] = anchor_from_window(
                tp.start, tp.end,
                baseline_lead_sec=int(tp.lead),
                reperfusion_tail_sec=int(tp.tail),
            )

        elif name == "s":
            # start 드래그 → lead 변경 (= inflate − new_start)
            cur_anchor = lf.dynamic_anchors.get(session)
            if cur_anchor is None or tp_idx < 0:
                return
            inflate_t = _clock_to_time(cur_anchor.inflate)
            lead_sec = max(0, min(600, int(round(_time_diff_sec(inflate_t, new_t)))))
            cur = nv_list[tp_idx]
            nv_list[tp_idx] = Timepoint(cur.name, cur.start, cur.end, lead_sec, cur.tail)
            row = self.param_panel.get_nirs_row(session)
            if row is not None:
                row.lead_spin.setValue(lead_sec)
            tp = nv_list[tp_idx]
            lf.dynamic_anchors[session] = anchor_from_window(
                tp.start, tp.end,
                baseline_lead_sec=int(tp.lead),
                reperfusion_tail_sec=int(tp.tail),
            )

        elif name == "e":
            # end 드래그 → tail 변경 (= new_end − deflate)
            cur_anchor = lf.dynamic_anchors.get(session)
            if cur_anchor is None or tp_idx < 0:
                return
            deflate_t = _clock_to_time(cur_anchor.deflate)
            tail_sec = max(0, min(1200, int(round(_time_diff_sec(new_t, deflate_t)))))
            cur = nv_list[tp_idx]
            nv_list[tp_idx] = Timepoint(cur.name, cur.start, cur.end, cur.lead, tail_sec)
            row = self.param_panel.get_nirs_row(session)
            if row is not None:
                row.tail_spin.setValue(tail_sec)
            tp = nv_list[tp_idx]
            lf.dynamic_anchors[session] = anchor_from_window(
                tp.start, tp.end,
                baseline_lead_sec=int(tp.lead),
                reperfusion_tail_sec=int(tp.tail),
            )

    def _on_auto_detect_requested(self) -> None:
        """gradient descent 로 occlusion min / reperfusion peak 검출 → override + 재분석."""
        cond = self.tab_nirs.condition_combo.currentText()
        sess = self.tab_nirs.session_combo.currentText()
        lf = self.tab_nirs.loaded.get(cond)
        if lf is None:
            QMessageBox.warning(self, "검출 실패", "데이터가 로드되지 않았습니다.")
            return
        try:
            anchor = self.tab_nirs._resolve_anchor(lf, cond, sess)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "검출 실패", f"anchor 산출 실패: {exc}")
            return

        # anchor 의 inflate / deflate / end 를 datetime 으로
        df = lf.smoothed
        anchor_date = df["datetime"].iloc[0]
        from .tabs.full_trace_tab import _to_ts
        try:
            t_inflate = _to_ts(anchor_date, anchor.inflate)
            t_deflate = _to_ts(anchor_date, anchor.deflate)
            t_end = _to_ts(anchor_date, anchor.end)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "검출 실패", f"anchor 시각 변환 실패: {exc}")
            return

        # GD + SGD + DE 모두 시도해 글로벌 best 채택. 검출 구간을 deflate ±30s buffer 로
        # 확장 → deflation 직후 진짜 dip (SmO2 가 occlusion 종료 후에도 잠시 더 낮아지는
        # 케이스, 예: HYPO 12:20:39) 까지 포함.
        try:
            from nirs_vot.metrics import find_extremum_robust  # type: ignore
        except ImportError:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from nirs_vot.metrics import find_extremum_robust  # type: ignore

        import pandas as pd
        BUFFER = pd.Timedelta(seconds=30)
        # min: occlusion 시작 ~ deflate +30s (deflation 직후 dip 포함)
        min_t, min_v, min_method = find_extremum_robust(
            df, t_inflate, t_deflate + BUFFER, kind="min"
        )
        # peak: deflate ~ end (이미 충분한 reperfusion 구간)
        peak_t, peak_v, peak_method = find_extremum_robust(
            df, t_deflate, t_end, kind="max"
        )

        # lf.overrides 적용 + 재분석
        ov = lf.overrides.setdefault(sess, {})
        if min_t is not None:
            ov["min_time"] = min_t
        if peak_t is not None:
            ov["peak_time"] = peak_t
        self.tab_nirs.analyze_session(cond, sess)
        self.nirs_page.full_trace_tab.refresh()
        self.status_info.setText(
            f"Auto detect: min={min_v:.2f}% @ {min_t.strftime('%H:%M:%S') if min_t else '—'} [{min_method}], "
            f"peak={peak_v:.2f}% @ {peak_t.strftime('%H:%M:%S') if peak_t else '—'} [{peak_method}]"
        )

    def _sessions_tree_needs_rebuild(self, lf) -> bool:
        """Apply 후 좌측 트리 전체 rebuild 가 필요한지 판정.

        - timepoint 이름이 추가/삭제됐으면 rebuild 필요
        - 시각만 바뀌었으면 refresh_times 로 충분 (트리 expand 상태 보존)
        """
        if lf is None or lf.config is None:
            return False
        new_names = [tp.name for tp in lf.config.nirs_timepoints() if tp.name]
        # 트리 모델에서 현재 condition 의 session 노드 이름 추출
        cond = lf.config.condition or ""
        model = self.nirs_browser._model
        root = model.invisibleRootItem()
        for r in range(root.rowCount()):
            subj = root.child(r)
            if subj is None:
                continue
            for c in range(subj.rowCount()):
                cond_item = subj.child(c)
                if cond_item is None:
                    continue
                cdata = cond_item.data(Qt.UserRole) or {}
                if cdata.get("condition") != cond:
                    continue
                tree_names: list[str] = []
                for s in range(cond_item.rowCount()):
                    sess_item = cond_item.child(s)
                    if sess_item is None:
                        continue
                    sdata = sess_item.data(Qt.UserRole) or {}
                    if sdata.get("type") == "session" and sdata.get("session"):
                        tree_names.append(sdata["session"])
                return tree_names != new_names
        return True  # 노드를 못 찾으면 안전하게 rebuild

    def _on_params_applied(self) -> None:
        """ParameterPanel.Apply: dynamic_anchors + Min/Peak overrides 갱신 + 재분석.

        [전체 데이터] 탭의 음영도 새 anchor 기준으로 갱신 (visible 일 때만).
        """
        cond = self.tab_nirs.condition_combo.currentText()
        lf = self.tab_nirs.loaded.get(cond)
        if lf is None:
            QMessageBox.warning(self, "Apply 실패", "데이터가 로드되지 않았습니다.")
            return
        lf.dynamic_anchors = self.param_panel.collect_anchors()
        # 사용자가 timepoint 행 추가/삭제했을 수 있어 session_combo 도 동기
        self.tab_nirs._sync_session_combo(cond)
        sess = self.tab_nirs.session_combo.currentText()

        # Baseline / Min / Peak override 적용 — 사용자가 ParameterPanel 에서 직접 입력한 값
        ov = lf.overrides.setdefault(sess, {})
        ov_input = self.param_panel.collect_overrides()

        # baseline (스칼라 SmO2 %) — 체크박스 활성 시에만 키 포함됨
        if "baseline" in ov_input:
            ov["baseline"] = float(ov_input["baseline"])
        else:
            ov.pop("baseline", None)

        anchor_date = lf.smoothed["datetime"].iloc[0]
        for key in ("min_time", "peak_time"):
            t = ov_input.get(key)
            if t is None:
                ov.pop(key, None)
            else:
                py_dt = __import__("datetime").datetime.combine(anchor_date.date(), t)
                import pandas as pd
                ts = pd.Timestamp(py_dt)
                if anchor_date.tz is not None:
                    ts = ts.tz_localize(anchor_date.tz)
                ov[key] = ts

        if sess in lf.dynamic_anchors:
            self.tab_nirs.analyze_session(cond, sess)
            self.status_info.setText(f"파라미터 적용 후 재분석: {cond}/{sess}")
        else:
            self.status_info.setText(
                f"파라미터 적용됨 (현재 session={sess} 의 anchor 없음)"
            )
        # [전체 데이터] 탭 음영 갱신
        self.nirs_page.full_trace_tab.refresh()
        # 좌측 Sessions 트리 — timepoint 이름 추가/삭제가 있을 때만 rebuild, 아니면 시각만 갱신
        if self._sessions_tree_needs_rebuild(lf):
            self.nirs_browser.set_loaded(self.tab_nirs.loaded)
        else:
            self.nirs_browser.refresh_times()
        # 명시적 show_for 제거: analyze_session → result_ready → ParameterPanel.show_for 가
        # diff-aware 로 호출되므로 여기서 또 부르면 안전망이 아닌 중복 작업이었음.

    def _run_nirs_batch(self) -> None:
        n = 0
        for cond in list(self.tab_nirs.loaded.keys()):
            for sess in ("Baseline", "Recovery2"):
                try:
                    self.tab_nirs.analyze_session(cond, sess); n += 1
                except Exception:  # noqa: BLE001
                    continue
        QMessageBox.information(self, "Batch", f"{n}개 NIRS 세션 분석 완료.")

    # ──────────────────────────────────────────
    #  Export all sessions  (multi-session wide CSV)
    # ──────────────────────────────────────────
    def _on_export_all_sessions(self) -> None:
        """모든 로드된 condition × session 의 결과를 한 wide-format CSV 로 저장.

        UI 사이드이펙트 없이 ``compute_metrics`` 를 직접 호출해 각 조합의 MetricsResult
        를 산출. ``lf.overrides`` 와 ``lf.dynamic_anchors`` 모두 일반 분석과 동일하게 적용.
        """
        from pathlib import Path
        try:
            from nirs_vot.metrics import compute_metrics  # type: ignore
        except ImportError:
            from .nirs_vot.metrics import compute_metrics  # type: ignore

        loaded = self.tab_nirs.loaded
        if not loaded:
            QMessageBox.warning(self, "Export", "로드된 데이터가 없습니다.")
            return

        # 기본 파일명 — 첫 cfg 의 subject 기반
        first_lf = next(iter(loaded.values()))
        subj = ""
        if first_lf.config is not None and first_lf.config.subject_info:
            subj = (
                first_lf.config.subject_info.get("Name")
                or first_lf.config.subject_info.get("ID(Protocol)")
                or ""
            )
        default = f"{subj}_all_sessions.xlsx" if subj else "all_sessions.xlsx"

        path, selected = QFileDialog.getSaveFileName(
            self, "Export all sessions", default,
            "Excel (*.xlsx);;CSV (*.csv);;Text/TSV (*.txt)",
        )
        if not path:
            return
        p = Path(path)
        if p.suffix == "":
            if "xlsx" in selected:
                p = p.with_suffix(".xlsx")
            elif "txt" in selected:
                p = p.with_suffix(".txt")
            else:
                p = p.with_suffix(".csv")

        rows: list[dict] = []
        skipped: list[str] = []
        order = {"NOR": 0, "HYPO": 1, "HYPER": 2}
        sorted_conds = sorted(loaded.keys(), key=lambda c: (order.get(c, 999), c))
        for cond in sorted_conds:
            lf = loaded[cond]
            for sess in ("Baseline", "Recovery2"):
                try:
                    anchor = self.tab_nirs._resolve_anchor(lf, cond, sess)
                    ov = lf.overrides.get(sess, {})
                    result = compute_metrics(
                        lf.smoothed, anchor, cond, sess,
                        override_baseline=ov.get("baseline"),
                        override_min_time=ov.get("min_time"),
                        override_peak_time=ov.get("peak_time"),
                    )
                except Exception as exc:  # noqa: BLE001
                    skipped.append(f"{cond}/{sess}: {exc}")
                    continue
                rows.append(_build_export_row(result, lf.config))

        if not rows:
            QMessageBox.warning(self, "Export", "분석 가능한 세션이 없습니다.\n" + "\n".join(skipped))
            return

        try:
            from .widgets.parameter_table import ParameterTable
            ParameterTable.write_multi_session(p, rows)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export 실패", str(exc))
            return

        msg = f"{len(rows)}개 세션을 저장했습니다:\n{p}"
        if skipped:
            msg += f"\n\n건너뜀 ({len(skipped)}):\n" + "\n".join(skipped[:10])
        QMessageBox.information(self, "Export all sessions", msg)

    # ──────────────────────────────────────────
    def _show_about(self) -> None:
        QMessageBox.about(
            self, "About",
            "<h3>physical_analysis</h3>"
            "<p>NIRS-VOT + HRV (Kubios-style) 분석 GUI. v0.6.6.</p>"
            "<p>NIRS-VOT 그래프의 vline·baseline·Min·Peak 핸들을 직접 드래그해 조절 가능.<br>"
            "Session Parameters 도크 (Ctrl+P) 에서 환자 정보·시간 구간 편집 가능.</p>"
        )


# ─────────────────────────────────────────────────────────────
#  드래그 처리용 helper (모듈 함수)
# ─────────────────────────────────────────────────────────────
def _clock_to_time(clock: str):
    """``'HH:MM:SS'`` → ``datetime.time``."""
    from datetime import time as dtime
    h, m, s = (int(x) for x in clock.split(":"))
    return dtime(h, m, s)


def _time_diff_sec(later, earlier) -> int:
    """``later - earlier`` (datetime.time), 초 단위. 자정 wrap 무시."""
    return ((later.hour - earlier.hour) * 3600
            + (later.minute - earlier.minute) * 60
            + (later.second - earlier.second))


# ─────────────────────────────────────────────────────────────
#  Export-all 행 빌더 (모듈 함수 — ParameterTable.write_multi_session_csv 가 소비)
# ─────────────────────────────────────────────────────────────
def _build_export_row(result, cfg) -> dict:
    """단일 (condition, session) 결과 + cfg → wide CSV 한 행 dict."""
    import datetime as _dt
    info = (cfg.subject_info if cfg is not None else {}) or {}
    ex = (cfg.timepoints.get("exercise", {}) if cfg is not None else {}) or {}

    def _t2s(t):
        if t is None:
            return ""
        if isinstance(t, _dt.time):
            return f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}"
        if hasattr(t, "strftime"):
            return t.strftime("%H:%M:%S")
        return str(t)

    def _tte_sec(t):
        if t is None:
            return ""
        if isinstance(t, _dt.time):
            return t.hour * 3600 + t.minute * 60 + t.second
        return ""

    # ground truth (vot_truth)
    timepoint = {"Baseline": "Baseline", "Recovery2": "Post"}.get(result.session, result.session)
    gt = (cfg.vot_truth.get(timepoint, {}) if cfg is not None else {}) or {}

    a = result.anchors_abs
    maint = ex.get("TTE_maintenance_rate")
    try:
        maint_f = float(maint) if maint is not None else None
    except (TypeError, ValueError):
        maint_f = None
    flag = ""
    if maint_f is not None:
        flag = "OK" if maint_f >= 70.0 else "WARN_<70%"

    return {
        "condition":          result.condition,
        "session":            result.session,
        "subject_name":       info.get("Name", ""),
        "subject_id":         info.get("ID(Protocol)", ""),
        "age":                info.get("Age", ""),
        "gender":             info.get("Gender", ""),
        "height_cm":          info.get("Height(cm)", ""),
        "weight_kg":          info.get("Weight(kg)", ""),
        "wattmax":            info.get("Wattmax", ""),
        "vo2max":             info.get("VO2max", ""),
        "w_per_kg":           info.get("W/kg", ""),
        "ftp":                info.get("FTP", ""),

        "anchor_start":       _t2s(a.get("s")),
        "anchor_inflate":     _t2s(a.get("i")),
        "anchor_deflate":     _t2s(a.get("d")),
        "anchor_end":         _t2s(a.get("e")),

        "baseline_smo2":      result.baseline_smo2,
        "slope1_0_60":        result.slope1_0_60,
        "slope1_30_150":      result.slope1_30_150,
        "oxy_deficit":        result.oxy_deficit,
        "min_smo2":           result.min_smo2,
        "peak_smo2":          result.peak_smo2,
        "magnitude":          result.magnitude,
        "slope2_0_10":        result.slope2_0_10,
        "slope2_0_30":        result.slope2_0_30,
        "t50_sec":            result.t50_sec,
        "t95_sec":            result.t95_sec,
        "auc_3min":           result.auc_3min,

        "min_time":           _t2s(getattr(result, "min_time", None)),
        "peak_time":          _t2s(getattr(result, "peak_time", None)),

        "tte1_sec":           _tte_sec(ex.get("TTE1")),
        "tte2_sec":           _tte_sec(ex.get("TTE2")),
        "maintenance_rate":   maint_f if maint_f is not None else "",
        "maintenance_flag":   flag,

        "gt_baseline_smo2":   gt.get("Calf_SmO2_Base", ""),
        "gt_min_smo2":        gt.get("Calf_SmO2_Min", ""),
        "gt_peak_smo2":       gt.get("Calf_SmO2_Peak", ""),
        "gt_slope1_30_150":   gt.get("VOT_Slope1_30_150", ""),
        "gt_slope2_0_10":     gt.get("VOT_Slope2_0_10", ""),
        "gt_t50":             gt.get("VOT_T50", ""),
        "gt_auc_3min":        gt.get("AUC_3min", ""),
    }
