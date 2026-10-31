# SPDX-License-Identifier: GPL-3.0-or-later
"""NetL's Bluetooth panel: the adapter's power and visibility switches, your paired devices (battery, connect,
disconnect, remove) and nearby ones found by a scan, paired through a black & white code dialog.

Everything goes through BlueZ as you (bluez.py), like Plasma's Bluetooth applet. Scanning stops when the panel is
hidden and after SCAN_SECONDS. Device names come from whatever is nearby, so they're only shown as plain text.
"""
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from grimoire.glyphs import glyph
from grimoire.i18n import isolate, ltr, tr
from grimoire.jobs import POOL, Job
from grimoire.spells.netl import bluez
from grimoire.spells.systeml.alertview import _row
from grimoire.spells.systeml.bidi import lead
from grimoire.spells.systeml.graph import Bar
from grimoire.widgets import Switch

SCAN_SECONDS = 30
GLYPHS = (("audio", "audio"), ("input-keyboard", "keyboard"), ("input-gaming", "game"), ("computer", "desktop"),
          ("video-display", "desktop"))


class _Signals(QObject):
    changed = Signal()
    loaded = Signal(object)
    request = Signal(object)
    cancel = Signal()
    acted = Signal(object)


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    lab.setTextFormat(Qt.TextFormat.PlainText)      # device names come from whoever is nearby
    return lab


def device_glyph(icon: str) -> str:
    return next((g for prefix, g in GLYPHS if icon.startswith(prefix)), "bluetooth")


def device_name(d: dict) -> str:
    return d["name"] or d["address"]


def signal_text(rssi) -> str:
    if rssi is None:
        return ""
    if rssi >= -60:
        return tr("grimoire.spells.netl.btview", "strong signal")
    return tr("grimoire.spells.netl.btview", "good signal") if rssi >= -75 else \
        tr("grimoire.spells.netl.btview", "weak signal")


