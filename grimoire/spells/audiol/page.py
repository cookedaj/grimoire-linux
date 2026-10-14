# SPDX-License-Identifier: GPL-3.0-or-later
"""AudioL page: sound on PipeWire. Outputs & inputs (default device, volume, mute, a level meter), per-app volume
and which device each app plays on, the system-wide equalizer, and sound card profiles (HDMI or analog…).

One pw-dump every 1.5 s on a worker thread, only while the page is on screen; nothing is read while it's hidden.
Writes go through pw.py (wpctl/pactl as you) and report back in the toast.
"""
import time

from PySide6 import QtGui
from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.audiol import eq, pw
from grimoire.spells.audiol.eqview import EqPanel
from grimoire.spells.audiol.meter import FLOOR, LevelBar, LevelReader
from grimoire.spells.systeml.page import _label
from grimoire.widgets import Slider

PANELS = [("devices", tr_noop("grimoire.spells.audiol.page", "Outputs & inputs"), "audio"),
          ("apps", tr_noop("grimoire.spells.audiol.page", "Apps"), "grid"),
          ("eq", tr_noop("grimoire.spells.audiol.page", "Equalizer"), "sliders"),
          ("profiles", tr_noop("grimoire.spells.audiol.page", "Profiles"), "card")]
# PipeWire's node states, as shown (anything else is shown as PipeWire says it)
STATES = {"running": tr_noop("grimoire.spells.audiol.page", "Running"),
          "idle": tr_noop("grimoire.spells.audiol.page", "Idle"),
          "suspended": tr_noop("grimoire.spells.audiol.page", "Suspended"),
          "error": tr_noop("grimoire.spells.audiol.page", "Error"),
          "creating": tr_noop("grimoire.spells.audiol.page", "Starting")}
# device.form-factor values a card may carry
FORMS = {"internal": tr_noop("grimoire.spells.audiol.page", "Internal"),
         "speaker": tr_noop("grimoire.spells.audiol.page", "Speaker"),
         "handset": tr_noop("grimoire.spells.audiol.page", "Handset"),
         "tv": tr_noop("grimoire.spells.audiol.page", "TV"),
         "webcam": tr_noop("grimoire.spells.audiol.page", "Webcam"),
         "microphone": tr_noop("grimoire.spells.audiol.page", "Microphone"),
         "headset": tr_noop("grimoire.spells.audiol.page", "Headset"),
         "headphone": tr_noop("grimoire.spells.audiol.page", "Headphones"),
         "hands-free": tr_noop("grimoire.spells.audiol.page", "Hands-free"),
         "car": tr_noop("grimoire.spells.audiol.page", "Car"),
         "hifi": tr_noop("grimoire.spells.audiol.page", "Hi-fi"),
         "computer": tr_noop("grimoire.spells.audiol.page", "Computer"),
         "portable": tr_noop("grimoire.spells.audiol.page", "Portable")}
POLL_MS = 1500
HOLD = 2.0                    # seconds a control you just moved isn't overwritten by a reading


def _state(state: str) -> str:
    """A PipeWire node state as shown."""
    if state in STATES:
        return tr("grimoire.spells.audiol.page", STATES[state])
    return state.capitalize()


class _Signals(QObject):
    sampled = Signal(object)
    acted = Signal(object)        # (what, message, ok, then, quiet)


def _mute_button() -> QToolButton:
    b = QToolButton()
    b.setObjectName("Tool")
    b.setCheckable(True)
    b.setIconSize(QSize(18, 18))
    b.setIcon(glyph("audio", 18))
    b.toggled.connect(lambda on: (b.setIcon(glyph("muted" if on else "audio", 18)),
                                  b.setToolTip(tr("grimoire.spells.audiol.page", "Unmute") if on else
                                               tr("grimoire.spells.audiol.page", "Mute"))))
    b.setToolTip(tr("grimoire.spells.audiol.page", "Mute"))
    return b


