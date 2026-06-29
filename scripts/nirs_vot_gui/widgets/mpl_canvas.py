"""matplotlib FigureCanvas Qt 래퍼.

옵션:
    show_toolbar: NavigationToolbar 표시 여부 (기본 False — Kubios 화면처럼 깔끔)
    figsize:      Figure 초기 inch 크기. **표시 크기 강제값 아님** —
                  실제 화면 크기는 부모 위젯(QSplitter 등)에 따라 늘어난다.
                  하지만 sizeHint()가 figsize × dpi 라서 너무 크면 위젯 minimum이 커져
                  splitter가 더 못 줄이게 되니, 화면용은 작게 잡는다.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

try:
    from ..sizing import mpl_dpi  # type: ignore
except ImportError:
    def mpl_dpi() -> float:  # fallback
        return 100.0


class _AdaptiveCanvas(FigureCanvasQTAgg):
    """sizeHint를 작게 잡아 부모 레이아웃이 자유롭게 늘이고 줄일 수 있도록.

    matplotlib 기본 FigureCanvasQTAgg.sizeHint()는 figsize×dpi 그대로 반환해
    QSplitter/Layout이 위젯을 줄이지 못하는 경우가 생긴다. minimumSizeHint를
    아주 작게 두고, 자체 sizeHint도 합리적인 작은 값으로 제한한다.
    """

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(200, 120)

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(80, 60)


class MplCanvas(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        figsize=(6, 3.5),
        dpi: float | None = None,
        show_toolbar: bool = False,
    ) -> None:
        super().__init__(parent)
        if dpi is None:
            dpi = mpl_dpi()
        self.figure = Figure(figsize=figsize, dpi=dpi, layout="constrained")
        self.canvas = _AdaptiveCanvas(self.figure)
        # 캔버스가 부모를 따라 늘어나도록
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if show_toolbar:
            self.toolbar = NavigationToolbar2QT(self.canvas, self)
            layout.addWidget(self.toolbar)
        else:
            self.toolbar = None

        layout.addWidget(self.canvas, stretch=1)

        # 위젯 자체도 확장 정책
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(80, 60)

    def clear(self) -> None:
        self.figure.clear()
        self.canvas.draw_idle()

    @property
    def fig(self) -> Figure:
        return self.figure
