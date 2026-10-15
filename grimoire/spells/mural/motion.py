# SPDX-License-Identifier: GPL-3.0-or-later
"""Motion tab: animation speed + which KWin effects run (open/close, minimize, desktop switch, closing breaks
apart, dialog sheets, dim inactive, sliding menus, wobbly windows, translucency, blur). Effects are loaded/unloaded
live and saved to kwinrc; every design sets every effect it manages, so switching designs leaves nothing behind.
"""
import subprocess

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import tr, tr_noop
from grimoire.spells.mural.kde import kwin_reconfigure, kwrite
from grimoire.spells.mural.screens import Choice, Design, ScreenTab, WrapCheck
from grimoire.widgets import Slider

# effect groups: only one of each group runs
OPEN_CLOSE = ["scale", "glide", "fade"]
MINIMIZE = ["squash", "magiclamp"]
SWITCH = ["slide", "fadedesktop"]
# extras every design sets, on or off, so switching designs never leaves one behind (Plasma's default first)
EXTRAS = {"fallapart": False, "sheet": False, "diminactive": False, "slidingpopups": True, "maximize": True}


def _p(speed, open_, mini, switch, translucent=False, **extras):
    return {"speed": speed, "open": open_, "minimize": mini, "switch": switch, "translucent": translucent,
            **EXTRAS, **extras}


PRESETS = {
    "still": _p(0.0, None, None, None, slidingpopups=False, maximize=False),
    "swift": _p(0.5, "scale", "squash", "slide"),
    "smooth": _p(1.0, "scale", "squash", "slide"),
    "fluid": _p(1.3, "glide", "magiclamp", "slide"),
    "glass": _p(1.0, "fade", "squash", "fadedesktop", True),
    "snap": _p(0.25, "scale", "squash", "slide", slidingpopups=False),
    "genie": _p(1.0, "scale", "magiclamp", "slide"),
    "quiet": _p(0.7, "fade", None, "fadedesktop", slidingpopups=False, maximize=False),
    "paper": _p(0.9, "glide", "squash", "slide", sheet=True),
    "focus": _p(0.8, "fade", "squash", "fadedesktop", diminactive=True),
    "shatter": _p(1.0, "scale", "squash", "slide", fallapart=True),
    "cinema": _p(1.8, "glide", "magiclamp", "fadedesktop", sheet=True),
}
DESIGNS = [
    Design("still", tr_noop("grimoire.spells.mural.motion", "Still"),
           tr_noop("grimoire.spells.mural.motion", "No animations at all. Everything happens instantly.")),
    Design("swift", tr_noop("grimoire.spells.mural.motion", "Swift"),
           tr_noop("grimoire.spells.mural.motion",
                   "Everything twice as fast. Snappy without losing the sense of motion.")),
    Design("smooth", tr_noop("grimoire.spells.mural.motion", "Smooth"),
           tr_noop("grimoire.spells.mural.motion", "Plasma's default timing: scale, squash and slide.")),
    Design("fluid", tr_noop("grimoire.spells.mural.motion", "Fluid"),
           tr_noop("grimoire.spells.mural.motion", "Slower and softer: windows glide in and pour into the panel.")),
    Design("glass", tr_noop("grimoire.spells.mural.motion", "Glass"),
           tr_noop("grimoire.spells.mural.motion",
                   "Fades everywhere, and windows turn see-through while you drag them.")),
    Design("snap", tr_noop("grimoire.spells.mural.motion", "Snap"),
           tr_noop("grimoire.spells.mural.motion",
                   "Four times as fast: a flicker of motion, then it's done. Menus just appear.")),
    Design("genie", tr_noop("grimoire.spells.mural.motion", "Genie"),
           tr_noop("grimoire.spells.mural.motion",
                   "Normal speed, but minimized windows bend and pour into the taskbar like a magic lamp.")),
    Design("quiet", tr_noop("grimoire.spells.mural.motion", "Quiet"),
           tr_noop("grimoire.spells.mural.motion",
                   "Nothing moves, things only fade. Minimize is instant. Easy on the eyes.")),
    Design("paper", tr_noop("grimoire.spells.mural.motion", "Paper"),
           tr_noop("grimoire.spells.mural.motion",
                   "Windows glide in like sheets of paper, and dialogs drop down from their window.")),
    Design("focus", tr_noop("grimoire.spells.mural.motion", "Focus"),
           tr_noop("grimoire.spells.mural.motion",
                   "Calm fades, and every window but the one you're using dims a little.")),
    Design("shatter", tr_noop("grimoire.spells.mural.motion", "Shatter"),
           tr_noop("grimoire.spells.mural.motion", "Plasma's timing, but closed windows break apart into pieces.")),
    Design("cinema", tr_noop("grimoire.spells.mural.motion", "Cinema"),
           tr_noop("grimoire.spells.mural.motion",
                   "Slow and deliberate: long glides, a magic lamp, desktops that dissolve into each other.")),
]
LABELS = {
    "scale": tr_noop("grimoire.spells.mural.motion", "Scale"),
    "glide": tr_noop("grimoire.spells.mural.motion", "Glide"),
    "fade": tr_noop("grimoire.spells.mural.motion", "Fade"),
    "squash": tr_noop("grimoire.spells.mural.motion", "Squash"),
    "magiclamp": tr_noop("grimoire.spells.mural.motion", "Magic lamp"),
    "slide": tr_noop("grimoire.spells.mural.motion", "Slide"),
    "fadedesktop": tr_noop("grimoire.spells.mural.motion", "Fade"),
    None: tr_noop("grimoire.spells.mural.motion", "Off"),
}
PACE = {"design": (tr_noop("grimoire.spells.mural.motion", "As designed"), 1.0),
        "faster": (tr_noop("grimoire.spells.mural.motion", "A bit faster"), 0.7),
        "slower": (tr_noop("grimoire.spells.mural.motion", "A bit slower"), 1.4)}
