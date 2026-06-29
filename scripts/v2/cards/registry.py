"""카드 등록 — ``@register`` 데코레이터로 한 줄 등록.

전역 ``REGISTRY`` 에 누적되며, ``+ Add card`` 팔레트가 이걸 읽어 표시.

사용:
    from v2.cards import register, AnalysisCard, CardMeta

    @register
    class MyCard:
        meta = CardMeta(id="my_card", name="My Card", category="Custom")
        def compute(self, ctx): return {...}
        def render(self, parent, data): return QLabel(...)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, Type

if TYPE_CHECKING:
    from .protocol import AnalysisCard


# 전역 레지스트리 — id → 카드 클래스
REGISTRY: dict[str, Type["AnalysisCard"]] = {}


def register(cls: Type["AnalysisCard"]) -> Type["AnalysisCard"]:
    """클래스 데코레이터 — REGISTRY 에 등록.

    중복 id 는 마지막이 이김 (재로드 시 핫스왑).
    Protocol 검사는 일부 (meta 존재 여부) 만 — Python duck typing 에 맡김.
    """
    if not hasattr(cls, "meta"):
        raise TypeError(f"{cls.__name__} 은 'meta: CardMeta' 클래스 변수가 필요합니다.")
    cid = getattr(cls.meta, "id", None)
    if not cid:
        raise TypeError(f"{cls.__name__}.meta.id 가 비어있습니다.")
    REGISTRY[cid] = cls
    return cls


def get(card_id: str) -> Type["AnalysisCard"] | None:
    return REGISTRY.get(card_id)


def all_cards() -> Iterator[Type["AnalysisCard"]]:
    """등록된 모든 카드 클래스 (등록 순서 보존)."""
    return iter(REGISTRY.values())


def by_category() -> dict[str, list[Type["AnalysisCard"]]]:
    """카테고리별 그룹 — Add palette UI 용."""
    out: dict[str, list] = {}
    for cls in REGISTRY.values():
        cat = cls.meta.category
        out.setdefault(cat, []).append(cls)
    return out


def reset() -> None:
    """테스트 / hot reload 용."""
    REGISTRY.clear()
