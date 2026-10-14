# SPDX-License-Identifier: GPL-3.0-or-later
"""Motion tab: animation speed + which KWin effects run (open/close, minimize, desktop switch,
wobbly windows, translucency, blur). Effects are loaded/unloaded live and saved to kwinrc.
"""
import subprocess

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import tr, tr_noop
from grimoire.spells.mural.kde import kwin_reconfigure, kwrite
from grimoire.spells.mural.screens import Design, ScreenTab, WrapCheck
from grimoire.widgets import Slider

# effect groups: only one of each group runs
OPEN_CLOSE = ["scale", "glide", "fade"]
MINIMIZE = ["squash", "magiclamp"]
SWITCH = ["slide", "fadedesktop"]
#             speed  open      minimize    switch          translucent-while-moving
PRESETS = {
    "still":  (0.0, None, None, None, False),
    "swift":  (0.5, "scale", "squash", "slide", False),
    "smooth": (1.0, "scale", "squash", "slide", False),
    "fluid":  (1.3, "glide", "magiclamp", "slide", False),
    "glass":  (1.0, "fade", "squash", "fadedesktop", True),
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
DEFAULTS = {"blur": 8, "noise": 0, "wobbly": False}


def render(pid: str, o: dict, w=1280, h=720) -> QImage:
    o = {**DEFAULTS, **o}
    speed, open_, mini, switch, translucent = PRESETS[pid]
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(8, 8, 8))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # easing curve: longer = slower; flat line = instant
    box = QRectF(90, 120, 520, 420)
    p.setPen(QPen(QColor(40, 40, 40), 1))
    p.drawRect(box)
    if speed == 0:
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawLine(QPointF(box.left(), box.bottom()), QPointF(box.left(), box.top()))
        p.drawLine(QPointF(box.left(), box.top()), QPointF(box.right(), box.top()))
    else:
        span = box.width() * min(1.0, speed / 1.4)
        path = QPainterPath(QPointF(box.left(), box.bottom()))
        path.cubicTo(QPointF(box.left() + span * 0.42, box.bottom()), QPointF(box.left() + span * 0.58, box.top()),
                     QPointF(box.left() + span, box.top()))
        path.lineTo(QPointF(box.right(), box.top()))
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawPath(path)
    p.setPen(QColor(120, 120, 120))
    p.setFont(QFont("IBM Plex Sans", 10))
    p.drawText(QRectF(box.left(), box.bottom() + 12, box.width(), 20),     # the curve runs left to right
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute,
               tr("grimoire.spells.mural.motion", "time →"))
    if speed == 0:
        speed_label = tr("grimoire.spells.mural.motion", "instant")
    elif speed == 1:
        speed_label = tr("grimoire.spells.mural.motion", "normal speed")
    else:
        speed_label = tr("grimoire.spells.mural.motion", "{factor}× speed").format(factor=f"{1 / speed:.1f}")
    p.setPen(QColor(255, 255, 255))
    p.setFont(QFont("IBM Plex Sans", 30, QFont.Weight.Light))
    p.drawText(QRectF(680, 120, 520, 50), Qt.AlignmentFlag.AlignLeft, speed_label)

    def on_off(on):
        return tr("grimoire.spells.mural.motion", "On") if on else tr("grimoire.spells.mural.motion", "Off")

    def effect(name):
        return tr("grimoire.spells.mural.motion", LABELS[name])

    if o["noise"]:
        blur = tr("grimoire.spells.mural.motion", "strength {blur}, grain {grain}")
    else:
        blur = tr("grimoire.spells.mural.motion", "strength {blur}")
    rows = [(tr("grimoire.spells.mural.motion", "Open / close"), effect(open_), open_ is not None),
            (tr("grimoire.spells.mural.motion", "Minimize"), effect(mini), mini is not None),
            (tr("grimoire.spells.mural.motion", "Switch desktop"), effect(switch), switch is not None),
            (tr("grimoire.spells.mural.motion", "Wobbly windows"), on_off(o["wobbly"]), o["wobbly"]),
            (tr("grimoire.spells.mural.motion", "See-through while moving"), on_off(translucent), translucent),
            (tr("grimoire.spells.mural.motion", "Blur"), blur.format(blur=o["blur"], grain=o["noise"]), True)]
    for k, (name, value, on) in enumerate(rows):
        y = 210 + k * 52
        p.setPen(QColor(140, 140, 140))
        p.setFont(QFont("IBM Plex Sans", 13))
        p.drawText(QRectF(680, y, 300, 30), Qt.AlignmentFlag.AlignVCenter, name)
        pill = QRectF(990, y + 2, 170, 28)
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
        self.blur = Slider(1, 15, "", self.changed)
        self.noise = Slider(0, 14, "", self.changed)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.motion", "Blur")), 0, 0)
        grid.addWidget(self.blur, 0, 1)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.motion", "Grain")), 1, 0)
        grid.addWidget(self.noise, 1, 1)
        lay.addLayout(grid)
        self.wobbly = WrapCheck(tr("grimoire.spells.mural.motion", "Wobbly windows"))
        self.wobbly.toggled.connect(self.changed)
        lay.addWidget(self.wobbly)

    def options(self):
        return {"blur": self.blur.value(), "noise": self.noise.value(), "wobbly": self.wobbly.isChecked()}

    def set_options(self, o):
        o = {**DEFAULTS, **o}
        self.blur.setValue(o["blur"])
        self.noise.setValue(o["noise"])
        self.wobbly.setChecked(o["wobbly"])

    def preview(self, design, o):
        return render(design.id, o)

    def apply(self, design, o):
        speed, open_, mini, switch, translucent = PRESETS[design.id]
        kwrite("kdeglobals", "KDE", "AnimationDurationFactor", speed, notify=True)
        for group, chosen in ((OPEN_CLOSE, open_), (MINIMIZE, mini), (SWITCH, switch)):
            for name in group:
                _effect(name, name == chosen)
        _effect("wobblywindows", o["wobbly"])
        _effect("translucency", translucent)
        kwrite("kwinrc", "Effect-blur", "BlurStrength", o["blur"])
        kwrite("kwinrc", "Effect-blur", "NoiseStrength", o["noise"])
        _effect("blur", True)
        subprocess.run(["qdbus6", "org.kde.KWin", "/Effects", "org.kde.kwin.Effects.reconfigureEffect", "blur"],
                       capture_output=True)
        kwin_reconfigure()
        return tr("grimoire.spells.mural.motion", "Applied ✓")
