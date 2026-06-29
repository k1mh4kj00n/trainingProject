"""색상·폰트·QSS 스타일시트 (Kubios 라이트 테마 기반).

분석·시각화 계층과 분리해 한 곳에서 관리한다.
"""

from __future__ import annotations


class Color:
    # 전역 배경
    WINDOW_BG     = "#FFFFFF"
    PANEL_BG      = "#F4F4F4"
    BORDER        = "#CCCCCC"
    TABLE_ALT_BG  = "#E8F4FF"
    HEADER_BG     = "#E8E8E8"

    # 데이터 라인
    SMO2_SMOOTH   = "#111111"
    SMO2_RAW      = "#9E9E9E"
    BASELINE      = "#424242"

    # Ribbon
    OXY_DEFICIT   = "#D32F2F"
    HYPEREMIA     = "#2E7D32"

    # 마커
    MIN_MARKER    = "#1F77B4"
    PEAK_MARKER   = "#D32F2F"

    # 강조/포인트
    ACCENT        = "#2E7DCA"
    ACCENT_DARK   = "#1B5FA3"
    WARNING       = "#FFA000"
    OK            = "#2E7D32"

    # 텍스트
    TEXT          = "#1A1A1A"
    TEXT_MUTED    = "#666666"


QSS = f"""
QMainWindow, QWidget {{
    background-color: {Color.WINDOW_BG};
    color: {Color.TEXT};
}}
QMenuBar {{
    background-color: {Color.PANEL_BG};
    border-bottom: 1px solid {Color.BORDER};
    padding: 2px;
}}
QMenuBar::item:selected {{
    background-color: {Color.ACCENT};
    color: white;
}}
QToolBar {{
    background-color: {Color.PANEL_BG};
    border: none;
    border-bottom: 1px solid {Color.BORDER};
    padding: 2px;
    spacing: 4px;
}}
QStatusBar {{
    background-color: {Color.PANEL_BG};
    border-top: 1px solid {Color.BORDER};
}}
QDockWidget {{
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}
QDockWidget::title {{
    background-color: {Color.HEADER_BG};
    padding: 4px 6px;
    border-bottom: 1px solid {Color.BORDER};
    font-weight: bold;
}}
QTabWidget::pane {{
    border: 1px solid {Color.BORDER};
    background-color: {Color.WINDOW_BG};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {Color.PANEL_BG};
    color: {Color.TEXT};
    padding: 6px 16px;
    border: 1px solid {Color.BORDER};
    border-bottom: none;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {Color.ACCENT};
    color: white;
    font-weight: bold;
}}
QTabBar::tab:!selected:hover {{
    background-color: {Color.TABLE_ALT_BG};
}}
/* ─── 메인 페이지 탭 (NIRS / HRV) — 분석법 구별 강조 ─── */
QTabWidget#mainPages > QTabBar::tab {{
    font-size: 12pt;
    font-weight: 500;
    padding: 10px 28px;
    min-width: 140px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    background-color: {Color.PANEL_BG};
    color: {Color.TEXT_MUTED};
}}
QTabWidget#mainPages > QTabBar::tab:selected {{
    background-color: {Color.ACCENT};
    color: white;
    font-weight: bold;
    border: 1px solid {Color.ACCENT_DARK};
    border-bottom: 3px solid {Color.ACCENT_DARK};
}}
QTabWidget#mainPages > QTabBar::tab:!selected:hover {{
    background-color: {Color.TABLE_ALT_BG};
    color: {Color.ACCENT};
}}
QTabWidget#mainPages::pane {{
    border: 1px solid {Color.BORDER};
    border-top: 2px solid {Color.ACCENT_DARK};
    background-color: {Color.WINDOW_BG};
    top: 0px;
}}
QTreeView {{
    background-color: {Color.WINDOW_BG};
    border: 1px solid {Color.BORDER};
    alternate-background-color: {Color.TABLE_ALT_BG};
    padding: 4px;
}}
QTreeView::item:selected {{
    background-color: {Color.ACCENT};
    color: white;
}}
QTableWidget {{
    background-color: {Color.WINDOW_BG};
    alternate-background-color: {Color.TABLE_ALT_BG};
    gridline-color: {Color.BORDER};
    border: 1px solid {Color.BORDER};
}}
QTableWidget QHeaderView::section {{
    background-color: {Color.HEADER_BG};
    padding: 4px 8px;
    border: none;
    border-right: 1px solid {Color.BORDER};
    border-bottom: 1px solid {Color.BORDER};
    font-weight: bold;
}}
QPushButton {{
    background-color: {Color.PANEL_BG};
    border: 1px solid {Color.BORDER};
    padding: 4px 14px;
    border-radius: 3px;
}}
QPushButton:hover {{
    background-color: {Color.TABLE_ALT_BG};
}}
QPushButton:pressed, QPushButton:checked {{
    background-color: {Color.ACCENT};
    color: white;
}}
QPushButton:disabled {{
    color: #AAAAAA;
    background-color: #F0F0F0;
}}
QComboBox {{
    border: 1px solid {Color.BORDER};
    padding: 3px 8px;
    background-color: white;
    min-width: 90px;
}}
QLabel[role="title"] {{
    font-size: 13pt;
    font-weight: bold;
    color: {Color.TEXT};
}}
"""
