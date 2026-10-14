# SPDX-License-Identifier: GPL-3.0-or-later
"""UpdateL page: every update in one list (APT, Flatpak, Snap, firmware) with its changelog, Update all / selected /
per source, the live log of a run, and the daily check, held packages and restart notice.

Opening the page only shows the last check (no network); Check now asks every source again. A run goes to a worker
thread and streams its output into Activity; the root part is one helper call, so one password prompt.
"""
import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QHeaderView, QPlainTextEdit, QProgressBar,
                               QPushButton, QScrollArea, QSplitter, QStackedWidget, QVBoxLayout,
                               QWidget)

from grimoire.fsutil import human
from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.systeml.alertview import _row
from grimoire.spells.systeml.page import NumItem, _label, _tree
from grimoire.spells.updatel import apply, daily, sources
from grimoire.spells.updatel.preview import PreviewDialog
from grimoire.spells.updatel.sources import isolate
from grimoire.widgets import Switch

FILTERS = [("all", tr_noop("grimoire.spells.updatel.page", "All updates"), "updatel"),
           ("apt", tr_noop("grimoire.spells.updatel.page", "System packages"), "archive"),
           ("flatpak", "Flatpak", "grid"), ("snap", "Snap", "store"),
           ("fwupd", tr_noop("grimoire.spells.updatel.page", "Firmware"), "drive")]
MORE = [("activity", tr_noop("grimoire.spells.updatel.page", "Activity"), "terminall"),
        ("schedule", tr_noop("grimoire.spells.updatel.page", "Schedule & holds"), "clock")]
COLS = [tr_noop("grimoire.spells.updatel.page", "Name"), tr_noop("grimoire.spells.updatel.page", "Installed"),
        tr_noop("grimoire.spells.updatel.page", "New"), tr_noop("grimoire.spells.updatel.page", "Source"),
        tr_noop("grimoire.spells.updatel.page", "Size")]

QSS = """
QDialog#Plan { background: #0b0b0b; }
QLabel#Risk { color: #e8e8e8; font-size: 12px; border-left: 2px solid #f2f2f2; padding-left: 8px; }
QLabel#Risk[rtl="true"] { border-left: none; padding-left: 0; border-right: 2px solid #f2f2f2; padding-right: 8px; }
QPlainTextEdit#Log { font-family: "IBM Plex Mono"; font-size: 11px; color: #bdbdbd; background: #080808;
                     border: 1px solid #1c1c1c; border-radius: 8px; padding: 6px; }
QProgressBar { background: #121212; border: 1px solid #262626; border-radius: 4px; max-height: 6px; }
QProgressBar::chunk { background: #f2f2f2; border-radius: 3px; }
QFrame#Banner { background: #f2f2f2; border-radius: 10px; }
QFrame#Banner QLabel { color: #000000; }
"""


class _Signals(QObject):
    checked = Signal(object)
    changelog = Signal(object)       # (key, new version, text)
    simulated = Signal(object)       # (plan, sim or None, error)
    line = Signal(object)
    finished = Signal(object)        # (ok, message)
    timer = Signal(object)
    timer_set = Signal(object)       # (on, error)


def _name(text: str) -> str:
    """A FILTERS/MORE/COLS text as shown (marked with tr_noop above; Flatpak and Snap are names)."""
    return tr("grimoire.spells.updatel.page", text)


def _src_label(it: dict) -> str:
    name = sources.name(it["source"])
    if it["source"] == "flatpak":
        scope = (tr("grimoire.spells.updatel.page", "yours", "Flatpak scope") if it["scope"] == "user" else
                 tr("grimoire.spells.updatel.page", "system", "Flatpak scope"))
        return "{name} · {scope}".format(name=isolate(name), scope=scope)
    return name


