# SPDX-License-Identifier: GPL-3.0-or-later
"""One device's tabs: Overview (send files, clipboard, ping, ring, its files, about, unpair), Notifications, Messages
(sms.py), Media, Commands, Remote (typing and pointer) and Plugins. A tab shows only when the device has the
plugin loaded; each tab reads only while it's on screen.
"""
import time

from PySide6.QtCore import QObject, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QToolButton,
                               QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.glyphs import glyph
from grimoire.i18n import isolate, tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.phonel import kdc
from grimoire.spells.phonel import page as pagemod
from grimoire.spells.phonel.page import TYPE_GLYPH, device_status, lead
from grimoire.spells.systeml.page import _label
from grimoire.widgets import Slider, Switch, segments

TABS = [("overview", tr_noop("grimoire.spells.phonel.views", "Overview"), ""),
        ("notifications", tr_noop("grimoire.spells.phonel.views", "Notifications"), "kdeconnect_notifications"),
        ("messages", tr_noop("grimoire.spells.phonel.views", "Messages"), "kdeconnect_sms"),
        ("media", tr_noop("grimoire.spells.phonel.views", "Media"), "kdeconnect_mprisremote"),
        ("commands", tr_noop("grimoire.spells.phonel.views", "Commands"), "kdeconnect_remotecommands"),
        ("remote", tr_noop("grimoire.spells.phonel.views", "Remote"), ("kdeconnect_remotekeyboard",
                                                                       "kdeconnect_remotecontrol")),
        ("plugins", tr_noop("grimoire.spells.phonel.views", "Plugins"), "")]
TYPES = {"phone": tr_noop("grimoire.spells.phonel.views", "Phone"),
         "smartphone": tr_noop("grimoire.spells.phonel.views", "Phone"),
         "tablet": tr_noop("grimoire.spells.phonel.views", "Tablet"),
         "desktop": tr_noop("grimoire.spells.phonel.views", "Desktop"),
         "laptop": tr_noop("grimoire.spells.phonel.views", "Laptop"),
         "tv": tr_noop("grimoire.spells.phonel.views", "TV")}


class _Got(QObject):
    got = Signal(object)


def fetch(owner, fn, done, serial=False):
    """fn() on the pool (or the ordered action queue), done(result) back on the UI thread; None when fn failed."""
    sig = _Got(owner)

    def work():
        try:
            return fn()
        except Exception:
            return None
    sig.got.connect(lambda r: (done(r), sig.deleteLater()))
    (pagemod.SERIAL if serial else POOL).start(Job(work, sig.got.emit))


