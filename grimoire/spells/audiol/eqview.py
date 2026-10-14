# SPDX-License-Identifier: GPL-3.0-or-later
"""AudioL's Equalizer panel: the response curve with a handle per band (drag up or down, scroll, double-click for
0 dB), presets, preamp, the device the EQ plays into, and the on/off switch with its explicit Apply button.

Turning the EQ on or off, or changing its device, only takes effect on Apply (it restarts PipeWire's filter-chain
service). Moving bands while it runs is live and needs no restart.
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QInputDialog, QMessageBox, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from grimoire.spells.audiol import eq, pw
from grimoire.spells.systeml.page import _label
from grimoire.widgets import Slider, Switch

LO, HI = 20.0, 20000.0
STEP = 0.5                                     # dB per scroll notch / drag snap


def _freq_text(f: float) -> str:
    return f"{f / 1000:g}k" if f >= 1000 else f"{f:g}"


class EqCurve(QWidget):
    """The curve and its ten handles. changed() fires while dragging; the panel throttles what it sends."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.gains = [0.0] * 10
        self.preamp = 0.0
        self.drag = -1
        self.hover = -1
        self.setMinimumHeight(260)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setToolTip("Drag a band up or down, scroll over it, or double-click it to set it back to 0 dB")

    def set_curve(self, gains, preamp):
        self.gains, self.preamp = list(gains), preamp
        self.update()

    # geometry
    def _plot(self) -> QRectF:
        return QRectF(44, 14, self.width() - 60, self.height() - 44)

    def _x(self, f: float) -> float:
        r = self._plot()
        return r.left() + r.width() * (math.log10(f) - math.log10(LO)) / (math.log10(HI) - math.log10(LO))

    def _y(self, db: float) -> float:
        r = self._plot()
        return r.top() + r.height() * (eq.LIMIT - db) / (2 * eq.LIMIT)

    def _db_at(self, y: float) -> float:
        r = self._plot()
        db = eq.LIMIT - (y - r.top()) / r.height() * 2 * eq.LIMIT
        return max(-eq.LIMIT, min(eq.LIMIT, round(db / STEP) * STEP))

    def _band_at(self, pos) -> int:
        best, dist = -1, 1e9
        for i, f in enumerate(eq.FREQS):
            d = abs(pos.x() - self._x(f))
            if d < dist:
                best, dist = i, d
        return best if dist < 26 else -1

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._plot()
        small = QFont(self.font())
        small.setPixelSize(10)
        p.setFont(small)
        for db in (-12, -6, 0, 6, 12):
            y = self._y(db)
            p.setPen(QPen(QColor("#2e2e2e" if db == 0 else "#1a1a1a"), 1))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(QColor("#5a5a5a"))
            p.drawText(QRectF(0, y - 7, r.left() - 8, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{db:+d}" if db else "0")
        for i, f in enumerate(eq.FREQS):
            x = self._x(f)
            p.setPen(QPen(QColor("#151515"), 1))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.setPen(QColor("#f2f2f2" if i in (self.drag, self.hover) else "#6f6f6f"))
            p.drawText(QRectF(x - 24, r.bottom() + 6, 48, 14), Qt.AlignmentFlag.AlignCenter, _freq_text(f))
        # the response
        n = 160
        freqs = [LO * (HI / LO) ** (k / (n - 1)) for k in range(n)]
        dbs = eq.response(self.gains, 0.0, freqs)        # the bands' shape; the preamp is the dashed line
        if self.preamp:
            y = self._y(self.preamp)
            p.setPen(QPen(QColor("#8c8c8c"), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.drawText(QRectF(r.right() - 120, y + 2, 116, 14), Qt.AlignmentFlag.AlignRight,
                       "preamp {db:+.1f} dB".format(db=self.preamp))
        path = QPainterPath()
        for k, (f, db) in enumerate(zip(freqs, dbs)):
            pt = QPointF(self._x(f), self._y(max(-eq.LIMIT - 2, min(eq.LIMIT + 2, db))))
            path.moveTo(pt) if k == 0 else path.lineTo(pt)
        p.save()
        p.setClipRect(r.adjusted(0, -2, 0, 2))
        fill = QPainterPath(path)
        fill.lineTo(QPointF(r.right(), self._y(0)))
        fill.lineTo(QPointF(r.left(), self._y(0)))
        fill.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 18))
        p.drawPath(fill)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#f2f2f2"), 2))
        p.drawPath(path)
        p.restore()
        # the handles
        for i, (f, g) in enumerate(zip(eq.FREQS, self.gains)):
            c = QPointF(self._x(f), self._y(g))
            active = i in (self.drag, self.hover)
            p.setPen(QPen(QColor("#f2f2f2"), 1.6))
            p.setBrush(QColor("#f2f2f2") if active else QColor("#0b0b0b"))
            p.drawEllipse(c, 6, 6)
            if active:
                p.setPen(QColor("#f2f2f2"))
                p.drawText(QRectF(c.x() - 30, c.y() - 26, 60, 14), Qt.AlignmentFlag.AlignCenter, f"{g:+.1f} dB")

    def mousePressEvent(self, e):
        self.drag = self._band_at(e.position())
        if self.drag >= 0:
            self._set(self.drag, self._db_at(e.position().y()))

    def mouseMoveEvent(self, e):
        if self.drag >= 0:
            self._set(self.drag, self._db_at(e.position().y()))
        else:
            h = self._band_at(e.position())
            if h != self.hover:
                self.hover = h
                self.update()

    def mouseReleaseEvent(self, _):
        self.drag = -1
        self.update()

    def mouseDoubleClickEvent(self, e):
        i = self._band_at(e.position())
        if i >= 0:
            self._set(i, 0.0)

    def wheelEvent(self, e):
        i = self._band_at(e.position())
        if i >= 0:
            step = STEP if e.angleDelta().y() > 0 else -STEP
            self._set(i, max(-eq.LIMIT, min(eq.LIMIT, self.gains[i] + step)))

    def leaveEvent(self, e):
        self.hover = -1
        self.update()
        super().leaveEvent(e)

    def _set(self, i: int, db: float):
        if self.gains[i] != db:
            self.gains[i] = db
            self.update()
            self.changed.emit()


class EqPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.s = eq.load()
        self.running_id: int | None = None          # the EQ's node while it's up
        self.outputs: list[dict] = []
        self.fc = None                              # filter-chain.service there? (asked once, off the UI thread)
        self.installed_output = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        top = QFrame()
        top.setObjectName("Row")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(18, 14, 18, 14)
        text = QVBoxLayout()
        text.setSpacing(4)
        text.addWidget(_label("Grimoire EQ", "RowTitle"))
        self.state = _label("", "Muted", wrap=True)
        text.addWidget(self.state)
        tl.addLayout(text, 1)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setObjectName("Primary")
        self.apply_btn.clicked.connect(self.apply)
        tl.addWidget(self.apply_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.switch = Switch()
        self.switch.toggled.connect(self._switched)
        tl.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(top)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addWidget(_label("Preset", "Muted"))
        self.preset = QComboBox()
        self.preset.setMinimumWidth(160)
        self.preset.activated.connect(self._preset_picked)
        bar.addWidget(self.preset)
        self.save_btn = QPushButton("Save as preset…")
        self.save_btn.clicked.connect(self._save_preset)
        bar.addWidget(self.save_btn)
        self.del_btn = QPushButton("Delete preset")
        self.del_btn.clicked.connect(self._delete_preset)
        bar.addWidget(self.del_btn)
        bar.addStretch(1)
        bar.addWidget(_label("Plays into", "Muted"))
        self.target = QComboBox()
        self.target.setMinimumWidth(260)
        self.target.activated.connect(self._target_picked)
        bar.addWidget(self.target)
        lay.addLayout(bar)

        self.curve = EqCurve()
        self.curve.changed.connect(self._curve_changed)
        lay.addWidget(self.curve, 1)

        pre = QHBoxLayout()
        pre.addWidget(_label("Preamp", "Muted"))
        self.pre = Slider(-24, 24, " dB")             # half-dB steps: the slider counts halves
        self.pre.v.setFixedWidth(64)
        self.pre.s.valueChanged.connect(self._pre_changed)
        pre.addWidget(self.pre, 1)
        auto = QPushButton("Prevent clipping")
        auto.setToolTip("Lowers the preamp by the biggest boost, so loud parts can't distort")
        auto.clicked.connect(self._auto_pre)
        pre.addWidget(auto)
        flat = QPushButton("Reset")
        flat.clicked.connect(lambda: self._load_preset("Flat"))
        pre.addWidget(flat)
        lay.addLayout(pre)
        lay.addWidget(_label(
            "The EQ is one more output, \"Grimoire EQ\", that plays into the device you pick; while it's on it's your "
            "default output. Turning it on or off, or changing its device, takes effect when you press Apply, which "
            "restarts PipeWire's filter-chain service (sound through the EQ pauses for a second). Moving bands while "
            "it's on changes the sound right away.", "Muted", wrap=True))

        self._live = QTimer(self, singleShot=True, interval=120, timeout=self._push_live)
        self._fill_presets()
        self._show_curve()
        self.switch.setChecked(self.s["on"])

    # ------------------------------------------------------------ state from the page's poll
    def update_snap(self, snap: dict, fc: bool | None, installed_output):
        self.fc, self.installed_output = fc, installed_output
        eq_node = next((d for d in snap["outputs"] if d["eq"]), None)
        self.running_id = eq_node["id"] if eq_node else None
        self.outputs = [d for d in snap["outputs"] if not d["eq"]]
        if not self.s["output"]:
            real = next((d for d in self.outputs if d["default"]), self.outputs[0] if self.outputs else None)
            if real:
                self.s["output"] = real["name"]
        names = [(d["label"], d["name"]) for d in self.outputs]
        if self.s["output"] and self.s["output"] not in (n for _, n in names):
            names.append(("{name} (not connected)".format(name=self.s["output"]), self.s["output"]))
        if names != [(self.target.itemText(i), self.target.itemData(i)) for i in range(self.target.count())]:
            self.target.blockSignals(True)
            self.target.clear()
            for label, name in names:
                self.target.addItem(label, name)
            self.target.blockSignals(False)
        idx = self.target.findData(self.s["output"])
        if idx >= 0 and not self.target.view().isVisible():
            self.target.setCurrentIndex(idx)
        self._show_state(eq_node)

    def pending(self) -> bool:
        running = self.running_id is not None
        if self.s["on"] != running:
            return True
        return self.s["on"] and self.installed_output is not None and self.installed_output != self.s["output"]

    def _show_state(self, eq_node=None):
        running = self.running_id is not None
        target_ok = any(d["name"] == self.s["output"] for d in self.outputs)
        label = next((d["label"] for d in self.outputs if d["name"] == self.s["output"]), self.s["output"])
        if self.pending():
            msg = ("Press Apply to turn it on." if self.s["on"] else "Press Apply to turn it off.") \
                if self.s["on"] != running else "Press Apply to play it into {device}.".format(device=label)
        elif running:
            msg = "On · plays into {device}".format(device=label)
            if eq_node is not None and not eq_node["default"]:
                msg = "On · plays into {device} · not your default output, so only apps you move to it go " \
                      "through it".format(device=label)
            if not target_ok:
                msg = "On, but {device} isn't connected: pick another device and press Apply.".format(device=label)
        else:
            msg = "Off"
        if self.fc is False:
            msg += "  " + "(This system has no filter-chain service, so Apply restarts PipeWire itself.)"
        self.state.setText(msg)
        self.apply_btn.setVisible(self.pending())

    # ------------------------------------------------------------ presets and the curve
    def _fill_presets(self):
        self.preset.blockSignals(True)
        self.preset.clear()
        for name in eq.all_presets(self.s):
            self.preset.addItem(name, name)
        self.preset.addItem("Custom", "")
        self.preset.blockSignals(False)
        self._sync_preset()

    def _sync_preset(self):
        name = eq.matching_preset(self.s)
        self.s["preset"] = name
        self.preset.setCurrentIndex(max(0, self.preset.findData(name)))
        self.del_btn.setEnabled(name in self.s["presets"] and name not in eq.PRESETS)

    def _show_curve(self):
        self.curve.set_curve(self.s["gains"], self.s["preamp"])
        self.pre.s.blockSignals(True)
        self.pre.s.setValue(round(self.s["preamp"] * 2))
        self.pre.s.blockSignals(False)
        self.pre.v.setText(f"{self.s['preamp']:+.1f} dB")

    def _load_preset(self, name: str):
        presets = eq.all_presets(self.s)
        if name not in presets:
            return
        gains, pre = presets[name]
        self.s["gains"], self.s["preamp"] = [float(g) for g in gains], float(pre)
        self._show_curve()
        self._changed()

    def _preset_picked(self, i: int):
        name = self.preset.itemData(i)
        if name:
            self._load_preset(name)
        else:
            self._sync_preset()

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Save preset", "Name for this curve:")
        name = name.strip()[:60]
        if not ok or not name:
            return
        if name in eq.PRESETS:
            QMessageBox.information(self, "Save preset", "{name} is a built-in preset; pick another name.".format(
                name=name))
            return
        self.s["presets"][name] = {"gains": list(self.s["gains"]), "preamp": self.s["preamp"]}
        eq.save(self.s)
        self._fill_presets()

    def _delete_preset(self):
        name = self.preset.currentData()
        if name in self.s["presets"]:
            del self.s["presets"][name]
            eq.save(self.s)
            self._fill_presets()

    def _curve_changed(self):
        self.s["gains"] = list(self.curve.gains)
        self._changed()

    def _pre_changed(self, v: int):
        self.s["preamp"] = v / 2
        self.pre.v.setText(f"{self.s['preamp']:+.1f} dB")
        self.curve.set_curve(self.s["gains"], self.s["preamp"])
        self._changed()

    def _auto_pre(self):
        self.s["preamp"] = eq.suggested_preamp(self.s["gains"])
        self._show_curve()
        self._changed()

    def _changed(self):
        self._sync_preset()
        self._live.start()

    def _push_live(self):
        """Save; while the EQ runs, send the new gains to it and rewrite its drop-in (no restart)."""
        s = dict(self.s)
        eq.save(s)
        running = self.running_id
        if running is None or not s["on"]:
            return
        fc = self.fc

        def work():
            pw.set_props(running, eq.live_params(s["gains"], s["preamp"]))
            path = eq.drop_in(fc)
            if eq.installed(path):
                eq.write(s, path)
            return "updated"
        self.page.act("Equalizer", work, quiet=True)

    def _target_picked(self, i: int):
        self.s["output"] = self.target.itemData(i) or ""
        eq.save(self.s)
        self._show_state()

    def _switched(self, on: bool):
        self.s["on"] = on
        eq.save(self.s)
        self._show_state()

    # ------------------------------------------------------------ Apply
    def apply(self):
        s = dict(self.s)
        if not s["output"]:
            self.page.say("Pick the device the equalizer plays into first.")
            return
        fc = self.fc
        self.apply_btn.setEnabled(False)

        def done_then():
            fresh = eq.load()                      # turn() records what it changed (old default, unit enabled)
            self.s["restore"], self.s["enabled_unit"] = fresh["restore"], fresh["enabled_unit"]
            self.apply_btn.setEnabled(True)
            self.page.refresh()
        self.page.act("Equalizer", lambda: turn(s, fc), then=done_then)


def _wait_eq(seconds=6.0) -> dict | None:
    import time
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        snap = pw.snapshot()
        node = next((d for d in snap["outputs"] if d["eq"]), None)
        if node:
            return node
        time.sleep(0.25)
    return None


def turn(s: dict, fc: bool | None) -> str:
    """The Apply step, on a worker thread: write or put aside the drop-in, restart its service, and move the
    default output onto the EQ (remembering the old one) or back off it."""
    fc = eq.uses_filter_chain() if fc is None else fc
    path = eq.drop_in(fc)
    snap = pw.snapshot()
    current = pw.default(snap)
    if s["on"]:
        eq.write(s, path)
        if fc and not eq.unit_enabled():
            eq.set_unit_enabled(True)              # so it's back after the next login
            s["enabled_unit"] = True
        if current and not current["eq"]:
            s["restore"] = current["name"]
        eq.save(s)
        unit = eq.restart(fc)
        node = _wait_eq()
        if not node:
            raise RuntimeError("{unit} restarted but the EQ didn't appear; see journalctl --user -u {unit}".format(
                unit=unit))
        pw.set_default(node["id"])
        label = next((d["label"] for d in snap["outputs"] if d["name"] == s["output"]), s["output"])
        return "on, playing into {device}".format(device=label)
    back_name = s["restore"] or s["output"]
    if current and current["eq"]:
        back = next((d for d in snap["outputs"] if d["name"] == back_name and not d["eq"]), None) \
            or next((d for d in snap["outputs"] if not d["eq"]), None)
        if back:
            pw.set_default(back["id"])
    eq.put_aside(path)
    unit = eq.restart(fc)
    if s.get("enabled_unit"):
        eq.set_unit_enabled(False)
        s["enabled_unit"] = False
    eq.save(s)
    return "off"
