"""외부 HRV 결과 카드 — 설정 xlsx `Coded Data` 의 HRV_xxx 값을 표시.

(α) 가정: _Calf 데이터에는 RR/ECG 가 없어 HRV 자체 계산 불가능. 대신 설정 파일의
`HRV_Baseline` / `HRV_Post` 행에 외부에서 계산된 5개 지표가 들어있다:

    HRV_SDNN, HRV_RMSSD, HRV_LF, HRV_HF, HRV_LF/HF

이 위젯은 한 condition 의 두 timepoint (Baseline · Post) 를 나란히 카드로 표시한다.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


HRV_METRICS = [
    ("HRV_SDNN",   "SDNN",      "ms"),
    ("HRV_RMSSD",  "RMSSD",     "ms"),
    ("HRV_LF",     "LF",        "n.u."),
    ("HRV_HF",     "HF",        "n.u."),
    ("HRV_LF/HF",  "LF / HF",   "ratio"),
]

TIMEPOINT_LABELS = {
    "Baseline": "Baseline (휴식 전)",
    "Post":     "Post (회복 후)",
}


def _fmt(v) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f != f:  # NaN
        return "—"
    return f"{f:,.3f}".rstrip("0").rstrip(".") or "0"


class _MetricCell(QFrame):
    """한 지표 셀 (label + 큰 숫자 + 단위)."""

    def __init__(self, label: str, unit: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setStyleSheet(
            "QFrame { background-color: #FAFBFC; border: 1px solid #E1E4E8; "
            "border-radius: 4px; padding: 6px; }"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        self.label = QLabel(label)
        f = QFont(); f.setPointSize(9)
        self.label.setFont(f)
        self.label.setStyleSheet("color: #586069; border: none;")

        self.value = QLabel("—")
        big = QFont(); big.setPointSize(18); big.setBold(True)
        self.value.setFont(big)
        self.value.setStyleSheet("color: #24292E; border: none;")
        self.value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.unit = QLabel(unit)
        f2 = QFont(); f2.setPointSize(8)
        self.unit.setFont(f2)
        self.unit.setStyleSheet("color: #6A737D; border: none;")

        lay.addWidget(self.label)
        lay.addWidget(self.value)
        lay.addWidget(self.unit)

    def set_value(self, v) -> None:
        self.value.setText(_fmt(v))


class ExternalHrvCard(QWidget):
    """한 condition 의 Baseline/Post HRV 외부 결과를 두 컬럼 카드로."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cells: dict[str, dict[str, _MetricCell]] = {  # tp → metric_key → cell
            "Baseline": {},
            "Post": {},
        }

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        title = QLabel("HRV results  ·  (외부 분석 결과)")
        f = QFont(); f.setPointSize(11); f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        self.context_label = QLabel("— condition 을 선택하세요 —")
        self.context_label.setStyleSheet("color: #6A737D;")
        self.context_label.setWordWrap(True)
        root.addWidget(self.context_label)

        # 두 컬럼 (Baseline / Post)
        cols = QHBoxLayout()
        cols.setSpacing(8)
        for tp in ("Baseline", "Post"):
            col = QFrame()
            col.setStyleSheet(
                "QFrame { border: none; }"
            )
            col_lay = QVBoxLayout(col)
            col_lay.setContentsMargins(0, 0, 0, 0)
            col_lay.setSpacing(6)

            tp_label = QLabel(TIMEPOINT_LABELS[tp])
            tpf = QFont(); tpf.setBold(True); tpf.setPointSize(10)
            tp_label.setFont(tpf)
            tp_label.setStyleSheet("color: #0366D6;")
            col_lay.addWidget(tp_label)

            for key, name, unit in HRV_METRICS:
                cell = _MetricCell(name, unit)
                col_lay.addWidget(cell)
                self._cells[tp][key] = cell
            col_lay.addStretch()

            cols.addWidget(col, stretch=1)

        root.addLayout(cols, stretch=1)

        note = QLabel(
            "ℹ HRV 분석 엔진이 구현되기 전까지는 값 표시를 보류합니다. "
            "현재는 모든 셀이 — 로 표시되며, 자체 분석 모듈이 추가되면 자동으로 값이 채워집니다."
        )
        note.setStyleSheet("color: #6A737D; font-style: italic; padding-top: 6px;")
        note.setWordWrap(True)
        root.addWidget(note)

    # ─────────────────────────────────────────────
    def show_for(self, condition: str, session_config) -> None:
        """HRV 분석 엔진 구현 전까지는 모든 값을 ``—`` 로 보류 표시.

        설정 xlsx 의 ``Coded Data`` 시트에 외부 ground truth 가 들어있더라도, 자체 분석 결과가
        없는 상태에서 외부값만 표시하면 사용자가 우리가 분석한 결과로 오해할 수 있어 표시를
        보류한다. UI 레이아웃·셀 구조는 그대로 유지 — 분석 엔진이 붙으면 즉시 채울 수 있음.
        """
        self.context_label.setText(
            f"Condition: <b>{condition}</b>  ·  HRV 분석 엔진 미구현 — 값 표시 보류"
        )
        for tp in ("Baseline", "Post"):
            for key, _, _ in HRV_METRICS:
                self._cells[tp][key].set_value(None)

    def clear(self) -> None:
        self.context_label.setText("— condition 을 선택하세요 —")
        for tp in ("Baseline", "Post"):
            for key, _, _ in HRV_METRICS:
                self._cells[tp][key].set_value(None)