def _scroll(inner: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    inner.setObjectName("Page")
    area.setWidget(inner)
    return area


def _clear(lay):
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear(item.layout())


def _row() -> tuple[QFrame, QVBoxLayout, QHBoxLayout]:
    row = QFrame()
    row.setObjectName("Row")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(16, 12, 16, 12)
    lay.setSpacing(12)
    text = QVBoxLayout()
    text.setSpacing(4)
    lay.addLayout(text, 1)
    extra = QHBoxLayout()
    extra.setSpacing(8)
    lay.addLayout(extra)
    return row, text, extra


def _plain(text: str, name: str, wrap=False) -> QLabel:
    """A label for text from the phone (never read as rich text)."""
    lab = _label(lead(text), name, wrap)
    lab.setTextFormat(Qt.TextFormat.PlainText)
    return lab


# ---------------------------------------------------------------- overview
class Overview(QWidget):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.page = view.page
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 12, 0)
        col.setSpacing(12)
        self.offline = _label("", "Muted", wrap=True)
        col.addWidget(self.offline)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.tiles = {}
        for i, (key, icon, label, plugin) in enumerate([
                ("send", "send", tr("grimoire.spells.phonel.views", "Send files…"), "kdeconnect_share"),
                ("clip", "clipboard", tr("grimoire.spells.phonel.views", "Send clipboard"), "kdeconnect_clipboard"),
                ("ping", "ping", tr("grimoire.spells.phonel.views", "Ping"), "kdeconnect_ping"),
                ("ring", "bell", tr("grimoire.spells.phonel.views", "Ring my phone"), "kdeconnect_findmyphone"),
                ("files", "folder", tr("grimoire.spells.phonel.views", "Browse files"), "kdeconnect_sftp"),
                ("unmount", "drive", tr("grimoire.spells.phonel.views", "Close files"), "kdeconnect_sftp")]):
            b = QPushButton(glyph(icon, 20), "  " + label)
            b.setMinimumHeight(52)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.clicked.connect(lambda _=False, k=key: self._do(k))
            b.plugin = plugin
            grid.addWidget(b, i // 3, i % 3)
            self.tiles[key] = b
        self.tiles["send"].setToolTip(tr("grimoire.spells.phonel.views", "Or drop files anywhere on this page"))
        self.tiles["clip"].setToolTip(tr("grimoire.spells.phonel.views", "Sends what you copied on this PC"))
        self.tiles["ring"].setToolTip(tr("grimoire.spells.phonel.views", "Rings loudly, even when it's on silent"))
        self.tiles["files"].setToolTip(tr("grimoire.spells.phonel.views", "Opens the phone's storage in VaultL"))
        col.addLayout(grid)
        col.addSpacing(6)
        col.addWidget(_label(tr("grimoire.spells.phonel.views", "ABOUT"), "NavSection"))
        self.about = QGridLayout()
        self.about.setHorizontalSpacing(24)
        self.about.setVerticalSpacing(6)
        col.addLayout(self.about)
        col.addStretch(1)
        foot = QHBoxLayout()
        foot.addStretch(1)
        self.unpair = QPushButton(tr("grimoire.spells.phonel.views", "Unpair…"))
        self.unpair.clicked.connect(lambda: self.view.dev and self.page.unpair(self.view.dev))
        foot.addWidget(self.unpair)
        col.addLayout(foot)

    def set_device(self, d: dict):
        on = d["reachable"]
        self.offline.setVisible(not on)
        self.offline.setText(tr("grimoire.spells.phonel.views",
                                "{name} isn't connected. Open KDE Connect on it, on the same network as this PC; "
                                "it connects by itself.").format(name=isolate(d["name"])))
        for key, b in self.tiles.items():
            b.setVisible(b.plugin in d["plugins"] or (not on and key not in ("unmount",)))
            b.setEnabled(on and b.plugin in d["plugins"])
        self.tiles["unmount"].setVisible(d["mounted"])
        _clear(self.about)
        rows = [(tr("grimoire.spells.phonel.views", "Status"), device_status(d)),
                (tr("grimoire.spells.phonel.views", "Type"),
                 tr("grimoire.spells.phonel.views", TYPES[d["type"]]) if d["type"] in TYPES else d["type"]),
                (tr("grimoire.spells.phonel.views", "Plugins on"),
                 tr("grimoire.spells.phonel.views", "%n plugin(s)", n=len(d["plugins"])) if on else "—"),
                (tr("grimoire.spells.phonel.views", "Device id"), lead(d["id"]))]
        for i, (k, v) in enumerate(rows):
            self.about.addWidget(_label(k, "Muted"), i, 0)
            val = _label(v, "" if i < 3 else "Tiny")
            val.setTextFormat(Qt.TextFormat.PlainText)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.about.addWidget(val, i, 1)
        self.about.setColumnStretch(1, 1)

    def _do(self, key: str):
        d = self.view.dev
        if not d:
            return
        dev, name = d["id"], isolate(d["name"])
        if key == "send":
            files, _ = QFileDialog.getOpenFileNames(self, tr("grimoire.spells.phonel.views", "Send files to {name}")
                                                    .format(name=d["name"]))
            if files:
                self.view.send(files)
        elif key == "clip":
            self.page.act(lambda: kdc.send_clipboard(dev),
                          tr("grimoire.spells.phonel.views", "Clipboard sent to {name}").format(name=name))
        elif key == "ping":
            self.page.act(lambda: kdc.ping(dev), tr("grimoire.spells.phonel.views", "Pinged {name}").format(name=name))
        elif key == "ring":
            self.page.act(lambda: kdc.ring(dev),
                          tr("grimoire.spells.phonel.views", "{name} is ringing").format(name=name))
        elif key == "files":
            self.page.say(tr("grimoire.spells.phonel.views", "Opening {name}'s files… allow it on the phone if "
                                                             "it asks").format(name=name))
            self.page.act(lambda: kdc.mount(dev), self._opened, then=self.page.refresh, serial=False)
        elif key == "unmount":
            self.page.act(lambda: kdc.unmount(dev), tr("grimoire.spells.phonel.views", "Files closed"),
                          then=self.page.refresh)

    @staticmethod
    def _opened(path: str) -> str:
        pagemod.OPEN_FOLDER(path)
        return tr("grimoire.spells.phonel.views", "Opened in VaultL: {path}").format(path=i18n.ltr(path))


# ---------------------------------------------------------------- notifications
class Notifications(QWidget):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.page = view.page
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        top = QHBoxLayout()
        self.count = _label("", "Muted")
        top.addWidget(self.count, 1)
        self.clear = QPushButton(tr("grimoire.spells.phonel.views", "Dismiss all"))
        self.clear.clicked.connect(self._dismiss_all)
        top.addWidget(self.clear)
        col.addLayout(top)
        inner = QWidget()
        self.list = QVBoxLayout(inner)
        self.list.setContentsMargins(0, 0, 12, 12)
        self.list.setSpacing(8)
        self.list.addStretch(1)
        col.addWidget(_scroll(inner), 1)
        self.items: list = []
        self.keys = None
        self.timer = QTimer(self, interval=4000, timeout=self.load)

    def showEvent(self, e):
        self.timer.start()
        self.load()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def load(self):
        d = self.view.dev
        if d:
            dev = d["id"]
            fetch(self, lambda: kdc.notifications(dev), lambda r, dev=dev: self._got(dev, r))

    def _got(self, dev, items):
        if items is None or not self.view.dev or self.view.dev["id"] != dev:
            return
        self.items = items
        keys = tuple((n["id"], n["title"], n["text"]) for n in items)
        self.count.setText(tr("grimoire.spells.phonel.views", "%n notification(s) on the phone", n=len(items)))
        self.clear.setEnabled(any(n["dismissable"] for n in items))
        if keys == self.keys:
            return
        self.keys = keys
        while self.list.count() > 1:
            w = self.list.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not items:
            self.list.insertWidget(0, _label(tr("grimoire.spells.phonel.views",
                                                "Nothing here. The phone's notifications show up here as they "
                                                "arrive, if the KDE Connect app may read them (Plugin settings → "
                                                "Notification sync on the phone)."), "Muted", wrap=True))
        for i, n in enumerate(items):
            row, text, extra = _row()
            text.addWidget(_plain(n["app"], "Tiny"))
            if n["title"]:
                text.addWidget(_plain(n["title"], "RowTitle", wrap=True))
            body = n["text"] or n["ticker"]
            if body:
                text.addWidget(_plain(body, "", wrap=True))
            if n["reply"]:
                rb = QPushButton(tr("grimoire.spells.phonel.views", "Reply…"))
                rb.clicked.connect(lambda _=False, note=n: self._reply(note))
                extra.addWidget(rb, 0, Qt.AlignmentFlag.AlignTop)
            if n["dismissable"]:
                db = QToolButton()
                db.setObjectName("Tool")
                db.setIcon(glyph("close", 16))
                db.setToolTip(tr("grimoire.spells.phonel.views", "Dismiss on the phone"))
                db.clicked.connect(lambda _=False, note=n: self._dismiss(note))
                extra.addWidget(db, 0, Qt.AlignmentFlag.AlignTop)
            self.list.insertWidget(i, row)

    def _dismiss(self, n):
        dev = self.view.dev["id"]
        self.page.act(lambda: kdc.dismiss(dev, n["id"]), "", then=self.load)

    def _dismiss_all(self):
        dev = self.view.dev["id"]
        ids = [n["id"] for n in self.items if n["dismissable"]]

        def work():
            for nid in ids:
                kdc.dismiss(dev, nid)
        self.page.act(work, tr("grimoire.spells.phonel.views", "%n notification(s) dismissed", n=len(ids)),
                      then=self.load)

    def _reply(self, n):
        text, ok = QInputDialog.getText(self, tr("grimoire.spells.phonel.views", "Reply"),
                                        tr("grimoire.spells.phonel.views", "Reply to {title} ({app}):").format(
                                            title=isolate(n["title"]), app=isolate(n["app"])))
        if ok and text.strip():
            dev = self.view.dev["id"]
            self.page.act(lambda: kdc.reply_notification(dev, n["id"], text.strip()),
                          tr("grimoire.spells.phonel.views", "Reply sent"))

    def heard(self, member, path, args):
        if member in ("notificationPosted", "notificationRemoved", "notificationUpdated",
                      "allNotificationsRemoved") and self.isVisible():
            self.load()


# ---------------------------------------------------------------- media
def _clock(ms: int) -> str:
    s = max(0, ms // 1000)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


class Media(QWidget):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.page = view.page
        self.touched = 0.0
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 12, 0)
        col.setSpacing(12)
        pick = QHBoxLayout()
        pick.addWidget(_label(tr("grimoire.spells.phonel.views", "Player"), "Muted"))
        self.player = QComboBox()
        self.player.setMinimumWidth(220)
        self.player.activated.connect(self._pick)
        pick.addWidget(self.player)
        pick.addStretch(1)
        col.addLayout(pick)
        card = QFrame()
        card.setObjectName("Row")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 22, 24, 22)
        cl.setSpacing(6)
        self.title = _plain("", "SectionTitle", wrap=True)
        cl.addWidget(self.title)
        self.sub = _plain("", "Muted", wrap=True)
        cl.addWidget(self.sub)
        self.time = _label("", "Tiny")
        cl.addWidget(self.time)
        cl.addSpacing(10)
        ctl = QHBoxLayout()
        ctl.setSpacing(6)
        buttons = QWidget()
        buttons.setLayoutDirection(Qt.LayoutDirection.LeftToRight)    # transport controls never mirror
        bl = QHBoxLayout(buttons)
        bl.setContentsMargins(0, 0, 0, 0)
        self.btn = {}
        for action, icon, tip in (("Previous", "prevtrack", tr("grimoire.spells.phonel.views", "Previous")),
                                  ("PlayPause", "play", tr("grimoire.spells.phonel.views", "Play or pause")),
                                  ("Next", "nexttrack", tr("grimoire.spells.phonel.views", "Next"))):
            b = QToolButton()
            b.setObjectName("Tool")
            b.setIcon(glyph(icon, 26))
            b.setIconSize(QSize(26, 26))
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=action: self._action(a))
            bl.addWidget(b)
            self.btn[action] = b
        ctl.addWidget(buttons)
        ctl.addSpacing(16)
        ctl.addWidget(_label(tr("grimoire.spells.phonel.views", "Volume"), "Muted"))
        self.volume = Slider(0, 100, "%")
        self.volume.s.valueChanged.connect(lambda _v: (setattr(self, "touched", time.monotonic()),
                                                       self._send.start()))
        ctl.addWidget(self.volume, 1)
        cl.addLayout(ctl)
        col.addWidget(card)
        self.empty = _label(tr("grimoire.spells.phonel.views",
                               "Nothing is playing on the phone. Start music or a video there and it shows up "
                               "here."), "Muted", wrap=True)
        col.addWidget(self.empty)
        col.addStretch(1)
        self.card = card
        self._send = QTimer(self, singleShot=True, interval=150, timeout=self._send_volume)
        self.timer = QTimer(self, interval=1500, timeout=self.load)

    def showEvent(self, e):
        self.timer.start()
        if self.view.dev:
            dev = self.view.dev["id"]
            fetch(self, lambda: kdc.media_refresh(dev), lambda _r: None)
        self.load()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def load(self):
        if self.view.dev:
            dev = self.view.dev["id"]
            fetch(self, lambda: kdc.media(dev), self._got)

    def _got(self, m):
        if m is None:
            return
        has = bool(m["players"])
        self.card.setVisible(has)
        self.empty.setVisible(not has)
        if not self.player.view().isVisible():
            self.player.blockSignals(True)
            self.player.clear()
            self.player.addItems(m["players"])
            self.player.setCurrentIndex(max(0, self.player.findText(m["player"])))
            self.player.blockSignals(False)
        self.player.setEnabled(len(m["players"]) > 1)
        self.title.setText(lead(m["title"] or tr("grimoire.spells.phonel.views", "Unknown title")))
        self.sub.setText(lead(" · ".join(x for x in (m["artist"], m["album"]) if x)))
        self.time.setText(i18n.ltr(f"{_clock(m['position'])} / {_clock(m['length'])}") if m["length"] else "")
        self.btn["PlayPause"].setIcon(glyph("pause" if m["playing"] else "play", 26))
        self.btn["PlayPause"].setToolTip(tr("grimoire.spells.phonel.views", "Pause") if m["playing"] else
                                         tr("grimoire.spells.phonel.views", "Play"))
        if time.monotonic() - self.touched > 2 and not self.volume.s.isSliderDown():
            self.volume.s.blockSignals(True)
            self.volume.setValue(m["volume"])
            self.volume.s.blockSignals(False)

    def _action(self, action):
        dev = self.view.dev["id"]
        self.page.act(lambda: kdc.media_action(dev, action), "", then=self.load)

    def _pick(self, _i):
        dev, player = self.view.dev["id"], self.player.currentText()
        self.page.act(lambda: kdc.media_player(dev, player), "", then=self.load)

    def _send_volume(self):
        dev, vol = self.view.dev["id"], self.volume.value()
        self.page.act(lambda: kdc.media_volume(dev, vol), "")


