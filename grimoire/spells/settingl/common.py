# SPDX-License-Identifier: GPL-3.0-or-later
"""Pieces every SettingL page is built from: a scrolling panel that reads off the UI thread, rows, links to KDE's
modules and to the other spells, and gray app icons (so the pages stay black & white)."""

import os
import subprocess
import sys
import time

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from grimoire import i18n
from grimoire.glyphs import glyph
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.paths import ROOT

_icons: dict[str, QIcon | None] = {}


def label(text="", name="", wrap=False, plain=False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    if plain:  # names that come from devices, apps or other people
        lab.setTextFormat(Qt.TextFormat.PlainText)
    if i18n.rtl():  # Latin text (a device's name, a version) still starts on the right
        lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignVCenter)
    return lab


def combo(min_width=220) -> QComboBox:
    c = QComboBox()
    c.setMinimumWidth(min_width)
    c.setMaximumWidth(420)
    c.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    c.setMinimumContentsLength(18)
    return c


def gray_icon(name: str, size: int = 32) -> QIcon | None:
    """A theme icon (an app's own) turned gray; None when the theme has none."""
    if not name:
        return None
    if name in _icons:
        return _icons[name]
    icon = None
    if os.path.isabs(name) and os.path.isfile(name):
        src = QIcon(name)
    elif QIcon.hasThemeIcon(name):
        src = QIcon.fromTheme(name)
    else:
        src = None
    if src is not None and not src.isNull():
        img = src.pixmap(size).toImage().convertToFormat(QImage.Format.Format_ARGB32)
        gray = img.convertToFormat(QImage.Format.Format_Grayscale8).convertToFormat(QImage.Format.Format_ARGB32)
        gray.setAlphaChannel(img.convertToFormat(QImage.Format.Format_Alpha8))
        icon = QIcon(QPixmap.fromImage(gray))
    _icons[name] = icon
    return icon


class Row(QFrame):
    """A setting: its title and a line under it on the reading side, the control on the other."""

    def __init__(self, title: str, sub: str = "", control: QWidget | None = None, icon: QIcon | None = None):
        super().__init__()
        self.setObjectName("Row")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        lay.setSpacing(14)
        if icon is not None:
            ic = QLabel()
            ic.setPixmap(icon.pixmap(24, 24))
            ic.setFixedWidth(28)
            lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignVCenter)
        text = QVBoxLayout()
        text.setSpacing(3)
        self.title = label(title, "RowTitle")
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text.addWidget(self.title)
        self.sub = label(sub, "Muted", wrap=True)
        self.sub.setVisible(bool(sub))
        text.addWidget(self.sub)
        lay.addLayout(text, 1)
        self.right = QHBoxLayout()
        self.right.setSpacing(8)
        lay.addLayout(self.right)
        if control is not None:
            self.right.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_sub(self, text: str):
        self.sub.setText(text)
        self.sub.setVisible(bool(text))


class _Sig(QObject):
    loaded = Signal(object)


