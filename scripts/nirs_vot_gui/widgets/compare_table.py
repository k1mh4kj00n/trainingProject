"""Kubios 결과와 우리 결과를 비교하는 테이블 위젯.

우측 Parameter Dock에 들어가 모든 HRV 탭에서 공유된다.
활성 탭에 따라 카테고리(time/freq/nonlinear/all)를 필터링할 수 있다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


CATEGORIES = ["all", "time", "freq", "nonlinear"]
CATEGORY_LABELS = {
    "all": "All",
    "time": "Time-domain",
    "freq": "Frequency-domain",
    "nonlinear": "Nonlinear",
}


class CompareTable(QWidget):
    """Item / Ours / Kubios / err 비교 테이블."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all_rows: list[tuple[str, str, float, float]] = []  # (cat, name, ours, kubios)
        self._current_cat = "all"
        self._last_controller = None  # update_results 가 setter — export 시 메타 사용

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        title = QLabel("Parameters & Results")
        title.setProperty("role", "title")
        root.addWidget(title)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Category:"))
        self.cat_combo = QComboBox()
        for c in CATEGORIES:
            self.cat_combo.addItem(CATEGORY_LABELS[c], c)
        self.cat_combo.currentIndexChanged.connect(self._on_cat_changed)
        ctrl.addWidget(self.cat_combo, stretch=1)
        root.addLayout(ctrl)

        self.session_label = QLabel("— 분석 결과 없음 —")
        self.session_label.setStyleSheet("color: #666666;")
        self.session_label.setWordWrap(True)
        root.addWidget(self.session_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Item", "Ours", "Kubios", "err %"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        root.addWidget(self.table, stretch=1)

        # ── Export 버튼 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.export_btn = QPushButton("Export HRV results…")
        self.export_btn.setToolTip(
            "현재 HRV 분석 결과(td/fd/nl 33 metrics + Kubios 비교) 를 xlsx/csv/txt 로 저장.\n"
            "메타: 파일·beats·sample·range·measurement date 포함."
        )
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export)
        btn_row.addWidget(self.export_btn)
        root.addLayout(btn_row)

    # ──────────────────────────────────────────
    def set_category(self, cat: str) -> None:
        if cat in CATEGORIES:
            self._current_cat = cat
            idx = CATEGORIES.index(cat)
            self.cat_combo.blockSignals(True)
            self.cat_combo.setCurrentIndex(idx)
            self.cat_combo.blockSignals(False)
            self._render_filtered()

    def update_results(self, controller) -> None:
        """controller (HrvController)에서 td/fd/nl + Kubios 메트릭을 가져와 갱신."""
        self._last_controller = controller
        if not controller.has_results or controller.report is None:
            self.clear()
            return

        td = controller.td
        fd = controller.fd
        nl = controller.nl
        kubios = controller.report.metrics

        def k(name: str) -> float:
            return float(kubios.get(name, float("nan")))

        rows: list[tuple[str, str, float, float]] = [
            # Time-domain
            ("time", "Mean RR (ms)",         td.mean_rr_ms,           k("Mean RR  (ms)")),
            ("time", "SDNN (ms)",            td.sdnn_ms,              k("SDNN (ms)")),
            ("time", "Mean HR (bpm)",        td.mean_hr_bpm,          k("Mean HR (beats/min)")),
            ("time", "SD HR (bpm)",          td.sd_hr_bpm,            k("SD HR (beats/min)")),
            ("time", "Min HR (bpm)",         td.min_hr_bpm,           k("Min HR (beats/min)")),
            ("time", "Max HR (bpm)",         td.max_hr_bpm,           k("Max HR (beats/min)")),
            ("time", "RMSSD (ms)",           td.rmssd_ms,             k("RMSSD (ms)")),
            ("time", "NN50",                 td.nn50_count,           k("NNxx (beats)")),
            ("time", "pNN50 (%)",            td.pnn50_pct,            k("pNNxx (%)")),
            ("time", "HRV tri index",        td.hrv_triangular_index, k("RR tri index")),
            ("time", "TINN (ms)",            td.tinn_ms,              k("TINN (ms)")),
            ("time", "Stress index",         td.stress_index,         k("Stress index")),
            ("time", "DC (ms)",              td.dc_ms,                k("DC (ms)")),
            ("time", "AC (ms)",              td.ac_ms,                k("AC (ms)")),
            ("time", "DCmod (ms)",           td.dc_mod_ms,            k("DCmod (ms)")),
            ("time", "ACmod (ms)",           td.ac_mod_ms,            k("ACmod (ms)")),
            # Frequency-domain (FFT)
            ("freq", "VLF peak (Hz)",        fd.vlf.peak_hz,          k("VLF (Hz) (FFT)")),
            ("freq", "LF peak (Hz)",         fd.lf.peak_hz,           k("LF (Hz) (FFT)")),
            ("freq", "HF peak (Hz)",         fd.hf.peak_hz,           k("HF (Hz) (FFT)")),
            ("freq", "VLF power (ms²)",      fd.vlf.power_ms2,        k("VLF (ms^2) (FFT)")),
            ("freq", "LF power (ms²)",       fd.lf.power_ms2,         k("LF (ms^2) (FFT)")),
            ("freq", "HF power (ms²)",       fd.hf.power_ms2,         k("HF (ms^2) (FFT)")),
            ("freq", "VLF (%)",              fd.vlf.power_pct,        k("VLF (%) (FFT)")),
            ("freq", "LF (%)",               fd.lf.power_pct,         k("LF (%) (FFT)")),
            ("freq", "HF (%)",               fd.hf.power_pct,         k("HF (%) (FFT)")),
            ("freq", "LF (n.u.)",            fd.lf.power_nu,          k("LF (n.u.) (FFT)")),
            ("freq", "HF (n.u.)",            fd.hf.power_nu,          k("HF (n.u.) (FFT)")),
            ("freq", "Total power (ms²)",    fd.total_power_ms2,      k("Total power (ms^2) (FFT)")),
            ("freq", "LF/HF ratio",          fd.lf_hf_ratio,          k("LF/HF ratio (FFT)")),
            # Nonlinear
            ("nonlinear", "SD1 (ms)",        nl.sd1_ms,               k("SD1 (ms)")),
            ("nonlinear", "SD2 (ms)",        nl.sd2_ms,               k("SD2 (ms)")),
            ("nonlinear", "SD2/SD1",         nl.sd2_sd1,              k("SD2/SD1")),
            ("nonlinear", "ApEn",            nl.apen,                 k("Approximate entropy (ApEn)")),
            ("nonlinear", "SampEn",          nl.sampen,               k("Sample entropy (SampEn)")),
            ("nonlinear", "DFA α1",          nl.dfa_alpha1,           k("DFA alpha1")),
            ("nonlinear", "DFA α2",          nl.dfa_alpha2,           k("DFA alpha2")),
        ]
        self._all_rows = rows

        rep = controller.report
        n = len(rep.rr_intervals_s)
        limits = rep.sample_info.get("limits", "?")
        path_name = controller.path.name if controller.path else "—"
        self.session_label.setText(f"{path_name}  ·  {n} beats  ·  sample {limits}")

        self.export_btn.setEnabled(True)
        self._render_filtered()

    def clear(self) -> None:
        self._all_rows = []
        self.session_label.setText("— 분석 결과 없음 —")
        self.table.setRowCount(0)
        self.export_btn.setEnabled(False)

    # ──────────────────────────────────────────
    def _on_cat_changed(self, _i: int) -> None:
        self._current_cat = self.cat_combo.currentData() or "all"
        self._render_filtered()

    def _render_filtered(self) -> None:
        rows = (
            self._all_rows if self._current_cat == "all"
            else [r for r in self._all_rows if r[0] == self._current_cat]
        )
        self.table.setRowCount(len(rows))
        for r, (_cat, name, ours, truth) in enumerate(rows):
            try:
                err = abs(ours - truth) / max(abs(truth), 1e-9) * 100 if truth != 0 \
                      else (0 if ours == 0 else float("inf"))
            except Exception:
                err = float("nan")

            err_text = f"{err:.2f}" if np.isfinite(err) else "—"
            if np.isfinite(err):
                if err < 3:
                    color = QColor("#2E7D32")  # green
                    sym = "✓"
                elif err < 15:
                    color = QColor("#FFA000")  # amber
                    sym = "≈"
                else:
                    color = QColor("#C62828")  # red
                    sym = "✗"
            else:
                color = QColor("#888888")
                sym = "—"

            self.table.setItem(r, 0, QTableWidgetItem(name))
            self.table.setItem(r, 1, _val_item(ours))
            self.table.setItem(r, 2, _val_item(truth))
            err_item = QTableWidgetItem(f"{sym} {err_text}")
            err_item.setForeground(color)
            err_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 3, err_item)


