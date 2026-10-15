# SPDX-License-Identifier: GPL-3.0-or-later
"""Taskbar tab: the panel's layout (where it sits, how long it is, how it's aligned) + a black & white look (a generated Plasma Style, see plasmastyle.py),
height, opacity, floating and auto-hide.

Layout properties go through plasmashell scripting; opacity is only read from plasmashellrc at startup,
so changing it restarts plasmashell (a one-second blink). The panel's widgets are left alone.
The original panel + Plasma Style are recorded on the first apply so "Restore" can put them back.
"""
import json
import subprocess
import time

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import tr, tr_noop
from grimoire.paths import ASSETS, DATA
from grimoire.spells.mural import plasmastyle
from grimoire.spells.mural.backdrop import wallpaper as _wallpaper
from grimoire.spells.mural.kde import kread, kwrite, plasma_script
from grimoire.spells.mural.screens import Choice, Design, ScreenTab, WrapButton, WrapCheck
from grimoire.widgets import Slider

ORIGINAL = DATA / "mural" / "taskbar-original.json"
PROPS = ("location", "height", "floating", "hiding", "alignment", "lengthMode", "opacity")
OPACITY = {tr_noop("grimoire.spells.mural.taskbar", "Adaptive"): 0,          # plasmashellrc panelOpacity values
           tr_noop("grimoire.spells.mural.taskbar", "Opaque"): 1,
           tr_noop("grimoire.spells.mural.taskbar", "Translucent"): 2}
OPACITY_NAMES = {"adaptive": 0, "opaque": 1, "translucent": 2}
KEEP = tr_noop("grimoire.spells.mural.taskbar", "Keep current")
LOOK_NAMES = {KEEP: None, **{look.name: key for key, look in plasmastyle.LOOKS.items()}}
DEFAULTS = {"height": 46, "opacity": "Adaptive", "floating": True, "autohide": False, "look": "Onyx"}

# ids never change once added (saved looks and shared setups use them)
#              id          location  lengthMode alignment
LAYOUTS = {
    "dock":       ("bottom", "fit", "center"),
    "bar":        ("bottom", "fill", "center"),
    "corner":     ("bottom", "fit", "left"),
    "top":        ("top", "fill", "center"),
    "top-dock":   ("top", "fit", "center"),
    "side":       ("left", "fill", "center"),
    "side-dock":  ("left", "fit", "center"),
    "right":      ("right", "fill", "center"),
    "right-dock": ("right", "fit", "center"),
}
DESIGNS = [
    Design("dock", tr_noop("grimoire.spells.mural.taskbar", "Dock"), tr_noop(
        "grimoire.spells.mural.taskbar", "Only as wide as its contents, centered at the bottom. The modern look.")),
    Design("bar", tr_noop("grimoire.spells.mural.taskbar", "Classic bar"), tr_noop(
        "grimoire.spells.mural.taskbar", "Edge to edge along the bottom, the familiar desktop taskbar.")),
    Design("corner", tr_noop("grimoire.spells.mural.taskbar", "Corner"), tr_noop(
        "grimoire.spells.mural.taskbar", "Fits its contents and sits in the bottom-left corner, out of the way.")),
    Design("top", tr_noop("grimoire.spells.mural.taskbar", "Top bar"), tr_noop(
        "grimoire.spells.mural.taskbar", "Edge to edge along the top of the screen.")),
    Design("top-dock", tr_noop("grimoire.spells.mural.taskbar", "Top dock"), tr_noop(
        "grimoire.spells.mural.taskbar", "Only as wide as its contents, centered at the top.")),
    Design("side", tr_noop("grimoire.spells.mural.taskbar", "Sidebar"), tr_noop(
        "grimoire.spells.mural.taskbar", "Full height down the left edge. Leaves wide screens more room to read.")),
    Design("side-dock", tr_noop("grimoire.spells.mural.taskbar", "Side dock"), tr_noop(
        "grimoire.spells.mural.taskbar", "Only as tall as its contents, centered on the left edge.")),
    Design("right", tr_noop("grimoire.spells.mural.taskbar", "Right sidebar"), tr_noop(
        "grimoire.spells.mural.taskbar", "Full height down the right edge.")),
    Design("right-dock", tr_noop("grimoire.spells.mural.taskbar", "Right dock"), tr_noop(
        "grimoire.spells.mural.taskbar", "Only as tall as its contents, centered on the right edge.")),
]