class VolumeRow(QFrame):
    """One device or app: title, a line under it, volume slider, mute, and room for extras on the right."""

    def __init__(self, page, title: str, icon=None):
        super().__init__()
        self.page = page
        self.item: dict = {}
        self.touched = 0.0
        self.setObjectName("Row")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)
        if icon is not None:
            ic = QLabel()
            ic.setPixmap(icon.pixmap(24, 24))
            ic.setFixedWidth(28)
            lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = _label(pw.lead(title), "RowTitle")
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        head.addWidget(self.title, 1)
        self.extra = QHBoxLayout()
        self.extra.setSpacing(8)
        head.addLayout(self.extra)
        text.addLayout(head)
        self.sub = _label("", "Muted")
        self.sub.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        for lab in (self.title, self.sub):          # app, device and track names are set by the apps themselves
            lab.setTextFormat(Qt.TextFormat.PlainText)
        text.addWidget(self.sub)
        vol = QHBoxLayout()
        vol.setSpacing(8)
        self.mute = _mute_button()
        self.mute.clicked.connect(self._muted)
        vol.addWidget(self.mute)
        self.vol = Slider(0, 100, "%")
        self.vol.s.valueChanged.connect(self._moved)
        vol.addWidget(self.vol, 1)
        text.addLayout(vol)
        self.level = LevelBar()
        self.level.hide()
        text.addWidget(self.level)
        lay.addLayout(text, 1)
        self._send = QTimer(self, singleShot=True, interval=80, timeout=self._send_volume)

    def show_item(self, item: dict):
        self.item = item
        if time.monotonic() - self.touched < HOLD or self.vol.s.isSliderDown():
            return
        self.vol.s.blockSignals(True)
        self.vol.s.setMaximum(max(100, min(pw.MAX_VOLUME, item["volume"])))
        self.vol.setValue(item["volume"])
        self.vol.s.blockSignals(False)
        self.mute.blockSignals(True)
        self.mute.setChecked(item["mute"])
        self.mute.setIcon(glyph("muted" if item["mute"] else "audio", 18))
        self.mute.blockSignals(False)

    def _moved(self, _v):
        self.touched = time.monotonic()
        self._send.start()

    def _send_volume(self):
        node, pct = self.item.get("id"), self.vol.value()
        if node is not None:
            self.page.act(self.title.text(), lambda: pw.set_volume(node, pct), quiet=True)

    def _muted(self, on: bool):
        self.touched = time.monotonic()
        node = self.item.get("id")
        if node is not None:
            self.page.act(self.title.text(), lambda: pw.set_mute(node, on), quiet=True)


class _List(QScrollArea):
    """A scrolling column of sections; rows are rebuilt only when the set of things in them changes."""

    def __init__(self, intro: str = ""):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        self.col = QVBoxLayout(inner)
        self.col.setContentsMargins(0, 0, 12, 20)
        self.col.setSpacing(10)
        if intro:
            self.col.addWidget(_label(intro, "Muted", wrap=True))
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        self.col.addLayout(self.body)
        self.col.addStretch(1)
        self.setWidget(inner)
        self.keys = None
        self.rows: dict = {}

    def rebuild(self, keys, build):
        """build() fills self.body and self.rows; called only when keys changed."""
        if keys == self.keys:
            return False
        self.keys = keys
        while self.body.count():
            w = self.body.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.rows = {}
        build()
        return True

    def section(self, text: str):
        lab = _label(text, "NavSection")
        self.body.addWidget(lab)

    def empty(self, text: str):
        self.body.addWidget(_label(text, "Muted", wrap=True))


