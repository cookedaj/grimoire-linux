# SPDX-License-Identifier: GPL-3.0-or-later
"""SystemL's Logs panel (in place of KSystemLog): the systemd journal with filters (level, unit or app, boot, time
range, text), follow mode, a details pane with every field, copy and export.

journalctl runs on journal.Reader's thread; a timer here drains what arrived into the model, so the window never
waits on the journal. Log text is untrusted: it's cleaned in journal.py and only ever shown as plain text (table
cells and a QPlainTextEdit; no tooltips, which Qt would render as rich text).
"""
import time
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QDateTime, QModelIndex, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QCompleter, QDateTimeEdit, QFileDialog, QHBoxLayout,
                               QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QSplitter,
                               QTreeView, QVBoxLayout, QWidget)

from grimoire.fsutil import free_name
from grimoire.i18n import isolate, ltr, tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.systeml import journal
from grimoire.widgets import Switch, segments

MAX_ROWS = 200_000                  # follow mode drops the oldest lines past this
COLS = [tr_noop("grimoire.spells.systeml.logview", "Time"), tr_noop("grimoire.spells.systeml.logview", "Level"),
        tr_noop("grimoire.spells.systeml.logview", "Source"), tr_noop("grimoire.spells.systeml.logview", "Message")]
LEVEL_FILTERS = [(tr_noop("grimoire.spells.systeml.logview", "All levels"), None),
                 (tr_noop("grimoire.spells.systeml.logview", "Critical and worse"), 2),
                 (tr_noop("grimoire.spells.systeml.logview", "Errors and worse"), 3),
                 (tr_noop("grimoire.spells.systeml.logview", "Warnings and worse"), 4),
                 (tr_noop("grimoire.spells.systeml.logview", "Notices and worse"), 5),
                 (tr_noop("grimoire.spells.systeml.logview", "Everything but debug"), 6)]
RANGES = [(tr_noop("grimoire.spells.systeml.logview", "Any time"), None),
          (tr_noop("grimoire.spells.systeml.logview", "Last 15 minutes"), 15 * 60),
          (tr_noop("grimoire.spells.systeml.logview", "Last hour"), 3600),
          (tr_noop("grimoire.spells.systeml.logview", "Last 24 hours"), 86400),
          (tr_noop("grimoire.spells.systeml.logview", "Last 7 days"), 7 * 86400),
          (tr_noop("grimoire.spells.systeml.logview", "Custom range…"), "custom")]
LINES = [500, 2000, 10000, 50000]
MUTED = QColor("#8c8c8c")


class _Signals(QObject):
    boots = Signal(object)          # (scope, boots)
    sources = Signal(object)        # (scope, names)
    exported = Signal(object)       # (ok, path or error)


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class LogModel(QAbstractTableModel):
    """Journal entries, oldest first; only the first line of each message shows in the table."""

    def __init__(self):
        super().__init__()
        self.rows: list[dict] = []
        self.bold = QFont()
        self.bold.setBold(True)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLS)

    def headerData(self, section, orient, role=Qt.ItemDataRole.DisplayRole):
        if orient == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return tr("grimoire.spells.systeml.logview", COLS[section])
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        e, c = self.rows[index.row()], index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if c == 0:
                return journal.stamp(e["t"])
            if c == 1:
                return journal.level_text(e["prio"])
            if c == 2:
                return e["source"] + (f"[{e['pid']}]" if e["pid"] else "")
            msg = e["msg"]
            cut = msg.find("\n")
            return (msg[:cut] + " …") if cut >= 0 else msg[:2000]
        if role == Qt.ItemDataRole.FontRole and e["prio"] <= 3:
            return self.bold
        if role == Qt.ItemDataRole.ForegroundRole and e["prio"] >= 7:
            return MUTED
        return None

    def clear(self):
        self.beginResetModel()
        self.rows = []
        self.endResetModel()

    def append(self, batch: list[dict]):
        if not batch:
            return
        over = len(self.rows) + len(batch) - MAX_ROWS
        if over > 0:
            drop = min(over, len(self.rows))
            self.beginRemoveRows(QModelIndex(), 0, drop - 1)
            del self.rows[:drop]
            self.endRemoveRows()
            batch = batch[-MAX_ROWS:]
        n = len(self.rows)
        self.beginInsertRows(QModelIndex(), n, n + len(batch) - 1)
        self.rows.extend(batch)
        self.endInsertRows()


class LogsPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.sig = _Signals()
        self.reader: journal.Reader | None = None
        self.scope = "user"
        self.system_ok = journal.can_read_system()
        self._stale = True                      # reload when shown next
        self._boots: dict[str, list] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(0)
        self.segs = []
        for scope, name in (("user", tr("grimoire.spells.systeml.logview", "Yours")),
                            ("system", tr("grimoire.spells.systeml.logview", "System"))):
            b = QPushButton(name)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, s=scope: self.set_scope(s))
            top.addWidget(b)
            self.segs.append((b, scope))
        segments([b for b, _ in self.segs])
        sys_btn = self.segs[1][0]
        sys_btn.setToolTip(tr("grimoire.spells.systeml.logview", "Messages from the system and its services")
                           if self.system_ok else
                           tr("grimoire.spells.systeml.logview", "Only members of the systemd-journal or adm group can "
                                                                 "read the system journal. To join: {command}, then "
                                                                 "log out and back in.").format(
                               command=ltr("sudo usermod -aG systemd-journal $USER")))
        sys_btn.setEnabled(self.system_ok)
        top.addSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.systeml.logview", "Search messages"))
        self.search.setClearButtonEnabled(True)
        self._search_timer = QTimer(self, singleShot=True, interval=450, timeout=self.reload)
        self.search.textChanged.connect(lambda _: self._search_timer.start())
        self.search.returnPressed.connect(self.reload)
        top.addWidget(self.search, 1)
        top.addSpacing(16)
        self.follow = Switch()
        self.follow.setToolTip(tr("grimoire.spells.systeml.logview", "Keep reading: new messages appear as they're "
                                                                     "written"))
        self.follow.toggled.connect(lambda _: self.reload())
        follow_label = _label(tr("grimoire.spells.systeml.logview", "Follow"))
        follow_label.setBuddy(self.follow)
        top.addWidget(follow_label)
        top.addSpacing(8)
        top.addWidget(self.follow)
        lay.addLayout(top)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.level = QComboBox()
        for name, prio in LEVEL_FILTERS:
            self.level.addItem(tr("grimoire.spells.systeml.logview", name), prio)
        self.level.setCurrentIndex(0)
        self.boot = QComboBox()
        self.boot.setMinimumContentsLength(12)
        self.range = QComboBox()
        for name, secs in RANGES:
            self.range.addItem(tr("grimoire.spells.systeml.logview", name), secs)
        self.source = QComboBox()
        self.source.setEditable(True)
        self.source.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.source.lineEdit().setPlaceholderText(tr("grimoire.spells.systeml.logview", "Any unit or app"))
        self.source.lineEdit().setClearButtonEnabled(True)
        self.source.setMinimumContentsLength(18)
        self.source.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        comp = QCompleter([], self.source)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.source.setCompleter(comp)
        self.lines = QComboBox()
        for n in LINES:
            self.lines.addItem(tr("grimoire.spells.systeml.logview", "Last %n entries", n=n), n)
        self.lines.setCurrentIndex(1)
        for w, tip in ((self.level, tr("grimoire.spells.systeml.logview", "Lowest level to show")),
                       (self.boot, tr("grimoire.spells.systeml.logview", "Which boot")),
                       (self.range, tr("grimoire.spells.systeml.logview", "Time range")),
                       (self.source, tr("grimoire.spells.systeml.logview", "Only this unit or app")),
                       (self.lines, tr("grimoire.spells.systeml.logview", "How many of the newest entries to read"))):
            w.setToolTip(tip)
            filters.addWidget(w, 1 if w is self.source else 0)
        lay.addLayout(filters)
        self.level.currentIndexChanged.connect(lambda _: self.reload())
        self.boot.currentIndexChanged.connect(lambda _: self.reload())
        self.range.currentIndexChanged.connect(self._range_changed)
        self.lines.currentIndexChanged.connect(lambda _: self.reload())
        self.source.activated.connect(lambda _: self.reload())
        self.source.lineEdit().editingFinished.connect(self._source_edited)
        self.source.lineEdit().textChanged.connect(lambda t: t or self._source_edited())
        self._source_used = ""

        self.custom = QWidget()
        cr = QHBoxLayout(self.custom)
        cr.setContentsMargins(0, 0, 0, 0)
        cr.setSpacing(8)
        now = QDateTime.currentDateTime()
        self.since = QDateTimeEdit(now.addSecs(-3600))
        self.until = QDateTimeEdit(now)
        for w in (self.since, self.until):
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd HH:mm")
            w.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            w.editingFinished.connect(self.reload)
        cr.addWidget(_label(tr("grimoire.spells.systeml.logview", "From")))
        cr.addWidget(self.since)
        cr.addWidget(_label(tr("grimoire.spells.systeml.logview", "to")))
        cr.addWidget(self.until)
        cr.addStretch(1)
        self.custom.hide()
        lay.addWidget(self.custom)

        self.model = LogModel()
        self.view = QTreeView()
        self.view.setObjectName("FileDetails")
        self.view.setModel(self.model)
        self.view.setLayoutDirection(Qt.LayoutDirection.LeftToRight)    # journal lines read left to right
        self.view.setRootIsDecorated(False)
        self.view.setItemsExpandable(False)
        self.view.setUniformRowHeights(True)
        self.view.setAllColumnsShowFocus(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setWordWrap(False)
        self.view.setTextElideMode(Qt.TextElideMode.ElideRight)
        h = self.view.header()
        h.setStretchLastSection(True)
        h.setHighlightSections(False)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter   # over its column, even
                              | Qt.AlignmentFlag.AlignAbsolute)                       # in RTL languages
        fm = self.fontMetrics()
        h.resizeSection(0, fm.horizontalAdvance("2026-10-16 18:88:88") + 24)
        h.resizeSection(1, max(fm.horizontalAdvance(journal.level_text(p)) for p in range(8)) + 28)
        h.resizeSection(2, fm.horizontalAdvance("x" * 22) + 16)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._menu)
        self.view.selectionModel().selectionChanged.connect(self._sel)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setFont(QFont("IBM Plex Mono", 10))
        self.details.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.details.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.details.setPlaceholderText(tr("grimoire.spells.systeml.logview", "Pick a line to see every field the "
                                                                              "journal keeps for it."))
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.view)
        split.addWidget(self.details)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setSizes([520, 170])
        split.setChildrenCollapsible(False)
        lay.addWidget(split, 1)

        acts = QHBoxLayout()
        self.info = _label("", "Muted")
        self.info.setTextFormat(Qt.TextFormat.PlainText)       # can carry journalctl's own error text
        acts.addWidget(self.info, 1)
        self.copy_btn = QPushButton(tr("grimoire.spells.systeml.logview", "Copy"))
        self.copy_btn.setToolTip(tr("grimoire.spells.systeml.logview", "Copy the selected lines ({key})").format(
            key=ltr("Ctrl+C")))
        self.copy_btn.clicked.connect(self.copy_lines)
        self.export_btn = QPushButton(tr("grimoire.spells.systeml.logview", "Export…"))
        self.export_btn.setToolTip(tr("grimoire.spells.systeml.logview", "Save the lines shown to a text or JSON file "
                                                                         "({key})").format(
            key=ltr("Ctrl+S")))
        self.export_btn.clicked.connect(self.export)
        self.reload_btn = QPushButton(tr("grimoire.spells.systeml.logview", "Reload"))
        self.reload_btn.setToolTip(ltr("F5"))
        self.reload_btn.clicked.connect(self.reload)
        for b in (self.copy_btn, self.export_btn, self.reload_btn):
            acts.addWidget(b)
        lay.addLayout(acts)

        for keys, fn in ((QKeySequence.StandardKey.Find, self._focus_search), (QKeySequence.StandardKey.Copy,
                         self.copy_lines), (QKeySequence.StandardKey.Save, self.export), ("F5", self.reload),
                         (QKeySequence.StandardKey.Refresh, self.reload)):
            sc = QShortcut(QKeySequence(keys), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)

        self.drain = QTimer(self, interval=120, timeout=self._drain)
        self.sig.boots.connect(self._boots_loaded)
        self.sig.sources.connect(self._sources_loaded)
        self.sig.exported.connect(self._exported)
        self._set_checked()
        self._fill_boots([])
        self._sel()

    # ------------------------------------------------------------ filters
    def set_scope(self, scope: str):
        if scope == "system" and not self.system_ok:
            scope = "user"
        self.scope = scope
        self._set_checked()
        self._fill_boots(self._boots.get(scope, []))
        self._load_lists()
        self.reload()

    def _set_checked(self):
        for b, s in self.segs:
            b.setChecked(s == self.scope)

    def _range_changed(self, _=None):
        self.custom.setVisible(self.range.currentData() == "custom")
        self.reload()

    def _source_edited(self):
        text = self.source.currentText().strip()
        if text != self._source_used:
            self.reload()

    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _fill_boots(self, boots: list[dict]):
        keep = self.boot.currentData() if self.boot.count() else "0"
        self.boot.blockSignals(True)
        self.boot.clear()
        self.boot.addItem(tr("grimoire.spells.systeml.logview", "This boot"), "0")
        for b in boots:
            if b["index"] == 0:
                continue
            when = QDateTime.fromSecsSinceEpoch(int(b["first"])).toString("yyyy-MM-dd HH:mm")
            self.boot.addItem(tr("grimoire.spells.systeml.logview", "Boot of {when}").format(when=ltr(when)), b["id"])
        self.boot.addItem(tr("grimoire.spells.systeml.logview", "All boots"), "")
        i = self.boot.findData(keep)
        self.boot.setCurrentIndex(max(0, i))
        self.boot.blockSignals(False)

    def _load_lists(self):
        scope, sig = self.scope, self.sig
        POOL.start(Job(lambda: (scope, journal.boots(scope)), sig.boots.emit))
        POOL.start(Job(lambda: (scope, journal.sources(scope)), sig.sources.emit))

    def _boots_loaded(self, result):
        scope, boots = result
        self._boots[scope] = boots
        if scope == self.scope:
            self._fill_boots(boots)

    def _sources_loaded(self, result):
        scope, names = result
        if scope != self.scope:
            return
        text = self.source.currentText()
        edit = self.source.lineEdit()
        self.source.blockSignals(True)
        edit.blockSignals(True)                   # refilling the list isn't the person editing the filter
        self.source.clear()
        self.source.addItems(names)
        self.source.setCurrentIndex(-1)
        self.source.setEditText(text)
        edit.blockSignals(False)
        self.source.blockSignals(False)
        self.source.completer().setModel(self.source.model())

    def filters(self) -> dict:
        span = self.range.currentData()
        since = until = None
        if span == "custom":
            since, until = self.since.dateTime().toSecsSinceEpoch(), self.until.dateTime().toSecsSinceEpoch()
        elif span:
            since = time.time() - span
        return {"scope": self.scope, "prio": self.level.currentData(), "source": self.source.currentText().strip(),
                "boot": self.boot.currentData() or None, "since": since, "until": until,
                "grep": self.search.text().strip(), "lines": self.lines.currentData(),
                "follow": self.follow.isChecked()}

    # ------------------------------------------------------------ reading
    def load(self):
        """Called when the panel is shown: read once (later visits keep what's there unless following)."""
        if self._stale:
            self._stale = False
            self._load_lists()
            self.reload()

    def reload(self):
        self._search_timer.stop()
        self.stop()
        f = self.filters()
        self._source_used = f["source"]
        try:
            cmd = journal.command(**f)
        except ValueError:
            return
        self.model.clear()
        self.details.clear()
        self._first = True
        self.reader = journal.Reader(cmd).start()
        self.drain.start()
        self._status()

    def stop(self):
        if self.reader:
            self.reader.stop()
            self.reader = None
        self.drain.stop()

    def _drain(self):
        r = self.reader
        if r is None:
            return
        finished = r.done                     # read before take(): everything is in once it's true
        batch = r.take()
        if batch:
            bar = self.view.verticalScrollBar()
            at_end = self._first or bar.value() >= bar.maximum() - 2
            self.model.append(batch)
            if at_end:
                self.view.scrollToBottom()
        else:
            self._first = False               # the first burst is in; from now on only follow if at the bottom
        if finished:
            self.drain.stop()
            self._first = False
            self._status(r.error)
        elif batch:
            self._status()

    def _status(self, error=""):
        n = len(self.model.rows)
        if error:
            text = tr("grimoire.spells.systeml.logview", "journalctl: {error}").format(error=error)
        elif self.reader and not self.reader.done and not self.follow.isChecked():
            text = tr("grimoire.spells.systeml.logview", "Reading the journal… %n entries so far", n=n)
        elif self.follow.isChecked() and self.reader and not self.reader.done:
            text = tr("grimoire.spells.systeml.logview", "Following · %n entries", n=n)
        elif n == 0:
            text = tr("grimoire.spells.systeml.logview", "Nothing matches these filters.")
        else:
            text = tr("grimoire.spells.systeml.logview", "%n entries", n=n)
        sel = len(self.view.selectionModel().selectedRows())
        if sel > 1:
            text += " · " + tr("grimoire.spells.systeml.logview", "%n selected", n=sel)
        self.info.setText(text)
        self.export_btn.setEnabled(n > 0)

    def showEvent(self, e):
        if self.follow.isChecked() and self.reader is None and not self._stale:
            self.reload()                     # following stopped while hidden: catch up
        super().showEvent(e)

    def hideEvent(self, e):
        if self.follow.isChecked():           # nothing runs while the panel can't be seen
            self.stop()
        super().hideEvent(e)

    # ------------------------------------------------------------ selection, copy, export
    def selected(self) -> list[dict]:
        rows = sorted(i.row() for i in self.view.selectionModel().selectedRows())
        return [self.model.rows[r] for r in rows if r < len(self.model.rows)]

    def _sel(self, *_):
        sel = self.selected()
        self.copy_btn.setEnabled(bool(sel))
        cur = self.view.currentIndex()
        e = self.model.rows[cur.row()] if cur.isValid() and cur.row() < len(self.model.rows) else \
            (sel[-1] if sel else None)
        if e:
            f = e["fields"]
            lines = [f"{journal.stamp(e['t'])}  {journal.level_text(e['prio'])}  {e['source']}"
                     + (f"[{e['pid']}]" if e["pid"] else "") + (f"  ·  {e['unit']}" if e["unit"] else ""),
                     "", e["msg"], ""]
            lines += [f"{k}={v}" for k, v in sorted(f.items()) if k != "MESSAGE"]
            self.details.setPlainText("\n".join(lines))
        else:
            self.details.clear()
        if self.reader is None or self.reader.done:
            self._status()

    def copy_lines(self):
        sel = self.selected()
        if sel:
            QGuiApplication.clipboard().setText("\n".join(journal.text_line(e) for e in sel))
            self.page.say(tr("grimoire.spells.systeml.logview", "%n line(s) copied", n=len(sel)))

    def _menu(self, pos):
        idx = self.view.indexAt(pos)
        if not idx.isValid():
            return
        if not self.view.selectionModel().isRowSelected(idx.row(), QModelIndex()):
            self.view.setCurrentIndex(idx)
        e = self.model.rows[idx.row()]
        m = QMenu(self)
        m.addAction(tr("grimoire.spells.systeml.logview", "Copy selected lines"), self.copy_lines)
        clip = QGuiApplication.clipboard()
        m.addAction(tr("grimoire.spells.systeml.logview", "Copy message"), lambda: clip.setText(e["msg"]))
        m.addAction(tr("grimoire.spells.systeml.logview", "Copy all fields"), lambda: clip.setText(
            "\n".join(f"{k}={v}" for k, v in sorted(e["fields"].items()))))
        m.addSeparator()
        if e["unit"]:
            m.addAction(tr("grimoire.spells.systeml.logview", "Only {unit}").format(unit=isolate(e["unit"])),
                        lambda: self.only(e["unit"]))
        if e["source"] and e["source"] != e["unit"]:
            m.addAction(tr("grimoire.spells.systeml.logview", "Only {app}").format(app=isolate(e["source"])),
                        lambda: self.only(e["source"]))
        if self.source.currentText():
            m.addAction(tr("grimoire.spells.systeml.logview", "Every unit and app"), lambda: self.only(""))
        m.exec(self.view.viewport().mapToGlobal(pos))

    def show_unit(self, unit: str, user: bool):
        """Open on one unit's messages (from Services), in its own journal when that one is readable."""
        scope = "user" if user or not self.system_ok else "system"
        if scope != self.scope:
            self.scope = scope
            self._set_checked()
            self._fill_boots(self._boots.get(scope, []))
        self.source.setEditText(unit)
        self.level.blockSignals(True)
        self.level.setCurrentIndex(0)
        self.level.blockSignals(False)
        if self._stale:                       # first visit: load() reads the lists and the journal
            return
        self._load_lists()
        self.reload()

    def only(self, source: str):
        self.source.setEditText(source)
        self.reload()

    def export(self):
        rows = list(self.model.rows)
        if not rows:
            return
        docs = Path.home() / "Documents"
        start = free_name((docs if docs.is_dir() else Path.home()) / time.strftime("journal-%Y-%m-%d-%H%M.txt"))
        kinds = tr("grimoire.spells.systeml.logview", "Text (*.txt *.log);;JSON lines (*.jsonl *.json)")
        path, kind = QFileDialog.getSaveFileName(self, tr("grimoire.spells.systeml.logview", "Export log"),
                                                 str(start), kinds, options=QFileDialog.Option.DontConfirmOverwrite)
        if not path:
            return
        json_filter = kinds.split(";;")[-1]          # by position: the filter text is translated
        as_json = path.lower().endswith((".jsonl", ".json")) or kind == json_filter
        if as_json and not path.lower().endswith((".jsonl", ".json")):
            path += ".jsonl"
        dest = free_name(Path(path))                # never write over an existing file
        self._export_count = len(rows)
        sig = self.sig

        def work():
            try:
                journal.export(rows, dest, as_json)
                return True, str(dest)
            except OSError as err:
                return False, err.strerror or str(err)
        POOL.start(Job(work, sig.exported.emit))

    def _exported(self, result):
        ok, what = result
        if ok:
            self.page.say(tr("grimoire.spells.systeml.logview", "Saved %n line(s) to {path}",
                             n=self._export_count).format(path=ltr(what)))
        else:
            self.page.say(tr("grimoire.spells.systeml.logview", "Couldn't save the log: {error}").format(error=what))