def _val_item(v: float) -> QTableWidgetItem:
    if not np.isfinite(v):
        it = QTableWidgetItem("—")
    else:
        it = QTableWidgetItem(f"{v:,.4f}")
    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return it


# ─────────────────────────────────────────────────────────────
#  Export — xlsx / csv / txt 디스패처
# ─────────────────────────────────────────────────────────────
def _attach_export_methods():
    """CompareTable 에 export 관련 메서드를 붙임 (파일 길이 줄이기)."""

    def _on_export(self) -> None:
        if not self._all_rows or self._last_controller is None:
            return
        ctrl = self._last_controller
        rep = ctrl.report
        if rep is None:
            return
        default = (
            f"{rep.file_path.stem}_hrv_results.xlsx" if rep.file_path
            else "hrv_results.xlsx"
        )
        path, selected = QFileDialog.getSaveFileName(
            self, "Export HRV results", default,
            "Excel (*.xlsx);;CSV (*.csv);;Text (*.txt)",
        )
        if not path:
            return
        p = Path(path)
        if p.suffix == "":
            p = p.with_suffix(".xlsx" if "xlsx" in selected
                              else ".csv" if "csv" in selected else ".txt")

        ext = p.suffix.lower()
        try:
            if ext in (".xlsx", ".xls"):
                _write_hrv_xlsx(p, ctrl, self._all_rows)
            elif ext == ".txt":
                _write_hrv_txt(p, ctrl, self._all_rows)
            else:
                _write_hrv_csv(p, ctrl, self._all_rows)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export 실패", str(exc))
            return
        QMessageBox.information(self, "Export", f"저장 완료:\n{p}")

    CompareTable._on_export = _on_export