# ---------------------------------------------------------------- outputs & inputs
class DevicesPanel(_List):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.reader = LevelReader(self)
        self.mic = LevelReader(self)
        self.out_row: VolumeRow | None = None
        self.in_row: VolumeRow | None = None
        self.reader.level.connect(lambda db: self.out_row and self.out_row.level.set_level(db))
        self.mic.level.connect(lambda db: self.in_row and self.in_row.level.set_level(db))

    def set_snap(self, snap: dict):
        keys = tuple((k, d["id"], d["label"]) for k in ("outputs", "inputs") for d in snap[k])

        def build():
            for kind, title in (("outputs", tr("grimoire.spells.audiol.page", "OUTPUTS")),
                                ("inputs", tr("grimoire.spells.audiol.page", "INPUTS"))):
                self.section(title)
                if not snap[kind]:
                    self.empty(tr("grimoire.spells.audiol.page", "No outputs found.") if kind == "outputs" else
                               tr("grimoire.spells.audiol.page", "No microphones or other inputs found."))
                for d in snap[kind]:
                    row = VolumeRow(self.page, d["label"])
                    use = QPushButton(tr("grimoire.spells.audiol.page", "Make default"))
                    use.clicked.connect(lambda _=False, r=row: self._make_default(r))
                    row.extra.addWidget(use)
                    row.use = use
                    if kind == "inputs":
                        test = QPushButton(tr("grimoire.spells.audiol.page", "Test level"))
                        test.setCheckable(True)
                        test.setToolTip(tr("grimoire.spells.audiol.page",
                                           "Shows how loud this input is. Plasma shows the microphone as in "
                                           "use while it's on"))
                        test.toggled.connect(lambda on, r=row: self._test(r, on))
                        row.extra.addWidget(test)
                        row.test = test
                    self.body.addWidget(row)
                    self.rows[(kind, d["id"])] = row
        if keys != self.keys:
            self._stop_mic()                       # its row is about to go
        self.out_row = None
        self.rebuild(keys, build)
        for kind in ("outputs", "inputs"):
            for d in snap[kind]:
                row = self.rows.get((kind, d["id"]))
                if not row:
                    continue
                row.show_item(d)
                bits = [tr("grimoire.spells.audiol.page", "Default")] if d["default"] else []
                if d["eq"]:
                    bits.append(tr("grimoire.spells.audiol.page", "AudioL's equalizer"))
                elif d["virtual"]:
                    bits.append(tr("grimoire.spells.audiol.page", "Virtual"))
                bits.append(tr("grimoire.spells.audiol.page", "Muted") if d["mute"] else
                            tr("grimoire.spells.audiol.page", "{n}%").format(n=d["volume"]))
                bits.append(_state(d["state"]))
                row.sub.setText(pw.lead(" · ".join(b for b in bits if b)))
                row.use.setVisible(not d["default"])
                if kind == "outputs" and d["default"]:
                    self.out_row = row
        self._meters()

    def _make_default(self, row: VolumeRow):
        node = row.item.get("id")
        if node is not None:
            done = tr("grimoire.spells.audiol.page", "now the default")
            self.page.act(row.title.text(), lambda: pw.set_default(node) and done, then=self.page.refresh)

    def _test(self, row: VolumeRow, on: bool):
        if on:
            for other in self.rows.values():
                if other is not row and getattr(other, "test", None) and other.test.isChecked():
                    other.test.setChecked(False)
            self.in_row = row
            row.level.show()
            self.mic.start(str(row.item["serial"]), output=False)      # by serial: a name could read as one
        elif self.in_row is row:
            self._stop_mic()

    def _stop_mic(self):
        if self.in_row is not None:
            self.in_row.level.hide()
            if getattr(self.in_row, "test", None):
                self.in_row.test.blockSignals(True)
                self.in_row.test.setChecked(False)
                self.in_row.test.blockSignals(False)
            self.in_row = None
        self.mic.stop()

    def _meters(self):
        """The default output's meter runs while this panel is on screen."""
        for row in self.rows.values():
            if row is not self.in_row and row is not self.out_row:
                row.level.hide()
        if not self.isVisible() or self.out_row is None:
            self.reader.stop()
            return
        self.out_row.level.show()
        self.reader.start(str(self.out_row.item["serial"]), output=True)

    def hideEvent(self, e):
        self.reader.stop()
        self._stop_mic()
        if self.out_row:
            self.out_row.level.set_level(FLOOR)
        super().hideEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        self._meters()


