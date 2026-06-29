"""TimepointsEditorCard — NIRS_VOT timepoint 동적 편집 카드.

v1 의 ``_TimepointRow`` 패턴 재사용. 행 추가/삭제/이름·시각·lead·tail 편집 + Apply.
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ..cards import (
    ACTION_TIMEPOINTS,
    AnalysisCard,
    AnalysisContext,
    CardMeta,
    register,
)
from ..theme.tokens import COLOR, FONT, SPACE


def _qtime_to_t(q: QTime) -> dt.time:
    return dt.time(q.hour(), q.minute(), q.second())


class _TimepointRow(QWidget):
    """한 timepoint 행 — Name · Start · End · Lead · Tail · ✕"""

    deleted = Signal(object)

    def __init__(self, parent=None, *, tp=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SPACE.xs)

        self.name_edit = QLineEdit(getattr(tp, "name", "") if tp else "")
        self.name_edit.setPlaceholderText("이름")
        self.name_edit.setMinimumWidth(80)
        self.name_edit.setMaximumWidth(110)
        lay.addWidget(self.name_edit, stretch=2)

        self.start_edit = QTimeEdit()
        self.start_edit.setDisplayFormat("HH:mm:ss")
        if tp is not None:
            self.start_edit.setTime(QTime(tp.start.hour, tp.start.minute, tp.start.second))
        lay.addWidget(self.start_edit, stretch=2)

        self.end_edit = QTimeEdit()
        self.end_edit.setDisplayFormat("HH:mm:ss")
        if tp is not None:
            self.end_edit.setTime(QTime(tp.end.hour, tp.end.minute, tp.end.second))
        lay.addWidget(self.end_edit, stretch=2)

        self.lead_spin = QSpinBox()
        self.lead_spin.setRange(0, 600)
        self.lead_spin.setSuffix(" s")
        self.lead_spin.setValue(int(tp.lead) if tp else 60)
        lay.addWidget(self.lead_spin, stretch=1)

        self.tail_spin = QSpinBox()
        self.tail_spin.setRange(0, 1200)
        self.tail_spin.setSuffix(" s")
        self.tail_spin.setValue(int(tp.tail) if tp else 180)
        lay.addWidget(self.tail_spin, stretch=1)

        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedWidth(24)
        self.del_btn.setToolTip("이 행 삭제")
        self.del_btn.clicked.connect(lambda: self.deleted.emit(self))
        lay.addWidget(self.del_btn, stretch=0)

    def to_timepoint(self):
        try:
            from config_loader import Timepoint  # type: ignore
        except ImportError:
            return None
        name = self.name_edit.text().strip()
        if not name:
            return None
        s = _qtime_to_t(self.start_edit.time())
        e = _qtime_to_t(self.end_edit.time())
        if s == dt.time(0, 0, 0) and e == dt.time(0, 0, 0):
            return None
        return Timepoint(
            name=name, start=s, end=e,
            lead=int(self.lead_spin.value()),
            tail=int(self.tail_spin.value()),
        )


@register
class TimepointsEditorCard:
    meta = CardMeta(
        id="timepoints_editor",
        name="NIRS_VOT timepoints (편집)",
        category="NIRS",
        icon="◷",
        description="timepoint 추가·삭제·시각·lead·tail 편집 — Apply 시 cfg/anchor 재산출",
        default_size=(8, 4),
    )

    def compute(self, ctx: AnalysisContext) -> dict:
        tps: list = []
        if ctx.cfg is not None and hasattr(ctx.cfg, "nirs_timepoints"):
            tps = list(ctx.cfg.nirs_timepoints())
        return {"timepoints": tps, "apply": ctx.apply}

    def render(self, parent: QWidget, data: dict) -> QWidget:
        root = QWidget(parent)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(SPACE.sm)

        # 헤더
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(SPACE.xs)
        for label, stretch in (
            ("Name", 2), ("Start", 2), ("End", 2), ("Lead", 1), ("Tail", 1),
        ):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")
            hdr.addWidget(lbl, stretch=stretch)
        spacer = QLabel("")
        spacer.setFixedWidth(24)
        hdr.addWidget(spacer, stretch=0)
        v.addLayout(hdr)

        # 행 컨테이너
        rows_container = QVBoxLayout()
        rows_container.setContentsMargins(0, 0, 0, 0)
        rows_container.setSpacing(SPACE.xs)
        v.addLayout(rows_container)

        rows: list[_TimepointRow] = []

        def add_row(tp=None):
            r = _TimepointRow(root, tp=tp)
            r.deleted.connect(lambda x: remove_row(x))
            rows.append(r)
            rows_container.addWidget(r)
            return r

        def remove_row(r):
            tp = r.to_timepoint()
            if tp is not None:
                ans = QMessageBox.question(
                    root, "삭제 확인",
                    f"'{tp.name}' 행을 삭제하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if ans != QMessageBox.Yes:
                    return
            if r in rows:
                rows.remove(r)
                rows_container.removeWidget(r)
                r.setParent(None)
                r.deleteLater()

        # 기존 timepoint 채우기
        for tp in data.get("timepoints", []):
            add_row(tp)

        # 추가 버튼 + Apply
        btn_row = QHBoxLayout()
        add_btn = QPushButton("＋  Add timepoint")
        add_btn.setMaximumWidth(160)

        def _on_add():
            existing = {r.name_edit.text().strip() for r in rows
                        if r.name_edit.text().strip()}
            n = 1
            while f"Custom{n}" in existing:
                n += 1
            new_row = add_row()
            new_row.name_edit.setText(f"Custom{n}")
            new_row.name_edit.selectAll()
            new_row.name_edit.setFocus()

        add_btn.clicked.connect(_on_add)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()

        apply_btn = QPushButton("▶ Apply")
        apply_btn.setObjectName("primary")

        def _on_apply():
            tps = []
            seen = set()
            for r in rows:
                tp = r.to_timepoint()
                if tp is None or tp.name in seen:
                    continue
                seen.add(tp.name)
                tps.append(tp)
            cb = data.get("apply")
            if callable(cb):
                cb(ACTION_TIMEPOINTS, tps)

        apply_btn.clicked.connect(_on_apply)
        btn_row.addWidget(apply_btn)
        v.addLayout(btn_row)
        v.addStretch()
        root.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return root