def _hrv_meta_lines(ctrl) -> list[str]:
    """HRV export 의 메타 헤더 (# 코멘트 7~8 줄)."""
    rep = ctrl.report
    n = len(rep.rr_intervals_s)
    limits = rep.sample_info.get("limits", "?")
    meas = rep.meta.get("Measurement date", "—")
    fname = rep.file_path.name if rep.file_path else "—"
    rng = ""
    if ctrl.range_abs is not None:
        t0, t1 = ctrl.range_abs
        rng = f"{t0:.2f} → {t1:.2f} (s, custom)"
    else:
        rng = f"{rep.rr_times_s[0]:.2f} → {rep.rr_times_s[-1]:.2f} (s, full)"
    return [
        f"# File: {fname}",
        f"# Measurement date: {meas}",
        f"# Sample limits: {limits}",
        f"# Beats total: {n}",
        f"# Analysis range: {rng}",
        f"# Bands (Hz): VLF {ctrl.fd.vlf.lo:g}-{ctrl.fd.vlf.hi:g} · "
        f"LF {ctrl.fd.lf.lo:g}-{ctrl.fd.lf.hi:g} · "
        f"HF {ctrl.fd.hf.lo:g}-{ctrl.fd.hf.hi:g}",
    ]


def _hrv_data_rows(all_rows) -> list[tuple[str, str, str, str, str]]:
    """(category, item, ours, kubios, err%) 5-튜플 리스트."""
    out = []
    for cat, name, ours, truth in all_rows:
        try:
            err = (abs(ours - truth) / max(abs(truth), 1e-9) * 100
                   if truth != 0 else (0.0 if ours == 0 else float("inf")))
        except Exception:  # noqa: BLE001
            err = float("nan")
        ours_s = "" if not np.isfinite(ours) else f"{ours:.4f}"
        truth_s = "" if not np.isfinite(truth) else f"{truth:.4f}"
        err_s = "" if not np.isfinite(err) else f"{err:.2f}"
        out.append((cat, name, ours_s, truth_s, err_s))
    return out


