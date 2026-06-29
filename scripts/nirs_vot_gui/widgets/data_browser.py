"""좌측 Sessions 패널 — 데이터 로드 버튼 + **실제 로드된 항목**만 표시하는 트리.

v0.6.9 변경:
- 이전 폴더 스캔 (discover_sessions) 제거. 폴더 안에 _Calf 파일이 있다고 자동으로
  트리에 표시하는 건 "로드되지 않은 항목"까지 보여서 혼란 → 사용자가 명시적으로 로드한
  항목만 트리에 등장하도록.
- ``set_loaded(loaded_dict)`` 메서드를 도입. ``NirsVotTab.loaded`` 의 dict 를 직접 받아
  트리를 빌드. ``measurement_loaded`` / ``measurement_cleared`` 시그널과 1:1 동기화.
- 시작 시 / clear 시 placeholder 만 표시.

v0.6.4 그대로:
- 헤더에 ``📂 Open data file…`` / ``📁 Open folder…`` 두 버튼 (실제 다이얼로그는
  NirsVotTab 이 처리).
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


SESSION_NAMES_FALLBACK = ("Baseline", "Recovery2")  # cfg 없을 때만 사용


class DataBrowser(QWidget):
    """헤더(로드 버튼) + 트리(현재 로드된 항목).

    트리는 ``NirsVotTab.loaded`` (dict[str, LoadedFile]) 와 1:1 동기.
    """

    session_selected = Signal(str, str, str)              # subject, condition, session
    condition_selected = Signal(str)                      # condition 노드 더블클릭
    open_file_clicked = Signal()
    open_folder_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loaded_snapshot: dict = {}  # condition → 표시용 메타

        # ── 루트 레이아웃 ──
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 헤더: 로드 버튼 행 ──
        header = QHBoxLayout()
        header.setContentsMargins(6, 6, 6, 4)
        header.setSpacing(6)

        self.open_file_btn = QPushButton("📂  Open data file…")
        self.open_file_btn.setToolTip("단일 _Calf 시계열 파일을 선택해 로드")
        self.open_file_btn.clicked.connect(self.open_file_clicked.emit)
        header.addWidget(self.open_file_btn)

        self.open_folder_btn = QPushButton("📁  Open folder…")
        self.open_folder_btn.setToolTip(
            "폴더의 모든 *_Calf 시계열을 condition 자동 추정으로 일괄 로드"
        )
        self.open_folder_btn.clicked.connect(self.open_folder_clicked.emit)
        header.addWidget(self.open_folder_btn)

        root.addLayout(header)

        # ── 트리 뷰 ──
        self.tree = QTreeView()
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)

        self._model = QStandardItemModel(self)
        self.tree.setModel(self._model)
        self.tree.doubleClicked.connect(self._on_double_clicked)

        root.addWidget(self.tree, stretch=1)

        self._render_empty()

    # ──────────────────────────────────────────────
    #  공개 API: 로드된 데이터 dict 동기화
    # ──────────────────────────────────────────────
    def set_loaded(self, loaded: dict) -> None:
        """``NirsVotTab.loaded`` (condition → LoadedFile) 를 받아 트리 빌드."""
        self._loaded_snapshot = dict(loaded) if loaded else {}
        self._model.clear()
        if not self._loaded_snapshot:
            self._render_empty()
            return
        self._render_loaded()
        self.tree.expandAll()

    def clear(self) -> None:
        self._loaded_snapshot = {}
        self._model.clear()
        self._render_empty()

    def refresh_times(self) -> None:
        """기존 트리 그대로, session 노드의 시각 라벨만 cfg 의 최신값으로 갱신.

        ParameterPanel.Apply 또는 그래프 vline 드래그로 ``cfg.timepoints["NIRS_VOT"]``
        가 in-memory 갱신된 직후 호출. 트리 모델을 재빌드하지 않으므로 expand/select
        상태를 보존한다. 또한 subject_info["Name"] 도 변경됐을 수 있어 루트 라벨도 갱신.
        """
        if not self._loaded_snapshot:
            return
        root = self._model.invisibleRootItem()
        for r in range(root.rowCount()):
            subj = root.child(r)
            if subj is None:
                continue
            data = subj.data(Qt.UserRole) or {}
            if data.get("type") != "subject":
                continue
            # subject 라벨 갱신 (Name 변경 시)
            new_name = ""
            for lf in self._loaded_snapshot.values():
                cfg = getattr(lf, "config", None)
                if cfg is not None and cfg.subject_info:
                    new_name = (
                        cfg.subject_info.get("Name")
                        or cfg.subject_info.get("ID(Protocol)")
                        or ""
                    )
                    if new_name:
                        break
            subj.setText(f"🧍  {new_name or 'Subject'}")

            for c in range(subj.rowCount()):
                cond_item = subj.child(c)
                if cond_item is None:
                    continue
                cdata = cond_item.data(Qt.UserRole) or {}
                cond = cdata.get("condition")
                if cond is None:
                    continue
                lf = self._loaded_snapshot.get(cond)
                cfg = getattr(lf, "config", None) if lf else None
                for s in range(cond_item.rowCount()):
                    sess_item = cond_item.child(s)
                    if sess_item is None:
                        continue
                    sdata = sess_item.data(Qt.UserRole) or {}
                    if sdata.get("type") != "session":
                        continue
                    sess_name = sdata.get("session")
                    if not sess_name:
                        continue
                    clock = self._session_clock(sess_name, cfg)
                    sess_item.setText(f"📍  {sess_name}   {clock}")

    # ──────────────────────────────────────────────
    #  내부: 트리 렌더
    # ──────────────────────────────────────────────
    def _render_empty(self) -> None:
        root = self._model.invisibleRootItem()
        item = QStandardItem(
            "(no data loaded)\n"
            "  • [📂 Open data file…] : 단일 파일 로드\n"
            "  • [📁 Open folder…] : 폴더 일괄 로드"
        )
        item.setEditable(False)
        item.setEnabled(False)
        root.appendRow(item)

    def _render_loaded(self) -> None:
        root = self._model.invisibleRootItem()

        # subject 추출 (첫 LoadedFile 의 config.subject_info 의 Name 또는 ID)
        subject_name = ""
        for lf in self._loaded_snapshot.values():
            cfg = getattr(lf, "config", None)
            if cfg is not None and cfg.subject_info:
                subject_name = (
                    cfg.subject_info.get("Name")
                    or cfg.subject_info.get("ID(Protocol)")
                    or ""
                )
                if subject_name:
                    break
        if not subject_name:
            subject_name = "Subject"

        subj_item = QStandardItem(f"🧍  {subject_name}")
        subj_item.setEditable(False)
        subj_item.setData({"type": "subject"}, Qt.UserRole)
        root.appendRow(subj_item)

        # condition 노드들 — loaded dict 의 정렬 (NOR < HYPO < HYPER 우선, 그 외 알파벳)
        order = {"NOR": 0, "HYPO": 1, "HYPER": 2}
        sorted_conds = sorted(
            self._loaded_snapshot.keys(),
            key=lambda c: (order.get(c, 999), c),
        )

        for cond in sorted_conds:
            lf = self._loaded_snapshot[cond]
            calf_path = getattr(lf, "path", None)
            cfg = getattr(lf, "config", None)
            calf_name = calf_path.name if calf_path else "(no calf)"
            cfg_name = cfg.file_path.name if cfg else "(no cfg)"

            cond_item = QStandardItem(f"🫁  {cond}    [{calf_name}]")
            cond_item.setEditable(False)
            cond_item.setData({"type": "condition", "condition": cond}, Qt.UserRole)
            cond_item.setToolTip(
                f"calf:   {calf_name}\n"
                f"config: {cfg_name}"
            )
            subj_item.appendRow(cond_item)

            # cfg 의 NIRS_VOT timepoint 이름들로 session 노드 생성. 없으면 fallback.
            session_names = (
                [tp.name for tp in cfg.nirs_timepoints() if tp.name]
                if cfg is not None and hasattr(cfg, "nirs_timepoints") else []
            )
            if not session_names:
                session_names = list(SESSION_NAMES_FALLBACK)

            for sess_name in session_names:
                clock = self._session_clock(sess_name, cfg)
                sess_item = QStandardItem(f"📍  {sess_name}   {clock}")
                sess_item.setEditable(False)
                sess_item.setData({
                    "type": "session",
                    "condition": cond,
                    "session": sess_name,
                }, Qt.UserRole)
                cond_item.appendRow(sess_item)

    @staticmethod
    def _session_clock(session: str, cfg) -> str:
        if cfg is None:
            return "—"
        win = cfg.nirs_vot_window(session) if hasattr(cfg, "nirs_vot_window") else None
        if win is None:
            return "—"
        return f"{_t2s(win.start)} → {_t2s(win.end)}"

    # ──────────────────────────────────────────────
    def _on_double_clicked(self, idx: QModelIndex) -> None:
        item = self._model.itemFromIndex(idx)
        if item is None:
            return
        data = item.data(Qt.UserRole) or {}
        kind = data.get("type")
        if kind == "session":
            self.session_selected.emit("", data["condition"], data["session"])
        elif kind == "condition":
            self.condition_selected.emit(data["condition"])


def _t2s(t) -> str:
    if t is None:
        return "—"
    return f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}"
