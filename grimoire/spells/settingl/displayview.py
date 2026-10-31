# SPDX-License-Identifier: GPL-3.0-or-later
"""Displays: arrange the screens, their resolution, refresh rate, scale and orientation, the primary one, and night
light. Screen changes are a draft until Apply; then a countdown puts the old layout back unless you keep it."""

import copy

from PySide6.QtCore import QCoreApplication, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QSizePolicy, QWidget

from grimoire import i18n
from grimoire.i18n import tr
from grimoire.spells.settingl import displays
from grimoire.spells.settingl.common import Panel, Row, combo, label
from grimoire.widgets import Slider, Switch, segments

CTX = "grimoire.spells.settingl.displayview"
SCALES = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0]
KEEP_SECONDS = 15
SNAP = 40  # px on the desktop within which a dragged screen sticks to another's edge


def _name(o: dict) -> str:
    return o["label"] or o["name"]


class Arrangement(QWidget):
    """The screens drawn to scale; drag one to move it, click to pick it. Always laid out left to right."""

    picked = Signal(object)
    moved = Signal()

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.outs: list[dict] = []
        self.sel = ""
        self._drag = None

    def set_outputs(self, outs: list[dict], sel: str):
        self.outs, self.sel = outs, sel
        self.update()

    def _on(self):
        return [o for o in self.outs if o["enabled"]]

    def _transform(self):
        on = self._on()
        if not on:
            return 1.0, 0.0, 0.0
        x0 = min(o["x"] for o in on)
        y0 = min(o["y"] for o in on)
        x1 = max(o["x"] + displays.logical_size(o)[0] for o in on)
        y1 = max(o["y"] + displays.logical_size(o)[1] for o in on)
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        pad = 24
        k = min((self.width() - 2 * pad) / w, (self.height() - 2 * pad) / h)
        ox = (self.width() - w * k) / 2 - x0 * k
        oy = (self.height() - h * k) / 2 - y0 * k
        return k, ox, oy

    def _rect(self, o, t=None) -> QRectF:
        k, ox, oy = t or self._transform()
        w, h = displays.logical_size(o)
        return QRectF(ox + o["x"] * k, oy + o["y"] * k, w * k, h * k)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#080808"))
        p.setPen(QPen(QColor("#1c1c1c")))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        t = self._transform()
        for o in self._on():
            r = self._rect(o, t).adjusted(3, 3, -3, -3)
            sel = o["name"] == self.sel
            p.setPen(QPen(QColor("#f2f2f2" if sel else "#4a4a4a"), 2 if sel else 1))
            p.setBrush(QColor("#1a1a1a" if sel else "#111111"))
            p.drawRoundedRect(r, 6, 6)
            f = QFont(self.font())
            f.setPointSizeF(max(7.5, min(12.0, r.height() / 9)))
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            p.setPen(QColor("#ffffff" if sel else "#9a9a9a"))
            w, h = (displays.mode_of(o) or {"w": 0, "h": 0})["w"], (displays.mode_of(o) or {"h": 0})["h"]
            text = f"{_name(o)}\n{o['name']} · {w}×{h}" + ("\n★" if o["primary"] else "")
            p.drawText(r.adjusted(6, 6, -6, -6), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
        if not self._on():
            p.setPen(QColor("#6f6f6f"))
            p.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, tr("grimoire.spells.settingl.displayview", "No screen is on")
            )

    def _hit(self, pos: QPointF):
        t = self._transform()
        return next((o for o in reversed(self._on()) if self._rect(o, t).contains(pos)), None)

    def mousePressEvent(self, e):
        o = self._hit(e.position())
        if o:
            self.sel = o["name"]
            self.picked.emit(o["name"])
            k, _, _ = self._transform()
            self._drag = (o, e.position(), o["x"], o["y"], k)
            self.update()

    def mouseMoveEvent(self, e):
        if not self._drag:
            return
        o, start, x, y, k = self._drag
        d = e.position() - start
        o["x"], o["y"] = round(x + d.x() / k), round(y + d.y() / k)
        self.update()

    def mouseReleaseEvent(self, e):
        if not self._drag:
            return
        o, start, x, y, _ = self._drag
        self._drag = None
        if (e.position() - start).manhattanLength() < 3:
            o["x"], o["y"] = x, y
            return
        self._snap(o)
        displays.tidy(self.outs)
        self.update()
        self.moved.emit()

    def _snap(self, o):
        """Make the dragged screen touch the nearest one, edges lined up when they're close."""
        others = [x for x in self._on() if x is not o]
        if not others:
            o["x"], o["y"] = 0, 0
            return
        w, h = displays.logical_size(o)
        best = None
        for t in others:
            tw, th = displays.logical_size(t)
            for cx, cy in ((t["x"] + tw, o["y"]), (t["x"] - w, o["y"]), (o["x"], t["y"] + th), (o["x"], t["y"] - h)):
                if cx in (t["x"] + tw, t["x"] - w):  # beside: keep the vertical overlap
                    cy = max(t["y"] - h + 1, min(t["y"] + th - 1, cy))
                    for edge in (t["y"], t["y"] + th - h):
                        if abs(cy - edge) < SNAP:
                            cy = edge
                else:  # above/below: keep the horizontal overlap
                    cx = max(t["x"] - w + 1, min(t["x"] + tw - 1, cx))
                    for edge in (t["x"], t["x"] + tw - w):
                        if abs(cx - edge) < SNAP:
                            cx = edge
                dist = abs(cx - o["x"]) + abs(cy - o["y"])
                overlap = any(
                    cx < s["x"] + displays.logical_size(s)[0]
                    and s["x"] < cx + w
                    and cy < s["y"] + displays.logical_size(s)[1]
                    and s["y"] < cy + h
                    for s in others
                )
                if not overlap and (best is None or dist < best[0]):
                    best = (dist, cx, cy)
        if best:
            o["x"], o["y"] = best[1], best[2]

    def keyPressEvent(self, e):
        on = self._on()
        if e.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Right, Qt.Key.Key_Left) and len(on) > 1:
            i = next((n for n, o in enumerate(on) if o["name"] == self.sel), 0)
            i = (i + (-1 if e.key() == Qt.Key.Key_Left else 1)) % len(on)
            self.sel = on[i]["name"]
            self.picked.emit(self.sel)
            self.update()
            return
        super().keyPressEvent(e)