# ---------------------------------------------------------------- apps
class AppsPanel(_List):
    def __init__(self, page):
        super().__init__(tr("grimoire.spells.audiol.page",
                            "Each app's own volume, on top of its device's. Pick a device to move an app "
                            "there; PipeWire remembers it for that app next time."))
        self.page = page

    def set_snap(self, snap: dict):
        keys = tuple((k, s["id"]) for k in ("playing", "recording") for s in snap[k]) + \
            tuple((d["id"], d["label"]) for d in snap["outputs"] + snap["inputs"])

        def build():
            from grimoire.spells.netl.page import app_icon
            for kind, title, devs in (("playing", tr("grimoire.spells.audiol.page", "PLAYING"), snap["outputs"]),
                                      ("recording", tr("grimoire.spells.audiol.page", "RECORDING"), snap["inputs"])):
                self.section(title)
                if not snap[kind]:
                    self.empty(tr("grimoire.spells.audiol.page",
                                  "Nothing is playing right now.") if kind == "playing" else
                               tr("grimoire.spells.audiol.page", "Nothing is recording right now."))
                for s in snap[kind]:
                    icon = app_icon(s["icon"] or s["binary"] or s["app"]) or app_icon(s["app"]) or \
                        glyph("mic" if kind == "recording" else "audio", 24)
                    row = VolumeRow(self.page, s["app"], icon)
                    pick = QComboBox()
                    pick.setMinimumWidth(200)
                    pick.setMaximumWidth(320)
                    for d in devs:
                        pick.addItem(d["label"], d["id"])
                    pick.activated.connect(lambda _i, r=row, p=pick, k=kind: self._move(r, p, k))
                    row.extra.addWidget(pick)
                    row.pick = pick
                    self.body.addWidget(row)
                    self.rows[(kind, s["id"])] = row
        self.rebuild(keys, build)
        devs = {d["id"]: d for d in snap["outputs"] + snap["inputs"]}
        for kind in ("playing", "recording"):
            for s in snap[kind]:
                row = self.rows.get((kind, s["id"]))
                if not row:
                    continue
                row.show_item(s)
                if s["state"] == "running":
                    state = (tr("grimoire.spells.audiol.page", "Playing") if kind == "playing" else
                             tr("grimoire.spells.audiol.page", "Recording"))
                elif s["state"] in ("idle", "suspended"):
                    state = tr("grimoire.spells.audiol.page", "Paused")
                else:
                    state = _state(s["state"])
                bits = [s["media"] if s["media"] and s["media"] != s["app"] else "", state]
                row.sub.setText(pw.lead(" · ".join(b for b in bits if b)))
                if not row.pick.view().isVisible() and time.monotonic() - row.touched >= HOLD:
                    i = row.pick.findData(s["target"])
                    row.pick.setCurrentIndex(i)
                    row.pick.setToolTip(QtGui.Qt.convertFromPlainText(devs[s["target"]]["label"])
                                        if s["target"] in devs else "")

    def _move(self, row: VolumeRow, pick: QComboBox, kind: str):
        row.touched = time.monotonic()
        dev = self.page.snap and next((d for d in self.page.snap["outputs"] + self.page.snap["inputs"]
                                       if d["id"] == pick.currentData()), None)
        if not dev or not row.item:
            return
        stream = dict(row.item)
        done = tr("grimoire.spells.audiol.page", "moved to {device}").format(device=pw.isolate(dev["label"]))
        self.page.act(row.title.text(), lambda: pw.move_stream(stream, dev, playing=kind == "playing") and done,
                      then=self.page.refresh)


