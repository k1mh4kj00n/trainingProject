"""DashboardView — 12-column 그리드 카드 컨테이너.

흐름:
  1. add_card(card_id) → 카드 클래스 인스턴스화 + CardFrame 으로 감쌈 + 그리드 배치
  2. set_context(ctx) → 모든 카드의 compute(ctx) 재호출 + 본문 위젯 갱신
  3. remove_card(slot) → 카드 제거 + 그리드 재배치

레이아웃 모델:
  카드 = (col, row, w, h) 슬롯. 12 cols × N rows. 새 카드 추가 시 빈 슬롯 자동 탐색.
  복잡한 drag-resize 는 후속. Phase 1 은 자동 placement 만.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Type

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

from .cards.context import AnalysisContext
from .cards.registry import REGISTRY
from .theme.tokens import GRID_COLUMNS, GRID_ROW_HEIGHT, SPACE
from .widgets.card_frame import CardFrame

if TYPE_CHECKING:
    from .cards.protocol import AnalysisCard


@dataclass
class _Slot:
    card_id: str
    instance: "AnalysisCard"
    frame: CardFrame
    col: int
    row: int
    w: int
    h: int


class DashboardView(QWidget):
    """카드 그리드 + 컨텍스트 전파."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slots: list[_Slot] = []
        self._ctx: AnalysisContext = AnalysisContext.empty()

        # ScrollArea > inner QWidget > QGridLayout (카드 12col)
        outer = QGridLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(self._scroll, 0, 0)

        self._inner = QWidget()
        self._scroll.setWidget(self._inner)

        self._grid = QGridLayout(self._inner)
        self._grid.setContentsMargins(SPACE.lg, SPACE.lg, SPACE.lg, SPACE.lg)
        self._grid.setHorizontalSpacing(SPACE.grid_gap)
        self._grid.setVerticalSpacing(SPACE.grid_gap)
        # 12 컬럼 모두 동일 stretch (균등 분배)
        for c in range(GRID_COLUMNS):
            self._grid.setColumnStretch(c, 1)

    # ──────────────────────────────────────────────
    #  컨텍스트 전파
    # ──────────────────────────────────────────────
    def set_context(self, ctx: AnalysisContext) -> None:
        """선택한 condition / timepoint 등이 바뀌면 호출. 모든 카드 재계산·재렌더."""
        self._ctx = ctx
        for slot in self._slots:
            self._refresh_slot(slot)

    def context(self) -> AnalysisContext:
        return self._ctx

    def _refresh_slot(self, slot: _Slot) -> None:
        try:
            data = slot.instance.compute(self._ctx)
            body = slot.instance.render(slot.frame, data)
        except Exception as exc:  # noqa: BLE001
            from PySide6.QtWidgets import QLabel
            body = QLabel(f"[{slot.card_id}] 계산 실패\n{exc}")
            body.setStyleSheet("color: #EF4444;")
            body.setWordWrap(True)
        slot.frame.set_body(body)

    # ──────────────────────────────────────────────
    #  카드 추가/제거
    # ──────────────────────────────────────────────
    def add_card(self, card_id: str,
                 col: int | None = None, row: int | None = None,
                 w: int | None = None, h: int | None = None) -> _Slot | None:
        """등록된 카드 1개 추가. 위치 미지정 시 자동 placement."""
        cls = REGISTRY.get(card_id)
        if cls is None:
            return None
        instance = cls()
        meta = instance.meta
        cw = w or meta.default_size[0]
        ch = h or meta.default_size[1]
        if col is None or row is None:
            col, row = self._find_free_slot(cw, ch)

        frame = CardFrame(meta, body=_make_loading(), parent=self._inner)
        slot = _Slot(card_id=card_id, instance=instance, frame=frame,
                     col=col, row=row, w=cw, h=ch)
        self._slots.append(slot)
        self._grid.addWidget(frame, row, col, ch, cw)
        # 카드 높이 = h * GRID_ROW_HEIGHT (행별 권장 높이)
        # QGridLayout 은 row별 height 를 명시 못 함 → setRowMinimumHeight
        for r in range(row, row + ch):
            self._grid.setRowMinimumHeight(r, GRID_ROW_HEIGHT)

        # ⋮ 메뉴 → 제거
        frame.request_remove.connect(lambda s=slot: self.remove_slot(s))

        # 즉시 첫 계산
        self._refresh_slot(slot)
        return slot

    def remove_slot(self, slot: _Slot) -> None:
        if slot not in self._slots:
            return
        self._grid.removeWidget(slot.frame)
        slot.frame.setParent(None)
        slot.frame.deleteLater()
        self._slots.remove(slot)

    def remove_all(self) -> None:
        for slot in list(self._slots):
            self.remove_slot(slot)

    # ──────────────────────────────────────────────
    #  자동 placement — 빈 슬롯 탐색
    # ──────────────────────────────────────────────
    def _find_free_slot(self, w: int, h: int) -> tuple[int, int]:
        """주어진 (w, h) 가 들어갈 첫 빈 슬롯 찾기 (좌상단 우선)."""
        if w > GRID_COLUMNS:
            w = GRID_COLUMNS
        # 점유 표 (set of (col,row))
        occupied: set[tuple[int, int]] = set()
        for s in self._slots:
            for cc in range(s.col, s.col + s.w):
                for rr in range(s.row, s.row + s.h):
                    occupied.add((cc, rr))

        # row 0 부터 늘려가며 탐색 (충분히 큰 한도)
        for row in range(0, 256):
            for col in range(0, GRID_COLUMNS - w + 1):
                if all(
                    (cc, rr) not in occupied
                    for cc in range(col, col + w)
                    for rr in range(row, row + h)
                ):
                    return col, row
        return 0, 0  # fallback (이론상 도달 안 함)

    # ──────────────────────────────────────────────
    #  레이아웃 직렬화 (간단)
    # ──────────────────────────────────────────────
    def to_layout_dict(self) -> list[dict]:
        return [
            {"card_id": s.card_id, "col": s.col, "row": s.row, "w": s.w, "h": s.h}
            for s in self._slots
        ]

    def load_layout(self, layout: list[dict]) -> None:
        self.remove_all()
        for item in layout:
            self.add_card(
                item["card_id"],
                col=item.get("col"), row=item.get("row"),
                w=item.get("w"), h=item.get("h"),
            )


def _make_loading() -> QWidget:
    """카드 첫 표시 — compute 전 placeholder."""
    from PySide6.QtWidgets import QLabel

    lbl = QLabel("Loading…")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("color: #6F7783; font-size: 11px;")
    return lbl