def _write_hrv_csv(path: Path, ctrl, all_rows) -> None:
    import csv
    meta = _hrv_meta_lines(ctrl)
    rows = _hrv_data_rows(all_rows)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        for line in meta:
            f.write(line + "\n")
        f.write("#\n")
        w = csv.writer(f)
        w.writerow(["Category", "Item", "Ours", "Kubios", "err %"])
        for r in rows:
            w.writerow(r)


def _write_hrv_xlsx(path: Path, ctrl, all_rows) -> None:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    meta = _hrv_meta_lines(ctrl)
    rows = _hrv_data_rows(all_rows)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "HRV Results"

    bold = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="E5E7EB")
    cat_fills = {
        "time":      PatternFill("solid", fgColor="DBEAFE"),
        "freq":      PatternFill("solid", fgColor="FEF3C7"),
        "nonlinear": PatternFill("solid", fgColor="EDE9FE"),
    }

    for line in meta:
        ws.append([line])
        ws.cell(row=ws.max_row, column=1).font = bold
    ws.append([])
    ws.append(["Category", "Item", "Ours", "Kubios", "err %"])
    for c in range(1, 6):
        cell = ws.cell(row=ws.max_row, column=c)
        cell.font = bold
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center")

    for cat, name, ours, kub, err in rows:
        ws.append([cat, name, _xnum(ours), _xnum(kub), _xnum(err)])
        r = ws.max_row
        # 카테고리 색상
        if cat in cat_fills:
            ws.cell(row=r, column=1).fill = cat_fills[cat]
        for c in (3, 4, 5):
            ws.cell(row=r, column=c).alignment = Alignment(horizontal="right")
        # err 색상
        try:
            e = float(err) if err else None
            if e is not None and np.isfinite(e):
                if e < 3:
                    color = "2E7D32"
                elif e < 15:
                    color = "FFA000"
                else:
                    color = "C62828"
                ws.cell(row=r, column=5).font = Font(bold=True, color=color)
        except (TypeError, ValueError):
            pass

    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 10
    ws.freeze_panes = "A4"  # 메타 위 + 헤더 고정
    wb.save(path)


def _write_hrv_txt(path: Path, ctrl, all_rows) -> None:
    """단일 HRV 분석 — fixed-width 사람 읽기용."""
    meta = _hrv_meta_lines(ctrl)
    rows = _hrv_data_rows(all_rows)
    widths = (10, 24, 12, 12, 10)
    header = ("Category", "Item", "Ours", "Kubios", "err %")

    def _row_str(values):
        return "  ".join(
            (str(v).ljust(widths[i]) if i <= 1 else str(v).rjust(widths[i]))
            for i, v in enumerate(values)
        )

    lines = list(meta) + ["#", ""]
    lines.append(_row_str(header))
    lines.append("─" * (sum(widths) + 2 * (len(widths) - 1)))
    for r in rows:
        lines.append(_row_str(r))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _xnum(s):
    if s == "" or s is None:
        return ""
    try:
        return float(s)
    except (TypeError, ValueError):
        return str(s)


_attach_export_methods()