class DisplaysPanel(Panel):
    POLL = 0

    def __init__(self, host):
        super().__init__(host)
        self.current: list[dict] = []  # what the screens are now
        self.draft: list[dict] = []  # what the page shows (current + your changes)
        self.before: list[dict] | None = None  # the layout to go back to while a change waits to be kept
        self.sel = ""
        self._quiet = False

        self.missing = self.note("")
        self.missing.hide()
        self.chips = QHBoxLayout()
        self.chips.setSpacing(0)
        chips = QWidget()
        chips.setLayout(self.chips)
        self.chip_box = chips
        self.col.addWidget(chips, 0, Qt.AlignmentFlag.AlignLeading)
        self.canvas = Arrangement()
        self.canvas.picked.connect(self._pick)
        self.canvas.moved.connect(self._changed)
        self.col.addWidget(self.canvas)
        self.col.addWidget(
            label(
                tr(
                    "grimoire.spells.settingl.displayview",
                    "Drag a screen to arrange it next to the others. Click one to change it below.",
                ),
                "Muted",
                wrap=True,
            )
        )

        self.head = label("", "SectionTitle", plain=True)
        self.col.addSpacing(6)
        self.col.addWidget(self.head)
        self.on_sw = Switch()
        self.on_sw.toggled.connect(self._enable)
        self.on_row = Row(tr("grimoire.spells.settingl.displayview", "Use this screen"), "", self.on_sw)
        self.col.addWidget(self.on_row)
        self.primary_btn = QPushButton(tr("grimoire.spells.settingl.displayview", "Make primary"))
        self.primary_btn.clicked.connect(self._primary)
        self.primary_row = Row(
            tr("grimoire.spells.settingl.displayview", "Primary screen"),
            tr("grimoire.spells.settingl.displayview", "The panel and new windows open here first."),
            self.primary_btn,
        )
        self.col.addWidget(self.primary_row)
        self.res = combo()
        self.res.activated.connect(self._resolution)
        self.res_row = Row(tr("grimoire.spells.settingl.displayview", "Resolution"), "", self.res)
        self.col.addWidget(self.res_row)
        self.rate = combo(160)
        self.rate.activated.connect(self._rate)
        self.col.addWidget(
            Row(
                tr("grimoire.spells.settingl.displayview", "Refresh rate"),
                tr("grimoire.spells.settingl.displayview", "How many times a second the picture is redrawn."),
                self.rate,
            )
        )
        self.scale = combo(160)
        self.scale.activated.connect(self._scale)
        self.col.addWidget(
            Row(
                tr("grimoire.spells.settingl.displayview", "Scale"),
                tr("grimoire.spells.settingl.displayview", "Makes text and everything else bigger on this screen."),
                self.scale,
            )
        )
        self.rot = combo(200)
        for rid, text in (
            ("none", tr("grimoire.spells.settingl.displayview", "Landscape")),
            ("left", tr("grimoire.spells.settingl.displayview", "Portrait (turned left)")),
            ("right", tr("grimoire.spells.settingl.displayview", "Portrait (turned right)")),
            ("inverted", tr("grimoire.spells.settingl.displayview", "Landscape (upside down)")),
        ):
            self.rot.addItem(text, rid)
        self.rot.activated.connect(self._rotation)
        self.col.addWidget(Row(tr("grimoire.spells.settingl.displayview", "Orientation"), "", self.rot))

        self.pending = QFrame()
        self.pending.setObjectName("Pending")
        pl = QHBoxLayout(self.pending)
        pl.setContentsMargins(18, 10, 12, 10)
        self.pending_text = label("", "PendingText", wrap=True)
        pl.addWidget(self.pending_text, 1)
        self.undo_btn = QPushButton(tr("grimoire.spells.settingl.displayview", "Reset"))
        self.undo_btn.clicked.connect(self._reset)
        self.apply_btn = QPushButton(tr("grimoire.spells.settingl.displayview", "Apply"))
        self.apply_btn.setObjectName("Primary")
        self.apply_btn.clicked.connect(self._apply)
        pl.addWidget(self.undo_btn)
        pl.addWidget(self.apply_btn)
        self.pending.hide()
        self.col.addWidget(self.pending)
        self._countdown = QTimer(self, interval=1000, timeout=self._tick)
        self._left = 0
        QCoreApplication.instance().aboutToQuit.connect(self._quitting)

        self.section(tr("grimoire.spells.settingl.displayview", "Night light"))
        self.night_sw = Switch()
        self.night_sw.toggled.connect(self._night_on)
        self.night_row = Row(
            tr("grimoire.spells.settingl.displayview", "Night light"),
            tr("grimoire.spells.settingl.displayview", "Warmer colors in the evening are easier on the eyes."),
            self.night_sw,
        )
        self.col.addWidget(self.night_row)
        self.mode_btns = []
        mode = QWidget()
        ml = QHBoxLayout(mode)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        for mid, text in (
            ("daynight", tr("grimoire.spells.settingl.displayview", "Sunset to sunrise")),
            ("constant", tr("grimoire.spells.settingl.displayview", "Always on")),
        ):
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, m=mid: self._night_mode(m))
            b.mode = mid
            ml.addWidget(b)
            self.mode_btns.append(b)
        segments(self.mode_btns)
        self.col.addWidget(
            Row(
                tr("grimoire.spells.settingl.displayview", "When"),
                tr("grimoire.spells.settingl.displayview", "Sunset and sunrise follow KDE's day-night cycle."),
                mode,
            )
        )
        self.warm = Slider(displays.NIGHT_MIN // 100, displays.NIGHT_MAX // 100)
        self.warm.setMinimumWidth(260)
        self.warm.v.setFixedWidth(64)
        self.warm.s.valueChanged.connect(lambda v: self.warm.v.setText(i18n.ltr(f"{v * 100} K")))
        self.warm.s.sliderReleased.connect(self._night_temp)
        self.warm.s.valueChanged.connect(
            lambda _v: None if self.warm.s.isSliderDown() or self._quiet else self._warm_timer.start()
        )
        self._warm_timer = QTimer(self, singleShot=True, interval=400, timeout=self._night_temp)
        self.col.addWidget(
            Row(
                tr("grimoire.spells.settingl.displayview", "Night warmth"),
                tr("grimoire.spells.settingl.displayview", "Lower is warmer (more orange). KWin's default is 4500 K."),
                self.warm,
            )
        )
        self.kde_links(["kcm_kscreen", "kcm_nightlight", "kcm_nighttime", "kcm_kgamma", "kcm_kwinscreenedges"])
        self.finish()

    # ------------------------------------------------------------ reading
    def read(self):
        return {"screens": displays.read(), "night": displays.night()}

    def fill(self, data):
        scr = data["screens"]
        if self.before is None and not self.pending.isVisible():
            self.current = scr["outputs"]
            self.draft = copy.deepcopy(self.current)
        if scr["error"] and not scr["outputs"]:
            self.missing.setText(
                tr("grimoire.spells.settingl.displayview", "KDE's screen tool didn't answer: {error}").format(
                    error=scr["error"]
                )
            )
            self.missing.show()
        else:
            self.missing.hide()
        if not any(o["name"] == self.sel for o in self.draft) and self.draft:
            self.sel = next((o["name"] for o in self.draft if o["primary"]), self.draft[0]["name"])
        self._show()
        self._show_night(data["night"])

    def _sel(self) -> dict | None:
        return next((o for o in self.draft if o["name"] == self.sel), None)

    def _show(self):
        self._quiet = True
        while self.chips.count():
            w = self.chips.takeAt(0).widget()
            if w:
                w.deleteLater()
        chips = []
        if len(self.draft) > 1:
            for o in self.draft:
                b = QPushButton(_name(o).replace("&", "&&"))
                b.setObjectName("Segment")
                b.setCheckable(True)
                b.setChecked(o["name"] == self.sel)
                b.clicked.connect(lambda _=False, n=o["name"]: self._pick(n))
                self.chips.addWidget(b)
                chips.append(b)
            segments(chips)
        self.chip_box.setVisible(bool(chips))
        self.canvas.set_outputs(self.draft, self.sel)
        o = self._sel()
        for w in (self.on_row, self.primary_row, self.res_row):
            w.setEnabled(o is not None)
        if o is None:
            self.head.setText("")
            self._quiet = False
            return
        mm = o["mm"]
        inches = ((mm[0] ** 2 + mm[1] ** 2) ** 0.5) / 25.4 if mm[0] else 0
        self.head.setText(
            _name(o) + (f"  ·  {o['name']}" if o["label"] else "") + (f"  ·  {inches:.0f}\"" if inches else "")
        )
        self.on_sw.setChecked(o["enabled"])
        alone = sum(x["enabled"] for x in self.draft) <= 1
        self.on_sw.setEnabled(not (alone and o["enabled"]))
        self.on_row.set_sub(
            tr("grimoire.spells.settingl.displayview", "This is the only screen that's on.")
            if alone and o["enabled"]
            else ""
        )
        self.primary_btn.setVisible(not o["primary"] and o["enabled"])
        self.primary_row.setVisible(len([x for x in self.draft if x["enabled"]]) > 1 or not o["primary"])
        self.primary_row.set_sub(
            tr(
                "grimoire.spells.settingl.displayview",
                "This is the primary screen: the panel and new windows open here first.",
            )
            if o["primary"]
            else tr("grimoire.spells.settingl.displayview", "The panel and new windows open here first.")
        )
        cur = displays.mode_of(o)
        self.res.clear()
        best = displays.mode_of(o, o["preferred"][0]) if o["preferred"] else None
        for w, h in displays.sizes(o):
            text = f"{w} × {h}"
            if best and (best["w"], best["h"]) == (w, h):
                text = tr("grimoire.spells.settingl.displayview", "{size} (recommended)").format(size=text)
            self.res.addItem(text, f"{w}x{h}")
        if cur:
            self.res.setCurrentIndex(self.res.findData(f"{cur['w']}x{cur['h']}"))
            self.rate.clear()
            for m in displays.rates(o, (cur["w"], cur["h"])):
                self.rate.addItem(
                    tr("grimoire.spells.settingl.displayview", "{rate} Hz").format(rate=f"{m['rate']:g}"), m["id"]
                )
            self.rate.setCurrentIndex(max(0, self.rate.findData(o["mode"])))
        self.scale.clear()
        for s in sorted(set(SCALES) | {o["scale"]}):
            self.scale.addItem(f"{round(s * 100)}%", s)
        self.scale.setCurrentIndex(self.scale.findData(o["scale"]))
        self.rot.setCurrentIndex(max(0, self.rot.findData(o["rotation"])))
        for w in (self.res, self.rate, self.scale, self.rot):
            w.setEnabled(o["enabled"])
        self._pending()
        self._quiet = False

    def _pending(self):
        if self.before is not None:
            return
        changed = bool(displays.args_for(self.draft, self.current))
        self.pending_text.setText(
            tr(
                "grimoire.spells.settingl.displayview",
                "You changed the screens. Apply to try it: you'll have {n} seconds to keep it.",
            ).format(n=KEEP_SECONDS)
        )
        self.undo_btn.setText(tr("grimoire.spells.settingl.displayview", "Reset"))
        self.apply_btn.setText(tr("grimoire.spells.settingl.displayview", "Apply"))
        self.pending.setVisible(changed)

    # ------------------------------------------------------------ editing the draft
    def _pick(self, name: str):
        self.sel = name
        self._show()

    def _changed(self):
        self._show()

    def _edit(self, fn):
        o = self._sel()
        if o is None or self._quiet or self.before is not None:
            return
        old = displays.logical_size(o)
        fn(o)
        displays.reflow(self.draft, o, old)
        displays.tidy(self.draft)
        self._show()

    def _enable(self, on: bool):
        def fn(o):
            o["enabled"] = on
            if on:  # comes back to the right of the others
                others = [x for x in self.draft if x["enabled"] and x is not o]
                o["x"] = max((x["x"] + displays.logical_size(x)[0] for x in others), default=0)
                o["y"] = 0
                if not o["mode"] and o["modes"]:
                    o["mode"] = (o["preferred"] or [o["modes"][0]["id"]])[0]
            elif o["primary"]:
                o["primary"] = False
                nxt = next((x for x in self.draft if x["enabled"] and x is not o), None)
                if nxt:
                    nxt["primary"] = True

        self._edit(fn)

    def _primary(self):
        def fn(o):
            for x in self.draft:
                x["primary"] = x is o

        self._edit(fn)

    def _resolution(self, _i):
        size = tuple(int(x) for x in self.res.currentData().split("x"))

        def fn(o):
            modes = displays.rates(o, size)
            cur = displays.mode_of(o)
            same = next((m for m in modes if cur and abs(m["rate"] - cur["rate"]) < 0.5), None)
            o["mode"] = (same or modes[0])["id"]

        self._edit(fn)

    def _rate(self, _i):
        mid = self.rate.currentData()
        self._edit(lambda o: o.__setitem__("mode", mid))

    def _scale(self, _i):
        s = self.scale.currentData()
        self._edit(lambda o: o.__setitem__("scale", s))

    def _rotation(self, _i):
        r = self.rot.currentData()
        self._edit(lambda o: o.__setitem__("rotation", r))

    def _reset(self):
        if self.before is not None:
            self._revert()
            return
        self.draft = copy.deepcopy(self.current)
        self._show()

    # ------------------------------------------------------------ applying, keeping, going back
    def _apply(self):
        if self.before is not None:  # "Keep"
            self._countdown.stop()
            self.before = None
            self.pending.hide()
            self.host.say(tr("grimoire.spells.settingl.displayview", "Kept the new display settings."))
            self.load(force=True)
            return
        before, draft = copy.deepcopy(self.current), copy.deepcopy(self.draft)
        self.apply_btn.setEnabled(False)
        self.host.act(
            tr("grimoire.spells.settingl.displayview", "Displays"),
            lambda: displays.apply(draft, before) or "",
            then=lambda: self._applied(before),
            quiet=True,
            on_fail=lambda: self._apply_failed(before),
        )

    def _apply_failed(self, before):
        """kscreen-doctor can fail or time out after KWin took part of the change: put the old layout back."""
        self.apply_btn.setEnabled(True)
        self.host.act(
            tr("grimoire.spells.settingl.displayview", "Displays"),
            lambda: displays.revert(before) or "",
            then=lambda: self.load(force=True),
            quiet=True,
        )

    def _applied(self, before):
        self.apply_btn.setEnabled(True)
        self.before = before
        self.current = copy.deepcopy(self.draft)
        self._left = KEEP_SECONDS
        self.undo_btn.setText(tr("grimoire.spells.settingl.displayview", "Go back"))
        self.apply_btn.setText(tr("grimoire.spells.settingl.displayview", "Keep"))
        self.pending.show()
        self._tick(first=True)
        self._countdown.start()

    def _tick(self, first=False):
        if not first:
            self._left -= 1
        if self._left <= 0:
            self._revert()
            return
        self.pending_text.setText(
            tr(
                "grimoire.spells.settingl.displayview",
                "Keep these display settings? Going back in %n second(s).",
                n=self._left,
            )
        )

    def _revert(self):
        self._countdown.stop()
        before, self.before = self.before, None
        self.pending.hide()
        if before is None:
            return
        self.host.act(
            tr("grimoire.spells.settingl.displayview", "Displays"),
            lambda: displays.revert(before) or tr("grimoire.spells.settingl.displayview", "put back as they were"),
            then=lambda: self._reverted(before),
        )

    def _reverted(self, before):
        self.current = before
        self.draft = copy.deepcopy(before)
        self._show()
        self.load(force=True)

    def hideEvent(self, e):
        super().hideEvent(e)  # the countdown keeps running: going back must still happen

    def _quitting(self):
        """The app closes while a change waits to be kept: go back now, as the countdown would have."""
        before, self.before = self.before, None
        if before is not None:
            try:
                self._countdown.stop()
                displays.revert(before)
            except Exception:  # quitting: nowhere left to show it
                pass

    # ------------------------------------------------------------ night light
    def _show_night(self, n: dict):
        self._quiet = True
        self.night_sw.setChecked(n["active"])
        for b in self.mode_btns:
            b.setChecked(b.mode == n["mode"])
        if not self.warm.s.isSliderDown() and not self._warm_timer.isActive():
            self.warm.setValue(n["temperature"] // 100)
            self.warm.v.setText(i18n.ltr(f"{n['temperature']} K"))
        self.warm.setEnabled(n["active"])
        if not n["available"]:
            sub = tr("grimoire.spells.settingl.displayview", "This graphics setup doesn't support night light.")
        elif n["active"] and n["running"]:
            sub = tr("grimoire.spells.settingl.displayview", "On now at {temp}.").format(
                temp=i18n.ltr(f"{n['current']} K")
            )
        elif n["active"]:
            sub = (
                tr("grimoire.spells.settingl.displayview", "On, waiting for sunset.")
                if n["mode"] == "daynight"
                else tr("grimoire.spells.settingl.displayview", "On.")
            )
        else:
            sub = tr("grimoire.spells.settingl.displayview", "Warmer colors in the evening are easier on the eyes.")
        self.night_row.set_sub(sub)
        self._quiet = False

    def _night_on(self, on: bool):
        if not self._quiet:
            self.act(
                tr("grimoire.spells.settingl.displayview", "Night light"),
                lambda: displays.set_night(active=on) or "",
                quiet=True,
            )

    def _night_mode(self, mode: str):
        for b in self.mode_btns:
            b.setChecked(b.mode == mode)
        self.act(
            tr("grimoire.spells.settingl.displayview", "Night light"),
            lambda: displays.set_night(mode=mode) or "",
            quiet=True,
        )

    def _night_temp(self):
        if self._quiet:
            return
        self._warm_timer.stop()
        k = self.warm.value() * 100
        self.act(
            tr("grimoire.spells.settingl.displayview", "Night light"),
            lambda: displays.set_night(temperature=k) or "",
            quiet=True,
        )
