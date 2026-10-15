# SPDX-License-Identifier: GPL-3.0-or-later
"""Fonts tab: a system font pairing (interface + monospace, some with their own title-bar face), size, title weight,
hinting, sub-pixel. Written to kdeglobals with --notify, so running KDE apps update immediately.

Pairings only use fonts already on the system. One that needs a font that isn't installed says which Ubuntu
package has it (installing needs sudo, so we show the command and never download anything ourselves).
"""
import subprocess
from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import ltr, tr, tr_noop
from grimoire.spells.mural.backdrop import wallpaper
from grimoire.spells.mural.kde import kwin_reconfigure, kwrite
from grimoire.spells.mural.screens import Choice, Design, ScreenTab, WrapButton
from grimoire.widgets import Slider



@dataclass(frozen=True)
class Pair:
    """Each role lists families best first; the first one installed is used. packages: where the first choices
    come from, for the install hint when none of a role's families is installed."""
    sans: tuple
    mono: tuple
    title: tuple = ()                                   # () = the interface font
    packages: tuple = ()


PAIRS = {            # ids never change: saved looks and shared setups name them
    "swiss": Pair(("Nimbus Sans",), ("DM Mono", "IBM Plex Mono"), packages=("fonts-urw-base35",)),
    "plex": Pair(("IBM Plex Sans",), ("IBM Plex Mono",), packages=("fonts-ibm-plex",)),
    "editorial": Pair(("IBM Plex Sans",), ("IBM Plex Mono",), ("IBM Plex Serif",), ("fonts-ibm-plex",)),
    "condensed": Pair(("IBM Plex Sans Condensed",), ("IBM Plex Mono",), packages=("fonts-ibm-plex",)),
    "ubuntu": Pair(("Ubuntu Sans", "Ubuntu"), ("Ubuntu Sans Mono", "Ubuntu Mono"), packages=("fonts-ubuntu",)),
    "noto": Pair(("Noto Sans",), ("Noto Sans Mono", "Noto Mono"), packages=("fonts-noto-core", "fonts-noto-mono")),
    "workshop": Pair(("DejaVu Sans",), ("Hack", "DejaVu Sans Mono"), packages=("fonts-dejavu-core", "fonts-hack")),
    "office": Pair(("Liberation Sans",), ("Liberation Mono",), packages=("fonts-liberation",)),
    "bauhaus": Pair(("URW Gothic",), ("Nimbus Mono PS",), packages=("fonts-urw-base35",)),
    "typewriter": Pair(("IBM Plex Mono",), ("IBM Plex Mono",), packages=("fonts-ibm-plex",)),
    "modern": Pair(("Inter",), ("JetBrains Mono",), packages=("fonts-inter", "fonts-jetbrains-mono")),
    "studio": Pair(("Cantarell",), ("Fira Code",), packages=("fonts-cantarell", "fonts-firacode")),
}
DESIGNS = [
    Design("swiss", tr_noop("grimoire.spells.mural.fonts", "Swiss"),
           tr_noop("grimoire.spells.mural.fonts",
                   "Nimbus Sans (a Helvetica design) + DM Mono, or IBM Plex Mono without it. "
                   "Classic poster typography.")),
    Design("plex", tr_noop("grimoire.spells.mural.fonts", "Grimoire"),
           tr_noop("grimoire.spells.mural.fonts",
                   "IBM Plex Sans + IBM Plex Mono: the typeface Grimoire itself is set in. Crisp and engineered.")),
    Design("editorial", tr_noop("grimoire.spells.mural.fonts", "Editorial"),
           tr_noop("grimoire.spells.mural.fonts",
                   "IBM Plex Sans, with IBM Plex Serif on title bars like a magazine headline.")),
    Design("condensed", tr_noop("grimoire.spells.mural.fonts", "Condensed"),
           tr_noop("grimoire.spells.mural.fonts",
                   "IBM Plex Sans Condensed: narrow letters fit more into menus, tabs and file names.")),
    Design("ubuntu", tr_noop("grimoire.spells.mural.fonts", "Ubuntu"),
           tr_noop("grimoire.spells.mural.fonts",
                   "Ubuntu Sans + Ubuntu Sans Mono. Friendly, rounded and very readable.")),
    Design("noto", tr_noop("grimoire.spells.mural.fonts", "Noto"),
           tr_noop("grimoire.spells.mural.fonts",
                   "Noto Sans + Noto Sans Mono: one calm design for every language and script.")),
    Design("workshop", tr_noop("grimoire.spells.mural.fonts", "Workshop"),
           tr_noop("grimoire.spells.mural.fonts",
                   "DejaVu Sans + Hack. Wide, sturdy letters that stay clear at small sizes.")),
    Design("office", tr_noop("grimoire.spells.mural.fonts", "Office"),
           tr_noop("grimoire.spells.mural.fonts",
                   "Liberation Sans + Liberation Mono: the same widths as Arial and Courier New, so documents "
                   "line up.")),
    Design("bauhaus", tr_noop("grimoire.spells.mural.fonts", "Bauhaus"),
           tr_noop("grimoire.spells.mural.fonts",
                   "URW Gothic (an Avant Garde design) + Nimbus Mono PS. Geometric circles and straight lines.")),
    Design("typewriter", tr_noop("grimoire.spells.mural.fonts", "Typewriter"),
           tr_noop("grimoire.spells.mural.fonts",
                   "IBM Plex Mono everywhere, menus included. Every letter the same width.")),
    Design("modern", tr_noop("grimoire.spells.mural.fonts", "Modern"),
           tr_noop("grimoire.spells.mural.fonts",
                   "Inter + JetBrains Mono, the clean pair many apps and code editors use.")),
    Design("studio", tr_noop("grimoire.spells.mural.fonts", "Studio"),
           tr_noop("grimoire.spells.mural.fonts",
                   "Cantarell + Fira Code: soft humanist letters with a coding font that joins => and !=.")),
]
HINTING = {tr_noop("grimoire.spells.mural.fonts", "None"): "hintnone",
           tr_noop("grimoire.spells.mural.fonts", "Slight"): "hintslight",
           tr_noop("grimoire.spells.mural.fonts", "Full"): "hintfull"}
