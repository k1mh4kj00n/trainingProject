"""CardFrame — 표준 카드 chrome (헤더 + 메뉴 + 본문 슬롯).

각 분석 카드가 자기 본문 위젯만 만들면, CardFrame 이 통일된 외형으로 감싼다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..theme.tokens import COLOR, FONT, SPACE

if TYPE_CHECKING:
    from ..cards.protocol import CardMeta


class CardFrame(QFrame):
    """카드 외형 — 헤더(제목 + ⋮ 메뉴) + 본문(슬롯).

    Signals:
        request_remove() — 헤더 ⋮ 메뉴의 'Remove' 클릭 시
        request_resize(int dw, int dh) — 미래용 (드래그 리사이즈)
    """

    request_remove = Signal()

    def __init__(
        self,
        meta: "CardMeta",
        body: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._meta = meta

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACE.card_padding, SPACE.sm,
                                  SPACE.card_padding, SPACE.card_padding)
        outer.setSpacing(SPACE.sm)

        # ── 헤더 ──
        header = QHBoxLayout()
        header.setSpacing(SPACE.xs)

        if meta.icon:
            icon_lbl = QLabel(meta.icon)
            icon_lbl.setStyleSheet(
                f"color: {COLOR.text_2}; font-size: {FONT.title}px; background: transparent;"
            )
            header.addWidget(icon_lbl)

        title = QLabel(meta.name)
        title.setObjectName("cardTitle")
        title.setToolTip(meta.description or meta.name)
        header.addWidget(title)
        header.addStretch()

        self.menu_btn = QPushButton("⋮")
        self.menu_btn.setFixedSize(20, 20)
        self.menu_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; "
            f"color: {COLOR.text_2}; font-size: 16px; }} "
            f"QPushButton:hover {{ color: {COLOR.text_0}; }}"
        )
        self.menu_btn.setToolTip("카드 메뉴 (삭제 / 리사이즈)")
        self.menu_btn.clicked.connect(self._on_menu_clicked)
        header.addWidget(self.menu_btn)

        outer.addLayout(header)

        # ── 본문 슬롯 ──
        self._body_container = QVBoxLayout()
        self._body_container.setContentsMargins(0, 0, 0, 0)
        self._body_container.setSpacing(0)
        self._body_widget: QWidget | None = None
        outer.addLayout(self._body_container, stretch=1)
        self.set_body(body)

    @property
    def meta(self) -> "CardMeta":
        return self._meta

    def set_body(self, body: QWidget) -> None:
        """카드 본문 위젯 교체. 같은 위젯이 다시 들어오면 no-op (stateful 카드 보호)."""
        # 같은 인스턴스 재사용 케이스 — TraceCard 처럼 자체 canvas 보존하는 카드
        if body is not None and body is self._body_widget:
            return
        # 기존 위젯 정리
        if self._body_widget is not None:
            try:
                self._body_container.removeWidget(self._body_widget)
                self._body_widget.setParent(None)
                self._body_widget.deleteLater()
            except RuntimeError:
                pass
        self._body_widget = body
        if body is not None:
            body.setParent(self)
            self._body_container.addWidget(body)

    def _on_menu_clicked(self) -> None:
        """⋮ 클릭 — 단순화: Remove 만. 추후 QMenu 로 확장."""
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        act_remove = menu.addAction("✕  카드 제거")
        chosen = menu.exec(self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomRight()))
        if chosen is act_remove:
            self.request_remove.emit()
