# SPDX-License-Identifier: GPL-3.0-or-later
"""Grimoire's own black & white cursor themes, drawn in code and written as real Xcursor files.

Every shape is a QPainterPath on a 32-unit canvas, painted in a Style (fill, outline rings, shadow, pixel grid) at
each nominal size, so one drawing gives every size crisp. write_theme() lays out a complete theme folder: one
Xcursor file per shape (wait/progress animated) and symlinks for every standard CSS, X11 and legacy hash name.
No Qt widgets: safe on worker threads once a QGuiApplication exists (fonts for the "?" badge).
"""
import os
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QTransform

SIZES = [24, 32, 36, 48, 64, 72, 96]
FRAMES, DELAY = 12, 50                   # spinner frames per cycle, ms each
MARKER = ".grimoire-cursors"             # tells our generated folders from anything else


@dataclass(frozen=True)
class Style:
    name: str
    fill: str | None                     # None = hollow (only the rings show)
    rings: tuple = ()                    # outline strokes, outermost first: (color, total width in units)
    mark: str = "#000000"                # badges' symbols, spinner arc, etc.
    arrow: str = "classic"               # classic | slim | sharp
    shadow: int = 0                      # shadow alpha (0 = none)
    round: bool = False                  # round joins on the outline
    pixel: bool = False                  # drawn on a coarse grid with no smoothing


STYLES = {
    "Grimoire-Cursors-Ink": Style("Grimoire Ink", "#0a0a0a", (("#ffffff", 3.0),), "#ffffff", shadow=90),
    "Grimoire-Cursors-Chalk": Style("Grimoire Chalk", "#fafafa", (("#0a0a0a", 3.0),), "#0a0a0a", shadow=90),
    "Grimoire-Cursors-Slim": Style("Grimoire Slim", "#000000", (("#ffffff", 2.0),), "#ffffff", arrow="slim"),
    "Grimoire-Cursors-Sharp": Style("Grimoire Sharp", "#111111", (("#f2f2f2", 2.4),), "#f2f2f2", arrow="sharp",
                                    shadow=70),
    "Grimoire-Cursors-Ghost": Style("Grimoire Ghost", None, (("#000000", 4.6), ("#ffffff", 2.2)), "#ffffff",
                                    round=True),
    "Grimoire-Cursors-Graphite": Style("Grimoire Graphite", "#3a3a3a", (("#d6d6d6", 3.0),), "#e8e8e8",
                                       round=True, shadow=60),
    "Grimoire-Cursors-Halo": Style("Grimoire Halo", "#ffffff", (("#ffffff", 7.0), ("#000000", 4.2)), "#000000",
                                   round=True),
    "Grimoire-Cursors-Pixel": Style("Grimoire Pixel", "#000000", (("#ffffff", 4.4),), "#ffffff", pixel=True),
}


# ---------------------------------------------------------------- shapes (32-unit canvas)
def _poly(*pts) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(*pts[0])
    for pt in pts[1:]:
        path.lineTo(*pt)
    path.closeSubpath()
    return path


def _rect(x, y, w, h, r=0.0) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, w, h), r, r)
    return path


def _circle(cx, cy, r) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QPointF(cx, cy), r, r)
    return path


def _union(*paths) -> QPainterPath:
    out = QPainterPath()
    for p in paths:
        out = out.united(p)
    return out.simplified()


def _turn(path: QPainterPath, deg: float, cx=16.0, cy=16.0) -> QPainterPath:
    return QTransform().translate(cx, cy).rotate(deg).translate(-cx, -cy).map(path)


def _arrow(kind: str) -> QPainterPath:
    if kind == "slim":
        return _poly((5, 3), (5, 23.5), (10, 19), (13.6, 26.6), (16.4, 25.3), (12.9, 18), (19, 18))
    if kind == "sharp":
        return _poly((5, 3), (5, 24), (10.8, 18.6), (20, 18.2))
    return _poly((4.5, 2.5), (4.5, 24.5), (9.6, 19.6), (13.2, 27.8), (17, 26.2), (13.5, 18.3), (20.5, 18.3))


