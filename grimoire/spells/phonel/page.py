# SPDX-License-Identifier: GPL-3.0-or-later
"""PhoneL page: your phone on this PC, through KDE Connect's own daemon (kdeconnectd). Paired devices on the left,
"Add a device" for pairing; each device has tabs for what its plugins allow: send files, ping, ring, clipboard,
its files in VaultL, its notifications, text messages, media, commands, typing and pointer, and the plugins.

Every D-Bus call runs on the worker pool; the frame is read every 3 s while the page is on screen (never while it's
hidden) and at once when the daemon signals a change (listen.py).
"""
from PySide6.QtCore import QObject, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.glyphs import glyph
from grimoire.i18n import isolate, tr
from grimoire.jobs import POOL, Job
from grimoire.spells.phonel import kdc
from grimoire.spells.phonel.listen import Listener
from grimoire.spells.systeml.page import _label

POLL_MS = 3000
# actions run one at a time, in the order you made them (typed text, then Enter; a move, then the click)
SERIAL = QThreadPool()
SERIAL.setMaxThreadCount(1)
TYPE_GLYPH = {"phone": "phone", "smartphone": "phone", "tablet": "tablet", "desktop": "desktop",
              "laptop": "desktop", "tv": "desktop"}


def lead(text: str) -> str:
    """A label holding only text from the phone or a user (a name, a message): in a right-to-left language it lines
    up on the right like the translated text around it, while the text itself keeps its own direction."""
    return "\u200f" + isolate(text) if text and i18n.rtl() else text


def open_folder(path: str):
    """The phone's files open in VaultL (a separate window). Stub point for tests."""
    from grimoire.tray import launch
    launch("grimoire-vaultl", path)


OPEN_FOLDER = open_folder


def device_status(d: dict) -> str:
    """One line under a device's name: connection, battery, signal."""
    if not d["paired"]:
        bits = [tr("grimoire.spells.phonel.page", "Not paired")]
    elif d["reachable"]:
        bits = [tr("grimoire.spells.phonel.page", "Connected")]
    else:
        bits = [tr("grimoire.spells.phonel.page", "Not connected")]
    if d.get("battery"):
        b = d["battery"]
        bits.append(tr("grimoire.spells.phonel.page", "Battery {n}%, charging").format(n=b["charge"])
                    if b["charging"] else tr("grimoire.spells.phonel.page", "Battery {n}%").format(n=b["charge"]))
    if d.get("signal"):
        s = d["signal"]
        bars = "▂▄▆█"[:max(0, min(4, s["strength"]))] or "·"
        bits.append(i18n.ltr(f"{s['type']} {bars}".strip()))
    if d.get("mounted"):
        bits.append(tr("grimoire.spells.phonel.page", "Files open"))
    return " · ".join(bits)


class _Signals(QObject):
    snap = Signal(object)
    acted = Signal(object)        # (ok, message, then)
    heard = Signal(object)        # (member, path, args) from the listener thread


# ---------------------------------------------------------------- KDE Connect not ready
class StatePanel(QWidget):
    """Shown while there's no daemon to talk to: why, and what fixes it."""

    def __init__(self, page):
        super().__init__()
        self.page = page
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        self.title = _label("", "SectionTitle", wrap=True)
        lay.addWidget(self.title)
        self.text = _label("", "Muted", wrap=True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.text)
        row = QHBoxLayout()
        self.start = QPushButton(tr("grimoire.spells.phonel.page", "Start KDE Connect"))
        self.start.setObjectName("Primary")
        self.start.clicked.connect(self._start)
        row.addWidget(self.start)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)

    def show_state(self, state: str, error: str = ""):
        self.start.setVisible(state == "stopped")
        self.start.setEnabled(True)
        if state == "stopped":
            self.title.setText(tr("grimoire.spells.phonel.page", "KDE Connect isn't running"))
            self.text.setText(tr("grimoire.spells.phonel.page",
                                 "PhoneL works through KDE Connect's background service, kdeconnectd, which keeps "
                                 "the link to your phone. Start it to see your devices. Plasma starts it at login "
                                 "unless it was turned off in System Settings → Autostart."))
        elif state == "missing":
            self.title.setText(tr("grimoire.spells.phonel.page", "KDE Connect isn't installed"))
            self.text.setText(tr("grimoire.spells.phonel.page",
                                 "PhoneL works through KDE Connect, which does the pairing, the encryption and the "
                                 "link to your phone. Install it with:\n\n{command}").format(command=kdc.APT))
        elif state == "nogi":
            self.title.setText(tr("grimoire.spells.phonel.page", "A Python module is missing"))
            self.text.setText(tr("grimoire.spells.phonel.page",
                                 "PhoneL talks to KDE Connect through GLib's D-Bus bindings. Install them with:"
                                 "\n\n{command}").format(command=kdc.APT_GI))
        else:
            self.title.setText(tr("grimoire.spells.phonel.page", "Can't reach KDE Connect"))
            self.text.setText(error or tr("grimoire.spells.phonel.page", "The session bus isn't answering."))

    def _start(self):
        self.start.setEnabled(False)
        self.page.act(kdc.start, tr("grimoire.spells.phonel.page", "KDE Connect started"), then=self.page.refresh)


