"""v2 MainWindow — 좌 icon-bar + Sessions Browser dock + 상단 context bar + 메인 dashboard.

v1 의 분석 엔진 / 데이터 로더 그대로 import.
편집 카드들은 ctx.apply(action, payload) 로 mainwindow 의 dispatcher 호출.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# v1 자산 재사용
from config_loader import (  # type: ignore
    SessionConfig,
    Timepoint,
    find_config_for_calf,
    load_session_config,
)
from nirs_vot.anchors import (  # type: ignore
    anchor_from_window,
    anchors_from_session_config,
)
from nirs_vot.loader import is_calf_timeseries, load_calf  # type: ignore
from nirs_vot.preprocess import preprocess  # type: ignore
from nirs_vot_gui.tabs.nirs_vot_tab import LoadedFile  # type: ignore

# v2
from .cards import (
    ACTION_AUTO_DETECT,
    ACTION_OVERRIDES,
    ACTION_SUBJECT_INFO,
    ACTION_TIMEPOINTS,
    ACTION_TTE,
)
from .cards.context import AnalysisContext
from .cards.registry import REGISTRY, by_category
from .dashboard import DashboardView
from .theme.styles import apply_global_style
from .theme.tokens import COLOR, FONT, SPACE
from .widgets.sessions_browser import SessionsBrowser

from . import analysis as _analysis  # noqa: F401  (autoload 카드)


# 기본 대시보드 레이아웃 — Phase A 까지의 카드 모두 배치
_DEFAULT_LAYOUT = [
    {"card_id": "context",            "col": 0, "row": 0, "w": 4,  "h": 2},
    {"card_id": "trace",              "col": 4, "row": 0, "w": 8,  "h": 4},
    {"card_id": "baseline_smo2",      "col": 0, "row": 2, "w": 4,  "h": 2},
    {"card_id": "min_peak",           "col": 4, "row": 4, "w": 4,  "h": 2},
    {"card_id": "slope_auc",          "col": 8, "row": 4, "w": 4,  "h": 2},
    {"card_id": "overrides",          "col": 0, "row": 6, "w": 5,  "h": 3},
    {"card_id": "tte",                "col": 5, "row": 6, "w": 4,  "h": 3},
    {"card_id": "comparison",         "col": 0, "row": 9, "w": 12, "h": 4},
]


class MainWindow(QMainWindow):
    """v2 메인 윈도우 — 대시보드 모델."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("physical_analysis · v2")
        self.resize(1600, 960)

        # 데이터
        self.loaded: dict[str, LoadedFile] = {}

        # 좌측 icon-bar + Sessions Browser dock + 메인 영역
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_icon_bar(root)

        # 우측 메인 영역
        right = QWidget()
        right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        root.addWidget(right, stretch=1)

        self._build_context_bar(rv)
        self._build_dashboard(rv)

        # Sessions Browser — 좌측 dock
        self._build_sessions_dock()

        # 메뉴바
        self._build_menu()

        # 빈 상태 표시
        self._refresh_context()

    # ──────────────────────────────────────────────
    #  좌측 icon-bar
    # ──────────────────────────────────────────────
    def _build_icon_bar(self, parent_layout: QHBoxLayout) -> None:
        bar = QFrame()
        bar.setObjectName("iconBar")
        bar.setFixedWidth(48)
        v = QVBoxLayout(bar)
        v.setContentsMargins(SPACE.xs, SPACE.sm, SPACE.xs, SPACE.sm)
        v.setSpacing(SPACE.xs)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        for icon_text, tooltip in [
            ("📊", "Dashboard (메인 분석)"),
            ("⊞",  "Compare"),
            ("📥", "Export"),
        ]:
            btn = QPushButton(icon_text)
            btn.setObjectName("navButton")
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedSize(36, 36)
            v.addWidget(btn)
            self._nav_group.addButton(btn)

        v.addStretch()

        load_btn = QPushButton("📂")
        load_btn.setObjectName("navButton")
        load_btn.setToolTip("폴더 열기 (Calf + cfg 페어 일괄 로드)  Ctrl+O")
        load_btn.setFixedSize(36, 36)
        load_btn.clicked.connect(self._on_open_folder)
        v.addWidget(load_btn)

        sess_btn = QPushButton("☰")
        sess_btn.setObjectName("navButton")
        sess_btn.setToolTip("Sessions 패널 토글  Ctrl+B")
        sess_btn.setFixedSize(36, 36)
        sess_btn.setCheckable(True)
        sess_btn.setChecked(True)
        sess_btn.clicked.connect(self._toggle_sessions_dock)
        v.addWidget(sess_btn)
        self._sess_toggle_btn = sess_btn

        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("navButton")
        settings_btn.setFixedSize(36, 36)
        settings_btn.setToolTip("Settings (미구현)")
        v.addWidget(settings_btn)

        if self._nav_group.buttons():
            self._nav_group.buttons()[0].setChecked(True)

        parent_layout.addWidget(bar)

    # ──────────────────────────────────────────────
    #  상단 context bar
    # ──────────────────────────────────────────────
    def _build_context_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = QFrame()
        bar.setObjectName("contextBar")
        bar.setFixedHeight(56)
        h = QHBoxLayout(bar)
        h.setContentsMargins(SPACE.lg, SPACE.sm, SPACE.lg, SPACE.sm)
        h.setSpacing(SPACE.md)

        h.addWidget(_label("Subject", FONT.caption, COLOR.text_2))
        self._subject_label = _label("—", FONT.body, COLOR.text_0, bold=True)
        h.addWidget(self._subject_label)

        h.addWidget(_sep())
        h.addWidget(_label("Condition", FONT.caption, COLOR.text_2))
        self.condition_combo = QComboBox()
        self.condition_combo.setMinimumWidth(120)
        self.condition_combo.currentTextChanged.connect(self._on_condition_changed)
        h.addWidget(self.condition_combo)

        h.addWidget(_label("Timepoint", FONT.caption, COLOR.text_2))
        self.timepoint_combo = QComboBox()
        self.timepoint_combo.setMinimumWidth(140)
        self.timepoint_combo.currentTextChanged.connect(self._on_timepoint_changed)
        h.addWidget(self.timepoint_combo)

        h.addStretch()

        self.add_card_btn = QPushButton("⊕  Add card")
        self.add_card_btn.setToolTip("등록된 분석 카드를 대시보드에 추가")
        self.add_card_btn.clicked.connect(self._on_add_card)
        h.addWidget(self.add_card_btn)

        self.analyze_btn = QPushButton("▶  Analyze")
        self.analyze_btn.setObjectName("primary")
        self.analyze_btn.setToolTip("현재 컨텍스트로 모든 카드 재계산")
        self.analyze_btn.clicked.connect(self._refresh_context)
        h.addWidget(self.analyze_btn)

        parent_layout.addWidget(bar)

    # ──────────────────────────────────────────────
    #  대시보드
    # ──────────────────────────────────────────────
    def _build_dashboard(self, parent_layout: QVBoxLayout) -> None:
        self.dashboard = DashboardView()
        parent_layout.addWidget(self.dashboard, stretch=1)
        self.dashboard.load_layout(_DEFAULT_LAYOUT)

    # ──────────────────────────────────────────────
    #  Sessions Browser dock
    # ──────────────────────────────────────────────
    def _build_sessions_dock(self) -> None:
        self.sessions_browser = SessionsBrowser()
        self.sessions_dock = QDockWidget("Sessions", self)
        self.sessions_dock.setWidget(self.sessions_browser)
        self.sessions_dock.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.sessions_dock.setMinimumWidth(220)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.sessions_dock)

        # 시그널 연결
        self.sessions_browser.open_folder_requested.connect(self._on_open_folder)
        self.sessions_browser.session_selected.connect(self._on_session_picked)
        self.sessions_browser.condition_selected.connect(self._on_condition_picked)

        # X 닫으면 토글 버튼도 동기화
        self.sessions_dock.visibilityChanged.connect(
            lambda v: self._sess_toggle_btn.setChecked(v)
        )

    def _toggle_sessions_dock(self, on: bool) -> None:
        self.sessions_dock.setVisible(on)

    # ──────────────────────────────────────────────
    #  메뉴바
    # ──────────────────────────────────────────────
    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")

        act_open = QAction("📂 Open folder…", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self._on_open_folder)
        file_menu.addAction(act_open)

        file_menu.addSeparator()

        act_load_params = QAction("📥 Load params…", self)
        act_load_params.triggered.connect(self._on_load_params)
        file_menu.addAction(act_load_params)

        act_save_params = QAction("💾 Save params…", self)
        act_save_params.setShortcut("Ctrl+S")
        act_save_params.triggered.connect(self._on_save_params)
        file_menu.addAction(act_save_params)

        file_menu.addSeparator()

        act_export = QAction("📊 Export current results…", self)
        act_export.setShortcut("Ctrl+E")
        act_export.triggered.connect(self._on_export_current)
        file_menu.addAction(act_export)

        act_export_all = QAction("📊 Export all sessions…", self)
        act_export_all.setShortcut("Ctrl+Shift+E")
        act_export_all.triggered.connect(self._on_export_all)
        file_menu.addAction(act_export_all)

        file_menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        view_menu = mb.addMenu("&View")
        act_toggle_sess = QAction("Toggle Sessions browser", self)
        act_toggle_sess.setShortcut("Ctrl+B")
        act_toggle_sess.setCheckable(True)
        act_toggle_sess.setChecked(True)
        act_toggle_sess.triggered.connect(
            lambda checked: self._toggle_sessions_dock(checked)
        )
        view_menu.addAction(act_toggle_sess)

        help_menu = mb.addMenu("&Help")
        act_about = QAction("About v2", self)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

    # ──────────────────────────────────────────────
    #  데이터 로드
    # ──────────────────────────────────────────────
    def _on_open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open measurement folder")
        if not folder:
            return
        self.load_folder(Path(folder))

    def load_folder(self, folder: Path) -> int:
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QApplication

        if not folder.is_dir():
            QMessageBox.warning(self, "폴더 없음", str(folder))
            return 0

        candidates = [p for p in sorted(folder.iterdir())
                      if p.is_file() and p.suffix.lower() in (".csv", ".txt", ".xlsx")]

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        loaded_count = 0
        try:
            for p in candidates:
                if not is_calf_timeseries(p):
                    continue
                try:
                    raw = load_calf(p)
                    sm = preprocess(raw)
                except Exception:  # noqa: BLE001
                    continue

                cfg = None
                cfg_path = find_config_for_calf(p)
                if cfg_path is not None:
                    try:
                        cfg = load_session_config(cfg_path)
                    except Exception:  # noqa: BLE001
                        pass

                cond = (cfg.condition if cfg and cfg.condition else p.stem)
                anchors = anchors_from_session_config(cfg) if cfg else {}
                lf = LoadedFile(
                    path=p, raw=raw, smoothed=sm, config=cfg,
                    dynamic_anchors=anchors,
                )
                self.loaded[cond] = lf
                loaded_count += 1
        finally:
            QApplication.restoreOverrideCursor()

        if loaded_count == 0:
            QMessageBox.information(
                self, "폴더 로드", f"로드된 파일이 없습니다:\n{folder}"
            )
            return 0

        self._populate_condition_combo()
        self.sessions_browser.set_loaded(self.loaded)
        return loaded_count

    def _populate_condition_combo(self) -> None:
        cur = self.condition_combo.currentText()
        self.condition_combo.blockSignals(True)
        self.condition_combo.clear()
        order = {"NOR": 0, "HYPO": 1, "HYPER": 2}
        names = sorted(self.loaded.keys(), key=lambda c: (order.get(c, 999), c))
        self.condition_combo.addItems(names)
        if cur and cur in names:
            self.condition_combo.setCurrentText(cur)
        self.condition_combo.blockSignals(False)
        if names:
            self._on_condition_changed(self.condition_combo.currentText())

    # ──────────────────────────────────────────────
    #  콤보 → 컨텍스트
    # ──────────────────────────────────────────────
    def _on_condition_changed(self, cond: str) -> None:
        if not cond:
            self._refresh_context()
            return
        lf = self.loaded.get(cond)
        cfg = getattr(lf, "config", None) if lf else None

        names: list[str] = []
        if cfg is not None and hasattr(cfg, "nirs_timepoints"):
            names = [tp.name for tp in cfg.nirs_timepoints() if tp.name]
        cur_tp = self.timepoint_combo.currentText()
        self.timepoint_combo.blockSignals(True)
        self.timepoint_combo.clear()
        self.timepoint_combo.addItems(names)
        if cur_tp and cur_tp in names:
            self.timepoint_combo.setCurrentText(cur_tp)
        self.timepoint_combo.blockSignals(False)
        self._refresh_context()

    def _on_timepoint_changed(self, _name: str) -> None:
        self._refresh_context()

    def _on_session_picked(self, cond: str, tp: str) -> None:
        """Sessions browser 더블클릭 — condition + timepoint 동시 전환."""
        if cond and cond != self.condition_combo.currentText():
            self.condition_combo.setCurrentText(cond)
        if tp and tp != self.timepoint_combo.currentText():
            self.timepoint_combo.setCurrentText(tp)

    def _on_condition_picked(self, cond: str) -> None:
        if cond and cond != self.condition_combo.currentText():
            self.condition_combo.setCurrentText(cond)

    def _refresh_context(self) -> None:
        cond = self.condition_combo.currentText()
        tp = self.timepoint_combo.currentText()
        lf = self.loaded.get(cond)
        cfg = getattr(lf, "config", None) if lf else None

        if cfg is not None and cfg.subject_info:
            name = cfg.subject_info.get("Name") or cfg.subject_info.get("ID(Protocol)") or "—"
            self._subject_label.setText(name)
        else:
            self._subject_label.setText("—")

        if lf is None or cfg is None or not tp:
            ctx = AnalysisContext.empty()
            ctx.condition = cond
            ctx.timepoint = tp
            ctx.cfg = cfg
            ctx.all_loaded = dict(self.loaded)
            ctx.apply = self._apply_dispatcher
        else:
            anchors = lf.dynamic_anchors or anchors_from_session_config(cfg)
            anchor = anchors.get(tp)
            ctx = AnalysisContext(
                subject_info=cfg.subject_info or {},
                condition=cond,
                timepoint=tp,
                smoothed=lf.smoothed,
                anchor=anchor,
                overrides=lf.overrides.get(tp, {}) if hasattr(lf, "overrides") else {},
                vot_truth=cfg.vot_truth.get(_session_to_truth(tp), {}),
                all_loaded=dict(self.loaded),
                cfg=cfg,
                apply=self._apply_dispatcher,
            )
        self.dashboard.set_context(ctx)

    # ──────────────────────────────────────────────
    #  편집 카드 → mainwindow dispatcher
    # ──────────────────────────────────────────────
    def _apply_dispatcher(self, action: str, payload) -> None:
        """편집 카드들이 ctx.apply(action, payload) 로 호출. 액션별 분기."""
        cond = self.condition_combo.currentText()
        tp = self.timepoint_combo.currentText()
        lf = self.loaded.get(cond)
        if lf is None or lf.config is None:
            QMessageBox.warning(self, "Apply 실패", "데이터가 로드되지 않았습니다.")
            return

        cfg = lf.config
        try:
            if action == ACTION_SUBJECT_INFO:
                cfg.subject_info = dict(payload or {})

            elif action == ACTION_TIMEPOINTS:
                cfg.timepoints["NIRS_VOT"] = list(payload or [])
                # anchor 재산출
                lf.dynamic_anchors = anchors_from_session_config(cfg)
                # timepoint 콤보 갱신
                names = [tp_o.name for tp_o in cfg.nirs_timepoints() if tp_o.name]
                cur = self.timepoint_combo.currentText()
                self.timepoint_combo.blockSignals(True)
                self.timepoint_combo.clear()
                self.timepoint_combo.addItems(names)
                if cur in names:
                    self.timepoint_combo.setCurrentText(cur)
                self.timepoint_combo.blockSignals(False)
                self.sessions_browser.set_loaded(self.loaded)

            elif action == ACTION_TTE:
                ex = cfg.timepoints.setdefault("exercise", {})
                ex.update(payload or {})

            elif action == ACTION_OVERRIDES:
                ov = lf.overrides.setdefault(tp, {})
                # 빈 payload 면 모든 override 제거
                ov.clear()
                for k in ("baseline", "min_time", "peak_time"):
                    if k in payload:
                        ov[k] = payload[k]

            elif action == ACTION_AUTO_DETECT:
                self._run_auto_detect(lf, tp)

            else:
                QMessageBox.information(self, "Apply", f"알 수 없는 액션: {action}")
                return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Apply 실패", f"{type(exc).__name__}: {exc}")
            return

        # 변경 후 컨텍스트 재전파 → 모든 카드 재계산
        self._refresh_context()

    def _run_auto_detect(self, lf, tp: str) -> None:
        """v1 의 auto_detect 로직 — Min/Peak 정밀 검출."""
        try:
            from nirs_vot.metrics import compute_metrics
        except ImportError:
            return
        anchor = lf.dynamic_anchors.get(tp) if lf.dynamic_anchors else None
        if anchor is None:
            return
        try:
            r = compute_metrics(lf.smoothed, anchor, "?", tp)
            ov = lf.overrides.setdefault(tp, {})
            mt = getattr(r, "min_time", None)
            pt = getattr(r, "peak_time", None)
            if mt is not None:
                ov["min_time"] = mt.time().replace(microsecond=0) if hasattr(mt, "time") else mt
            if pt is not None:
                ov["peak_time"] = pt.time().replace(microsecond=0) if hasattr(pt, "time") else pt
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Auto detect", f"검출 실패: {exc}")

    # ──────────────────────────────────────────────
    #  + Add card
    # ──────────────────────────────────────────────
    def _on_add_card(self) -> None:
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        cats = by_category()
        for cat in sorted(cats.keys()):
            cat_menu = menu.addMenu(cat)
            for cls in cats[cat]:
                act = cat_menu.addAction(f"{cls.meta.icon}  {cls.meta.name}")
                act.triggered.connect(lambda _checked=False, cid=cls.meta.id: self._add_card_from_palette(cid))
        menu.exec(self.add_card_btn.mapToGlobal(self.add_card_btn.rect().bottomLeft()))

    def _add_card_from_palette(self, card_id: str) -> None:
        slot = self.dashboard.add_card(card_id)
        if slot is None:
            QMessageBox.warning(self, "카드 추가 실패", f"등록되지 않은 카드: {card_id}")

    # ──────────────────────────────────────────────
    #  Save / Load params (v1 의 parameter_io 재사용)
    # ──────────────────────────────────────────────
    def _on_save_params(self) -> None:
        cond = self.condition_combo.currentText()
        lf = self.loaded.get(cond)
        if lf is None or lf.config is None:
            QMessageBox.information(self, "Save params", "현재 condition 데이터가 없습니다.")
            return
        try:
            from nirs_vot_gui.widgets import parameter_io as pio  # type: ignore
        except ImportError as exc:
            QMessageBox.critical(self, "Save params", f"v1 parameter_io import 실패: {exc}")
            return

        # parameter_io.serialize 는 v1 의 ParameterPanel 인스턴스가 필요 →
        # 직접 panel-less 직렬화 (Subject + NIRS_VOT + HRV + Exercise + Lock)
        rows = self._serialize_session_params(lf)
        default = f"{lf.config.file_path.stem}_params.xlsx" if lf.config.file_path else "params.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save params", default,
            "Excel (*.xlsx);;CSV (*.csv);;Text/INI (*.txt)",
        )
        if not path:
            return
        try:
            pio.save(path, rows)
            QMessageBox.information(self, "Save params", f"저장 완료:\n{path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save params", str(exc))

    def _on_load_params(self) -> None:
        cond = self.condition_combo.currentText()
        lf = self.loaded.get(cond)
        if lf is None or lf.config is None:
            QMessageBox.information(self, "Load params", "먼저 폴더를 로드하세요.")
            return
        try:
            from nirs_vot_gui.widgets import parameter_io as pio  # type: ignore
        except ImportError as exc:
            QMessageBox.critical(self, "Load params", f"v1 parameter_io import 실패: {exc}")
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Load params", "",
            "Parameters (*.xlsx *.csv *.txt);;All files (*)",
        )
        if not path:
            return
        try:
            state = pio.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load params", str(exc))
            return
        applied = self._apply_loaded_params(lf, state)
        # 변경 사항 컨텍스트 재전파
        self._refresh_context()
        QMessageBox.information(self, "Load params", f"적용 완료: {applied} 키")

    def _serialize_session_params(self, lf) -> list[tuple[str, str, str]]:
        """v1 parameter_io 의 schema 와 호환되는 트리플 시퀀스 생성."""
        try:
            from nirs_vot_gui.widgets import parameter_io as pio  # type: ignore
        except ImportError:
            return []
        cfg = lf.config
        rows: list[tuple[str, str, str]] = []

        # Subject
        info = cfg.subject_info or {}
        for k in pio.SUBJECT_KEYS:
            rows.append(("Subject", k, pio._fmt(info.get(k))))

        # NIRS_VOT — indexed
        tps = list(cfg.nirs_timepoints()) if hasattr(cfg, "nirs_timepoints") else []
        rows.append(("NIRS_VOT", "count", pio._fmt(len(tps))))
        for i, tp in enumerate(tps, start=1):
            rows.append(("NIRS_VOT", f"{i}.name", tp.name))
            rows.append(("NIRS_VOT", f"{i}.start", pio._fmt(tp.start)))
            rows.append(("NIRS_VOT", f"{i}.end", pio._fmt(tp.end)))
            rows.append(("NIRS_VOT", f"{i}.lead", pio._fmt(int(tp.lead))))
            rows.append(("NIRS_VOT", f"{i}.tail", pio._fmt(int(tp.tail))))

        # HRV
        for sess in ("Baseline", "Recovery2"):
            w = cfg.timepoints.get("HRV", {}).get(sess) if hasattr(cfg, "timepoints") else None
            rows.append(("HRV", f"{sess}.start", pio._fmt(w.start) if w else ""))
            rows.append(("HRV", f"{sess}.end", pio._fmt(w.end) if w else ""))

        # Exercise
        ex = cfg.timepoints.get("exercise", {}) if hasattr(cfg, "timepoints") else {}
        rows.append(("Exercise", "TTE1", pio._fmt(ex.get("TTE1")) if ex.get("TTE1") else ""))
        rows.append(("Exercise", "TTE2", pio._fmt(ex.get("TTE2")) if ex.get("TTE2") else ""))
        rows.append(("Exercise", "TTE_maintenance_rate",
                     pio._fmt(float(ex.get("TTE_maintenance_rate", 0.0)))))

        return rows

    def _apply_loaded_params(self, lf, state: list) -> int:
        """v1 parameter_io 형식 트리플 → cfg 에 직접 적용 (panel 우회)."""
        try:
            from nirs_vot_gui.widgets import parameter_io as pio  # type: ignore
            from config_loader import Timepoint  # type: ignore
        except ImportError:
            return 0

        cfg = lf.config
        applied = 0
        state_dict = {(s.strip(), k.strip()): v for s, k, v in state}

        # Subject
        info = dict(cfg.subject_info or {})
        for k in pio.SUBJECT_KEYS:
            v = state_dict.get(("Subject", k))
            if v is None:
                continue
            info[k] = v if v else None
            applied += 1
        cfg.subject_info = info

        # NIRS_VOT
        count_v = state_dict.get(("NIRS_VOT", "count"))
        if count_v is not None:
            try:
                n = int(float(count_v))
            except ValueError:
                n = 0
            tps: list = []
            for i in range(1, n + 1):
                name = (state_dict.get(("NIRS_VOT", f"{i}.name")) or "").strip()
                s = pio._parse_time(state_dict.get(("NIRS_VOT", f"{i}.start"), ""))
                e = pio._parse_time(state_dict.get(("NIRS_VOT", f"{i}.end"), ""))
                if not name or s is None or e is None:
                    continue
                lead_v = state_dict.get(("NIRS_VOT", f"{i}.lead"), "60")
                tail_v = state_dict.get(("NIRS_VOT", f"{i}.tail"), "180")
                try:
                    lead = int(float(lead_v))
                    tail = int(float(tail_v))
                except (TypeError, ValueError):
                    lead, tail = 60, 180
                tps.append(Timepoint(name=name, start=s, end=e, lead=lead, tail=tail))
                applied += 5
            if tps:
                cfg.timepoints["NIRS_VOT"] = tps
                lf.dynamic_anchors = anchors_from_session_config(cfg)

        # Exercise
        for k in ("TTE1", "TTE2"):
            v = state_dict.get(("Exercise", k))
            if v is None:
                continue
            t = pio._parse_time(v)
            if t is None and v:
                continue
            ex = cfg.timepoints.setdefault("exercise", {})
            if t is not None:
                ex[k] = t
            applied += 1
        v = state_dict.get(("Exercise", "TTE_maintenance_rate"))
        if v is not None and v != "":
            try:
                cfg.timepoints.setdefault("exercise", {})["TTE_maintenance_rate"] = float(v)
                applied += 1
            except ValueError:
                pass

        return applied

    # ──────────────────────────────────────────────
    #  Export
    # ──────────────────────────────────────────────
    def _on_export_current(self) -> None:
        cond = self.condition_combo.currentText()
        tp = self.timepoint_combo.currentText()
        lf = self.loaded.get(cond)
        if lf is None or lf.config is None or not tp:
            QMessageBox.information(self, "Export", "분석할 데이터·timepoint 가 필요합니다.")
            return
        try:
            from nirs_vot.metrics import compute_metrics
            from nirs_vot_gui.widgets.parameter_table import ParameterTable  # type: ignore
        except ImportError as exc:
            QMessageBox.critical(self, "Export", f"v1 모듈 import 실패: {exc}")
            return
        anchor = lf.dynamic_anchors.get(tp)
        if anchor is None:
            QMessageBox.information(self, "Export", "anchor 가 없습니다 (timepoint 설정 확인).")
            return
        try:
            ov = lf.overrides.get(tp, {}) if hasattr(lf, "overrides") else {}
            r = compute_metrics(
                lf.smoothed, anchor, cond, tp,
                override_baseline=ov.get("baseline"),
                override_min_time=ov.get("min_time"),
                override_peak_time=ov.get("peak_time"),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export", f"분석 실패: {exc}")
            return
        default = f"{cond}_{tp}_results.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export results", default,
            "Excel (*.xlsx);;CSV (*.csv);;Text (*.txt)",
        )
        if not path:
            return
        p = Path(path)
        try:
            ext = p.suffix.lower()
            if ext in (".xlsx", ".xls"):
                ParameterTable._write_single_session_xlsx(p, r, lf.config)
            elif ext == ".txt":
                ParameterTable._write_single_session_txt(p, r, lf.config)
            else:
                ParameterTable._write_single_session_csv(p, r, lf.config)
            QMessageBox.information(self, "Export", f"저장 완료:\n{p}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export", str(exc))

    def _on_export_all(self) -> None:
        if not self.loaded:
            QMessageBox.information(self, "Export all", "로드된 데이터가 없습니다.")
            return
        try:
            from nirs_vot.metrics import compute_metrics
            from nirs_vot_gui.widgets.parameter_table import ParameterTable  # type: ignore
        except ImportError as exc:
            QMessageBox.critical(self, "Export all", f"v1 모듈 import 실패: {exc}")
            return

        rows: list[dict] = []
        for cond, lf in self.loaded.items():
            cfg = lf.config
            if cfg is None:
                continue
            for tp in cfg.nirs_timepoints():
                anchor = lf.dynamic_anchors.get(tp.name) if lf.dynamic_anchors else None
                if anchor is None:
                    continue
                try:
                    r = compute_metrics(lf.smoothed, anchor, cond, tp.name)
                except Exception:  # noqa: BLE001
                    continue
                row = {
                    "condition": cond, "session": tp.name,
                    "subject_name": (cfg.subject_info or {}).get("Name", ""),
                    "baseline_smo2": getattr(r, "baseline_smo2", None),
                    "min_smo2": getattr(r, "min_smo2", None),
                    "peak_smo2": getattr(r, "peak_smo2", None),
                    "magnitude": getattr(r, "magnitude", None),
                    "slope1_30_150": getattr(r, "slope1_30_150", None),
                    "slope2_0_10": getattr(r, "slope2_0_10", None),
                    "t50_sec": getattr(r, "t50_sec", None),
                    "auc_3min": getattr(r, "auc_3min", None),
                }
                rows.append(row)
        if not rows:
            QMessageBox.information(self, "Export all", "분석 가능한 세션이 없습니다.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export all sessions", "all_sessions.xlsx",
            "Excel (*.xlsx);;CSV (*.csv);;Text (*.txt)",
        )
        if not path:
            return
        try:
            ParameterTable.write_multi_session(Path(path), rows)
            QMessageBox.information(self, "Export all", f"저장 완료:\n{path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export all", str(exc))

    # ──────────────────────────────────────────────
    def _on_about(self) -> None:
        QMessageBox.about(
            self, "About v2",
            "physical_analysis · v2.0.0-alpha\n"
            "대시보드 + 카드 기반 분석 도구\n"
            "v1 (nirs_vot_gui) 의 분석 엔진 그대로 재사용.\n\n"
            "단축키: Ctrl+O 폴더 열기 · Ctrl+S Save params · Ctrl+E Export · Ctrl+B Sessions"
        )


# ──────────────────────────────────────────────
#  helpers
# ──────────────────────────────────────────────
def _label(text: str, size: int, color: str, *, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    weight = FONT.w_semibold if bold else FONT.w_regular
    lbl.setStyleSheet(
        f"color: {color}; font-size: {size}px; font-weight: {weight}; background: transparent;"
    )
    return lbl


def _sep() -> QLabel:
    s = QLabel("│")
    s.setStyleSheet(f"color: {COLOR.border_strong};")
    return s


def _session_to_truth(tp: str) -> str:
    return "Baseline" if tp == "Baseline" else ("Post" if tp == "Recovery2" else tp)
