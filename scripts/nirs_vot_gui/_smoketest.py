"""오프스크린 스크린샷으로 GUI 시각 검증 (v0.3).

캡처 순서:
    1. 시작 화면 (HRV 미로드, Overview 탭의 placeholder)
    2. HRV CSV 로드 후 Overview 탭
    3. Time-domain 탭
    4. Frequency-domain 탭
    5. Nonlinear 탭
    6. NIRS-VOT 탭 (HYPER Recovery2)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

for _sn in ("stdout", "stderr"):
    _s = getattr(sys, _sn, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from nirs_vot_gui.app import MainWindow  # type: ignore
else:
    from .app import MainWindow

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

try:
    from .main import _pick_cjk_font  # type: ignore
except ImportError:
    from nirs_vot_gui.main import _pick_cjk_font  # type: ignore


OUT_DIR = Path("docs/결과-results/gui-screenshots-v0.3")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _grab(window, filename: str, settle_ms: int = 250) -> Path:
    loop = QEventLoop()
    QTimer.singleShot(settle_ms, loop.quit)
    loop.exec()
    pix = window.grab()
    p = OUT_DIR / filename
    pix.save(str(p), "PNG")
    print(f"  saved: {p}  ({pix.width()}x{pix.height()})")
    return p


def main() -> int:
    app = QApplication(sys.argv)
    fn = _pick_cjk_font()
    if fn:
        app.setFont(QFont(fn, 9))
        print(f"[font] {fn}")

    w = MainWindow()
    w.resize(1600, 920)
    w.show()

    QTimer.singleShot(300, lambda: None)
    loop = QEventLoop(); QTimer.singleShot(300, loop.quit); loop.exec()

    print("[1] 시작 화면 (Overview placeholder)")
    _grab(w, "01_initial_empty.png")

    print("[2] HRV CSV 로드 → Overview")
    csv = Path("참고자료/Kubios 프로그램/이찬민_NOR_HRV.csv")
    w.controller.load_file(csv)
    w.tabs.setCurrentWidget(w.tab_overview)
    _grab(w, "02_hrv_overview.png")

    print("[3] Time-domain 탭")
    w.tabs.setCurrentWidget(w.tab_time)
    _grab(w, "03_hrv_time_domain.png")

    print("[4] Frequency-domain 탭")
    w.tabs.setCurrentWidget(w.tab_freq)
    _grab(w, "04_hrv_freq_domain.png")

    print("[5] Nonlinear 탭")
    w.tabs.setCurrentWidget(w.tab_nonlinear)
    _grab(w, "05_hrv_nonlinear.png")

    print("[6] NIRS-VOT 탭 (HYPER Recovery2)")
    w.tabs.setCurrentWidget(w.tab_nirs)
    w.tab_nirs.analyze_session("HYPER", "Recovery2")
    _grab(w, "06_nirs_vot.png")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