# ---------------------------------------------------------------- updates list
class UpdatesPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.filter = "all"
        self.items: list[dict] = []
        self.notes: dict[str, str] = {}               # changelog cache by "key=new version"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.banner = QFrame()
        self.banner.setObjectName("Banner")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(16, 10, 16, 10)
        self.banner_text = _label("", wrap=True)
        bl.addWidget(self.banner_text, 1)
        self.banner.hide()
        lay.addWidget(self.banner)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.check_btn = QPushButton(tr("grimoire.spells.updatel.page", "Check now"))
        self.check_btn.setToolTip(tr("grimoire.spells.updatel.page", "Ask APT, Flatpak, Snap and fwupd what's new "
                                     "(Flatpak and fwupd go online)"))
        self.check_btn.clicked.connect(page.check)
        self.refresh_btn = QPushButton(tr("grimoire.spells.updatel.page", "Refresh package lists"))
        self.refresh_btn.setToolTip(tr("grimoire.spells.updatel.page",
                                       "apt-get update, then check again (asks for your password)"))
        self.refresh_btn.clicked.connect(page.refresh_lists)
        bar.addWidget(self.check_btn)
        bar.addWidget(self.refresh_btn)
        bar.addStretch(1)
        self.summary = _label("", "Muted")
        self.summary.setMinimumWidth(1)              # longer translations clip here rather than widen the window
        bar.addWidget(self.summary)
        bar.addSpacing(8)
        self.sel_btn = QPushButton(tr("grimoire.spells.updatel.page", "Update selected"))
        self.sel_btn.clicked.connect(lambda: page.update(selected=True))
        self.all_btn = QPushButton(tr("grimoire.spells.updatel.page", "Update all"))
        self.all_btn.setObjectName("Primary")
        self.all_btn.clicked.connect(lambda: page.update(selected=False))
        bar.addWidget(self.sel_btn)
        bar.addWidget(self.all_btn)
        lay.addLayout(bar)

        split = QSplitter(Qt.Orientation.Vertical)
        self.tree = _tree([_name(c) for c in COLS])
        h = self.tree.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c, w in ((1, 170), (2, 170), (3, 120), (4, 90)):
            h.resizeSection(c, w)
        self.tree.currentItemChanged.connect(self._current)
        self.tree.itemChanged.connect(lambda *_: self._sel_count())
        split.addWidget(self.tree)
        notes = QWidget()
        nl = QVBoxLayout(notes)
        nl.setContentsMargins(0, 8, 0, 0)
        nl.setSpacing(6)
        self.note_title = _label("", "RowTitle")
        nl.addWidget(self.note_title)
        self.note = QPlainTextEdit()
        self.note.setObjectName("Log")
        self.note.setReadOnly(True)
        nl.addWidget(self.note, 1)
        split.addWidget(notes)
        split.setSizes([420, 220])
        lay.addWidget(split, 1)
        self._note_timer = QTimer(self, singleShot=True, interval=250, timeout=self._load_note)
        page.sig.changelog.connect(self._note_loaded)

    def set_state(self, state: dict):
        self.items = state.get("items", [])
        live = {f"{i['key']}={i['new']}" for i in self.items}
        self.notes = {k: v for k, v in self.notes.items() if k in live}
        reboot = sources.reboot_required()
        if reboot is not None:
            pk = ", ".join(reboot[:6]) + (" …" if len(reboot) > 6 else "")
            self.banner_text.setText(tr("grimoire.spells.updatel.page",
                                        "Restart required to finish installing updates. "
                                        "Asked for by: {pkgs}.").format(pkgs=isolate(pk)) if pk else
                                     tr("grimoire.spells.updatel.page",
                                        "Restart required to finish installing updates."))
        self.banner.setVisible(reboot is not None)
        self.fill()

    def visible_items(self) -> list[dict]:
        return [i for i in self.items if self.filter in ("all", i["source"])]

    def fill(self):
        keep = self.tree.currentItem().data(0, Qt.ItemDataRole.UserRole + 1) if self.tree.currentItem() else None
        checked = {it.data(0, Qt.ItemDataRole.UserRole + 1) for it in self._tree_items()
                   if it.checkState(0) == Qt.CheckState.Checked}
        self.tree.blockSignals(True)
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        for i in self.visible_items():
            size = i.get("size")
            row = NumItem([isolate(i["title"]), isolate(i["current"] or "–"), isolate(i["new"]), _src_label(i),
                           isolate(human(size)) if size else "–"])
            for c, v in enumerate([i["title"].lower(), i["current"], i["new"], _src_label(i), size or 0]):
                row.setData(c, Qt.ItemDataRole.UserRole, v)
            row.setData(0, Qt.ItemDataRole.UserRole + 1, i["key"])
            row.setTextAlignment(4, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(0, Qt.CheckState.Checked if i["key"] in checked else Qt.CheckState.Unchecked)
            if i.get("security"):
                row.setToolTip(0, tr("grimoire.spells.updatel.page", "Security update"))
                f = row.font(0)
                f.setWeight(QFont.Weight.DemiBold)
                row.setFont(0, f)
            self.tree.addTopLevelItem(row)
        self.tree.setSortingEnabled(True)
        self.tree.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.tree.blockSignals(False)
        hit = [it for it in self._tree_items() if it.data(0, Qt.ItemDataRole.UserRole + 1) == keep]
        if hit:
            self.tree.setCurrentItem(hit[0])
        elif self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        else:
            self._current(None)
        self._sel_count()

    def _tree_items(self):
        return [self.tree.topLevelItem(n) for n in range(self.tree.topLevelItemCount())]

    def selected(self) -> list[dict]:
        keys = {it.data(0, Qt.ItemDataRole.UserRole + 1) for it in self._tree_items()
                if it.checkState(0) == Qt.CheckState.Checked}
        return [i for i in self.items if i["key"] in keys]

    def _sel_count(self):
        n, vis = len(self.selected()), self.visible_items()
        busy = self.page.busy
        self.sel_btn.setText(tr("grimoire.spells.updatel.page", "Update selected ({n})").format(n=n) if n else
                             tr("grimoire.spells.updatel.page", "Update selected"))
        self.sel_btn.setEnabled(bool(n) and not busy)
        self.all_btn.setEnabled(bool(vis) and not busy)
        self.all_btn.setText(tr("grimoire.spells.updatel.page", "Update all") if self.filter == "all" else
                             tr("grimoire.spells.updatel.page", "Update all {source}").format(
                                 source=isolate(sources.name(self.filter))))
        self.check_btn.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy and sources.have("apt-get"))
        size = sum(i.get("size") or 0 for i in vis)
        sec = sum(bool(i.get("security")) for i in vis)
        bits = []
        if vis:
            bits.append(tr("grimoire.spells.updatel.page", "%n update(s)", n=len(vis)))
        if size:
            bits.append(tr("grimoire.spells.updatel.page", "{size} to download").format(size=human(size)))
        if sec:
            bits.append(tr("grimoire.spells.updatel.page", "%n security update(s) (bold)", n=sec))
        self.summary.setText("   ·   ".join(bits))

    def _current(self, cur, _prev=None):
        if cur is None:
            state = self.page.state
            self.note_title.setText("")
            self.note.setPlainText("" if not state else tr("grimoire.spells.updatel.page", "Nothing to update here."))
            if not state:
                self.note_title.setText(tr("grimoire.spells.updatel.page", "Not checked yet"))
                self.note.setPlainText(tr("grimoire.spells.updatel.page",
                                          "Press Check now to ask APT, Flatpak, Snap and fwupd "
                                          "for updates."))
            return
        key = cur.data(0, Qt.ItemDataRole.UserRole + 1)
        it = next((i for i in self.items if i["key"] == key), None)
        if not it:
            return
        self.note_title.setText("{title}   {old} → {new}".format(title=it["title"], old=it["current"] or "?",
                                                               new=it["new"]))
        if f"{key}={it['new']}" in self.notes:
            self.note.setPlainText(self.notes[f"{key}={it['new']}"])
        else:
            self.note.setPlainText(tr("grimoire.spells.updatel.page", "Loading what's new…"))
            self._note_timer.start()

    def _load_note(self):
        cur = self.tree.currentItem()
        if not cur:
            return
        key = cur.data(0, Qt.ItemDataRole.UserRole + 1)
        it = next((i for i in self.items if i["key"] == key), None)
        if it and f"{key}={it['new']}" in self.notes:
            self.note.setPlainText(self.notes[f"{key}={it['new']}"])
        elif it:
            POOL.start(Job(lambda: (key, it["new"], sources.changelog(it)), self.page.sig.changelog.emit))

    def _note_loaded(self, result):
        key, new, text = result
        self.notes[f"{key}={new}"] = text
        cur = self.tree.currentItem()
        if cur and cur.data(0, Qt.ItemDataRole.UserRole + 1) == key:
            self.note.setPlainText(text)