def _double(length=22.0, bar=3.4, head=9.0, deep=6.5) -> QPainterPath:
    """A horizontal double-headed arrow centred on the canvas."""
    x0, x1, c = 16 - length / 2, 16 + length / 2, 16
    return _union(_rect(x0 + deep - 0.5, c - bar / 2, length - 2 * deep + 1, bar),
                  _poly((x0, c), (x0 + deep, c - head / 2), (x0 + deep, c + head / 2)),
                  _poly((x1, c), (x1 - deep, c - head / 2), (x1 - deep, c + head / 2)))


def _single(length=22.0) -> QPainterPath:
    """An arrow pointing up, tip at (16, 5)."""
    return _union(_poly((16, 5), (24, 14), (8, 14)), _rect(14.2, 13, 3.6, length - 8))


def _hand(kind: str) -> QPainterPath:
    if kind == "point":
        parts = [_rect(10.5, 2.5, 5, 16, 2.5), _rect(15.2, 11, 4.4, 9, 2.2), _rect(19.2, 12, 4.4, 9, 2.2),
                 _rect(23.0, 13.5, 3.8, 8, 1.9), _turn(_rect(5, 15, 4.4, 10, 2.2), -35, 8, 18),
                 _rect(8, 15.5, 18.8, 13, 5)]
    elif kind == "open":
        parts = [_rect(9.4, 5.5, 4.2, 13, 2.1), _rect(13.8, 3, 4.2, 15, 2.1), _rect(18.2, 4, 4.2, 14, 2.1),
                 _rect(22.4, 7, 3.8, 11, 1.9), _turn(_rect(4.5, 13, 4.2, 10, 2.1), -40, 7, 17),
                 _rect(8.4, 13, 18, 15.5, 5.5)]
    else:                                                # closed fist
        parts = [_rect(9.4, 10, 4.2, 8, 2.1), _rect(13.8, 9, 4.2, 9, 2.1), _rect(18.2, 9.5, 4.2, 9, 2.1),
                 _rect(22.4, 11, 3.8, 8, 1.9), _turn(_rect(5.5, 14, 4.2, 8, 2.1), -45, 7.5, 17),
                 _rect(8.4, 13, 18, 14.5, 5.5)]
    return _union(*parts)


def _ring(cx, cy, r, w) -> QPainterPath:
    path = _circle(cx, cy, r)
    path.addEllipse(QPointF(cx, cy), r - w, r - w)
    path.setFillRule(Qt.FillRule.OddEvenFill)
    return path


def _arc(cx, cy, r, w, start, span) -> QPainterPath:
    """A thick arc: the spinner's moving part."""
    path = QPainterPath()
    outer, inner = QRectF(cx - r, cy - r, 2 * r, 2 * r), QRectF(cx - r + w, cy - r + w, 2 * (r - w), 2 * (r - w))
    path.arcMoveTo(outer, start)
    path.arcTo(outer, start, span)
    path.arcTo(inner, start + span, -span)
    path.closeSubpath()
    return path


def _text(symbol: str, cx, cy, px) -> QPainterPath:
    f = QFont("IBM Plex Sans")
    f.setPixelSize(int(px * 4))                          # laid out large, scaled down: crisp outlines
    f.setWeight(QFont.Weight.Bold)
    path = QPainterPath()
    path.addText(0, 0, f, symbol)
    r = path.boundingRect()
    return QTransform().translate(cx, cy).scale(0.25, 0.25).translate(-r.center().x(), -r.center().y()).map(path)


def _plus(cx, cy, s, w) -> QPainterPath:
    return _union(_rect(cx - s / 2, cy - w / 2, s, w), _rect(cx - w / 2, cy - s / 2, w, s))


