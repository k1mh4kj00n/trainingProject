"""설정 xlsx 파라미터 편집 패널 (별도 도크용).

설정 파일 로드 → 모든 input 위젯이 자동 채워짐.
사용자가 수정 → Apply → SessionConfig in-memory 갱신 + LoadedFile.dynamic_anchors 재산출
                + ``params_applied`` 시그널 → 호출자가 분석 재실행.

원본 xlsx 는 변경하지 않는다 (in-memory 만).

모든 텍스트 필드는 편집 가능 (read-only QLabel 없음).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDate, QTime, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from ...config_loader import SessionConfig, TimeWindow, Timepoint  # type: ignore
    from ...nirs_vot.anchors import (  # type: ignore
        BASELINE_LEAD_SEC,
        REPERFUSION_TAIL_SEC,
        Anchor,
        anchor_from_window,
    )
except ImportError:
    from config_loader import SessionConfig, TimeWindow, Timepoint  # type: ignore
    from nirs_vot.anchors import (  # type: ignore
        BASELINE_LEAD_SEC,
        REPERFUSION_TAIL_SEC,
        Anchor,
        anchor_from_window,
    )

from PySide6.QtWidgets import QFileDialog, QMessageBox

try:
    from . import parameter_io  # type: ignore
except ImportError:
    import parameter_io  # type: ignore


# ─────────────────────────────────────────────────────────────
#  필드 스펙: 어떤 입력 위젯을 쓸지 정의
# ─────────────────────────────────────────────────────────────
# kind: 'text' | 'int' | 'float' | 'gender' | 'date'
_INFO_FIELDS: list[tuple[str, str, str, dict]] = [
    ("ID(Protocol)",  "ID",            "text",   {}),
    ("Name",          "Name",          "text",   {}),
    ("D.O.B",         "D.O.B",         "date",   {}),
    ("Age",           "Age",           "int",    {"min": 0,    "max": 150}),
    ("Gender",        "Gender",        "gender", {}),
    ("Weight(kg)",    "Weight (kg)",   "float",  {"min": 0.0,  "max": 250.0, "step": 0.1, "decimals": 2}),
    ("Height(cm)",    "Height (cm)",   "float",  {"min": 0.0,  "max": 250.0, "step": 0.1, "decimals": 1}),
    ("Wattmax",       "Wattmax",       "int",    {"min": 0,    "max": 1000}),
    ("VO2max",        "VO2max",        "float",  {"min": 0.0,  "max": 100.0, "step": 0.1, "decimals": 2}),
    ("W/kg",          "W/kg",          "float",  {"min": 0.0,  "max": 20.0,  "step": 0.01,"decimals": 4}),
    ("FTP",           "FTP",           "float",  {"min": 0.0,  "max": 1000.0,"step": 0.5, "decimals": 1}),
    ("AT(VT1)",       "AT (VT1)",      "float",  {"min": 0.0,  "max": 1000.0,"step": 0.5, "decimals": 1}),
    ("RC(VT2)",       "RC (VT2)",      "float",  {"min": 0.0,  "max": 1000.0,"step": 0.5, "decimals": 1}),
    ("Wattmax(90%)",  "Wattmax(90%)",  "float",  {"min": 0.0,  "max": 1000.0,"step": 0.1, "decimals": 1}),
    ("Wattmax(40%)",  "Wattmax(40%)",  "float",  {"min": 0.0,  "max": 1000.0,"step": 0.1, "decimals": 1}),
    ("Wattmax(110%)", "Wattmax(110%)", "float",  {"min": 0.0,  "max": 1000.0,"step": 0.1, "decimals": 1}),
    ("안장 높이",      "Saddle (cm)",   "float",  {"min": 0.0,  "max": 200.0, "step": 0.1, "decimals": 1}),
    ("안정시 심박수",  "Resting HR",    "int",    {"min": 0,    "max": 250}),
]


def _t_to_qtime(t: Optional[dt.time]) -> QTime:
    if t is None:
        return QTime(0, 0, 0)
    return QTime(t.hour, t.minute, t.second)


def _qtime_to_t(q: QTime) -> dt.time:
    return dt.time(q.hour(), q.minute(), q.second())


def _time_to_seconds(t) -> int:
    """dt.time / int / float / str / None → 초 단위 정수."""
    if t is None:
        return 0
    if isinstance(t, dt.time):
        return t.hour * 3600 + t.minute * 60 + t.second
    if isinstance(t, dt.timedelta):
        return int(t.total_seconds())
    if isinstance(t, (int, float)):
        return max(0, int(t))
    return 0


def _seconds_to_time(s: int) -> dt.time:
    """초 단위 정수 → dt.time (3600 초 미만 가정, 초과해도 hour 로 자동 보정)."""
    s = max(0, int(s))
    h = (s // 3600) % 24
    m = (s % 3600) // 60
    sec = s % 60
    return dt.time(h, m, sec)


def _tte_to_str(v) -> str:
    """TTE 값 → 사람 읽기 좋은 짧은 문자열 (예: '39s', '1:05')."""
    s = _time_to_seconds(v)
    if s <= 0:
        return "—"
    if s < 60:
        return f"{s}s"
    return f"{s // 60}:{s % 60:02d}"


def _maint_to_str(v) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    if f != f:  # NaN
        return "—"
    return f"{f:.1f}%"


def _make_input(kind: str, opts: dict) -> QWidget:
    if kind == "text":
        w = QLineEdit()
        w.setClearButtonEnabled(True)
        return w
    if kind == "int":
        w = QSpinBox()
        w.setRange(opts.get("min", -10**9), opts.get("max", 10**9))
        return w
    if kind == "float":
        w = QDoubleSpinBox()
        w.setRange(opts.get("min", -1e9), opts.get("max", 1e9))
        w.setSingleStep(opts.get("step", 0.1))
        w.setDecimals(opts.get("decimals", 2))
        return w
    if kind == "gender":
        w = QComboBox()
        w.addItems(["", "Male", "Female", "Other"])
        return w
    if kind == "date":
        w = QDateEdit()
        w.setDisplayFormat("yyyy-MM-dd")
        w.setCalendarPopup(True)
        w.setSpecialValueText(" ")
        w.setMinimumDate(QDate(1900, 1, 1))
        w.setMaximumDate(QDate(2100, 12, 31))
        w.setDate(QDate(1900, 1, 1))  # special value
        return w
    raise ValueError(f"unknown kind: {kind}")


def _set_input(w: QWidget, kind: str, value) -> None:
    if value is None:
        if kind == "text":
            w.setText("")
        elif kind == "int":
            w.setValue(0)
        elif kind == "float":
            w.setValue(0.0)
        elif kind == "gender":
            w.setCurrentIndex(0)
        elif kind == "date":
            w.setDate(QDate(1900, 1, 1))
        return

    if kind == "text":
        w.setText(str(value))
    elif kind == "int":
        try:
            w.setValue(int(value))
        except (TypeError, ValueError):
            w.setValue(0)
    elif kind == "float":
        try:
            w.setValue(float(value))
        except (TypeError, ValueError):
            w.setValue(0.0)
    elif kind == "gender":
        s = str(value).strip()
        idx = w.findText(s, Qt.MatchFixedString)
        w.setCurrentIndex(idx if idx >= 0 else 0)
    elif kind == "date":
        if isinstance(value, dt.datetime):
            d = value.date()
            w.setDate(QDate(d.year, d.month, d.day))
        elif isinstance(value, dt.date):
            w.setDate(QDate(value.year, value.month, value.day))


def _timepoints_equal(a: list, b: list) -> bool:
    """두 Timepoint 리스트가 동등한지 (이름·시각·lead·tail 모두 일치)."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if (x.name != y.name or x.start != y.start or x.end != y.end
                or int(x.lead) != int(y.lead) or int(x.tail) != int(y.tail)):
            return False
    return True


