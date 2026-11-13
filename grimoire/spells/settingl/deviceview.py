# SPDX-License-Identifier: GPL-3.0-or-later
"""Device pages: Bluetooth, mouse & touchpad, keyboard and power. Each change applies when you make it (KWin,
PowerDevil and BlueZ take it at once); the keyboard's layout list waits for Apply, as it's edited in several steps."""

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from grimoire import i18n
from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop
from grimoire.spells.settingl import bluetooth, inputdev, power
from grimoire.spells.settingl.common import Panel, Row, combo, gray_icon, label, minutes
from grimoire.widgets import Slider, Switch, segments

CTX = "grimoire.spells.settingl.deviceview"


def _clear(lay):
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
        elif item.layout():
            _clear(item.layout())


# ---------------------------------------------------------------- Bluetooth
KIND_NAMES = {
    "audio-headset": tr_noop("grimoire.spells.settingl.deviceview", "Headset"),
    "audio-headphones": tr_noop("grimoire.spells.settingl.deviceview", "Headphones"),
    "audio-card": tr_noop("grimoire.spells.settingl.deviceview", "Speaker"),
    "input-mouse": tr_noop("grimoire.spells.settingl.deviceview", "Mouse"),
    "input-keyboard": tr_noop("grimoire.spells.settingl.deviceview", "Keyboard"),
    "input-gaming": tr_noop("grimoire.spells.settingl.deviceview", "Game controller"),
    "input-tablet": tr_noop("grimoire.spells.settingl.deviceview", "Drawing tablet"),
    "phone": tr_noop("grimoire.spells.settingl.deviceview", "Phone"),
    "computer": tr_noop("grimoire.spells.settingl.deviceview", "Computer"),
    "camera-video": tr_noop("grimoire.spells.settingl.deviceview", "Camera"),
    "printer": tr_noop("grimoire.spells.settingl.deviceview", "Printer"),
    "multimedia-player": tr_noop("grimoire.spells.settingl.deviceview", "Media player"),
}