# ---------------------------------------------------------------- activity (the log of a run)
class ActivityPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        head = QHBoxLayout()
        self.state = _label(tr("grimoire.spells.updatel.page", "Nothing has run yet."), "Muted", wrap=True)
        head.addWidget(self.state, 1)
        copy = QPushButton(tr("grimoire.spells.updatel.page", "Copy log"))
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.log.toPlainText()))
        head.addWidget(copy)
        lay.addLayout(head)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 100)
        self.bar.hide()
        lay.addWidget(self.bar)
        self.log = QPlainTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(20000)
        lay.addWidget(self.log, 1)

    def start(self, what: str):
        self.log.clear()
        self.state.setText(what)
        self.bar.setRange(0, 0)                      # busy until APT reports a percentage
        self.bar.show()

    def add(self, line: str):
        st = apply.parse_status(line)
        if st:
            pct, msg = st
            self.bar.setRange(0, 100)
            self.bar.setValue(int(pct))
            self.state.setText(msg)
            return
        self.log.appendPlainText(line)

    def done(self, ok: bool, msg: str):
        self.bar.hide()
        self.state.setText(msg)


# ---------------------------------------------------------------- schedule, holds, sources
class SchedulePanel(QScrollArea):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 20)
        col.setSpacing(8)
        self.timer_sw = Switch()
        self.timer_sub = _label("", "Muted", wrap=True)
        self.timer_sw.toggled.connect(self._toggle_timer)
        col.addWidget(_row(tr("grimoire.spells.updatel.page", "Check every day"), self.timer_sub, self.timer_sw))
        self.notify_sw = Switch()
        self.notify_sw.setChecked(daily.settings()["notify"])
        self.notify_sw.toggled.connect(self._toggle_notify)
        col.addWidget(_row(tr("grimoire.spells.updatel.page", "Notify me about new updates"),
                           _label(tr("grimoire.spells.updatel.page",
                                     "One desktop notification when the daily check finds "
                                     "updates it hasn't told you about yet."), "Muted", wrap=True), self.notify_sw))
        col.addSpacing(6)
        col.addWidget(_label(tr("grimoire.spells.updatel.page", "Held packages"), "SectionTitle"))
        self.held = _label("", "Muted", wrap=True)
        self.held.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.held)
        col.addSpacing(6)
        col.addWidget(_label(tr("grimoire.spells.updatel.page", "Sources"), "SectionTitle"))
        self.srcs = _label("", "Muted", wrap=True)
        col.addWidget(self.srcs)
        col.addSpacing(6)
        col.addWidget(_label(tr("grimoire.spells.updatel.page", "Restart", "heading"), "SectionTitle"))
        self.reboot = _label("", "Muted", wrap=True)
        col.addWidget(self.reboot)
        col.addStretch(1)
        self.setWidget(inner)
        page.sig.timer.connect(self._show_timer)
        page.sig.timer_set.connect(self._timer_set)

    def load(self):
        POOL.start(Job(daily.enabled, self.page.sig.timer.emit))

    def _show_timer(self, on: bool):
        self.timer_sw.blockSignals(True)
        self.timer_sw.setChecked(on)
        self.timer_sw.blockSignals(False)
        last = daily.ago(self.page.state.get("t"))
        self.timer_sub.setText((tr("grimoire.spells.updatel.page",
                                   "On: a user timer looks for updates once a day (it never "
                                   "installs anything). Last check: {when}.") if on else
                                tr("grimoire.spells.updatel.page", "Off: UpdateL only looks when you press Check now. "
                                   "Last check: {when}.")).format(when=last))

    def _toggle_timer(self, on: bool):
        def work():
            try:
                daily.set_enabled(on)
                err = ""
            except Exception as e:                     # shown, not a crash
                err = str(e)
            return daily.enabled(), err
        POOL.start(Job(work, self.page.sig.timer_set.emit))

    def _timer_set(self, result):
        on, err = result
        self._show_timer(on)
        if err:
            self.page.say(tr("grimoire.spells.updatel.page", "Couldn't change the daily check: {err}").format(
                err=isolate(err)))

    def _toggle_notify(self, on: bool):
        s = daily.settings()
        s["notify"] = on
        daily.save_settings(s)

    def set_state(self, state: dict):
        held = state.get("held", [])
        self.held.setText(tr("grimoire.spells.updatel.page",
                             "Kept at their version with apt-mark hold, so they're never "
                             "upgraded: {names}. Release one with: sudo apt-mark unhold NAME").format(
                                 names=isolate(", ".join(held)))
                          if held else tr("grimoire.spells.updatel.page", "No held packages."))
        lines = []
        c = daily.counts(state.get("items", []))
        for src in sources.SOURCES:
            if src in state.get("missing", []):
                lines.append(tr("grimoire.spells.updatel.page", "{name}: not installed").format(
                    name=isolate(sources.name(src))))
            elif src in state.get("errors", {}):
                lines.append(tr("grimoire.spells.updatel.page", "{name}: couldn't be read ({err})").format(
                    name=isolate(sources.name(src)), err=isolate(state["errors"][src])))
            elif state:
                lines.append(tr("grimoire.spells.updatel.page", "{name}: %n update(s)", n=c.get(src, 0)).format(
                    name=isolate(sources.name(src))))
        self.srcs.setText("\n".join(lines) or tr("grimoire.spells.updatel.page", "Not checked yet."))
        reboot = sources.reboot_required()
        self.reboot.setText(tr("grimoire.spells.updatel.page", "No restart needed.") if reboot is None else
                            tr("grimoire.spells.updatel.page", "A restart is required to finish installing updates. "
                               "Asked for by: {pkgs}.")
                            .format(pkgs=isolate(", ".join(reboot))) if reboot else
                            tr("grimoire.spells.updatel.page", "A restart is required to finish installing updates."))
        self._show_timer(self.timer_sw.isChecked())


