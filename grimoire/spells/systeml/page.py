# SPDX-License-Identifier: GPL-3.0-or-later
"""SystemL page: Grimoire's system monitor (in place of KDE System Monitor). Overview graphs, processes, per-app
history, services, startup apps, disks and background alerts, each a panel picked from the list on the left.

One Sampler reads the machine on a worker thread once a second while the page is on screen; nothing is sampled
while it's hidden. Actions that can take a moment (or ask for the password) run on the pool too.
"""
import getpass
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QAbstractItemModel, QDateTime, QLocale, QModelIndex, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QScrollArea, QSizePolicy, QStackedWidget, QTreeView, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget, QDialog)

from grimoire.fsutil import human
from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.systeml import probe, system
from grimoire.spells.systeml.alertview import AlertsPanel
from grimoire.spells.systeml.bidi import lead, ltr
from grimoire.spells.systeml.graph import Bar, CoreGrid, Graph, Spark
from grimoire.spells.systeml.history import History, per_app
from grimoire.widgets import Switch

REPO = Path(__file__).resolve().parents[3]
ME = getpass.getuser()
PANELS = [("overview", tr_noop("grimoire.spells.systeml.page", "Overview"), "system"),
          ("procs", tr_noop("grimoire.spells.systeml.page", "Processes"), "list"),
          ("apps", tr_noop("grimoire.spells.systeml.page", "Apps & history"), "clock"),
          ("services", tr_noop("grimoire.spells.systeml.page", "Services"), "boot"),
          ("startup", tr_noop("grimoire.spells.systeml.page", "Startup apps"), "splash"),
          ("disks", tr_noop("grimoire.spells.systeml.page", "Disks"), "drive"),
          ("alerts", tr_noop("grimoire.spells.systeml.page", "Alerts"), "bell")]
PRIORITIES = [(tr_noop("grimoire.spells.systeml.page", "Very high"), -10),
              (tr_noop("grimoire.spells.systeml.page", "High"), -5),
              (tr_noop("grimoire.spells.systeml.page", "Normal"), 0),
              (tr_noop("grimoire.spells.systeml.page", "Low"), 10),
              (tr_noop("grimoire.spells.systeml.page", "Very low"), 19)]
# psutil's process states and systemd's unit and unit-file states: shown in the app's language (English as systemd
# and psutil write them); the raw value stays the data
STATES = frozenset((
    tr_noop("grimoire.spells.systeml.page", "running"), tr_noop("grimoire.spells.systeml.page", "sleeping"),
    tr_noop("grimoire.spells.systeml.page", "disk-sleep"), tr_noop("grimoire.spells.systeml.page", "stopped"),
    tr_noop("grimoire.spells.systeml.page", "tracing-stop"), tr_noop("grimoire.spells.systeml.page", "zombie"),
    tr_noop("grimoire.spells.systeml.page", "dead"), tr_noop("grimoire.spells.systeml.page", "idle"),
    tr_noop("grimoire.spells.systeml.page", "parked"), tr_noop("grimoire.spells.systeml.page", "waking"),
    tr_noop("grimoire.spells.systeml.page", "active"), tr_noop("grimoire.spells.systeml.page", "inactive"),
    tr_noop("grimoire.spells.systeml.page", "failed"), tr_noop("grimoire.spells.systeml.page", "activating"),
    tr_noop("grimoire.spells.systeml.page", "deactivating"), tr_noop("grimoire.spells.systeml.page", "reloading"),
    tr_noop("grimoire.spells.systeml.page", "exited"), tr_noop("grimoire.spells.systeml.page", "waiting"),
    tr_noop("grimoire.spells.systeml.page", "listening"), tr_noop("grimoire.spells.systeml.page", "auto-restart"),
    tr_noop("grimoire.spells.systeml.page", "mounted"), tr_noop("grimoire.spells.systeml.page", "plugged")))
STARTUP = frozenset((
    tr_noop("grimoire.spells.systeml.page", "enabled"), tr_noop("grimoire.spells.systeml.page", "disabled"),
    tr_noop("grimoire.spells.systeml.page", "static"), tr_noop("grimoire.spells.systeml.page", "indirect"),
    tr_noop("grimoire.spells.systeml.page", "masked"), tr_noop("grimoire.spells.systeml.page", "generated"),
    tr_noop("grimoire.spells.systeml.page", "alias"), tr_noop("grimoire.spells.systeml.page", "enabled-runtime"),
    tr_noop("grimoire.spells.systeml.page", "linked")))


def state_text(value: str) -> str:
    """A process or unit state in words; unknown ones as systemd/psutil wrote them."""
    return tr("grimoire.spells.systeml.page", value) if value in STATES else value


def startup_text(value: str) -> str:
    return tr("grimoire.spells.systeml.page", value) if value in STARTUP else value


def when_text(t: float) -> str:
    """A short date and time in the app's language (month names from QLocale, not the C locale)."""
    return QLocale().toString(QDateTime.fromSecsSinceEpoch(int(t)), "MMM dd HH:mm")


class _Signals(QObject):
    sampled = Signal(object)
    acted = Signal(object)        # (what, message, ok, then, quiet)
    failed = Signal(object)       # failed service count
    log = Signal(object)          # (unit, text)
    services = Signal(object)
    startup = Signal(object)
    drives = Signal(object)
    info = Signal(object)


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _rate(n: float) -> str:
    return human(n) + "/s"


def _launch(module: str, *args: str):
    """Start another Grimoire window (VaultL, OptimizeL) from this checkout or installed copy."""
    env = dict(os.environ, PYTHONPATH=f"{REPO}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"))
    subprocess.Popen([sys.executable, "-m", module, *args], env=env, start_new_session=True)


def _tree(headers: list[str]) -> QTreeWidget:
    t = QTreeWidget()
    t.setHeaderLabels(headers)
    t.setRootIsDecorated(False)
    t.setUniformRowHeights(True)
    t.setAlternatingRowColors(False)
    t.setSortingEnabled(True)
    t.header().setStretchLastSection(True)
    return t


class NumItem(QTreeWidgetItem):
    """Sorts by the number stored in UserRole, not by the formatted text."""

    def __lt__(self, other):
        col = self.treeWidget().sortColumn() if self.treeWidget() else 0
        a, b = self.data(col, Qt.ItemDataRole.UserRole), other.data(col, Qt.ItemDataRole.UserRole)
        if a is not None and b is not None:
            return a < b
        return self.text(col).lower() < other.text(col).lower()


# ---------------------------------------------------------------- processes
COLS = [(tr_noop("grimoire.spells.systeml.page", "Name"), "name"), ("PID", "pid"),
        (tr_noop("grimoire.spells.systeml.page", "User"), "user"), (tr_noop("grimoire.spells.systeml.page", "CPU"), "cpu"),
        (tr_noop("grimoire.spells.systeml.page", "Memory"), "mem"), (tr_noop("grimoire.spells.systeml.page", "Disk"), "io"),
        (tr_noop("grimoire.spells.systeml.page", "Threads"), "threads"),
        (tr_noop("grimoire.spells.systeml.page", "Priority"), "nice"),
        (tr_noop("grimoire.spells.systeml.page", "Status"), "status")]