DEFAULTS = {"blur": 8, "noise": 0, "wobbly": False, "pace": "design"}


def speed_of(pid: str, o: dict) -> float:
    """The animation duration factor: the design's, nudged by the Pace option (0 stays 0: no animations)."""
    o = {**DEFAULTS, **o}
    return round(PRESETS[pid]["speed"] * PACE.get(o["pace"], PACE["design"])[1], 2)


def _frame(p: QPainter, box: QRectF):
    p.setPen(QPen(QColor(46, 46, 46), 1))
    p.setBrush(QColor(14, 14, 14))
    p.drawRoundedRect(box, 4, 4)
    p.fillRect(QRectF(box.left() + 1, box.bottom() - 6, box.width() - 2, 5), QColor(34, 34, 34))   # taskbar


def _window(p: QPainter, r: QRectF, alpha: float):
    p.save()
    p.setOpacity(max(0.0, min(1.0, alpha)))
    p.setPen(QPen(QColor(210, 210, 210), 1))
    p.setBrush(QColor(236, 236, 236))
    p.drawRoundedRect(r, 2, 2)
    p.fillRect(QRectF(r.left(), r.top(), r.width(), max(2.0, r.height() * 0.14)), QColor(120, 120, 120))
    p.restore()


def _open_frame(p: QPainter, box: QRectF, effect, t: float):
    """One frame of a window opening (t 0..1) with this effect."""
    full = QRectF(box.left() + box.width() * 0.2, box.top() + box.height() * 0.16, box.width() * 0.6,
                  box.height() * 0.6)
    if effect is None:
        if t > 0:
            _window(p, full, 1)
    elif effect == "scale":
        k = 0.6 + 0.4 * t
        _window(p, QRectF(full.center().x() - full.width() * k / 2, full.center().y() - full.height() * k / 2,
                          full.width() * k, full.height() * k), t)
    elif effect == "glide":                       # tips forward from below: a trapezoid that straightens up
        lift = (1 - t) * full.height() * 0.35
        squeeze = (1 - t) * full.width() * 0.18
        path = QPainterPath(QPointF(full.left() + squeeze, full.top() + lift))
        path.lineTo(QPointF(full.right() - squeeze, full.top() + lift))
        path.lineTo(QPointF(full.right(), full.bottom()))
        path.lineTo(QPointF(full.left(), full.bottom()))
        path.closeSubpath()
        p.save()
        p.setOpacity(t)
        p.fillPath(path, QColor(236, 236, 236))
        p.restore()
    else:                                         # fade
        _window(p, full, t)


def _minimize_frame(p: QPainter, box: QRectF, effect, t: float):
    """One frame of a window minimizing (t 0..1) into the taskbar."""
    full = QRectF(box.left() + box.width() * 0.2, box.top() + box.height() * 0.16, box.width() * 0.6,
                  box.height() * 0.6)
    dock = QPointF(box.left() + box.width() * 0.3, box.bottom() - 4)
    if effect is None:
        if t < 1:
            _window(p, full, 1)
    elif effect == "squash":
        k = 1 - 0.9 * t
        c = QPointF(full.center().x() + (dock.x() - full.center().x()) * t,
                    full.center().y() + (dock.y() - full.center().y()) * t)
        _window(p, QRectF(c.x() - full.width() * k / 2, c.y() - full.height() * k / 2,
                          full.width() * k, full.height() * k), 1 - t * 0.6)
    else:                                         # magic lamp: the bottom pinches to the dock first
        fast = min(1.0, t * 2.2)
        bx = full.center().x() + (dock.x() - full.center().x()) * fast
        by = full.bottom() + (dock.y() - full.bottom()) * fast
        bh = full.width() / 2 * max(0.03, 1 - fast * 0.97)
        top = full.top() + (dock.y() - full.top()) * t ** 1.5
        tx = full.center().x() + (dock.x() - full.center().x()) * t
        th = full.width() / 2 * max(0.03, 1 - t * 0.97)
        mid = (top + by) / 2
        path = QPainterPath(QPointF(tx - th, top))
        path.lineTo(QPointF(tx + th, top))
        path.cubicTo(QPointF(tx + th, mid), QPointF(bx + bh, mid), QPointF(bx + bh, by))
        path.lineTo(QPointF(bx - bh, by))
        path.cubicTo(QPointF(bx - bh, mid), QPointF(tx - th, mid), QPointF(tx - th, top))
        p.fillPath(path, QColor(236, 236, 236))