# ---------------------------------------------------------------- commands
class Commands(QWidget):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.page = view.page
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        col.addWidget(_label(tr("grimoire.spells.phonel.views",
                                "Commands set up on the other device, to run there from here. They're added in "
                                "KDE Connect on that device (Plugins → Run command)."), "Muted", wrap=True))
        inner = QWidget()
        self.list = QVBoxLayout(inner)
        self.list.setContentsMargins(0, 0, 12, 12)
        self.list.setSpacing(8)
        self.list.addStretch(1)
        col.addWidget(_scroll(inner), 1)

    def showEvent(self, e):
        self.load()
        super().showEvent(e)

    def load(self):
        if self.view.dev:
            dev = self.view.dev["id"]
            fetch(self, lambda: kdc.commands(dev), self._got)

    def heard(self, member, path, args):
        if member == "commandsChanged" and self.isVisible():
            self.load()

    def _got(self, cmds):
        if cmds is None:
            return
        while self.list.count() > 1:
            w = self.list.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not cmds:
            self.list.insertWidget(0, _label(tr("grimoire.spells.phonel.views", "No commands set up yet."),
                                             "Muted", wrap=True))
        for i, c in enumerate(cmds):
            row, text, extra = _row()
            text.addWidget(_plain(c["name"], "RowTitle"))
            cmd = _label(i18n.ltr(c["command"]), "Muted")
            cmd.setTextFormat(Qt.TextFormat.PlainText)
            text.addWidget(cmd)
            run = QPushButton(glyph("play", 16), tr("grimoire.spells.phonel.views", "Run"))
            run.clicked.connect(lambda _=False, cm=c: self._run(cm))
            extra.addWidget(run)
            self.list.insertWidget(i, row)

    def _run(self, c):
        dev = self.view.dev["id"]
        self.page.act(lambda: kdc.run_command(dev, c["key"]),
                      tr("grimoire.spells.phonel.views", "Ran {name}").format(name=isolate(c["name"])))


