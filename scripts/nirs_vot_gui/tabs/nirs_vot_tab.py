"""NIRS-VOT 메인 분석 탭.

상단 컨트롤: Condition / Session / Analyze / Close
본문: matplotlib 그래프

DataBrowser 에서 세션을 더블클릭하거나 Analyze 버튼을 누르면 분석 실행.
데이터 로드 버튼(``Open data file…`` / ``Open folder…``) 은 좌측 Sessions 패널 헤더에 위치.

v0.6.4 변경:
- 본문 상단의 ``Open data file…`` / ``Open folder…`` 버튼을 좌측 ``DataBrowser`` 헤더로 이동.
  본문은 그래프 시야 확보를 위해 Condition / Session / Analyze / Close 만 남김.
- ``_on_open_file`` / ``_on_open_folder`` 메서드는 그대로 유지 — 좌측 ``DataBrowser`` 시그널이
  app.py 와이어링을 통해 호출.

v0.6.3 변경:
- 시작 시 자동 로드/하드코딩 환자명 흔적 모두 제거. 사용자가 직접 로드하기 전까지 빈 상태.
- ParameterPanel 은 NirsVotTab 본문이 아닌 별도 도크에서 관리됨 (app.py 에서 wiring).
- 폴더 단위 로드는 환자명 패턴(`이찬민_*`) 의존을 끊고 임의 폴더의 `*_Calf.{ext}` 모두 처리.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication as _QApp
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from ...config_loader import (  # type: ignore
        SessionConfig,
        TimeWindow,
        find_config_for_calf,
        load_session_config,
    )
    from ...nirs_vot.anchors import (  # type: ignore
        Anchor,
        SESSION_ANCHORS,
        anchor_from_window,
        anchors_from_session_config,
        auto_window_from_signal,
        get_anchors,
    )
    from ...nirs_vot.loader import is_calf_timeseries, load_calf  # type: ignore
    from ...nirs_vot.metrics import compute_metrics, MetricsResult  # type: ignore
    from ...nirs_vot.preprocess import preprocess  # type: ignore
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from config_loader import (  # type: ignore
        SessionConfig,
        TimeWindow,
        find_config_for_calf,
        load_session_config,
    )
    from nirs_vot.anchors import (  # type: ignore
        Anchor,
        SESSION_ANCHORS,
        anchor_from_window,
        anchors_from_session_config,
        auto_window_from_signal,
        get_anchors,
    )
    from nirs_vot.loader import is_calf_timeseries, load_calf  # type: ignore
    from nirs_vot.metrics import compute_metrics, MetricsResult  # type: ignore
    from nirs_vot.preprocess import preprocess  # type: ignore

from ..style import Color
from ..widgets.draggable_overlay import DraggableOverlay
from ..widgets.mpl_canvas import MplCanvas


SESSIONS = ("Baseline", "Recovery2")  # 데이터 로드 전 default — 로드 후 cfg.nirs_timepoints() 로 동적 갱신
CONDITIONS = ("NOR", "HYPO", "HYPER")
_CALF_EXTS = (".csv", ".txt", ".xlsx")

# 시계열 + 설정 파일 다이얼로그 필터
_FILE_FILTER = (
    "NIRS Calf data (*.txt *.csv *.xlsx);;"
    "All measurement files (*.txt *.csv *.xlsx);;"
    "All files (*.*)"
)


def _condition_from_stem(stem: str) -> Optional[str]:
    """파일명에 포함된 condition 토큰 추출 (HYPER/HYPO/NOR)."""
    for cond in CONDITIONS:
        if cond in stem:
            return cond
    return None


@dataclass
class LoadedFile:
    """한 condition 의 시계열 + 설정 페어."""
    path: Path                              # _Calf 시계열 경로
    raw: pd.DataFrame
    smoothed: pd.DataFrame
    config: Optional[SessionConfig] = None  # 설정 xlsx (없을 수 있음)
    dynamic_anchors: dict[str, Anchor] = field(default_factory=dict)  # session → Anchor
    # 사용자가 그래프에서 드래그로 직접 지정한 override (session → {key: value}).
    # key ∈ {'baseline', 'min_time', 'peak_time'}.
    overrides: dict[str, dict] = field(default_factory=dict)


class NirsVotTab(QWidget):
    """NIRS-VOT 분석 탭. 데이터 로드 + 세션 선택 + 분석 실행."""

    status_message = Signal(str)
    result_ready = Signal(object, object)              # MetricsResult, preprocessed df
    measurement_loaded = Signal(str, object)           # condition, LoadedFile
    measurement_cleared = Signal()                     # 모든 데이터 비움
    anchor_dragged = Signal(str, str, object)          # (kind, name, value): 드래그 종료
    anchor_dragging = Signal(str, str, object)         # (kind, name, value): 드래그 중 (실시간)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.loaded: dict[str, LoadedFile] = {}
        self._last_result: Optional[MetricsResult] = None
        self._overlay: Optional[DraggableOverlay] = None  # _render 에서 새로 생성
        # 재사용되는 artist 들 (setup 1회, update 마다 데이터만 갱신)
        self._ax = None
        self._raw_line = None
        self._smooth_line = None
        self._fill_deficit = None
        self._fill_hyperemia = None
        self._text_labels: dict[str, object] = {}
        self._fig_legend = None  # figure 우상단 외부 legend
        # 외부 callback (드래그 motion 시 ParameterPanel 동기화)
        self.on_drag_motion_external = None  # type: ignore

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # ─── 상단 컨트롤 ──────────────────────────────
        # NOTE (v0.6.4): Open data file / Open folder 버튼은 좌측 Sessions 패널 헤더로 이동.
        # 여기는 분석 컨텍스트(Condition / Session / Analyze / Close) 만 남긴다.
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        ctrl.addWidget(QLabel("Condition:"))
        self.condition_combo = QComboBox()
        self.condition_combo.addItems(list(CONDITIONS))
        ctrl.addWidget(self.condition_combo)

        ctrl.addWidget(QLabel("Session:"))
        self.session_combo = QComboBox()
        self.session_combo.addItems(list(SESSIONS))
        ctrl.addWidget(self.session_combo)
        # Condition 변경 시 session_combo 도 해당 cfg 의 timepoint 들로 갱신
        self.condition_combo.currentTextChanged.connect(self._sync_session_combo)

        self.analyze_btn = QPushButton("▶  Analyze")
        self.analyze_btn.setStyleSheet(
            f"background-color: {Color.ACCENT}; color: white; font-weight: bold;"
            " padding: 6px 18px;"
        )
        self.analyze_btn.clicked.connect(lambda: self.analyze_current())
        ctrl.addWidget(self.analyze_btn)

        ctrl.addStretch()

        self.clear_btn = QPushButton("🗙  Close")
        self.clear_btn.setToolTip("로드된 데이터·결과 모두 제거")
        self.clear_btn.clicked.connect(self.clear_all)
        ctrl.addWidget(self.clear_btn)

        self.zoom_reset_btn = QPushButton("⟲  Zoom Reset")
        self.zoom_reset_btn.setToolTip(
            "그래프 확대/축소 초기화 (단축키: 더블클릭 또는 R 키)"
        )
        self.zoom_reset_btn.clicked.connect(self._reset_zoom)
        ctrl.addWidget(self.zoom_reset_btn)

        root.addLayout(ctrl)

        # ─── 상태 표시줄 ────────────────────────────
        self.info_label = QLabel(
            "데이터를 로드해주세요. 좌측 Sessions 패널 상단의 [📂 Open data file…] / [📁 Open folder…] 버튼을 사용하세요.   "
            "│ 줌: 마우스 휠   │ 박스 줌: 우클릭 드래그   │ 리셋: 더블클릭 또는 R 키"
        )
        self.info_label.setStyleSheet(f"color: {Color.TEXT_MUTED}; padding: 4px;")
        root.addWidget(self.info_label)

        # ─── 그래프 ───────────────────────────────
        self.canvas = MplCanvas(figsize=(12, 5.5))
        root.addWidget(self.canvas, stretch=1)

    # ──────────────────────────────────────────────
    #  파일 로드
    # ──────────────────────────────────────────────
    def _load_pair(self, calf_path: Path) -> LoadedFile:
        """시계열 1개 + (옆에 있으면) 설정 xlsx 1개 로드. 동적 anchor 산출.

        cfg 가 없으면 SmO2 신호로부터 occlusion 구간을 자동 추정해 합성 SessionConfig 를
        만든다 (사용자가 ParameterPanel 에서 그대로 보고 수정 가능).
        """
        raw = load_calf(calf_path)
        sm = preprocess(raw)

        cfg: Optional[SessionConfig] = None
        dyn: dict[str, Anchor] = {}
        cfg_path = find_config_for_calf(calf_path)
        if cfg_path is not None:
            try:
                cfg = load_session_config(cfg_path)
                dyn = anchors_from_session_config(cfg)
            except Exception as exc:  # noqa: BLE001
                self.status_message.emit(f"설정 파일 파싱 실패 ({cfg_path.name}): {exc}")

        if cfg is None:
            cfg, dyn = self._build_template_config(calf_path, sm)

        return LoadedFile(path=calf_path, raw=raw, smoothed=sm, config=cfg, dynamic_anchors=dyn)

    def _build_template_config(
        self, calf_path: Path, sm
    ) -> tuple[Optional[SessionConfig], dict[str, Anchor]]:
        """cfg 가 없을 때 SmO2 신호 기반 자동 anchor + 합성 SessionConfig 생성."""
        try:
            win = auto_window_from_signal(sm)
        except Exception as exc:  # noqa: BLE001
            self.status_message.emit(f"자동 anchor 추정 실패 ({calf_path.name}): {exc}")
            return None, {}
        if win is None:
            self.status_message.emit(
                f"자동 anchor 추정 못 함 (SmO2 dip 부족): {calf_path.name}"
            )
            return None, {}
        inflate_t, deflate_t = win
        cond = _condition_from_stem(calf_path.stem) or "?"
        try:
            from config_loader import Timepoint  # type: ignore
        except ImportError:
            from ...config_loader import Timepoint  # type: ignore
        cfg = SessionConfig(
            file_path=calf_path,
            condition=cond,
            subject_info={},
            timepoints={
                "NIRS_VOT": [Timepoint("Baseline", inflate_t, deflate_t)],
                "HRV": {},
            },
        )
        dyn = {"Baseline": anchor_from_window(inflate_t, deflate_t)}
        self.status_message.emit(
            f"자동 템플릿 적용 ({calf_path.name}): "
            f"Baseline {inflate_t}~{deflate_t}"
        )
        return cfg, dyn

    def _on_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open NIRS-VOT Calf data",
            "",
            _FILE_FILTER,
        )
        if not path:
            return
        p = Path(path)
        if not is_calf_timeseries(p):
            QMessageBox.warning(
                self, "시계열 아님",
                "선택한 파일은 _Calf 시계열로 보이지 않습니다.\n"
                "(헤더에 'mm-dd' 또는 'Date' + 'SmO2' 컬럼이 있어야 함)\n\n"
                f"{p}"
            )
            return
        _QApp.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            lf = self._load_pair(p)
        except Exception as exc:  # noqa: BLE001
            _QApp.restoreOverrideCursor()
            QMessageBox.critical(self, "로드 실패", str(exc))
            return
        finally:
            if _QApp.overrideCursor() is not None:
                _QApp.restoreOverrideCursor()

        # condition 추정 (config 우선, 없으면 파일명, 없으면 콤보 현재 값)
        guess = (lf.config.condition if lf.config and lf.config.condition else None)
        if not guess:
            guess = _condition_from_stem(Path(path).stem)
        if not guess:
            guess = self.condition_combo.currentText()

        self.loaded[guess] = lf
        if self.condition_combo.currentText() == guess:
            # 같은 값 → 시그널 발생 안 함. 직접 measurement_loaded 만 emit.
            pass
        else:
            self.condition_combo.setCurrentText(guess)
        cfg_tag = f" + cfg={lf.config.file_path.name}" if lf.config else "  (cfg 없음)"
        msg = (
            f"로드됨 ({guess}): {Path(path).name}{cfg_tag}  "
            f"[{len(lf.smoothed)} rows, "
            f"{lf.smoothed.attrs['sampling_interval_sec']:.3f}s 간격]"
        )
        self.info_label.setText(msg)
        self.status_message.emit(msg)
        self.measurement_loaded.emit(guess, lf)

    def _on_open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select measurement folder", ""
        )
        if not folder:
            return
        self.load_folder(Path(folder))

    def load_folder(self, folder: Path) -> int:
        """폴더의 모든 _Calf 시계열을 발견 순서대로 로드.

        파일명/접미사가 아닌 헤더 컬럼(``mm-dd`` + ``SmO2``)으로 시계열인지 판정한다.
        condition 은 설정 xlsx 의 condition 또는 파일명 토큰(NOR/HYPO/HYPER)으로 추정.
        같은 condition 이 중복 등장하면 마지막 것이 유지됨.

        UX: 로드 중 wait cursor + 파일별 status 메시지 + processEvents 로 GUI 응답 유지.
        """
        if not folder.is_dir():
            QMessageBox.warning(self, "폴더 없음", f"{folder}")
            return 0

        # 미리 후보 수집 (header 검사도 한 번에)
        candidates = [p for p in sorted(folder.iterdir())
                      if p.is_file() and p.suffix.lower() in _CALF_EXTS]
        total = len(candidates)

        _QApp.setOverrideCursor(QCursor(Qt.WaitCursor))
        loaded_conds: list[str] = []
        try:
            for idx, p in enumerate(candidates, start=1):
                self.info_label.setText(f"로드 중 ({idx}/{total}): {p.name}")
                _QApp.processEvents()
                if not is_calf_timeseries(p):
                    continue
                try:
                    lf = self._load_pair(p)
                except Exception as exc:  # noqa: BLE001
                    self.status_message.emit(f"로드 스킵: {p.name} ({exc})")
                    continue
                stem = p.stem
                cond = (lf.config.condition if lf.config and lf.config.condition
                        else _condition_from_stem(stem))
                if cond is None:
                    if stem.lower().endswith("_calf"):
                        cond = stem[: -len("_calf")]
                    else:
                        cond = stem
                self.loaded[cond] = lf
                self.measurement_loaded.emit(cond, lf)
                loaded_conds.append(cond)
        finally:
            _QApp.restoreOverrideCursor()

        if not loaded_conds:
            QMessageBox.information(
                self, "폴더 로드",
                f"폴더에서 _Calf 시계열을 찾지 못함 (mm-dd + SmO2 헤더 기준):\n{folder}"
            )
            return 0

        msg = f"폴더 로드: {len(loaded_conds)}개  ({', '.join(loaded_conds)})"
        self.info_label.setText(msg)
        self.status_message.emit(msg)

        first = loaded_conds[0]
        if first in CONDITIONS and self.condition_combo.currentText() != first:
            self.condition_combo.setCurrentText(first)
        return len(loaded_conds)

    def clear_all(self) -> None:
        """모든 로드된 데이터·결과 제거 + 그래프 초기화."""
        self.loaded.clear()
        self._last_result = None
        if self._overlay is not None:
            self._overlay.disconnect()
            self._overlay = None
        self._ax = None
        self._raw_line = self._smooth_line = None
        self._fill_deficit = self._fill_hyperemia = None
        self._text_labels.clear()
        self._fig_legend = None
        self.canvas.figure.clear()
        self.canvas.canvas.draw_idle()
        self.info_label.setText(
            "데이터를 로드해주세요.  [Open data file] 단일 파일 / [Open folder] 폴더 일괄."
        )
        self.status_message.emit("Cleared")
        self.measurement_cleared.emit()

    def _sync_session_combo(self, condition: str | None = None) -> None:
        """현재 condition 의 cfg.nirs_timepoints() 이름들로 session_combo 재구성.

        cfg 가 없거나 timepoint 가 비어있으면 default SESSIONS 유지.
        현재 선택된 session 이 새 목록에 있으면 보존, 없으면 첫 번째.
        """
        cond = condition or self.condition_combo.currentText()
        names: list[str] = []
        lf = self.loaded.get(cond) if cond else None
        if lf is not None and lf.config is not None:
            names = [tp.name for tp in lf.config.nirs_timepoints() if tp.name]
        if not names:
            names = list(SESSIONS)
        # 현재 값 보존
        cur = self.session_combo.currentText()
        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        self.session_combo.addItems(names)
        if cur and cur in names:
            self.session_combo.setCurrentText(cur)
        self.session_combo.blockSignals(False)

    # ──────────────────────────────────────────────
    #  분석
    # ──────────────────────────────────────────────
    def analyze_current(self) -> None:
        cond = self.condition_combo.currentText()
        sess = self.session_combo.currentText()
        self.analyze_session(cond, sess)

    def _resolve_anchor(self, lf: LoadedFile, condition: str, session: str) -> Anchor:
        """동적 anchor 우선, 없으면 하드코딩 fallback."""
        if session in lf.dynamic_anchors:
            return lf.dynamic_anchors[session]
        return get_anchors(condition, session)

    def analyze_session(self, condition: str, session: str, *, silent: bool = False) -> None:
        if condition not in self.loaded:
            if not silent:
                QMessageBox.warning(
                    self, "데이터 없음",
                    f"{condition} 조건의 파일이 로드되지 않았습니다.\n"
                    f"[Open data file] 또는 [Open folder] 로 먼저 로드하세요."
                )
            return

        lf = self.loaded[condition]
        try:
            anchor = self._resolve_anchor(lf, condition, session)
            ov = lf.overrides.get(session, {})
            result = compute_metrics(
                lf.smoothed, anchor, condition, session,
                override_baseline=ov.get("baseline"),
                override_min_time=ov.get("min_time"),
                override_peak_time=ov.get("peak_time"),
            )
        except Exception as exc:  # noqa: BLE001
            if not silent:
                QMessageBox.critical(self, "분석 실패", str(exc))
            else:
                self.status_message.emit(f"분석 실패 ({condition}/{session}): {exc}")
            return

        self._last_result = result
        self.condition_combo.setCurrentText(condition)
        self.session_combo.setCurrentText(session)

        self._render(lf, result)

        anchor_src = "config" if session in lf.dynamic_anchors else "fallback"
        self.info_label.setText(
            f"분석 완료: {condition} / {session}  [{anchor_src}]  —  "
            f"Baseline {result.baseline_smo2:.1f}%, "
            f"Min {result.min_smo2:.1f}%, Peak {result.peak_smo2:.1f}%, "
            f"Magnitude {result.magnitude:.1f}%, T50 {result.t50_sec:.1f}s"
        )
        self.status_message.emit(f"Analyzed: {condition}/{session}")
        self.result_ready.emit(result, lf.smoothed)

    # ──────────────────────────────────────────────
    #  렌더링
    # ──────────────────────────────────────────────
    def _render(self, lf: LoadedFile, r: MetricsResult) -> None:
        """그래프를 그리거나 갱신.

        첫 호출에서만 axes/line/title 등 무거운 setup. 이후 호출은 set_data /
        set_offsets 만으로 빠르게 갱신 (fig.clear 없음). 단, fill_between 만은 매번
        제거 후 재생성 (PolyCollection 부분 갱신이 까다로움).
        """
        if self._ax is None:
            self._setup_axes(r)
        self._update_render(lf, r)

    # ──────────────────────────────────────────────
    def _setup_axes(self, r: MetricsResult) -> None:
        """1회 setup — axes·persistent line·title·formatter."""
        fig = self.canvas.figure
        fig.clear()
        # constrained_layout 끄고 manual margin — zoom 시 axes 가 자동으로 좁아지는
        # ("뭉개짐") 현상 방지. legend 가 axes 위 외부 (bbox_to_anchor=(0.5, 1.10)) 에
        # 있어 constrained_layout 이 매번 axes 폭을 재계산하던 게 원인.
        try:
            fig.set_layout_engine(None)
        except Exception:  # noqa: BLE001
            pass
        fig.subplots_adjust(left=0.07, right=0.985, top=0.85, bottom=0.16)
        ax = fig.add_subplot(111)
        self._ax = ax

        # Raw / Smoothed 선 (set_data 로 갱신)
        self._raw_line, = ax.plot([], [],
            color=Color.SMO2_RAW, alpha=0.45, linewidth=0.9, label="Raw")
        self._smooth_line, = ax.plot([], [],
            color=Color.SMO2_SMOOTH, linewidth=1.8, label="Smoothed (5s)")

        # 드래그 가능한 핸들 (vline 4 + hline 1 + marker 2). 처음 한 번 추가.
        overlay = DraggableOverlay(
            ax,
            on_drag_end=self._on_overlay_drag_end,
            on_drag_motion=self._on_overlay_drag_motion,
        )
        overlay.add_hline("baseline", 0.0,
            color=Color.BASELINE, linestyle="--", linewidth=1.4, alpha=0.9)
        for name in ("s", "i", "d", "e"):
            overlay.add_vline(name, r.anchors_abs[name],
                color="#666666", linestyle=":", linewidth=1.4, alpha=0.85)
        overlay.add_marker("min", r.anchors_abs["i"], 0.0,
            color=Color.MIN_MARKER, s=90, zorder=5,
            edgecolors="white", linewidths=1.5)
        overlay.add_marker("peak", r.anchors_abs["d"], 0.0,
            color=Color.PEAK_MARKER, s=90, zorder=5,
            edgecolors="white", linewidths=1.5)
        self._overlay = overlay

        # vline 라벨 (start / inflate / deflate / end). 위치만 갱신.
        for name, label in [("s", "start"), ("i", "inflate"),
                             ("d", "deflate"), ("e", "end")]:
            t = r.anchors_abs[name]
            txt = ax.text(t, 1.0, label, rotation=90, ha="right", va="top",
                          fontsize=8, color="#666666",
                          transform=ax.get_xaxis_transform())
            self._text_labels[name] = txt

        ax.set_xlabel("Time")
        ax.set_ylabel("SmO2 (%)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S", tz=r.anchors_abs["s"].tz))
        ax.grid(True, alpha=0.25)
        # autofmt_xdate 대신 직접 회전 — autofmt_xdate 는 subplots_adjust 를 강제로
        # 덮어써서 우리 manual margin 과 충돌.
        for lbl in ax.get_xticklabels():
            lbl.set_rotation(25)
            lbl.set_horizontalalignment("right")

        # ── 줌/팬 기능 (휠·우클릭 박스·더블클릭 리셋) ──
        self._setup_zoom_pan()

    def _update_render(self, lf: LoadedFile, r: MetricsResult) -> None:
        """artist 데이터·위치만 갱신 (빠른 경로)."""
        ax = self._ax
        if ax is None:
            return

        s = r.anchors_abs["s"]
        i = r.anchors_abs["i"]
        d = r.anchors_abs["d"]
        e = r.anchors_abs["e"]

        df = lf.smoothed
        seg = df[(df["datetime"] >= s) & (df["datetime"] <= e)]

        # 1) Raw / Smoothed line 데이터만 갱신
        self._raw_line.set_data(seg["datetime"], seg["SmO2_raw"])
        self._smooth_line.set_data(seg["datetime"], seg["SmO2_smooth"])

        # 2) fill_between 재생성 (PolyCollection 갱신은 까다로워 새로 만듦)
        self._rebuild_fills(seg, r.baseline_smo2, i, d, e)

        # 3) 핸들 위치 갱신 (overlay artist 재사용)
        ov = self._overlay
        if ov is not None:
            ov.update_handle("hline", "baseline", r.baseline_smo2)
            for name, t in [("s", s), ("i", i), ("d", d), ("e", e)]:
                ov.update_handle("vline", name, t)
            # marker 위치 + legend 라벨 갱신 (값이 변하면 라벨도 따라감)
            if pd.notna(r.min_time):
                ov.update_handle("marker", "min", r.min_time, r.min_smo2)
                ov.handles[("marker", "min")].artist.set_label(f"Min {r.min_smo2:.1f}%")
            if pd.notna(r.peak_time):
                ov.update_handle("marker", "peak", r.peak_time, r.peak_smo2)
                ov.handles[("marker", "peak")].artist.set_label(f"Peak {r.peak_smo2:.1f}%")
            # baseline hline 라벨도 동기화
            ov.handles[("hline", "baseline")].artist.set_label(
                f"Baseline {r.baseline_smo2:.1f}%"
            )

        # 4) text 라벨 위치
        from matplotlib.dates import date2num
        for name, t in [("s", s), ("i", i), ("d", d), ("e", e)]:
            txt = self._text_labels.get(name)
            if txt is not None:
                txt.set_position((date2num(t.to_pydatetime()), 1.0))

        # 5) 축 범위 — 명시적으로 데이터 범위로 (autoscale_view 는 axvline/marker 의
        #    default datalim 까지 union 해 xlim 이 거대해지는 문제 회피).
        if not seg.empty:
            t_min = seg["datetime"].iloc[0]
            t_max = seg["datetime"].iloc[-1]
            ax.set_xlim(t_min, t_max)
            y_lo = float(min(seg["SmO2_raw"].min(), seg["SmO2_smooth"].min()))
            y_hi = float(max(seg["SmO2_raw"].max(), seg["SmO2_smooth"].max()))
            margin = max(2.0, (y_hi - y_lo) * 0.05)
            ax.set_ylim(y_lo - margin, y_hi + margin)

        # 6) 타이틀 — axes 위쪽 (Qt legend 가 axes 외부에 별도 위젯이라 겹침 없음)
        ax.set_title(
            f"NIRS-VOT  |  {r.condition}  |  {r.session}    "
            f"Mag {r.magnitude:.1f}%   Slope1(0-60s) {r.slope1_0_60:.3f}%/s   "
            f"Slope2(0-10s) {r.slope2_0_10:.3f}%/s   T50 {r.t50_sec:.1f}s   "
            f"T95 {r.t95_sec:.1f}s     (드래그: vline·baseline·Min·Peak)",
            fontsize=9, loc="left",
        )

        # 7) figure 우상단 외부 legend (axes 영역 밖, close 버튼 바로 밑).
        #    fig.legend 로 figure 좌표계 사용 → axes layout 영향 없음, 데이터 가림 없음.
        # 옛 figure legend 제거 (재분석 시 누수 방지)
        if self._fig_legend is not None:
            try:
                self._fig_legend.remove()
            except Exception:  # noqa: BLE001
                pass
            self._fig_legend = None

        fig = self.canvas.figure
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            self._fig_legend = fig.legend(
                handles, labels,
                loc="upper right",
                bbox_to_anchor=(0.985, 0.985),  # figure 우상단 안쪽
                ncol=2,
                fontsize=7,
                framealpha=0.92,
                handletextpad=0.3,
                columnspacing=0.8,
                labelspacing=0.3,
                borderpad=0.4,
            )

        self.canvas.canvas.draw_idle()

    def _rebuild_fills(self, seg, baseline_y: float, i_t, d_t, e_t) -> None:
        """fill_between 두 영역 재생성 (옛 PolyCollection 제거 + 새로)."""
        ax = self._ax
        if ax is None:
            return
        for f_attr in ("_fill_deficit", "_fill_hyperemia"):
            f = getattr(self, f_attr, None)
            if f is not None:
                try:
                    f.remove()
                except Exception:  # noqa: BLE001
                    pass
                setattr(self, f_attr, None)

        # Oxygen Deficit (occlusion 구간, baseline 아래)
        occ = seg[(seg["datetime"] >= i_t) & (seg["datetime"] <= d_t)]
        if not occ.empty:
            self._fill_deficit = ax.fill_between(
                occ["datetime"],
                np.minimum(occ["SmO2_smooth"], baseline_y),
                baseline_y,
                where=(occ["SmO2_smooth"] < baseline_y),
                color=Color.OXY_DEFICIT, alpha=0.3, label="Oxygen Deficit",
            )

        # Hyperemia (deflation 이후, baseline 위)
        rep = seg[(seg["datetime"] >= d_t) & (seg["datetime"] <= e_t)]
        if not rep.empty:
            self._fill_hyperemia = ax.fill_between(
                rep["datetime"],
                baseline_y,
                np.maximum(rep["SmO2_smooth"], baseline_y),
                where=(rep["SmO2_smooth"] > baseline_y),
                color=Color.HYPEREMIA, alpha=0.3, label="Hyperemia (AUC 3min)",
            )

    # ──────────────────────────────────────────────
    #  드래그 콜백
    # ──────────────────────────────────────────────
    # ──────────────────────────────────────────────
    #  줌 / 팬 (마우스 휠 + 우클릭 박스 드래그 + 더블클릭 리셋)
    # ──────────────────────────────────────────────
    def _setup_zoom_pan(self) -> None:
        """matplotlib 표준 zoom/pan 보다 가볍게: scroll 휠 + RectangleSelector(우클릭).

        DraggableOverlay 가 좌클릭 드래그를 핸들 이동에 사용하므로 충돌 회피:
            • 마우스 휠 (위/아래)            → 커서 위치 중심 zoom in/out
            • 우클릭 드래그 (박스)            → 박스 영역으로 zoom
            • 더블클릭 (좌클릭) 또는 'r' 키   → 원본 뷰 복원 (autoscale)
        """
        from matplotlib.widgets import RectangleSelector

        ax = self._ax
        canvas = self.canvas.canvas
        if ax is None:
            return

        # 휠 zoom
        self._cid_scroll = canvas.mpl_connect("scroll_event", self._on_scroll)
        # 더블클릭 → reset
        self._cid_dblclk = canvas.mpl_connect("button_press_event", self._on_press_for_reset)
        # 키보드: 'r' → reset
        self._cid_key = canvas.mpl_connect("key_press_event", self._on_key_for_reset)

        # 박스 줌 (우클릭 드래그). useblit=False — manual layout 과 호환성 ↑.
        try:
            self._rect_selector = RectangleSelector(
                ax,
                onselect=self._on_rect_select,
                useblit=False,
                button=[3],  # 우클릭만 — 좌클릭은 DraggableOverlay 가 사용
                minspanx=5, minspany=5,
                spancoords="pixels",
                interactive=False,
                props=dict(facecolor="#FBBF24", alpha=0.25,
                           edgecolor="#F59E0B", linewidth=1.2, linestyle="--"),
            )
        except Exception:  # noqa: BLE001
            self._rect_selector = None

    def _on_scroll(self, event) -> None:
        """마우스 휠 → 커서 위치 중심으로 zoom."""
        ax = self._ax
        if ax is None or event.inaxes is not ax:
            return
        if event.xdata is None or event.ydata is None:
            return
        base = 1.25
        scale = (1.0 / base) if event.button == "up" else base
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        x_curr, y_curr = event.xdata, event.ydata
        new_w = (cur_xlim[1] - cur_xlim[0]) * scale
        new_h = (cur_ylim[1] - cur_ylim[0]) * scale
        relx = (cur_xlim[1] - x_curr) / max(cur_xlim[1] - cur_xlim[0], 1e-12)
        rely = (cur_ylim[1] - y_curr) / max(cur_ylim[1] - cur_ylim[0], 1e-12)
        ax.set_xlim([x_curr - new_w * (1 - relx), x_curr + new_w * relx])
        ax.set_ylim([y_curr - new_h * (1 - rely), y_curr + new_h * rely])
        self.canvas.canvas.draw_idle()

    def _on_rect_select(self, eclick, erelease) -> None:
        """우클릭 드래그 박스 영역으로 zoom."""
        ax = self._ax
        if ax is None:
            return
        if (eclick.xdata is None or erelease.xdata is None
                or eclick.ydata is None or erelease.ydata is None):
            return
        x1, x2 = sorted([float(eclick.xdata), float(erelease.xdata)])
        y1, y2 = sorted([float(eclick.ydata), float(erelease.ydata)])
        if x2 - x1 < 1e-9 or y2 - y1 < 1e-9:
            return
        ax.set_xlim(x1, x2)
        ax.set_ylim(y1, y2)
        self.canvas.canvas.draw_idle()

    def _on_press_for_reset(self, event) -> None:
        """더블클릭 (좌·우 무관) → 원본 뷰 복원."""
        if event.inaxes is not self._ax:
            return
        if getattr(event, "dblclick", False):
            self._reset_zoom()

    def _on_key_for_reset(self, event) -> None:
        """'r' 또는 'R' 키 → 원본 뷰 복원."""
        if event.key in ("r", "R", "home"):
            self._reset_zoom()

    def _reset_zoom(self) -> None:
        """원본 데이터 범위로 xlim/ylim 복원."""
        ax = self._ax
        if ax is None:
            return
        # last_result 가 있으면 anchors_abs 의 s~e 와 SmO2 데이터 범위 사용
        r = self._last_result
        if r is not None and self._raw_line is not None and self._smooth_line is not None:
            try:
                ax.set_xlim(r.anchors_abs["s"], r.anchors_abs["e"])
                yd = list(self._raw_line.get_ydata()) + list(self._smooth_line.get_ydata())
                if yd:
                    y_lo = float(min(yd)); y_hi = float(max(yd))
                    margin = max(2.0, (y_hi - y_lo) * 0.05)
                    ax.set_ylim(y_lo - margin, y_hi + margin)
            except Exception:  # noqa: BLE001
                ax.relim(); ax.autoscale_view()
        else:
            ax.relim(); ax.autoscale_view()
        self.canvas.canvas.draw_idle()
        self.status_message.emit("Zoom 리셋")

    def _on_overlay_drag_end(self, kind: str, name: str, value) -> None:
        """DraggableOverlay drag-end — 시그널만 emit. 실제 처리는 MainWindow."""
        self.anchor_dragged.emit(kind, name, value)

    def _on_overlay_drag_motion(self, kind: str, name: str, value) -> None:
        """드래그 중 매 motion. fill 영역 실시간 갱신 + 외부에 알림."""
        # 현재 핸들 상태로부터 (s, i, d, e, baseline) 추출 → fill 갱신
        cond = self.condition_combo.currentText()
        lf = self.loaded.get(cond)
        if lf is None or self._ax is None or self._overlay is None:
            return

        ov = self._overlay
        # 핸들 위치 직접 읽기 (matplotlib float 값)
        from matplotlib.dates import num2date
        try:
            tz = ov._tz
            def to_ts(line):
                return pd.Timestamp(num2date(line.get_xdata()[0], tz=tz))

            s_t = to_ts(ov.handles[("vline", "s")].artist)
            i_t = to_ts(ov.handles[("vline", "i")].artist)
            d_t = to_ts(ov.handles[("vline", "d")].artist)
            e_t = to_ts(ov.handles[("vline", "e")].artist)
            base_y = float(ov.handles[("hline", "baseline")].artist.get_ydata()[0])
        except Exception:  # noqa: BLE001
            return

        df = lf.smoothed
        seg = df[(df["datetime"] >= s_t) & (df["datetime"] <= e_t)]
        if seg.empty:
            seg = df  # 너무 좁아지면 전체로 fallback

        # fill 만 빠르게 다시 그림 (line 데이터는 그대로)
        self._rebuild_fills(seg, base_y, i_t, d_t, e_t)

        # 외부 (MainWindow) 에 alpha-quality 시그널 emit — ParameterPanel 동기화용
        self.anchor_dragging.emit(kind, name, value)

    @property
    def last_result(self) -> Optional[MetricsResult]:
        return self._last_result
