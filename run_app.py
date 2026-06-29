"""PyInstaller / 스크립트 공용 엔트리.

개발 시:
    python run_app.py

PyInstaller 빌드:
    PyInstaller가 이 파일을 entry로 동결한다. spec 파일에 `pathex=['scripts']`가
    들어있어 `nirs_vot_gui` 패키지를 정상적으로 찾는다.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _prep_path() -> None:
    """개발 모드(미동결)에서만 scripts/ 를 sys.path에 추가."""
    if getattr(sys, "frozen", False):
        return
    scripts_dir = Path(__file__).resolve().parent / "scripts"
    if scripts_dir.is_dir():
        sys.path.insert(0, str(scripts_dir))


def main() -> int:
    _prep_path()
    from nirs_vot_gui.main import main as _main
    return _main()


if __name__ == "__main__":
    raise SystemExit(main())