def _plasma(script: str) -> str:
    r = plasma_script(script)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or tr("grimoire.spells.mural.taskbar", "plasmashell refused the script"))
    return r.stdout.strip()


def read_panel() -> dict:
    out = _plasma("var p = panels()[0]; print(JSON.stringify({" +
                  ", ".join(f"{k}: p.{k}" for k in PROPS) + "}));")
    return json.loads(out)


def write_panel(props: dict):
    sets = "".join(f" p.{k} = {json.dumps(v)};" for k, v in props.items())
    _plasma(f"var p = panels()[0];{sets}")


def _panel_groups() -> list[str]:
    """The first panel's group in plasmashellrc."""
    return ["PlasmaViews", f"Panel {_plasma('print(panels()[0].id)')}"]


def set_opacity(value: int):
    """Opacity is only read at startup: write it and restart plasmashell, but only if it changed."""
    groups = _panel_groups()
    if kread("plasmashellrc", groups, "panelOpacity", default="0") == str(value):
        return
    kwrite("plasmashellrc", groups, "panelOpacity", value)
    subprocess.run(["systemctl", "--user", "restart", "plasma-plasmashell"], check=True)
    for _ in range(40):                        # wait until plasmashell answers again
        if subprocess.run(["qdbus6", "org.kde.plasmashell", "/PlasmaShell"], capture_output=True).returncode == 0:
            break
        time.sleep(0.25)


def _glyph(size: int, color: QColor) -> QImage:
    """The white clover launcher icon, recolored (dark on light looks)."""
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    QSvgRenderer(str(ASSETS / "clover5.svg")).render(p)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(img.rect(), color)
    p.end()
    return img


def panel_rect(loc: str, length: str, align: str, thick: float, content: float, gap: float, w: int, h: int) -> QRectF:
    vertical = loc in ("left", "right")
    edge = h if vertical else w
    span = edge - 2 * gap if length == "fill" else min(edge - 2 * gap, content)
    start = {"left": gap, "center": (edge - span) / 2, "right": edge - span - gap}[align]
    if vertical:
        return QRectF(gap if loc == "left" else w - thick - gap, start, thick, span)
    return QRectF(start, gap if loc == "top" else h - thick - gap, span, thick)


def draw_panel(p: QPainter, rect: QRectF, vertical: bool, look, o: dict, s: float, radius: float):
    """The panel itself: background (with the look's hairline border) and its contents."""
    thick = rect.width() if vertical else rect.height()
    fill = QColor(look.fill) if look else QColor(32, 35, 38)
    base_alpha = look.fill_opacity if look else 0.95
    alpha = {"Opaque": 1.0, "Translucent": 0.6, "Adaptive": 0.85}[o["opacity"]] * base_alpha
    if o["opacity"] == "Opaque":
        alpha = 1.0
    fill.setAlphaF(alpha)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    p.fillPath(path, fill)
    if look and look.stroke_opacity > 0 and look.stroke_width:
        line = QColor(look.stroke)
        line.setAlphaF(look.stroke_opacity)
        width = max(1.0, look.stroke_width * s * 2)
        inner = QPainterPath()
        inner.addRoundedRect(rect.adjusted(width / 2, width / 2, -width / 2, -width / 2), radius, radius)
        p.strokePath(inner, QPen(line, width))

    light = look is not None and look.light
    ink = QColor(24, 24, 24) if light else QColor(232, 232, 232)
    icon = thick * 0.56
    pad = thick * 0.28

    def slot(k):                                        # the k-th icon slot along the panel
        if vertical:
            return QRectF(rect.x() + (thick - icon) / 2, rect.y() + pad + k * (icon + pad), icon, icon)
        return QRectF(rect.x() + pad + k * (icon + pad), rect.y() + (thick - icon) / 2, icon, icon)

    launcher = slot(0).adjusted(icon * .12, icon * .12, -icon * .12, -icon * .12)
    p.drawImage(launcher, _glyph(max(8, int(launcher.width() * 2)), ink))
    p.setPen(Qt.PenStyle.NoPen)
    for k in range(N_TASKS):
        r = slot(k + 1.4)
        shade = (40 if k == 1 else 120) if light else (225 if k == 1 else 120)
        p.setBrush(QColor(shade, shade, shade, 230))
        p.drawRoundedRect(r, icon * 0.24, icon * 0.24)
    active = slot(2.4)                                  # running-indicator under the active task
    p.setBrush(ink)
    if vertical:
        x = rect.x() + 2 * s if rect.center().x() < p.device().width() / 2 else rect.right() - 5 * s
        p.drawRoundedRect(QRectF(x, active.center().y() - icon * .25, 3 * s, icon * .5), 1, 1)
    else:
        y = rect.bottom() - 4 * s if rect.center().y() > p.device().height() / 2 else rect.y() + 1 * s
        p.drawRoundedRect(QRectF(active.center().x() - icon * .25, y, icon * .5, 3 * s), 1, 1)
    p.setFont(QFont("IBM Plex Sans", max(6, int(thick * 0.26))))
    tray = QColor(110, 110, 110) if light else QColor(170, 170, 170)
    if vertical:
        clock = QRectF(rect.x(), rect.bottom() - thick, thick, thick)
        p.setPen(ink)
        p.drawText(clock, Qt.AlignmentFlag.AlignCenter, "2:45")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tray)
        for k in range(3):
            p.drawEllipse(QRectF(rect.center().x() - icon * .16, clock.y() - (k + 1) * icon * 0.75, icon * .32,
                                 icon * .32))
    else:
        clock = QRectF(rect.right() - pad - CLOCK * s, rect.y(), CLOCK * s, thick)
        p.setPen(ink)
        p.drawText(clock, Qt.AlignmentFlag.AlignCenter, "2:45")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tray)
        for k in range(3):                              # tray
            p.drawEllipse(QRectF(clock.x() - (k + 1) * icon * 0.75, rect.center().y() - icon * .16, icon * .32,
                                 icon * .32))


