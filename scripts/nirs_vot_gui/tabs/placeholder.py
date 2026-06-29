"""미구현 탭용 placeholder. Kubios의 5개 공식 탭 중 아직 만들지 않은 것들."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderTab(QWidget):
    def __init__(self, tab_name: str, eta: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel(tab_name)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22pt; font-weight: 700; color: #1A1A1A;")

        msg = QLabel("Coming in next iteration")
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet("font-size: 13pt; color: #888888; margin-top: 12px;")

        eta_lbl = QLabel(eta) if eta else None
        if eta_lbl is not None:
            eta_lbl.setAlignment(Qt.AlignCenter)
            eta_lbl.setStyleSheet("color: #AAAAAA; margin-top: 6px;")

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(msg)
        if eta_lbl is not None:
            layout.addWidget(eta_lbl)
        layout.addStretch()