class BluetoothPanel(Panel):
    POLL = 5000

    def __init__(self, host):
        super().__init__(host)
        self._quiet = False
        self.missing = self.note(
            tr(
                "grimoire.spells.settingl.deviceview",
                "No Bluetooth adapter was found, or BlueZ (the Bluetooth service) isn't running.",
            )
        )
        self.missing.hide()
        self.power_sw = Switch()
        self.power_sw.toggled.connect(self._power)
        self.power_row = Row(tr("grimoire.spells.settingl.deviceview", "Bluetooth"), "", self.power_sw)
        self.col.addWidget(self.power_row)
        head = QHBoxLayout()
        head.addWidget(label(tr("grimoire.spells.settingl.deviceview", "Your devices"), "SectionTitle"))
        head.addStretch(1)
        add = QPushButton(glyph("plus", 16), " " + tr("grimoire.spells.settingl.deviceview", "Add a device…"))
        add.setToolTip(
            tr(
                "grimoire.spells.settingl.deviceview",
                "Opens KDE's pairing wizard, which shows and confirms the pairing codes",
            )
        )
        add.clicked.connect(
            lambda: self.act(
                tr("grimoire.spells.settingl.deviceview", "Bluetooth"), lambda: bluetooth.add_device() or "", quiet=True
            )
        )
        head.addWidget(add)
        self.col.addSpacing(8)
        self.col.addLayout(head)
        self.list = QVBoxLayout()
        self.list.setSpacing(8)
        self.col.addLayout(self.list)
        self.keys = None
        self.kde_links(["kcm_bluetooth"])
        self.finish()

    def read(self):
        return bluetooth.state()

    def fill(self, s):
        self.missing.setVisible(not s["available"])
        self.power_row.setVisible(s["available"])
        a = s["adapters"][0] if s["adapters"] else None
        self._quiet = True
        if a:
            self.power_sw.setChecked(a["powered"])
            self.power_row.set_sub(
                tr("grimoire.spells.settingl.deviceview", "On · this PC shows up as {name}").format(
                    name=i18n.isolate(a["name"])
                )
                if a["powered"]
                else tr("grimoire.spells.settingl.deviceview", "Off")
            )
        self._quiet = False
        keys = tuple((d["path"], d["connected"], d["battery"]) for d in s["devices"]) + (bool(a and a["powered"]),)
        if keys == self.keys:
            return
        self.keys = keys
        _clear(self.list)
        if not s["devices"]:
            self.list.addWidget(label(tr("grimoire.spells.settingl.deviceview", "No paired devices yet."), "Muted"))
        for d in s["devices"]:
            btn = QPushButton(
                tr("grimoire.spells.settingl.deviceview", "Disconnect")
                if d["connected"]
                else tr("grimoire.spells.settingl.deviceview", "Connect")
            )
            btn.setEnabled(bool(a and a["powered"]))
            btn.clicked.connect(lambda _=False, d=d: self._connect(d))
            bits = [
                tr("grimoire.spells.settingl.deviceview", KIND_NAMES[d["icon"]]) if d["icon"] in KIND_NAMES else "",
                tr("grimoire.spells.settingl.deviceview", "Connected")
                if d["connected"]
                else tr("grimoire.spells.settingl.deviceview", "Not connected"),
            ]
            if d["battery"] is not None:
                bits.append(tr("grimoire.spells.settingl.deviceview", "Battery {n}%").format(n=d["battery"]))
            row = Row(d["name"], " · ".join(b for b in bits if b), btn, gray_icon(d["icon"]) or glyph("bluetooth", 24))
            row.title.setTextFormat(Qt.TextFormat.PlainText)
            self.list.addWidget(row)

    def _power(self, on: bool):
        if self._quiet or not self.data or not self.data["adapters"]:
            return
        path = self.data["adapters"][0]["path"]
        self.act(
            tr("grimoire.spells.settingl.deviceview", "Bluetooth"),
            lambda: bluetooth.set_power(path, on) or "",
            quiet=True,
        )

    def _connect(self, d: dict):
        on = not d["connected"]
        name = i18n.isolate(d["name"])
        if on:
            self.host.say(tr("grimoire.spells.settingl.deviceview", "Connecting to {device}…").format(device=name))
        else:
            self.host.say(tr("grimoire.spells.settingl.deviceview", "Disconnecting {device}…").format(device=name))
        done = (
            tr("grimoire.spells.settingl.deviceview", "connected")
            if on
            else tr("grimoire.spells.settingl.deviceview", "disconnected")
        )
        self.act(d["name"], lambda: bluetooth.connect(d["path"], on) or done)


# ---------------------------------------------------------------- mouse & touchpad
SCROLL = [0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0]
SWITCHES = [
    (
        "naturalScroll",
        tr_noop("grimoire.spells.settingl.deviceview", "Natural scrolling"),
        tr_noop("grimoire.spells.settingl.deviceview", "Content moves the way your fingers move, like on a phone."),
    ),
    (
        "leftHanded",
        tr_noop("grimoire.spells.settingl.deviceview", "Left-handed"),
        tr_noop("grimoire.spells.settingl.deviceview", "Swaps the left and right buttons."),
    ),
    ("middleEmulation", tr_noop("grimoire.spells.settingl.deviceview", "Middle-click by pressing both buttons"), ""),
    (
        "tapToClick",
        tr_noop("grimoire.spells.settingl.deviceview", "Tap to click"),
        tr_noop("grimoire.spells.settingl.deviceview", "A light tap counts as a click."),
    ),
    (
        "disableWhileTyping",
        tr_noop("grimoire.spells.settingl.deviceview", "Ignore while typing"),
        tr_noop("grimoire.spells.settingl.deviceview", "Stops the palm from moving the pointer while you type."),
    ),
    ("scrollTwoFinger", tr_noop("grimoire.spells.settingl.deviceview", "Scroll with two fingers"), ""),
    ("scrollEdge", tr_noop("grimoire.spells.settingl.deviceview", "Scroll along the edge"), ""),
]