# ---------------------------------------------------------------- profiles
class ProfilesPanel(_List):
    def __init__(self, page):
        super().__init__(tr("grimoire.spells.audiol.page",
                            "A sound card's profile picks which of its connectors are in use: HDMI or the "
                            "analog jack, stereo or surround, with or without its microphone. Its \"Off\" "
                            "profile turns the card off."))
        self.page = page

    def set_snap(self, snap: dict):
        keys = tuple((c["id"], c["label"], tuple((p["index"], p["label"], p["available"]) for p in c["profiles"]))
                     for c in snap["cards"])

        def build():
            if not snap["cards"]:
                self.empty(tr("grimoire.spells.audiol.page", "No sound cards found."))
            for c in snap["cards"]:
                row = QFrame()
                row.setObjectName("Row")
                lay = QHBoxLayout(row)
                lay.setContentsMargins(16, 12, 16, 12)
                text = QVBoxLayout()
                text.setSpacing(4)
                title = _label(pw.lead(c["label"]), "RowTitle")
                title.setTextFormat(Qt.TextFormat.PlainText)
                title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                text.addWidget(title)
                row.sub = _label("", "Muted")
                row.sub.setTextFormat(Qt.TextFormat.PlainText)
                text.addWidget(row.sub)
                lay.addLayout(text, 1)
                pick = QComboBox()
                pick.setMinimumWidth(280)
                for p in sorted(c["profiles"], key=lambda p: (p["index"] != 0, not p["available"], -p["priority"])):
                    label = p["label"] if p["available"] else \
                        tr("grimoire.spells.audiol.page", "{profile} (not plugged in)").format(profile=p["label"])
                    pick.addItem(label, p["index"])
                pick.activated.connect(lambda _i, card=c, p=pick: self._pick(card, p))
                lay.addWidget(pick, 0, Qt.AlignmentFlag.AlignVCenter)
                row.pick = pick
                row.touched = 0.0
                self.body.addWidget(row)
                self.rows[c["id"]] = row
        self.rebuild(keys, build)
        for c in snap["cards"]:
            row = self.rows.get(c["id"])
            if not row:
                continue
            bits = [c["bus"].upper() if c["bus"] in ("usb", "pci") else c["bus"].capitalize(),
                    tr("grimoire.spells.audiol.page", FORMS[c["form"]]) if c["form"] in FORMS else
                    c["form"].capitalize(),
                    tr("grimoire.spells.audiol.page", "%n profile(s)", n=len(c["profiles"]))]
            row.sub.setText(pw.lead(" · ".join(b for b in bits if b)))
            if not row.pick.view().isVisible() and time.monotonic() - row.touched >= HOLD:
                row.pick.setCurrentIndex(row.pick.findData(c["profile"]))

    def _pick(self, card: dict, pick: QComboBox):
        row = self.rows.get(card["id"])
        if row:
            row.touched = time.monotonic()
        index, label = pick.currentData(), pick.currentText()
        self.page.act(card["label"], lambda: pw.set_profile(card["id"], index) and label, then=self.page.refresh)