# ---------------------------------------------------------------- pairing
class AddPanel(QScrollArea):
    """Devices asking to pair, waiting for an answer, or nearby; how to get the phone app; this PC's name."""

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 20)
        col.setSpacing(10)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        col.addLayout(self.body)
        col.addSpacing(10)
        col.addWidget(_label(tr("grimoire.spells.phonel.page", "HOW TO CONNECT A PHONE"), "NavSection"))
        mark = "\u200f" if i18n.rtl() else ""        # each line is its own paragraph: keep it right to left
        stores = "\n".join(f"{mark}    {name}: {i18n.ltr(url)}" for name, url in kdc.STORES)
        steps = _label(tr("grimoire.spells.phonel.page",
                          "1. Install the KDE Connect app on your phone:\n{stores}\n"
                          "2. Connect the phone to the same Wi-Fi network as this PC and open the app.\n"
                          "3. This PC shows up in the app and the phone shows up here. Press Pair on one side "
                          "and accept on the other.\n\n"
                          "Not showing up? A firewall may be blocking KDE Connect: it needs ports 1714 to 1764 "
                          "(TCP and UDP). With ufw: {command}").format(
            stores=stores, command=i18n.ltr("sudo ufw allow 1714:1764/udp && sudo ufw allow 1714:1764/tcp")),
            "Muted", wrap=True)
        steps.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(steps)
        again = QHBoxLayout()
        look = QPushButton(glyph("search", 16), tr("grimoire.spells.phonel.page", "Look again"))
        look.setToolTip(tr("grimoire.spells.phonel.page", "Announce this PC on the network again"))
        look.clicked.connect(lambda: self.page.act(kdc.refresh_network,
                                                   tr("grimoire.spells.phonel.page", "Looking for devices…"),
                                                   then=self.page.refresh))
        again.addWidget(look)
        again.addStretch(1)
        col.addLayout(again)
        col.addSpacing(10)
        col.addWidget(_label(tr("grimoire.spells.phonel.page", "THIS PC"), "NavSection"))
        name_row = QHBoxLayout()
        from PySide6.QtWidgets import QLineEdit
        self.name = QLineEdit()
        self.name.setMaxLength(32)
        self.name.setPlaceholderText(tr("grimoire.spells.phonel.page", "This PC's name on your devices"))
        self.name.returnPressed.connect(self._rename)
        name_row.addWidget(self.name, 1)
        ren = QPushButton(tr("grimoire.spells.phonel.page", "Rename"))
        ren.clicked.connect(self._rename)
        name_row.addWidget(ren)
        col.addLayout(name_row)
        col.addStretch(1)
        self.setWidget(inner)
        self.keys = None

    def set_snap(self, snap: dict):
        if not self.name.hasFocus() and not self.name.isModified():
            self.name.setText(snap["name"])
        devs = [d for d in snap["devices"] if not d["paired"] and d["reachable"]]
        keys = tuple((d["id"], d["name"], d["by_peer"], d["requested"], d["key"]) for d in devs)
        if keys == self.keys:
            return
        self.keys = keys
        while self.body.count():
            w = self.body.takeAt(0).widget()
            if w:
                w.deleteLater()
        asking = [d for d in devs if d["by_peer"]]
        waiting = [d for d in devs if d["requested"] and not d["by_peer"]]
        nearby = [d for d in devs if not d["requested"] and not d["by_peer"]]
        if asking:
            self.body.addWidget(_label(tr("grimoire.spells.phonel.page", "ASKING TO PAIR"), "NavSection"))
            for d in asking:
                row = self._row(d, tr("grimoire.spells.phonel.page",
                                      "Wants to pair with this PC. Accept only if you asked for it and the phone "
                                      "shows this key: {key}").format(key=i18n.ltr(d["key"] or "…")))
                ok = QPushButton(tr("grimoire.spells.phonel.page", "Accept"))
                ok.setObjectName("Primary")
                ok.clicked.connect(lambda _=False, dev=d: self.page.accept(dev))
                no = QPushButton(tr("grimoire.spells.phonel.page", "Turn down"))
                no.clicked.connect(lambda _=False, dev=d: self.page.act(
                    lambda: kdc.cancel_pairing(dev["id"]), tr("grimoire.spells.phonel.page", "Turned down"),
                    then=self.page.refresh))
                row.extra.addWidget(ok)
                row.extra.addWidget(no)
                self.body.addWidget(row)
        if waiting:
            self.body.addWidget(_label(tr("grimoire.spells.phonel.page", "WAITING FOR THE OTHER DEVICE"),
                                       "NavSection"))
            for d in waiting:
                row = self._row(d, tr("grimoire.spells.phonel.page",
                                      "Accept on the device. Check that it shows this key: {key}").format(
                    key=i18n.ltr(d["key"] or "…")))
                stop = QPushButton(tr("grimoire.spells.phonel.page", "Cancel"))
                stop.clicked.connect(lambda _=False, dev=d: self.page.act(
                    lambda: kdc.cancel_pairing(dev["id"]), tr("grimoire.spells.phonel.page", "Pairing cancelled"),
                    then=self.page.refresh))
                row.extra.addWidget(stop)
                self.body.addWidget(row)
        self.body.addWidget(_label(tr("grimoire.spells.phonel.page", "NEARBY"), "NavSection"))
        if not nearby:
            self.body.addWidget(_label(tr("grimoire.spells.phonel.page",
                                          "No unpaired devices nearby. Open the KDE Connect app on your phone, on "
                                          "the same network."), "Muted", wrap=True))
        for d in nearby:
            row = self._row(d, tr("grimoire.spells.phonel.page", "Ready to pair"))
            pair = QPushButton(tr("grimoire.spells.phonel.page", "Pair…"))
            pair.clicked.connect(lambda _=False, dev=d: self.page.pair(dev))
            row.extra.addWidget(pair)
            self.body.addWidget(row)

    def _row(self, d: dict, text: str) -> QFrame:
        row = QFrame()
        row.setObjectName("Row")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)
        ic = QLabel()
        ic.setPixmap(glyph(TYPE_GLYPH.get(d["type"], "phone"), 24).pixmap(24, 24))
        lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        title = _label(lead(d["name"]), "RowTitle")
        title.setTextFormat(Qt.TextFormat.PlainText)
        texts.addWidget(title)
        sub = _label(text, "Muted", wrap=True)
        sub.setTextFormat(Qt.TextFormat.PlainText)
        texts.addWidget(sub)
        lay.addLayout(texts, 1)
        row.extra = QHBoxLayout()
        row.extra.setSpacing(8)
        lay.addLayout(row.extra)
        return row

    def _rename(self):
        name = self.name.text()
        self.name.setModified(False)
        self.page.act(lambda: kdc.rename_pc(name),
                      tr("grimoire.spells.phonel.page", "This PC is now called {name}").format(
                          name=isolate(" ".join(name.split()))), then=self.page.refresh)