class PointerPanel(Panel):
    def __init__(self, host):
        super().__init__(host)
        self.devs: list[dict] = []
        self._quiet = False
        self.missing = self.note(
            tr("grimoire.spells.settingl.deviceview", "No mouse or touchpad was found, or KWin didn't answer.")
        )
        self.missing.hide()
        self.pick = combo(280)
        self.pick.activated.connect(lambda _i: self._show())
        self.pick_row = Row(tr("grimoire.spells.settingl.deviceview", "Device"), "", self.pick)
        self.col.addWidget(self.pick_row)
        self.speed = Slider(-100, 100)
        self.speed.setMinimumWidth(260)
        self.speed.s.valueChanged.connect(lambda _v: self._later("pointerAcceleration"))
        self.speed_row = Row(
            tr("grimoire.spells.settingl.deviceview", "Pointer speed"),
            tr("grimoire.spells.settingl.deviceview", "0 is the device's normal speed."),
            self.speed,
        )
        self.col.addWidget(self.speed_row)
        prof = QWidget()
        pl = QHBoxLayout(prof)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        self.prof_btns = []
        for pid, text in (
            ("flat", tr("grimoire.spells.settingl.deviceview", "Flat")),
            ("adaptive", tr("grimoire.spells.settingl.deviceview", "Adaptive")),
        ):
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.prof = pid
            b.clicked.connect(lambda _=False, p=pid: self._profile(p))
            pl.addWidget(b)
            self.prof_btns.append(b)
        segments(self.prof_btns)
        self.prof_row = Row(
            tr("grimoire.spells.settingl.deviceview", "Acceleration"),
            tr(
                "grimoire.spells.settingl.deviceview",
                "Flat moves the pointer exactly as far as the mouse (best for games); adaptive "
                "goes further when you move fast.",
            ),
            prof,
        )
        self.col.addWidget(self.prof_row)
        self.scroll = Slider(0, len(SCROLL) - 1)
        self.scroll.setMinimumWidth(260)
        self.scroll.s.valueChanged.connect(lambda v: self.scroll.v.setText(f"{SCROLL[v]:g}×"))
        self.scroll.s.valueChanged.connect(lambda _v: self._later("scrollFactor"))
        self.col.addWidget(Row(tr("grimoire.spells.settingl.deviceview", "Scrolling speed"), "", self.scroll))
        self.sw: dict[str, tuple[Switch, Row]] = {}
        for prop, title, sub in SWITCHES:
            s = Switch()
            s.toggled.connect(lambda on, p=prop: self._set(p, on))
            row = Row(
                tr("grimoire.spells.settingl.deviceview", title),
                tr("grimoire.spells.settingl.deviceview", sub) if sub else "",
                s,
            )
            self.sw[prop] = (s, row)
            self.col.addWidget(row)
        self._pending: set[str] = set()
        self._timer = QTimer(self, singleShot=True, interval=250, timeout=self._send)
        self.kde_links(
            ["kcm_mouse", "kcm_touchpad", "kcm_cursortheme", "kcm_gamecontroller", "kcm_tablet", "kcm_access"]
        )
        self.finish()

    def read(self):
        return inputdev.pointers()

    def fill(self, devs):
        self.devs = devs
        self.missing.setVisible(not devs)
        cur = self.pick.currentData()
        self._quiet = True
        self.pick.clear()
        for i, d in enumerate(devs):
            kind = (
                tr("grimoire.spells.settingl.deviceview", "Touchpad")
                if d["touchpad"]
                else tr("grimoire.spells.settingl.deviceview", "Mouse")
            )
            self.pick.addItem(f"{d['name']} · {kind}", i)
        if cur is not None and cur < len(devs):
            self.pick.setCurrentIndex(cur)
        self.pick.setEnabled(len(devs) > 1)
        self.pick_row.setVisible(bool(devs))
        self._quiet = False
        self._show()

    def _dev(self) -> dict | None:
        i = self.pick.currentData()
        return self.devs[i] if i is not None and i < len(self.devs) else None

    def _show(self):
        d = self._dev()
        widgets = [self.speed_row, self.prof_row, self.scroll.parentWidget()] + [r for _, r in self.sw.values()]
        for w in widgets:
            w.setVisible(d is not None)
        if d is None:
            return
        self._quiet = True
        p = d["props"]
        self.pick_row.set_sub(tr("grimoire.spells.settingl.deviceview", "Touchpad") if d["touchpad"] else "")
        self.speed_row.setVisible(inputdev.supports(d, "pointerAcceleration"))
        self.speed.setValue(round(float(p.get("pointerAcceleration", 0)) * 100))
        self.prof_row.setVisible(inputdev.supports(d, "profile"))
        flat = bool(p.get("pointerAccelerationProfileFlat"))
        for b in self.prof_btns:
            b.setChecked((b.prof == "flat") == flat)
        f = float(p.get("scrollFactor", 1.0))
        idx = min(range(len(SCROLL)), key=lambda i: abs(SCROLL[i] - f))
        self.scroll.setValue(idx)
        self.scroll.v.setText(f"{SCROLL[idx]:g}×")
        for prop, (s, row) in self.sw.items():
            row.setVisible(inputdev.supports(d, prop))
            s.setChecked(bool(p.get(prop)))
        self._quiet = False

    def _later(self, prop: str):
        if not self._quiet:
            self._pending.add(prop)
            self._timer.start()

    def _send(self):
        d = self._dev()
        if d is None:
            return
        for prop in self._pending:
            value = self.speed.value() / 100 if prop == "pointerAcceleration" else SCROLL[self.scroll.value()]
            d["props"][prop] = value
            self.host.act(d["name"], lambda p=prop, v=value: inputdev.set_prop(d, p, v) or "", quiet=True)
        self._pending.clear()

    def _profile(self, pid: str):
        d = self._dev()
        for b in self.prof_btns:
            b.setChecked(b.prof == pid)
        if d and not self._quiet:
            d["props"]["pointerAccelerationProfileFlat"] = pid == "flat"
            self.host.act(d["name"], lambda: inputdev.set_prop(d, "profile", pid) or "", quiet=True)

    def _set(self, prop: str, on: bool):
        d = self._dev()
        if d and not self._quiet:
            d["props"][prop] = on
            self.host.act(d["name"], lambda: inputdev.set_prop(d, prop, on) or "", quiet=True)


