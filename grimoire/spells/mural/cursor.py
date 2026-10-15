# SPDX-License-Identifier: GPL-3.0-or-later
"""Cursor tab: black & white cursor themes at any size. Grimoire's own themes are drawn by cursorgen and written as
real Xcursor files into ~/.local/share/icons on Apply; black & white themes already on the system and community
ones from the store sit next to them. Previews are drawn from the real cursor files (a tiny Xcursor reader), or
straight from cursorgen for ours, on black and on white.
"""
import struct
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import tr, tr_noop
from grimoire.paths import HOME
from grimoire.spells.mural import cursorgen
from grimoire.spells.mural import store as community
from grimoire.spells.mural.kde import kread, run_tool
from grimoire.spells.mural.screens import Choice, Design, ScreenTab, by_line

ICONS = Path("/usr/share/icons")
USER_ICONS = HOME / ".local/share/icons"
SEARCH = [USER_ICONS, HOME / ".icons", ICONS]
DESIGNS = [          # ids never change: saved looks and shared setups name them
    Design("Oxygen_Black", "Oxygen Black",
           tr_noop("grimoire.spells.mural.cursor", "Glossy black cursors with soft shading.")),
    Design("Grimoire-Cursors-Ink", "Grimoire Ink",
           tr_noop("grimoire.spells.mural.cursor",
                   "Solid black with a crisp white edge and a soft shadow. Clear on any background.")),
    Design("Grimoire-Cursors-Chalk", "Grimoire Chalk",
           tr_noop("grimoire.spells.mural.cursor",
                   "The same shapes in white with a black edge: easy to spot on dark windows.")),
    Design("Grimoire-Cursors-Slim", "Grimoire Slim",
           tr_noop("grimoire.spells.mural.cursor",
                   "A narrow black arrow with a hairline white edge and no shadow. Precise and quiet.")),
    Design("Grimoire-Cursors-Sharp", "Grimoire Sharp",
           tr_noop("grimoire.spells.mural.cursor", "A tail-less arrowhead in near-black. Modern and minimal.")),
    Design("Grimoire-Cursors-Ghost", "Grimoire Ghost",
           tr_noop("grimoire.spells.mural.cursor",
                   "Hollow outlines: a white line with a black edge, so what's underneath shows through.")),
    Design("Grimoire-Cursors-Graphite", "Grimoire Graphite",
           tr_noop("grimoire.spells.mural.cursor",
                   "Dark gray with a light gray edge and rounded corners. Softer than pure black.")),
    Design("Grimoire-Cursors-Halo", "Grimoire Halo",
           tr_noop("grimoire.spells.mural.cursor",
                   "White with a heavy black ring and a white halo: the easiest to find on any screen.")),
    Design("Grimoire-Cursors-Pixel", "Grimoire Pixel",
           tr_noop("grimoire.spells.mural.cursor",
                   "Retro pixel art, snapped to pure black and white with no smoothing.")),
    Design("Oxygen_White", "Oxygen White",
           tr_noop("grimoire.spells.mural.cursor", "Oxygen's glossy cursors in white.")),
    Design("KDE_Classic", "KDE Classic",
           tr_noop("grimoire.spells.mural.cursor", "The plain black and white cursors of older KDE releases.")),
    Design("breeze_cursors", "Breeze",
           tr_noop("grimoire.spells.mural.cursor",
                   "KDE's default cursors, with a few colored accents. Pick it to go back to how Plasma looked.")),
]
SIZES = ["24", "32", "36", "48", "64", "72", "96"]
DEFAULTS = {"size": "24"}
SHAPES = [("default", "left_ptr"), ("pointer", "pointing_hand", "hand2"), ("text", "xterm", "ibeam"),
          ("wait", "watch"), ("help", "question_arrow", "left_ptr_help"),
          ("openhand", "grab", "hand1"), ("fleur", "all-scroll", "size_all"),
          ("ew-resize", "size_hor", "sb_h_double_arrow"),
          ("not-allowed", "crossed_circle", "forbidden"), ("crosshair", "cross", "tcross")]


def generated(theme: str) -> bool:
    return theme in cursorgen.STYLES