class CodeDialog(QDialog):
    """One pairing question: show a code, confirm one, or type a PIN/passkey. Black & white, big digits."""

    def __init__(self, parent, req: bluez.AgentRequest):
        super().__init__(parent)
        self.req = req
        self.setObjectName("Page")
        self.setWindowTitle(tr("grimoire.spells.netl.btview", "Pair with {device}").format(device=isolate(req.name)))
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 20)
        lay.setSpacing(14)
        lay.addWidget(lead(_label(req.name, "RowTitle")))
        kind, v = req.kind, req.value
        texts = {
            "RequestConfirmation": tr("grimoire.spells.netl.btview", "Check that {device} shows this number, then "
                                                                     "confirm on both."),
            "DisplayPasskey": tr("grimoire.spells.netl.btview", "Type this number on {device}, then press Enter "
                                                                "on it."),
            "DisplayPinCode": tr("grimoire.spells.netl.btview", "Type this PIN on {device}, then press Enter on it."),
            "RequestPasskey": tr("grimoire.spells.netl.btview", "Type the number {device} shows."),
            "RequestPinCode": tr("grimoire.spells.netl.btview", "Type the PIN for {device} (often 0000 or 1234, or the "
                                                                "one in its manual)."),
            "RequestAuthorization": tr("grimoire.spells.netl.btview", "{device} wants to pair with this PC. Allow it?"),
            "AuthorizeService": tr("grimoire.spells.netl.btview", "{device} wants to use a service on this PC "
                                                                  "({service}). Allow it?")}
        info = QLabel(texts.get(kind, kind).format(device=isolate(req.name), service=ltr(req.uuid)))
        info.setTextFormat(Qt.TextFormat.PlainText)
        info.setObjectName("Muted")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.edit = None
        if kind in ("RequestConfirmation", "DisplayPasskey", "DisplayPinCode"):
            code = f"{int(v):06d}" if kind != "DisplayPinCode" else str(v)
            num = QLabel(code)
            num.setTextFormat(Qt.TextFormat.PlainText)
            num.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            num.setStyleSheet('font-family: "IBM Plex Mono"; font-size: 40px; font-weight: 600; '
                              'letter-spacing: 8px; color: #ffffff; padding: 10px 0;')
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(num)
        elif kind in ("RequestPasskey", "RequestPinCode"):
            self.edit = QLineEdit()
            self.edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            self.edit.setStyleSheet('font-family: "IBM Plex Mono"; font-size: 24px; letter-spacing: 4px;')
            self.edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if kind == "RequestPasskey":
                self.edit.setValidator(QIntValidator(0, 999999, self.edit))
                self.edit.setMaxLength(6)
                self.edit.setPlaceholderText("000000")
            else:
                self.edit.setMaxLength(16)
                self.edit.setPlaceholderText("0000")
            lay.addWidget(self.edit)
        btns = QHBoxLayout()
        btns.addStretch(1)
        if kind.startswith("Display"):
            cancel = QPushButton(tr("grimoire.spells.netl.btview", "Cancel pairing"))
            cancel.clicked.connect(self.reject)
            btns.addWidget(cancel)
        else:
            asks = kind in ("RequestAuthorization", "AuthorizeService")
            confirm = kind == "RequestConfirmation"
            no = QPushButton(tr("grimoire.spells.netl.btview", "Don't allow") if asks
                             else tr("grimoire.spells.netl.btview", "Doesn't match") if confirm
                             else tr("grimoire.spells.netl.btview", "Cancel"))
            no.clicked.connect(self.reject)
            self.ok = QPushButton(tr("grimoire.spells.netl.btview", "Allow") if asks
                                  else tr("grimoire.spells.netl.btview", "It matches") if confirm
                                  else tr("grimoire.spells.netl.btview", "Pair"))
            self.ok.setObjectName("Primary")
            self.ok.setDefault(True)
            self.ok.clicked.connect(self.accept)
            btns.addWidget(no)
            btns.addWidget(self.ok)
            if self.edit is not None:
                self.edit.textChanged.connect(lambda t: self.ok.setEnabled(bool(t.strip())))
                self.ok.setEnabled(False)
        lay.addLayout(btns)

    def answer(self) -> str | None:
        return self.edit.text().strip() if self.edit is not None else None


class DeviceRow(QFrame):
    def __init__(self, panel, d: dict, paired: bool):
        super().__init__()
        self.setObjectName("Row")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 16, 12)
        lay.setSpacing(14)
        icon = QLabel()
        icon.setPixmap(glyph(device_glyph(d["icon"]), 22).pixmap(22, 22))
        lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
        text = QVBoxLayout()
        text.setSpacing(4)
        title = QHBoxLayout()
        title.setSpacing(8)
        title.addWidget(lead(_label(device_name(d), "RowTitle")))
        title.addStretch(1)
        text.addLayout(title)
        bits = []
        if paired:
            bits.append(tr("grimoire.spells.netl.btview", "Connected") if d["connected"]
                        else tr("grimoire.spells.netl.btview", "Not connected"))
            if d["battery"] is not None:
                bits.append(tr("grimoire.spells.netl.btview", "battery {percent}").format(
                    percent=ltr(f"{d['battery']}%")))
        else:
            bits.append(ltr(d["address"]))
            if d["rssi"] is not None:
                bits.append(signal_text(d["rssi"]))
        sub = _label(" · ".join(b for b in bits if b), "Muted")
        text.addWidget(lead(sub))
        if paired and d["battery"] is not None:
            bar = Bar(4)
            bar.set(d["battery"] / 100)
            bar.setMaximumWidth(160)
            line = QHBoxLayout()                      # a row, so the bar starts where reading starts
            line.addWidget(bar)
            line.addStretch(1)
            text.addLayout(line)
        lay.addLayout(text, 1)
        busy = d["path"] in panel.busy
        if paired:
            b = QPushButton(tr("grimoire.spells.netl.btview", "Disconnect") if d["connected"]
                            else tr("grimoire.spells.netl.btview", "Connect"))
            b.setEnabled(not busy and panel.powered)
            b.clicked.connect(lambda: panel.toggle_connection(d))
            rm = QPushButton(tr("grimoire.spells.netl.btview", "Remove"))
            rm.setToolTip(tr("grimoire.spells.netl.btview", "Forget this device (pair it again to use it)"))
            rm.setEnabled(not busy)
            rm.clicked.connect(lambda: panel.remove(d))
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(rm, 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            b = QPushButton(tr("grimoire.spells.netl.btview", "Pairing…") if busy
                            else tr("grimoire.spells.netl.btview", "Pair"))
            b.setObjectName("Primary")
            b.setEnabled(not busy and panel.powered)
            b.clicked.connect(lambda: panel.pair(d))
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)


