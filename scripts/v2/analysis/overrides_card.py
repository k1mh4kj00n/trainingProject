"""OverridesCard — Baseline / Min / Peak 사용자 override + Auto detect.

v1 의 ParameterPanel 의 Min/Peak 그룹 + Auto detect 버튼을 카드 하나로.
"""

from __future__ import annotations

import datetime as dt
import math

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ..cards import (
    ACTION_AUTO_DETECT,
    ACTION_OVERRIDES,
    AnalysisCard,
    AnalysisContext,
    CardMeta,
    register,
)
from ..theme.tokens import COLOR, FONT, SPACE


def _qtime_to_t(q: QTime) -> dt.time:
    return dt.time(q.hour(), q.minute(), q.second())


def _t_to_qtime(t):
    if t is None:
        return QTime(0, 0, 0)
    if hasattr(t, "hour"):
        return QTime(int(t.hour), int(t.minute), int(getattr(t, "second", 0) or 0))
    return QTime(0, 0, 0)


@register
class OverridesCard:
    meta = CardMeta(
        id="overrides",
        name="Baseline · Min · Peak 사용자 override",
        category="NIRS",
        icon="🔒",
        description="기저값 잠금, Min/Peak 시각 직접 지정 + Auto detect (Gradient Descent)",
        default_size=(5, 3),
    )

    def compute(self, ctx: AnalysisContext) -> dict:
        ov = ctx.overrides or {}
        # 분석 결과 (Min/Peak time + value) 가져오기 — 표시용
        result_min_t = None
        result_peak_t = None
        result_baseline = None
        result_min_v = None
        result_peak_v = None
        if ctx.is_ready:
            try:
                from nirs_vot.metrics import compute_metrics
                r = compute_metrics(
                    ctx.smoothed, ctx.anchor, ctx.condition, ctx.timepoint,
                    override_baseline=ov.get("baseline"),
                    override_min_time=ov.get("min_time"),
                    override_peak_time=ov.get("peak_time"),
                )
                result_baseline = float(r.baseline_smo2)
                result_min_t = getattr(r, "min_time", None)
                result_peak_t = getattr(r, "peak_time", None)
                result_min_v = float(r.min_smo2)
                result_peak_v = float(r.peak_smo2)
            except Exception:  # noqa: BLE001
                pass

        return {
            "baseline_locked": "baseline" in ov,
            "baseline_value": ov.get("baseline", result_baseline),
            "min_time": ov.get("min_time", result_min_t),
            "peak_time": ov.get("peak_time", result_peak_t),
            "min_value": result_min_v,
            "peak_value": result_peak_v,
            "ready": ctx.is_ready,
            "apply": ctx.apply,
        }

    def render(self, parent: QWidget, data: dict) -> QWidget:
        root = QWidget(parent)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(SPACE.sm)

        grid = QGridLayout()
        grid.setHorizontalSpacing(SPACE.md)
        grid.setVerticalSpacing(SPACE.xs)

        # Baseline lock + value
        lock_chk = QCheckBox("잠금")
        lock_chk.setChecked(bool(data.get("baseline_locked")))
        baseline_spin = QDoubleSpinBox()
        baseline_spin.setRange(0.0, 100.0)
        baseline_spin.setDecimals(2)
        baseline_spin.setSingleStep(0.1)
        baseline_spin.setSuffix(" %")
        bv = data.get("baseline_value")
        if bv is not None and not (isinstance(bv, float) and math.isnan(bv)):
            baseline_spin.setValue(float(bv))

        grid.addWidget(QLabel("<b>Baseline</b>"), 0, 0)
        grid.addWidget(baseline_spin, 0, 1)
        grid.addWidget(lock_chk, 0, 2)

        # Min time
        min_time_edit = QTimeEdit()
        min_time_edit.setDisplayFormat("HH:mm:ss")
        min_time_edit.setTime(_t_to_qtime(data.get("min_time")))
        min_v = data.get("min_value")
        min_v_lbl = QLabel(f"{min_v:.2f} %" if isinstance(min_v, (int, float)) and not math.isnan(min_v) else "—")
        min_v_lbl.setStyleSheet(f"color: {COLOR.error}; font-weight: 600;")

        grid.addWidget(QLabel("<b>Min</b>"), 1, 0)
        grid.addWidget(min_time_edit, 1, 1)
        grid.addWidget(min_v_lbl, 1, 2)

        # Peak time
        peak_time_edit = QTimeEdit()
        peak_time_edit.setDisplayFormat("HH:mm:ss")
        peak_time_edit.setTime(_t_to_qtime(data.get("peak_time")))
        peak_v = data.get("peak_value")
        peak_v_lbl = QLabel(f"{peak_v:.2f} %" if isinstance(peak_v, (int, float)) and not math.isnan(peak_v) else "—")
        peak_v_lbl.setStyleSheet(f"color: {COLOR.success}; font-weight: 600;")

        grid.addWidget(QLabel("<b>Peak</b>"), 2, 0)
        grid.addWidget(peak_time_edit, 2, 1)
        grid.addWidget(peak_v_lbl, 2, 2)

        v.addLayout(grid)

        # 안내
        if not data.get("ready"):
            hint = QLabel("데이터 로드 후 사용 가능")
            hint.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")
            v.addWidget(hint)

        # Auto detect + Apply
        btn_row = QHBoxLayout()
        auto_btn = QPushButton("▶ Auto detect (GD)")
        auto_btn.setToolTip("Gradient Descent + SGD + DE 로 Min/Peak 정밀 검출")
        auto_btn.setEnabled(bool(data.get("ready")))

        def _on_auto():
            cb = data.get("apply")
            if callable(cb):
                cb(ACTION_AUTO_DETECT, None)

        auto_btn.clicked.connect(_on_auto)
        btn_row.addWidget(auto_btn)
        btn_row.addStretch()

        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("primary")
        apply_btn.setEnabled(bool(data.get("ready")))

        def _on_apply():
            payload = {}
            if lock_chk.isChecked():
                payload["baseline"] = float(baseline_spin.value())
            mt = _qtime_to_t(min_time_edit.time())
            if mt != dt.time(0, 0, 0):
                payload["min_time"] = mt
            pt = _qtime_to_t(peak_time_edit.time())
            if pt != dt.time(0, 0, 0):
                payload["peak_time"] = pt
            cb = data.get("apply")
            if callable(cb):
                cb(ACTION_OVERRIDES, payload)

        apply_btn.clicked.connect(_on_apply)
        btn_row.addWidget(apply_btn)

        v.addLayout(btn_row)
        v.addStretch()
        root.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return root