def _badge(mark: str) -> tuple[QPainterPath, QPainterPath]:
    """A round badge at the arrow's lower right, and its symbol."""
    cx, cy, r = 23.5, 23.5, 6.6
    body = _circle(cx, cy, r)
    if mark == "?":
        sym = _text("?", cx, cy, 10)
    elif mark == "+":
        sym = _plus(cx, cy, 8, 2.2)
    elif mark == "link":
        sym = _union(_rect(cx - 3.6, cy - 1.0, 5.6, 2.0).united(_rect(cx - 3.6, cy - 1, 2, 4.4)),
                     _poly((cx + 3.8, cy), (cx + 0.6, cy - 3.2), (cx + 0.6, cy + 3.2)))
    elif mark == "no":
        sym = _union(_ring(cx, cy, 4.4, 1.6), _turn(_rect(cx - 0.8, cy - 4, 1.6, 8), 45, cx, cy))
    else:                                                # menu
        body = _rect(17, 16.5, 13, 13, 2.5)
        sym = _union(*(_rect(19.5, 19.5 + 3 * k, 8, 1.6) for k in range(3)))
    return body, sym


@dataclass(frozen=True)
class Shape:
    file: str                                             # the real file; aliases link to it
    hot: tuple
    aliases: tuple = ()


SHAPES = [
    Shape("default", (4.5, 2.5), ("left_ptr", "arrow", "top_left_arrow", "wayland-cursor", "size-bdiag", "size-fdiag",
                                  "size-hor", "size-ver")),
    Shape("right_ptr", (27.5, 2.5), ("draft_large", "draft_small")),
    Shape("pointer", (13, 2.5), ("hand1", "hand2", "pointing_hand", "9d800788f1b08800ae810202380a0822",
                                 "e29285e634086352946a0e7090d73106")),
    Shape("openhand", (16, 16), ("grab", "5aca4d189052212118709018842178c0", "hand")),
    Shape("closedhand", (16, 16), ("grabbing", "dnd-move", "dnd-none", "move", "4498f0e0c1937ffe01fd06f973665830",
                                   "9081237383d90e509aa00f00170e968f", "fcf21c00b30f7e3f83fe0dfd12e71cff")),
    Shape("text", (16, 16), ("xterm", "ibeam")),
    Shape("vertical-text", (16, 16), ()),
    Shape("crosshair", (16, 16), ("cross", "tcross", "cross_reverse", "diamond_cross")),
    Shape("cell", (16, 16), ("plus",)),
    Shape("fleur", (16, 16), ("all-scroll", "size_all", "move-all")),
    Shape("size_hor", (16, 16), ("ew-resize", "e-resize", "w-resize", "h_double_arrow", "sb_h_double_arrow",
                                 "left_side", "right_side", "14fef782d02440884392942c11205230")),
    Shape("size_ver", (16, 16), ("ns-resize", "n-resize", "s-resize", "v_double_arrow", "sb_v_double_arrow",
                                 "top_side", "bottom_side", "00008160000006810000408080010102")),
    Shape("size_fdiag", (16, 16), ("nwse-resize", "nw-resize", "se-resize", "top_left_corner", "bottom_right_corner",
                                   "c7088f0f3e6c8088236ef8e1e3e70000")),
    Shape("size_bdiag", (16, 16), ("nesw-resize", "ne-resize", "sw-resize", "top_right_corner", "bottom_left_corner",
                                   "fcf1c3c7cd4491d801f1e1c78f100000")),
    Shape("col-resize", (16, 16), ("split_h", "sb_h_double_arrow_bar")),
    Shape("row-resize", (16, 16), ("split_v",)),
    Shape("up-arrow", (16, 5), ("center_ptr", "sb_up_arrow")),
    Shape("down-arrow", (16, 27), ("sb_down_arrow",)),
    Shape("left-arrow", (5, 16), ("sb_left_arrow",)),
    Shape("right-arrow", (27, 16), ("sb_right_arrow",)),
    Shape("wait", (16, 16), ("watch", "clock")),
    Shape("progress", (4.5, 2.5), ("left_ptr_watch", "half-busy", "00000000000000020006000e7e9ffc3f",
                                   "08e8e1c95fe2fc01f976f1e063a24ccd", "3ecb610c1bf2410f44200f48c40d3599")),
    Shape("help", (4.5, 2.5), ("question_arrow", "whats_this", "left_ptr_help", "dnd-ask",
                               "5c6cd98b3f3ebcb1f9c7f1c204630408", "d9ce0ab605698f320427677b458ad60b")),
    Shape("copy", (4.5, 2.5), ("dnd-copy", "1081e37283d90000800003c07f3ef6bf", "6407b0e94181790501fd1e167b474872",
                               "b66166c04f8c3109214a4fbd64a50fc8")),
    Shape("alias", (4.5, 2.5), ("link", "dnd-link", "3085a0e285430894940527032f8b26df",
                                "640fb0e74195791501fd1ed57b41487f", "a2a266d0498c3104214a47bd64ab0fc8")),
    Shape("context-menu", (4.5, 2.5), ()),
    Shape("no-drop", (4.5, 2.5), ("dnd-no-drop", "forbidden")),
    Shape("not-allowed", (16, 16), ("crossed_circle", "circle", "03b6e0fcb3499374a867c041f52298f0")),
    Shape("x-cursor", (16, 16), ("X_cursor", "pirate")),
    Shape("zoom-in", (13, 13), ()),
    Shape("zoom-out", (13, 13), ()),
    Shape("pencil", (5, 27), ("draft",)),
    Shape("color-picker", (5, 27), ()),
]
BY_NAME = {n: s for s in SHAPES for n in (s.file, *s.aliases)}