WEIGHTS = [tr_noop("grimoire.spells.mural.fonts", "Bold"), tr_noop("grimoire.spells.mural.fonts", "Regular")]
SUBPIXEL = [tr_noop("grimoire.spells.mural.fonts", "On"), tr_noop("grimoire.spells.mural.fonts", "Off")]
DEFAULTS = {"size": 10, "title_weight": "Bold", "hinting": "Slight", "subpixel": "On"}


@lru_cache(maxsize=1)
def families() -> frozenset:
    """Every font family fontconfig knows (each alias of a family counts)."""
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return frozenset()
    return frozenset(name.strip() for line in out.splitlines() for name in line.split(","))


def installed(family: str) -> bool:
    return family in families()


def resolve(pid: str) -> tuple[str, str, str, list[str]]:
    """(interface, monospace, title, packages to install) for a pairing: the first installed family of each role,
    else its first choice (shown with a "not installed" note)."""
    pair = PAIRS[pid]
    missing = False

    def pick(options):
        nonlocal missing
        hit = next((f for f in options if installed(f)), None)
        missing |= hit is None
        return hit or options[0]

    sans, mono = pick(pair.sans), pick(pair.mono)
    title = pick(pair.title) if pair.title else sans
    return sans, mono, title, list(pair.packages) if missing else []


def install_command(packages: list[str]) -> str:
    return "sudo apt install " + " ".join(packages)


def qfont_string(family: str, size: int, weight: int = 400) -> str:
    """Qt 6 font description string as KDE stores it."""
    return f"{family},{size},-1,5,{weight},0,0,0,0,0,0,0,0,0,0,1"


def _text(p, rect, family, px, weight, color, value, flags=Qt.AlignmentFlag.AlignLeft):
    f = QFont(family)
    f.setPixelSize(max(1, int(px)))
    f.setWeight(weight)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(rect, flags | Qt.TextFlag.TextWordWrap, value)


def render(pid: str, o: dict, w=1280, h=720) -> QImage:
    o = {**DEFAULTS, **o}
    sans, mono, title, packages = resolve(pid)
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

    x, wd = card.x() + 48, card.width() - 96
    title_w = QFont.Weight.Bold if o["title_weight"] == "Bold" else QFont.Weight.Normal
    p.fillRect(QRectF(card.x(), card.y(), card.width(), 40), QColor(20, 20, 20))
    _text(p, QRectF(card.x(), card.y() + 10, card.width(), 24), title, 13 * s, title_w, "#e8e8e8",
          "Grimoire — MuraL", Qt.AlignmentFlag.AlignHCenter)
    _text(p, QRectF(x, card.y() + 70, wd, 70), sans, 46 * s, QFont.Weight.Light, "#ffffff", sans)
    roles = (tr("grimoire.spells.mural.fonts", "Interface font  ·  {size} pt  ·  monospace: {mono}")
             if title == sans else
             tr("grimoire.spells.mural.fonts",
                "Interface font  ·  {size} pt  ·  titles: {title}  ·  monospace: {mono}"))
    _text(p, QRectF(x, card.y() + 70 + 64 * s, wd, 30), sans, 14 * s, QFont.Weight.Normal, "#8c8c8c",
          roles.format(size=o["size"], mono=mono, title=title))
    _text(p, QRectF(x, card.y() + 140 + 64 * s, wd, 110), sans, 17 * s, QFont.Weight.Normal, "#d8d8d8",
          "The five-leaf grimoire chose the boy with no magic. Asta trained until his hands bled, "
          "and Yuno never stopped chasing the crown. Surpass your limits, right here, right now.")
    code = QRectF(x, card.y() + 270 + 80 * s, wd, 96 * s + 20)
    cp = QPainterPath()
    cp.addRoundedRect(code, 8, 8)
    p.fillPath(cp, QColor(0, 0, 0))
    _text(p, code.adjusted(18, 14, -18, 0), mono, 14 * s, QFont.Weight.Normal, "#cfcfcf",
          "$ grimoire-sightc on\n$ git commit -m \"surpass your limits\"\n0123456789  {}[]()<>=!  il1| O0  => !=")
    _text(p, QRectF(x, card.bottom() - 40, wd, 24), sans, 11 * s, QFont.Weight.Normal, "#6f6f6f",
          tr("grimoire.spells.mural.fonts", "SMALL TEXT · MENUS · TOOLBARS") + " · 0123456789")
    if packages:
        _banner(p, w, h, packages)
    p.end()
    return img