# ---------------------------------------------------------------- remote input
class Touchpad(QFrame):
    """Drag to move the phone's pointer; click, right-click, wheel to scroll. Moves are batched (one call per tick)."""

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setMinimumHeight(220)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.last: QPoint | None = None
        self.pressed_at = None
        self.dx = self.dy = 0
        self.busy = False
        self.tick = QTimer(self, interval=40, timeout=self._flush)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#2a2a2a"), 1))
        p.setBrush(QColor("#0c0c0c"))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)
        p.setPen(QColor("#5a5a5a"))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                   tr("grimoire.spells.phonel.views", "Drag to move · click · right-click · scroll"))

    def mousePressEvent(self, e):
        self.last = e.position().toPoint()
        self.pressed_at = (self.last, time.monotonic(), e.button())
        self.tick.start()

    def mouseMoveEvent(self, e):
        if self.last is not None:
            pt = e.position().toPoint()
            self.dx += pt.x() - self.last.x()
            self.dy += pt.y() - self.last.y()
            self.last = pt

    def mouseReleaseEvent(self, e):
        self.last = None
        start, t, button = self.pressed_at or (None, 0, None)
        moved = start is not None and (e.position().toPoint() - start).manhattanLength() < 6
        if moved and time.monotonic() - t < 0.4:
            kind = "rightclick" if button == Qt.MouseButton.RightButton else \
                "middleclick" if button == Qt.MouseButton.MiddleButton else "singleclick"
            self._send(lambda dev: kdc.click(dev, kind))

    def wheelEvent(self, e):
        steps = e.angleDelta().y() // 120
        if steps:
            self._send(lambda dev: kdc.scroll(dev, -steps))

    def _flush(self):
        if self.last is None and not (self.dx or self.dy):
            self.tick.stop()
            return
        if self.busy or not (self.dx or self.dy):
            return
        dx, dy = self.dx, self.dy
        self.dx = self.dy = 0
        self.busy = True
        self._send(lambda dev: kdc.move_pointer(dev, dx, dy), done=lambda _r: setattr(self, "busy", False))

    def _send(self, fn, done=lambda _r: None):
        d = self.view.dev
        if d:
            dev = d["id"]
            fetch(self, lambda: fn(dev) or True, done, serial=True)