def outline(file: str, arrow: str, frame: int = 0) -> tuple[QPainterPath, QPainterPath]:
    """(body, marks) of a shape: the body takes the style's fill and rings, marks are drawn in the mark color."""
    none = QPainterPath()
    a = _arrow(arrow)
    if file == "default":
        return a, none
    if file == "right_ptr":
        return QTransform(-1, 0, 0, 1, 32, 0).map(a), none
    if file == "pointer":
        return _hand("point"), none
    if file == "openhand":
        return _hand("open"), none
    if file == "closedhand":
        return _hand("closed"), none
    if file in ("text", "vertical-text"):
        beam = _union(_rect(14.6, 6, 2.8, 20), _rect(10.5, 4, 11, 2.8, 1.2), _rect(10.5, 25.2, 11, 2.8, 1.2))
        return (beam if file == "text" else _turn(beam, 90)), none
    if file == "crosshair":
        return _union(_rect(14.8, 2, 2.4, 11), _rect(14.8, 19, 2.4, 11), _rect(2, 14.8, 11, 2.4),
                      _rect(19, 14.8, 11, 2.4), _circle(16, 16, 1.5)), none
    if file == "cell":
        return _plus(16, 16, 22, 6), none
    if file == "fleur":
        d = _double(26, 3, 8.5, 6)
        return _union(d, _turn(d, 90)), none
    rot = {"size_hor": 0, "size_ver": 90, "size_fdiag": 45, "size_bdiag": -45}
    if file in rot:
        return _turn(_double(), rot[file]), none
    if file in ("col-resize", "row-resize"):
        shape = _union(_double(26, 3, 8.5, 6), _rect(12.4, 6, 2.6, 20), _rect(17, 6, 2.6, 20))
        return (shape if file == "col-resize" else _turn(shape, 90)), none
    turns = {"up-arrow": 0, "right-arrow": 90, "down-arrow": 180, "left-arrow": 270}
    if file in turns:
        return _turn(_single(24), turns[file]), none
    spin = -(360 / FRAMES) * frame
    if file == "wait":
        return _circle(16, 16, 11.5), _union(_ring(16, 16, 9.5, 3.4).subtracted(_arc(16, 16, 10, 4.4, 90 + spin, 100)))
    if file == "progress":
        return _union(a, _circle(24, 24, 7)), _ring(24, 24, 5.4, 2.2).subtracted(_arc(24, 24, 6, 3.2, 90 + spin, 110))
    badges = {"help": "?", "copy": "+", "alias": "link", "context-menu": "menu", "no-drop": "no"}
    if file in badges:
        body, sym = _badge(badges[file])
        return _union(a, body), sym
    if file == "not-allowed":
        return _union(_ring(16, 16, 12, 4.4), _turn(_rect(13.8, 5, 4.4, 22), 45)), none
    if file == "x-cursor":
        bar = _rect(13.8, 3, 4.4, 26, 1.5)
        return _union(_turn(bar, 45), _turn(bar, -45)), none
    if file in ("zoom-in", "zoom-out"):
        body = _union(_circle(13, 13, 10), _turn(_rect(20.5, 11, 10, 4.6, 2.3), 45, 20.5, 13.3))
        sym = _ring(13, 13, 7.6, 1.4).united(_plus(13, 13, 8, 2.2) if file == "zoom-in" else _rect(9, 11.9, 8, 2.2))
        return body, sym
    if file == "pencil":
        return _turn(_union(_poly((4, 16), (9, 13), (9, 19)), _rect(9, 13, 18, 6, 1), _rect(27, 13, 2.6, 6, 1.2)),
                     -45, 4, 16).translated(1, 11), _turn(_rect(23.5, 13, 1.4, 6), -45, 4, 16).translated(1, 11)
    if file == "color-picker":
        return _turn(_union(_poly((3.5, 16), (8, 14.5), (8, 17.5)), _rect(8, 14, 13, 4, 1), _rect(20, 11.5, 9, 9, 3)),
                     -45, 4, 16).translated(1, 11), QPainterPath()
    raise KeyError(file)