# ---------------------------------------------------------------- the page
class UpdateLPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.setStyleSheet(QSS)
        self.sig = _Signals()
        self.state: dict = daily.load()
        self.busy = False
        self._after = ""
        self._picked: list[dict] = []
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        nav = QFrame()
        nav.setObjectName("SubNav")
        nav.setMinimumWidth(210)                     # grows for longer names in other languages
        nav.setMaximumWidth(300)
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(12, 26, 12, 16)
        nl.setSpacing(2)
        nl.addWidget(_label("UpdateL", "Title"))
        nl.addSpacing(12)
        nl.addWidget(_label(tr("grimoire.spells.updatel.page", "UPDATES"), "NavSection"))
        self.nav: dict[str, QPushButton] = {}
        for pid, name, icon in FILTERS + MORE:
            if pid == "activity":
                nl.addSpacing(10)
                nl.addWidget(_label(tr("grimoire.spells.updatel.page", "MORE"), "NavSection"))
            b = QPushButton(glyph(icon, 18), "  " + _name(name).replace("&", "&&"))
            b.setObjectName("SubNavItem")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, p=pid: self.show_panel(p))
            nl.addWidget(b)
            self.nav[pid] = b
        nl.addStretch(1)
        self.foot = _label("", "Tiny", wrap=True)
        nl.addWidget(self.foot)
        root.addWidget(nav)

        right = QVBoxLayout()
        right.setContentsMargins(32, 26, 32, 18)
        right.setSpacing(14)
        self.heading = _label("", "PageHeading")
        right.addWidget(self.heading)
        self.stack = QStackedWidget()
        self.updates = UpdatesPanel(self)
        self.activity = ActivityPanel(self)
        self.schedule = SchedulePanel(self)
        for w in (self.updates, self.activity, self.schedule):
            self.stack.addWidget(w)
        right.addWidget(self.stack, 1)
        self.toast = _label("", "Toast", wrap=True)
        self.toast.setTextFormat(Qt.TextFormat.PlainText)
        self.toast.hide()
        right.addWidget(self.toast)
        self._toast_timer = QTimer(self, singleShot=True, interval=8000, timeout=self.toast.hide)
        root.addLayout(right, 1)

        # these carry package/device names, vendor text and apt's messages: never read them as rich text
        for lab in (self.updates.banner_text, self.updates.summary, self.updates.note_title, self.activity.state,
                    self.schedule.held, self.schedule.srcs, self.schedule.reboot, self.foot):
            lab.setTextFormat(Qt.TextFormat.PlainText)
        self.sig.checked.connect(self._checked)
        self.sig.simulated.connect(self._simulated)
        self.sig.line.connect(self.activity.add)
        self.sig.finished.connect(self._finished)
        self._apply_state()
        self.show_panel("all")

    # ------------------------------------------------------------ navigation
    def show_panel(self, pid: str):
        for p, b in self.nav.items():
            b.setChecked(p == pid)
        self.heading.setText(_name(next(n for p, n, _ in FILTERS + MORE if p == pid)))
        if pid in dict((f[0], f) for f in FILTERS):
            self.updates.filter = pid
            self.stack.setCurrentWidget(self.updates)
            self.updates.fill()
        elif pid == "activity":
            self.stack.setCurrentWidget(self.activity)
        else:
            self.stack.setCurrentWidget(self.schedule)
            self.schedule.load()

    def showEvent(self, e):
        self._apply_state()                    # the daily check may have run since
        super().showEvent(e)

    def say(self, text: str):
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start()

    def set_busy(self, busy: bool):
        self.busy = busy
        self.updates._sel_count()

    # ------------------------------------------------------------ checking
    def _apply_state(self):
        if not self.busy:
            self.state = daily.load() or self.state
        c = daily.counts(self.state.get("items", []))
        for pid, name, _ in FILTERS:
            n = len(self.state.get("items", [])) if pid == "all" else c.get(pid, 0)
            name = _name(name).replace("&", "&&")
            self.nav[pid].setText("  " + (name if not n else "{name}  ·  {n}".format(name=name, n=n)))
        self.nav["snap"].setVisible("snap" not in self.state.get("missing", ["snap"]) or bool(c.get("snap")))
        self.foot.setText(daily.status_line())
        self.updates.set_state(self.state)
        self.schedule.set_state(self.state)

    def check(self):
        if self.busy:
            return
        self.set_busy(True)
        self.updates.summary.setText(tr("grimoire.spells.updatel.page", "Checking…"))
        before = self.state

        def work():
            try:
                return daily.check()
            except Exception as e:                     # e.g. the cache can't be written: answer, so busy clears
                return {**before, "items": before.get("items", []), "failed": str(e)}
        POOL.start(Job(work, self.sig.checked.emit))

    def _checked(self, state):
        self.set_busy(False)
        self.state = state
        self._apply_state()
        errs = state.get("errors", {})
        n = len(state["items"])
        msg = (tr("grimoire.spells.updatel.page", "%n update(s) available.", n=n) if n else
               tr("grimoire.spells.updatel.page", "Everything is up to date."))
        if errs:
            msg += " " + tr("grimoire.spells.updatel.page", "Couldn't read: {names}.").format(
                names=isolate(", ".join(sources.name(s) for s in errs)))
        if state.get("failed"):
            msg = tr("grimoire.spells.updatel.page", "The check failed: {err}").format(err=isolate(state["failed"]))
        if self._after:                                # how the run went comes first
            msg, self._after = self._after + " " + msg, ""
        self.say(msg)

    def refresh_lists(self):
        self._start(apply.Plan(refresh=True), tr("grimoire.spells.updatel.page", "Refreshing the package lists…"))

    # ------------------------------------------------------------ updating
    def update(self, selected: bool):
        if self.busy:
            return
        vis = self.updates.visible_items()
        items = self.updates.selected() if selected else vis
        if not items:
            return
        everything = set() if selected else {i["source"] for i in vis} - {"fwupd"}
        try:
            plan = apply.plan_for(items, everything)
        except ValueError as e:
            self.say(str(e))
            return
        self.set_busy(True)
        self._picked = items
        if plan.apt is None or plan.apt:
            names = plan.apt

            def work():
                try:
                    return plan, sources.simulate(names), ""
                except Exception as e:                 # apt-get's own message, shown in the toast
                    return plan, None, str(e)
            POOL.start(Job(work, self.sig.simulated.emit))
        else:
            self._simulated((plan, None, ""))

    def _simulated(self, result):
        plan, sim, err = result
        self.set_busy(False)
        if err:
            self.say(tr("grimoire.spells.updatel.page", "APT couldn't plan this upgrade: {err}").format(
                err=isolate(err)))
            return
        dlg = PreviewDialog(self, plan, sim, daily.counts(self._picked))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        plan.removals = dlg.confirmed_removals()
        self._start(plan, tr("grimoire.spells.updatel.page", "Updating…"))

    def _start(self, plan: apply.Plan, what: str):
        if self.busy:
            return
        self.set_busy(True)
        self.activity.start(what)
        self.show_panel("activity")

        def work():
            try:
                ok, msg = apply.run(plan, self.sig.line.emit)
            except Exception as e:                     # e.g. a bad name slipped in: shown, not a crash
                ok, msg = False, str(e)
            self.sig.finished.emit((ok, msg))
        threading.Thread(target=work, daemon=True).start()

    def _finished(self, result):
        ok, msg = result
        self.activity.done(ok, msg)
        self.busy = False
        self._after = msg
        self.check()                                   # what's left, and a restart notice (also after a partial run)
