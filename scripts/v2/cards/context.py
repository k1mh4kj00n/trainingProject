"""AnalysisContext — 카드 compute 가 받는 입력 묶음.

v1 의 ``LoadedFile`` + 현재 선택된 condition/timepoint 를 합쳐 카드에 전달.
편집 카드는 ``apply(action, payload)`` 콜백으로 mainwindow 에 변경 사항 전달.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    import pandas as pd


# 편집 액션 이름 — mainwindow 의 dispatcher 가 처리
ACTION_SUBJECT_INFO = "subject_info"     # payload: dict
ACTION_TIMEPOINTS = "timepoints"         # payload: list[Timepoint]
ACTION_TTE = "tte"                       # payload: dict (TTE1/TTE2/TTE_maintenance_rate)
ACTION_OVERRIDES = "overrides"           # payload: dict (baseline/min_time/peak_time)
ACTION_AUTO_DETECT = "auto_detect"       # payload: None — Min/Peak 자동 검출 트리거


@dataclass
class AnalysisContext:
    """한 카드의 ``compute(ctx)`` 호출에 필요한 모든 정보.

    - subject_info: cfg.subject_info (이름·나이·VO2 등)
    - condition: 'HYPER' / 'NOR' / 'HYPO' 등
    - timepoint: 현재 분석 대상 timepoint 이름 (예: 'Recovery2')
    - smoothed: SmO2_smooth DataFrame (시계열)
    - anchor: 4점 anchor (start/inflate/deflate/end) — v1 의 Anchor
    - overrides: 사용자가 그래프 위에서 잡은 baseline / min / peak override
    - vot_truth: Coded Data 의 ground truth (해당 timepoint)
    - all_loaded: 비교용 — {condition: LoadedFile}
    - cfg: SessionConfig 전체 참조 (timepoint 편집·exercise 등 접근용)
    - apply: 편집 카드의 변경 사항을 mainwindow 로 전달하는 콜백
              ``apply(action: str, payload: Any)`` — action 은 ACTION_* 상수
    """

    subject_info: dict
    condition: str
    timepoint: str
    smoothed: "pd.DataFrame"
    anchor: Any  # v1 의 Anchor (clock str 4개)
    overrides: dict
    vot_truth: dict
    all_loaded: dict  # {cond: LoadedFile}
    cfg: Any = None
    apply: Optional[Callable[[str, Any], None]] = None

    @classmethod
    def empty(cls) -> "AnalysisContext":
        """데이터 없을 때 (앱 시작 직후) 카드 render 용 placeholder."""
        import pandas as pd
        return cls(
            subject_info={},
            condition="",
            timepoint="",
            smoothed=pd.DataFrame(),
            anchor=None,
            overrides={},
            vot_truth={},
            all_loaded={},
            cfg=None,
            apply=None,
        )

    @property
    def is_ready(self) -> bool:
        """compute 가 의미있는 결과를 낼 수 있는 상태인지."""
        return (
            self.condition != ""
            and self.timepoint != ""
            and self.smoothed is not None
            and not self.smoothed.empty
            and self.anchor is not None
        )

    def has_cfg(self) -> bool:
        return self.cfg is not None