class Remote(QWidget):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.page = view.page
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 12, 0)
        col.setSpacing(10)
        self.kb_title = _label(tr("grimoire.spells.phonel.views", "TYPE ON THE PHONE"), "NavSection")
        col.addWidget(self.kb_title)
        self.kb_note = _label("", "Muted", wrap=True)
        col.addWidget(self.kb_note)
        kb = QHBoxLayout()
        self.text = QLineEdit()
        self.text.setPlaceholderText(tr("grimoire.spells.phonel.views", "Text to type, Enter sends it"))
        self.text.returnPressed.connect(self._type)
        kb.addWidget(self.text, 1)
        self.keys = []
        for key, label in (("backspace", tr("grimoire.spells.phonel.views", "Backspace")),
                           ("enter", tr("grimoire.spells.phonel.views", "Enter"))):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, k=key: self._press(k))
            kb.addWidget(b)
            self.keys.append(b)
        self.kb_row = QWidget()
        self.kb_row.setLayout(kb)
        col.addWidget(self.kb_row)
        col.addSpacing(8)
        self.pad_title = _label(tr("grimoire.spells.phonel.views", "POINTER"), "NavSection")
        col.addWidget(self.pad_title)
        self.pad_note = _label(tr("grimoire.spells.phonel.views",
                                  "Moves the phone's pointer. On Android this needs KDE Connect's remote input "
                                  "allowed in the phone's Accessibility settings."), "Muted", wrap=True)
        col.addWidget(self.pad_note)
        self.pad = Touchpad(view)
        col.addWidget(self.pad, 1)

    def set_device(self, d: dict):
        kb = "kdeconnect_remotekeyboard" in d["plugins"]
        pad = "kdeconnect_remotecontrol" in d["plugins"]
        for w in (self.kb_title, self.kb_note, self.kb_row):
            w.setVisible(kb)
        for w in (self.pad_title, self.pad_note, self.pad):
            w.setVisible(pad)

    def showEvent(self, e):
        d = self.view.dev
        if d and "kdeconnect_remotekeyboard" in d["plugins"]:
            dev = d["id"]
            fetch(self, lambda: kdc.keyboard_active(dev), self._kb_state)
        super().showEvent(e)

    def _kb_state(self, on):
        self.kb_note.setText(tr("grimoire.spells.phonel.views", "The phone's KDE Connect keyboard is active: "
                                                                "what you type here appears there.") if on else
                             tr("grimoire.spells.phonel.views", "Pick KDE Connect's keyboard on the phone (it shows "
                                                                "when you tap a text field) to type from here."))

    def _type(self):
        text = self.text.text()
        if text and self.view.dev:
            dev = self.view.dev["id"]
            self.text.clear()
            self.page.act(lambda: kdc.type_text(dev, text), "")

    def _press(self, key):
        if self.view.dev:
            dev = self.view.dev["id"]
            self.page.act(lambda: kdc.press(dev, key), "")