# ---------------------------------------------------------------- the page
class AudioLPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.sig = _Signals()
        self.snap: dict | None = None
        self._busy = False
        self._fc: bool | None = None

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
        nl.addWidget(_label("AudioL", "Title"))
        nl.addSpacing(12)
        nl.addWidget(_label(tr("grimoire.spells.audiol.page", "SOUND"), "NavSection"))
        self.nav = {}
        for pid, name, icon in PANELS:
            b = QPushButton(glyph(icon, 18), "  " + tr("grimoire.spells.audiol.page", name).replace("&", "&&"))
            b.setObjectName("SubNavItem")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, p=pid: self.show_panel(p))
            nl.addWidget(b)
            self.nav[pid] = b
        nl.addStretch(1)
        self.foot = _label("", "Tiny")
        self.foot.setTextFormat(Qt.TextFormat.PlainText)     # the default output's name
        self.foot.setWordWrap(True)
        nl.addWidget(self.foot)
        root.addWidget(nav)

        right = QVBoxLayout()
        right.setContentsMargins(32, 26, 32, 18)
        right.setSpacing(14)
        self.heading = _label("", "PageHeading")
        right.addWidget(self.heading)
        self.stack = QStackedWidget()
        self.panels = {"devices": DevicesPanel(self), "apps": AppsPanel(self), "eq": EqPanel(self),
                       "profiles": ProfilesPanel(self)}
        for p in self.panels.values():
            self.stack.addWidget(p)
        self.missing = _label(tr("grimoire.spells.audiol.page",
                                 "AudioL works through PipeWire's own tools, pw-dump and wpctl, and they "
                                 "aren't installed. Install them with:\n\nsudo apt install pipewire-bin "
                                 "wireplumber"), "Muted", wrap=True)
        self.missing.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.missing.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.stack.addWidget(self.missing)
        right.addWidget(self.stack, 1)
        self.toast = _label("", "Toast", wrap=True)
        self.toast.setTextFormat(Qt.TextFormat.PlainText)    # carries device names and wpctl's messages
        self.toast.hide()
        right.addWidget(self.toast)
        self._toast_timer = QTimer(self, singleShot=True, interval=7000, timeout=self.toast.hide)
        root.addLayout(right, 1)

        self.sig.sampled.connect(self._sampled)
        self.sig.acted.connect(self._acted)
        self.timer = QTimer(self, interval=POLL_MS, timeout=self.refresh)
        self.show_panel("devices")

    # ------------------------------------------------------------ reading
    def showEvent(self, e):
        self.timer.start()
        self.refresh()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def refresh(self):
        if self._busy:
            return
        if not pw.available():
            self.stack.setCurrentWidget(self.missing)
            return
        if self.stack.currentWidget() is self.missing:
            self.show_panel("devices")
        self._busy = True
        fc = self._fc

        def work():
            try:
                snap = pw.snapshot()
                use_fc = eq.uses_filter_chain() if fc is None else fc
                return {"snap": snap, "fc": use_fc, "installed": eq.installed_output(eq.drop_in(use_fc))}
            except Exception as err:            # always answer, so _busy clears and the next tick tries again
                return {"error": str(err)}
        POOL.start(Job(work, self.sig.sampled.emit))

    def _sampled(self, r: dict):
        self._busy = False
        if "error" in r:
            self.foot.setText(tr("grimoire.spells.audiol.page",
                                 "PipeWire isn't answering: {error}").format(error=r["error"]))
            return
        self.snap, self._fc = r["snap"], r["fc"]
        snap = self.snap
        out = pw.default(snap)
        if out:
            vol = tr("grimoire.spells.audiol.page",
                     "Muted") if out["mute"] else tr("grimoire.spells.audiol.page", "{n}%").format(n=out["volume"])
            self.foot.setText(pw.lead("{device}\n{volume}".format(device=out["label"], volume=vol)))
        else:
            self.foot.setText(tr("grimoire.spells.audiol.page", "No output"))
        self.panels["devices"].set_snap(snap)
        self.panels["apps"].set_snap(snap)
        self.panels["eq"].update_snap(snap, r["fc"], r["installed"])
        self.panels["profiles"].set_snap(snap)

    # ------------------------------------------------------------ navigation
    def show_panel(self, pid: str):
        for p, b in self.nav.items():
            b.setChecked(p == pid)
        self.heading.setText(tr("grimoire.spells.audiol.page", next(n for p, n, _ in PANELS if p == pid)))
        self.stack.setCurrentWidget(self.panels[pid])

    # ------------------------------------------------------------ actions
    def act(self, what: str, fn, then=None, quiet=False):
        """Run fn on the pool; report how it went in the toast, then call then() (e.g. read again)."""
        def work():
            try:
                return (what, fn() or tr("grimoire.spells.audiol.page", "done"), True, then, quiet)
            except Exception as err:                 # shown to the user, not a crash
                return (what, str(err), False, then, quiet)
        POOL.start(Job(work, self.sig.acted.emit))

    def _acted(self, result):
        what, msg, ok, then, quiet = result
        if not ok or not quiet:
            what, msg = pw.isolate(what.lstrip("‏")), pw.isolate(msg)
            self.say(tr("grimoire.spells.audiol.page", "{what}: {message}").format(what=what, message=msg) if ok else
                     tr("grimoire.spells.audiol.page",
                        "Couldn't change {what}: {message}").format(what=what, message=msg))
        if then:
            then()

    def say(self, text: str):
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start()