def render(pid: str, o: dict, w=1280, h=720) -> QImage:
    o = {**DEFAULTS, **o}
    pr = PRESETS[pid]
    speed = speed_of(pid, o)
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(8, 8, 8))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.scale(w / 1280, h / 720)
    left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute     # the curve and strips run left to right

    if speed == 0:
        speed_label = tr("grimoire.spells.mural.motion", "instant")
    elif speed == 1:
        speed_label = tr("grimoire.spells.mural.motion", "normal speed")
    else:
        speed_label = tr("grimoire.spells.mural.motion", "{factor}× speed").format(factor=f"{1 / speed:.1f}")
    p.setPen(QColor(255, 255, 255))
    p.setFont(QFont("IBM Plex Sans", 30, QFont.Weight.Light))
    p.drawText(QRectF(70, 52, 560, 56), Qt.AlignmentFlag.AlignVCenter, speed_label)

    # easing curve: longer = slower; a corner = instant
    box = QRectF(70, 130, 540, 170)
    p.setPen(QPen(QColor(40, 40, 40), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(box)
    p.setPen(QPen(QColor(255, 255, 255), 2))
    if speed == 0:
        p.drawLine(QPointF(box.left(), box.bottom()), QPointF(box.left(), box.top()))
        p.drawLine(QPointF(box.left(), box.top()), QPointF(box.right(), box.top()))
    else:
        span = box.width() * min(1.0, speed / 2.0)
        path = QPainterPath(QPointF(box.left(), box.bottom()))
        path.cubicTo(QPointF(box.left() + span * 0.42, box.bottom()), QPointF(box.left() + span * 0.58, box.top()),
                     QPointF(box.left() + span, box.top()))
        path.lineTo(QPointF(box.right(), box.top()))
        p.drawPath(path)
    p.setPen(QColor(120, 120, 120))
    p.setFont(QFont("IBM Plex Sans", 10))
    p.drawText(QRectF(box.left(), box.bottom() + 8, box.width(), 20), left,
               tr("grimoire.spells.mural.motion", "time →"))

    # film strips: a window opening, a window minimizing
    strips = ((tr("grimoire.spells.mural.motion", "Opening a window"), _open_frame, pr["open"] if speed else None),
              (tr("grimoire.spells.mural.motion", "Minimizing"), _minimize_frame, pr["minimize"] if speed else None))
    for k, (title, draw, effect) in enumerate(strips):
        y = 360 + k * 150
        p.setPen(QColor(140, 140, 140))
        p.setFont(QFont("IBM Plex Sans", 12))
        p.drawText(QRectF(70, y, 540, 24), Qt.AlignmentFlag.AlignVCenter, title)
        for i in range(5):
            frame = QRectF(70 + i * 110, y + 32, 100, 66)
            _frame(p, frame)
            p.save()
            p.setClipRect(frame.adjusted(1, 1, -1, -1))
            draw(p, frame, effect, i / 4)
            p.restore()

    def on_off(on):
        return tr("grimoire.spells.mural.motion", "On") if on else tr("grimoire.spells.mural.motion", "Off")

    def effect(name):
        return tr("grimoire.spells.mural.motion", LABELS[name])

    if o["noise"]:
        blur = tr("grimoire.spells.mural.motion", "strength {blur}, grain {grain}")
    else:
        blur = tr("grimoire.spells.mural.motion", "strength {blur}")
    rows = [(tr("grimoire.spells.mural.motion", "Open / close"), effect(pr["open"]), pr["open"] is not None),
            (tr("grimoire.spells.mural.motion", "Minimize"), effect(pr["minimize"]), pr["minimize"] is not None),
            (tr("grimoire.spells.mural.motion", "Switch desktop"), effect(pr["switch"]), pr["switch"] is not None),
            (tr("grimoire.spells.mural.motion", "Closing breaks apart"), on_off(pr["fallapart"]), pr["fallapart"]),
            (tr("grimoire.spells.mural.motion", "Dialogs drop from their window"), on_off(pr["sheet"]), pr["sheet"]),
            (tr("grimoire.spells.mural.motion", "Dim inactive windows"), on_off(pr["diminactive"]),
             pr["diminactive"]),
            (tr("grimoire.spells.mural.motion", "Menus slide in"), on_off(pr["slidingpopups"]), pr["slidingpopups"]),
            (tr("grimoire.spells.mural.motion", "Wobbly windows"), on_off(o["wobbly"]), o["wobbly"]),
            (tr("grimoire.spells.mural.motion", "See-through while moving"), on_off(pr["translucent"]),
             pr["translucent"]),
            (tr("grimoire.spells.mural.motion", "Blur"), blur.format(blur=o["blur"], grain=o["noise"]), True)]
    for k, (name, value, on) in enumerate(rows):
        y = 70 + k * 56
        p.setPen(QColor(140, 140, 140))
        p.setFont(QFont("IBM Plex Sans", 13))
        p.drawText(QRectF(680, y, 330, 30), Qt.AlignmentFlag.AlignVCenter, name)
        pill = QRectF(1020, y + 2, 190, 28)
        pp = QPainterPath()
        pp.addRoundedRect(pill, 14, 14)
        p.fillPath(pp, QColor(240, 240, 240) if on else QColor(30, 30, 30))
        p.setPen(QColor(10, 10, 10) if on else QColor(110, 110, 110))
        p.setFont(QFont("IBM Plex Sans", 11))
        p.drawText(pill, Qt.AlignmentFlag.AlignCenter, value)
    p.end()
    return img


def _effect(name: str, on: bool):
    kwrite("kwinrc", "Plugins", f"{name}Enabled", "true" if on else "false")
    method = "loadEffect" if on else "unloadEffect"
    subprocess.run(["qdbus6", "org.kde.KWin", "/Effects", f"org.kde.kwin.Effects.{method}", name],
                   capture_output=True)


class MotionTab(ScreenTab):
    key = "motion"
    context = "grimoire.spells.mural.motion"
    subtitle = tr_noop("grimoire.spells.mural.motion", "How things move: animation speed and window effects. "
                       "Applies instantly.")
    apply_label = tr_noop("grimoire.spells.mural.motion", "Apply motion")

    def designs(self):
        return DESIGNS

    def build_options(self, lay):
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        self.pace = Choice([(k, tr("grimoire.spells.mural.motion", v[0])) for k, v in PACE.items()], self.changed)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.motion", "Pace")), 0, 0)
        grid.addWidget(self.pace, 0, 1)
        self.blur = Slider(1, 15, "", self.changed)
        self.noise = Slider(0, 14, "", self.changed)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.motion", "Blur")), 1, 0)
        grid.addWidget(self.blur, 1, 1)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.motion", "Grain")), 2, 0)
        grid.addWidget(self.noise, 2, 1)
        lay.addLayout(grid)
        self.wobbly = WrapCheck(tr("grimoire.spells.mural.motion", "Wobbly windows"))
        self.wobbly.toggled.connect(self.changed)
        lay.addWidget(self.wobbly)

    def options(self):
        return {"blur": self.blur.value(), "noise": self.noise.value(), "wobbly": self.wobbly.isChecked(),
                "pace": self.pace.value()}

    def set_options(self, o):
        o = {**DEFAULTS, **o}
        self.blur.setValue(o["blur"])
        self.noise.setValue(o["noise"])
        self.wobbly.setChecked(o["wobbly"])
        self.pace.set_value(o["pace"] if o["pace"] in PACE else "design")

    def preview(self, design, o):
        return render(design.id, o)

    def apply(self, design, o):
        pr = PRESETS[design.id]
        kwrite("kdeglobals", "KDE", "AnimationDurationFactor", speed_of(design.id, o), notify=True)
        for group, chosen in ((OPEN_CLOSE, pr["open"]), (MINIMIZE, pr["minimize"]), (SWITCH, pr["switch"])):
            for name in group:
                _effect(name, name == chosen)
        for name in EXTRAS:
            _effect(name, pr[name])
        _effect("wobblywindows", o["wobbly"])
        _effect("translucency", pr["translucent"])
        kwrite("kwinrc", "Effect-blur", "BlurStrength", o["blur"])
        kwrite("kwinrc", "Effect-blur", "NoiseStrength", o["noise"])
        _effect("blur", True)
        subprocess.run(["qdbus6", "org.kde.KWin", "/Effects", "org.kde.kwin.Effects.reconfigureEffect", "blur"],
                       capture_output=True)
        kwin_reconfigure()
        return tr("grimoire.spells.mural.motion", "Applied ✓")
