"""v2 진입점 — `python -m v2` 또는 직접 실행.

QApplication 부트 + 한국어 폰트 처리 + 전역 QSS 적용 + MainWindow.
"""

from __future__ import annotations

import sys
from pathlib import Path


# 한글 글리프 후보 (플랫폼별)
CJK_FONT_CANDIDATES = [
    "Pretendard",
    "Malgun Gothic",          # Windows 기본
    "맑은 고딕",
    "Noto Sans CJK KR",       # Linux
    "Noto Sans KR",
    "NanumGothic",
    "Apple SD Gothic Neo",    # macOS
    "AppleGothic",
]


def _ensure_path() -> None:
    """scripts/ 가 sys.path 에 있어야 v1 분석 엔진 import 가능."""
    here = Path(__file__).resolve()
    scripts_dir = here.parent.parent  # scripts/
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _pick_qt_cjk_font() -> str | None:
    """Qt 가 알고있는 폰트 중 한글 가능한 첫 후보."""
    from PySide6.QtGui import QFontDatabase

    families = set(QFontDatabase.families())
    for name in CJK_FONT_CANDIDATES:
        if name in families:
            return name
    return None


def _apply_matplotlib_cjk(qt_font_name: str | None) -> None:
    """matplotlib 그래프 안의 한국어 텍스트도 깨지지 않도록 폰트 등록.

    Qt 와 matplotlib 은 별도 폰트 검색 시스템을 쓴다.
    Linux 의 .ttc (Noto CJK) 는 findSystemFonts(fontext='ttf') 로 못 잡혀
    fc-list 로 직접 발견 후 addfont. 등록된 face 들 중 CJK 식별자 가진 것을
    rcParams['font.sans-serif'] 우선순위에 둔다.
    """
    import matplotlib
    import matplotlib.font_manager as fm

    extra_paths: list[str] = []
    for ext in ("ttf", "otf"):
        try:
            extra_paths.extend(fm.findSystemFonts(fontext=ext))
        except Exception:  # noqa: BLE001
            pass
    try:
        import subprocess
        out = subprocess.check_output(
            ["fc-list", ":lang=ko", "--format=%{file}\n"],
            text=True, timeout=2,
        )
        for line in out.splitlines():
            p = line.strip()
            if p:
                extra_paths.append(p)
    except Exception:  # noqa: BLE001
        pass

    seen: set[str] = set()
    for fp in extra_paths:
        if fp in seen:
            continue
        seen.add(fp)
        try:
            fm.fontManager.addfont(fp)
        except Exception:  # noqa: BLE001
            pass

    available = {f.name for f in fm.fontManager.ttflist}
    priority: list[str] = []
    if qt_font_name:
        priority.append(qt_font_name)
    priority.extend(CJK_FONT_CANDIDATES)
    for name in sorted(available):
        if any(k in name for k in ("CJK", "Gothic", "Nanum", "Hangul", "Korean", "Pretendard")):
            if name not in priority:
                priority.append(name)
    priority.append("DejaVu Sans")

    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = priority
    matplotlib.rcParams["axes.unicode_minus"] = False


def main(argv: list[str] | None = None) -> int:
    _ensure_path()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(argv or sys.argv)

    # Qt 위젯용 폰트
    qt_cjk = _pick_qt_cjk_font()
    if qt_cjk:
        app.setFont(QFont(qt_cjk, 10))

    # matplotlib 그래프용 폰트 (한국어 깨짐 방지)
    _apply_matplotlib_cjk(qt_cjk)

    from v2.theme.styles import apply_global_style

    apply_global_style(app)

    from v2.app import MainWindow

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
