"""TTECard — Exercise / Time-To-Exhaustion 표시 + 편집.

cfg.timepoints['exercise'] 의 TTE1 / TTE2 / TTE_maintenance_rate 표시 + Apply 시 갱신.
v1 의 maintenance < 70% 경고 패턴 유지.
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..cards import (
    ACTION_TTE,
    AnalysisCard,
    AnalysisContext,
    CardMeta,
    register,
)
from ..theme.tokens import COLOR, FONT, SPACE


def _time_to_seconds(t) -> int:
    if t is None:
        return 0
    if isinstance(t, dt.time):
        return t.hour * 3600 + t.minute * 60 + t.second
    if isinstance(t, dt.timedelta):
        return int(t.total_seconds())
    if isinstance(t, (int, float)):
        return max(0, int(t))
    return 0


def _seconds_to_time(s: int) -> dt.time:
    s = max(0, int(s))
    h = (s // 3600) % 24
    m = (s % 3600) // 60
    sec = s % 60
    return dt.time(h, m, sec)


@register
class TTECard:
    meta = CardMeta(
        id="tte",
        name="Exercise · TTE",
        category="NIRS",
        icon="🏃",
        description="Time-To-Exhaustion (TTE1/TTE2) + Maintenance rate. <70% 경고.",
        default_size=(4, 3),
    )

    def compute(self, ctx: AnalysisContext) -> dict:
        ex: dict = {}
        if ctx.cfg is not None and hasattr(ctx.cfg, "timepoints"):
            ex = ctx.cfg.timepoints.get("exercise", {}) or {}
        return {
            "tte1": _time_to_seconds(ex.get("TTE1")),
            "tte2": _time_to_seconds(ex.get("TTE2")),
            "maintenance": float(ex.get("TTE_maintenance_rate") or 0.0),
            "apply": ctx.apply,
        }

    def render(self, parent: QWidget, data: dict) -> QWidget:
        root = QWidget(parent)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(SPACE.sm)

        form = QFormLayout()
        form.setHorizontalSpacing(SPACE.md)
        form.setVerticalSpacing(SPACE.xs)

        tte1_spin = QSpinBox()
        tte1_spin.setRange(0, 3600)
        tte1_spin.setSuffix(" sec")
        tte1_spin.setValue(int(data.get("tte1", 0)))

        tte2_spin = QSpinBox()
        tte2_spin.setRange(0, 3600)
        tte2_spin.setSuffix(" sec")
        tte2_spin.setValue(int(data.get("tte2", 0)))

        maint_spin = QDoubleSpinBox()
        maint_spin.setRange(0.0, 200.0)
        maint_spin.setDecimals(2)
        maint_spin.setSingleStep(0.1)
        maint_spin.setSuffix(" %")
        maint_spin.setValue(float(data.get("maintenance", 0.0)))

        form.addRow("TTE1 (Ex1):", tte1_spin)
        form.addRow("TTE2 (Ex2):", tte2_spin)
        form.addRow("Maintenance:", maint_spin)
        v.addLayout(form)

        # 품질 라벨 (maintenance 70% 임계)
        quality = QLabel("")
        quality.setWordWrap(True)
        quality.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(quality)

        def _update_quality(val: float):
            if val <= 0.0:
                quality.setText("")
                return
            if val < 70.0:
                quality.setText(
                    f"<span style='color:{COLOR.error}; font-weight:600;'>"
                    f"⚠ Maintenance {val:.1f}% &lt; 70% — 프로토콜 미준수 가능</span>"
                )
            else:
                quality.setText(
                    f"<span style='color:{COLOR.success};'>"
                    f"✓ Maintenance {val:.1f}% — OK</span>"
                )

        maint_spin.valueChanged.connect(_update_quality)
        _update_quality(maint_spin.value())

        # Apply
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        apply_btn = QPushButton("▶ Apply")
        apply_btn.setObjectName("primary")

        def _on_apply():
            payload = {
                "TTE1": _seconds_to_time(tte1_spin.value()),
                "TTE2": _seconds_to_time(tte2_spin.value()),
                "TTE_maintenance_rate": float(maint_spin.value()),
            }
            cb = data.get("apply")
            if callable(cb):
                cb(ACTION_TTE, payload)

        apply_btn.clicked.connect(_on_apply)
        btn_row.addWidget(apply_btn)
        v.addLayout(btn_row)
        v.addStretch()
        root.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return root
