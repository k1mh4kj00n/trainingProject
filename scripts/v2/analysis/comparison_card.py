"""ComparisonCard — 모든 로드된 condition × 같은 timepoint 의 핵심 metric 비교 표."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..cards import AnalysisCard, AnalysisContext, CardMeta, register
from ..theme.tokens import COLOR, FONT, SPACE


_METRICS = [
    ("Baseline", "baseline_smo2", "Calf_SmO2_Base", "%"),
    ("Min",      "min_smo2",      "Calf_SmO2_Min",  "%"),
    ("Peak",     "peak_smo2",     "Calf_SmO2_Peak", "%"),
    ("Slope1",   "slope1_30_150", "VOT_Slope1_30_150", "%/s"),
    ("Slope2",   "slope2_0_10",   "VOT_Slope2_0_10",   "%/s"),
    ("T50",      "t50_sec",       "VOT_T50",     "s"),
    ("AUC",      "auc_3min",      "AUC_3min",    "·min"),
]


@register
class ComparisonCard:
    meta = CardMeta(
        id="comparison",
        name="Multi-condition comparison",
        category="Compare",
        icon="⊞",
        description="현재 timepoint 기준, 모든 condition 의 12 metrics 표",
        default_size=(12, 4),
        min_size=(6, 3),
    )

    def compute(self, ctx: AnalysisContext) -> dict:
        if not ctx.timepoint:
            return {"rows": [], "conditions": []}

        try:
            from nirs_vot.metrics import compute_metrics
            from nirs_vot.anchors import anchors_from_session_config
        except ImportError:
            return {"rows": [], "conditions": []}

        conditions = []
        per_cond_results = {}
        for cond, lf in ctx.all_loaded.items():
            cfg = getattr(lf, "config", None)
            if cfg is None:
                continue
            anchor_map = anchors_from_session_config(cfg)
            anchor = anchor_map.get(ctx.timepoint)
            if anchor is None:
                continue
            try:
                r = compute_metrics(lf.smoothed, anchor, cond, ctx.timepoint)
            except Exception:  # noqa: BLE001
                continue
            conditions.append(cond)
            per_cond_results[cond] = r

        rows = []
        for label, attr, gt_col, unit in _METRICS:
            row = {"label": label, "unit": unit, "values": {}}
            for cond in conditions:
                r = per_cond_results[cond]
                v = getattr(r, attr, None)
                row["values"][cond] = float(v) if v is not None else None
            rows.append(row)
        return {"rows": rows, "conditions": conditions}

    def render(self, parent: QWidget, data: dict) -> QWidget:
        root = QWidget(parent)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        conds = data.get("conditions", [])
        if not conds:
            from PySide6.QtWidgets import QLabel
            ph = QLabel("로드된 condition 이 없거나 timepoint 미지정")
            ph.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")
            ph.setAlignment(Qt.AlignCenter)
            lay.addWidget(ph)
            return root

        n_cols = 1 + len(conds)
        rows = data["rows"]
        tbl = QTableWidget(len(rows), n_cols, root)
        tbl.setHorizontalHeaderLabels(["Metric"] + conds)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.setShowGrid(False)
        h = tbl.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for c in range(1, n_cols):
            h.setSectionResizeMode(c, QHeaderView.Stretch)

        # 카드 안의 표는 자체 스타일 (전역 QSS 와 별도)
        tbl.setStyleSheet(f"""
            QTableWidget {{
                background: {COLOR.bg_1};
                color: {COLOR.text_0};
                border: none;
                font-size: {FONT.body}px;
                gridline-color: {COLOR.border};
            }}
            QHeaderView::section {{
                background: {COLOR.bg_1};
                color: {COLOR.text_2};
                border: none;
                border-bottom: 1px solid {COLOR.border};
                font-weight: {FONT.w_semibold};
                font-size: {FONT.caption}px;
                padding: 6px 8px;
            }}
            QTableWidget::item:selected {{
                background: {COLOR.bg_3};
                color: {COLOR.text_0};
            }}
        """)

        for r, row in enumerate(rows):
            label_item = QTableWidgetItem(f"{row['label']}  ({row['unit']})")
            label_item.setForeground(_qcolor(COLOR.text_2))
            tbl.setItem(r, 0, label_item)
            for c, cond in enumerate(conds, start=1):
                v = row["values"].get(cond)
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    txt = "—"
                else:
                    txt = f"{v:.2f}"
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tbl.setItem(r, c, item)

        tbl.resizeRowsToContents()
        tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(tbl)
        return root


def _qcolor(hex_str: str):
    from PySide6.QtGui import QColor

    return QColor(hex_str)