NUMERIC = {"pid", "cpu", "mem", "io", "threads", "nice"}


class Node:
    __slots__ = ("row", "parent", "children", "pos")

    def __init__(self, row):
        self.row, self.parent, self.children, self.pos = row, None, [], 0


class ProcModel(QAbstractItemModel):
    """Processes as a flat list or as a tree under their parents, filtered and sorted here (so a refresh keeps
    the order steady)."""

    def __init__(self):
        super().__init__()
        self.rows: list[dict] = []
        self.top: list[Node] = []
        self.nodes: dict[int, Node] = {}
        self.visible: set[int] = set()
        self.tree = False
        self.query = ""
        self.show_kernel = False
        self.only_mine = False
        self.col, self.order = 3, Qt.SortOrder.DescendingOrder

    def set_rows(self, rows):
        self.rows = rows
        self.rebuild()

    def rebuild(self):
        self.beginResetModel()
        rows = [r for r in self.rows if (self.show_kernel or not r["kernel"]) and (not self.only_mine or r["user"] == ME)]
        nodes = {r["pid"]: Node(r) for r in rows}
        q = self.query.lower().strip()
        keep = None
        if q:
            keep = {p for p, n in nodes.items() if q in n.row["name"].lower() or q in n.row["cmd"].lower()
                    or q == str(p) or q in probe.app_name(n.row).lower()}
        self.shown = len(nodes) if keep is None else len(keep)
        top = []
        if self.tree:
            for n in nodes.values():
                par = nodes.get(n.row["ppid"])
                if par is not None and par is not n:
                    n.parent = par
                    par.children.append(n)
                else:
                    top.append(n)
            if keep is not None:                      # keep matches and the parents that lead to them
                shown = set()
                for p in keep:
                    n = nodes[p]
                    while n is not None and n.row["pid"] not in shown:
                        shown.add(n.row["pid"])
                        n = n.parent
                for n in nodes.values():
                    n.children = [c for c in n.children if c.row["pid"] in shown]
                top = [n for n in top if n.row["pid"] in shown]
                keep = shown
        else:
            top = [n for p, n in nodes.items() if keep is None or p in keep]
        self.visible = set(nodes) if keep is None else keep
        key = COLS[self.col][1]
        rev = self.order == Qt.SortOrder.DescendingOrder

        def sort(lst):
            lst.sort(key=lambda n: (n.row.get(key) is None, n.row.get(key) if key in NUMERIC
                                    else str(n.row.get(key, "")).lower()), reverse=rev)
            for i, n in enumerate(lst):
                n.pos = i
                if n.children:
                    sort(n.children)
        sort(top)
        self.top = top
        self.nodes = nodes
        self.endResetModel()

    # Qt model plumbing
    def _list(self, parent: QModelIndex):
        return parent.internalPointer().children if parent.isValid() else self.top

    def index(self, row, col, parent=QModelIndex()):
        lst = self._list(parent)
        if 0 <= row < len(lst) and 0 <= col < len(COLS):
            return self.createIndex(row, col, lst[row])
        return QModelIndex()

    def parent(self, index=QModelIndex()):
        if not index.isValid():
            return QModelIndex()
        p = index.internalPointer().parent
        return QModelIndex() if p is None else self.createIndex(p.pos, 0, p)

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid() and parent.column() > 0:
            return 0
        return len(self._list(parent))

    def columnCount(self, parent=QModelIndex()):
        return len(COLS)

    def headerData(self, section, orient, role=Qt.ItemDataRole.DisplayRole):
        if orient == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return tr("grimoire.spells.systeml.page", COLS[section][0])
        if orient == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.TextAlignmentRole and section >= 3:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r, key = index.internalPointer().row, COLS[index.column()][1]
        if role == Qt.ItemDataRole.DisplayRole:
            v = r.get(key)
            if key == "cpu":
                return ltr(f"{v:.1f}%")
            if key == "mem":
                return ltr(human(v))
            if key == "io":
                return "" if not v else ltr(_rate(v))
            if key == "nice":
                return next((tr("grimoire.spells.systeml.page", n) for n, x in PRIORITIES if x == v), ltr(str(v)))
            if key == "status":
                return state_text(v)
            return str(v)
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() >= 3:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole and key == "name":
            return r["cmd"] or r["name"]
        if role == Qt.ItemDataRole.UserRole:
            return r["pid"]
        return None

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        self.col, self.order = column, order
        self.rebuild()

    def row_of(self, index) -> dict | None:
        return index.internalPointer().row if index.isValid() else None

    def find(self, pid: int) -> QModelIndex:
        n = self.nodes.get(pid)
        if n is None or pid not in self.visible:     # filtered out: an index to it would act on a hidden row
            return QModelIndex()
        return self.createIndex(n.pos, 0, n)


class ProcPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.collapsed: set[int] = set()
        self._restoring = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.systeml.page", "Search name, command or PID"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        bar.addWidget(self.search, 1)
        self.tree_btn = QCheckBox(tr("grimoire.spells.systeml.page", "Tree"))
        self.mine_btn = QCheckBox(tr("grimoire.spells.systeml.page", "Only mine"))
        self.kernel_btn = QCheckBox(tr("grimoire.spells.systeml.page", "Kernel threads"))
        for b in (self.tree_btn, self.mine_btn, self.kernel_btn):
            b.toggled.connect(self._options)
            bar.addWidget(b)
        lay.addLayout(bar)

        self.model = ProcModel()
        self.view = QTreeView()
        self.view.setObjectName("FileDetails")
        self.view.setModel(self.model)
        self.view.setUniformRowHeights(True)
        self.view.setRootIsDecorated(False)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(3, Qt.SortOrder.DescendingOrder)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._menu)
        self.view.collapsed.connect(lambda i: self._restoring or self.collapsed.add(self.model.row_of(i)["pid"]))
        self.view.expanded.connect(lambda i: self._restoring or self.collapsed.discard(self.model.row_of(i)["pid"]))
        h = self.view.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c, w in ((1, 80), (2, 100), (3, 70), (4, 90), (5, 90), (6, 70), (7, 90), (8, 90)):
            h.resizeSection(c, w)
        lay.addWidget(self.view, 1)

        acts = QHBoxLayout()
        self.info = _label("", "Muted")
        acts.addWidget(self.info, 1)
        self.prio_btn = QPushButton(tr("grimoire.spells.systeml.page", "Priority"))
        self.prio_btn.setMenu(self._prio_menu())
        self.pause_btn = QPushButton(tr("grimoire.spells.systeml.page", "Pause"))
        self.pause_btn.clicked.connect(lambda: self._signal("CONT" if self._sel_status() == "stopped" else "STOP"))
        self.kill_btn = QPushButton(tr("grimoire.spells.systeml.page", "Force quit"))
        self.kill_btn.clicked.connect(lambda: self._signal("KILL"))
        self.end_btn = QPushButton(tr("grimoire.spells.systeml.page", "End process"))
        self.end_btn.setObjectName("Primary")
        self.end_btn.clicked.connect(lambda: self._signal("TERM"))
        for b in (self.prio_btn, self.pause_btn, self.kill_btn, self.end_btn):
            acts.addWidget(b)
        lay.addLayout(acts)
        self.view.selectionModel().selectionChanged.connect(self._sel_changed)
        self._sel_changed()

    def _prio_menu(self) -> QMenu:
        m = QMenu(self)
        for name, nice in PRIORITIES:
            name = tr("grimoire.spells.systeml.page", name)
            m.addAction(f"{name} ({nice:+d})" if nice else f"{name} (0)", lambda n=nice: self._renice(n))
        return m

    def selected(self) -> dict | None:
        idx = self.view.currentIndex()
        return self.model.row_of(idx.siblingAtColumn(0)) if idx.isValid() and self.view.selectionModel().hasSelection() \
            else None

    def _sel_status(self):
        r = self.selected()
        return r["status"] if r else ""

    def _sel_changed(self, *_):
        r = self.selected()
        for b in (self.prio_btn, self.pause_btn, self.kill_btn, self.end_btn):
            b.setEnabled(bool(r) and not r["kernel"] and not r["self"])
        stopped = bool(r) and r["status"] == "stopped"
        if r and system.is_protected(r["name"]):         # the session needs it; only Resume and Priority stay
            self.kill_btn.setEnabled(False)
            self.end_btn.setEnabled(False)
            self.pause_btn.setEnabled(stopped)
        self.pause_btn.setText(tr("grimoire.spells.systeml.page", "Resume") if stopped
                               else tr("grimoire.spells.systeml.page", "Pause"))
        if r:
            line = tr("grimoire.spells.systeml.page", "{name} · PID {pid} · started {when}").format(
                name=r["name"], pid=r["pid"], when=when_text(r["started"]))
            self.info.setText(line + (f" · {r['exe']}" if r["exe"] else ""))
        else:
            self.info.setText(tr("grimoire.spells.systeml.page", "%n process(es)",
                                 n=getattr(self.model, "shown", len(self.model.rows))))

    def _filter(self, text):
        self.model.query = text
        self.refresh()

    def _options(self):
        self.model.tree = self.tree_btn.isChecked()
        self.model.only_mine = self.mine_btn.isChecked()
        self.model.show_kernel = self.kernel_btn.isChecked()
        self.view.setRootIsDecorated(self.model.tree)
        self.refresh()

    def set_rows(self, rows):
        self.model.rows = rows
        self.refresh()

    def refresh(self):
        """Rebuild while keeping the selection, the collapsed branches and the scroll position."""
        r = self.selected()
        scroll = self.view.verticalScrollBar().value()
        self._restoring = True
        self.model.rebuild()
        if self.model.tree:
            self.view.expandAll()
            for pid in self.collapsed:
                idx = self.model.find(pid)
                if idx.isValid():
                    self.view.collapse(idx)
        self._restoring = False
        if r:
            idx = self.model.find(r["pid"])
            if idx.isValid():
                self.view.setCurrentIndex(idx)
        self.view.verticalScrollBar().setValue(scroll)
        self._sel_changed()

    def show_query(self, text: str):
        self.search.setText(text)

    def _menu(self, pos):
        idx = self.view.indexAt(pos)
        if not idx.isValid():
            return
        self.view.setCurrentIndex(idx)
        r = self.selected()
        if not r or r["kernel"] or r["self"]:
            return
        m = QMenu(self)
        guarded = system.is_protected(r["name"])
        m.addAction(tr("grimoire.spells.systeml.page", "End process"), lambda: self._signal("TERM")).setEnabled(not guarded)
        m.addAction(tr("grimoire.spells.systeml.page", "Force quit"), lambda: self._signal("KILL")).setEnabled(not guarded)
        m.addAction(tr("grimoire.spells.systeml.page", "Resume") if r["status"] == "stopped"
                    else tr("grimoire.spells.systeml.page", "Pause"),
                    lambda: self._signal("CONT" if r["status"] == "stopped" else "STOP")) \
            .setEnabled(r["status"] == "stopped" or not guarded)
        m.addMenu(self._prio_menu()).setText(tr("grimoire.spells.systeml.page", "Priority"))
        m.addSeparator()
        m.addAction(tr("grimoire.spells.systeml.page", "Show only this app"),
                    lambda: self.search.setText(probe.app_name(r)))
        if r["exe"]:
            m.addAction(tr("grimoire.spells.systeml.page", "Open its folder"),
                        lambda: _launch("grimoire.spells.vaultl", r["exe"]))
        m.exec(self.view.viewport().mapToGlobal(pos))

    def _signal(self, sig: str):
        r = self.selected()
        if not r:
            return
        if sig != "CONT" and system.is_protected(r["name"]):
            return
        if sig in ("TERM", "KILL", "STOP"):
            title = {"KILL": tr("grimoire.spells.systeml.page", "Force quit {name}"),
                     "TERM": tr("grimoire.spells.systeml.page", "End {name}"),
                     "STOP": tr("grimoire.spells.systeml.page", "Pause {name}")}[sig]
            ask = {"KILL": tr("grimoire.spells.systeml.page", "Force quit {name} (PID {pid})? Unsaved work in it will "
                              "be lost."),
                   "TERM": tr("grimoire.spells.systeml.page", "End {name} (PID {pid})? It gets the chance to save and "
                              "close."),
                   "STOP": tr("grimoire.spells.systeml.page", "Pause {name} (PID {pid})? It freezes until you resume "
                              "it; if other apps wait on it, they freeze too.")}[sig].format(name=r["name"], pid=r["pid"])
            if r["user"] != ME:
                ask += "\n\n" + tr("grimoire.spells.systeml.page", "It belongs to another user, so this asks for your "
                                   "password.")
            if QMessageBox.question(self, title.format(name=r["name"]), ask) != QMessageBox.StandardButton.Yes:
                return
        self.page.act(f"{r['name']}", lambda: system.send(r["pid"], sig, r["started"]))

    def _renice(self, nice: int):
        r = self.selected()
        if r:
            self.page.act(tr("grimoire.spells.systeml.page", "{name} priority").format(name=r["name"]),
                          lambda: system.renice(r["pid"], nice, r["started"]))


# ---------------------------------------------------------------- apps & history
WINDOWS = [(tr_noop("grimoire.spells.systeml.page", "Now"), 0), (tr_noop("grimoire.spells.systeml.page", "Hour"), 60),
           (tr_noop("grimoire.spells.systeml.page", "Day"), 24 * 60),
           (tr_noop("grimoire.spells.systeml.page", "Week"), 7 * 24 * 60)]


class AppsPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.window_min = 0
        self.procs: list[dict] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        bar = QHBoxLayout()
        bar.setSpacing(0)
        self.segs = []
        for i, (name, mins) in enumerate(WINDOWS):
            b = QPushButton(tr("grimoire.spells.systeml.page", name))
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setProperty("pos", "first" if i == 0 else "last" if i == len(WINDOWS) - 1 else "mid")
            b.clicked.connect(lambda _=False, m=mins: self.set_window(m))
            bar.addWidget(b)
            self.segs.append((b, mins))
        bar.addSpacing(16)
        self.note = _label("", "Muted", wrap=True)
        bar.addWidget(self.note, 1)
        lay.addLayout(bar)
        self.table = _tree([""] * 6)
        self.table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.header().setStretchLastSection(False)
        self.table.itemSelectionChanged.connect(self._show_app)
        self.table.itemDoubleClicked.connect(lambda it, _c: self.page.find_app(it.text(0)))
        lay.addWidget(self.table, 1)
        sparks = QHBoxLayout()
        self.cpu_spark = Spark(tr("grimoire.spells.systeml.page", "CPU"), top=None, height=90)
        self.mem_spark = Spark(tr("grimoire.spells.systeml.page", "MEMORY"), top=None, height=90)
        sparks.addWidget(self.cpu_spark)
        sparks.addWidget(self.mem_spark)
        self.sparks = QWidget()
        self.sparks.setLayout(sparks)
        sparks.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.sparks)
        self.set_window(0)

    def set_window(self, mins: int):
        self.window_min = mins
        for b, m in self.segs:
            b.setChecked(m == mins)
        if mins == 0:
            heads = [tr("grimoire.spells.systeml.page", "App"), tr("grimoire.spells.systeml.page", "CPU"), "",
                     tr("grimoire.spells.systeml.page", "Memory"), "", tr("grimoire.spells.systeml.page", "Processes")]
        else:
            heads = [tr("grimoire.spells.systeml.page", "App"), tr("grimoire.spells.systeml.page", "Avg CPU"),
                     tr("grimoire.spells.systeml.page", "Peak CPU"), tr("grimoire.spells.systeml.page", "Avg memory"),
                     tr("grimoire.spells.systeml.page", "Peak memory"), tr("grimoire.spells.systeml.page", "Minutes")]
        self.table.setHeaderLabels(heads)
        self.sparks.setVisible(mins > 0)
        for c in (2, 4):
            self.table.setColumnHidden(c, mins == 0)
        self.fill()

    def set_procs(self, procs):
        self.procs = procs
        if self.window_min == 0:
            self.fill()

    def fill(self):
        h = self.page.history
        sel = self.table.currentItem().text(0) if self.table.currentItem() else None
        self.table.setSortingEnabled(False)
        self.table.clear()
        if self.window_min == 0:
            rows = sorted(per_app(self.procs).items(), key=lambda kv: kv[1][0], reverse=True)
            for app, (cpu, mem, n) in rows:
                self._row([app, f"{cpu:.1f}%", "", human(mem), "", str(n)], [app.lower(), cpu, 0, mem, 0, n])
            self.note.setText(tr("grimoire.spells.systeml.page", "Live, summed over every process of each app. "
                                 "Double-click one to see its processes."))
        else:
            for o in h.summary(self.window_min):
                self._row([o["app"], f"{o['cpu']:.1f}%", f"{o['cpu_peak']:.0f}%", human(o["mem"]), human(o["mem_peak"]),
                           str(o["minutes"])],
                          [o["app"].lower(), o["cpu"], o["cpu_peak"], o["mem"], o["mem_peak"], o["minutes"]])
            span = h.span()
            self.note.setText(tr("grimoire.spells.systeml.page", "History is recorded while SystemL is open (busiest "
                                 "apps, once a minute, kept a week). {h} h {m} min recorded so far.").format(
                                     h=int(span // 60), m=int(span % 60)) if span else
                              tr("grimoire.spells.systeml.page", "Nothing recorded yet: history builds up minute by "
                                 "minute while SystemL is open."))
        self.table.setSortingEnabled(True)
        self.table.sortItems(1, Qt.SortOrder.DescendingOrder)
        if sel:
            hit = self.table.findItems(sel, Qt.MatchFlag.MatchExactly, 0)
            if hit:
                self.table.setCurrentItem(hit[0])

    def _row(self, texts, values):
        it = NumItem(texts[:1] + [ltr(t) for t in texts[1:]])
        for c, v in enumerate(values):
            it.setData(c, Qt.ItemDataRole.UserRole, v)
            if c:
                it.setTextAlignment(c, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.addTopLevelItem(it)

    def _show_app(self):
        it = self.table.currentItem()
        if not it or not self.window_min:
            return
        series = self.page.history.series(it.text(0), self.window_min)
        self.cpu_spark.label = tr("grimoire.spells.systeml.page", "{app} · CPU").format(app=it.text(0))
        self.mem_spark.label = tr("grimoire.spells.systeml.page", "{app} · MEMORY").format(app=it.text(0))
        self.cpu_spark.set_values([s[1] for s in series] or [0, 0])
        self.mem_spark.set_values([s[2] / 2**20 for s in series] or [0, 0])


# ---------------------------------------------------------------- services
class ServicesPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.user = False
        self.units: list[dict] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        bar = QHBoxLayout()
        bar.setSpacing(0)
        self.segs = []
        for i, (name, user) in enumerate(((tr("grimoire.spells.systeml.page", "System"), False),
                                          (tr("grimoire.spells.systeml.page", "Yours"), True))):
            b = QPushButton(name)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setProperty("pos", "first" if i == 0 else "last")
            b.clicked.connect(lambda _=False, u=user: self.set_user(u))
            bar.addWidget(b)
            self.segs.append((b, user))
        bar.addSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.systeml.page", "Search services"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.fill)
        bar.addWidget(self.search, 1)
        bar.addSpacing(12)
        self.running = QCheckBox(tr("grimoire.spells.systeml.page", "Running only"))
        self.failed = QCheckBox(tr("grimoire.spells.systeml.page", "Failed only"))
        for c in (self.running, self.failed):
            c.toggled.connect(self.fill)
            bar.addWidget(c)
            bar.addSpacing(12)
        lay.addLayout(bar)
        self.table = _tree([tr("grimoire.spells.systeml.page", "Service"), tr("grimoire.spells.systeml.page", "State"),
                            tr("grimoire.spells.systeml.page", "Startup"), tr("grimoire.spells.systeml.page", "Memory"),
                            tr("grimoire.spells.systeml.page", "Description")])
        self.table.header().setStretchLastSection(True)
        for c, w in ((0, 300), (1, 130), (2, 100), (3, 90)):
            self.table.header().resizeSection(c, w)
        self.table.itemSelectionChanged.connect(self._sel)
        lay.addWidget(self.table, 1)
        acts = QHBoxLayout()
        self.info = _label("", "Muted")
        acts.addWidget(self.info, 1)
        self.btns = {}
        for action, text in (("log", tr("grimoire.spells.systeml.page", "Log")),
                             ("enable", tr("grimoire.spells.systeml.page", "Start at boot")),
                             ("disable", tr("grimoire.spells.systeml.page", "Don't start at boot")),
                             ("restart", tr("grimoire.spells.systeml.page", "Restart")),
                             ("stop", tr("grimoire.spells.systeml.page", "Stop")),
                             ("start", tr("grimoire.spells.systeml.page", "Start"))):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, a=action: self._do(a))
            acts.addWidget(b)
            self.btns[action] = b
        lay.addLayout(acts)
        self.set_user(False)

    def set_user(self, user: bool):
        self.user = user
        for b, u in self.segs:
            b.setChecked(u == user)
        self.load()

    def load(self):
        self.info.setText(tr("grimoire.spells.systeml.page", "Loading services…"))
        user, sig = self.user, self.page.sig
        POOL.start(Job(lambda: (user, system.services(user)), sig.services.emit))

    def loaded(self, result):
        user, units = result
        if user != self.user:
            return
        self.units = units
        self.fill()

    def fill(self):
        sel = self.table.currentItem().text(0) if self.table.currentItem() else None
        q = self.search.text().lower().strip()
        self.table.setSortingEnabled(False)
        self.table.clear()
        shown = 0
        for u in self.units:
            if q and q not in u["unit"].lower() and q not in u["description"].lower():
                continue
            if self.running.isChecked() and u["active"] != "active":
                continue
            if self.failed.isChecked() and u["active"] != "failed":
                continue
            state = u["active"] if u["sub"] in (u["active"], "dead") else f"{u['active']} ({u['sub']})"
            shown_state = state_text(u["active"]) if u["sub"] in (u["active"], "dead") else \
                f"{state_text(u['active'])} ({state_text(u['sub'])})"
            it = NumItem([u["unit"].removesuffix(".service"), shown_state, startup_text(u["enabled"]),
                          ltr(human(u["memory"])) if u["memory"] else "", u["description"]])
            for c, v in enumerate([u["unit"].lower(), state, u["enabled"], u["memory"] or 0, u["description"].lower()]):
                it.setData(c, Qt.ItemDataRole.UserRole, v)
            it.setData(0, Qt.ItemDataRole.UserRole + 1, u)
            it.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.addTopLevelItem(it)
            shown += 1
        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        if sel:
            hit = self.table.findItems(sel, Qt.MatchFlag.MatchExactly, 0)
            if hit:
                self.table.setCurrentItem(hit[0])
        failed = sum(1 for u in self.units if u["active"] == "failed")
        self.count_text = tr("grimoire.spells.systeml.page", "{shown} of %n service(s)", n=len(self.units)).format(
            shown=shown) + (" · " + tr("grimoire.spells.systeml.page", "%n failed", n=failed) if failed else "")
        self._sel()

    def current(self) -> dict | None:
        it = self.table.currentItem()
        return it.data(0, Qt.ItemDataRole.UserRole + 1) if it else None

    def _sel(self):
        u = self.current()
        active = bool(u) and u["active"] in ("active", "activating", "reloading")
        core = bool(u) and system.is_core(u["unit"])
        en = u["enabled"] if u else ""
        self.btns["log"].setEnabled(bool(u))
        self.btns["start"].setEnabled(bool(u) and not active)
        self.btns["stop"].setEnabled(active and not core)
        self.btns["restart"].setEnabled(active and not core)
        self.btns["enable"].setEnabled(en == "disabled")
        self.btns["disable"].setEnabled(en == "enabled" and not core)
        if u and core:
            self.info.setText(tr("grimoire.spells.systeml.page", "{unit} keeps the system running, so it can't be "
                                 "stopped or restarted from here").format(unit=u["unit"]))
        elif u:
            self.info.setText(u["unit"] if self.user else tr(
                "grimoire.spells.systeml.page", "{unit} · system changes ask for your password").format(unit=u["unit"]))
        else:
            self.info.setText(getattr(self, "count_text", ""))

    def _do(self, action: str):
        u = self.current()
        if not u:
            return
        unit, user = u["unit"], self.user
        if action == "log":
            POOL.start(Job(lambda: (unit, system.unit_log(user, unit)), self.page.sig.log.emit))
            return
        if action in ("stop", "disable", "restart") and system.is_core(unit):
            return
        ask = {"stop": tr("grimoire.spells.systeml.page", "Stop {unit}? Whatever depends on it may stop working."),
               "disable": tr("grimoire.spells.systeml.page", "Stop starting {unit} at boot? Whatever depends on it may "
                             "stop working."),
               "restart": tr("grimoire.spells.systeml.page", "Restart {unit}? Whatever depends on it may stop working "
                             "for a moment.")}
        if action in ask and QMessageBox.question(self, unit, ask[action].format(unit=unit)) \
                != QMessageBox.StandardButton.Yes:
            return
        self.page.act(unit, lambda: system.unit_action(user, action, unit), then=self.load)


# ---------------------------------------------------------------- startup apps
class StartupRow(QFrame):
    def __init__(self, panel, e: dict):
        super().__init__()
        self.setObjectName("Row")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 16, 12)
        lay.setSpacing(14)
        text = QVBoxLayout()
        text.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(_label(e["name"], "RowTitle"))
        source = tr("grimoire.spells.systeml.page", "System") if e["source"] == "System" else \
            tr("grimoire.spells.systeml.page", "Yours")
        top.addWidget(_label(source.upper(), "Badge"))
        if e["essential"]:
            top.addWidget(_label(tr("grimoire.spells.systeml.page", "NEEDED BY PLASMA"), "Badge"))
        top.addStretch(1)
        text.addLayout(top)
        if e["comment"]:
            text.addWidget(lead(_label(e["comment"], "Muted", wrap=True)))
        cmd = lead(_label(e["exec"], "Value"))
        cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(cmd)
        lay.addLayout(text, 1)
        if e["removable"]:
            rm = QPushButton(tr("grimoire.spells.systeml.page", "Remove"))
            rm.clicked.connect(lambda: panel.remove(e))
            lay.addWidget(rm, 0, Qt.AlignmentFlag.AlignVCenter)
        sw = Switch()
        sw.setChecked(e["on"])
        sw.setEnabled(not e["essential"])
        sw.toggled.connect(lambda on: panel.flip(e, on))
        lay.addWidget(sw, 0, Qt.AlignmentFlag.AlignVCenter)


class StartupPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        bar = QHBoxLayout()
        bar.addWidget(_label(tr("grimoire.spells.systeml.page", "Apps and helpers that start when you log in. "
                                "Turning one off writes an override in {folder}, the same way Plasma's settings do; "
                                "turning it back on removes it.").format(folder="~/.config/autostart"),
                             "Muted", wrap=True), 1)
        add = QPushButton(tr("grimoire.spells.systeml.page", "Add app…"))
        add.clicked.connect(self.add)
        bar.addWidget(add, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(bar)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        self.col = QVBoxLayout(inner)
        self.col.setContentsMargins(0, 0, 10, 10)
        self.col.setSpacing(8)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

    def load(self):
        POOL.start(Job(system.startup_apps, self.page.sig.startup.emit))

    def loaded(self, entries):
        while self.col.count():
            w = self.col.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not entries:
            self.col.addWidget(_label(tr("grimoire.spells.systeml.page", "Nothing starts at login besides Plasma "
                                         "itself."), "Muted"))
        for e in entries:
            self.col.addWidget(StartupRow(self, e))
        self.col.addStretch(1)

    def flip(self, e, on):
        self.page.act(e["name"], lambda: system.set_startup(e["file"], on), then=self.load, quiet=True)

    def remove(self, e):
        if QMessageBox.question(self, e["name"], tr("grimoire.spells.systeml.page", "Stop {name} from starting at "
                                                    "login and move its entry to the Trash?").format(name=e["name"])) \
                == QMessageBox.StandardButton.Yes:
            self.page.act(e["name"], lambda: system.remove_startup(e["file"]), then=self.load)

    def add(self):
        apps = system.installed_apps()
        names = [a["name"] for a in apps]
        name, ok = QInputDialog.getItem(self, tr("grimoire.spells.systeml.page", "Add to startup"),
                                        tr("grimoire.spells.systeml.page", "Start this app when you log in:"),
                                        names, 0, False)
        if ok and name:
            app = apps[names.index(name)]
            self.page.act(name, lambda: system.add_startup(app["path"]) and tr("grimoire.spells.systeml.page", "added"),
                          then=self.load)


# ---------------------------------------------------------------- disks
class DisksPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.rate_labels: dict[str, QLabel] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        self.col = QVBoxLayout(inner)
        self.col.setContentsMargins(0, 0, 10, 10)
        self.col.setSpacing(10)
        scroll.setWidget(inner)
        lay.addWidget(scroll)

    def load(self):
        POOL.start(Job(system.drives, self.page.sig.drives.emit))

    def loaded(self, drives):
        while self.col.count():
            w = self.col.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.rate_labels = {}
        for d in drives:
            card = QFrame()
            card.setObjectName("Row")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(20, 16, 20, 16)
            cl.setSpacing(10)
            top = QHBoxLayout()
            top.addWidget(_label(d["model"], "RowTitle"))
            top.addWidget(_label(d["kind"].upper(), "Badge"))
            top.addWidget(_label(human(d["size"]), "Muted"))
            top.addStretch(1)
            rate = _label("", "Value")
            top.addWidget(rate)
            self.rate_labels[d["name"]] = rate
            cl.addLayout(top)
            for p in d["parts"]:
                row = QHBoxLayout()
                row.setSpacing(12)
                name = p["label"] or p["name"]
                fs = p["fs"] or tr("grimoire.spells.systeml.page", "no file system")
                row.addWidget(_label(f"{name}  ·  {fs}  ·  {human(p['size'])}"), 2)
                mount = p["mounts"][0] if p["mounts"] else ""
                row.addWidget(_label(mount or tr("grimoire.spells.systeml.page", "not mounted"), "Muted"), 2)
                bar = Bar()
                if p["total"]:
                    bar.set(p["used"] / p["total"])
                    row.addWidget(bar, 2)
                    row.addWidget(_label(tr("grimoire.spells.systeml.page", "{used} of {total}").format(
                        used=ltr(human(p["used"])), total=ltr(human(p["total"]))), "Muted"), 1)
                else:
                    row.addStretch(3)
                if mount and mount != "[SWAP]":
                    b = QPushButton(tr("grimoire.spells.systeml.page", "Open"))
                    b.clicked.connect(lambda _=False, m=mount: _launch("grimoire.spells.vaultl", m))
                    row.addWidget(b)
                    if d["removable"]:
                        u = QPushButton(tr("grimoire.spells.systeml.page", "Unmount"))
                        u.clicked.connect(lambda _=False, n=p["name"]: self.page.act(
                            n, lambda: system.unmount(n), then=self.load))
                        row.addWidget(u)
                cl.addLayout(row)
            self.col.addWidget(card)
        self.col.addStretch(1)

    def set_rates(self, rates: dict):
        for name, lab in self.rate_labels.items():
            r, w = rates.get(name, (0, 0))
            lab.setText(tr("grimoire.spells.systeml.page", "read {read}   write {write}").format(read=ltr(_rate(r)),
                                                                                              write=ltr(_rate(w))))


# ---------------------------------------------------------------- overview
class OverviewPanel(QScrollArea):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 20)
        col.setSpacing(14)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.tiles = {}
        for key, label in (("cpu", tr("grimoire.spells.systeml.page", "CPU")),
                           ("mem", tr("grimoire.spells.systeml.page", "Memory")),
                           ("swap", tr("grimoire.spells.systeml.page", "Swap")),
                           ("procs", tr("grimoire.spells.systeml.page", "Processes")),
                           ("failed", tr("grimoire.spells.systeml.page", "Failed services"))):
            tile = QFrame()
            tile.setObjectName("Stat")
            tl = QVBoxLayout(tile)
            tl.setContentsMargins(18, 12, 18, 12)
            tl.setSpacing(0)
            num = _label("–", "StatNum")
            tl.addWidget(num)
            tl.addWidget(_label(label.upper(), "StatLabel"))
            tiles.addWidget(tile, 1)
            self.tiles[key] = num
        col.addLayout(tiles)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.cpu = Graph(tr("grimoire.spells.systeml.page", "CPU"))
        self.mem = Graph(tr("grimoire.spells.systeml.page", "Memory"), fmt=human, top=1,
                         labels=(tr("grimoire.spells.systeml.page", "used"), tr("grimoire.spells.systeml.page", "cache")),
                         two=True)
        self.swap = Graph(tr("grimoire.spells.systeml.page", "Swap"), fmt=human, top=1)
        self.disk = Graph(tr("grimoire.spells.systeml.page", "Disk"), fmt=_rate, top=None,
                          labels=(tr("grimoire.spells.systeml.page", "read"), tr("grimoire.spells.systeml.page", "write")),
                          two=True)
        self.net = Graph(tr("grimoire.spells.systeml.page", "Network"), fmt=_rate, top=None,
                         labels=(tr("grimoire.spells.systeml.page", "down"), tr("grimoire.spells.systeml.page", "up")),
                         two=True)
        self.gpu = Graph("GPU", labels=("", ""))
        self.temp = Graph(tr("grimoire.spells.systeml.page", "Temperature"), fmt=lambda v: f"{v:.0f}°C", top=100,
                          labels=(tr("grimoire.spells.systeml.page", "CPU"), "GPU"), two=True)
        self.load = Graph(tr("grimoire.spells.systeml.page", "Load average"), fmt=lambda v: f"{v:.2f}", top=None)
        for i, g in enumerate((self.cpu, self.mem, self.disk, self.net, self.gpu, self.temp, self.swap, self.load)):
            grid.addWidget(g, i // 2, i % 2)
        col.addLayout(grid)

        col.addWidget(_label(tr("grimoire.spells.systeml.page", "Cores"), "SectionTitle"))
        self.cores = CoreGrid(probe.CORES)
        col.addWidget(self.cores)

        lower = QHBoxLayout()
        lower.setSpacing(12)
        self.top_cpu = self._top_box(tr("grimoire.spells.systeml.page", "Busiest right now"))
        self.top_mem = self._top_box(tr("grimoire.spells.systeml.page", "Biggest in memory"))
        lower.addWidget(self.top_cpu[0], 1)
        lower.addWidget(self.top_mem[0], 1)
        col.addLayout(lower)

        col.addWidget(_label(tr("grimoire.spells.systeml.page", "Quick actions"), "SectionTitle"))
        qa = QHBoxLayout()
        qa.setSpacing(10)
        for text, tip, fn in (
                (tr("grimoire.spells.systeml.page", "Empty swap into RAM"),
                 tr("grimoire.spells.systeml.page", "Moves everything in swap back into memory when it fits (asks for "
                    "your password). Handy after a big game when the desktop feels sluggish."), page.empty_swap),
                (tr("grimoire.spells.systeml.page", "Restart Plasma desktop"),
                 tr("grimoire.spells.systeml.page", "Restarts the panel and desktop without logging out. Open apps "
                    "keep running."), page.restart_plasma),
                (tr("grimoire.spells.systeml.page", "Clear failed services"),
                 tr("grimoire.spells.systeml.page", "Forgets your user services' failed state so the count starts "
                    "fresh."), page.reset_failed),
                (tr("grimoire.spells.systeml.page", "Open OptimizeL"),
                 tr("grimoire.spells.systeml.page", "Speed tweaks for this PC as on/off switches."),
                 page.open_optimizel)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            qa.addWidget(b)
        qa.addStretch(1)
        col.addLayout(qa)

        col.addWidget(_label(tr("grimoire.spells.systeml.page", "This PC"), "SectionTitle"))
        info = QGridLayout()
        info.setHorizontalSpacing(24)
        info.setVerticalSpacing(6)
        self.info_box = info
        col.addLayout(info)
        col.addStretch(1)
        self.setWidget(inner)
        page.sig.info.connect(self._fill_info)
        POOL.start(Job(probe.system_info, page.sig.info.emit))

    def _fill_info(self, rows):
        for i, (k, v) in enumerate(rows):
            self.info_box.addWidget(_label(k.upper(), "StatLabel"), i, 0)
            val = lead(_label(v))
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.info_box.addWidget(val, i, 1)
        self.info_box.setColumnStretch(1, 1)

    def _top_box(self, title):
        box = QFrame()
        box.setObjectName("Row")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(18, 14, 18, 14)
        bl.setSpacing(6)
        bl.addWidget(_label(title.upper(), "StatLabel"))
        rows = []
        for _ in range(5):
            r = QHBoxLayout()
            name = QPushButton("")
            name.setObjectName("Link")
            name.setToolTip(tr("grimoire.spells.systeml.page", "Show its processes"))
            name.clicked.connect(lambda _=False, b=name: b.text() and self.page.find_app(b.text()))
            val = _label("", "Value")
            r.addWidget(name, 1)
            r.addWidget(val)
            bl.addLayout(r)
            rows.append((name, val))
        return box, rows

    def update_snap(self, s: dict):
        self.cpu.push(s["cpu"], note=f"{s['freq'] / 1000:.2f} GHz" if s["freq"] else "")
        self.mem.top = s["mem_total"]
        of = tr("grimoire.spells.systeml.page", "of {total}")
        self.mem.push(s["mem_used"], s["mem_cache"], note=of.format(total=ltr(human(s["mem_total"]))))
        self.swap.top = s["swap_total"] or 1
        self.swap.push(s["swap_used"], note=of.format(total=ltr(human(s["swap_total"]))) if s["swap_total"]
                       else tr("grimoire.spells.systeml.page", "no swap"))
        self.disk.push(s["disk_read"], s["disk_write"])
        self.net.push(s["net_down"], s["net_up"])
        g = s["gpu"]
        self.gpu.setVisible(g is not None)
        if g:
            self.gpu.title = g["name"].replace("NVIDIA GeForce ", "")
            parts = [tr("grimoire.spells.systeml.page", "{used} of {total}").format(
                used=ltr(human(g["vram_used"])), total=ltr(human(g["vram_total"])))]
            if g["power"] is not None:
                parts.append(f"{g['power']:.0f} W")
            self.gpu.push(g["util"] or 0, note="  ·  ".join(parts))
        t = s["temps"]
        self.temp.push(t.get("CPU", 0), t.get("GPU", 0),
                       note="  ".join(f"{k} {v:.0f}°" for k, v in t.items() if k not in ("CPU", "GPU"))[:40])
        self.load.push(s["load"][0], note=tr("grimoire.spells.systeml.page", "5 min {five} · 15 min {fifteen}").format(
            five=f"{s['load'][1]:.2f}", fifteen=f"{s['load'][2]:.2f}"))
        self.cores.push(s["cores"])
        self.tiles["cpu"].setText(f"{s['cpu']:.0f}%")
        self.tiles["mem"].setText(f"{s['mem_used'] / 2**30:.1f} GB")
        self.tiles["swap"].setText(f"{s['swap_used'] / 2**30:.1f} GB" if s["swap_total"] else "—")
        if "procs" in s:
            self.tiles["procs"].setText(str(sum(1 for p in s["procs"] if not p["kernel"])))
            apps = per_app(s["procs"])
            for rows, key, fmt in ((self.top_cpu[1], 0, lambda v: f"{v:.1f}%"), (self.top_mem[1], 1, human)):
                top = sorted(apps.items(), key=lambda kv: kv[1][key], reverse=True)[:5]
                for (name, val), (app, nums) in zip(rows, top + [("", (0, 0, 0))] * (5 - len(top))):
                    name.setText(app)
                    val.setText(fmt(nums[key]) if app else "")


# ---------------------------------------------------------------- the page
class SystemLPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.sig = _Signals()
        self.sampler = probe.Sampler()
        self.history = History()
        self._busy = False
        self._tick = 0
        self._disk_prev, self._disk_t = None, 0.0

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        nav = QFrame()
        nav.setObjectName("SubNav")
        nav.setFixedWidth(210)
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(12, 26, 12, 16)
        nl.setSpacing(2)
        nl.addWidget(_label("SystemL", "Title"))
        nl.addSpacing(12)
        nl.addWidget(_label(tr("grimoire.spells.systeml.page", "MONITOR"), "NavSection"))
        self.nav = {}
        for pid, name, icon in PANELS:
            if pid == "services":
                nl.addSpacing(10)
                nl.addWidget(_label(tr("grimoire.spells.systeml.page", "MANAGE"), "NavSection"))
            b = QPushButton(glyph(icon, 18), "  " + tr("grimoire.spells.systeml.page", name).replace("&", "&&"))
            b.setObjectName("SubNavItem")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, p=pid: self.show_panel(p))
            nl.addWidget(b)
            self.nav[pid] = b
        nl.addStretch(1)
        self.uptime = _label("", "Tiny")
        self.uptime.setWordWrap(True)
        nl.addWidget(self.uptime)
        root.addWidget(nav)

        right = QVBoxLayout()
        right.setContentsMargins(32, 26, 32, 18)
        right.setSpacing(14)
        self.heading = _label("", "PageHeading")
        right.addWidget(self.heading)
        self.stack = QStackedWidget()
        self.panels = {"overview": OverviewPanel(self), "procs": ProcPanel(self), "apps": AppsPanel(self),
                       "services": ServicesPanel(self), "startup": StartupPanel(self), "disks": DisksPanel(self),
                       "alerts": AlertsPanel(self)}
        for p in self.panels.values():
            self.stack.addWidget(p)
        right.addWidget(self.stack, 1)
        self.toast = _label("", "Toast", wrap=True)
        self.toast.hide()
        right.addWidget(self.toast)
        self._toast_timer = QTimer(self, singleShot=True, interval=7000, timeout=self.toast.hide)
        root.addLayout(right, 1)

        self.sig.sampled.connect(self._sampled)
        self.sig.acted.connect(self._acted)
        self.sig.failed.connect(lambda n: self.panels["overview"].tiles["failed"].setText(str(n)))
        self.sig.log.connect(lambda r: self._show_log(*r))
        self.sig.services.connect(self.panels["services"].loaded)
        self.sig.startup.connect(self.panels["startup"].loaded)
        self.sig.drives.connect(self.panels["disks"].loaded)
        self.timer = QTimer(self, interval=1000, timeout=self._sample)
        self.show_panel("overview")
        POOL.start(Job(system.failed_count, self.sig.failed.emit))

    # ------------------------------------------------------------ sampling
    def showEvent(self, e):
        self.timer.start()
        self._sample()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def _sample(self):
        if self._busy:
            return
        self._busy = True
        sampler, history = self.sampler, self.history
        prev, prev_t = self._disk_prev, self._disk_t

        def work():
            try:
                snap = sampler.sample()
                history.add(snap["procs"])
                now = time.monotonic()
                snap["disk_counters"], snap["disk_rates"] = system.disk_rates(prev, now - prev_t if prev else 0)
                snap["disk_t"] = now
                return snap
            except Exception:              # always answer, so _busy clears and the next tick tries again
                traceback.print_exc()
                return None
        POOL.start(Job(work, self.sig.sampled.emit))

    def _sampled(self, s):
        self._busy = False
        if s is None:
            return
        self._tick += 1
        self._disk_prev, self._disk_t = s["disk_counters"], s["disk_t"]
        self.uptime.setText(tr("grimoire.spells.systeml.page", "Up {time}\nLoad {load}").format(
            time=probe.uptime_text(s["uptime"]), load=f"{s['load'][0]:.2f}"))
        current = self.stack.currentWidget()
        self.panels["overview"].update_snap(s)               # graphs keep their history even when not shown
        if current is self.panels["procs"] and (self._tick % 2 == 0 or not self.panels["procs"].model.rows):
            self.panels["procs"].set_rows(s["procs"])
        elif current is not self.panels["procs"]:
            self.panels["procs"].model.rows = s["procs"]
        if current is self.panels["apps"]:
            self.panels["apps"].set_procs(s["procs"])
        else:
            self.panels["apps"].procs = s["procs"]
        if current is self.panels["disks"]:
            self.panels["disks"].set_rates(s["disk_rates"])

    # ------------------------------------------------------------ navigation
    def show_panel(self, pid: str):
        for p, b in self.nav.items():
            b.setChecked(p == pid)
        self.heading.setText(tr("grimoire.spells.systeml.page", next(n for p, n, _ in PANELS if p == pid)))
        panel = self.panels[pid]
        self.stack.setCurrentWidget(panel)
        if pid == "procs":
            panel.refresh()
        elif pid == "apps":
            panel.fill()
        elif pid in ("services", "startup", "disks", "alerts"):
            panel.load()

    def find_app(self, app: str):
        self.show_panel("procs")
        self.panels["procs"].show_query(app)

    # ------------------------------------------------------------ actions
    def act(self, what: str, fn, then=None, quiet=False):
        """Run fn on the pool; report how it went in the toast, then call then() (e.g. reload a list)."""
        def work():
            try:
                return (what, fn() or tr("grimoire.spells.systeml.page", "done"), True, then, quiet)
            except Exception as err:                 # shown to the user, not a crash
                msg = str(err)                       # "cancelled" is run_root's id for a dismissed password prompt
                return (what, tr("grimoire.spells.systeml.page", "cancelled") if msg == "cancelled" else msg, False,
                        then, quiet)
        POOL.start(Job(work, self.sig.acted.emit))

    def _acted(self, result):
        what, msg, ok, then, quiet = result
        if not ok or not quiet:
            self.say(tr("grimoire.spells.systeml.page", "{what}: {result}").format(what=what, result=msg) if ok else
                     tr("grimoire.spells.systeml.page", "Couldn't change {what}: {error}").format(what=what, error=msg))
        if then:
            then()

    def say(self, text: str):
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start()

    def _show_log(self, unit: str, text: str):
        d = QDialog(self)
        d.setWindowTitle(tr("grimoire.spells.systeml.page", "{unit} log").format(unit=unit))
        d.resize(900, 560)
        lay = QVBoxLayout(d)
        view = QPlainTextEdit(text)
        view.setReadOnly(True)
        view.setObjectName("Mono")
        view.setLayoutDirection(Qt.LayoutDirection.LeftToRight)     # journal lines: never mirrored in RTL
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(view)
        view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
        d.show()

    def empty_swap(self):
        if QMessageBox.question(self, tr("grimoire.spells.systeml.page", "Empty swap"),
                                tr("grimoire.spells.systeml.page", "Move everything in swap back into RAM? This asks "
                                   "for your password and only runs when there's room.")) \
                == QMessageBox.StandardButton.Yes:
            self.act(tr("grimoire.spells.systeml.page", "Swap"), lambda: system.run_root("swap-refresh")
                     or tr("grimoire.spells.systeml.page", "emptied into RAM"))

    def restart_plasma(self):
        if QMessageBox.question(self, tr("grimoire.spells.systeml.page", "Restart Plasma"),
                                tr("grimoire.spells.systeml.page", "Restart the Plasma desktop and panel? Your open "
                                   "apps keep running.")) == QMessageBox.StandardButton.Yes:
            self.act("Plasma", lambda: subprocess.run(["systemctl", "--user", "restart", "plasma-plasmashell"],
                                                      check=True, timeout=60)
                     and tr("grimoire.spells.systeml.page", "restarted"))

    def reset_failed(self):
        def work():
            subprocess.run(["systemctl", "--user", "reset-failed"], check=True, timeout=30)
            return tr("grimoire.spells.systeml.page", "cleared · %n failed system service(s) left",
                      n=system.failed_count())
        self.act(tr("grimoire.spells.systeml.page", "Failed services"), work,
                 then=lambda: POOL.start(Job(system.failed_count, self.sig.failed.emit)))

    def open_optimizel(self):
        win = self.window()
        if hasattr(win, "pages") and "optimizel" in win.pages:
            win.open("optimizel")
        else:
            _launch("grimoire.standalone", "optimizel")