@lru_cache(maxsize=128)
def load_cursor(theme: str, names: tuple, size: int) -> QImage:
    """First frame of a cursor, at the nominal size closest to `size`: drawn by cursorgen for our own themes,
    else read from the theme's Xcursor file."""
    if generated(theme):
        shape = next((cursorgen.BY_NAME[n].file for n in names if n in cursorgen.BY_NAME), None)
        return cursorgen.image(theme, shape, size, 3) if shape else QImage()
    path = next((base / theme / "cursors" / name for base in SEARCH for name in names
                 if (base / theme / "cursors" / name).exists()), None)
    if path is None:
        return QImage()
    data = path.read_bytes()
    if data[:4] != b"Xcur":
        return QImage()
    ntoc = struct.unpack_from("<I", data, 12)[0]
    images = []
    for i in range(ntoc):
        kind, subtype, pos = struct.unpack_from("<III", data, 16 + i * 12)
        if kind == 0xFFFD0002:                        # image chunk; subtype = nominal size
            images.append((abs(subtype - size), subtype, pos))
    if not images:
        return QImage()
    _, _, pos = min(images)
    w, h = struct.unpack_from("<II", data, pos + 16)
    pixels = data[pos + 36: pos + 36 + w * h * 4]
    return QImage(pixels, w, h, w * 4, QImage.Format.Format_ARGB32_Premultiplied).copy()


def render(theme: str, o: dict, w=1280, h=720, shapes=SHAPES, labels=True) -> QImage:
    """The theme's cursors on a dark half and a light half, magnified so the shapes are clear."""
    size = int({**DEFAULTS, **o}["size"])
    img = QImage(w, h, QImage.Format.Format_RGB32)
    p = QPainter(img)
    p.fillRect(QRectF(0, 0, w / 2, h), QColor(10, 10, 10))
    p.fillRect(QRectF(w / 2, 0, w / 2, h), QColor(242, 242, 242))
    cols = min(len(shapes), 5)
    rows = (len(shapes) + cols - 1) // cols
    cell = min((w / 2) / (cols + 0.4), (h - (150 if labels else 40)) / rows)
    zoom = max(1, min(3, int(cell * 0.85 / size)))   # whole steps, unsmoothed: every pixel shows as it is
    top = (h - rows * cell) / 2
    for half in range(2):
        for k, names in enumerate(shapes):
            cur = load_cursor(theme, names, size)
            if cur.isNull():
                continue
            cw, ch = cur.width() * zoom, cur.height() * zoom
            cx = half * w / 2 + (w / 2) * ((k % cols) + 0.5) / cols
            cy = top + cell * (k // cols + 0.5)
            p.drawImage(QRectF(cx - cw / 2, cy - ch / 2, cw, ch), cur)
        if labels:
            p.setPen(QColor(120, 120, 120))
            p.setFont(QFont("IBM Plex Sans", 11))
            p.drawText(QRectF(half * w / 2, h - 60, w / 2, 24), Qt.AlignmentFlag.AlignCenter,
                       tr("grimoire.spells.mural.cursor", "on dark") if half == 0
                       else tr("grimoire.spells.mural.cursor", "on light"))
    if labels:
        p.setPen(QColor(150, 150, 150))
        p.setFont(QFont("IBM Plex Sans", 11))
        p.drawText(QRectF(0, 30, w, 24), Qt.AlignmentFlag.AlignCenter,
                   tr("grimoire.spells.mural.cursor", "{size} px  ·  shown at {zoom}×").format(size=size, zoom=zoom))
    p.end()
    return img


def current() -> str:
    return kread("kcminputrc", "Mouse", "cursorTheme")


def installed(theme: str) -> bool:
    return any((base / theme / "cursors").is_dir() for base in SEARCH)


class CursorTab(ScreenTab):
    key = "cursor"
    context = "grimoire.spells.mural.cursor"
    subtitle = tr_noop("grimoire.spells.mural.cursor",
                       "Your mouse pointer. Previews come from the real cursor files, shown on dark and light. "
                       "Grimoire's own themes are made on your PC when you apply them.")
    apply_label = tr_noop("grimoire.spells.mural.cursor", "Apply cursor")
    store = ["cursor"]

    def designs(self):
        own = [d for d in DESIGNS if generated(d.id) or installed(d.id)]
        return own + [Design(e["ident"], e["name"], by_line(e)) for e in community.installed("cursor")]

    def build_options(self, lay):
        grid = QGridLayout()
        self.size = Choice([(k, tr("grimoire.spells.mural.cursor", "{size} px").format(size=k)) for k in SIZES],
                           self.changed)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.cursor", "Size")), 0, 0)
        grid.addWidget(self.size, 0, 1)
        lay.addLayout(grid)

    def options(self):
        return {"size": self.size.value()}

    def set_options(self, o):
        self.size.set_value({**DEFAULTS, **o}["size"])

    def preview(self, design, o):
        return render(design.id, o)

    def thumbnail(self, design, o):
        """Cards show two cursors big enough to tell the themes apart."""
        return render(design.id, {"size": "48"}, 256, 144, SHAPES[:2], labels=False)

    def apply(self, design, o):
        if generated(design.id):
            cursorgen.write_theme(design.id, USER_ICONS)
        run_tool(["plasma-apply-cursortheme", "--size", o["size"], design.id], ok_if_already=True)
        return tr("grimoire.spells.mural.cursor", "Applied ✓")