def _get_input(w: QWidget, kind: str):
    if kind == "text":
        s = w.text().strip()
        return s or None
    if kind == "int":
        return int(w.value())
    if kind == "float":
        return float(w.value())
    if kind == "gender":
        s = w.currentText().strip()
        return s or None
    if kind == "date":
        q: QDate = w.date()
        if q == QDate(1900, 1, 1):
            return None
        return dt.datetime(q.year(), q.month(), q.day())
    return None


class _TimepointRow(QWidget):
    """NIRS_VOT 동적 timepoint 한 행 — Name · Start(Occ) · Fin(Def) · Lead · Tail · 삭제.

    삭제 버튼 클릭 시 ``deleted(self)`` 시그널 emit, 모든 input 변경 시 ``edited`` emit.
    부모 ParameterPanel 이 시그널을 받아 행 제거 / 재산출 / Apply 활성화 처리.
    """

    deleted = Signal(object)
    edited = Signal()  # 어떤 셀이든 변경되면 emit (Apply 버튼 강조 등 용도)

    def __init__(self, parent: QWidget | None = None,
                 *, tp: "Timepoint | None" = None,
                 deletable: bool = True) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # 컴팩트 사이즈 — 도크 폭이 좁아도 5 컬럼 + ✕ 모두 보이도록
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("이름")
        self.name_edit.setMinimumWidth(60)
        self.name_edit.setMaximumWidth(90)
        self.name_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        if tp is not None:
            self.name_edit.setText(tp.name)
        lay.addWidget(self.name_edit, stretch=2)

        self.start_edit = QTimeEdit()
        self.start_edit.setDisplayFormat("HH:mm:ss")
        self.start_edit.setMinimumWidth(70)
        self.start_edit.setMaximumWidth(95)
        self.start_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        if tp is not None:
            self.start_edit.setTime(QTime(tp.start.hour, tp.start.minute, tp.start.second))
        lay.addWidget(self.start_edit, stretch=2)

        self.end_edit = QTimeEdit()
        self.end_edit.setDisplayFormat("HH:mm:ss")
        self.end_edit.setMinimumWidth(70)
        self.end_edit.setMaximumWidth(95)
        self.end_edit.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        if tp is not None:
            self.end_edit.setTime(QTime(tp.end.hour, tp.end.minute, tp.end.second))
        lay.addWidget(self.end_edit, stretch=2)

        self.lead_spin = QSpinBox()
        self.lead_spin.setRange(0, 600)
        self.lead_spin.setSuffix(" s")
        self.lead_spin.setValue(int(tp.lead) if tp is not None else BASELINE_LEAD_SEC)
        self.lead_spin.setMinimumWidth(55)
        self.lead_spin.setMaximumWidth(80)
        self.lead_spin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(self.lead_spin, stretch=1)

        self.tail_spin = QSpinBox()
        self.tail_spin.setRange(0, 1200)
        self.tail_spin.setSuffix(" s")
        self.tail_spin.setValue(int(tp.tail) if tp is not None else REPERFUSION_TAIL_SEC)
        self.tail_spin.setMinimumWidth(60)
        self.tail_spin.setMaximumWidth(85)
        self.tail_spin.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(self.tail_spin, stretch=1)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedWidth(24)
        self.delete_btn.setFixedHeight(self.start_edit.sizeHint().height())
        self.delete_btn.setToolTip("이 timepoint 행 삭제")
        self.delete_btn.clicked.connect(lambda: self.deleted.emit(self))
        self.delete_btn.setVisible(deletable)
        lay.addWidget(self.delete_btn, stretch=0)

        # 변경 시그널 — Qt 시그널은 인자 emit 하므로 lambda 로 인자 버리고 0-arg edited emit
        self.name_edit.textChanged.connect(lambda _=None: self.edited.emit())
        self.start_edit.timeChanged.connect(lambda _=None: self.edited.emit())
        self.end_edit.timeChanged.connect(lambda _=None: self.edited.emit())
        self.lead_spin.valueChanged.connect(lambda _=None: self.edited.emit())
        self.tail_spin.valueChanged.connect(lambda _=None: self.edited.emit())

    def to_timepoint(self) -> "Timepoint | None":
        """현재 input 값으로 Timepoint dataclass 생성. 이름이 비거나 시각이 0:0:0 이면 None."""
        name = self.name_edit.text().strip()
        if not name:
            return None
        s = _qtime_to_t(self.start_edit.time())
        e = _qtime_to_t(self.end_edit.time())
        if s == dt.time(0, 0, 0) and e == dt.time(0, 0, 0):
            return None
        return Timepoint(
            name=name, start=s, end=e,
            lead=int(self.lead_spin.value()),
            tail=int(self.tail_spin.value()),
        )

    def set_enabled_all(self, enabled: bool) -> None:
        for w in (self.name_edit, self.start_edit, self.end_edit,
                  self.lead_spin, self.tail_spin, self.delete_btn):
            w.setEnabled(enabled)


