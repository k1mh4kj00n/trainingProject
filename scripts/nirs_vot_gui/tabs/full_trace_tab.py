"""NIRS-VOT 전체 시계열 뷰어 — 구간 잡기용 참고 그래프.

용도:
    측정 전체(보통 1~2시간) 의 SmO2 곡선을 한 눈에 보고, 어디가 baseline/occlusion/
    recovery 구간인지 시각적으로 파악. 사용자가 ParameterPanel 의 NIRS_VOT timepoint
    또는 그래프 드래그로 구간을 정확히 잡을 때 참고.

표시 요소:
    - 전체 SmO2_smooth 곡선 (raw 는 노이즈 많아 생략, 옵션화 가능)
    - 현재 ``dynamic_anchors`` 의 Baseline / Recovery2 anchor 영역 음영
    - inflate / deflate 시점 세로선
    - 운동 구간 (Ex1 / Ex2) 음영 (있을 경우)
    - 시간 마커 (HH:MM:SS)

NirsVotTab.loaded 와 동기화 — measurement_loaded / measurement_cleared 시그널을 받아 갱신.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.dates as mdates
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..style import Color
from ..widgets.mpl_canvas import MplCanvas


# 동적 timepoint 음영용 팔레트 (matplotlib 'tab10' 베이스, 가독성 조정)
_SESSION_PALETTE: tuple[str, ...] = (
    "#3B82F6",  # 파랑 (Baseline)
    "#F59E0B",  # 주황 (Recovery2)
    "#8B5CF6",  # 보라
    "#10B981",  # 청록
    "#EC4899",  # 핑크
    "#F97316",  # 짙은 주황
    "#0EA5E9",  # 밝은 파랑
    "#84CC16",  # 라임
)


class FullTraceTab(QWidget):
    """전체 SmO2 시계열 + anchor 영역 표시."""

    def __init__(self, nirs_tab, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._nirs_tab = nirs_tab  # NirsVotTab 참조 (loaded dict 접근용)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── 상단 컨트롤 ──
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)
        ctrl.addWidget(QLabel("Condition:"))
        self.condition_combo = QComboBox()
        self.condition_combo.setMinimumWidth(120)
        self.condition_combo.currentTextChanged.connect(self.refresh)
        ctrl.addWidget(self.condition_combo)

        ctrl.addWidget(QLabel("|"))

        self.show_raw = QCheckBox("Raw")
        self.show_raw.setChecked(False)
        self.show_raw.toggled.connect(self.refresh)
        ctrl.addWidget(self.show_raw)

        self.show_anchors = QCheckBox("NIRS_VOT 구간 음영")
        self.show_anchors.setChecked(True)
        self.show_anchors.toggled.connect(self.refresh)
        ctrl.addWidget(self.show_anchors)

        self.show_exercise = QCheckBox("운동 구간 음영")
        self.show_exercise.setChecked(True)
        self.show_exercise.toggled.connect(self.refresh)
        ctrl.addWidget(self.show_exercise)

        self.show_thb = QCheckBox("THb")
        self.show_thb.setChecked(False)
        self.show_thb.toggled.connect(self.refresh)
        ctrl.addWidget(self.show_thb)

        ctrl.addStretch()
        root.addLayout(ctrl)

        # ── 안내 라벨 ──
        self.info = QLabel(
            "전체 측정 구간을 보고 NIRS_VOT 구간을 잡는 데 참고하세요. "
            "구간 수정은 [Session Parameters] 또는 [분석] 탭의 그래프에서."
        )
        self.info.setStyleSheet(f"color: {Color.TEXT_MUTED}; padding: 2px 4px;")
        self.info.setWordWrap(True)
        root.addWidget(self.info)

        # ── 그래프 ──
        self.canvas = MplCanvas(figsize=(12, 5.5))
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.canvas, stretch=1)

        # 처음 + condition 변경 시 자동 refresh
        nirs_tab.measurement_loaded.connect(self._on_measurement_loaded)
        nirs_tab.measurement_cleared.connect(self._on_cleared)
        # NirsVotTab 메인 콤보가 바뀌면 본 탭의 콤보도 따라가게 (편의)
        nirs_tab.condition_combo.currentTextChanged.connect(self._sync_combo_from_main)

    # ──────────────────────────────────────────
    def showEvent(self, event):  # noqa: N802 (Qt naming)
        """탭이 visible 로 전환될 때마다 refresh 강제.

        invisible 상태에서 draw 된 figure 는 matplotlib constrained_layout 이 사이즈를
        0 으로 잡아 빈 화면처럼 보일 수 있다. 사용자가 [전체 데이터] 탭으로 진입할 때
        실제 위젯 크기 기준으로 다시 그린다.
        """
        super().showEvent(event)
        self.refresh()

    # ──────────────────────────────────────────
    def _on_measurement_loaded(self, condition: str, _lf) -> None:
        """새 condition 이 NirsVotTab.loaded 에 추가되면 콤보 동기화.

        ⚠ invisible 상태(분석 탭이 활성)에서 refresh 하면 matplotlib constrained_layout
        이 0 사이즈로 layout cache 를 잡아 사용자가 [전체 데이터] 탭으로 전환해도
        빈 화면처럼 보인다. 따라서 invisible 일 때는 콤보 동기화만 하고 draw 는 보류 →
        visible 로 전환될 때 (showEvent / subtab changed) 처음 그린다.
        """
        self._sync_combo_options()
        # 처음이면 현재 condition 자동 선택 (콤보 변경 시그널이 다시 들어와 currentText 가 바뀌어도
        # blockSignals 안에서 자동 첫 항목이 선택되므로 보통 따로 호출 불필요)
        if self.condition_combo.currentText() == "" and condition:
            self.condition_combo.setCurrentText(condition)

        if self.isVisible():
            self.refresh()

    def _on_cleared(self) -> None:
        self.condition_combo.blockSignals(True)
        self.condition_combo.clear()
        self.condition_combo.blockSignals(False)
        self.canvas.figure.clear()
        self.canvas.canvas.draw_idle()

    def _sync_combo_options(self) -> None:
        loaded = self._nirs_tab.loaded
        current = self.condition_combo.currentText()
        self.condition_combo.blockSignals(True)
        self.condition_combo.clear()
        if loaded:
            order = {"NOR": 0, "HYPO": 1, "HYPER": 2}
            sorted_conds = sorted(loaded.keys(), key=lambda c: (order.get(c, 999), c))
            self.condition_combo.addItems(sorted_conds)
            if current in sorted_conds:
                self.condition_combo.setCurrentText(current)
        self.condition_combo.blockSignals(False)

    def _sync_combo_from_main(self, condition: str) -> None:
        """NirsVotTab 의 메인 콤보 변경 시 본 탭 콤보도 같은 값으로."""
        if not condition:
            return
        if self.condition_combo.findText(condition) < 0:
            self._sync_combo_options()
        # invisible 상태이면 currentTextChanged 시그널이 와도 refresh 가 무거우므로 차단
        was_visible = self.isVisible()
        self.condition_combo.blockSignals(not was_visible)
        if self.condition_combo.currentText() != condition:
            self.condition_combo.setCurrentText(condition)
        self.condition_combo.blockSignals(False)

    # ──────────────────────────────────────────
    def refresh(self) -> None:
        """현재 선택된 condition 의 전체 시계열 + anchor 그림.

        invisible 상태에서 호출되면 matplotlib constrained_layout 이 axes 를 0 사이즈로
        잡아 visible 전환 후에도 cached 빈 화면이 그려진다. 따라서 invisible 이면 skip.
        """
        if not self.isVisible():
            return  # showEvent 가 visible 전환 시 다시 호출함
        cond = self.condition_combo.currentText()
        loaded = self._nirs_tab.loaded
        fig = self.canvas.figure
        fig.clear()

        if not cond or cond not in loaded:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "(no data)", ha="center", va="center",
                    transform=ax.transAxes, color="#888888", fontsize=12)
            ax.set_xticks([]); ax.set_yticks([])
            self.canvas.canvas.draw_idle()
            return

        lf = loaded[cond]
        df = lf.smoothed
        if df is None or df.empty:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "(empty)", ha="center", va="center",
                    transform=ax.transAxes, color="#888888")
            self.canvas.canvas.draw_idle()
            return

        ax = fig.add_subplot(111)
        tz = df["datetime"].iloc[0].tz

        anchor_date = df["datetime"].iloc[0]

        # ── (1) NIRS_VOT 구간 음영 (3 단계 분할) ──
        # 한 세션 = (start ~ inflate) Baseline 측정 + (inflate ~ deflate) Occlusion +
        #          (deflate ~ end) Reperfusion. 3 부분을 다른 색상·진하기로 구분.
        # v0.7: timepoint 개수가 동적 — 색상 팔레트로 자동 부여.
        if self.show_anchors.isChecked():
            session_label_added: set[str] = set()
            session_names = list(lf.dynamic_anchors.keys())
            palette = _SESSION_PALETTE
            for i, sess_name in enumerate(session_names):
                sess_color = palette[i % len(palette)]
                anc = lf.dynamic_anchors.get(sess_name)
                if anc is None:
                    continue
                try:
                    t_s = _to_ts(anchor_date, anc.start)
                    t_i = _to_ts(anchor_date, anc.inflate)
                    t_d = _to_ts(anchor_date, anc.deflate)
                    t_e = _to_ts(anchor_date, anc.end)
                except Exception:  # noqa: BLE001
                    continue

                # (a) Baseline 측정 영역 (start ~ inflate): 옅은 회색
                ax.axvspan(t_s, t_i, color="#94A3B8", alpha=0.18,
                           label="Baseline (1분)" if "Baseline (1분)" not in session_label_added else None)
                session_label_added.add("Baseline (1분)")
                # (b) Occlusion 영역 (inflate ~ deflate): 세션 색상으로 진하게
                ax.axvspan(t_i, t_d, color=sess_color, alpha=0.30,
                           label=f"{sess_name} occlusion")
                # (c) Reperfusion 영역 (deflate ~ end): 옅은 초록
                ax.axvspan(t_d, t_e, color="#10B981", alpha=0.16,
                           label="Reperfusion (3분)" if "Reperfusion (3분)" not in session_label_added else None)
                session_label_added.add("Reperfusion (3분)")

                # (d) 시점 세로 점선 + 짧은 라벨
                for t, lab in [(t_s, "start"), (t_i, "inflate"),
                                (t_d, "deflate"), (t_e, "end")]:
                    ax.axvline(t, color=sess_color, linestyle=":", linewidth=0.9, alpha=0.7)
                    ax.text(t, 1.0, lab, rotation=90, ha="right", va="top",
                            fontsize=7, color=sess_color,
                            transform=ax.get_xaxis_transform())

        # ── (2) 운동 구간 음영 (Ex1 / Ex2) ──
        if self.show_exercise.isChecked() and lf.config is not None:
            ex = lf.config.exercise()
            for ex_key, color in [("Ex1", "#EF4444"), ("Ex2", "#DC2626")]:
                win = ex.get(ex_key)
                if win is None:
                    continue
                try:
                    es = _to_ts(anchor_date, win.start)
                    ee = _to_ts(anchor_date, win.end)
                    ax.axvspan(es, ee, color=color, alpha=0.10, label=ex_key)
                except Exception:  # noqa: BLE001
                    pass

        # ── (3) 시계열 라인 ──
        if self.show_raw.isChecked():
            ax.plot(df["datetime"], df["SmO2_raw"],
                    color=Color.SMO2_RAW, alpha=0.4, linewidth=0.8, label="Raw SmO2")
        ax.plot(df["datetime"], df["SmO2_smooth"],
                color=Color.SMO2_SMOOTH, linewidth=1.4, label="Smoothed SmO2")

        # THb (옵션)
        if self.show_thb.isChecked() and "THb" in df.columns:
            ax2 = ax.twinx()
            ax2.plot(df["datetime"], df["THb"], color="#9333EA",
                     alpha=0.6, linewidth=0.9, label="THb")
            ax2.set_ylabel("THb", color="#9333EA")
            ax2.tick_params(axis="y", colors="#9333EA")

        # ── (4) 라벨 / 포맷 ──
        cfg = lf.config
        subj = (cfg.subject_info.get("Name") if cfg and cfg.subject_info else "") or ""
        n = len(df)
        t0, t1 = df["datetime"].iloc[0], df["datetime"].iloc[-1]
        dur = (t1 - t0).total_seconds() / 60.0

        ax.set_title(
            f"전체 시계열  ·  {subj}  ·  {cond}    "
            f"({t0.strftime('%H:%M:%S')} → {t1.strftime('%H:%M:%S')}, {dur:.1f}분, {n} samples)",
            fontsize=10, loc="left",
        )
        ax.set_xlabel("Time")
        ax.set_ylabel("SmO2 (%)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S", tz=tz))
        ax.grid(True, alpha=0.25)
        # 중복 라벨 제거 후 legend
        handles, labels = ax.get_legend_handles_labels()
        seen = set()
        uniq = []
        for h, l in zip(handles, labels):
            if l not in seen:
                seen.add(l); uniq.append((h, l))
        if uniq:
            ax.legend([h for h, _ in uniq], [l for _, l in uniq],
                      loc="upper right", fontsize=8, ncol=2, framealpha=0.85)
        fig.autofmt_xdate()
        self.canvas.canvas.draw_idle()


import datetime as _dt


def _t2s(t) -> str:
    if t is None:
        return "00:00:00"
    return f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}"


def _to_ts(anchor_date, time_value) -> "pd.Timestamp":
    """``datetime.time`` 또는 ``'HH:MM:SS'`` → 같은 날짜의 tz-aware ``pd.Timestamp``.

    ``anchor_date`` (전체 시계열의 첫 timestamp) 의 ``date()`` 와 ``tz`` 를 빌려 사용.
    외부 모듈 (``nirs_vot.metrics._parse_clock``) 에 의존하지 않아 import 환경 무관.
    """
    if time_value is None:
        raise ValueError("time_value is None")

    if hasattr(time_value, "hour") and hasattr(time_value, "minute"):
        t = _dt.time(int(time_value.hour), int(time_value.minute),
                     int(getattr(time_value, "second", 0) or 0))
    else:
        s = str(time_value).strip()
        parts = [int(p) for p in s.split(":")]
        if len(parts) == 2:
            t = _dt.time(parts[0], parts[1])
        elif len(parts) == 3:
            t = _dt.time(parts[0], parts[1], parts[2])
        else:
            raise ValueError(f"unrecognized time format: {time_value!r}")

    py_dt = _dt.datetime.combine(anchor_date.date(), t)
    ts = pd.Timestamp(py_dt)
    if anchor_date.tz is not None:
        ts = ts.tz_localize(anchor_date.tz)
    return ts
