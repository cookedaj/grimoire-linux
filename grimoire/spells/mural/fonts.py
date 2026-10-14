# SPDX-License-Identifier: GPL-3.0-or-later
"""Fonts tab: a system font pairing (interface + monospace), size, title weight, hinting, sub-pixel.
Written to kdeglobals with --notify, so running KDE apps update immediately.
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import tr, tr_noop
from grimoire.spells.mural.backdrop import wallpaper
from grimoire.spells.mural.kde import kwin_reconfigure, kwrite
from grimoire.spells.mural.screens import Choice, Design, ScreenTab
from grimoire.widgets import Slider

PAIRS = {
    "swiss":     ("Nimbus Sans", "DM Mono"),
}
DESIGNS = [
    Design("swiss", tr_noop("grimoire.spells.mural.fonts", "Swiss"),
           tr_noop("grimoire.spells.mural.fonts",
                   "Nimbus Sans (a Helvetica design) + DM Mono. Classic poster typography.")),
]
HINTING = {tr_noop("grimoire.spells.mural.fonts", "None"): "hintnone",
           tr_noop("grimoire.spells.mural.fonts", "Slight"): "hintslight",
           tr_noop("grimoire.spells.mural.fonts", "Full"): "hintfull"}
WEIGHTS = [tr_noop("grimoire.spells.mural.fonts", "Bold"), tr_noop("grimoire.spells.mural.fonts", "Regular")]
SUBPIXEL = [tr_noop("grimoire.spells.mural.fonts", "On"), tr_noop("grimoire.spells.mural.fonts", "Off")]
DEFAULTS = {"size": 10, "title_weight": "Bold", "hinting": "Slight", "subpixel": "On"}


def qfont_string(family: str, size: int, weight: int = 400) -> str:
    """Qt 6 font description string as KDE stores it."""
    return f"{family},{size},-1,5,{weight},0,0,0,0,0,0,0,0,0,0,1"


def render(pid: str, o: dict, w=1280, h=720) -> QImage:
    o = {**DEFAULTS, **o}
    sans, mono = PAIRS[pid]
    img = wallpaper(w, h).copy()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.fillRect(img.rect(), QColor(0, 0, 0, 150))
    card = QRectF(w * 0.1, h * 0.1, w * 0.8, h * 0.8)
    path = QPainterPath()
    path.addRoundedRect(card, 12, 12)
    p.fillPath(path, QColor(12, 12, 12, 240))
    s = o["size"] / 10

    def text(rect, family, px, weight, color, value, flags=Qt.AlignmentFlag.AlignLeft):
        f = QFont(family)
        f.setPixelSize(int(px))
        f.setWeight(weight)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(rect, flags | Qt.TextFlag.TextWordWrap, value)

    x, wd = card.x() + 48, card.width() - 96
    title_w = QFont.Weight.Bold if o["title_weight"] == "Bold" else QFont.Weight.Normal
    p.fillRect(QRectF(card.x(), card.y(), card.width(), 40), QColor(20, 20, 20))
    text(QRectF(card.x(), card.y() + 10, card.width(), 24), sans, 13 * s, title_w, "#e8e8e8",
         "Grimoire — MuraL", Qt.AlignmentFlag.AlignHCenter)
    text(QRectF(x, card.y() + 70, wd, 70), sans, 46 * s, QFont.Weight.Light, "#ffffff", sans)
    text(QRectF(x, card.y() + 70 + 64 * s, wd, 30), sans, 14 * s, QFont.Weight.Normal, "#8c8c8c",
         tr("grimoire.spells.mural.fonts", "Interface font  ·  {size} pt  ·  monospace: {mono}")
         .format(size=o["size"], mono=mono))
    text(QRectF(x, card.y() + 140 + 64 * s, wd, 110), sans, 17 * s, QFont.Weight.Normal, "#d8d8d8",
         "The five-leaf grimoire chose the boy with no magic. Asta trained until his hands bled, "
         "and Yuno never stopped chasing the crown. Surpass your limits, right here, right now.")
    code = QRectF(x, card.y() + 270 + 80 * s, wd, 96 * s + 20)
    cp = QPainterPath()
    cp.addRoundedRect(code, 8, 8)
    p.fillPath(cp, QColor(0, 0, 0))
    text(code.adjusted(18, 14, -18, 0), mono, 14 * s, QFont.Weight.Normal, "#cfcfcf",
         "$ grimoire-sightc on\n$ git commit -m \"surpass your limits\"\n0123456789  {}[]()<>=!  il1| O0")
    text(QRectF(x, card.bottom() - 40, wd, 24), sans, 11 * s, QFont.Weight.Normal, "#6f6f6f",
         tr("grimoire.spells.mural.fonts", "SMALL TEXT · MENUS · TOOLBARS") + " · 0123456789")
    p.end()
    return img


class FontsTab(ScreenTab):
    key = "fonts"
    context = "grimoire.spells.mural.fonts"
    subtitle = tr_noop("grimoire.spells.mural.fonts", "System fonts for every app, menu and title bar. "
                       "Running KDE apps update immediately.")
    apply_label = tr_noop("grimoire.spells.mural.fonts", "Apply fonts")

    def designs(self):
        return DESIGNS

    def build_options(self, lay):
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        self.size = Slider(8, 14, " pt", self.changed)
        self.title_weight = Choice([(k, tr("grimoire.spells.mural.fonts", k)) for k in WEIGHTS], self.changed)
        self.hinting = Choice([(k, tr("grimoire.spells.mural.fonts", k)) for k in HINTING], self.changed)
        self.subpixel = Choice([(k, tr("grimoire.spells.mural.fonts", k)) for k in SUBPIXEL], self.changed)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.fonts", "Size")), 0, 0)
        grid.addWidget(self.size, 0, 1)
        for r, (name, c) in enumerate(((tr("grimoire.spells.mural.fonts", "Title bars"), self.title_weight),
                                       (tr("grimoire.spells.mural.fonts", "Hinting"), self.hinting),
                                       (tr("grimoire.spells.mural.fonts", "Sub-pixel"), self.subpixel)), start=1):
            grid.addWidget(QLabel(name), r, 0)
            grid.addWidget(c, r, 1)
        lay.addLayout(grid)

    def options(self):
        return {"size": self.size.value(), "title_weight": self.title_weight.value(),
                "hinting": self.hinting.value(), "subpixel": self.subpixel.value()}

    def set_options(self, o):
        o = {**DEFAULTS, **o}
        self.size.setValue(o["size"])
        self.title_weight.set_value(o["title_weight"])
        self.hinting.set_value(o["hinting"])
        self.subpixel.set_value(o["subpixel"])

    def preview(self, design, o):
        return render(design.id, o)

    def apply(self, design, o):
        sans, mono = PAIRS[design.id]
        size = o["size"]
        writes = [
            ("General", "font", qfont_string(sans, size)),
            ("General", "menuFont", qfont_string(sans, size)),
            ("General", "toolBarFont", qfont_string(sans, max(8, size - 1))),
            ("General", "smallestReadableFont", qfont_string(sans, max(7, size - 2))),
            ("General", "fixed", qfont_string(mono, size)),
            ("WM", "activeFont", qfont_string(sans, size, 700 if o["title_weight"] == "Bold" else 400)),
            ("General", "XftAntialias", "true"),
            ("General", "XftHintStyle", HINTING[o["hinting"]]),
            ("General", "XftSubPixel", "rgb" if o["subpixel"] == "On" else "none"),
        ]
        for group, key, value in writes:
            kwrite("kdeglobals", group, key, value, notify=True)
        kwin_reconfigure()
        return tr("grimoire.spells.mural.fonts", "Applied ✓  Some apps pick up new fonts when reopened.")
