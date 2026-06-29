"""QSS 생성 — Light 의료/연구 톤 기본.

전역: ``apply_global_style(app)``
"""

from __future__ import annotations

from .tokens import COLOR, FONT, RADIUS, SPACE


def global_qss() -> str:
    """앱 전역 QSS — QApplication.setStyleSheet 에 적용."""
    c = COLOR
    return f"""
QWidget {{
    background-color: {c.bg_0};
    color: {c.text_0};
    font-family: {FONT.family_ui};
    font-size: {FONT.body}px;
}}

/* ─ 카드 — Light 톤은 흰색 + 미세 1px 보더 ─ */
QFrame#card {{
    background-color: {c.bg_1};
    border: 1px solid {c.border};
    border-radius: {RADIUS.lg}px;
}}
QFrame#card:hover {{
    border-color: {c.border_strong};
}}

QLabel#cardTitle {{
    color: {c.text_1};
    font-size: {FONT.title}px;
    font-weight: {FONT.w_semibold};
    background: transparent;
}}
QLabel#kpiValue {{
    color: {c.text_0};
    font-size: {FONT.kpi_value}px;
    font-weight: {FONT.w_semibold};
    background: transparent;
}}
QLabel#kpiCaption {{
    color: {c.text_2};
    font-size: {FONT.caption}px;
    background: transparent;
}}
QLabel#kpiDeltaPos {{
    color: {c.success};
    font-size: {FONT.caption}px;
    font-weight: {FONT.w_medium};
    background: transparent;
}}
QLabel#kpiDeltaNeg {{
    color: {c.error};
    font-size: {FONT.caption}px;
    font-weight: {FONT.w_medium};
    background: transparent;
}}

/* ─ 좌측 nav (icon-bar) ─ */
QFrame#iconBar {{
    background-color: {c.bg_1};
    border-right: 1px solid {c.border};
}}
QPushButton#navButton {{
    background-color: transparent;
    border: none;
    color: {c.text_2};
    padding: 10px;
    font-size: 18px;
}}
QPushButton#navButton:hover {{
    background-color: {c.bg_2};
    color: {c.text_0};
    border-radius: {RADIUS.md}px;
}}
QPushButton#navButton:checked {{
    background-color: {c.bg_3};
    color: {c.accent};
    border-radius: {RADIUS.md}px;
}}

/* ─ 상단 context bar ─ */
QFrame#contextBar {{
    background-color: {c.bg_1};
    border-bottom: 1px solid {c.border};
}}

/* ─ Buttons (의료톤: 외곽선 강조 + 호버시 색 변화) ─ */
QPushButton {{
    background-color: {c.bg_1};
    color: {c.text_0};
    border: 1px solid {c.border_strong};
    border-radius: {RADIUS.md}px;
    padding: 7px 14px;
    font-weight: {FONT.w_medium};
}}
QPushButton:hover {{
    background-color: {c.bg_2};
    border-color: {c.accent};
    color: {c.accent};
}}
QPushButton:pressed {{
    background-color: {c.bg_3};
}}

/* Primary 버튼: 의료 블루 채움 */
QPushButton#primary {{
    background-color: {c.accent};
    color: white;
    border: 1px solid {c.accent};
    font-weight: {FONT.w_semibold};
}}
QPushButton#primary:hover {{
    background-color: {c.accent};
    border-color: {c.accent};
    color: white;
}}

/* ─ ComboBox ─ */
QComboBox {{
    background-color: {c.bg_1};
    color: {c.text_0};
    border: 1px solid {c.border_strong};
    border-radius: {RADIUS.md}px;
    padding: 5px 10px;
    min-height: 24px;
}}
QComboBox:hover {{
    border-color: {c.accent};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {c.bg_1};
    color: {c.text_0};
    border: 1px solid {c.border};
    selection-background-color: {c.bg_3};
    selection-color: {c.accent};
    padding: 4px;
}}

/* ─ ScrollArea ─ */
QScrollArea {{
    background-color: {c.bg_0};
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c.border_strong};
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c.text_2};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c.border_strong};
    border-radius: 4px;
    min-width: 28px;
}}

/* ─ Menu ─ */
QMenu {{
    background-color: {c.bg_1};
    color: {c.text_0};
    border: 1px solid {c.border};
    padding: 6px;
    border-radius: {RADIUS.md}px;
}}
QMenu::item {{
    padding: 6px 14px;
    border-radius: {RADIUS.sm}px;
}}
QMenu::item:selected {{
    background-color: {c.bg_2};
    color: {c.accent};
}}
QMenu::separator {{
    height: 1px;
    background: {c.border};
    margin: 4px 0;
}}

/* ─ ToolTip ─ */
QToolTip {{
    background-color: {c.text_0};
    color: {c.bg_1};
    border: none;
    padding: 6px 10px;
    border-radius: {RADIUS.sm}px;
    font-size: {FONT.caption}px;
}}
"""


def apply_global_style(app) -> None:
    """QApplication 에 전역 QSS 적용. 테마 변경 시 다시 호출."""
    app.setStyleSheet(global_qss())
