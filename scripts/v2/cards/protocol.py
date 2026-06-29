"""AnalysisCard Protocol — 모든 분석 카드의 인터페이스.

분석 카드 1개 = 입력(ctx) → 계산(compute) → 렌더(render) 의 3단 분리.
``meta`` 클래스 변수로 카드의 자기소개 (이름·아이콘·기본 사이즈).

새 분석 카드 = 이 Protocol 만족하는 클래스 1개 + ``@register`` 데코레이터.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from .context import AnalysisContext


@dataclass(frozen=True)
class CardMeta:
    """카드의 자기소개. ``+ Add card`` 팔레트 / 카드 헤더에 사용."""

    id: str                         # 'baseline_smo2' (snake_case, 등록 키)
    name: str                       # 'Baseline SmO2' (사용자 표시)
    category: str = "NIRS"          # 'NIRS' / 'HRV' / 'Compare' / 'Custom'
    icon: str = "•"                 # 글리프 또는 아이콘 이름
    description: str = ""           # 1줄 설명
    default_size: tuple[int, int] = (3, 2)  # (cols, rows) — 12-col grid 기준
    min_size: tuple[int, int] = (2, 1)
    max_size: tuple[int, int] = (12, 6)


@runtime_checkable
class AnalysisCard(Protocol):
    """모든 분석 카드가 만족해야 할 인터페이스.

    클래스 변수 ``meta`` 와 메서드 2개 (``compute`` / ``render``) 만 있으면 됨.
    """

    meta: CardMeta

    def compute(self, ctx: "AnalysisContext") -> dict:
        """ctx → 결과 dict. 순수 함수 권장 (사이드이펙트 X).

        결과는 ``render`` 가 받아 위젯에 그림. 비싼 연산은 여기에서.
        """
        ...

    def render(self, parent: "QWidget", data: dict) -> "QWidget":
        """``data`` (compute 결과) 를 그리는 Qt 위젯 반환.

        부모 위젯 layout 에 추가 가능한 형태. 카드 chrome (헤더/메뉴) 은
        ``CardFrame`` 이 자동 감쌈 — 여기서는 본문만 만들면 됨.
        """
        ...
