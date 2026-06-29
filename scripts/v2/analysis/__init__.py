"""분석 카드 — 한 파일 = 한 카드 = 한 분석법.

이 패키지가 import 되는 순간 모든 *.py 가 자동 로드되어 ``REGISTRY`` 에 등록된다.
새 카드 추가 = 이 폴더에 파일 1개 + ``@register`` 데코레이터.
"""

from __future__ import annotations

import importlib
import pkgutil


def _autoload() -> None:
    """이 패키지의 모든 모듈 자동 import — @register 데코레이터 발화."""
    for mod_info in pkgutil.iter_modules(__path__):
        if mod_info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{mod_info.name}")


_autoload()
