"""HRV 분석 상태 컨트롤러.

GUI 전반에서 단일 진실 소스(single source of truth)로서
현재 로드된 Kubios CSV와 분석 결과를 보유한다. 각 탭은 시그널을 구독해
같은 데이터를 동시에 그린다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

try:
    from ..hrv_analysis.loader import KubiosReport, load_kubios_csv  # type: ignore
    from ..hrv_analysis.time_domain import TimeDomainResult, compute_time_domain  # type: ignore
    from ..hrv_analysis.freq_domain import FreqDomainResult, compute_freq_domain  # type: ignore
    from ..hrv_analysis.nonlinear import NonlinearResult, compute_nonlinear  # type: ignore
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hrv_analysis.loader import KubiosReport, load_kubios_csv  # type: ignore
    from hrv_analysis.time_domain import TimeDomainResult, compute_time_domain  # type: ignore
    from hrv_analysis.freq_domain import FreqDomainResult, compute_freq_domain  # type: ignore
    from hrv_analysis.nonlinear import NonlinearResult, compute_nonlinear  # type: ignore


class HrvController(QObject):
    """모든 HRV 탭이 공유하는 분석 상태."""

    file_loaded = Signal(object)        # KubiosReport
    analyzed   = Signal()                # td/fd/nl 모두 준비됨
    cleared    = Signal()
    status     = Signal(str)
    error      = Signal(str)
    range_changed = Signal(float, float) # 선택된 (t_start_abs, t_end_abs) 초 단위

    def __init__(self) -> None:
        super().__init__()
        self._report: Optional[KubiosReport] = None
        self._td: Optional[TimeDomainResult] = None
        self._fd: Optional[FreqDomainResult] = None
        self._nl: Optional[NonlinearResult] = None
        self._path: Optional[Path] = None
        # 현재 선택된 분석 범위 (절대 시간 초). None이면 전체.
        self._range_abs: tuple[float, float] | None = None

    # ── properties ────────────────────────────
    @property
    def report(self) -> Optional[KubiosReport]:
        return self._report

    @property
    def td(self) -> Optional[TimeDomainResult]:
        return self._td

    @property
    def fd(self) -> Optional[FreqDomainResult]:
        return self._fd

    @property
    def nl(self) -> Optional[NonlinearResult]:
        return self._nl

    @property
    def path(self) -> Optional[Path]:
        return self._path

    @property
    def has_data(self) -> bool:
        return self._report is not None

    @property
    def has_results(self) -> bool:
        return self._td is not None and self._fd is not None and self._nl is not None

    @property
    def range_abs(self) -> tuple[float, float] | None:
        """현재 분석에 사용 중인 절대 시간 범위 (초). None이면 전체."""
        return self._range_abs

    @property
    def full_range_abs(self) -> tuple[float, float] | None:
        """파일 전체 RR 시계열의 절대 시간 범위."""
        if self._report is None or len(self._report.rr_times_s) == 0:
            return None
        t = self._report.rr_times_s
        return float(t[0]), float(t[-1])

    # ── actions ───────────────────────────────
    def load_file(self, path: str | Path) -> bool:
        path = Path(path)
        try:
            rep = load_kubios_csv(path)
        except Exception as exc:  # noqa: BLE001
            self._report = None
            self._path = None
            self.error.emit(f"파일 로드 실패: {exc}")
            self.cleared.emit()
            return False
        self._report = rep
        self._path = path
        self._td = self._fd = self._nl = None
        n = len(rep.rr_intervals_s)
        limits = rep.sample_info.get("limits", "?")
        self.status.emit(f"Loaded: {path.name}  |  {n} beats  |  sample {limits}")
        self.file_loaded.emit(rep)
        # Kubios도 파일 열면 즉시 분석. 여기서도 동일.
        return self.analyze()

    def analyze(self) -> bool:
        """전체 시계열 재분석 (선택 범위 초기화)."""
        return self.analyze_range(None, None)

    def analyze_range_with_bands(self, t_start_abs: float, t_end_abs: float,
                                  bands: dict) -> bool:
        """analyze_range + 사용자 정의 VLF/LF/HF band 적용.

        ``bands`` — ``{"VLF": (lo, hi), "LF": (lo, hi), "HF": (lo, hi)}``.
        compute_freq_domain 인자로 전달. 다른 분석은 default 그대로.
        """
        return self._analyze_internal(t_start_abs, t_end_abs, bands=bands)

    def analyze_range(self, t_start_abs: float | None,
                      t_end_abs: float | None) -> bool:
        """절대 시간 [t_start, t_end]의 RR만 사용해 분석.

        None을 주면 해당 끝은 전체 범위로 클램프.
        선택 범위에 RR이 너무 적으면(<20) 분석 거부.
        """
        return self._analyze_internal(t_start_abs, t_end_abs, bands=None)

    def _analyze_internal(self, t_start_abs: float | None,
                          t_end_abs: float | None,
                          *, bands: dict | None) -> bool:
        """range + (optional) bands 동시 적용 — analyze_range / analyze_range_with_bands 공용."""
        if self._report is None:
            self.error.emit("먼저 파일을 로드하세요.")
            return False
        rep = self._report
        t_all = rep.rr_times_s
        rr_all_s = rep.rr_intervals_s
        if len(t_all) == 0:
            self.error.emit("RR 시계열이 비어 있음.")
            return False

        t0 = float(t_start_abs) if t_start_abs is not None else float(t_all[0])
        t1 = float(t_end_abs)   if t_end_abs   is not None else float(t_all[-1])
        if t1 <= t0:
            self.error.emit(f"잘못된 범위: t1({t1:.1f}) ≤ t0({t0:.1f})")
            return False

        mask = (t_all >= t0) & (t_all <= t1)
        n = int(mask.sum())
        if n < 20:
            self.error.emit(f"선택 범위에 RR이 너무 적음: {n} beats (최소 20)")
            return False

        t_sel = t_all[mask]
        rr_sel_s = rr_all_s[mask]
        rr_ms = rr_sel_s * 1000.0

        try:
            self._td = compute_time_domain(rr_ms)
            if bands:
                self._fd = compute_freq_domain(
                    t_sel, rr_sel_s,
                    vlf=bands.get("VLF", (0.0, 0.04)),
                    lf=bands.get("LF",  (0.04, 0.15)),
                    hf=bands.get("HF",  (0.15, 0.4)),
                )
            else:
                self._fd = compute_freq_domain(t_sel, rr_sel_s)
            self._nl = compute_nonlinear(rr_ms)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"분석 실패: {exc}")
            return False

        full = (t_start_abs is None and t_end_abs is None)
        self._range_abs = None if full else (t0, t1)

        band_tag = ""
        if bands:
            band_tag = f" · bands custom"
        self.status.emit(
            f"Analyzed: {n} beats · SDNN {self._td.sdnn_ms:.2f}ms · "
            f"LF/HF {self._fd.lf_hf_ratio:.2f} · DFA α1 {self._nl.dfa_alpha1:.3f}{band_tag}"
        )
        self.range_changed.emit(t0, t1)
        self.analyzed.emit()
        return True

    def clear(self) -> None:
        self._report = None
        self._path = None
        self._td = self._fd = self._nl = None
        self._range_abs = None
        self.cleared.emit()
        self.status.emit("Ready")