class BluetoothPanel(QScrollArea):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.sig = _Signals()
        self.client: bluez.Client | None = None
        self.data: dict = {}
        self.busy: set[str] = set()
        self.powered = False
        self._quiet = False
        self._loading = False
        self._shape = None
        self._dialogs: dict[int, CodeDialog] = {}
        self._rejected: set[str] = set()       # devices whose pairing question you answered no
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 20)
        col.setSpacing(12)

        self.state = _label("", "Muted", wrap=True)
        self.state.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.state.hide()
        col.addWidget(self.state)
        self.body = QWidget()                     # everything below: hidden while there's no Bluetooth to show
        top, col = col, QVBoxLayout(self.body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)
        top.addWidget(self.body)
        self.power_sw, self.vis_sw = Switch(), Switch()
        self.power_sub = _label("", "Muted", wrap=True)
        self.vis_sub = _label("", "Muted", wrap=True)
        self.power_row = _row(tr("grimoire.spells.netl.page", "Bluetooth"), self.power_sub, self.power_sw)
        self.vis_row = _row(tr("grimoire.spells.netl.btview", "Visible to nearby devices"), self.vis_sub, self.vis_sw)
        col.addWidget(self.power_row)
        col.addWidget(self.vis_row)
        self.power_sw.toggled.connect(self._power)
        self.vis_sw.toggled.connect(self._visible)

        col.addWidget(_label(tr("grimoire.spells.netl.btview", "My devices"), "SectionTitle"))
        self.mine = QVBoxLayout()
        self.mine.setSpacing(8)
        col.addLayout(self.mine)

        head = QHBoxLayout()
        head.addWidget(_label(tr("grimoire.spells.netl.btview", "Nearby devices"), "SectionTitle"))
        head.addStretch(1)
        self.scan_btn = QPushButton(tr("grimoire.spells.netl.btview", "Scan"))
        self.scan_btn.setToolTip(tr("grimoire.spells.netl.btview", "Look for devices in pairing mode for {seconds} "
                                                                   "seconds").format(
            seconds=SCAN_SECONDS))
        self.scan_btn.clicked.connect(self._scan_clicked)
        head.addWidget(self.scan_btn)
        col.addLayout(head)
        self.near = QVBoxLayout()
        self.near.setSpacing(8)
        col.addLayout(self.near)
        top.addStretch(1)
        self.setWidget(inner)

        self.sig.changed.connect(lambda: self.isVisible() and self._debounce.start())   # shown: load() catches up
        self.sig.loaded.connect(self.loaded)
        self.sig.request.connect(self._ask)
        self.sig.cancel.connect(self._cancelled)
        self.sig.acted.connect(self._acted)
        self._debounce = QTimer(self, singleShot=True, interval=400, timeout=self.load)
        self._scan_timer = QTimer(self, singleShot=True, interval=SCAN_SECONDS * 1000,
                                  timeout=lambda: self.scan(False))
        self._sel_controls(False)

    # ------------------------------------------------------------ loading
    def _ensure_client(self):
        if self.client is None:
            sig = self.sig
            self.client = bluez.Client(on_change=sig.changed.emit, on_request=sig.request.emit,
                                       on_cancel=sig.cancel.emit)

    def load(self):
        if self._loading:
            self._debounce.start()
            return
        missing = bluez.missing()
        if missing:
            self._show_state(missing)
            self.body.hide()
            return
        self._ensure_client()
        self._loading = True
        client = self.client
        POOL.start(Job(lambda: client.start().snapshot(), self.sig.loaded.emit))

    def adapter(self) -> dict | None:
        ads = self.data.get("adapters") or []
        return next((a for a in ads if a["powered"]), ads[0] if ads else None)

    def _show_state(self, text: str):
        self.state.setText(text)
        self.state.setVisible(bool(text))

    def _sel_controls(self, on: bool):
        for w in (self.power_row, self.vis_row, self.scan_btn):
            w.setEnabled(on)

    def loaded(self, d: dict):
        self._loading = False
        self.data = d
        a = self.adapter()
        self.body.setVisible(bool(d["running"] and a))
        if not d["running"] and d.get("code") != "NoService" and d["error"]:
            self._show_state(d["error"])
        elif not d["running"]:
            self._show_state(tr("grimoire.spells.netl.btview", "The Bluetooth service isn't running. Start it with "
                                                               "{command}.")
                             .format(command=ltr("systemctl start bluetooth")))
        elif a is None:
            self._show_state(tr("grimoire.spells.netl.btview", "No Bluetooth adapter found. If this PC has one, it may "
                                                               "be switched off in the firmware settings or need a "
                                                               "driver."))
        elif a["blocked"]:
            self._show_state(tr("grimoire.spells.netl.btview", "Bluetooth is blocked by airplane mode or a hardware "
                                                               "switch. Turn airplane mode off in Wi-Fi & VPN."))
        elif not d["agent"]:
            self._show_state(tr("grimoire.spells.netl.btview", "Pairing isn't available right now (BlueZ didn't accept "
                                                               "NetL's pairing helper); devices you already paired "
                                                               "still work."))
        else:
            self._show_state("")
        self._sel_controls(bool(a) and not a["blocked"])
        self.powered = bool(a and a["powered"])
        self._quiet = True
        self.power_sw.setChecked(self.powered)
        self.vis_sw.setChecked(bool(a and a["discoverable"]))
        self._quiet = False
        self.vis_row.setEnabled(self.powered)
        self.scan_btn.setEnabled(self.powered)
        if a:
            self.power_sub.setText(tr("grimoire.spells.netl.btview", "{name} · {address}").format(
                                       name=isolate(a["name"]),
                                                                       address=ltr(a["address"]))
                                   if a["powered"] else tr("grimoire.spells.netl.btview", "Off"))
            self.vis_sub.setText(
                tr("grimoire.spells.netl.btview", "Others can find this PC as {name}. Turns itself off after %n "
                                                  "minute(s).",
                   n=max(1, a["timeout"] // 60)).format(name=isolate(a["name"])) if a["timeout"] else
                tr("grimoire.spells.netl.btview", "Others can find this PC as {name} while this is on.").format(
                    name=isolate(a["name"])))
        else:
            self.power_sub.setText("")
            self.vis_sub.setText("")
        scanning = bool(a and a["discovering"] and self._scan_timer.isActive())
        self.scan_btn.setText(tr("grimoire.spells.netl.btview", "Stop") if scanning
                              else tr("grimoire.spells.netl.btview", "Scan"))
        self._fill(d)

    def _fill(self, d: dict):
        a = self.adapter()
        devs = [x for x in d["devices"] if not a or x["adapter"] == a["path"]]
        mine = sorted((x for x in devs if x["paired"]), key=lambda x: (not x["connected"], device_name(x).lower()))
        near = sorted((x for x in devs if not x["paired"] and x["rssi"] is not None and (x["named"] or x["icon"])),
                      key=lambda x: -(x["rssi"] or -200))
        shape = (self.powered, tuple(sorted(self.busy)),
                 tuple((x["path"], x["name"], x["connected"], x["battery"], x["icon"]) for x in mine),
                 tuple((x["path"], x["name"], signal_text(x["rssi"]), x["icon"]) for x in near))
        if shape == self._shape:
            return
        self._shape = shape
        for box in (self.mine, self.near):
            while box.count():
                w = box.takeAt(0).widget()
                if w:
                    w.deleteLater()
        if not mine:
            empty = tr("grimoire.spells.netl.btview", "No paired devices yet. Put a device in pairing mode, press "
                                                      "Scan, then Pair.")
            self.mine.addWidget(_label(empty, "Muted", wrap=True))
        for x in mine:
            self.mine.addWidget(DeviceRow(self, x, True))
        if not near:
            scanning = self._scan_timer.isActive()
            self.near.addWidget(_label(tr("grimoire.spells.netl.btview", "Looking for devices in pairing mode…")
                                       if scanning else
                                       tr("grimoire.spells.netl.btview", "Press Scan to look for devices in pairing "
                                                                         "mode."), "Muted",
                                       wrap=True))
        for x in near:
            self.near.addWidget(DeviceRow(self, x, False))

    def showEvent(self, e):
        self.load()
        super().showEvent(e)

    def hideEvent(self, e):
        if self._scan_timer.isActive():
            self.scan(False)
        super().hideEvent(e)

    # ------------------------------------------------------------ actions
    def run(self, what: str, fn, key: str = "", verb: str = "change"):
        """fn on the pool; the result lands in the toast and the list reloads. verb picks the failure sentence."""
        if key:
            self.busy.add(key)
            self._shape = None
            self._fill(self.data)

        def work():
            try:
                return what, fn() or tr("grimoire.spells.netl.btview", "done"), True, key, verb
            except Exception as err:            # BluezError or a broken bus: shown, not a crash
                return what, str(err), False, key, verb
        POOL.start(Job(work, self.sig.acted.emit))

    def _acted(self, result):
        what, msg, ok, key, verb = result
        self.busy.discard(key)
        if not ok and key in self._rejected:          # you said no in the code dialog: that's not an error
            ok, msg = True, "cancelled"
        self._rejected.discard(key)
        for k, dlg in list(self._dialogs.items()):      # pairing over: a code still on screen has done its job
            if key and dlg.req.device == key:
                dlg.req.closed = True
                self._dialogs.pop(k, None)
                dlg.reject()
        self._shape = None
        if msg == "cancelled":
            msg = tr("grimoire.spells.netl.btview", "cancelled")
        fail = {"pair": tr("grimoire.spells.netl.btview", "Couldn't pair with {what}: {error}"),
                "connect": tr("grimoire.spells.netl.btview", "Couldn't connect to {what}: {error}")}.get(
                    verb, tr("grimoire.spells.netl.btview", "Couldn't change {what}: {error}"))
        self.page.say(tr("grimoire.spells.netl.btview", "{what}: {result}").format(what=isolate(what), result=msg)
                      if ok else
                      fail.format(what=isolate(what), error=msg))
        self.load()

    def _power(self, on: bool):
        a = self.adapter()
        if self._quiet or not a:
            return
        if not on:
            n = sum(1 for x in self.data.get("devices", []) if x["connected"])
            if n and QMessageBox.question(self, "Bluetooth", tr("grimoire.spells.netl.btview", "Turn Bluetooth off? %n "
                                                                                               "device(s) will "
                                                                                               "disconnect.", n=n)) \
                    != QMessageBox.StandardButton.Yes:
                self._quiet = True
                self.power_sw.setChecked(True)
                self._quiet = False
                return
        client = self.client
        self.run("Bluetooth", lambda: client.set_powered(a["path"], on) or (
            tr("grimoire.spells.netl.btview", "on") if on else tr("grimoire.spells.netl.btview", "off")))

    def _visible(self, on: bool):
        a = self.adapter()
        if self._quiet or not a:
            return
        client = self.client
        self.run(tr("grimoire.spells.netl.btview", "Visibility"), lambda: client.set_discoverable(a["path"], on) or (
            tr("grimoire.spells.netl.btview", "visible") if on else tr("grimoire.spells.netl.btview", "hidden")))

    def _scan_clicked(self):
        self.scan(not self._scan_timer.isActive())

    def scan(self, on: bool):
        a = self.adapter()
        if not a or self.client is None:
            return
        if on:
            self._scan_timer.start()
        else:
            self._scan_timer.stop()
        self.scan_btn.setText(tr("grimoire.spells.netl.btview", "Stop") if on
                              else tr("grimoire.spells.netl.btview", "Scan"))
        self._shape = None
        self._fill(self.data)
        client, sig = self.client, self.sig

        def work():
            try:
                client.scan(a["path"], on)
            except bluez.BluezError as err:
                return tr("grimoire.spells.netl.btview", "Scan"), str(err), False, "", "change"
            return None
        POOL.start(Job(work, lambda r: r and sig.acted.emit(r)))

    def toggle_connection(self, d: dict):
        client = self.client
        if d["connected"]:
            self.run(device_name(d), lambda: client.disconnect(d["path"]), d["path"])
        else:
            self.page.say(tr("grimoire.spells.netl.btview", "Connecting to {device}…").format(
                device=isolate(device_name(d))))
            self.run(device_name(d), lambda: client.connect(d["path"]), d["path"], "connect")

    def pair(self, d: dict):
        client = self.client
        if self._scan_timer.isActive():               # discovery slows pairing down; it's found what it needed
            self.scan(False)
        self.page.say(tr("grimoire.spells.netl.btview", "Pairing with {device}… follow what it asks.").format(
            device=isolate(device_name(d))))
        self.run(device_name(d), lambda: client.pair(d["path"]), d["path"], "pair")

    def remove(self, d: dict):
        a = self.adapter()
        if not a:
            return
        ask = tr("grimoire.spells.netl.btview", "Remove {device}? To use it again, put it in pairing mode and pair it "
                                                "from here.").format(device=isolate(device_name(d)))
        if QMessageBox.question(self, tr("grimoire.spells.netl.btview", "Remove device"), ask) \
                != QMessageBox.StandardButton.Yes:
            return
        client = self.client
        self.run(device_name(d), lambda: client.remove(a["path"], d["path"]), d["path"])

    # ------------------------------------------------------------ the pairing agent's questions
    def _ask(self, req: bluez.AgentRequest):
        if req.closed:
            return
        dlg = CodeDialog(self, req)
        self._dialogs[id(req)] = dlg

        def done(code):
            self._dialogs.pop(id(req), None)
            if req.kind.startswith("Display"):
                if code != QDialog.DialogCode.Accepted and not req.closed:
                    self._rejected.add(req.device)
                    client = self.client
                    POOL.start(Job(lambda: client.cancel_pairing(req.device), lambda _: None))
                return
            if code == QDialog.DialogCode.Accepted:
                answer = dlg.answer()
                try:
                    req.accept(answer)
                except (TypeError, ValueError):
                    req.reject()
            else:
                if not req.closed:
                    self._rejected.add(req.device)
                req.reject()
        dlg.finished.connect(done)
        dlg.open()

    def _cancelled(self):
        """BlueZ cancelled the pairing (timeout, the device gave up): close any open question."""
        for dlg in list(self._dialogs.values()):
            dlg.req.closed = True
            dlg.reject()
        self._dialogs.clear()

    def closeEvent(self, e):
        if self.client:
            self.client.stop()
        super().closeEvent(e)
