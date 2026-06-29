"""KpiCard 본문 — 큰 값 + 비교 + 미니 sparkline.

카드 chrome (CardFrame) 이 헤더를 그리고, 이 위젯이 본문을 그린다.
Apple Health / Vercel / intervals.icu 패턴.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..theme.tokens import COLOR, FONT, SPACE


class _Sparkline(QWidget):
    """매우 작은 한 줄 차트 — 최근 N 값의 추세 표시."""

    def __init__(self, values: list[float], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._values: list[float] = [float(v) for v in (values or [])
                                     if v is not None and not (isinstance(v, float) and math.isnan(v))]
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(80, 24)

    def paintEvent(self, _evt) -> None:  # noqa: N802
        if not self._values or len(self._values) < 2:
            return
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            w = self.width()
            h = self.height()
            mn, mx = min(self._values), max(self._values)
            rng = mx - mn or 1.0
            n = len(self._values)
            pen = QPen(QColor(COLOR.accent))
            pen.setWidth(2)
            p.setPen(pen)
            prev = None
            for i, v in enumerate(self._values):
                x = int(i * (w - 2) / (n - 1)) + 1
                y = int(h - 2 - (v - mn) / rng * (h - 4)) - 1
                if prev is not None:
                    p.drawLine(prev[0], prev[1], x, y)
                prev = (x, y)
        finally:
            p.end()


class KpiCard(QWidget):
    """KPI 본문: 큰 값 + (옵션) 비교/단위 캡션 + (옵션) sparkline.

    인자:
        value: '61.2 %' 처럼 포맷된 문자열 (또는 float)
        caption: 'GT 63.1 %  Δ −1.9' 같은 보조 정보
        delta: (+1.2, "%") 또는 (-2.4, "%") — 색상 자동
        spark: 최근 값들의 list (시계열 추세)
        value_color: 값의 색 override (None 이면 text_0)
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        value: str | float = "—",
        caption: str = "",
        delta: tuple[float, str] | None = None,
        spark: Iterable[float] | None = None,
        value_color: str | None = None,
    ) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SPACE.xs)

        # 값
        self._value_label = QLabel(self._fmt_value(value))
        self._value_label.setObjectName("kpiValue")
        if value_color:
            self._value_label.setStyleSheet(
                f"color: {value_color}; font-size: {FONT.kpi_value}px; "
                f"font-weight: {FONT.w_semibold}; background: transparent;"
            )
        lay.addWidget(self._value_label)

        # 캡션 + 델타 (한 줄)
        cap_row = QHBoxLayout()
        cap_row.setContentsMargins(0, 0, 0, 0)
        cap_row.setSpacing(SPACE.sm)
        if caption:
            cap_lbl = QLabel(caption)
            cap_lbl.setObjectName("kpiCaption")
            cap_row.addWidget(cap_lbl)
        if delta is not None:
            d_val, d_unit = delta
            sign = "+" if d_val >= 0 else "−"
            d_lbl = QLabel(f"{sign}{abs(d_val):.2f}{d_unit}")
            d_lbl.setObjectName("kpiDeltaPos" if d_val >= 0 else "kpiDeltaNeg")
            cap_row.addWidget(d_lbl)
        cap_row.addStretch()
        if cap_row.count() > 1 or (cap_row.count() == 1 and caption):
            lay.addLayout(cap_row)

        # 스파크라인
        if spark is not None:
            spark_list = list(spark)
            if len(spark_list) >= 2:
                lay.addSpacing(SPACE.xs)
                lay.addWidget(_Sparkline(spark_list, self))

        lay.addStretch()

    @staticmethod
    def _fmt_value(v) -> str:
        if v is None:
            return "—"
        if isinstance(v, float):
            if math.isnan(v) or math.isinf(v):
                return "—"
            return f"{v:.2f}"
        return str(v)
