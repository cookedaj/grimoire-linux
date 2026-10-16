# SPDX-License-Identifier: GPL-3.0-or-later
"""About this PC: a fastfetch-style card under the spells on the home page, with a Copy button.

The facts come from sysinfo.py, read once off the UI thread and cached; only the uptime ticks. Host and user names
stay hidden (and out of the copied text) unless the box is ticked.
"""
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from grimoire import NAME, i18n, sysinfo
from grimoire.fsutil import human
from grimoire.glyphs import clover
from grimoire.i18n import tr
from grimoire.theme import FONT



def uptime(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, hours, mins = seconds // 86400, seconds % 86400 // 3600, seconds % 3600 // 60
    bits = []
    if days:
        bits.append(tr("grimoire.aboutview", "%n day(s)", n=days))
    if hours or days:
        bits.append(tr("grimoire.aboutview", "%n hour(s)", n=hours))
    bits.append(tr("grimoire.aboutview", "%n minute(s)", n=mins))
    return " ".join(bits)


def displays() -> str:
    """Each screen as '2560 × 1440 @ 165 Hz' (physical pixels)."""
    out = []
    for s in QGuiApplication.screens():
        size, ratio = s.size(), s.devicePixelRatio()
        w, h = round(size.width() * ratio), round(size.height() * ratio)
        hz = round(s.refreshRate())
        out.append(f"{w} × {h} @ {hz} Hz" if hz else f"{w} × {h}")
    return ", ".join(out)


def lines(info: dict, personal: bool) -> list[tuple[str, str]]:
    """(label, value) pairs in the card's order, translated; empty values are left out."""
    ltr = i18n.ltr
    rows = []
    if personal:
        rows += [(tr("grimoire.aboutview", "User"), i18n.isolate(info.get("user", ""))),
                 (tr("grimoire.aboutview", "Host"), i18n.isolate(info.get("host", "")))]
    rows.append((tr("grimoire.aboutview", "Machine"), ltr(info["machine"]) if info.get("machine") else ""))
    rows.append((tr("grimoire.aboutview", "System"), ltr(info.get("system", ""))))
    rows.append((tr("grimoire.aboutview", "Kernel"), ltr(info.get("kernel", ""))))
    desktop = ""
    if info.get("plasma"):
        desktop = ltr(f"KDE Plasma {info['plasma']}" + (f" · {info['session']}" if info.get("session") else ""))
    rows.append((tr("grimoire.aboutview", "Desktop"), desktop))
    cpu = ltr(info.get("cpu", "")) if info.get("cpu") else ""
    if cpu and info.get("threads"):
        cpu += " · " + tr("grimoire.aboutview", "%n thread(s)", n=info["threads"])
    rows.append((tr("grimoire.aboutview", "Processor"), cpu))
    rows.append((tr("grimoire.aboutview", "Graphics"), "\n".join(ltr(g) for g in info.get("gpus", []))))
    rows.append((tr("grimoire.aboutview", "Memory"), ltr(human(info["memory"])) if info.get("memory") else ""))
    d = info.get("disk") or {}
    storage = ""
    if d.get("total"):
        storage = tr("grimoire.aboutview", "{size}, {free} free").format(size=ltr(human(d["total"])),
                                                                         free=ltr(human(d["free"])))
        if d.get("model"):
            storage = ltr(d["model"]) + " · " + storage
    rows.append((tr("grimoire.aboutview", "Storage"), storage))
    rows.append((tr("grimoire.aboutview", "Display"), ltr(displays())))
    rows.append((tr("grimoire.aboutview", "Uptime"), uptime(time.time() - info["boot"]) if info.get("boot") else ""))
    rows.append((NAME, ltr(info.get("version", ""))))
    return [(k, v) for k, v in rows if v]


def summary(info: dict, personal: bool) -> str:
    """The copied text: one 'Label: value' line each (bidi marks stripped so it pastes cleanly anywhere)."""
    strip = str.maketrans("", "", "⁦⁧⁨⁩‏")
    return "\n".join(f"{k}: {v.replace(chr(10), ', ')}".translate(strip) for k, v in lines(info, personal))


class AboutCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Row")
        self.info = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 20, 20)
        lay.setSpacing(24)
        logo = QLabel()
        logo.setPixmap(clover(56))
        logo.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        cols = QHBoxLayout()                      # two columns of label + value, each with its own row heights
        cols.setSpacing(32)
        self.grids = []
        for _ in range(2):
            g = QGridLayout()
            g.setHorizontalSpacing(18)
            g.setVerticalSpacing(7)
            g.setColumnStretch(1, 1)
            cols.addLayout(g, 1)
            self.grids.append(g)
        self.wait = QLabel(tr("grimoire.aboutview", "Reading this PC…"))
        self.wait.setObjectName("Muted")
        self.grids[0].addWidget(self.wait, 0, 0)
        lay.addLayout(cols, 1)
        side = QVBoxLayout()
        side.setSpacing(10)
        from grimoire.settingsview import _button
        self.copy = _button(tr("grimoire.aboutview", "Copy"), self._copy,
                            tip=tr("grimoire.aboutview", "Copy these specs as plain text to share"))
        self.copy.setEnabled(False)
        side.addWidget(self.copy, 0, Qt.AlignmentFlag.AlignRight)
        self.personal = QCheckBox(tr("grimoire.aboutview", "Show host and user name"))
        self.personal.setToolTip(tr("grimoire.aboutview",
                                    "Off by default, so the copied text has nothing personal in it"))
        self.personal.toggled.connect(lambda _on: self._fill())
        side.addWidget(self.personal, 0, Qt.AlignmentFlag.AlignRight)
        side.addStretch(1)
        lay.addLayout(side)
        self.tick = QTimer(self)                  # the uptime, while the card is on screen
        self.tick.setInterval(60_000)
        self.tick.timeout.connect(self._fill)
        self._asked = False

    def showEvent(self, e):
        super().showEvent(e)
        if self.info is None and not self._asked:
            self._asked = True
            if sysinfo.cached() is not None:
                self._got(True, sysinfo.cached())
            else:
                from grimoire.settingsview import run
                run(sysinfo.info, self._got)
        elif self.info is not None:
            self._fill()
        self.tick.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.tick.stop()

    def _got(self, ok, value):
        if not ok:
            self.wait.setText(tr("grimoire.aboutview", "Couldn't read this PC: {err}").format(err=value))
            return
        self.info = value
        self.copy.setEnabled(True)
        self._fill()

    def _fill(self):
        if self.info is None:
            return
        for g in self.grids:
            while g.count():
                w = g.takeAt(0).widget()
                if w:
                    w.deleteLater()
        rows = lines(self.info, self.personal.isChecked())
        half = (len(rows) + 1) // 2                     # read down the first column, then the second
        for i, (key, value) in enumerate(rows):
            grid, row = (self.grids[0], i) if i < half else (self.grids[1], i - half)
            k = QLabel(key.upper())
            k.setObjectName("Section")
            k.setTextFormat(Qt.TextFormat.PlainText)
            k.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeading)
            if i18n.rtl():                       # a Latin value still lines up on the right in Arabic/Urdu
                value = "\u200f" + value.replace("\n", "\n\u200f")
            v = QLabel(value)
            v.setTextFormat(Qt.TextFormat.PlainText)
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.setFont(QFont(FONT, 10))
            grid.addWidget(k, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(v, row, 1, Qt.AlignmentFlag.AlignTop)
        for g in self.grids:
            for r in range(g.rowCount()):
                g.setRowStretch(r, 0)
            g.setRowStretch(g.rowCount(), 1)

    def _copy(self):
        if self.info is None:
            return
        QGuiApplication.clipboard().setText(summary(self.info, self.personal.isChecked()))
        self.copy.setText(tr("grimoire.aboutview", "Copied"))
        QTimer.singleShot(2000, lambda: self.copy.setText(tr("grimoire.aboutview", "Copy")))


class AboutSection(QWidget):
    """The 'THIS PC' heading and the card, as the home page shows them."""
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 28, 0, 0)
        lay.setSpacing(10)
        text = tr("grimoire.aboutview", "THIS PC")
        head = QLabel(text)
        font = QFont(FONT, 10, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, i18n.spacing(text, 4))
        head.setFont(font)
        lay.addWidget(head)
        lay.addWidget(AboutCard())
