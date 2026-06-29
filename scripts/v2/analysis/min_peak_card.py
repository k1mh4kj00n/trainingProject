"""MinPeakCard — Min·Peak 값 + 그 사이 magnitude.

KpiCard 한 개로는 표현 부족 → 본문 위젯 직접 구성.
"""

from __future__ import annotations

import math

from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..cards import AnalysisCard, AnalysisContext, CardMeta, register
from ..theme.tokens import COLOR, FONT, SPACE


@register
class MinPeakCard:
    meta = CardMeta(
        id="min_peak",
        name="Min · Peak · Magnitude",
        category="NIRS",
        icon="↕",
        description="Occlusion 최저점, Reperfusion peak, 그 차이 (Magnitude)",
        default_size=(4, 2),
    )

    def compute(self, ctx: AnalysisContext) -> dict:
        if not ctx.is_ready:
            return {"min": None, "peak": None, "mag": None, "min_t": None, "peak_t": None}
        try:
            from nirs_vot.metrics import compute_metrics
        except ImportError:
            return {"min": None, "peak": None, "mag": None, "min_t": None, "peak_t": None}

        r = compute_metrics(
            ctx.smoothed, ctx.anchor, ctx.condition, ctx.timepoint,
            override_baseline=ctx.overrides.get("baseline"),
            override_min_time=ctx.overrides.get("min_time"),
            override_peak_time=ctx.overrides.get("peak_time"),
        )
        return {
            "min": float(r.min_smo2),
            "peak": float(r.peak_smo2),
            "mag": float(r.magnitude),
            "min_t": getattr(r, "min_time", None),
            "peak_t": getattr(r, "peak_time", None),
        }

    def render(self, parent: QWidget, data: dict) -> QWidget:
        root = QWidget(parent)
        lay = QGridLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(SPACE.lg)
        lay.setVerticalSpacing(SPACE.xs)

        def fmt(v):
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return "—"
            return f"{v:.2f} %"

        def fmt_t(t):
            if t is None:
                return ""
            try:
                return t.strftime("%H:%M:%S")
            except Exception:  # noqa: BLE001
                return ""

        # Min
        min_lbl_n = QLabel("Min")
        min_lbl_n.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")
        min_lbl_v = QLabel(fmt(data.get("min")))
        min_lbl_v.setStyleSheet(
            f"color: {COLOR.error}; font-size: {FONT.kpi_value}px; "
            f"font-weight: {FONT.w_semibold};"
        )
        min_lbl_t = QLabel(fmt_t(data.get("min_t")))
        min_lbl_t.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")

        # Peak
        peak_lbl_n = QLabel("Peak")
        peak_lbl_n.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")
        peak_lbl_v = QLabel(fmt(data.get("peak")))
        peak_lbl_v.setStyleSheet(
            f"color: {COLOR.success}; font-size: {FONT.kpi_value}px; "
            f"font-weight: {FONT.w_semibold};"
        )
        peak_lbl_t = QLabel(fmt_t(data.get("peak_t")))
        peak_lbl_t.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")

        # Magnitude
        mag_lbl_n = QLabel("Magnitude")
        mag_lbl_n.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")
        mag_lbl_v = QLabel(fmt(data.get("mag")))
        mag_lbl_v.setStyleSheet(
            f"color: {COLOR.text_0}; font-size: {FONT.kpi_value}px; "
            f"font-weight: {FONT.w_semibold};"
        )

        lay.addWidget(min_lbl_n, 0, 0)
        lay.addWidget(min_lbl_v, 1, 0)
        lay.addWidget(min_lbl_t, 2, 0)

        lay.addWidget(peak_lbl_n, 0, 1)
        lay.addWidget(peak_lbl_v, 1, 1)
        lay.addWidget(peak_lbl_t, 2, 1)

        lay.addWidget(mag_lbl_n, 0, 2)
        lay.addWidget(mag_lbl_v, 1, 2)
        lay.addWidget(QLabel(""), 2, 2)  # 시각 자리 매칭

        root.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return root
