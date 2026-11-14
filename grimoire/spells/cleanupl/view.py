# SPDX-License-Identifier: GPL-3.0-or-later
"""UninstallerL's page: a table of apps with ticks, sizes and how each is installed, the Uninstall button
(remover.py does the rest), Removed earlier with Reinstall, and a log of what ran. Two tabs (CleanupL's list was
folded in): "All apps" (every app, with search, a source filter, Pick a window and Leftovers only) and "Replaced by
Grimoire" (only the apps Grimoire does the job of, the settings already-removed ones left behind, and the KDE apps
that stay on purpose).
"""

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from grimoire import i18n
from grimoire.fsutil import human
from grimoire.i18n import tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.cleanupl import engine, remover
from grimoire.spells.cleanupl.engine import Found
from grimoire.widgets import plain_tip, segments

SOURCES = (
    ("", tr_noop("grimoire.spells.cleanupl.view", "All apps")),
    ("apt", tr_noop("grimoire.spells.cleanupl.view", "System packages")),
    ("flatpak", tr_noop("grimoire.spells.cleanupl.view", "Flatpaks")),
    ("snap", tr_noop("grimoire.spells.cleanupl.view", "Snaps")),
    ("appimage", tr_noop("grimoire.spells.cleanupl.view", "AppImages")),
    ("user", tr_noop("grimoire.spells.cleanupl.view", "Installed in your home")),
)


def _label(text="", name="", wrap=True) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)  # app names come from packages and menu entries
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class _Row(QTreeWidgetItem):
    """Sizes sort by bytes, not by their text ("800 KB" after "1.5 GB")."""

    def __lt__(self, other):
        col = self.treeWidget().sortColumn() if self.treeWidget() else 0
        if col in (3, 4):
            return (self.data(col, Qt.ItemDataRole.UserRole) or 0) < (other.data(col, Qt.ItemDataRole.UserRole) or 0)
        return self.text(col).lower() < other.text(col).lower()


class _Signals(QObject):
    loaded = Signal(object)
    hunted = Signal(str)