# ---------------------------------------------------------------- plugins
class Plugins(QWidget):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.page = view.page
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        self.note = _label("", "Muted", wrap=True)
        col.addWidget(self.note)
        inner = QWidget()
        self.list = QVBoxLayout(inner)
        self.list.setContentsMargins(0, 0, 12, 12)
        self.list.setSpacing(6)
        self.list.addStretch(1)
        col.addWidget(_scroll(inner), 1)

    def showEvent(self, e):
        self.load()
        super().showEvent(e)

    def load(self):
        d = self.view.dev
        if d:
            self.note.setText(tr("grimoire.spells.phonel.views",
                                 "What {name} and this PC may do together. A switch here changes it for this "
                                 "device only; the phone has its own switches in its app.").format(
                name=isolate(d["name"])))
            dev, sup = d["id"], d["supported"]
            fetch(self, lambda: kdc.plugins(dev, sup), self._got)

    def _got(self, items):
        if items is None:
            return
        while self.list.count() > 1:
            w = self.list.takeAt(0).widget()
            if w:
                w.deleteLater()
        items = sorted(items, key=lambda it: kdc.plugin_name(it[0]).lower())
        for i, (pid, on) in enumerate(items):
            row, text, extra = _row()
            row.layout().setContentsMargins(16, 8, 16, 8)
            text.addWidget(_label(kdc.plugin_name(pid), ""))
            sw = Switch()
            sw.setChecked(on)
            sw.setAccessibleName(kdc.plugin_name(pid))
            sw.toggled.connect(lambda v, p=pid: self._set(p, v))
            extra.addWidget(sw)
            self.list.insertWidget(i, row)

    def _set(self, pid, on):
        dev = self.view.dev["id"]
        self.page.act(lambda: kdc.set_plugin(dev, pid, on),
                      (tr("grimoire.spells.phonel.views", "{plugin} on") if on else
                       tr("grimoire.spells.phonel.views", "{plugin} off")).format(plugin=kdc.plugin_name(pid)),
                      then=self.page.refresh)