class ParameterPanel(QWidget):
    """설정 파라미터 편집 + Apply + Auto Detect.

    Subject info 19 필드 + NIRS_VOT 동적 timepoint(이름·시각·lead·tail) + HRV display + Min/Peak.
    NIRS_VOT 는 사용자가 + Add row 로 자유롭게 추가/삭제 가능 (v0.7).
    """

    params_applied = Signal()
    auto_detect_requested = Signal()  # Min/Peak 그룹의 Auto Detect 버튼 클릭

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cfg: Optional[SessionConfig] = None
        self._last_result = None  # 가장 최근 MetricsResult — Reset 시 재사용
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 스크롤 영역으로 감싸 도크 폭이 좁을 때도 깔끔
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        body = QWidget()
        # NIRS_VOT 행 5컬럼 + 삭제버튼 모두 보이는 최소 폭
        # (60+70+70+55+60+24 + spacing 5×4 + groupbox 좌우 16 + outer margin 16 ≈ 395)
        body.setMinimumWidth(400)
        scroll.setWidget(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        root = QVBoxLayout(body)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.title_label = QLabel("Session parameters  ·  (no data)")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        self.title_label.setWordWrap(True)
        root.addWidget(self.title_label)

        # ── 헤더 버튼 행: 파라미터 스냅샷 load/save ──
        header_btns = QHBoxLayout()
        header_btns.setContentsMargins(0, 0, 0, 0)
        header_btns.setSpacing(6)

        self.load_params_btn = QPushButton("📥  Load params…")
        self.load_params_btn.setToolTip(
            "파라미터 스냅샷(xlsx/csv/txt) 을 불러와 모든 입력 위젯을 채움.\n"
            "Save params 로 저장한 평문 키-값 형식 (docs/templates/parameters-template 참고)."
        )
        self.load_params_btn.clicked.connect(self._on_load_params)
        header_btns.addWidget(self.load_params_btn)

        self.save_params_btn = QPushButton("💾  Save params…")
        self.save_params_btn.setToolTip(
            "현재 패널의 모든 파라미터 값을 xlsx/csv/txt 로 저장.\n"
            "다음에 Load params 로 그대로 복원 가능."
        )
        self.save_params_btn.clicked.connect(self._on_save_params)
        header_btns.addWidget(self.save_params_btn)

        header_btns.addStretch()
        root.addLayout(header_btns)

        # ── (1) Subject info — 모두 편집 가능 ──
        self._info_inputs: dict[str, tuple[str, QWidget]] = {}
        info_box = QGroupBox("Subject info  (편집 가능)")
        info_form = QFormLayout(info_box)
        info_form.setContentsMargins(8, 12, 8, 8)
        info_form.setHorizontalSpacing(10)
        info_form.setVerticalSpacing(4)
        info_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for key, label, kind, opts in _INFO_FIELDS:
            w = _make_input(kind, opts)
            self._info_inputs[key] = (kind, w)
            info_form.addRow(QLabel(label + ":"), w)
        root.addWidget(info_box)

        # ── (2) NIRS_VOT timepoint — 동적 테이블 (v0.7) ──
        nirs_box = QGroupBox("NIRS_VOT timepoint  (분석 anchor 산출)")
        nirs_box_v = QVBoxLayout(nirs_box)
        nirs_box_v.setContentsMargins(6, 10, 6, 6)
        nirs_box_v.setSpacing(4)

        # 헤더 행 (라벨) — _TimepointRow 와 동일한 stretch 비율로 정렬
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(4)
        # (label, min, max, stretch)
        for label, w_min, w_max, stretch in (
            ("Name",   60, 90,  2),
            ("Start",  70, 95,  2),
            ("End",    70, 95,  2),
            ("Lead",   55, 80,  1),
            ("Tail",   60, 85,  1),
        ):
            lbl = QLabel(f"<b>{label}</b>")
            lbl.setMinimumWidth(w_min)
            lbl.setMaximumWidth(w_max)
            lbl.setStyleSheet("color: #4B5563;")
            hdr.addWidget(lbl, stretch=stretch)
        spacer_hdr = QLabel("")
        spacer_hdr.setFixedWidth(24)
        hdr.addWidget(spacer_hdr, stretch=0)  # 삭제 버튼 자리 맞춤
        nirs_box_v.addLayout(hdr)

        self._nirs_rows_layout = QVBoxLayout()
        self._nirs_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._nirs_rows_layout.setSpacing(2)
        nirs_box_v.addLayout(self._nirs_rows_layout)
        self._nirs_rows: list[_TimepointRow] = []

        # + Add row 버튼 — 컴팩트, 행 폭에 맞춰 좌측 정렬
        add_row_btn = QPushButton("＋  Add timepoint")
        add_row_btn.setToolTip(
            "새 timepoint 행 추가. 이름·시작·끝·lead·tail 입력 후 Apply 로 anchor 산출."
        )
        add_row_btn.setMaximumWidth(160)
        add_row_btn.setStyleSheet("padding: 3px 10px;")
        add_row_btn.clicked.connect(self._on_add_nirs_row)
        nirs_box_v.addWidget(add_row_btn, alignment=Qt.AlignLeft)
        self.add_nirs_row_btn = add_row_btn

        root.addWidget(nirs_box)

        # ── (3) HRV timepoint — 고정 2칸 (display 전용) ──
        self._hrv_inputs = self._build_timepoint_box(
            "HRV timepoint  (분석 엔진 미구현 — 표시 전용)",
            ("Baseline", "Recovery2"),
        )
        for sess in ("Baseline", "Recovery2"):
            self._hrv_inputs[sess]["start"].setEnabled(False)
            self._hrv_inputs[sess]["end"].setEnabled(False)
            self._hrv_inputs[sess]["start"].setReadOnly(True)
            self._hrv_inputs[sess]["end"].setReadOnly(True)
        root.addWidget(self._hrv_inputs["box"])

        # ── (5) Baseline / Min / Peak  (시각 편집 가능, 값은 보간 자동 표시) ──
        mp_box = QGroupBox("Baseline / Min / Peak  (현재 분석 결과)")
        mp_grid = QGridLayout(mp_box)
        mp_grid.setContentsMargins(8, 12, 8, 8)
        mp_grid.setHorizontalSpacing(10)
        mp_grid.setVerticalSpacing(4)

        mp_grid.addWidget(QLabel(""), 0, 0)
        mp_grid.addWidget(_h("Time / Value"), 0, 1)
        mp_grid.addWidget(_h("Lock"), 0, 2)

        # Baseline (스칼라 SmO2 % 값 — 자동 평균값 또는 사용자 override)
        mp_grid.addWidget(QLabel("<b>Baseline</b>"), 1, 0)
        self.baseline_value_spin = QDoubleSpinBox()
        self.baseline_value_spin.setRange(0.0, 100.0)
        self.baseline_value_spin.setSingleStep(0.1)
        self.baseline_value_spin.setDecimals(2)
        self.baseline_value_spin.setSuffix(" %")
        self.baseline_value_spin.setMinimumWidth(100)
        mp_grid.addWidget(self.baseline_value_spin, 1, 1)
        self.baseline_override_chk = QCheckBox()
        self.baseline_override_chk.setToolTip(
            "체크 시 위 baseline 값을 잠금 — Apply 후에도 그 값을 그대로 사용.\n"
            "체크 해제 시 inflate 직전 60초 평균이 자동 계산됨."
        )
        mp_grid.addWidget(self.baseline_override_chk, 1, 2, alignment=Qt.AlignCenter)

        mp_grid.addWidget(QLabel("<b>Min</b>"), 2, 0)
        self.min_time_edit = QTimeEdit()
        self.min_time_edit.setDisplayFormat("HH:mm:ss")
        mp_grid.addWidget(self.min_time_edit, 2, 1)
        self.min_value_label = QLabel("— %")
        self.min_value_label.setStyleSheet(
            "color: #DC2626; font-weight: bold; padding: 4px 8px;"
        )
        self.min_value_label.setMinimumWidth(70)
        mp_grid.addWidget(self.min_value_label, 2, 2)

        mp_grid.addWidget(QLabel("<b>Peak</b>"), 3, 0)
        self.peak_time_edit = QTimeEdit()
        self.peak_time_edit.setDisplayFormat("HH:mm:ss")
        mp_grid.addWidget(self.peak_time_edit, 3, 1)
        self.peak_value_label = QLabel("— %")
        self.peak_value_label.setStyleSheet(
            "color: #16A34A; font-weight: bold; padding: 4px 8px;"
        )
        self.peak_value_label.setMinimumWidth(70)
        mp_grid.addWidget(self.peak_value_label, 3, 2)

        # Magnitude 표시 (Peak - Min) 자동
        mp_grid.addWidget(QLabel("Magnitude"), 4, 0)
        self.magnitude_label = QLabel("— %")
        self.magnitude_label.setStyleSheet(
            "color: #1F2937; font-weight: bold; padding: 4px 8px;"
        )
        mp_grid.addWidget(self.magnitude_label, 4, 1, 1, 2)

        # Auto detect 버튼 (Min/Peak 검출)
        self.auto_detect_btn = QPushButton("▶  Auto detect by gradient descent")
        self.auto_detect_btn.setEnabled(False)
        self.auto_detect_btn.setToolTip(
            "현재 분석 구간의 occlusion(inflate~deflate+30s)과 reperfusion(deflate~end) 에서\n"
            "GD + SGD + DE 알고리즘으로 local min/max 정밀 검출 → Min/Peak override 적용 + 재분석."
        )
        self.auto_detect_btn.clicked.connect(self.auto_detect_requested.emit)
        mp_grid.addWidget(self.auto_detect_btn, 5, 0, 1, 3)

        root.addWidget(mp_box)

        # ── (6) Exercise / TTE — 운동 결과 (Time To Exhaustion) ──
        ex_box = QGroupBox("Exercise · TTE  (운동 결과 — Time To Exhaustion)")
        ex_form = QFormLayout(ex_box)
        ex_form.setContentsMargins(8, 12, 8, 8)
        ex_form.setHorizontalSpacing(10)
        ex_form.setVerticalSpacing(4)

        self.tte1_spin = QSpinBox()
        self.tte1_spin.setRange(0, 3600)
        self.tte1_spin.setSuffix(" sec")
        self.tte1_spin.setToolTip("Ex1 인터벌의 Time To Exhaustion (초). xlsx Timepoint 시트 R8 의 TTE1 셀.")

        self.tte2_spin = QSpinBox()
        self.tte2_spin.setRange(0, 3600)
        self.tte2_spin.setSuffix(" sec")
        self.tte2_spin.setToolTip("Ex2 인터벌의 Time To Exhaustion (초). xlsx Timepoint 시트 R8 의 TTE2 셀.")

        self.maint_spin = QDoubleSpinBox()
        self.maint_spin.setRange(0.0, 200.0)
        self.maint_spin.setDecimals(2)
        self.maint_spin.setSingleStep(0.1)
        self.maint_spin.setSuffix(" %")
        self.maint_spin.setToolTip(
            "목표 와트 (예: 110% Wattmax) 유지율.\n"
            "70% 미만이면 프로토콜 미준수 가능 — 결과 신뢰도 ↓ 경고."
        )
        self.maint_spin.valueChanged.connect(self._update_tte_quality_label)

        self.tte_quality_label = QLabel("")
        self.tte_quality_label.setWordWrap(True)
        self.tte_quality_label.setTextFormat(Qt.RichText)
        self.tte_quality_label.setStyleSheet("padding: 4px 0;")

        ex_form.addRow("TTE1 (Ex1 탈진까지):", self.tte1_spin)
        ex_form.addRow("TTE2 (Ex2 탈진까지):", self.tte2_spin)
        ex_form.addRow("Maintenance rate:",   self.maint_spin)
        ex_form.addRow(self.tte_quality_label)
        root.addWidget(ex_box)
        self._ex_box = ex_box

        # ── (7) TTE comparison — 모든 로드된 condition 의 TTE 한눈에 ──
        cmp_box = QGroupBox("TTE comparison · all loaded conditions")
        cmp_grid = QGridLayout(cmp_box)
        cmp_grid.setContentsMargins(8, 12, 8, 8)
        cmp_grid.setHorizontalSpacing(10)
        cmp_grid.setVerticalSpacing(4)
        cmp_grid.addWidget(_h("Condition"), 0, 0)
        cmp_grid.addWidget(_h("TTE1"),      0, 1)
        cmp_grid.addWidget(_h("TTE2"),      0, 2)
        cmp_grid.addWidget(_h("Maint."),    0, 3)
        self._tte_compare_grid = cmp_grid
        self._tte_compare_box = cmp_box
        self._tte_compare_value_widgets: list[QWidget] = []
        self._tte_compare_placeholder = QLabel(
            "  로드된 condition 이 없습니다."
        )
        self._tte_compare_placeholder.setStyleSheet("color: #6A737D; font-style: italic;")
        cmp_grid.addWidget(self._tte_compare_placeholder, 1, 0, 1, 4)
        root.addWidget(cmp_box)

        # ── 버튼 행 ──
        btns = QHBoxLayout()
        btns.addStretch()
        self.reset_btn = QPushButton("↺  Reset")
        self.reset_btn.setToolTip("로드 직후 값으로 되돌림")
        self.reset_btn.clicked.connect(self._on_reset)
        btns.addWidget(self.reset_btn)
        self.apply_btn = QPushButton("▶  Apply")
        self.apply_btn.setToolTip("변경된 값으로 anchor 재산출 + 분석 재실행")
        self._apply_btn_default_qss = (
            "background-color: #0969DA; color: white; "
            "font-weight: bold; padding: 6px 18px;"
        )
        self._apply_btn_flash_qss = (
            "background-color: #16A34A; color: white; "
            "font-weight: bold; padding: 6px 18px;"
        )
        self.apply_btn.setStyleSheet(self._apply_btn_default_qss)
        self.apply_btn.clicked.connect(self._on_apply)
        btns.addWidget(self.apply_btn)
        root.addLayout(btns)

        root.addStretch()
        self.set_enabled_inputs(False)

    # ──────────────────────────────────────────
    def _build_timepoint_box(self, title: str, sessions: tuple[str, ...]) -> dict:
        """HRV 표시 전용 고정 2칸 박스 (NIRS_VOT 는 동적 _nirs_rows_layout 사용)."""
        box = QGroupBox(title)
        grid = QGridLayout(box)
        grid.setContentsMargins(8, 12, 8, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        grid.addWidget(QLabel(""), 0, 0)
        grid.addWidget(_h("Start (Occ)"), 0, 1)
        grid.addWidget(_h("End (Def)"), 0, 2)

        out: dict = {"box": box}
        for r, sess in enumerate(sessions, start=1):
            grid.addWidget(QLabel(f"<b>{sess}</b>"), r, 0)
            start = QTimeEdit()
            start.setDisplayFormat("HH:mm:ss")
            end = QTimeEdit()
            end.setDisplayFormat("HH:mm:ss")
            grid.addWidget(start, r, 1)
            grid.addWidget(end, r, 2)
            out[sess] = {"start": start, "end": end}
        return out

    # ──────────────────────────────────────────
    #  NIRS_VOT 동적 행 관리
    # ──────────────────────────────────────────
    def _on_add_nirs_row(self) -> None:
        """+ Add timepoint 클릭 — 자동 이름이 채워진 빈 행 추가 (Apply 시 검증)."""
        # 기존 이름과 충돌하지 않는 Custom{N} 자동 생성 (사용자가 자유 수정 가능)
        existing = {r.name_edit.text().strip() for r in self._nirs_rows
                    if r.name_edit.text().strip()}
        n = 1
        while f"Custom{n}" in existing:
            n += 1
        suggested = f"Custom{n}"
        new_row = self._add_nirs_row(tp=None)
        new_row.name_edit.setText(suggested)
        # 사용자가 즉시 수정할 수 있게 이름 필드에 포커스
        new_row.name_edit.selectAll()
        new_row.name_edit.setFocus()

    def _add_nirs_row(self, *, tp: "Timepoint | None" = None,
                      deletable: bool = True) -> _TimepointRow:
        row = _TimepointRow(self, tp=tp, deletable=deletable)
        row.deleted.connect(self._on_remove_nirs_row)
        self._nirs_rows_layout.addWidget(row)
        self._nirs_rows.append(row)
        return row

    def _on_remove_nirs_row(self, row: _TimepointRow) -> None:
        if row not in self._nirs_rows:
            return
        # 데이터가 있는 행이면 실수 삭제 방지 — 빈 행은 즉시 제거
        tp = row.to_timepoint()
        if tp is not None:
            label = tp.name if tp.name else "(이름 없음)"
            ans = QMessageBox.question(
                self, "Timepoint 삭제 확인",
                f"'{label}' 행을 삭제하시겠습니까?\n"
                f"(시각: {tp.start} ~ {tp.end}, lead {tp.lead}s / tail {tp.tail}s)",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return
        self._nirs_rows.remove(row)
        self._nirs_rows_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()

    def _clear_nirs_rows(self) -> None:
        """모든 NIRS timepoint 행 제거. show_for / clear 가 사용."""
        while self._nirs_rows:
            r = self._nirs_rows.pop()
            self._nirs_rows_layout.removeWidget(r)
            r.setParent(None)
            r.deleteLater()

    def get_nirs_row(self, name: str) -> "_TimepointRow | None":
        """이름으로 NIRS 행 단건 조회 — app.py 의 vline drag 핸들러용."""
        for r in self._nirs_rows:
            if r.name_edit.text().strip() == name:
                return r
        return None

    def nirs_row_names(self) -> list[str]:
        return [r.name_edit.text().strip() for r in self._nirs_rows
                if r.name_edit.text().strip()]

    def _snapshot_nirs_rows(self) -> list[Timepoint]:
        """현재 패널 행들의 값을 Timepoint 리스트로 스냅샷 (빈 행 포함, 비교용).

        ``collect_nirs_timepoints`` 와 달리 빈 이름 행도 None 자리표시자로 포함시켜
        diff 비교에 사용한다.
        """
        out: list[Timepoint] = []
        for r in self._nirs_rows:
            tp = r.to_timepoint()
            if tp is not None:
                out.append(tp)
        return out

    # ──────────────────────────────────────────
    def show_for(self, cfg: SessionConfig, last_result=None) -> None:
        """SessionConfig 의 값을 input box 에 채움.

        ``last_result`` (MetricsResult) 가 주어지면 Min/Peak time + value 도 자동 갱신.
        """
        self._cfg = cfg
        self._last_result = last_result

        # (1) Subject info
        info = cfg.subject_info or {}
        for key, (kind, w) in self._info_inputs.items():
            _set_input(w, kind, info.get(key))

        # 타이틀
        cond = cfg.condition or "?"
        self.title_label.setText(
            f"Session parameters  ·  <b>{cond}</b>  ·  {cfg.file_path.name}"
        )

        # (2) NIRS_VOT timepoints — diff-aware: 현재 행과 cfg 가 일치하면 재구축 skip.
        # show_for 는 result_ready / Apply / condition 변경 등 다양한 경로로 자주 호출된다.
        # 같은 cfg 로 들어온 경우 행을 destroy/recreate 하면 사용자 입력 포커스/스크롤이
        # 깨지므로 (name, start, end, lead, tail) 모두 일치할 때 전체 재구축 회피.
        new_tps = list(cfg.nirs_timepoints())
        existing_tps = self._snapshot_nirs_rows()
        if not _timepoints_equal(new_tps, existing_tps):
            self._clear_nirs_rows()
            for tp in new_tps:
                self._add_nirs_row(tp=tp)

        # (3) HRV timepoints (display 전용 고정 2칸)
        for sess in ("Baseline", "Recovery2"):
            win = cfg.hrv_window(sess)
            self._hrv_inputs[sess]["start"].setTime(_t_to_qtime(win.start) if win else QTime(0, 0, 0))
            self._hrv_inputs[sess]["end"].setTime(_t_to_qtime(win.end)   if win else QTime(0, 0, 0))

        # (5) Min / Peak — last_result 가 있으면 채움
        self._update_minpeak_from_result(last_result)

        # (6) Exercise / TTE — cfg.timepoints["exercise"] 에서
        ex = (cfg.timepoints.get("exercise", {}) or {}) if cfg else {}
        self.tte1_spin.setValue(_time_to_seconds(ex.get("TTE1")))
        self.tte2_spin.setValue(_time_to_seconds(ex.get("TTE2")))
        maint = ex.get("TTE_maintenance_rate")
        try:
            self.maint_spin.setValue(float(maint) if maint is not None else 0.0)
        except (TypeError, ValueError):
            self.maint_spin.setValue(0.0)
        self._update_tte_quality_label()

        self.set_enabled_inputs(True)

    def _update_minpeak_from_result(self, r) -> None:
        """MetricsResult 의 baseline/min/peak 값으로 그룹 input/label 갱신."""
        import math
        if r is None:
            self.baseline_value_spin.setValue(0.0)
            self.min_time_edit.setTime(QTime(0, 0, 0))
            self.peak_time_edit.setTime(QTime(0, 0, 0))
            self.min_value_label.setText("— %")
            self.peak_value_label.setText("— %")
            self.magnitude_label.setText("— %")
            return

        # baseline value (override 체크 상태는 보존 — 사용자 의도)
        bv = getattr(r, "baseline_smo2", float("nan"))
        if isinstance(bv, (int, float)) and not math.isnan(bv):
            self.baseline_value_spin.setValue(float(bv))

        # min
        mt = getattr(r, "min_time", None)
        mv = getattr(r, "min_smo2", float("nan"))
        if mt is not None and not (isinstance(mt, float) and math.isnan(mt)) \
                and hasattr(mt, "hour"):
            self.min_time_edit.setTime(QTime(int(mt.hour), int(mt.minute), int(mt.second)))
        else:
            self.min_time_edit.setTime(QTime(0, 0, 0))
        self.min_value_label.setText(
            f"{mv:.2f} %" if isinstance(mv, (int, float)) and not math.isnan(mv) else "— %"
        )

        # peak
        pt = getattr(r, "peak_time", None)
        pv = getattr(r, "peak_smo2", float("nan"))
        if pt is not None and not (isinstance(pt, float) and math.isnan(pt)) \
                and hasattr(pt, "hour"):
            self.peak_time_edit.setTime(QTime(int(pt.hour), int(pt.minute), int(pt.second)))
        else:
            self.peak_time_edit.setTime(QTime(0, 0, 0))
        self.peak_value_label.setText(
            f"{pv:.2f} %" if isinstance(pv, (int, float)) and not math.isnan(pv) else "— %"
        )

        # magnitude (peak - min)
        mag = getattr(r, "magnitude", float("nan"))
        self.magnitude_label.setText(
            f"{mag:.2f} %  (Peak − Min)"
            if isinstance(mag, (int, float)) and not math.isnan(mag) else "— %"
        )

    def clear(self) -> None:
        self._cfg = None
        self._last_result = None
        for key, (kind, w) in self._info_inputs.items():
            _set_input(w, kind, None)
        # NIRS_VOT 동적 행 모두 제거
        self._clear_nirs_rows()
        # HRV 고정 2칸 비움
        for sess in ("Baseline", "Recovery2"):
            self._hrv_inputs[sess]["start"].setTime(QTime(0, 0, 0))
            self._hrv_inputs[sess]["end"].setTime(QTime(0, 0, 0))
        self.baseline_value_spin.setValue(0.0)
        self.baseline_override_chk.setChecked(False)
        self.min_time_edit.setTime(QTime(0, 0, 0))
        self.peak_time_edit.setTime(QTime(0, 0, 0))
        self.min_value_label.setText("— %")
        self.peak_value_label.setText("— %")
        self.magnitude_label.setText("— %")
        self.tte1_spin.setValue(0)
        self.tte2_spin.setValue(0)
        self.maint_spin.setValue(0.0)
        self.tte_quality_label.setText("")
        self.title_label.setText("Session parameters  ·  (no data)")
        self.set_enabled_inputs(False)

    def set_enabled_inputs(self, enabled: bool) -> None:
        for key, (kind, w) in self._info_inputs.items():
            w.setEnabled(enabled)
        # NIRS_VOT 동적 행 + Add 버튼 enable/disable. HRV 시각은 영구 disabled.
        for r in self._nirs_rows:
            r.set_enabled_all(enabled)
        if hasattr(self, "add_nirs_row_btn"):
            self.add_nirs_row_btn.setEnabled(enabled)
        self.baseline_value_spin.setEnabled(enabled)
        self.baseline_override_chk.setEnabled(enabled)
        self.min_time_edit.setEnabled(enabled)
        self.peak_time_edit.setEnabled(enabled)
        self.tte1_spin.setEnabled(enabled)
        self.tte2_spin.setEnabled(enabled)
        self.maint_spin.setEnabled(enabled)
        self.apply_btn.setEnabled(enabled)
        self.reset_btn.setEnabled(enabled)
        self.auto_detect_btn.setEnabled(enabled)

    # ──────────────────────────────────────────
    def collect_subject_info(self) -> dict:
        out: dict = {}
        for key, (kind, w) in self._info_inputs.items():
            out[key] = _get_input(w, kind)
        return out

    def collect_anchors(self) -> dict[str, Anchor]:
        """현재 NIRS_VOT 동적 행들로부터 timepoint 별 anchor 산출 (per-row lead/tail)."""
        out: dict[str, Anchor] = {}
        for tp in self.collect_nirs_timepoints():
            out[tp.name] = anchor_from_window(
                tp.start, tp.end,
                baseline_lead_sec=tp.lead,
                reperfusion_tail_sec=tp.tail,
            )
        return out

    def collect_overrides(self) -> dict:
        """Baseline/Min/Peak 사용자 override 값 → dict.

        - ``baseline``: 체크박스 활성 시 spinbox 의 float 값. 비활성이면 키 없음 (자동).
        - ``min_time`` / ``peak_time``: ``00:00:00`` 이 아니면 ``datetime.time``.
          호출자(app.py) 가 키 부재 시 ``lf.overrides[sess]`` 에서 제거해 자동 검출로 복귀.
        반환되는 시각은 ``datetime.time`` (날짜 무관).
        """
        out: dict = {}
        if self.baseline_override_chk.isChecked():
            out["baseline"] = float(self.baseline_value_spin.value())
        mt = _qtime_to_t(self.min_time_edit.time())
        if mt != dt.time(0, 0, 0):
            out["min_time"] = mt
        pt = _qtime_to_t(self.peak_time_edit.time())
        if pt != dt.time(0, 0, 0):
            out["peak_time"] = pt
        return out

    def collect_nirs_timepoints(self) -> list[Timepoint]:
        """현재 NIRS_VOT 행들 → Timepoint 리스트. 빈 행/잘못된 행은 자동 제외.

        검증은 ``validate_nirs_timepoints`` 가 별도로 수행 — 여기는 단순 추출.
        """
        out: list[Timepoint] = []
        seen_names: set[str] = set()
        for r in self._nirs_rows:
            tp = r.to_timepoint()
            if tp is None:
                continue
            if tp.name in seen_names:
                continue
            seen_names.add(tp.name)
            out.append(tp)
        return out

    def validate_nirs_timepoints(self) -> tuple[list["Timepoint"], list[str]]:
        """현재 행 검증 후 (유효 timepoints, 경고 메시지 list) 반환.

        체크 항목:
          - 빈 이름 / 시각 0:0:0:0:0:0 → 행 무시 + 경고
          - 중복 이름 → 첫 행만 채택 + 경고
          - start >= end → 경고 (그래도 list 에 포함, anchor 산출 시 음수 윈도우 가능)
          - lead < 0, tail < 0 → 0 으로 clip
        """
        warnings: list[str] = []
        out: list[Timepoint] = []
        seen_names: set[str] = set()
        empty_count = 0
        for i, r in enumerate(self._nirs_rows, start=1):
            name = r.name_edit.text().strip()
            s = _qtime_to_t(r.start_edit.time())
            e = _qtime_to_t(r.end_edit.time())
            if not name and s == dt.time(0, 0, 0) and e == dt.time(0, 0, 0):
                empty_count += 1
                continue
            if not name:
                warnings.append(f"{i}번 행: 이름 없음 — 무시됨")
                continue
            if s == dt.time(0, 0, 0) and e == dt.time(0, 0, 0):
                warnings.append(f"'{name}': 시작/끝 시각 미설정 — 무시됨")
                continue
            if name in seen_names:
                warnings.append(f"'{name}': 중복 이름 — 두 번째 행은 무시됨")
                continue
            if s >= e:
                warnings.append(f"'{name}': 시작({s})이 끝({e}) 이상 — anchor 가 비정상")
            seen_names.add(name)
            out.append(Timepoint(
                name=name, start=s, end=e,
                lead=max(0, int(r.lead_spin.value())),
                tail=max(0, int(r.tail_spin.value())),
            ))
        if empty_count > 0:
            warnings.append(f"빈 행 {empty_count}개 — 무시됨")
        return out, warnings

    def collect_nirs_windows(self) -> dict[str, TimeWindow]:
        """구버전 호환 — 호출하는 코드를 점진적으로 collect_nirs_timepoints 로 이행."""
        return {tp.name: TimeWindow(tp.start, tp.end)
                for tp in self.collect_nirs_timepoints()}

    def collect_hrv_windows(self) -> dict[str, TimeWindow]:
        out: dict[str, TimeWindow] = {}
        for sess in ("Baseline", "Recovery2"):
            s = _qtime_to_t(self._hrv_inputs[sess]["start"].time())
            e = _qtime_to_t(self._hrv_inputs[sess]["end"].time())
            if s == dt.time(0, 0, 0) and e == dt.time(0, 0, 0):
                continue
            out[sess] = TimeWindow(s, e)
        return out

    def collect_exercise(self) -> dict:
        """현재 Exercise/TTE input 값들을 cfg.timepoints['exercise'] 형식의 dict 로.

        Ex1/Ex2 (TimeWindow) 는 panel 에 input 이 없어 기존 cfg 값 보존이 필요하므로
        ``_on_apply`` 에서 setdefault 패턴으로 합친다 — 여기는 새 키만 반환.
        """
        return {
            "TTE1": _seconds_to_time(self.tte1_spin.value()),
            "TTE2": _seconds_to_time(self.tte2_spin.value()),
            "TTE_maintenance_rate": float(self.maint_spin.value()),
        }

    # ──────────────────────────────────────────
    #  TTE quality / comparison helpers
    # ──────────────────────────────────────────
    def _update_tte_quality_label(self) -> None:
        """maintenance_rate 임계값 비교해 경고 표시 (Level 5).

        임계값 70% — [가정]: 운동 프로토콜 신뢰도 컷오프. 운영자/논문 기준으로
        교체 가능. 0% (= 데이터 없음) 인 경우는 메시지 비움.
        """
        m = float(self.maint_spin.value())
        if m <= 0.0:
            self.tte_quality_label.setText("")
            return
        threshold = 70.0
        if m < threshold:
            self.tte_quality_label.setText(
                f"<span style='color:#DC2626; font-weight:bold;'>"
                f"⚠ Maintenance {m:.1f}% &lt; {threshold:.0f}% — "
                f"프로토콜 미준수 가능, 결과 신뢰도 ↓</span>"
                f"<span style='color:#6A737D;'>  [임계값 70% 가정]</span>"
            )
        else:
            self.tte_quality_label.setText(
                f"<span style='color:#16A34A;'>"
                f"✓ Maintenance {m:.1f}% — OK</span>"
                f"<span style='color:#6A737D;'>  [임계값 70% 가정]</span>"
            )

    def update_tte_comparison(self, loaded: dict, current_condition: str | None = None) -> None:
        """모든 로드된 condition 의 TTE 를 비교 그리드에 갱신 (Level 2).

        ``loaded`` — ``{condition: LoadedFile}`` 형식. LoadedFile.config.timepoints[
        'exercise'] 에서 TTE1/TTE2/TTE_maintenance_rate 추출.
        ``current_condition`` — 현재 콤보 선택 condition. 해당 행만 강조.
        """
        # 기존 동적 위젯 제거
        for w in self._tte_compare_value_widgets:
            self._tte_compare_grid.removeWidget(w)
            w.setParent(None)
        self._tte_compare_value_widgets.clear()
        # placeholder 도 일단 제거 (재사용)
        self._tte_compare_grid.removeWidget(self._tte_compare_placeholder)
        self._tte_compare_placeholder.setParent(None)

        rows_with_data = []
        for cond, lf in (loaded or {}).items():
            cfg = getattr(lf, "config", None)
            if cfg is None:
                continue
            ex = (cfg.timepoints.get("exercise", {}) or {})
            rows_with_data.append((cond, ex))

        if not rows_with_data:
            self._tte_compare_placeholder.setText(
                "  로드된 condition 이 없습니다."
            )
            self._tte_compare_grid.addWidget(self._tte_compare_placeholder, 1, 0, 1, 4)
            return

        for r, (cond, ex) in enumerate(rows_with_data, start=1):
            is_current = (cond == current_condition)
            cond_lbl = QLabel(f"<b>{cond}</b>" if is_current else cond)
            if is_current:
                cond_lbl.setStyleSheet("color: #0969DA;")
            self._tte_compare_grid.addWidget(cond_lbl, r, 0)
            self._tte_compare_value_widgets.append(cond_lbl)

            cells = (
                QLabel(_tte_to_str(ex.get("TTE1"))),
                QLabel(_tte_to_str(ex.get("TTE2"))),
                QLabel(_maint_to_str(ex.get("TTE_maintenance_rate"))),
            )
            for c, cell in enumerate(cells, start=1):
                cell.setAlignment(Qt.AlignCenter)
                if is_current:
                    cell.setStyleSheet("font-weight: bold;")
                # maintenance < 70% 빨갛게
                if c == 3:
                    try:
                        v = float(ex.get("TTE_maintenance_rate", 0) or 0)
                        if 0 < v < 70.0:
                            cell.setStyleSheet(
                                ("font-weight: bold; " if is_current else "") + "color: #DC2626;"
                            )
                    except (TypeError, ValueError):
                        pass
                self._tte_compare_grid.addWidget(cell, r, c)
                self._tte_compare_value_widgets.append(cell)

        if len(rows_with_data) < 2:
            n = len(rows_with_data) + 1
            self._tte_compare_placeholder.setText(
                "  다른 condition 도 로드하면 비교됩니다 (HYPER / NOR / HYPO)."
            )
            self._tte_compare_grid.addWidget(self._tte_compare_placeholder, n, 0, 1, 4)

    # ──────────────────────────────────────────
    def _on_apply(self) -> None:
        if self._cfg is None:
            return
        # 포커스 commit — QSpinBox / QTimeEdit / QDateEdit 등은 Enter 또는 focus-out
        # 시점에만 텍스트를 value() 에 반영. 사용자가 input 에 타이핑 후 곧장 Apply
        # 버튼을 누르면 옛 value 로 collect 될 수 있어 강제 interpretText() 호출.
        self._commit_all_inputs()

        # SessionConfig in-memory 갱신
        self._cfg.subject_info = self.collect_subject_info()
        # NIRS_VOT 는 list[Timepoint] (v0.7) — 검증 후 반영, 경고는 메시지박스로
        nirs_tps, tp_warnings = self.validate_nirs_timepoints()
        if tp_warnings:
            QMessageBox.warning(
                self, "Timepoint 검증",
                "다음 항목 확인 필요:\n\n• " + "\n• ".join(tp_warnings)
            )
        self._cfg.timepoints["NIRS_VOT"] = nirs_tps
        # HRV 는 disabled 라 collect_hrv_windows 가 input 의 옛 값 그대로 반환 — OK.
        self._cfg.timepoints["HRV"] = self.collect_hrv_windows()
        # Exercise — Ex1/Ex2 시각은 panel 에 input 이 없어 기존 cfg 값 보존, TTE 만 갱신
        ex = self._cfg.timepoints.setdefault("exercise", {})
        ex.update(self.collect_exercise())
        self.params_applied.emit()
        # 시각 피드백 — 사용자에게 적용 완료 표시
        self._flash_apply_feedback()

    def _flash_apply_feedback(self) -> None:
        """Apply 클릭 시 버튼을 잠깐 초록 ✓ Applied 로 변경 후 원상복귀."""
        self.apply_btn.setText("✓  Applied")
        self.apply_btn.setStyleSheet(self._apply_btn_flash_qss)
        QTimer.singleShot(900, self._restore_apply_btn)

    def _restore_apply_btn(self) -> None:
        self.apply_btn.setText("▶  Apply")
        self.apply_btn.setStyleSheet(self._apply_btn_default_qss)

    def _commit_all_inputs(self) -> None:
        """모든 spinbox/timeedit/dateedit 의 텍스트를 즉시 value 로 commit.

        ``QAbstractSpinBox.interpretText()`` 가 현재 lineEdit 의 텍스트를 파싱해 value()
        에 반영. 포커스 이슈 (Apply 버튼 클릭 직전 input 에 타이핑만 하고 Enter 안 누름)
        를 회피.
        """
        candidates: list = [self.baseline_value_spin,
                            self.min_time_edit, self.peak_time_edit,
                            self.tte1_spin, self.tte2_spin, self.maint_spin]
        # NIRS_VOT 동적 행 — 각 행의 5 위젯
        for r in self._nirs_rows:
            candidates.extend([r.name_edit, r.start_edit, r.end_edit,
                               r.lead_spin, r.tail_spin])
        # HRV (display 전용이지만 commit 안전)
        for sess in ("Baseline", "Recovery2"):
            candidates.append(self._hrv_inputs[sess]["start"])
            candidates.append(self._hrv_inputs[sess]["end"])
        # Subject info 의 spinbox / dateedit 도
        for _key, (kind, w) in self._info_inputs.items():
            if kind in ("int", "float", "date"):
                candidates.append(w)

        for w in candidates:
            try:
                if hasattr(w, "interpretText"):
                    w.interpretText()
            except Exception:  # noqa: BLE001
                pass

    def _on_reset(self) -> None:
        if self._cfg is None:
            return
        # 현재 SessionConfig + last_result 로 다시 채움 (편집 전 상태)
        self.show_for(self._cfg, self._last_result)

    # ──────────────────────────────────────────
    #  파라미터 스냅샷 (xlsx/csv/txt) Save / Load
    # ──────────────────────────────────────────
    def _on_save_params(self) -> None:
        """현재 입력값을 xlsx/csv/txt 중 하나로 저장.

        SessionConfig 가 아직 로드되지 않은 상태에서도 (예: 사용자가 빈 패널에 직접
        값을 채워넣은 뒤) 그대로 저장 가능 — input 위젯의 값만 사용.
        """
        # 기본 파일명 — condition + 이름이 있으면 그 stem 사용
        default_name = "parameters.xlsx"
        if self._cfg is not None and self._cfg.file_path:
            default_name = f"{self._cfg.file_path.stem}_params.xlsx"

        path, selected = QFileDialog.getSaveFileName(
            self,
            "Save parameters",
            default_name,
            "Excel (*.xlsx);;CSV (*.csv);;Text/INI (*.txt)",
        )
        if not path:
            return

        # 사용자가 확장자 없이 입력했고 Excel 필터 선택했다면 .xlsx 보강
        p = Path(path)
        if p.suffix == "":
            if "xlsx" in selected:
                path = path + ".xlsx"
            elif "csv" in selected:
                path = path + ".csv"
            elif "txt" in selected:
                path = path + ".txt"

        # 인풋 commit 후 직렬화
        self._commit_all_inputs()
        try:
            state = parameter_io.serialize(self)
            parameter_io.save(path, state)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "파라미터 저장 실패", str(exc))
            return
        QMessageBox.information(
            self, "파라미터 저장 완료",
            f"{Path(path).name} 에 {len(state)} 개 항목을 저장했습니다."
        )

    def _on_load_params(self) -> None:
        """xlsx/csv/txt 파라미터 스냅샷을 불러와 input 위젯에 반영.

        Apply 까지 자동 실행하지 않으므로, 사용자가 값을 검토한 뒤 직접 ``Apply``.
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load parameters",
            "",
            "Parameter snapshot (*.xlsx *.csv *.txt);;Excel (*.xlsx);;"
            "CSV (*.csv);;Text/INI (*.txt);;All files (*.*)",
        )
        if not path:
            return
        try:
            state = parameter_io.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "파라미터 로드 실패", str(exc))
            return

        # 빈 패널에 로드해도 동작하도록 input 위젯을 enable
        self.set_enabled_inputs(True)

        applied, warnings = parameter_io.apply_to_panel(self, state)

        # 타이틀 갱신
        suffix = Path(path).suffix.lower().lstrip(".")
        self.title_label.setText(
            f"Session parameters  ·  loaded {applied} keys from "
            f"<b>{Path(path).name}</b>  ({suffix})"
        )

        if warnings:
            msg = (
                f"{applied} 개 항목 적용됨. "
                f"다음 항목은 건너뜀:\n\n• "
                + "\n• ".join(warnings[:30])
                + ("" if len(warnings) <= 30 else f"\n… (외 {len(warnings)-30}개)")
            )
            QMessageBox.warning(self, "파라미터 로드 — 경고", msg)


def _h(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet("color: #6A737D; font-size: 9pt;")
    l.setAlignment(Qt.AlignCenter)
    return l
