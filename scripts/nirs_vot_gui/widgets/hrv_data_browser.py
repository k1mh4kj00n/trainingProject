"""HRV 탭에서 좌측 도크에 보이는 측정 정보 패널.

Kubios의 Data Browser 위치를 그대로 사용해, 현재 로드된 HRV 측정의
파일명·메타·sample 구간·beats 수를 표시한다. 단일 측정만 다루므로
트리는 단순 (Measurement → Sample 1).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..hrv_state import HrvController


class HrvDataBrowser(QWidget):
    def __init__(self, controller: HrvController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctrl = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.title = QLabel("HRV Data")
        self.title.setProperty("role", "title")
        root.addWidget(self.title)

        # 메타 텍스트
        self.meta_label = QLabel("— 로드된 HRV 측정 없음 —\n\n[File → Open Kubios HRV CSV…]")
        self.meta_label.setStyleSheet("color: #666666; padding: 8px;")
        self.meta_label.setWordWrap(True)
        self.meta_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        root.addWidget(self.meta_label)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #DDDDDD;")
        root.addWidget(line)

        # 트리: Measurement → Sample
        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(14)
        self._model = QStandardItemModel(self)
        self.tree.setModel(self._model)
        root.addWidget(self.tree, stretch=1)

        controller.file_loaded.connect(self._on_loaded)
        controller.cleared.connect(self._on_cleared)

    # ──────────────────────────────────────────
    def _on_cleared(self) -> None:
        self.meta_label.setText("— 로드된 HRV 측정 없음 —\n\n[File → Open Kubios HRV CSV…]")
        self._model.clear()

    def _on_loaded(self, report) -> None:
        m = report.meta
        s = report.sample_info
        n = len(report.rr_intervals_s)
        path = self.ctrl.path

        info = []
        info.append(f"<b>{path.name}</b>" if path else "<b>(unnamed)</b>")
        if "Measurement date" in m:
            info.append(f"📅 {m['Measurement date']}")
        if "Data length" in m:
            info.append(f"⏱ {m['Data length']}")
        if "Channel label" in m:
            info.append(f"📡 {m['Channel label']}  ({m.get('File type', '?')})")
        if "Measurement rate" in m:
            info.append(f"🎚 {m['Measurement rate']}")
        info.append("")
        info.append(f"<b>Sample 1</b>")
        info.append(f"⌛ {s.get('limits', '?')}")
        info.append(f"💓 {n} beats  ·  effective {s.get('effective_length_s', '?')} s")
        info.append(f"🛠 corrected {s.get('beats_corrected', 0)} ({s.get('beats_corrected', 0) and round(100 * s['beats_corrected']/max(s.get('beats_total',1),1),2) or 0}%)")
        self.meta_label.setText("<br>".join(info))

        # 트리 갱신
        self._model.clear()
        root = self._model.invisibleRootItem()

        meas = QStandardItem(f"📊  {path.stem if path else 'measurement'}")
        meas.setEditable(False)
        root.appendRow(meas)

        sample = QStandardItem(f"📍  Sample 1   {s.get('limits', '?')}   ({n} beats)")
        sample.setEditable(False)
        meas.appendRow(sample)

        self.tree.expandAll()
