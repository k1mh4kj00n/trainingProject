"""앱 엔트리포인트.

사용:
    python -m scripts.nirs_vot_gui.main
"""

from __future__ import annotations

import sys
from pathlib import Path

# 패키지/스크립트 양쪽 호환 import
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from nirs_vot_gui.app import MainWindow  # type: ignore
else:
    from .app import MainWindow

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


# 한글 글리프가 있는 폰트 후보. 플랫폼별로 먼저 발견된 것을 사용.
CJK_FONT_CANDIDATES = [
    "Malgun Gothic",          # Windows 기본 한글
    "맑은 고딕",
    "Noto Sans CJK KR",       # Linux 대부분
    "Noto Sans KR",
    "NanumGothic",
    "Apple SD Gothic Neo",    # macOS
    "AppleGothic",
]


def _pick_cjk_font() -> str | None:
    families = set(QFontDatabase.families())
    for name in CJK_FONT_CANDIDATES:
        if name in families:
            return name
    return None


def _apply_matplotlib_cjk(font_name: str | None) -> None:
    """matplotlib 의 기본 폰트도 한글 글리프가 있는 패밀리로 교체.

    PySide6 위젯과 matplotlib 은 별도의 폰트 검색 시스템을 쓴다.
    이걸 안 해주면 그래프 안의 한국어 텍스트가 □ 로 깨진다.

    Linux 의 ``Noto Sans CJK`` 류는 .ttc (multi-face) 라서 ``findSystemFonts`` 가
    기본 ``fontext='ttf'`` 로는 못 찾는다. ``fc-list`` (fontconfig) 으로 직접 한글 폰트
    파일을 찾아 ``addfont`` 한 뒤, ``font.sans-serif`` 우선순위 리스트에 등록된 face
    이름까지 함께 둬서 fallback 이 확실히 작동하도록 한다.
    """
    import matplotlib
    import matplotlib.font_manager as fm

    # 1) ttf / otf / ttc 시스템 폰트를 fontManager 에 추가
    extra_paths: list[str] = []
    for ext in ("ttf", "otf"):
        try:
            extra_paths.extend(fm.findSystemFonts(fontext=ext))
        except Exception:  # noqa: BLE001
            pass
    # ttc / 한국어 폰트 파일은 fontconfig 으로 보강 (Linux only)
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

    # 2) 등록된 폰트 중 한글 글리프 가능한 것 우선순위 결정
    available = {f.name for f in fm.fontManager.ttflist}

    # PySide6 가 고른 것 → CJK_FONT_CANDIDATES → 등록된 *CJK* / *Korean* 패밀리 자동 발견
    priority: list[str] = []
    if font_name:
        priority.append(font_name)
    priority.extend(CJK_FONT_CANDIDATES)
    # ttc 등록 시 face 인덱스에 따라 'Noto Sans CJK JP' 만 잡힐 수도 있어 일반 매칭 추가
    for name in sorted(available):
        if any(k in name for k in ("CJK", "Gothic", "Nanum", "Hangul", "Korean")):
            if name not in priority:
                priority.append(name)
    priority.append("DejaVu Sans")

    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = priority
    matplotlib.rcParams["axes.unicode_minus"] = False


def main() -> int:
    # Windows console이 UTF-8 출력을 못 할 때 이모지 등이 터지는 것 방지
    for s_name in ("stdout", "stderr"):
        _s = getattr(sys, s_name, None)
        if _s is not None and hasattr(_s, "reconfigure"):
            try:
                _s.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    # High-DPI 처리: Qt6는 기본 활성화이나 명시.
    # HighDpiScaleFactorRoundingPolicy로 125%/150% 등 분수 스케일에서도 깨짐 최소화.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("physical_analysis")
    app.setOrganizationName("physical_analysis")

    # 한글 표시용 기본 폰트 설정 (PySide6 + matplotlib 양쪽)
    font_name = _pick_cjk_font()
    if font_name is not None:
        app.setFont(QFont(font_name, 9))
    _apply_matplotlib_cjk(font_name)

    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