N_TASKS = 6
CLOCK = 70                                              # clock width at full scale


def render(design_id: str, o: dict, w=1280, h=720) -> QImage:
    o = {**DEFAULTS, **o}
    loc, length, align = LAYOUTS[design_id]
    s = w / 2560                                       # preview scale vs your 2560x1440 screen
    img = _wallpaper(w, h).copy()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.fillRect(img.rect(), QColor(0, 0, 0, 70))         # a touch darker so the panel reads

    thick = o["height"] * s
    gap = 8 * s if o["floating"] else 0
    vertical = loc in ("left", "right")
    icon, pad = thick * 0.56, thick * 0.28
    tray = icon * 0.75 * 3 + (thick if vertical else CLOCK * s)
    content = pad * 2 + icon * (N_TASKS + 3) + pad * (N_TASKS + 2) + tray
    rect = panel_rect(loc, length, align, thick, content, gap, w, h)
    look = plasmastyle.LOOKS.get(LOOK_NAMES.get(o["look"]) or "", None)
    radius = (look.radius if look else 8) * s * 2 if o["floating"] else 0   # Plasma squares a docked panel
    if o["autohide"]:
        p.setOpacity(0.45)
    draw_panel(p, rect, vertical, look, o, s, min(radius, thick / 2))
    if o["autohide"]:
        p.setOpacity(1)
        p.setPen(QColor(255, 255, 255, 160))
        p.setFont(QFont("IBM Plex Sans", 10))
        if vertical:
            note = (QRectF(rect.right() + 12, h / 2 - 11, 260, 22) if loc == "left"
                    else QRectF(rect.x() - 272, h / 2 - 11, 260, 22))
            flag = Qt.AlignmentFlag.AlignLeft if loc == "left" else Qt.AlignmentFlag.AlignRight
        else:
            note = QRectF(0, rect.y() - 30 if loc != "top" else rect.bottom() + 8, w, 22)
            flag = Qt.AlignmentFlag.AlignHCenter
        p.drawText(note, flag | Qt.AlignmentFlag.AlignVCenter,
                   tr("grimoire.spells.mural.taskbar", "hides until you touch the edge"))
    p.end()
    return img


