"""HRV 분석 전용 파라미터 패널 (NIRS ParameterPanel 의 HRV 짝).

NIRS 와 입력·도메인이 다르므로 별도 패널.
입력 출처:
  - **Kubios CSV** (raw RR 시계열 + ``time_varying`` 슬라이딩 윈도우 표 + Kubios metrics)
  - (선택) **NIRS xlsx** 의 ``cfg.timepoints["HRV"]`` 와 ``cfg.hrv_truth``

그룹 구성:
  1) Measurement info  — 파일 / 측정일 / sample limits / beats (read-only)
  2) External lookup    — HH:MM:SS 입력 → ``time_varying_at`` 에서 가장 가까운 행 표시
                            (자체 분석 없이도 그 시점의 SDNN/LF/HF/DFA 확인 가능)
  3) Analysis range     — ``rr_times_s`` 범위 내 (t0, t1) 초 입력 + Apply
                            → HrvController.analyze_range 호출
  4) Frequency bands    — VLF / LF / HF (default Kubios 0/0.04/0.15/0.4)
                            → controller 가 ``compute_freq_domain`` 에 전달
  5) External truth     — xlsx ``hrv_truth.Baseline / Post`` 5 metric (있으면)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTime, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from ..hrv_state import HrvController  # type: ignore
except ImportError:
    from hrv_state import HrvController  # type: ignore


# 5 핵심 HRV metric — xlsx hrv_truth 키 ↔ time_varying 컬럼 ↔ 자체 결과 매핑
_HRV_TRUTH_KEYS = ("HRV_SDNN", "HRV_RMSSD", "HRV_LF", "HRV_HF", "HRV_LF/HF")
_TV_LOOKUP = {
    "HRV_SDNN":   "SDNN",
    "HRV_RMSSD":  "RMSSD",
    "HRV_LF":     "LF power (n.u.)",
    "HRV_HF":     "HF power (n.u.)",
    "HRV_LF/HF":  "LF/HF ratio",
}
_DISPLAY_NAMES = {
    "HRV_SDNN":  "SDNN (ms)",
    "HRV_RMSSD": "RMSSD (ms)",
    "HRV_LF":    "LF (n.u.)",
    "HRV_HF":    "HF (n.u.)",
    "HRV_LF/HF": "LF / HF",
}


def _hms_to_sec(s: str) -> Optional[int]:
    parts = (s or "").strip().split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return None
    return None


def _qtime_to_str(q: QTime) -> str:
    return f"{q.hour():02d}:{q.minute():02d}:{q.second():02d}"


def _h(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet("color: #6A737D; font-size: 9pt;")
    l.setAlignment(Qt.AlignCenter)
    return l


class HrvParameterPanel(QWidget):
    """HRV 입력값 편집 + Apply + 외부 검증값 비교."""

    # session "Baseline" 또는 "Recovery2" 또는 "" (custom) 라벨
    range_apply_requested = Signal(str)

    def __init__(self, controller: HrvController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl = controller
        self._nirs_cfg = None   # 외부 NIRS xlsx (cfg.timepoints["HRV"], cfg.hrv_truth)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        scroll.setWidget(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        root = QVBoxLayout(body)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.title_label = QLabel("HRV parameters  ·  (no data)")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        self.title_label.setWordWrap(True)
        root.addWidget(self.title_label)

        # ── 헤더 버튼 ──
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(6)
        self.load_params_btn = QPushButton("📥  Load params…")
        self.load_params_btn.setToolTip(
            "HRV 파라미터 스냅샷(xlsx/csv/txt) 불러오기 — Range, Bands."
        )
        self.load_params_btn.clicked.connect(self._on_load_params)
        hdr.addWidget(self.load_params_btn)
        self.save_params_btn = QPushButton("💾  Save params…")
        self.save_params_btn.setToolTip(
            "현재 패널의 모든 HRV 파라미터를 xlsx/csv/txt 로 저장."
        )
        self.save_params_btn.clicked.connect(self._on_save_params)
        hdr.addWidget(self.save_params_btn)
        hdr.addStretch()
        root.addLayout(hdr)

        # ── (1) Measurement info — read-only ──
        info_box = QGroupBox("Measurement info  (Kubios CSV 메타)")
        info_form = QFormLayout(info_box)
        info_form.setContentsMargins(8, 12, 8, 8)
        self.lbl_file        = QLabel("—")
        self.lbl_meas_date   = QLabel("—")
        self.lbl_sample      = QLabel("—")
        self.lbl_beats       = QLabel("—")
        for lb in (self.lbl_file, self.lbl_meas_date, self.lbl_sample, self.lbl_beats):
            lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lb.setStyleSheet("color: #24292E;")
        info_form.addRow("File:",            self.lbl_file)
        info_form.addRow("Measurement date:", self.lbl_meas_date)
        info_form.addRow("Sample limits:",   self.lbl_sample)
        info_form.addRow("Beats total:",     self.lbl_beats)
        root.addWidget(info_box)

        # ── (2) External lookup — time_varying 매칭 ──
        lookup_box = QGroupBox("External lookup  (Kubios time-varying 표 조회)")
        lk_lay = QVBoxLayout(lookup_box)
        lk_lay.setContentsMargins(8, 12, 8, 8)

        lk_row = QHBoxLayout()
        lk_row.addWidget(QLabel("HH:MM:SS:"))
        self.lookup_time = QTimeEdit()
        self.lookup_time.setDisplayFormat("HH:mm:ss")
        lk_row.addWidget(self.lookup_time)
        self.lookup_btn = QPushButton("▶  Find")
        self.lookup_btn.setToolTip(
            "Kubios time_varying 표에서 가장 가까운 윈도우(±90s)의 5 핵심 metric 표시."
        )
        self.lookup_btn.clicked.connect(self._on_lookup)
        lk_row.addWidget(self.lookup_btn)
        lk_row.addStretch()
        lk_lay.addLayout(lk_row)

        # 5 metric 라벨
        lk_grid = QGridLayout()
        lk_grid.setHorizontalSpacing(8)
        lk_grid.setVerticalSpacing(2)
        lk_grid.addWidget(_h("Metric"),    0, 0)
        lk_grid.addWidget(_h("Kubios TV"), 0, 1)
        self._lookup_value_labels: dict[str, QLabel] = {}
        for r, key in enumerate(_HRV_TRUTH_KEYS, start=1):
            lk_grid.addWidget(QLabel(_DISPLAY_NAMES[key]), r, 0)
            v = QLabel("—")
            v.setStyleSheet("color: #0969DA; font-weight: bold;")
            v.setAlignment(Qt.AlignRight)
            v.setMinimumWidth(80)
            lk_grid.addWidget(v, r, 1)
            self._lookup_value_labels[key] = v
        lk_lay.addLayout(lk_grid)
        self.lookup_status = QLabel("")
        self.lookup_status.setStyleSheet("color: #6A737D; font-size: 9pt;")
        lk_lay.addWidget(self.lookup_status)
        root.addWidget(lookup_box)

        # ── (3) Analysis range — rr_times_s 범위 내 ──
        range_box = QGroupBox("Analysis range  (자체 분석 호출)")
        range_lay = QFormLayout(range_box)
        range_lay.setContentsMargins(8, 12, 8, 8)
        self.range_t0 = QDoubleSpinBox()
        self.range_t0.setRange(0, 86400.0)
        self.range_t0.setDecimals(2)
        self.range_t0.setSuffix(" s")
        self.range_t0.setSingleStep(1.0)
        self.range_t1 = QDoubleSpinBox()
        self.range_t1.setRange(0, 86400.0)
        self.range_t1.setDecimals(2)
        self.range_t1.setSuffix(" s")
        self.range_t1.setSingleStep(1.0)
        range_lay.addRow("t_start (절대 초):", self.range_t0)
        range_lay.addRow("t_end (절대 초):",   self.range_t1)
        rb_row = QHBoxLayout()
        self.btn_range_full = QPushButton("Full")
        self.btn_range_full.setToolTip("전체 RR 시계열로 분석")
        self.btn_range_full.clicked.connect(self._on_range_full)
        rb_row.addWidget(self.btn_range_full)
        self.btn_range_apply = QPushButton("▶  Apply range")
        self.btn_range_apply.setToolTip("입력한 (t0, t1) 으로 HrvController.analyze_range 호출")
        self.btn_range_apply.clicked.connect(self._on_range_apply)
        rb_row.addWidget(self.btn_range_apply)
        rb_row.addStretch()
        range_lay.addRow(rb_row)
        root.addWidget(range_box)

        # ── (4) Frequency bands ──
        band_box = QGroupBox("Frequency bands  (Hz)")
        band_grid = QGridLayout(band_box)
        band_grid.setContentsMargins(8, 12, 8, 8)
        band_grid.setHorizontalSpacing(8)
        band_grid.setVerticalSpacing(4)
        band_grid.addWidget(_h("lo"),   0, 1)
        band_grid.addWidget(_h("hi"),   0, 2)
        self.band_inputs: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox]] = {}
        defaults = {"VLF": (0.0, 0.04), "LF": (0.04, 0.15), "HF": (0.15, 0.4)}
        for r, (name, (lo, hi)) in enumerate(defaults.items(), start=1):
            band_grid.addWidget(QLabel(f"<b>{name}</b>"), r, 0)
            sp_lo = QDoubleSpinBox(); sp_lo.setRange(0.0, 5.0); sp_lo.setDecimals(4); sp_lo.setSingleStep(0.01); sp_lo.setValue(lo)
            sp_hi = QDoubleSpinBox(); sp_hi.setRange(0.0, 5.0); sp_hi.setDecimals(4); sp_hi.setSingleStep(0.01); sp_hi.setValue(hi)
            band_grid.addWidget(sp_lo, r, 1)
            band_grid.addWidget(sp_hi, r, 2)
            self.band_inputs[name] = (sp_lo, sp_hi)
        self.band_reset_btn = QPushButton("↺  Reset to Kubios defaults")
        self.band_reset_btn.clicked.connect(self._on_bands_reset)
        band_grid.addWidget(self.band_reset_btn, 4, 0, 1, 3)
        root.addWidget(band_box)

        # ── (5) External truth — xlsx hrv_truth (있으면) ──
        truth_box = QGroupBox("External truth  (NIRS xlsx hrv_truth)")
        t_grid = QGridLayout(truth_box)
        t_grid.setContentsMargins(8, 12, 8, 8)
        t_grid.setHorizontalSpacing(8)
        t_grid.setVerticalSpacing(2)
        t_grid.addWidget(_h("Metric"),       0, 0)
        t_grid.addWidget(_h("xlsx Baseline"),0, 1)
        t_grid.addWidget(_h("xlsx Post"),    0, 2)
        self._truth_labels: dict[str, tuple[QLabel, QLabel]] = {}
        for r, key in enumerate(_HRV_TRUTH_KEYS, start=1):
            t_grid.addWidget(QLabel(_DISPLAY_NAMES[key]), r, 0)
            l_b = QLabel("—"); l_b.setAlignment(Qt.AlignRight); l_b.setMinimumWidth(70)
            l_p = QLabel("—"); l_p.setAlignment(Qt.AlignRight); l_p.setMinimumWidth(70)
            l_b.setStyleSheet("color: #6F42C1;")
            l_p.setStyleSheet("color: #6F42C1;")
            t_grid.addWidget(l_b, r, 1)
            t_grid.addWidget(l_p, r, 2)
            self._truth_labels[key] = (l_b, l_p)
        self.truth_status = QLabel("")
        self.truth_status.setStyleSheet("color: #6A737D; font-size: 9pt;")
        t_grid.addWidget(self.truth_status, 6, 0, 1, 3)
        root.addWidget(truth_box)

        # ── 하단 Apply All ──
        btns = QHBoxLayout()
        btns.addStretch()
        self.apply_btn = QPushButton("▶  Apply")
        self.apply_btn.setToolTip(
            "현재 range + bands 로 HrvController 재분석 — 결과 패널 즉시 갱신"
        )
        self.apply_btn.setStyleSheet(
            "background-color: #0969DA; color: white; "
            "font-weight: bold; padding: 6px 18px;"
        )
        self.apply_btn.clicked.connect(self._on_apply_all)
        btns.addWidget(self.apply_btn)
        root.addLayout(btns)

        root.addStretch()
        self.set_enabled(False)

        # controller 시그널 — 새 파일 로드 / 분석 변화 시 라벨 갱신
        self._ctrl.file_loaded.connect(self._on_file_loaded)
        self._ctrl.cleared.connect(self._on_cleared)

    # ──────────────────────────────────────────
    #  Public — 외부에서 NIRS cfg 를 주입
    # ──────────────────────────────────────────
    def set_nirs_config(self, cfg) -> None:
        """NIRS xlsx 의 SessionConfig 를 받아 hrv_truth 5 metric 표시."""
        self._nirs_cfg = cfg
        self._refresh_truth()

    # ──────────────────────────────────────────
    #  Internal — Kubios 파일 로드/clear 시 라벨 갱신
    # ──────────────────────────────────────────
    def _on_file_loaded(self, rep) -> None:
        try:
            self.lbl_file.setText(rep.file_path.name if rep.file_path else "—")
            self.lbl_meas_date.setText(str(rep.meta.get("Measurement date", "—")))
            self.lbl_sample.setText(str(rep.sample_info.get("limits", "—")))
            self.lbl_beats.setText(str(rep.sample_info.get("beats_total", "—")))
            # Range 의 default = 전체 범위
            t = rep.rr_times_s
            if len(t) >= 2:
                self.range_t0.setRange(float(t[0]), float(t[-1]))
                self.range_t1.setRange(float(t[0]), float(t[-1]))
                self.range_t0.setValue(float(t[0]))
                self.range_t1.setValue(float(t[-1]))
            # 측정 시작 시각으로 lookup default
            sample = str(rep.sample_info.get("limits", ""))
            if "-" in sample:
                start_hms = sample.split("-", 1)[0].strip()
                t = _hms_to_sec(start_hms)
                if t is not None:
                    self.lookup_time.setTime(QTime((t // 3600) % 24, (t % 3600) // 60, t % 60))
            self.title_label.setText(
                f"HRV parameters  ·  <b>{rep.file_path.name if rep.file_path else '?'}</b>"
            )
            self.set_enabled(True)
        except Exception as exc:  # noqa: BLE001
            self.title_label.setText(f"HRV parameters  ·  load error: {exc}")
        self._refresh_truth()

    def _on_cleared(self) -> None:
        self.lbl_file.setText("—")
        self.lbl_meas_date.setText("—")
        self.lbl_sample.setText("—")
        self.lbl_beats.setText("—")
        self.range_t0.setValue(0); self.range_t1.setValue(0)
        for v in self._lookup_value_labels.values():
            v.setText("—")
        self.lookup_status.setText("")
        self.title_label.setText("HRV parameters  ·  (no data)")
        self.set_enabled(False)

    def _refresh_truth(self) -> None:
        cfg = self._nirs_cfg
        if cfg is None or not getattr(cfg, "hrv_truth", None):
            for l_b, l_p in self._truth_labels.values():
                l_b.setText("—"); l_p.setText("—")
            self.truth_status.setText("NIRS xlsx 미연결 — hrv_truth 없음")
            return
        b = cfg.hrv_truth.get("Baseline", {}) or {}
        p = cfg.hrv_truth.get("Post", {}) or {}
        for key in _HRV_TRUTH_KEYS:
            l_b, l_p = self._truth_labels[key]
            l_b.setText(_fmt_truth(b.get(key)))
            l_p.setText(_fmt_truth(p.get(key)))
        self.truth_status.setText(
            f"NIRS xlsx: {cfg.file_path.name if getattr(cfg, 'file_path', None) else 'loaded'}"
        )

    # ──────────────────────────────────────────
    #  Lookup
    # ──────────────────────────────────────────
    def _on_lookup(self) -> None:
        rep = self._ctrl.report
        if rep is None or rep.time_varying is None or rep.time_varying.empty:
            self.lookup_status.setText("Kubios CSV 미로드 또는 time_varying 없음")
            for v in self._lookup_value_labels.values():
                v.setText("—")
            return
        hms = _qtime_to_str(self.lookup_time.time())
        row = rep.time_varying_at(hms)
        if row is None:
            self.lookup_status.setText(f"{hms}: time_varying 범위 밖 (±90s)")
            for v in self._lookup_value_labels.values():
                v.setText("—")
            return
        delta = abs(_hms_to_sec(str(row['Time'])) - _hms_to_sec(hms))
        self.lookup_status.setText(f"{hms} → 매칭 {row['Time']} (Δ {delta}s)")
        for key in _HRV_TRUTH_KEYS:
            col = _TV_LOOKUP[key]
            val = row.get(col, None)
            self._lookup_value_labels[key].setText(_fmt_num(val))

    # ──────────────────────────────────────────
    #  Range
    # ──────────────────────────────────────────
    def _on_range_full(self) -> None:
        rep = self._ctrl.report
        if rep is None:
            return
        t = rep.rr_times_s
        if len(t) < 2:
            return
        self.range_t0.setValue(float(t[0]))
        self.range_t1.setValue(float(t[-1]))

    def _on_range_apply(self) -> None:
        if self._ctrl.report is None:
            QMessageBox.warning(self, "HRV", "Kubios CSV 를 먼저 로드하세요.")
            return
        t0 = float(self.range_t0.value())
        t1 = float(self.range_t1.value())
        if t1 <= t0:
            QMessageBox.warning(self, "HRV", f"잘못된 범위: t1 ({t1}) ≤ t0 ({t0})")
            return
        # bands 도 적용해서 재분석
        bands = self._collect_bands()
        ok = self._ctrl.analyze_range_with_bands(t0, t1, bands)
        if ok:
            self._flash_apply()
        self.range_apply_requested.emit("custom")

    # ──────────────────────────────────────────
    #  Bands
    # ──────────────────────────────────────────
    def _collect_bands(self) -> dict:
        out: dict[str, tuple[float, float]] = {}
        for name, (sp_lo, sp_hi) in self.band_inputs.items():
            out[name] = (float(sp_lo.value()), float(sp_hi.value()))
        return out

    def _on_bands_reset(self) -> None:
        defaults = {"VLF": (0.0, 0.04), "LF": (0.04, 0.15), "HF": (0.15, 0.4)}
        for name, (lo, hi) in defaults.items():
            sp_lo, sp_hi = self.band_inputs[name]
            sp_lo.setValue(lo); sp_hi.setValue(hi)

    def _on_apply_all(self) -> None:
        """현재 (range, bands) 모두 적용해서 재분석."""
        self._on_range_apply()

    def _flash_apply(self) -> None:
        orig = self.apply_btn.styleSheet()
        self.apply_btn.setText("✓  Applied")
        self.apply_btn.setStyleSheet(
            "background-color: #16A34A; color: white; "
            "font-weight: bold; padding: 6px 18px;"
        )
        QTimer.singleShot(900, lambda: (
            self.apply_btn.setText("▶  Apply"),
            self.apply_btn.setStyleSheet(orig),
        ))

    # ──────────────────────────────────────────
    #  enable / disable
    # ──────────────────────────────────────────
    def set_enabled(self, enabled: bool) -> None:
        for w in (self.lookup_time, self.lookup_btn,
                  self.range_t0, self.range_t1,
                  self.btn_range_full, self.btn_range_apply,
                  self.band_reset_btn, self.apply_btn):
            w.setEnabled(enabled)
        for sp_lo, sp_hi in self.band_inputs.values():
            sp_lo.setEnabled(enabled)
            sp_hi.setEnabled(enabled)

    # ──────────────────────────────────────────
    #  Save / Load HRV params (xlsx/csv/txt)
    # ──────────────────────────────────────────
    def _on_save_params(self) -> None:
        try:
            from . import parameter_io as pio  # type: ignore
        except ImportError:
            import parameter_io as pio  # type: ignore

        default = "hrv_parameters.xlsx"
        if self._ctrl.report is not None and self._ctrl.report.file_path:
            default = f"{self._ctrl.report.file_path.stem}_hrv_params.xlsx"
        path, selected = QFileDialog.getSaveFileName(
            self, "Save HRV parameters", default,
            "Excel (*.xlsx);;CSV (*.csv);;Text (*.txt)",
        )
        if not path:
            return
        p = Path(path)
        if p.suffix == "":
            p = p.with_suffix(".xlsx" if "xlsx" in selected
                              else ".csv" if "csv" in selected else ".txt")
        try:
            state = self._serialize()
            pio.save(p, state)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "HRV 저장 실패", str(exc))
            return
        QMessageBox.information(self, "HRV 저장",
                                f"{p.name} 에 {len(state)} 개 항목 저장.")

    def _on_load_params(self) -> None:
        try:
            from . import parameter_io as pio  # type: ignore
        except ImportError:
            import parameter_io as pio  # type: ignore

        path, _ = QFileDialog.getOpenFileName(
            self, "Load HRV parameters", "",
            "Parameter snapshot (*.xlsx *.csv *.txt);;All files (*.*)",
        )
        if not path:
            return
        try:
            state = pio.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "HRV 로드 실패", str(exc))
            return

        applied, warnings = self._apply_state(state)
        msg = f"{applied} 개 항목 적용됨."
        if warnings:
            msg += f"\n\n건너뜀:\n• " + "\n• ".join(warnings[:20])
        QMessageBox.information(self, "HRV 로드", msg)

    def _serialize(self) -> list[tuple[str, str, str]]:
        """현재 입력값 → (section, key, value) 트리플."""
        rows: list[tuple[str, str, str]] = []
        rows.append(("HRV.Range", "t0_sec", f"{float(self.range_t0.value()):.2f}"))
        rows.append(("HRV.Range", "t1_sec", f"{float(self.range_t1.value()):.2f}"))
        rows.append(("HRV.Range", "lookup_time", _qtime_to_str(self.lookup_time.time())))
        for name, (lo, hi) in self._collect_bands().items():
            rows.append(("HRV.Bands", f"{name}_lo", f"{lo:g}"))
            rows.append(("HRV.Bands", f"{name}_hi", f"{hi:g}"))
        return rows

    def _apply_state(self, state) -> tuple[int, list[str]]:
        applied = 0
        warnings: list[str] = []
        d: dict[tuple[str, str], str] = {}
        for sect, key, val in state:
            d[(str(sect).strip(), str(key).strip())] = "" if val is None else str(val)

        # Range
        for k, sp in (("t0_sec", self.range_t0), ("t1_sec", self.range_t1)):
            v = d.pop(("HRV.Range", k), None)
            if v is None:
                continue
            try:
                sp.setValue(float(v) if v else 0.0); applied += 1
            except ValueError:
                warnings.append(f"HRV.Range.{k}: 파싱 실패 → '{v}'")
        v = d.pop(("HRV.Range", "lookup_time"), None)
        if v is not None:
            t = _hms_to_sec(v)
            if t is not None:
                self.lookup_time.setTime(QTime((t // 3600) % 24, (t % 3600) // 60, t % 60))
                applied += 1

        # Bands
        for name in ("VLF", "LF", "HF"):
            for which in ("lo", "hi"):
                key = f"{name}_{which}"
                v = d.pop(("HRV.Bands", key), None)
                if v is None:
                    continue
                try:
                    sp = self.band_inputs[name][0 if which == "lo" else 1]
                    sp.setValue(float(v) if v else 0.0); applied += 1
                except ValueError:
                    warnings.append(f"HRV.Bands.{key}: 파싱 실패 → '{v}'")

        # 알 수 없는 키 — NIRS 의 다른 섹션은 무시 (HRV 패널이라 Subject/Anchor/Lock/Exercise 미사용)
        ignore_sections = {"Subject", "NIRS_VOT", "HRV", "Anchor", "Lock", "Exercise"}
        for (sect, key) in d:
            if sect in ignore_sections:
                continue
            warnings.append(f"unknown key: [{sect}] {key}")
        return applied, warnings


# ─────────────────────────────────────────────────────────────
#  helpers
# ─────────────────────────────────────────────────────────────
def _fmt_truth(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_num(v) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
        if f != f:
            return "—"
        return f"{f:.3f}".rstrip("0").rstrip(".") or "0"
    except (TypeError, ValueError):
        return str(v)
