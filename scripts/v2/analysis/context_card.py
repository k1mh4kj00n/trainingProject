"""ContextCard — 현재 subject·condition·timepoint 메타 표시.

분석 안 함. ctx.subject_info 등 그대로 렌더.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..cards import AnalysisCard, AnalysisContext, CardMeta, register
from ..theme.tokens import COLOR, FONT, SPACE


@register
class ContextCard:
    meta = CardMeta(
        id="context",
        name="Subject · Session",
        category="NIRS",
        icon="◐",
        description="현재 분석 대상의 메타 정보 (피험자·condition·timepoint)",
        default_size=(4, 2),
    )

    def compute(self, ctx: AnalysisContext) -> dict:
        info = ctx.subject_info or {}
        return {
            "name": info.get("Name", "—"),
            "id": info.get("ID(Protocol)", "—"),
            "age": info.get("Age", "—"),
            "gender": info.get("Gender", "—"),
            "weight": info.get("Weight(kg)", "—"),
            "height": info.get("Height(cm)", "—"),
            "wattmax": info.get("Wattmax", "—"),
            "vo2max": info.get("VO2max", "—"),
            "condition": ctx.condition or "—",
            "timepoint": ctx.timepoint or "—",
            "ready": ctx.is_ready,
        }

    def render(self, parent: QWidget, data: dict) -> QWidget:
        root = QWidget(parent)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SPACE.xs)

        # 이름 (크게)
        name_lbl = QLabel(data["name"])
        name_lbl.setStyleSheet(
            f"color: {COLOR.text_0}; font-size: {FONT.kpi_value}px; "
            f"font-weight: {FONT.w_semibold};"
        )
        lay.addWidget(name_lbl)

        # ID · 나이 · 성별 · 신체
        sub = " · ".join([
            f"{data['id']}",
            f"{data['age']} {data['gender']}".strip(),
            f"{data['height']}cm / {data['weight']}kg",
        ])
        sub_lbl = QLabel(sub)
        sub_lbl.setStyleSheet(f"color: {COLOR.text_2}; font-size: {FONT.caption}px;")
        sub_lbl.setWordWrap(True)
        lay.addWidget(sub_lbl)

        # 운동 능력
        perf = f"Wattmax {data['wattmax']}W · VO2max {data['vo2max']}"
        perf_lbl = QLabel(perf)
        perf_lbl.setStyleSheet(f"color: {COLOR.text_1}; font-size: {FONT.caption}px;")
        lay.addWidget(perf_lbl)

        # 현재 분석 컨텍스트
        ctx_str = f"<b style='color:{COLOR.accent}'>{data['condition']}</b>  ·  {data['timepoint']}"
        ctx_lbl = QLabel(ctx_str)
        ctx_lbl.setTextFormat(Qt.TextFormat.RichText)
        ctx_lbl.setStyleSheet(f"color: {COLOR.text_0}; font-size: {FONT.body}px;")
        lay.addWidget(ctx_lbl)

        lay.addStretch()
        root.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return root
