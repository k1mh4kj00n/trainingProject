"""NIRS-VOT 분석 엔진.

Kubios HRV Scientific 스타일의 탭 기반 분석 앱을 지향하는 첫 번째 모듈.
Calf (종아리) SmO2 시계열 데이터에서 VOT(Vascular Occlusion Test) 표준
지표 12종을 산출한다.

기존 R 스크립트 (참고자료/NIRS_VOT_분석용.R, 작성: 코딩하는 김재혁) 로직을
Python으로 포팅했으며, 동일한 결과가 나오도록 설계되었다.
"""

from .anchors import SESSION_ANCHORS, get_anchors
from .loader import load_calf_csv
from .preprocess import preprocess
from .metrics import compute_metrics, MetricsResult
from .plot import plot_session

__all__ = [
    "SESSION_ANCHORS",
    "get_anchors",
    "load_calf_csv",
    "preprocess",
    "compute_metrics",
    "MetricsResult",
    "plot_session",
]