class TaskbarTab(ScreenTab):
    key = "taskbar"
    context = "grimoire.spells.mural.taskbar"
    subtitle = tr_noop("grimoire.spells.mural.taskbar", "Your Plasma taskbar. Changes apply instantly; the first apply "
                       "records your original panel so you can restore it.")
    apply_label = tr_noop("grimoire.spells.mural.taskbar", "Apply to taskbar")

    def designs(self):
        return DESIGNS

    def build_options(self, lay):
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        self.height_ = Slider(28, 80, " px", self.changed)
        # Plasma Style names are Style-tab design names: shown in that tab's words
        looks = [(k, tr("grimoire.spells.mural.taskbar", KEEP) if k == KEEP else tr("grimoire.spells.mural.style", k))
                 for k in LOOK_NAMES]
        self.look = Choice(looks, self.changed)
        self.look.setToolTip(tr("grimoire.spells.mural.taskbar", "The panel's look (also popups and tooltips): "
                                "a black & white Plasma Style"))
        self.opacity = Choice([(k, tr("grimoire.spells.mural.taskbar", k)) for k in OPACITY], self.changed)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.taskbar", "Look")), 0, 0)
        grid.addWidget(self.look, 0, 1)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.taskbar", "Height")), 1, 0)
        grid.addWidget(self.height_, 1, 1)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.taskbar", "Opacity")), 2, 0)
        grid.addWidget(self.opacity, 2, 1)
        lay.addLayout(grid)
        self.floating = WrapCheck(tr("grimoire.spells.mural.taskbar", "Floating (gap + rounded corners)"))
        self.autohide = WrapCheck(tr("grimoire.spells.mural.taskbar", "Auto-hide"))
        for c in (self.floating, self.autohide):
            c.toggled.connect(self.changed)
            lay.addWidget(c)
        lay.addSpacing(6)
        restore = WrapButton(tr("grimoire.spells.mural.taskbar", "Restore original taskbar"))
        restore.clicked.connect(self._restore)
        lay.addWidget(restore)

    def options(self):
        return {"look": self.look.value(), "height": self.height_.value(), "opacity": self.opacity.value(),
                "floating": self.floating.isChecked(), "autohide": self.autohide.isChecked()}

    def set_options(self, o):
        o = {**DEFAULTS, **o}
        self.look.set_value(o["look"])
        self.height_.setValue(o["height"])
        self.opacity.set_value(o["opacity"])
        self.floating.setChecked(o["floating"])
        self.autohide.setChecked(o["autohide"])

    def preview(self, design, o):
        return render(design.id, o)

    def thumbnail(self, design, o):
        """Cards zoom in on the panel's edge of the screen (it's thin at real scale)."""
        img = render(design.id, o, 2560, 1440)
        loc, length, align = LAYOUTS[design.id]
        along = 0 if length == "fill" else {"left": 0, "center": 1, "right": 2}[align]   # where its contents start
        x, y = {"bottom": (853 * along, 960), "top": (853 * along, 0), "left": (0, 480 * along),
                "right": (1707, 480 * along)}[loc]
        return img.copy(x, y, 853, 480)

    def apply(self, design, o):
        if not ORIGINAL.exists():
            ORIGINAL.parent.mkdir(parents=True, exist_ok=True)
            original = read_panel()
            original["opacity"] = OPACITY_NAMES.get(str(original.get("opacity")), 0)
            style = plasmastyle.current()
            original["style"] = style if not style.startswith("grimoire") else "default"   # ours gets rebuilt
            ORIGINAL.write_text(json.dumps(original, indent=2))
        set_opacity(OPACITY[o["opacity"]])     # may restart plasmashell, so it goes first
        loc, length, align = LAYOUTS[design.id]
        write_panel({"location": loc, "lengthMode": length, "alignment": align, "height": o["height"],
                     "floating": o["floating"], "hiding": "autohide" if o["autohide"] else "none"})
        look = LOOK_NAMES.get(o["look"])
        if look:
            plasmastyle.apply(look)
        return tr("grimoire.spells.mural.taskbar", "Applied ✓  (Floating panels go flat while a window is maximized; "
                  "that's Plasma.)")

    def _restore(self):
        if not ORIGINAL.exists():
            self.status.setText(tr("grimoire.spells.mural.taskbar", "Nothing to restore — the taskbar hasn't been "
                                   "changed by MuraL."))
            return

        def work():                             # may restart plasmashell, so it runs off the UI thread
            original = json.loads(ORIGINAL.read_text())
            style = original.pop("style", None)
            opacity = original.pop("opacity", 0)
            set_opacity(opacity if isinstance(opacity, int) else OPACITY_NAMES.get(opacity, 0))
            write_panel(original)
            if style and subprocess.run(["plasma-apply-desktoptheme", style], capture_output=True).returncode:
                return tr("grimoire.spells.mural.taskbar", "Taskbar restored, but the “{style}” Plasma style is "
                          "gone; pick one in Style.").format(style=style)
            return tr("grimoire.spells.mural.taskbar", "Original taskbar restored.")
        self.background(work, tr("grimoire.spells.mural.taskbar", "Restoring…"))