# ---------------------------------------------------------------- the page
class PhoneLPage(QWidget):
    def __init__(self):
        super().__init__()
        from grimoire.spells.phonel.views import DeviceView
        self.setObjectName("Page")
        self.sig = _Signals()
        self.snap: dict = {"state": "", "devices": [], "name": ""}
        self.current = ""                 # device id shown, "" = Add a device
        self._busy = False
        self.listener = Listener(lambda member, path, args: self.sig.heard.emit((member, path, args)))

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        nav = QFrame()
        nav.setObjectName("SubNav")
        nav.setMinimumWidth(210)
        nav.setMaximumWidth(300)
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(12, 26, 12, 16)
        nl.setSpacing(2)
        nl.addWidget(_label("PhoneL", "Title"))
        nl.addSpacing(12)
        nl.addWidget(_label(tr("grimoire.spells.phonel.page", "DEVICES"), "NavSection"))
        self.dev_list = QVBoxLayout()
        self.dev_list.setSpacing(2)
        nl.addLayout(self.dev_list)
        self.none = _label(tr("grimoire.spells.phonel.page", "No paired devices yet"), "Tiny", wrap=True)
        nl.addWidget(self.none)
        nl.addSpacing(8)
        self.add_btn = QPushButton(glyph("plus", 18), "  " + tr("grimoire.spells.phonel.page", "Add a device"))
        self.add_btn.setObjectName("SubNavItem")
        self.add_btn.setCheckable(True)
        self.add_btn.clicked.connect(lambda: self.show_device(""))
        nl.addWidget(self.add_btn)
        nl.addStretch(1)
        self.foot = _label("", "Tiny", wrap=True)
        self.foot.setTextFormat(Qt.TextFormat.PlainText)
        nl.addWidget(self.foot)
        root.addWidget(nav)
        self.dev_buttons: dict = {}
        self.dev_keys = None

        right = QVBoxLayout()
        right.setContentsMargins(32, 26, 32, 18)
        right.setSpacing(14)
        self.heading = _label("", "PageHeading")
        self.heading.setTextFormat(Qt.TextFormat.PlainText)
        right.addWidget(self.heading)
        self.stack = QStackedWidget()
        self.state_panel = StatePanel(self)
        self.add_panel = AddPanel(self)
        self.device_view = DeviceView(self)
        for w in (self.state_panel, self.add_panel, self.device_view):
            self.stack.addWidget(w)
        right.addWidget(self.stack, 1)
        self.toast = _label("", "Toast", wrap=True)
        self.toast.setTextFormat(Qt.TextFormat.PlainText)       # carries device names and KDE Connect's errors
        self.toast.hide()
        right.addWidget(self.toast)
        self._toast_timer = QTimer(self, singleShot=True, interval=6000, timeout=self.toast.hide)
        root.addLayout(right, 1)

        self.sig.snap.connect(self._snapped)
        self.sig.acted.connect(self._acted)
        self.sig.heard.connect(self._heard)
        self.timer = QTimer(self, interval=POLL_MS, timeout=self.refresh)
        self._soon = QTimer(self, singleShot=True, interval=250, timeout=self.refresh)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Refresh), self, self.refresh)
        self.stack.setCurrentWidget(self.state_panel)
        self.state_panel.show_state("loading")
        self.state_panel.title.setText(tr("grimoire.spells.phonel.page", "Looking for KDE Connect…"))
        self.state_panel.text.setText("")

    # ------------------------------------------------------------ reading
    def showEvent(self, e):
        self.timer.start()
        self.refresh()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        self.listener.stop()
        super().hideEvent(e)

    def refresh(self):
        if self._busy:
            return
        self._busy = True
        POOL.start(Job(kdc.snapshot, self.sig.snap.emit))

    def _snapped(self, snap: dict):
        self._busy = False
        self.snap = snap
        if snap["state"] != "running":
            self.listener.stop()
            self.heading.setText("PhoneL")
            self.state_panel.show_state(snap["state"], snap.get("error", ""))
            self.stack.setCurrentWidget(self.state_panel)
            self._nav([])
            self.foot.setText("")
            self.add_btn.hide()
            return
        self.add_btn.show()
        if self.isVisible():
            self.listener.start()
        self.foot.setText(tr("grimoire.spells.phonel.page", "This PC: {name}").format(name=isolate(snap["name"])))
        paired = [d for d in snap["devices"] if d["paired"]]
        self._nav(paired)
        asking = sum(1 for d in snap["devices"] if d["by_peer"] and not d["paired"])
        self.add_btn.setText("  " + (tr("grimoire.spells.phonel.page", "Add a device ({n})").format(n=asking)
                                     if asking else tr("grimoire.spells.phonel.page", "Add a device")))
        self.add_panel.set_snap(snap)
        ids = [d["id"] for d in paired]
        if self.current not in ids:
            if self.current == "" and self.stack.currentWidget() is self.add_panel:
                pass
            else:
                reach = [d["id"] for d in paired if d["reachable"]]
                self.current = (reach or ids or [""])[0]
        self.show_device(self.current, quiet=True)

    def _nav(self, devices: list):
        keys = tuple((d["id"], d["name"], d["type"]) for d in devices)
        if keys != self.dev_keys:
            self.dev_keys = keys
            for b in self.dev_buttons.values():
                b.deleteLater()
            self.dev_buttons = {}
            for d in devices:
                b = QPushButton(glyph(TYPE_GLYPH.get(d["type"], "phone"), 18), "  " + d["name"].replace("&", "&&"))
                b.setObjectName("SubNavItem")
                b.setCheckable(True)
                b.clicked.connect(lambda _=False, dev=d["id"]: self.show_device(dev))
                self.dev_list.addWidget(b)
                self.dev_buttons[d["id"]] = b
        for d in devices:
            self.dev_buttons[d["id"]].setToolTip(device_status(d))
        self.none.setVisible(not devices and self.snap.get("state") == "running")

    def device(self, dev: str | None = None) -> dict | None:
        dev = self.current if dev is None else dev
        return next((d for d in self.snap["devices"] if d["id"] == dev), None)

    # ------------------------------------------------------------ navigation
    def show_device(self, dev: str, quiet: bool = False):
        if self.snap.get("state") != "running":
            return
        changed = dev != self.current
        self.current = dev
        for d, b in self.dev_buttons.items():
            b.setChecked(d == dev)
        self.add_btn.setChecked(not dev)
        d = self.device(dev) if dev else None
        if d is None:
            self.heading.setText(tr("grimoire.spells.phonel.page", "Add a device"))
            self.stack.setCurrentWidget(self.add_panel)
            self.device_view.set_device(None)
            return
        self.heading.setText(lead(d["name"]))
        self.stack.setCurrentWidget(self.device_view)
        self.device_view.set_device(d, changed=changed or not quiet)

    # ------------------------------------------------------------ signals from the daemon
    def _heard(self, event):
        member, path, args = event
        if member in ("deviceAdded", "deviceRemoved", "deviceVisibilityChanged", "deviceListChanged",
                      "pairingRequestsChanged", "pairStateChanged", "reachableChanged", "pluginsChanged",
                      "nameChanged", "announcedNameChanged", "refreshed", "mounted", "unmounted",
                      "pairingFailed"):
            self._soon.start()
            if member == "pairingFailed" and args:
                self.say(tr("grimoire.spells.phonel.page", "Pairing failed: {error}").format(error=args[0]))
        self.device_view.heard(member, path, args)

    # ------------------------------------------------------------ actions
    def act(self, fn, done, then=None, serial=True):
        """Run fn on the action queue (or the pool, for slow ones); say done (a text, or a function of fn's result)
        or the error in the toast."""
        def work():
            try:
                result = fn()
                return (True, done(result) if callable(done) else done, then)
            except kdc.Error as err:
                return (False, str(err), then)
            except Exception as err:                    # shown to the user, not a crash
                return (False, str(err) or type(err).__name__, then)
        (SERIAL if serial else POOL).start(Job(work, self.sig.acted.emit))

    def _acted(self, result):
        ok, msg, then = result
        if msg:
            self.say(msg if ok else tr("grimoire.spells.phonel.page", "Didn't work: {error}").format(error=msg))
        if then:
            then()

    def say(self, text: str):
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start()

    def ask(self, title: str, text: str, yes: str) -> bool:
        box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=self)
        box.setTextFormat(Qt.TextFormat.PlainText)        # device names come from the network: no markup that
                                                          # could fake the key or the warning in a pairing prompt
        ok = box.addButton(yes, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("grimoire.spells.phonel.page", "Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(ok)
        box.exec()
        return box.clickedButton() is ok

    def pair(self, d: dict):
        if self.ask(tr("grimoire.spells.phonel.page", "Pair"),
                    tr("grimoire.spells.phonel.page",
                       "Pair with {name}?\n\nThe device asks you to accept. Both then show the same key: check "
                       "they match. A paired device can send you files and, as its plugins allow, read this PC's "
                       "clipboard and run commands here.").format(name=isolate(d["name"])),
                    tr("grimoire.spells.phonel.page", "Pair")):
            self.act(lambda: kdc.pair(d["id"]),
                     tr("grimoire.spells.phonel.page", "Asked {name} to pair: accept on the device").format(
                         name=isolate(d["name"])), then=self.refresh)

    def accept(self, d: dict):
        if self.ask(tr("grimoire.spells.phonel.page", "Accept pairing"),
                    tr("grimoire.spells.phonel.page",
                       "Pair with {name}?\n\nOnly accept if you asked for it from that device and it shows the "
                       "key {key}.").format(name=isolate(d["name"]), key=i18n.ltr(d["key"] or "…")),
                    tr("grimoire.spells.phonel.page", "Accept")):
            self.act(lambda: kdc.accept(d["id"]),
                     tr("grimoire.spells.phonel.page", "Paired with {name}").format(name=isolate(d["name"])),
                     then=self._paired(d["id"]))

    def _paired(self, dev: str):
        def then():
            self.current = dev
            self.refresh()
        return then

    def unpair(self, d: dict):
        if self.ask(tr("grimoire.spells.phonel.page", "Unpair"),
                    tr("grimoire.spells.phonel.page",
                       "Unpair {name}?\n\nIt can't reach this PC any more (files, notifications, clipboard, "
                       "commands) until you pair the two again.").format(name=isolate(d["name"])),
                    tr("grimoire.spells.phonel.page", "Unpair")):
            self.act(lambda: kdc.unpair(d["id"]),
                     tr("grimoire.spells.phonel.page", "Unpaired {name}").format(name=isolate(d["name"])),
                     then=self.refresh)

    def sizeHint(self):
        return QSize(1000, 700)