def _banner(p: QPainter, w, h, packages):
    """A strip over the preview: this pairing needs fonts that aren't installed (shown with stand-ins)."""
    band = QRectF(0, h - 64, w, 64)
    p.fillRect(band, QColor(245, 245, 245))
    _text(p, band.adjusted(24, 0, -24, 0), "IBM Plex Sans", 17, QFont.Weight.Medium, "#0a0a0a",
          tr("grimoire.spells.mural.fonts", "Not installed, shown with stand-in fonts. Get them with: {command}")
          .format(command=ltr(install_command(packages))), Qt.AlignmentFlag.AlignVCenter)


def specimen(pid: str, w=640, h=360) -> QImage:
    """A gallery card: the interface face big, the monospace face under it, and the name."""
    sans, mono, title, packages = resolve(pid)
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(10, 10, 10))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    _text(p, QRectF(40, 20, w - 80, 200), title if title != sans else sans, 150, QFont.Weight.Normal, "#f2f2f2",
          "Aa")
    _text(p, QRectF(w * 0.5, 70, w * 0.5 - 40, 80), sans, 34, QFont.Weight.Normal, "#bdbdbd", "Qg 0123",
          Qt.AlignmentFlag.AlignRight)
    _text(p, QRectF(40, 220, w - 80, 60), mono, 40, QFont.Weight.Normal, "#9a9a9a", "{ } => il1 O0")
    _text(p, QRectF(40, 280, w - 80, 40), sans, 26, QFont.Weight.Normal, "#6f6f6f", sans)
    if packages:
        p.fillRect(QRectF(0, h - 40, w, 40), QColor(245, 245, 245))
        _text(p, QRectF(20, h - 40, w - 40, 40), "IBM Plex Sans", 22, QFont.Weight.Medium, "#0a0a0a",
              tr("grimoire.spells.mural.fonts", "Not installed"), Qt.AlignmentFlag.AlignVCenter)
    p.end()
    return img


class FontsTab(ScreenTab):
    key = "fonts"
    context = "grimoire.spells.mural.fonts"
    subtitle = tr_noop("grimoire.spells.mural.fonts",
                       "System fonts for every app, menu and title bar. Running KDE apps update immediately.")
    apply_label = tr_noop("grimoire.spells.mural.fonts", "Apply fonts")

    def designs(self):
        families.cache_clear()                     # fonts installed since the last visit show up
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
        lay.addSpacing(6)
        self.copy = WrapButton(tr("grimoire.spells.mural.fonts", "Copy install command"))
        self.copy.clicked.connect(self._copy_command)
        lay.addWidget(self.copy)
        self.gallery.currentRowChanged.connect(self._update_copy)

    def showEvent(self, e):
        super().showEvent(e)
        self._update_copy()

    def _update_copy(self, *_):
        d = self.current()
        self.copy.setVisible(bool(d and resolve(d.id)[3]))

    def _copy_command(self):
        d = self.current()
        packages = resolve(d.id)[3] if d else []
        if packages:
            QGuiApplication.clipboard().setText(install_command(packages))
            self.status.setText(tr("grimoire.spells.mural.fonts",
                                   "Copied. Paste it into a terminal, then reopen this tab."))

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

    def thumbnail(self, design, o):
        return specimen(design.id)

    def apply(self, design, o):
        sans, mono, title, packages = resolve(design.id)
        if packages:
            raise RuntimeError(tr("grimoire.spells.mural.fonts",
                                  "these fonts aren't installed. Get them with: {command}")
                               .format(command=ltr(install_command(packages))))
        size = o["size"]
        writes = [
            ("General", "font", qfont_string(sans, size)),
            ("General", "menuFont", qfont_string(sans, size)),
            ("General", "toolBarFont", qfont_string(sans, max(8, size - 1))),
            ("General", "smallestReadableFont", qfont_string(sans, max(7, size - 2))),
            ("General", "fixed", qfont_string(mono, size)),
            ("WM", "activeFont", qfont_string(title, size, 700 if o["title_weight"] == "Bold" else 400)),
            ("General", "XftAntialias", "true"),
            ("General", "XftHintStyle", HINTING[o["hinting"]]),
            ("General", "XftSubPixel", "rgb" if o["subpixel"] == "On" else "none"),
        ]
        for group, key, value in writes:
            kwrite("kdeglobals", group, key, value, notify=True)
        kwin_reconfigure()
        return tr("grimoire.spells.mural.fonts", "Applied ✓  Some apps pick up new fonts when reopened.")
