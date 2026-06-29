"""SubjectEditorCard — 피험자 메타 19 필드 편집 카드.

v1 의 ``ParameterPanel._INFO_FIELDS`` 스펙 재사용. Apply 시 ctx.apply(SUBJECT_INFO, dict).
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..cards import (
    ACTION_SUBJECT_INFO,
    AnalysisCard,
    AnalysisContext,
    CardMeta,
    register,
)
from ..theme.tokens import COLOR, FONT, SPACE


# v1 의 _INFO_FIELDS 와 동일 스펙
_INFO_FIELDS: list[tuple[str, str, str, dict]] = [
    ("ID(Protocol)",  "ID",            "text",   {}),
    ("Name",          "Name",          "text",   {}),
    ("D.O.B",         "D.O.B",         "date",   {}),
    ("Age",           "Age",           "int",    {"min": 0, "max": 150}),
    ("Gender",        "Gender",        "gender", {}),
    ("Weight(kg)",    "Weight (kg)",   "float",  {"min": 0.0, "max": 250.0, "step": 0.1, "decimals": 2}),
    ("Height(cm)",    "Height (cm)",   "float",  {"min": 0.0, "max": 250.0, "step": 0.1, "decimals": 1}),
    ("Wattmax",       "Wattmax",       "int",    {"min": 0, "max": 1000}),
    ("VO2max",        "VO2max",        "float",  {"min": 0.0, "max": 100.0, "step": 0.1, "decimals": 2}),
    ("W/kg",          "W/kg",          "float",  {"min": 0.0, "max": 20.0,  "step": 0.01,"decimals": 4}),
    ("FTP",           "FTP",           "float",  {"min": 0.0, "max": 1000.0,"step": 0.5, "decimals": 1}),
    ("AT(VT1)",       "AT (VT1)",      "float",  {"min": 0.0, "max": 1000.0,"step": 0.5, "decimals": 1}),
    ("RC(VT2)",       "RC (VT2)",      "float",  {"min": 0.0, "max": 1000.0,"step": 0.5, "decimals": 1}),
    ("Wattmax(90%)",  "Wattmax(90%)",  "float",  {"min": 0.0, "max": 1000.0,"step": 0.1, "decimals": 1}),
    ("Wattmax(40%)",  "Wattmax(40%)",  "float",  {"min": 0.0, "max": 1000.0,"step": 0.1, "decimals": 1}),
    ("Wattmax(110%)", "Wattmax(110%)", "float",  {"min": 0.0, "max": 1000.0,"step": 0.1, "decimals": 1}),
    ("안장 높이",      "Saddle (cm)",   "float",  {"min": 0.0, "max": 200.0, "step": 0.1, "decimals": 1}),
    ("안정시 심박수",  "Resting HR",    "int",    {"min": 0, "max": 250}),
]


def _make_input(kind: str, opts: dict) -> QWidget:
    if kind == "text":
        w = QLineEdit()
        w.setClearButtonEnabled(True)
        return w
    if kind == "int":
        w = QSpinBox()
        w.setRange(opts.get("min", -10**9), opts.get("max", 10**9))
        return w
    if kind == "float":
        w = QDoubleSpinBox()
        w.setRange(opts.get("min", -1e9), opts.get("max", 1e9))
        w.setSingleStep(opts.get("step", 0.1))
        w.setDecimals(opts.get("decimals", 2))
        return w
    if kind == "gender":
        w = QComboBox()
        w.addItems(["", "Male", "Female", "Other"])
        return w
    if kind == "date":
        w = QDateEdit()
        w.setDisplayFormat("yyyy-MM-dd")
        w.setCalendarPopup(True)
        w.setMinimumDate(QDate(1900, 1, 1))
        w.setMaximumDate(QDate(2100, 12, 31))
        w.setDate(QDate(1900, 1, 1))
        return w
    raise ValueError(f"unknown kind: {kind}")


def _set_input(w: QWidget, kind: str, value) -> None:
    if value is None:
        if kind == "text": w.setText("")
        elif kind == "int": w.setValue(0)
        elif kind == "float": w.setValue(0.0)
        elif kind == "gender": w.setCurrentIndex(0)
        elif kind == "date": w.setDate(QDate(1900, 1, 1))
        return
    if kind == "text":
        w.setText(str(value))
    elif kind == "int":
        try: w.setValue(int(value))
        except (TypeError, ValueError): w.setValue(0)
    elif kind == "float":
        try: w.setValue(float(value))
        except (TypeError, ValueError): w.setValue(0.0)
    elif kind == "gender":
        s = str(value).strip()
        idx = w.findText(s, Qt.MatchFixedString)
        w.setCurrentIndex(idx if idx >= 0 else 0)
    elif kind == "date":
        if isinstance(value, dt.datetime):
            d = value.date()
            w.setDate(QDate(d.year, d.month, d.day))
        elif isinstance(value, dt.date):
            w.setDate(QDate(value.year, value.month, value.day))


def _get_input(w: QWidget, kind: str):
    if kind == "text":
        s = w.text().strip()
        return s or None
    if kind == "int":
        return int(w.value())
    if kind == "float":
        return float(w.value())
    if kind == "gender":
        s = w.currentText().strip()
        return s or None
    if kind == "date":
        q: QDate = w.date()
        if q == QDate(1900, 1, 1):
            return None
        return dt.datetime(q.year(), q.month(), q.day())
    return None


@register
class SubjectEditorCard:
    meta = CardMeta(
        id="subject_editor",
        name="Subject info (편집)",
        category="NIRS",
        icon="✎",
        description="피험자 19 필드 직접 편집 — Apply 시 cfg.subject_info 갱신",
        default_size=(6, 5),
    )

    def compute(self, ctx: AnalysisContext) -> dict:
        return {"info": ctx.subject_info or {}, "apply": ctx.apply}

    def render(self, parent: QWidget, data: dict) -> QWidget:
        root = QWidget(parent)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(SPACE.sm)

        form = QFormLayout()
        form.setHorizontalSpacing(SPACE.md)
        form.setVerticalSpacing(SPACE.xs)

        info: dict = data.get("info") or {}
        inputs: dict = {}
        for key, label, kind, opts in _INFO_FIELDS:
            w = _make_input(kind, opts)
            _set_input(w, kind, info.get(key))
            inputs[key] = (kind, w)
            form.addRow(label + ":", w)
        outer.addLayout(form, stretch=1)

        # Apply
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        apply_btn = QPushButton("▶ Apply")
        apply_btn.setObjectName("primary")

        def _on_apply() -> None:
            new_info: dict = {}
            for key, (kind, w) in inputs.items():
                new_info[key] = _get_input(w, kind)
            cb = data.get("apply")
            if callable(cb):
                cb(ACTION_SUBJECT_INFO, new_info)

        apply_btn.clicked.connect(_on_apply)
        btn_row.addWidget(apply_btn)
        outer.addLayout(btn_row)
        root.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return root