class Panel(QScrollArea):
    """A page: a column of sections that scrolls. read() runs on a worker thread whenever the page is shown (at
    most every STALE seconds) and its answer goes to fill() on the UI thread."""

    STALE = 3.0
    POLL = 0  # ms; > 0 reads again on a timer while the page is on screen

    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        self.col = QVBoxLayout(inner)
        self.col.setContentsMargins(0, 4, 14, 24)
        self.col.setSpacing(10)
        self.setWidget(inner)
        self._sig = _Sig()
        self._sig.loaded.connect(self._loaded)
        self._busy = False
        self._at = 0.0
        self.data = None
        self._poll_timer = QTimer(self, interval=max(self.POLL, 1000), timeout=self.load)

    # ------------------------------------------------------------ building
    def section(self, text: str) -> QLabel:
        lab = label(text, "SectionTitle")
        self.col.addSpacing(8)
        self.col.addWidget(lab)
        return lab

    def note(self, text: str) -> QLabel:
        lab = label(text, "Muted", wrap=True)
        self.col.addWidget(lab)
        return lab

    def kde_links(self, modules: list[str], text: str = ""):
        """A last line: the matching modules of KDE's own System Settings."""
        self.col.addSpacing(10)
        self.col.addWidget(label(text or tr("grimoire.spells.settingl.common", "MORE IN KDE'S SETTINGS"), "NavSection"))
        self.col.addWidget(FlowLinks(modules, self.host))

    def finish(self):
        self.col.addStretch(1)

    # ------------------------------------------------------------ reading
    def read(self):
        return None

    def fill(self, data):
        pass

    def load(self, force=False):
        if self._busy or (
            not force and time.monotonic() - self._at < self.STALE and self.data is not None and not self.POLL
        ):
            return
        self._busy = True
        reader = self.read

        def work():
            try:
                return ("ok", reader())
            except Exception as e:  # an answer always comes back, so _busy clears
                return ("error", str(e))

        POOL.start(Job(work, self._sig.loaded.emit))

    def _loaded(self, result):
        self._busy = False
        self._at = time.monotonic()
        kind, data = result
        if kind == "error":
            self.host.say(
                tr("grimoire.spells.settingl.common", "Couldn't read the settings: {error}").format(error=data)
            )
            return
        self.data = data
        self.fill(data)

    def showEvent(self, e):
        super().showEvent(e)
        self.load()
        if self.POLL:
            self._poll_timer.start(self.POLL)

    def hideEvent(self, e):
        self._poll_timer.stop()
        super().hideEvent(e)

    def act(self, what: str, fn, then=None, quiet=False):
        self.host.act(what, fn, then=then or (lambda: self.load(force=True)), quiet=quiet)


class FlowLinks(QWidget):
    """Buttons that open KDE's modules, wrapped in rows of three; names in KDE's language for ours. Built once the
    host has read the module list (on a worker thread when SettingL opens)."""

    def __init__(self, modules: list[str], host):
        super().__init__()
        self.host, self.modules = host, modules
        self.grid = QVBoxLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        if host.modules is None:
            host.modules_ready.connect(self._build)
        else:
            self._build()

    def _build(self):
        names = {m["id"]: m["name"] for m in self.host.modules or []}
        row = None
        shown = [m for m in self.modules if m in names]
        for i, mid in enumerate(shown):
            if i % 3 == 0:
                if row is not None:
                    row.addStretch(1)
                row = QHBoxLayout()
                row.setSpacing(4)
                self.grid.addLayout(row)
            b = QPushButton(glyph("forward", 14), " " + names[mid].replace("&", "&&"))
            b.setObjectName("Link")
            b.setIconSize(QSize(14, 14))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(
                tr("grimoire.spells.settingl.common", "Opens KDE's own {module} settings").format(
                    module=i18n.isolate(names[mid])
                )
            )
            b.clicked.connect(lambda _=False, m=mid: self.host.open_module(m))
            row.addWidget(b)
        if row is not None:
            row.addStretch(1)


def open_spell(widget: QWidget, spell_id: str, then=None):
    """Show another spell: in the hub's own window when SettingL is in it (then(page) can pick a tab), else in a
    new Grimoire window."""
    win = widget.window()
    pages = getattr(win, "pages", None)
    if isinstance(pages, dict) and spell_id in pages and hasattr(win, "open"):
        win.open(spell_id)
        if then:
            then(win.pages[spell_id][1])
        return
    env = dict(os.environ, PYTHONPATH=f"{ROOT}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"))
    subprocess.Popen(
        [sys.executable, "-m", "grimoire", spell_id],
        env=env,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


OPEN_SPELL = open_spell  # stub point for tests


def minutes(seconds: int) -> str:
    """A timeout as shown: "Never", "5 min", "1 h 30 min"."""
    if not seconds:
        return tr("grimoire.spells.settingl.common", "Never")
    m = round(seconds / 60)
    if m < 60:
        return tr("grimoire.spells.settingl.common", "%n min", n=m)
    h, rest = divmod(m, 60)
    if rest:
        return tr("grimoire.spells.settingl.common", "{hours} h {minutes} min").format(hours=h, minutes=rest)
    return tr("grimoire.spells.settingl.common", "%n h", n=h)