class RemovalPage(QWidget):
    def __init__(self, mode: str = "all"):
        super().__init__()
        self.setObjectName("Page")
        self.mode = mode
        self.found: list[Found] = []
        self.sig = _Signals()
        self.sig.loaded.connect(self._fill)
        self.sig.hunted.connect(self._hunted)
        self.remover = remover.Remover(self)
        self.remover.status.connect(self._say)
        self.remover.line.connect(self._log_line)
        self.remover.finished.connect(lambda changed: self.load() if changed else self._update())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 18)
        lay.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(_label("UninstallerL", "PageHeading"), 1)
        self.tabs = {}
        for key, text in (("all", tr("grimoire.spells.cleanupl.view", "All apps")),
                          ("cleanup", tr("grimoire.spells.cleanupl.view", "Replaced by Grimoire"))):
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setChecked(key == mode)
            b.clicked.connect(lambda _=False, k=key: self.set_mode(k))
            self.tabs[key] = b
            head.addWidget(b)
        segments(list(self.tabs.values()))
        lay.addLayout(head)
        self.lede = _label("", "Muted")
        lay.addWidget(self.lede)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.cleanupl.view", "Search apps"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.source = QComboBox()
        for key, name in SOURCES:
            self.source.addItem(tr("grimoire.spells.cleanupl.view", name), key)
        self.source.currentIndexChanged.connect(self._filter)
        self.hunt_btn = QPushButton(tr("grimoire.spells.cleanupl.view", "Pick a window…"))
        self.hunt_btn.setToolTip(
            tr("grimoire.spells.cleanupl.view", "Click any open window to find the app it belongs to")
        )
        self.hunt_btn.clicked.connect(self._hunt)
        bar.addWidget(self.search, 1)
        bar.addWidget(self.source)
        bar.addWidget(self.hunt_btn)
        self.rescan = QPushButton(tr("grimoire.spells.cleanupl.view", "Rescan"))
        self.rescan.clicked.connect(self.load)
        bar.addWidget(self.rescan)
        lay.addLayout(bar)

        self.table = QTreeWidget()
        self.table.setRootIsDecorated(False)
        self.table.setUniformRowHeights(True)
        self.table.setSortingEnabled(True)
        self.table.setHeaderLabels(
            [
                tr("grimoire.spells.cleanupl.view", "App"),
                tr("grimoire.spells.cleanupl.view", "Grimoire instead"),
                tr("grimoire.spells.cleanupl.view", "Installed as"),
                tr("grimoire.spells.cleanupl.view", "Size"),
                tr("grimoire.spells.cleanupl.view", "Leftovers"),
            ]
        )
        h = self.table.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c, w in ((1, 150), (2, 190), (3, 90), (4, 90)):
            self.table.setColumnWidth(c, w)
        self.table.itemChanged.connect(lambda *_: self._update())
        lay.addWidget(self.table, 1)

        foot = QHBoxLayout()
        self.summary = _label("", "Muted", wrap=False)
        foot.addWidget(self.summary, 1)
        self.left_btn = QPushButton(tr("grimoire.spells.cleanupl.view", "Leftovers only…"))
        self.left_btn.setToolTip(
            tr(
                "grimoire.spells.cleanupl.view",
                "For an app that's already gone or half-removed: just find what it left",
            )
        )
        self.left_btn.clicked.connect(lambda: self.remover.leftovers_only(self.ticked()))
        self.go = QPushButton(tr("grimoire.spells.cleanupl.view", "Uninstall ticked…"))
        self.go.setObjectName("Primary")
        self.go.clicked.connect(lambda: self.remover.start(self.ticked()))
        foot.addWidget(self.left_btn)
        foot.addWidget(self.go)
        lay.addLayout(foot)
        self.status = _label("", "Muted")
        lay.addWidget(self.status)

        self.restore_box = QFrame()
        self.restore_box.setObjectName("Card")
        self.restore_lay = QVBoxLayout(self.restore_box)
        self.restore_lay.setContentsMargins(16, 12, 16, 12)
        lay.addWidget(self.restore_box)
        kept = ", ".join(f"{name} ({tr('grimoire.spells.cleanupl.engine', why)})" for name, why in engine.KEPT)
        self.kept = _label(tr("grimoire.spells.cleanupl.view", "Staying on purpose: {list}").format(list=kept), "Muted")
        lay.addWidget(self.kept)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("Mono")
        self.log.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.log.setMaximumHeight(120)
        self.log.hide()
        lay.addWidget(self.log)
        self._loaded_once = False
        self._apply_mode()

    def set_mode(self, mode: str):
        for k, b in self.tabs.items():
            b.setChecked(k == mode)
        if mode != self.mode:
            self.mode = mode
            self._apply_mode()
            self.load()

    def _apply_mode(self):
        cleanup = self.mode == "cleanup"
        self.lede.setText(
            tr(
                "grimoire.spells.cleanupl.view",
                "Grimoire does these apps' jobs now. Tick the ones you don't need: you see exactly what goes "
                "before anything changes, their settings are offered afterwards, and Reinstall brings any back.",
            )
            if cleanup
            else tr(
                "grimoire.spells.cleanupl.view",
                "Every app on this PC: system packages, Flatpaks, snaps, AppImages and apps installed in your "
                "home. Uninstall, then sweep up what it left behind.",
            )
        )
        for w in (self.source, self.hunt_btn):
            w.setVisible(not cleanup)
        self.kept.setVisible(cleanup)
        self.table.clear()

    def showEvent(self, e):
        super().showEvent(e)
        if not self._loaded_once:
            self._loaded_once = True
            self.load()

    # ------------------------------------------------------------ reading what's installed
    def load(self):
        self.rescan.setEnabled(False)
        self._say(tr("grimoire.spells.cleanupl.view", "Looking at what's installed…"))
        mode = self.mode
        POOL.start(Job(lambda: engine.replaced() if mode == "cleanup" else engine.everything(), self.sig.loaded.emit))

    def _fill(self, found: list[Found]):
        self.found = found
        self.rescan.setEnabled(True)
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.clear()
        for f in found:
            lefts = sum(s for _p, s in f.leftovers)
            it = _Row(
                [
                    f.title,
                    f.replaced_by,
                    engine.describe_source(f),
                    i18n.ltr(human(f.size)) if f.size else "",
                    i18n.ltr(human(lefts)) if lefts else "",
                ]
            )
            it.setData(0, Qt.ItemDataRole.UserRole, f.key)
            it.setData(3, Qt.ItemDataRole.UserRole, f.size or 0)
            it.setData(4, Qt.ItemDataRole.UserRole, lefts)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Unchecked)
            if f.why_not:
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsUserCheckable & ~Qt.ItemFlag.ItemIsEnabled)
                it.setToolTip(0, plain_tip(f.why_not))
            else:
                it.setToolTip(0, plain_tip("\n".join(str(n) for n in f.names)))
            self.table.addTopLevelItem(it)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.blockSignals(False)
        self._filter()
        self._fill_restore()
        engine.remember_status(self.mode, found)
        if not found:
            self._say(
                tr("grimoire.spells.cleanupl.view", "Nothing to clean up: none of the apps Grimoire replaces are here.")
                if self.mode == "cleanup"
                else tr("grimoire.spells.cleanupl.view", "No apps found.")
            )
        elif self.status.text() == tr("grimoire.spells.cleanupl.view", "Looking at what's installed…"):
            self._say("")  # keep "Uninstalled 2 apps." from the run just before
        self._update()

    def _filter(self, *_):
        text = self.search.text().strip().lower()
        src = self.source.currentData() or ""
        by_key = {f.key: f for f in self.found}
        for i in range(self.table.topLevelItemCount()):
            it = self.table.topLevelItem(i)
            f = by_key.get(it.data(0, Qt.ItemDataRole.UserRole))
            hide = bool(
                f
                and (
                    (src and f.source != src)
                    or (text and text not in f.title.lower() and not any(text in str(n).lower() for n in f.names))
                )
            )
            it.setHidden(hide)

    def ticked(self) -> list[Found]:
        by_key = {f.key: f for f in self.found}
        out = []
        for i in range(self.table.topLevelItemCount()):
            it = self.table.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked and not it.isHidden():
                f = by_key.get(it.data(0, Qt.ItemDataRole.UserRole))
                if f:
                    out.append(f)
        return out

    def _update(self):
        picked = self.ticked()
        apps = [f for f in picked if f.source != "files"]
        self.go.setEnabled(bool(apps) and not self.remover.busy)
        self.left_btn.setEnabled(bool(picked) and not self.remover.busy)
        self.summary.setText(
            tr("grimoire.spells.cleanupl.view", "%n ticked", n=len(picked))
            + (
                "   ·   "
                + tr("grimoire.spells.cleanupl.view", "about {size} freed").format(
                    size=i18n.ltr(human(engine.total(picked)))
                )
                if picked and engine.total(picked)
                else ""
            )
        )

    # ------------------------------------------------------------ removed earlier
    def _fill_restore(self):
        while self.restore_lay.count():
            w = self.restore_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        entries = engine.removed()
        self.restore_box.setVisible(bool(entries))
        if not entries:
            return
        self.restore_lay.addWidget(_label(tr("grimoire.spells.cleanupl.view", "Removed earlier"), "SectionTitle"))
        for e in reversed(entries[-8:]):
            row = QHBoxLayout()
            row.addWidget(_label(f"{e['title']}   ·   {', '.join(e['names'])}", "Muted", wrap=False), 1)
            b = QPushButton(tr("grimoire.spells.cleanupl.view", "Reinstall"))
            b.clicked.connect(lambda _=False, e=e: self.remover.reinstall(e))
            row.addWidget(b)
            holder = QWidget()
            holder.setLayout(row)
            row.setContentsMargins(0, 0, 0, 0)
            self.restore_lay.addWidget(holder)

    # ------------------------------------------------------------ pick a window
    def _hunt(self):
        self.hunt_btn.setEnabled(False)
        self._say(
            tr("grimoire.spells.cleanupl.view", "Click the window of the app you want to uninstall (Esc cancels).")
        )
        POOL.start(Job(remover.hunt, self.sig.hunted.emit))

    def _hunted(self, desktop: str):
        self.hunt_btn.setEnabled(True)
        f = engine.owner_of(desktop, self.found) if desktop else None
        if not f:
            self._say(
                tr("grimoire.spells.cleanupl.view", "Couldn't tell which app that window belongs to.")
                if desktop
                else ""
            )
            return
        self.search.clear()
        self.source.setCurrentIndex(0)
        for i in range(self.table.topLevelItemCount()):
            it = self.table.topLevelItem(i)
            if it.data(0, Qt.ItemDataRole.UserRole) == f.key:
                if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    it.setCheckState(0, Qt.CheckState.Checked)
                self.table.scrollToItem(it)
                self.table.setCurrentItem(it)
        self._say(
            tr("grimoire.spells.cleanupl.view", "That window is {name}.").format(name=i18n.isolate(f.title))
            + (" " + f.why_not if f.why_not else "")
        )

    # ------------------------------------------------------------ messages
    def _say(self, msg: str):
        self.status.setText(msg)
        self._update()

    def _log_line(self, text: str):
        self.log.show()
        self.log.appendPlainText(text)
