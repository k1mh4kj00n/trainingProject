"""Kubios HRV Scientific 호환 HRV 분석 엔진.

Ground truth: 참고자료/Kubios 프로그램/이찬민_NOR_HRV.{csv,pdf}
Kubios 4.2.0 (2025-06) 기준, Sample 1 (14:06:31-14:11:31, 464 beats) 값에 맞춰 검증한다.

구현 원칙:
- 직접 구현 (scipy + numpy). 라이브러리 의존 최소화.
- Kubios User's Guide 2026 Appendix A의 수식을 그대로 따른다.
- 기본 파라미터는 Kubios 기본값(CSV에 기록된 실제 설정)을 반영.
"""

from .loader import load_kubios_csv
from .time_domain import compute_time_domain, TimeDomainResult

__all__ = [
    "load_kubios_csv",
    "compute_time_domain",
    "TimeDomainResult",
]