# ---------------------------------------------------------------- the device view
class DeviceView(QWidget):
    def __init__(self, page):
        super().__init__()
        from grimoire.spells.phonel.sms import Messages
        self.page = page
        self.dev: dict | None = None
        self.setAcceptDrops(True)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(14)
        head = QHBoxLayout()
        head.setSpacing(12)
        self.icon = QLabel()
        head.addWidget(self.icon)
        self.status = _label("", "Muted", wrap=True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        head.addWidget(self.status, 1)
        col.addLayout(head)
        tabs = QHBoxLayout()
        tabs.setSpacing(0)
        self.tab_buttons = {}
        for tid, name, _plugin in TABS:
            b = QPushButton(tr("grimoire.spells.phonel.views", name))
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, t=tid: self.show_tab(t))
            tabs.addWidget(b)
            self.tab_buttons[tid] = b
        tabs.addStretch(1)
        col.addLayout(tabs)
        self.stack = QStackedWidget()
        self.tabs = {"overview": Overview(self), "notifications": Notifications(self), "messages": Messages(self),
                     "media": Media(self), "commands": Commands(self), "remote": Remote(self),
                     "plugins": Plugins(self)}
        for w in self.tabs.values():
            self.stack.addWidget(w)
        col.addWidget(self.stack, 1)
        self.tab = "overview"
        self.shown: tuple = ()
        QShortcut(QKeySequence("Ctrl+PgDown"), self, lambda: self._cycle(1))
        QShortcut(QKeySequence("Ctrl+PgUp"), self, lambda: self._cycle(-1))

    def available(self, d: dict) -> list[str]:
        out = []
        for tid, _name, plugin in TABS:
            if tid == "plugins":
                ok = d["paired"]
            elif not plugin:
                ok = True
            else:
                need = plugin if isinstance(plugin, tuple) else (plugin,)
                ok = d["reachable"] and any(p in d["plugins"] for p in need)
            if ok:
                out.append(tid)
        return out

    def set_device(self, d: dict | None, changed: bool = False):
        old = self.dev
        self.dev = d
        if d is None:
            return
        self.icon.setPixmap(glyph(TYPE_GLYPH.get(d["type"], "phone"), 32).pixmap(32, 32))
        self.status.setText(device_status(d))
        shown = tuple(self.available(d))
        if shown != self.shown:
            self.shown = shown
            for tid, b in self.tab_buttons.items():
                b.setVisible(tid in shown)
            segments([self.tab_buttons[t] for t in shown])
        if old is None or old["id"] != d["id"] or self.tab not in shown:
            self.show_tab("overview")
        self.tabs["overview"].set_device(d)
        self.tabs["remote"].set_device(d)
        if old and old["id"] != d["id"]:
            self.tabs["messages"].reset()

    def show_tab(self, tid: str):
        self.tab = tid
        for t, b in self.tab_buttons.items():
            b.setChecked(t == tid)
        self.stack.setCurrentWidget(self.tabs[tid])

    def _cycle(self, step: int):
        if self.shown and self.isVisible():
            i = self.shown.index(self.tab) if self.tab in self.shown else 0
            self.show_tab(self.shown[(i + step) % len(self.shown)])

    def heard(self, member, path, args):
        if not self.dev or not path.startswith(kdc.dev_path(self.dev["id"])):
            return
        for tab in ("notifications", "messages", "commands"):
            self.tabs[tab].heard(member, path, args)

    def send(self, files: list[str]):
        d = self.dev
        if not d or "kdeconnect_share" not in d["plugins"]:
            return
        dev, name = d["id"], isolate(d["name"])
        self.page.act(lambda: kdc.send_files(dev, files),
                      lambda n: tr("grimoire.spells.phonel.views", "Sending %n file(s) to {name}…", n=n).format(
                          name=name))

    def dragEnterEvent(self, e):
        if self.dev and "kdeconnect_share" in self.dev["plugins"] and e.mimeData().hasUrls() and \
                all(u.isLocalFile() for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.send([u.toLocalFile() for u in e.mimeData().urls()])

