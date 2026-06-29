"""SlopeAucCard — Slope1 (desaturation) / Slope2 (resaturation) / T50 / AUC 한 묶음."""

from __future__ import annotations

import math

from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QWidget

from ..cards import AnalysisCard, AnalysisContext, CardMeta, register
from ..theme.tokens import COLOR, FONT, SPACE


@register
class SlopeAucCard:
    meta = CardMeta(
        id="slope_auc",
        name="Slope · T50 · AUC",
        category="NIRS",
        icon="∫",
        description="Slope1(30~150s desaturation) · Slope2(0~10s resaturation) · T50 · AUC 3min",
        default_size=(5, 2),
    )

    def compute(self, ctx: AnalysisContext) -> dict:
        if not ctx.is_ready:
            return {}
        try:
            from nirs_vot.metrics import compute_metrics
        except ImportError:
            return {}
        r = compute_metrics(
            ctx.smoothed, ctx.anchor, ctx.condition, ctx.timepoint,
            override_baseline=ctx.overrides.get("baseline"),
            override_min_time=ctx.overrides.get("min_time"),
            override_peak_time=ctx.overrides.get("peak_time"),
        )
        gt = ctx.vot_truth or {}

        def gt_f(k):
            v = gt.get(k)
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        return {
            "slope1": float(getattr(r, "slope1_30_150", float("nan"))),
            "slope2": float(getattr(r, "slope2_0_10", float("nan"))),
            "t50": float(getattr(r, "t50_sec", float("nan"))),
            "auc": float(getattr(r, "auc_3min", float("nan"))),
            "gt_slope1": gt_f("VOT_Slope1_30_150"),
            "gt_slope2": gt_f("VOT_Slope2_0_10"),
            "gt_t50": gt_f("VOT_T50"),
            "gt_auc": gt_f("AUC_3min"),
        }

    def render(self, parent: QWidget, data: dict) -> QWidget:
        root = QWidget(parent)
        lay = QGridLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(SPACE.lg)
        lay.setVerticalSpacing(SPACE.xs)

        def cell(name: str, ours: float | None, gt: float | None,
                 unit: str, col: int) -> None:
            n_lbl = QLabel(name)
            n_lbl.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")
            ours_str = "—" if ours is None or math.isnan(ours) else f"{ours:.2f}{unit}"
            v_lbl = QLabel(ours_str)
            v_lbl.setStyleSheet(
                f"color: {COLOR.text_0}; font-size: {FONT.kpi_value}px; "
                f"font-weight: {FONT.w_semibold};"
            )
            gt_lbl = QLabel(f"GT {gt:.2f}{unit}" if gt is not None else "GT 없음")
            gt_lbl.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")
            lay.addWidget(n_lbl, 0, col)
            lay.addWidget(v_lbl, 1, col)
            lay.addWidget(gt_lbl, 2, col)

        if data:
            cell("Slope1", data.get("slope1"), data.get("gt_slope1"), " %/s", 0)
            cell("Slope2", data.get("slope2"), data.get("gt_slope2"), " %/s", 1)
            cell("T50",    data.get("t50"),    data.get("gt_t50"),    " s",   2)
            cell("AUC",    data.get("auc"),    data.get("gt_auc"),    "·min", 3)
        else:
            ph = QLabel("데이터 로드 후 표시")
            ph.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")
            lay.addWidget(ph, 0, 0)

        root.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return root