# ---------------------------------------------------------------- keyboard
class LayoutPicker(QDialog):
    """Search xkb's layouts and variants by name."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("grimoire.spells.settingl.deviceview", "Add a keyboard layout"))
        self.resize(460, 520)
        lay = QVBoxLayout(self)
        self.find = QLineEdit()
        self.find.setPlaceholderText(
            tr("grimoire.spells.settingl.deviceview", "Search layouts (e.g. French, Dvorak, Arabic)")
        )
        self.find.setClearButtonEnabled(True)
        lay.addWidget(self.find)
        self.list = QListWidget()
        self.list.setObjectName("Plain")
        lay.addWidget(self.list, 1)
        for c in inputdev.catalog():
            it = QListWidgetItem(c["label"])
            it.setData(Qt.ItemDataRole.UserRole, (c["layout"], c["variant"]))
            self.list.addItem(it)
        self.find.textChanged.connect(self._filter)
        self.find.returnPressed.connect(self._first)
        self.list.itemDoubleClicked.connect(lambda _it: self.accept())
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        self.list.setCurrentRow(0)

    def _filter(self, text: str):
        words = text.casefold().split()
        first = None
        for i in range(self.list.count()):
            it = self.list.item(i)
            hit = all(w in it.text().casefold() for w in words)
            it.setHidden(not hit)
            if hit and first is None:
                first = it
        if first:
            self.list.setCurrentItem(first)

    def _first(self):
        if self.list.currentItem() and not self.list.currentItem().isHidden():
            self.accept()

    def choice(self):
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it and not it.isHidden() else None


class KeyboardPanel(Panel):
    def __init__(self, host):
        super().__init__(host)
        self.layouts: list[tuple[str, str]] = []
        self.saved: list[tuple[str, str]] = []
        self._quiet = False
        self.section(tr("grimoire.spells.settingl.deviceview", "Layouts"))
        self.note(
            tr(
                "grimoire.spells.settingl.deviceview",
                "The first one is used when you log in. Switch between them with Meta+Alt+K or the "
                "keyboard icon in the panel.",
            )
        )
        box = QHBoxLayout()
        self.list = QListWidget()
        self.list.setObjectName("Plain")
        self.list.setMinimumHeight(140)
        self.list.setMaximumHeight(200)
        box.addWidget(self.list, 1)
        tools = QVBoxLayout()
        for icon, tip, fn in (
            ("plus", tr("grimoire.spells.settingl.deviceview", "Add a layout"), self._add),
            ("close", tr("grimoire.spells.settingl.deviceview", "Remove"), self._remove),
            ("up", tr("grimoire.spells.settingl.deviceview", "Move up"), lambda: self._move(-1)),
            ("down", tr("grimoire.spells.settingl.deviceview", "Move down"), lambda: self._move(1)),
        ):
            b = QToolButton()
            b.setObjectName("Tool")
            b.setIcon(glyph(icon, 18))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.clicked.connect(fn)
            tools.addWidget(b)
        tools.addStretch(1)
        box.addLayout(tools)
        self.col.addLayout(box)
        self.pending = QFrame()
        self.pending.setObjectName("Pending")
        pl = QHBoxLayout(self.pending)
        pl.setContentsMargins(18, 10, 12, 10)
        pl.addWidget(label(tr("grimoire.spells.settingl.deviceview", "You changed the layouts."), "PendingText"), 1)
        undo = QPushButton(tr("grimoire.spells.settingl.deviceview", "Reset"))
        undo.clicked.connect(lambda: self._set_list(list(self.saved)))
        apply = QPushButton(tr("grimoire.spells.settingl.deviceview", "Apply"))
        apply.setObjectName("Primary")
        apply.clicked.connect(self._apply)
        pl.addWidget(undo)
        pl.addWidget(apply)
        self.pending.hide()
        self.col.addWidget(self.pending)

        self.section(tr("grimoire.spells.settingl.deviceview", "Key repeat"))
        self.rep_sw = Switch()
        self.rep_sw.toggled.connect(lambda on: self._repeat(repeat=on))
        self.col.addWidget(
            Row(tr("grimoire.spells.settingl.deviceview", "Repeat a key while it's held down"), "", self.rep_sw)
        )
        ms = tr("grimoire.spells.settingl.deviceview", " ms", "milliseconds, after a number")
        self.delay = Slider(100, 2000, ms)
        self.delay.v.setFixedWidth(max(70, self.delay.v.fontMetrics().horizontalAdvance("2000" + self.delay.suffix) + 8))
        self.delay.setMinimumWidth(260)
        self.delay.s.setSingleStep(25)
        self.delay.s.valueChanged.connect(lambda _v: self._later())
        self.col.addWidget(
            Row(
                tr("grimoire.spells.settingl.deviceview", "Delay"),
                tr("grimoire.spells.settingl.deviceview", "How long to hold a key before it repeats."),
                self.delay,
            )
        )
        self.rate = Slider(1, 100, tr("grimoire.spells.settingl.deviceview", "/s", "times a second, after a number"))
        self.rate.v.setFixedWidth(max(70, self.rate.v.fontMetrics().horizontalAdvance("100" + self.rate.suffix) + 8))
        self.rate.setMinimumWidth(260)
        self.rate.s.valueChanged.connect(lambda _v: self._later())
        self.col.addWidget(
            Row(
                tr("grimoire.spells.settingl.deviceview", "Rate"),
                tr("grimoire.spells.settingl.deviceview", "How many times a second it repeats."),
                self.rate,
            )
        )
        self.test = QLineEdit()
        self.test.setPlaceholderText(tr("grimoire.spells.settingl.deviceview", "Type here to try it"))
        self.col.addWidget(self.test)
        self._timer = QTimer(
            self,
            singleShot=True,
            interval=400,
            timeout=lambda: self._repeat(delay=self.delay.value(), rate=self.rate.value()),
        )
        self.kde_links(["kcm_keyboard", "kcm_keys", "kcm_virtualkeyboard", "kcm_plasmakeyboard", "kcm_access"])
        self.finish()

    def read(self):
        kb = inputdev.keyboard()
        kb["labels"] = {p: inputdev.label(*p) for p in kb["layouts"]}
        return kb

    def fill(self, kb):
        self._quiet = True
        self.saved = list(kb["layouts"])
        if not self.pending.isVisible():
            self._set_list(list(kb["layouts"]), kb["labels"])
        self.rep_sw.setChecked(kb["repeat"])
        self.delay.setValue(kb["delay"])
        self.rate.setValue(round(kb["rate"]))
        self.delay.setEnabled(kb["repeat"])
        self.rate.setEnabled(kb["repeat"])
        self._quiet = False

    def _set_list(self, pairs, labels=None):
        self.layouts = pairs
        row = self.list.currentRow()
        self.list.clear()
        for i, p in enumerate(pairs):
            name = (labels or {}).get(p) or inputdev.label(*p)
            text = (
                tr("grimoire.spells.settingl.deviceview", "{layout} (default)").format(layout=name) if i == 0 else name
            )
            self.list.addItem(text)
        self.list.setCurrentRow(min(max(row, 0), len(pairs) - 1))
        self.pending.setVisible(pairs != self.saved)

    def _add(self):
        d = LayoutPicker(self)
        if d.exec() and d.choice() and d.choice() not in self.layouts:
            self._set_list(self.layouts + [d.choice()])
            self.list.setCurrentRow(len(self.layouts) - 1)

    def _remove(self):
        i = self.list.currentRow()
        if 0 <= i < len(self.layouts) and len(self.layouts) > 1:
            self._set_list(self.layouts[:i] + self.layouts[i + 1 :])

    def _move(self, step: int):
        i = self.list.currentRow()
        j = i + step
        if 0 <= i < len(self.layouts) and 0 <= j < len(self.layouts):
            pairs = list(self.layouts)
            pairs[i], pairs[j] = pairs[j], pairs[i]
            self._set_list(pairs)
            self.list.setCurrentRow(j)

    def _apply(self):
        pairs = list(self.layouts)
        self.pending.hide()
        self.act(
            tr("grimoire.spells.settingl.deviceview", "Keyboard layouts"),
            lambda: inputdev.set_layouts(pairs) or tr("grimoire.spells.settingl.deviceview", "saved"),
        )

    def _later(self):
        if not self._quiet:
            self._timer.start()

    def _repeat(self, **kw):
        if self._quiet:
            return
        if "repeat" in kw:
            self.delay.setEnabled(kw["repeat"])
            self.rate.setEnabled(kw["repeat"])
        self.host.act(
            tr("grimoire.spells.settingl.deviceview", "Key repeat"), lambda: inputdev.set_repeat(**kw) or "", quiet=True
        )


# ---------------------------------------------------------------- power
PROFILE_NAMES = {
    "power-saver": tr_noop("grimoire.spells.settingl.deviceview", "Power saver"),
    "balanced": tr_noop("grimoire.spells.settingl.deviceview", "Balanced"),
    "performance": tr_noop("grimoire.spells.settingl.deviceview", "Performance"),
}
TIMEOUTS = [0, 60, 120, 300, 600, 900, 1200, 1800, 2700, 3600, 7200, 10800]
TIMER_ROWS = [
    ("dim", tr_noop("grimoire.spells.settingl.deviceview", "Dim the screen after")),
    ("off", tr_noop("grimoire.spells.settingl.deviceview", "Turn the screen off after")),
    ("sleep", tr_noop("grimoire.spells.settingl.deviceview", "Sleep after")),
]
SUPPLIES = [
    ("AC", tr_noop("grimoire.spells.settingl.deviceview", "Plugged in")),
    ("Battery", tr_noop("grimoire.spells.settingl.deviceview", "On battery")),
    ("LowBattery", tr_noop("grimoire.spells.settingl.deviceview", "On low battery")),
]


class PowerPanel(Panel):
    def __init__(self, host):
        super().__init__(host)
        self._quiet = False
        prof = QWidget()
        pl = QHBoxLayout(prof)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        self.prof_btns = []
        for pid in PROFILE_NAMES:
            b = QPushButton(tr("grimoire.spells.settingl.deviceview", PROFILE_NAMES[pid]))
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.prof = pid
            b.clicked.connect(lambda _=False, p=pid: self._profile(p))
            pl.addWidget(b)
            self.prof_btns.append(b)
        segments(self.prof_btns)
        self.prof_row = Row(tr("grimoire.spells.settingl.deviceview", "Power profile"), "", prof)
        self.col.addWidget(self.prof_row)
        self.batt_title = self.section(tr("grimoire.spells.settingl.deviceview", "Batteries"))
        self.batts = QVBoxLayout()
        self.batts.setSpacing(8)
        self.col.addLayout(self.batts)
        self.timer_title = self.section(tr("grimoire.spells.settingl.deviceview", "When the PC isn't used"))
        self.supply_rows: dict[str, list] = {}
        self.timer_box = QVBoxLayout()
        self.timer_box.setSpacing(8)
        self.col.addLayout(self.timer_box)
        self.note(
            tr(
                "grimoire.spells.settingl.deviceview",
                "These are Plasma's own power settings: KDE's Power Management module shows the same ones, and more.",
            )
        )
        self.kde_links(["kcm_powerdevilprofilesconfig", "kcm_screenlocker", "kcm_smserver"])
        self.finish()
        self._built = None

    def read(self):
        bat = power.batteries()
        supplies = ["AC"] + (["Battery", "LowBattery"] if any(b["system"] for b in bat) else [])
        return {"profiles": power.profiles(), "batteries": bat, "timers": {s: power.timers(s) for s in supplies}}

    def fill(self, d):
        self._quiet = True
        p = d["profiles"]
        self.prof_row.setVisible(p["ok"])
        for b in self.prof_btns:
            b.setVisible(b.prof in p["available"])
            b.setChecked(b.prof == p["active"])
        segments([b for b in self.prof_btns if b.prof in p["available"]])
        sub = (
            tr("grimoire.spells.settingl.deviceview", "Performance is held back right now: {reason}").format(
                reason=p["degraded"]
            )
            if p["degraded"]
            else tr("grimoire.spells.settingl.deviceview", "Trades speed for power use and heat. Changes at once.")
        )
        self.prof_row.set_sub(sub)
        _clear(self.batts)
        for b in d["batteries"]:
            name = tr("grimoire.spells.settingl.deviceview", "This PC") if b["system"] else (b["model"] or b["name"])
            state = {
                "Charging": tr("grimoire.spells.settingl.deviceview", "Charging"),
                "Discharging": tr("grimoire.spells.settingl.deviceview", "On battery"),
                "Full": tr("grimoire.spells.settingl.deviceview", "Full"),
                "Not charging": tr("grimoire.spells.settingl.deviceview", "Not charging"),
            }.get(b["status"], b["status"])
            pct = (
                tr("grimoire.spells.settingl.deviceview", "{n}%").format(n=b["percent"])
                if b["percent"] is not None
                else ""
            )
            row = Row(name, " · ".join(x for x in (pct, state) if x), None, glyph("boot", 24))
            row.title.setTextFormat(Qt.TextFormat.PlainText)
            self.batts.addWidget(row)
        self.batt_title.setVisible(bool(d["batteries"]))
        supplies = tuple(d["timers"])
        if self._built != supplies:
            self._built = supplies
            _clear(self.timer_box)
            self.supply_rows = {}
            for sid, title in SUPPLIES:
                if sid not in supplies:
                    continue
                if len(supplies) > 1:
                    self.timer_box.addWidget(
                        label(tr("grimoire.spells.settingl.deviceview", title).upper(), "NavSection")
                    )
                rows = {}
                for which, text in TIMER_ROWS:
                    c = combo(160)
                    c.activated.connect(lambda _i, s=sid, w=which, c=c: self._set_timer(s, w, c))
                    self.timer_box.addWidget(Row(tr("grimoire.spells.settingl.deviceview", text), "", c))
                    rows[which] = c
                self.supply_rows[sid] = rows
        for sid, rows in self.supply_rows.items():
            t = d["timers"][sid]
            for which, c in rows.items():
                c.clear()
                for s in sorted(set(TIMEOUTS) | {t[which]}):
                    c.addItem(minutes(s), s)
                c.setCurrentIndex(c.findData(t[which]))
        self._quiet = False

    def _profile(self, pid: str):
        for b in self.prof_btns:
            b.setChecked(b.prof == pid)
        self.act(
            tr("grimoire.spells.settingl.deviceview", "Power profile"),
            lambda: power.set_profile(pid) or tr("grimoire.spells.settingl.deviceview", PROFILE_NAMES[pid]),
        )

    def _set_timer(self, supply: str, which: str, c):
        if self._quiet:
            return
        secs = c.currentData()
        self.act(
            tr("grimoire.spells.settingl.deviceview", "Power"),
            lambda: power.set_timer(supply, which, secs) or "",
            quiet=True,
        )
