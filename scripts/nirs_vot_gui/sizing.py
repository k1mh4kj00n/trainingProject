"""해상도·DPI 무관 사이징 헬퍼.

원칙:
    - 고정 px 대신 **폰트 라인 높이 배수**(폰트가 OS DPI 스케일링을 따르므로)
    - 절대 sizes 대신 **화면 가용 영역의 비율**
    - High-DPI 화면(125%, 150%, 200%)에서도 깨지지 않게

사용 예:
    from .sizing import lh, screen_size, scaled_size, dock_width
    self.setMinimumHeight(lh() * 16)   # 폰트 16줄 ≈ 적절한 시그널 영역 높이
    w, h = scaled_size(0.85)           # 화면의 85%
    self.dock.setMinimumWidth(dock_width("medium"))
"""

from __future__ import annotations

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication


# ──────────────────────────────────────────────
#  폰트 기준
# ──────────────────────────────────────────────
def lh(font=None) -> int:
    """현재 application 폰트의 라인 높이(px). DPI 스케일링이 자동 반영된다.

    일반적으로 14~20 px 사이. 9pt 폰트 100% DPI ≈ 15 px,
    150% DPI ≈ 22 px, 200% DPI ≈ 30 px.
    """
    app = QApplication.instance()
    if app is None:
        return 16
    return QFontMetrics(font or app.font()).height()


def char_w(font=None) -> int:
    """평균 문자 폭(px). 'M'의 폭으로 근사."""
    app = QApplication.instance()
    if app is None:
        return 8
    return QFontMetrics(font or app.font()).horizontalAdvance("M")


# ──────────────────────────────────────────────
#  화면 기준
# ──────────────────────────────────────────────
def screen_geometry():
    """현재 primary screen의 available geometry (작업표시줄 제외)."""
    app = QApplication.instance()
    if app is None:
        return None
    screen = app.primaryScreen()
    if screen is None:
        return None
    return screen.availableGeometry()


def screen_size(default=(1600, 900)) -> tuple[int, int]:
    g = screen_geometry()
    if g is None:
        return default
    return g.width(), g.height()


def scaled_size(ratio: float = 0.85, default=(1600, 900)) -> tuple[int, int]:
    """화면 가용 영역의 ratio 배 크기."""
    w, h = screen_size(default)
    return int(w * ratio), int(h * ratio)


def screen_dpi(default: float = 96.0) -> float:
    """primary screen의 logical DPI (보통 96, HiDPI에서 144/192 등)."""
    app = QApplication.instance()
    if app is None:
        return default
    s = app.primaryScreen()
    if s is None:
        return default
    return float(s.logicalDotsPerInch())


# ──────────────────────────────────────────────
#  도크/위젯 표준 크기
# ──────────────────────────────────────────────
_DOCK_WIDTH_RATIO = {
    "small":  0.14,   # ~220 px @ 1600
    "medium": 0.18,   # ~290 px
    "large":  0.22,
}


def dock_width(size: str = "medium") -> int:
    """좌/우 도크의 권장 minimum width (화면 폭 비례 + 폰트 보정)."""
    ratio = _DOCK_WIDTH_RATIO.get(size, 0.18)
    w, _ = screen_size()
    base = int(w * ratio)
    # 폰트가 큰 환경에서 텍스트 잘리지 않도록 char_w * 28 이상 보장
    return max(base, char_w() * 28)


# ──────────────────────────────────────────────
#  matplotlib Figure DPI
# ──────────────────────────────────────────────
def mpl_dpi() -> float:
    """matplotlib Figure에 쓸 DPI. 화면 logical DPI 기준 + 너무 크면 클램프."""
    d = screen_dpi()
    # matplotlib에서 너무 큰 dpi는 figure 텍스트를 과하게 키운다.
    # 96~120 사이로 클램프.
    return float(min(max(d, 96.0), 120.0))
