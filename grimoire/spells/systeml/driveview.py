# SPDX-License-Identifier: GPL-3.0-or-later
"""SystemL's Drives panel (the everyday half of KDE Partition Manager): every disk with a map of its partitions,
usage, live read/write rates, health, and mount / unmount / safely remove through udisks2 (drives.py).

Formatting and partition editing aren't here on purpose; the panel says so and opens KDE Partition Manager.
The list is re-read every few seconds while the panel is on screen, on a worker thread.
"""
import json

from PySide6.QtCore import QObject, QProcess, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QScrollArea, QSizePolicy, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from grimoire.fsutil import human
from grimoire.i18n import isolate, ltr, tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.systeml import drives
from grimoire.spells.systeml.bidi import lead
from grimoire.spells.systeml.graph import INK, SOFT, Bar

REFRESH_MS = 4000
HEALTH_ROWS = {"temp": tr_noop("grimoire.spells.systeml.driveview", "Temperature"),
               "hours": tr_noop("grimoire.spells.systeml.driveview", "Powered on"),
               "bad_sectors": tr_noop("grimoire.spells.systeml.driveview", "Bad sectors"),
               "percent_used": tr_noop("grimoire.spells.systeml.driveview", "Wear (of rated life)"),
               "avail_spare": tr_noop("grimoire.spells.systeml.driveview", "Spare blocks left"),
               "spare_thresh": tr_noop("grimoire.spells.systeml.driveview", "Spare warning level"),
               "written": tr_noop("grimoire.spells.systeml.driveview", "Data written"),
               "read": tr_noop("grimoire.spells.systeml.driveview", "Data read"),
               "power_cycles": tr_noop("grimoire.spells.systeml.driveview", "Power cycles"),
               "unsafe_shutdowns": tr_noop("grimoire.spells.systeml.driveview", "Unsafe shutdowns"),
               "media_errors": tr_noop("grimoire.spells.systeml.driveview", "Media errors"),
               "error_log": tr_noop("grimoire.spells.systeml.driveview", "Error log entries"),
               "sensors": tr_noop("grimoire.spells.systeml.driveview", "Sensors"),
               "selftest": tr_noop("grimoire.spells.systeml.driveview", "Last self-test")}
SELFTEST = {"success": tr_noop("grimoire.spells.systeml.driveview", "passed"),
            "inprogress": tr_noop("grimoire.spells.systeml.driveview", "running"),
            "aborted": tr_noop("grimoire.spells.systeml.driveview", "aborted"),
            "interrupted": tr_noop("grimoire.spells.systeml.driveview", "interrupted")}


class _Signals(QObject):
    loaded = Signal(object)
    health = Signal(object)          # (drive object path, report)


def _label(text="", name="", wrap=False, plain=True) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    if plain:                         # labels, models and errors come from the drive or udisks
        lab.setTextFormat(Qt.TextFormat.PlainText)
    return lab


def _rate(n: float) -> str:
    return human(n) + "/s"


def part_name(p: dict) -> str:
    return p["label"] or p["device"].rsplit("/", 1)[-1]


def fs_text(p: dict) -> str:
    if p["encrypted"] and not p["unlocked"]:
        return tr("grimoire.spells.systeml.driveview", "encrypted, locked")
    if p["encrypted"]:
        return tr("grimoire.spells.systeml.driveview", "encrypted · {fs}").format(fs=p["fs"] or "?")
    if p["swap"]:
        return tr("grimoire.spells.systeml.driveview", "swap")
    if p["container"]:
        return tr("grimoire.spells.systeml.driveview", "extended")
    return p["fs"] or tr("grimoire.spells.systeml.driveview", "no file system")


def _degrees(c: float) -> str:
    return ltr(f"{c:.0f} °C")


def health_line(d: dict) -> str:
    h = d["health"]
    if h.get("failing") is None:
        return tr("grimoire.spells.systeml.driveview", "Health unknown")
    text = tr("grimoire.spells.systeml.driveview", "Failing") if h["failing"] else \
        tr("grimoire.spells.systeml.driveview", "Healthy")
    if h.get("temp") is not None:
        text += " · " + _degrees(h["temp"])
    return text


