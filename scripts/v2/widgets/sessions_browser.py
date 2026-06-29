"""SessionsBrowser — 좌측 dock. 로드된 condition × timepoint 트리.

더블클릭 → 그 (condition, timepoint) 로 컨텍스트 전환.
v1 의 ``data_browser.py`` 와 같은 역할이지만 라이트 톤·트리만 (Open 버튼은 메뉴/icon-bar).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..theme.tokens import COLOR, FONT, SPACE


class SessionsBrowser(QWidget):
    """헤더 + 트리. NIRS 분석 페이지의 좌측 패널."""

    open_folder_requested = Signal()
    session_selected = Signal(str, str)        # (condition, timepoint)
    condition_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loaded: dict = {}

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 헤더
        hdr = QFrame()
        hdr.setStyleSheet(
            f"background: {COLOR.bg_1}; border-bottom: 1px solid {COLOR.border};"
        )
        hdr_lay = QVBoxLayout(hdr)
        hdr_lay.setContentsMargins(SPACE.md, SPACE.sm, SPACE.md, SPACE.sm)
        hdr_lay.setSpacing(SPACE.xs)

        title = QLabel("Sessions")
        title.setStyleSheet(
            f"color: {COLOR.text_2}; font-size: {FONT.caption}px; "
            f"font-weight: {FONT.w_semibold}; letter-spacing: 0.5px;"
        )
        hdr_lay.addWidget(title)

        open_btn = QPushButton("📂  Open folder…")
        open_btn.setStyleSheet(
            f"text-align: left; padding: 6px 8px; border-radius: 6px; "
            f"background: {COLOR.bg_2}; border: 1px solid {COLOR.border};"
        )
        open_btn.clicked.connect(self.open_folder_requested.emit)
        hdr_lay.addWidget(open_btn)
        v.addWidget(hdr)

        # 트리
        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(True)
        self.tree.setStyleSheet(
            f"QTreeView {{ background: {COLOR.bg_1}; border: none; "
            f"color: {COLOR.text_0}; padding: 6px; }} "
            f"QTreeView::item:hover {{ background: {COLOR.bg_2}; }} "
            f"QTreeView::item:selected {{ background: {COLOR.bg_3}; "
            f"color: {COLOR.accent}; }}"
        )
        self._model = QStandardItemModel(self)
        self.tree.setModel(self._model)
        self.tree.doubleClicked.connect(self._on_double_clicked)
        v.addWidget(self.tree, stretch=1)

        self._render_empty()

    def set_loaded(self, loaded: dict) -> None:
        """``{condition: LoadedFile}`` 로 트리 빌드."""
        self._loaded = dict(loaded) if loaded else {}
        self._model.clear()
        if not self._loaded:
            self._render_empty()
            return
        self._render_loaded()
        self.tree.expandAll()

    def clear(self) -> None:
        self._loaded = {}
        self._model.clear()
        self._render_empty()

    def _render_empty(self) -> None:
        item = QStandardItem("(데이터 없음)\n  📂 위 버튼으로 폴더 로드")
        item.setEditable(False)
        item.setEnabled(False)
        self._model.invisibleRootItem().appendRow(item)

    def _render_loaded(self) -> None:
        root = self._model.invisibleRootItem()

        # subject 추출
        subject = ""
        for lf in self._loaded.values():
            cfg = getattr(lf, "config", None)
            if cfg and cfg.subject_info:
                subject = cfg.subject_info.get("Name") or cfg.subject_info.get("ID(Protocol)") or ""
                if subject:
                    break
        subj_item = QStandardItem(f"🧍  {subject or 'Subject'}")
        subj_item.setEditable(False)
        subj_item.setData({"type": "subject"}, Qt.UserRole)
        root.appendRow(subj_item)

        order = {"NOR": 0, "HYPO": 1, "HYPER": 2}
        sorted_conds = sorted(self._loaded.keys(), key=lambda c: (order.get(c, 999), c))

        for cond in sorted_conds:
            lf = self._loaded[cond]
            cfg = getattr(lf, "config", None)

            cond_item = QStandardItem(f"🫁  {cond}")
            cond_item.setEditable(False)
            cond_item.setData({"type": "condition", "condition": cond}, Qt.UserRole)
            subj_item.appendRow(cond_item)

            # timepoints
            tp_names: list[str] = []
            if cfg is not None and hasattr(cfg, "nirs_timepoints"):
                tp_names = [tp.name for tp in cfg.nirs_timepoints() if tp.name]
            if not tp_names:
                tp_names = ["Baseline", "Recovery2"]

            for tp_name in tp_names:
                clock = ""
                if cfg is not None:
                    win = cfg.nirs_vot_window(tp_name) if hasattr(cfg, "nirs_vot_window") else None
                    if win:
                        clock = f"   {win.start.strftime('%H:%M:%S')} → {win.end.strftime('%H:%M:%S')}"
                sess_item = QStandardItem(f"📍  {tp_name}{clock}")
                sess_item.setEditable(False)
                sess_item.setData({
                    "type": "session",
                    "condition": cond,
                    "session": tp_name,
                }, Qt.UserRole)
                cond_item.appendRow(sess_item)

    def _on_double_clicked(self, idx: QModelIndex) -> None:
        item = self._model.itemFromIndex(idx)
        if item is None:
            return
        data = item.data(Qt.UserRole) or {}
        kind = data.get("type")
        if kind == "session":
            self.session_selected.emit(data["condition"], data["session"])
        elif kind == "condition":
            self.condition_selected.emit(data["condition"])