def _paint(p: QPainter, s: Style, body: QPainterPath, marks: QPainterPath):
    join = Qt.PenJoinStyle.RoundJoin if s.round or s.pixel else Qt.PenJoinStyle.MiterJoin
    for color, width in s.rings:                      # widest ring first; each shows only outside the body
        pen = QPen(QColor(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, join)
        pen.setMiterLimit(3)
        p.strokePath(body, pen)
    if s.fill:
        p.fillPath(body, QColor(s.fill))
    if marks.isEmpty():
        return
    if not s.fill:                                   # hollow: marks get a thin edge in the outer ring's color
        p.strokePath(marks, QPen(QColor(s.rings[0][0]), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                 Qt.PenJoinStyle.RoundJoin))
    p.fillPath(marks, QColor(s.mark))


def _shadow(body: QPainterPath, s: Style, size: int) -> QImage:
    """A soft drop shadow: the silhouette drawn small, then scaled up smoothly (a cheap, even blur)."""
    small = max(6, size // 4)
    img = QImage(small, small, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(small / 32, small / 32)
    p.translate(0.8, 1.6)
    widest = max((w for _, w in s.rings), default=0)
    p.strokePath(body, QPen(QColor(0, 0, 0, s.shadow), widest + 1.5))
    p.fillPath(body, QColor(0, 0, 0, s.shadow))
    p.end()
    return img.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)


@lru_cache(maxsize=512)
def image(theme: str, file: str, size: int, frame: int = 0) -> QImage:
    """One cursor picture (ARGB32 premultiplied, size x size) of a generated theme."""
    s = STYLES[theme]
    body, marks = outline(file, s.arrow, frame)
    if s.pixel:                                       # a ~16-cell grid, snapped to pure black/white, no smoothing
        k = max(1, round(size / 16))
        grid = max(8, size // k)
        small = QImage(grid, grid, QImage.Format.Format_ARGB32)
        small.fill(0)
        p = QPainter(small)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(grid / 32, grid / 32)
        _paint(p, s, body, marks)
        p.end()
        for y in range(grid):
            for x in range(grid):
                c = small.pixelColor(x, y)
                if c.alpha() < 110:
                    small.setPixelColor(x, y, QColor(0, 0, 0, 0))
                else:
                    small.setPixelColor(x, y, QColor("#ffffff") if c.lightness() > 127 else QColor("#000000"))
        big = small.scaled(grid * k, grid * k, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.FastTransformation)
        img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.drawImage(0, 0, big)
        p.end()
        return img
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    if s.shadow:
        p.drawImage(0, 0, _shadow(body, s, size))
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 32, size / 32)
    _paint(p, s, body, marks)
    p.end()
    return img


def hotspot(theme: str, file: str, size: int) -> tuple[int, int]:
    x, y = BY_NAME[file].hot
    if STYLES[theme].pixel:
        k = max(1, round(size / 16))
        grid = max(8, size // k)
        return min(size - 1, int(x * grid / 32) * k), min(size - 1, int(y * grid / 32) * k)
    return min(size - 1, round(x * size / 32)), min(size - 1, round(y * size / 32))


def animated(file: str) -> bool:
    return file in ("wait", "progress")


# ---------------------------------------------------------------- Xcursor files
def xcursor(theme: str, file: str, sizes=SIZES) -> bytes:
    """A complete Xcursor file: every size (and every frame for spinners) of one shape."""
    chunks = []                                       # (nominal size, image bytes)
    for size in sizes:
        xh, yh = hotspot(theme, file, size)
        for frame in range(FRAMES if animated(file) else 1):
            img = image(theme, file, size, frame)
            pixels = bytes(img.constBits())[: size * size * 4]
            delay = DELAY if animated(file) else 0
            chunks.append((size, struct.pack("<9I", 36, 0xFFFD0002, size, 1, size, size, xh, yh, delay) + pixels))
    ntoc = len(chunks)
    pos = 16 + ntoc * 12
    toc, body = [], []
    for size, chunk in chunks:
        toc.append(struct.pack("<3I", 0xFFFD0002, size, pos))
        body.append(chunk)
        pos += len(chunk)
    return struct.pack("<4sIII", b"Xcur", 16, 0x10000, ntoc) + b"".join(toc) + b"".join(body)


def is_ours(folder: Path) -> bool:
    return (folder / MARKER).is_file()


def write_theme(theme: str, base: Path) -> Path:
    """Write (or refresh) the theme under base/<theme>; returns the folder. Only ever writes into a folder we made
    (or a new one): an unrelated theme that happens to share the name is never touched."""
    s = STYLES[theme]
    folder = base / theme
    if folder.exists() and not is_ours(folder):
        raise RuntimeError(f"{folder} isn't a Grimoire cursor theme; not overwriting it")
    cursors = folder / "cursors"
    cursors.mkdir(parents=True, exist_ok=True)
    (folder / MARKER).write_text("Generated by Grimoire Linux → MuraL → Cursor. Safe to delete.\n")
    (folder / "index.theme").write_text(f"[Icon Theme]\nName={s.name}\nComment=Black & white cursors by Grimoire "
                                        f"Linux\nInherits=breeze_cursors\n")
    (folder / "cursor.theme").write_text(f"[Icon Theme]\nInherits={theme}\n")
    for shape in SHAPES:
        target = cursors / shape.file
        tmp = cursors / f".{shape.file}.tmp"
        tmp.write_bytes(xcursor(theme, shape.file))
        tmp.replace(target)                           # atomic: a running app never reads half a file
        for alias in shape.aliases:
            link = cursors / alias
            if link.is_symlink() or link.exists():
                if link.is_symlink() and os.readlink(link) == shape.file:
                    continue
                link.unlink()                         # our own generated folder: a stale link or file of ours
            link.symlink_to(shape.file)
    return folder