class PartMap(QWidget):
    """The drive's layout as one bar: each partition as wide as its share (with a minimum so small ones show),
    filled up to how full it is. A chart, so it never mirrors."""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.parts: list[dict] = []
        self.size = 1

    def set(self, size: int, parts: list[dict]):
        self.size, self.parts = max(1, size), [p for p in parts if not p.get("container")]
        self.update()

    def sizeHint(self):
        return QSize(400, 30)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor("#2a2a2a"), 1))
        p.setBrush(QColor("#0b0b0b"))
        p.drawRoundedRect(r, 6, 6)
        if not self.parts:
            p.end()
            return
        gap, min_w = 3.0, 14.0
        avail = r.width() - gap * (len(self.parts) + 1)
        widths = [max(min_w, avail * q["size"] / self.size) for q in self.parts]
        scale = min(1.0, avail / sum(widths)) if sum(widths) else 1.0
        x = r.left() + gap
        f = QFont(self.font())
        f.setPointSizeF(max(7.0, f.pointSizeF() * 0.8))
        p.setFont(f)
        for q, w in zip(self.parts, widths):
            w *= scale
            cell = QRectF(x, r.top() + gap, w, r.height() - 2 * gap)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#1c1c1c"))
            p.drawRoundedRect(cell, 4, 4)
            if q.get("total"):
                fill = QRectF(cell.left(), cell.top(), cell.width() * min(1.0, q["used"] / q["total"]), cell.height())
                p.setBrush(QColor("#3a3a3a"))
                p.drawRoundedRect(fill, 4, 4)
            p.setPen(INK if q["mounts"] else SOFT)
            label = p.fontMetrics().elidedText(part_name(q), Qt.TextElideMode.ElideRight, int(cell.width() - 10))
            if cell.width() > 30:
                p.drawText(cell.adjusted(6, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                           | Qt.AlignmentFlag.AlignAbsolute, label)
            x += w + gap
        p.end()


class HealthDialog(QDialog):
    def __init__(self, parent, drive: dict, sig: _Signals):
        super().__init__(parent)
        self.drive = drive
        self.setObjectName("Page")
        self.setWindowTitle(tr("grimoire.spells.systeml.driveview", "Health of {drive}").format(
            drive=isolate(drive["model"])))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(12)
        title = _label(drive["model"], "RowTitle")
        lay.addWidget(lead(title))
        bits = [drives.kind_text(drive["kind"]), ltr(human(drive["size"])), ltr(drive["device"])]
        if drive["serial"]:
            bits.append(tr("grimoire.spells.systeml.driveview", "serial {serial}").format(serial=ltr(drive["serial"])))
        if drive["revision"]:
            bits.append(tr("grimoire.spells.systeml.driveview", "firmware {version}").format(
                version=ltr(drive["revision"])))
        sub = " · ".join(b for b in bits if b)
        lay.addWidget(lead(_label(sub, "Muted", wrap=True)))
        self.verdict = _label(tr("grimoire.spells.systeml.driveview", "Reading health data…"), "RowTitle",
                              wrap=True)                  # a sentence: not the big heading font
        lay.addWidget(self.verdict)
        self.note = _label("", "Muted", wrap=True)
        self.note.hide()
        lay.addWidget(self.note)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(6)
        lay.addLayout(self.grid)
        self.table = QTreeWidget()
        self.table.setHeaderLabels(["ID", tr("grimoire.spells.systeml.driveview", "Attribute"),
                                    tr("grimoire.spells.systeml.driveview", "Value"),
                                    tr("grimoire.spells.systeml.driveview", "Worst"),
                                    tr("grimoire.spells.systeml.driveview", "Threshold"),
                                    tr("grimoire.spells.systeml.driveview", "Raw")])
        self.table.setRootIsDecorated(False)
        self.table.setLayoutDirection(Qt.LayoutDirection.LeftToRight)     # SMART's own names and numbers
        self.table.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.header().setStretchLastSection(False)
        self.table.header().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                                                | Qt.AlignmentFlag.AlignAbsolute)    # over its column in RTL too
        self.table.setMinimumHeight(240)
        self.table.hide()
        lay.addWidget(self.table, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        close = QPushButton(tr("grimoire.spells.systeml.driveview", "Close"))
        close.setDefault(True)
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        lay.addLayout(btns)
        sig.health.connect(self._loaded)
        POOL.start(Job(lambda: (drive["object"] or drive["device"], drives.health(drive)), sig.health.emit))

    def _loaded(self, result):
        key, rep = result
        if key != (self.drive["object"] or self.drive["device"]):
            return
        v = rep["verdict"]
        if v == "good":
            verdict = tr("grimoire.spells.systeml.driveview", "Healthy: the drive reports no problems.")
        elif v == "failing":
            verdict = tr("grimoire.spells.systeml.driveview", "Failing: back up what's on it now and plan to replace "
                                                              "it.")
        else:
            verdict = tr("grimoire.spells.systeml.driveview", "Health unknown")
        self.verdict.setText(verdict)
        notes = [rep.get("note") or ""] + [tr("grimoire.spells.systeml.driveview",
                                              "Warning from the drive: {warning}").format(warning=w)
                                           for w in rep.get("warnings", [])]
        if rep.get("source") == "smartctl":
            notes.append(tr("grimoire.spells.systeml.driveview", "Read with smartctl."))
        notes = [n for n in notes if n]
        self.note.setText("\n".join(notes))
        self.note.setVisible(bool(notes))
        row = 0
        for key, value in rep["rows"]:
            if key == "ata":
                aid, name, val, worst, thresh, pretty, unit = value
                it = QTreeWidgetItem([str(aid), str(name), str(val), str(worst), str(thresh), _pretty(pretty, unit)])
                if thresh and 0 < (val or 0) <= thresh:
                    f = it.font(1)
                    f.setBold(True)
                    for c in range(6):
                        it.setFont(c, f)
                self.table.addTopLevelItem(it)
                continue
            name = tr("grimoire.spells.systeml.driveview", HEALTH_ROWS.get(key, key))
            self.grid.addWidget(_label(name.upper(), "StatLabel"), row, 0)
            val = lead(_label(_value(key, value)))
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.grid.addWidget(val, row, 1)
            row += 1
        self.grid.setColumnStretch(1, 1)
        self.table.setVisible(self.table.topLevelItemCount() > 0)
        for c in (0, 2, 3, 4, 5):
            self.table.resizeColumnToContents(c)
        self.layout().activate()
        QTimer.singleShot(0, self.adjustSize)           # once the new rows have their real heights


def _value(key: str, v) -> str:
    if key == "temp":
        return _degrees(v)
    if key == "hours":
        return tr("grimoire.spells.systeml.driveview", "%n hour(s)", n=int(v))
    if key in ("percent_used", "avail_spare", "spare_thresh"):
        return ltr(f"{v}%")
    if key in ("written", "read"):
        return ltr(human(v))
    if key == "sensors":
        return ", ".join(_degrees(t) for t in v)
    if key == "selftest":
        return tr("grimoire.spells.systeml.driveview", SELFTEST[v]) if v in SELFTEST else str(v)
    return ltr(str(v))


def _pretty(value, unit) -> str:
    """udisks' "pretty" SMART value: 2 = milliseconds, 3 = sectors, 4 = millikelvin, else a plain count."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return str(value)
    if unit == 2:
        return tr("grimoire.spells.systeml.driveview", "%n hour(s)", n=value // 3_600_000)
    if unit == 4:
        return f"{value / 1000 - 273.15:.0f} °C"
    return str(value)


class DriveCard(QFrame):
    def __init__(self, panel, d: dict, udisks: bool):
        super().__init__()
        self.setObjectName("Row")
        self.panel, self.d = panel, d
        cl = QVBoxLayout(self)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(lead(_label(d["model"], "RowTitle")))
        top.addWidget(_label(drives.kind_text(d["kind"]).upper(), "Badge"))
        if d["system"]:
            top.addWidget(_label(tr("grimoire.spells.systeml.driveview", "SYSTEM"), "Badge"))
        top.addWidget(_label(" · ".join((ltr(human(d["size"])), ltr(d["device"]))) if d["device"]
                             else ltr(human(d["size"])), "Muted"))
        top.addStretch(1)
        self.rate = _label("", "Value")
        top.addWidget(self.rate)
        cl.addLayout(top)

        line = QHBoxLayout()
        line.setSpacing(8)
        self.health = QPushButton(health_line(d))
        self.health.setObjectName("Link")
        self.health.setToolTip(tr("grimoire.spells.systeml.driveview", "Show the drive's health report (SMART)"))
        self.health.clicked.connect(lambda: panel.show_health(self.d))
        line.addWidget(self.health)
        line.addStretch(1)
        if udisks and d["ejectable"] and not d["system"] and d["kind"] == "optical":
            b = QPushButton(tr("grimoire.spells.systeml.driveview", "Eject"))
            b.clicked.connect(lambda: panel.page.act(d["model"], lambda: drives.eject(self.d), then=panel.load))
            line.addWidget(b)
        elif udisks and d["removable"] and not d["system"]:
            b = QPushButton(tr("grimoire.spells.systeml.driveview", "Safely remove"))
            b.setToolTip(tr("grimoire.spells.systeml.driveview", "Unmounts everything on it, then powers it off so it "
                                                                 "can be unplugged"))
            b.clicked.connect(lambda: panel.safely_remove(self.d))
            line.addWidget(b)
        cl.addLayout(line)

        self.map = PartMap()
        self.map.set(d["size"], d["parts"])
        cl.addWidget(self.map)
        self.rows = {}
        if not d["parts"]:
            empty = tr("grimoire.spells.systeml.driveview", "No media") if not d["media"] else \
                tr("grimoire.spells.systeml.driveview", "No partitions or file systems on this drive.")
            cl.addWidget(_label(empty, "Muted"))
        for p in d["parts"]:
            if p["container"]:
                continue
            cl.addLayout(self._part_row(p, udisks))

    def _part_row(self, p: dict, udisks: bool) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        name = lead(_label(" · ".join((isolate(part_name(p)), fs_text(p), ltr(human(p["size"]))))))
        name.setMinimumWidth(200)
        row.addWidget(name, 3)
        mount = p["mounts"][0] if p["mounts"] else ""
        where = ltr(mount) if mount else tr("grimoire.spells.systeml.driveview", "not mounted")
        row.addWidget(lead(_label(where, "Muted")), 2)
        bar = Bar()
        used = _label("", "Muted")
        row.addWidget(bar, 2)
        row.addWidget(used, 2)
        self.rows[p["object"] or p["device"]] = (bar, used)
        self._usage(p)
        busy = self.panel.busy
        if mount:
            b = QPushButton(tr("grimoire.spells.systeml.driveview", "Open", "verb"))
            b.setToolTip(tr("grimoire.spells.systeml.driveview", "Open in VaultL"))
            b.clicked.connect(lambda _=False, m=mount: self.panel.open_folder(m))
            row.addWidget(b)
        if udisks and p["can_mount"] and not p["swap"]:
            key = p.get("inner") or p["object"]
            if mount:
                b = QPushButton(tr("grimoire.spells.systeml.driveview", "Unmount"))
                system = any(drives.is_system_mount(m) for m in p["mounts"])
                b.setEnabled(not system and key not in busy)
                if system:
                    b.setToolTip(tr("grimoire.spells.systeml.driveview", "The system runs from it, so it stays "
                                                                         "mounted"))
                b.clicked.connect(lambda _=False, p=p: self.panel.unmount(p))
            else:
                b = QPushButton(tr("grimoire.spells.systeml.driveview", "Mount"))
                b.setEnabled(key not in busy)
                b.clicked.connect(lambda _=False, p=p: self.panel.mount(p))
            row.addWidget(b)
        return row

    def _usage(self, p: dict):
        bar, used = self.rows[p["object"] or p["device"]]
        if p["total"]:
            bar.set(p["used"] / p["total"])
            bar.show()
            used.setText(tr("grimoire.spells.systeml.driveview", "{used} of {total}").format(
                used=ltr(human(p["used"])), total=ltr(human(p["total"]))))
        else:
            bar.hide()
            used.setText("")

    def update_usage(self, d: dict):
        self.d = d
        for p in d["parts"]:
            if (p["object"] or p["device"]) in self.rows:
                self._usage(p)
        self.health.setText(health_line(d))
        self.map.set(d["size"], d["parts"])


def _shape(snap: dict, busy) -> str:
    """What decides the cards' layout (not usage numbers), to rebuild only when something really changed."""
    return json.dumps([snap["udisks"], sorted(busy)] + [
        [d["object"], d["device"], d["model"], d["system"], d["media"], d["ejectable"], d["removable"],
         [[p["object"], p["device"], p["label"], p["fs"], p["mounts"], p["encrypted"], p["unlocked"], p["size"]]
          for p in d["parts"]]] for d in snap["drives"]])


class DrivesPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.sig = _Signals()
        self.sig.loaded.connect(self.loaded)
        self.cards: dict[str, DriveCard] = {}
        self.busy: set[str] = set()          # partitions being mounted/unmounted right now
        self._shape = ""
        self._loading = False
        self._dialogs = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.note = _label("", "Muted", wrap=True)
        self.note.hide()
        lay.addWidget(self.note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(0, 0, 10, 10)
        outer.setSpacing(10)
        self.col = QVBoxLayout()
        self.col.setSpacing(10)
        outer.addLayout(self.col)
        outer.addWidget(self._partition_card())
        outer.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        self.timer = QTimer(self, interval=REFRESH_MS, timeout=self.load)

    def _partition_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Row")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(14)
        text = QVBoxLayout()
        text.setSpacing(3)
        text.addWidget(lead(_label(tr("grimoire.spells.systeml.driveview", "Formatting and partitions"), "RowTitle")))
        tool = drives.partition_manager()
        msg = tr("grimoire.spells.systeml.driveview", "Creating, resizing, formatting and deleting partitions can "
                                                      "erase a whole disk, so SystemL leaves them to KDE Partition "
                                                      "Manager, which checks every step and asks for your password.")
        if not tool:
            msg += " " + tr("grimoire.spells.systeml.driveview", "It isn't installed: {command}").format(
                command=ltr("sudo apt install partitionmanager"))
        sub = _label(msg, "Muted", wrap=True)
        sub.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(sub)
        lay.addLayout(text, 1)
        b = QPushButton(tr("grimoire.spells.systeml.driveview", "Open Partition Manager"))
        b.setEnabled(bool(tool))
        b.clicked.connect(self.open_partition_manager)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
        return card

    # ------------------------------------------------------------ loading
    def load(self):
        if self._loading:
            return
        self._loading = True
        POOL.start(Job(drives.snapshot, self.sig.loaded.emit))

    def showEvent(self, e):
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def loaded(self, snap: dict):
        self._loading = False
        self.snap = snap
        note = tr("grimoire.spells.systeml.driveview", "udisks2 isn't available, so drives are listed read-only "
                                                       "(from lsblk): nothing can be mounted or removed from here.")
        self.note.setText(note if not snap["udisks"] else "")
        self.note.setVisible(not snap["udisks"])
        shape = _shape(snap, self.busy)
        if shape == self._shape:
            for d in snap["drives"]:
                card = self.cards.get(d["object"] or d["device"])
                if card:
                    card.update_usage(d)
            return
        self._shape = shape
        while self.col.count():
            w = self.col.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.cards = {}
        if not snap["drives"]:
            self.col.addWidget(_label(tr("grimoire.spells.systeml.driveview", "No drives found."), "Muted"))
        for d in snap["drives"]:
            card = DriveCard(self, d, snap["udisks"])
            self.cards[d["object"] or d["device"]] = card
            self.col.addWidget(card)

    def set_rates(self, rates: dict):
        for card in self.cards.values():
            name = card.d["device"].rsplit("/", 1)[-1]
            r, w = rates.get(name, (0, 0))
            card.rate.setText(tr("grimoire.spells.systeml.driveview", "read {read}   write {write}").format(
                read=ltr(_rate(r)), write=ltr(_rate(w))))

    # ------------------------------------------------------------ actions
    def _busy_act(self, key: str, what: str, fn):
        self.busy.add(key)
        self._shape = ""                         # redraw with the buttons greyed out
        if hasattr(self, "snap"):
            self.loaded(self.snap)

        def then():
            self.busy.discard(key)
            self._shape = ""
            self.load()
        self.page.act(what, fn, then=then)

    def mount(self, p: dict):
        key = p.get("inner") or p["object"]
        self._busy_act(key, part_name(p), lambda: tr("grimoire.spells.systeml.driveview", "mounted at {folder}").format(
            folder=ltr(drives.mount(key))))

    def unmount(self, p: dict):
        key = p.get("inner") or p["object"]
        self._busy_act(key, part_name(p), lambda: drives.unmount(key, p["mounts"]))

    def safely_remove(self, d: dict):
        self._busy_act(d["object"], d["model"], lambda: drives.power_off(d))

    def show_health(self, d: dict):
        dlg = HealthDialog(self, d, self.sig)
        self._dialogs = [x for x in self._dialogs if x.isVisible()] + [dlg]
        dlg.show()

    def open_folder(self, folder: str):
        from grimoire.spells.systeml.page import _launch
        _launch("grimoire.spells.vaultl", folder)

    def open_partition_manager(self):
        tool = drives.partition_manager()
        if not tool or not QProcess.startDetached(tool, []):
            self.page.say(tr("grimoire.spells.systeml.driveview", "Couldn't start KDE Partition Manager."))
