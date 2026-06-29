"""BaselineSmO2Card — 기저 SmO2 % + GT 비교 + 다중 condition sparkline."""

from __future__ import annotations

import math

from PySide6.QtWidgets import QWidget

from ..cards import AnalysisCard, AnalysisContext, CardMeta, register
from ..widgets.kpi_card import KpiCard


@register
class BaselineSmO2Card:
    meta = CardMeta(
        id="baseline_smo2",
        name="Baseline SmO2",
        category="NIRS",
        icon="●",
        description="커프 팽창 직전 60초 평균 SmO2 (%) + Coded Data 의 GT 비교",
        default_size=(3, 2),
    )

    def compute(self, ctx: AnalysisContext) -> dict:
        if not ctx.is_ready:
            return {"value": None, "gt": None, "history": [], "delta": None}

        # v1 의 분석 엔진 그대로 호출
        try:
            from nirs_vot.metrics import compute_metrics
        except ImportError:
            return {"value": None, "gt": None, "history": [], "delta": None,
                    "error": "nirs_vot.metrics import 실패"}

        result = compute_metrics(
            ctx.smoothed, ctx.anchor, ctx.condition, ctx.timepoint,
            override_baseline=ctx.overrides.get("baseline"),
            override_min_time=ctx.overrides.get("min_time"),
            override_peak_time=ctx.overrides.get("peak_time"),
        )
        value = float(result.baseline_smo2)
        gt = ctx.vot_truth.get("Calf_SmO2_Base")
        gt_f = float(gt) if gt is not None else None
        delta = (value - gt_f, " %") if gt_f is not None else None

        # history — 비교용. 다른 condition 의 baseline 도 같이 보여주면 sparkline.
        history: list[float] = []
        for cond_name, lf in ctx.all_loaded.items():
            cfg = getattr(lf, "config", None)
            if cfg is None:
                continue
            base = cfg.vot_truth.get(ctx.timepoint, {}).get("Calf_SmO2_Base")
            if base is not None:
                try:
                    history.append(float(base))
                except (TypeError, ValueError):
                    pass

        return {"value": value, "gt": gt_f, "history": history, "delta": delta}

    def render(self, parent: QWidget, data: dict) -> QWidget:
        if data.get("value") is None:
            return KpiCard(parent, value="—", caption="데이터 로드 후 표시")
        value_str = f"{data['value']:.2f} %"
        caption = f"GT  {data['gt']:.2f} %" if data.get("gt") is not None else "GT 없음"
        return KpiCard(
            parent,
            value=value_str,
            caption=caption,
            delta=data.get("delta"),
            spark=data.get("history") or None,
        )
