# SPDX-License-Identifier: GPL-3.0-or-later
"""Generated wallpapers for the Desktop tab: black & white designs drawn at the screen's own resolution.

A design draws white "ink" on black into a PIL "L" image; the tone then maps black to the background and white to
the foreground (dark, light or gray), and a little grain goes on last (it also hides banding in gradients).
Sizes scale with the width (u = w / 1920) and the random numbers depend only on design + seed, so the preview and
the full-size file are the same picture. PIL + QPainter on QImages only: safe on worker threads.
Design ids and option keys are stored (saved choices, Looks): never rename them.
"""
import hashlib
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer

from grimoire.i18n import tr_noop
from grimoire.paths import ASSETS
from grimoire.spells.mural import library
from grimoire.spells.mural.screens import Design

DESIGNS = [
    Design("grimoire", tr_noop("grimoire.spells.mural.desktop", "Grimoire"),
           tr_noop("grimoire.spells.mural.desktop", "The clover emblem in a soft pool of light on black.")),
    Design("grain", tr_noop("grimoire.spells.mural.desktop", "Film grain"),
           tr_noop("grimoire.spells.mural.desktop", "A dark gradient under heavy film grain, like a darkroom print.")),
    Design("lines", tr_noop("grimoire.spells.mural.desktop", "Hairlines"),
           tr_noop("grimoire.spells.mural.desktop", "Fine parallel lines that fade in and out across the screen.")),
    Design("topo", tr_noop("grimoire.spells.mural.desktop", "Topographic"),
           tr_noop("grimoire.spells.mural.desktop", "Contour lines of an imaginary landscape, with bold index lines.")),
    Design("halftone", tr_noop("grimoire.spells.mural.desktop", "Halftone"),
           tr_noop("grimoire.spells.mural.desktop", "A newspaper dot screen: dots swell and shrink with the light.")),
    Design("bauhaus", tr_noop("grimoire.spells.mural.desktop", "Bauhaus"),
           tr_noop("grimoire.spells.mural.desktop", "A grid of tiles: quarter circles, halves, triangles and bars.")),
    Design("fog", tr_noop("grimoire.spells.mural.desktop", "Fog"),
           tr_noop("grimoire.spells.mural.desktop", "Soft gray clouds drifting into each other, out of focus.")),
    Design("clover", tr_noop("grimoire.spells.mural.desktop", "Clover field"),
           tr_noop("grimoire.spells.mural.desktop", "Rows of Grimoire clovers, a few of them lit up.")),
    Design("type", tr_noop("grimoire.spells.mural.desktop", "Typography"),
           tr_noop("grimoire.spells.mural.desktop", "Your words, huge, repeated in solid and outlined rows.")),
    Design("ridges", tr_noop("grimoire.spells.mural.desktop", "Ridges"),
           tr_noop("grimoire.spells.mural.desktop", "Stacked signal lines rising into peaks in the middle.")),
    Design("rings", tr_noop("grimoire.spells.mural.desktop", "Rings"),
           tr_noop("grimoire.spells.mural.desktop", "Two sets of rings crossing into a quiet moiré.")),
    Design("maze", tr_noop("grimoire.spells.mural.desktop", "Maze"),
           tr_noop("grimoire.spells.mural.desktop", "Quarter-circle tiles that join into an endless winding path.")),
    Design("stars", tr_noop("grimoire.spells.mural.desktop", "Night sky"),
           tr_noop("grimoire.spells.mural.desktop", "A field of stars, a faint Milky Way, a few that glow.")),
    Design("grid", tr_noop("grimoire.spells.mural.desktop", "Graph paper"),
           tr_noop("grimoire.spells.mural.desktop", "Fine and bold grid lines with crosses where they meet.")),
    Design("spot", tr_noop("grimoire.spells.mural.desktop", "Spotlight"),
           tr_noop("grimoire.spells.mural.desktop", "One smooth beam of light falling across the screen.")),
    Design("bitmap", tr_noop("grimoire.spells.mural.desktop", "1-bit"),
           tr_noop("grimoire.spells.mural.desktop", "A gradient dithered down to pure black and white pixels.")),
]
IDS = {d.id: d for d in DESIGNS}
TONES = {   # stored key: (label, background, foreground)
    "dark": (tr_noop("grimoire.spells.mural.desktop", "Dark"), 10, 238),
    "light": (tr_noop("grimoire.spells.mural.desktop", "Light"), 240, 14),
    "gray": (tr_noop("grimoire.spells.mural.desktop", "Gray"), 40, 200),
    "black": (tr_noop("grimoire.spells.mural.desktop", "Pure black"), 0, 255),
}
SIZES = ["screen", "1920x1080", "2560x1440", "3440x1440", "3840x2160"]
DEFAULTS = {"tone": "dark", "density": 5, "grain": 2, "seed": 1, "text": "GRIMOIRE", "size": "screen"}


# ---------------------------------------------------------------- helpers
def _canvas(w: int, h: int) -> tuple[QImage, QPainter]:
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    return img, p


def _to_l(img: QImage) -> Image.Image:
    g = img.convertToFormat(QImage.Format.Format_Grayscale8)
    # Qt pads each row to 4 bytes, so pass the real row stride
    return Image.frombuffer("L", (g.width(), g.height()), bytes(g.constBits()), "raw", "L", g.bytesPerLine(), 1).copy()


def _ink(v: float) -> QColor:
    v = max(0, min(255, int(v)))
    return QColor(v, v, v)


def _noise(rng: random.Random, w: int, h: int, cells: float, octaves: int = 3) -> Image.Image:
    """Smooth value noise (0..255, full range): random lattices upscaled bicubic, each octave half as strong."""
    acc, total = None, 0.0
    for k in range(octaves):
        cx = max(2, round(cells * 2 ** k))
        cy = max(2, round(cx * h / w))
        small = Image.frombytes("L", (cx + 1, cy + 1), rng.randbytes((cx + 1) * (cy + 1)))
        layer = small.resize((w, h), Image.BICUBIC)
        weight = 0.5 ** k
        total += weight
        acc = layer if acc is None else Image.blend(acc, layer, weight / total)
    acc = acc.filter(ImageFilter.GaussianBlur(w / (cells * 10)))
    return ImageOps.autocontrast(acc, cutoff=1)


def _radial(w: int, h: int, cx: float, cy: float, r: float, gamma: float = 1.6) -> Image.Image:
    """255 at (cx, cy) falling to 0 at radius r (drawn small, scaled up smooth)."""
    sw, sh = max(8, w // 8), max(8, h // 8)
    data = bytearray(sw * sh)
    for y in range(sh):
        for x in range(sw):
            d = math.hypot(x * 8 - cx, y * 8 - cy) / r
            data[y * sw + x] = int(255 * max(0.0, 1 - d) ** gamma)
    return Image.frombytes("L", (sw, sh), bytes(data)).resize((w, h), Image.BICUBIC)


def _band(w: int, h: int, angle: float, width: float) -> Image.Image:
    """255 along a line through the middle at angle (radians), fading out over width (drawn small, scaled up)."""
    sw, sh = max(8, w // 8), max(8, h // 8)
    nx, ny = -math.sin(angle), math.cos(angle)
    data = bytearray(sw * sh)
    for y in range(sh):
        for x in range(sw):
            dist = (x * 8 - w / 2) * nx + (y * 8 - h / 2) * ny
            data[y * sw + x] = int(255 * math.exp(-(dist / width) ** 2))
    return Image.frombytes("L", (sw, sh), bytes(data)).resize((w, h), Image.BICUBIC)


def _uniform(rng: random.Random, w: int, h: int) -> Image.Image:
    return Image.frombytes("L", (w, h), rng.randbytes(w * h))


def _grain(rng: random.Random, im: Image.Image, amount: float) -> Image.Image:
    """Add monochrome grain of +-amount levels. Drawn at up to 1920 wide and scaled up, so it looks the same size
    on every screen."""
    if amount <= 0:
        return im
    w, h = im.size
    k = max(1.0, w / 1920)
    gw, gh = max(1, round(w / k)), max(1, round(h / k))
    n = Image.blend(_uniform(rng, gw, gh), _uniform(rng, gw, gh), 0.5)      # triangular: softer than uniform
    if (gw, gh) != (w, h):
        n = n.resize((w, h), Image.BILINEAR)
    lut = [max(0, min(255, round(128 + (v - 128) * amount / 64))) for v in range(256)]
    return ImageChops.add(im, n.point(lut), 1.0, -128)


def _emblem(size: int, svg: str = "clover5.svg") -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    QSvgRenderer(str(ASSETS / svg)).render(p)
    p.end()
    return img


# ---------------------------------------------------------------- the designs (ink on black)
def _grimoire(rng, w, h, u, d, o):
    glow = _radial(w, h, w / 2, h / 2, max(w, h) * 0.55, 2.2).point(lambda v: v * 0.16)
    img, p = _canvas(w, h)
    s = int(h * (0.10 + d * 0.016))
    p.setOpacity(0.92)
    p.drawImage(QPointF(w / 2 - s / 2, h / 2 - s / 2), _emblem(s))
    p.setOpacity(1)
    p.setPen(QPen(_ink(70), max(1.0, 1.2 * u)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(w / 2, h / 2), s * 0.78, s * 0.78)
    p.end()
    return ImageChops.lighter(glow, _to_l(img))


def _grain_design(rng, w, h, u, d, o):
    angle = rng.uniform(0, math.tau)
    cx, cy = w / 2 + math.cos(angle) * w * 0.45, h / 2 + math.sin(angle) * h * 0.6
    light = _radial(w, h, cx, cy, max(w, h) * 1.1, 1.5).point(lambda v: v * 0.42)
    cloud = _noise(rng, w, h, 2.5, 2).point(lambda v: v * 0.12)
    return _grain(rng, ImageChops.add(light, cloud), 10 + d * 5)


def _lines(rng, w, h, u, d, o):
    img, p = _canvas(w, h)
    gap = (40 - d * 3.2) * u
    p.translate(w / 2, h / 2)
    p.rotate(rng.choice([0, 30, 45, 60, 90, 120, 135, 150]))
    reach = math.hypot(w, h) / 2 + gap
    p.setPen(QPen(_ink(255), max(1.0, 1.4 * u)))
    y = -reach
    while y < reach:
        p.drawLine(QPointF(-reach, y), QPointF(reach, y))
        y += gap
    p.end()
    mask = _noise(rng, w, h, 1.6, 2).point(lambda v: 90 + v * 0.65)
    return ImageChops.multiply(_to_l(img), mask)


def _topo(rng, w, h, u, d, o):
    field = _noise(rng, w, h, 3, 3).filter(ImageFilter.GaussianBlur(3 * u))
    levels = 5 * (3 + d // 2)                                     # every fifth line is an index line

    def edges(n, size):
        q = field.point(lambda v: int(v // (256 / n)))
        k = max(3, int(size) | 1)
        hi = q.filter(ImageFilter.MaxFilter(k))
        return ImageChops.difference(hi, q).point(lambda v: 255 if v else 0)

    minor = edges(levels, 2 * u + 1).point(lambda v: v * 0.45)
    major = edges(levels // 5, 3.2 * u + 1)
    lines = ImageChops.lighter(minor, major).filter(ImageFilter.GaussianBlur(max(0.5, 0.6 * u)))
    return lines


def _halftone(rng, w, h, u, d, o):
    field = _noise(rng, w, h, 1.4, 2)
    down = Image.linear_gradient("L").resize((w, h), Image.BILINEAR)
    across = Image.linear_gradient("L").transpose(Image.Transpose.ROTATE_90).resize((w, h), Image.BILINEAR)
    if rng.random() < 0.5:
        down = ImageOps.flip(down)
    if rng.random() < 0.5:
        across = ImageOps.mirror(across)
    ramp = Image.blend(down, across, 0.5)                         # a diagonal ramp corner to corner
    field = Image.blend(field, ramp, 0.55)
    px = field.load()
    img, p = _canvas(w, h)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_ink(255))
    s = (46 - d * 3.2) * u
    row = 0
    y = s / 2
    while y < h + s:
        x = s / 2 + (s / 2 if row % 2 else 0)
        while x < w + s:
            v = px[min(w - 1, int(x)), min(h - 1, int(y))] / 255
            r = s * 0.5 * v ** 1.4
            if r > 0.4 * u:
                p.drawEllipse(QPointF(x, y), r, r)
            x += s
        y += s * 0.866
        row += 1
    p.end()
    return _to_l(img)


def _bauhaus(rng, w, h, u, d, o):
    img, p = _canvas(w, h)
    cols = 4 + d
    t = w / cols
    rows = math.ceil(h / t)
    oy = (h - rows * t) / 2
    p.setPen(Qt.PenStyle.NoPen)
    for r in range(rows):
        for c in range(cols):
            x, y = c * t, oy + r * t
            back = rng.choice([0, 0, 0, 22, 48])
            if back:
                p.fillRect(QRectF(x, y, t, t), _ink(back))
            p.setBrush(_ink(rng.choice([255, 255, 200, 120, 70])))
            kind = rng.randrange(8)
            if kind == 0:                                            # quarter circle from a corner
                corner = rng.randrange(4)
                cx, cy = x + (t if corner in (1, 2) else 0), y + (t if corner >= 2 else 0)
                p.drawPie(QRectF(cx - t, cy - t, 2 * t, 2 * t), [270, 180, 90, 0][corner] * 16, 90 * 16)
            elif kind == 1:                                          # half circle on an edge
                side = rng.randrange(4)
                rect = [QRectF(x, y - t / 2, t, t), QRectF(x + t / 2, y, t, t),
                        QRectF(x, y + t / 2, t, t), QRectF(x - t / 2, y, t, t)][side]
                p.drawPie(rect, [180, 90, 0, 270][side] * 16, 180 * 16)
            elif kind == 2:
                p.drawEllipse(QPointF(x + t / 2, y + t / 2), t * 0.36, t * 0.36)
            elif kind == 3:                                          # triangle
                pts = [QPointF(x, y), QPointF(x + t, y), QPointF(x + t, y + t), QPointF(x, y + t)]
                k = rng.randrange(4)
                path = QPainterPath(pts[k])
                path.lineTo(pts[(k + 1) % 4])
                path.lineTo(pts[(k + 2) % 4])
                path.closeSubpath()
                p.drawPath(path)
            elif kind == 4:                                          # three bars
                for i in range(3):
                    p.drawRect(QRectF(x + t * (0.12 + i * 0.3), y + t * 0.12, t * 0.16, t * 0.76))
            elif kind == 5:                                          # ring
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(_ink(220), t * 0.08))
                p.drawEllipse(QPointF(x + t / 2, y + t / 2), t * 0.3, t * 0.3)
                p.setPen(Qt.PenStyle.NoPen)
            # 6, 7: left empty, so the grid breathes
    p.end()
    return _to_l(img)


def _fog(rng, w, h, u, d, o):
    sw, sh = 192, max(8, round(192 * h / w))
    img, p = _canvas(sw, sh)
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(4 + d):
        p.setBrush(_ink(rng.uniform(50, 120 + d * 12)))
        rx, ry = rng.uniform(0.12, 0.4) * sw, rng.uniform(0.12, 0.35) * sw
        p.setOpacity(rng.uniform(0.35, 0.8))
        p.drawEllipse(QPointF(rng.uniform(0, sw), rng.uniform(0, sh)), rx, ry)
    p.end()
    soft = _to_l(img).filter(ImageFilter.GaussianBlur(sw / 14))
    return soft.resize((w, h), Image.BICUBIC)


def _clover(rng, w, h, u, d, o):
    img, p = _canvas(w, h)
    s = (300 - d * 20) * u
    size = int(s * 0.46)
    mark = _emblem(size, "clover4.svg")
    row = 0
    y = s / 2
    while y < h + s:
        x = s / 2 + (s / 2 if row % 2 else 0)
        while x < w + s:
            p.save()
            p.translate(x, y)
            p.rotate(rng.uniform(-25, 25))
            p.setOpacity(1.0 if rng.random() < 0.07 else rng.uniform(0.14, 0.3))
            p.drawImage(QPointF(-size / 2, -size / 2), mark)
            p.restore()
            x += s
        y += s * 0.75
        row += 1
    p.end()
    return _to_l(img)


def _type(rng, w, h, u, d, o):
    word = " ".join((o.get("text") or "").split()) or "GRIMOIRE"
    img, p = _canvas(w, h)
    rows = 2 + d // 2
    rh = h / rows
    font = QFont("IBM Plex Sans Condensed")
    font.setWeight(QFont.Weight.Bold)
    font.setPixelSize(max(8, int(rh * 0.92)))
    fm = QFontMetricsF(font)
    unit = word + "  "
    span = max(1.0, fm.horizontalAdvance(unit))
    line = unit * (int(w / span) + 3)
    bright = rng.randrange(rows)
    for r in range(rows):
        base = r * rh + (rh + fm.capHeight()) / 2
        path = QPainterPath()
        path.addText(QPointF(-rng.uniform(0, span), base), font, line)
        if r % 2 == 0:
            p.fillPath(path, _ink(255 if r == bright else 54))
        else:
            p.strokePath(path, QPen(_ink(255 if r == bright else 120), max(1.0, 1.6 * u)))
    p.end()
    return _to_l(img)


def _ridges(rng, w, h, u, d, o):
    img, p = _canvas(w, h)
    n = 26 + d * 5
    top, bottom = h * 0.2, h * 0.86
    gap = (bottom - top) / n
    samples = 220
    pen = QPen(_ink(240), max(1.0, 1.3 * u))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    for i in range(n):
        lattice = [rng.random() for _ in range(26)]
        peaks = [(rng.uniform(0.35, 0.65), rng.uniform(0.03, 0.08), rng.uniform(0.3, 1.0)) for _ in range(3)]
        y0 = top + i * gap
        path = QPainterPath(QPointF(-2, y0))
        for k in range(samples + 1):
            t = k / samples
            f = t * (len(lattice) - 1)
            a, b = lattice[int(f)], lattice[min(len(lattice) - 1, int(f) + 1)]
            s = f - int(f)
            v = a + (b - a) * (3 - 2 * s) * s * s
            env = math.exp(-((t - 0.5) / 0.17) ** 2)
            bump = sum(m * math.exp(-((t - c) / wd) ** 2) for c, wd, m in peaks)
            lift = gap * (0.6 * v + 9 * env * (0.35 * v + bump))
            path.lineTo(QPointF(t * (w + 4) - 2, y0 - lift))
        path.lineTo(QPointF(w + 2, h + 2))
        path.lineTo(QPointF(-2, h + 2))
        path.closeSubpath()
        p.fillPath(path, _ink(0))
        p.strokePath(path, pen)
    p.end()
    return _to_l(img)


def _rings(rng, w, h, u, d, o):
    img, p = _canvas(w, h)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    p.setBrush(Qt.BrushStyle.NoBrush)
    gap = (34 - d * 2.4) * u
    far = math.hypot(w, h) * 1.2
    centers = [(rng.uniform(0.2, 0.45) * w, rng.uniform(0.3, 0.7) * h),
               (rng.uniform(0.55, 0.8) * w, rng.uniform(0.3, 0.7) * h)]
    for cx, cy in centers:
        p.setPen(QPen(_ink(130), max(1.0, 1.4 * u)))
        r = gap
        while r < far:
            p.drawEllipse(QPointF(cx, cy), r, r)
            r += gap
    p.end()
    fade = _radial(w, h, w / 2, h / 2, max(w, h) * 0.75, 0.8).point(lambda v: 70 + v * 0.73)
    return ImageChops.multiply(_to_l(img), fade)


def _maze(rng, w, h, u, d, o):
    img, p = _canvas(w, h)
    t = (120 - d * 8) * u
    pen = QPen(_ink(230), t * 0.11)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for r in range(math.ceil(h / t) + 1):
        for c in range(math.ceil(w / t) + 1):
            x, y = c * t, r * t
            if rng.random() < 0.5:
                p.drawArc(QRectF(x - t / 2, y - t / 2, t, t), 270 * 16, 90 * 16)
                p.drawArc(QRectF(x + t / 2, y + t / 2, t, t), 90 * 16, 90 * 16)
            else:
                p.drawArc(QRectF(x + t / 2, y - t / 2, t, t), 180 * 16, 90 * 16)
                p.drawArc(QRectF(x - t / 2, y + t / 2, t, t), 0, 90 * 16)
    p.end()
    mask = _noise(rng, w, h, 1.5, 2).point(lambda v: 60 + v * 0.77)
    return ImageChops.multiply(_to_l(img), mask)


def _stars(rng, w, h, u, d, o):
    band = _band(w, h, rng.uniform(-0.6, 0.6), h * 0.16)
    clouds = _noise(rng, w, h, 3, 3)
    milky = ImageChops.multiply(band, clouds).point(lambda v: v * 0.22)
    img, p = _canvas(w, h)
    p.setPen(Qt.PenStyle.NoPen)
    count = int((300 + d * 260) * (w * h) / (1920 * 1080) / max(u, 0.01) ** 2)
    bpx = band.load()
    for _ in range(count):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        dense = bpx[min(w - 1, int(x)), min(h - 1, int(y))] / 255
        if rng.random() > 0.35 + 0.65 * dense:
            continue
        b = rng.random() ** 2.6
        p.setBrush(_ink(40 + 215 * b))
        r = (0.5 + 1.3 * b) * u
        p.drawEllipse(QPointF(x, y), r, r)
    p.end()
    stars = _to_l(img)
    glow = stars.filter(ImageFilter.GaussianBlur(3 * u)).point(lambda v: min(255, v * 3))
    return ImageChops.lighter(ImageChops.add(milky, stars), glow)


def _grid(rng, w, h, u, d, o):
    img, p = _canvas(w, h)
    t = (92 - d * 6) * u
    ox, oy = (w / 2) % (t * 4), (h / 2) % (t * 4)
    for k in range(-4, math.ceil(max(w, h) / t) + 5):
        major = k % 4 == 0
        p.setPen(QPen(_ink(80 if major else 34), max(1.0, (1.4 if major else 1.0) * u)))
        x, y = ox + k * t, oy + k * t
        p.drawLine(QPointF(x, 0), QPointF(x, h))
        p.drawLine(QPointF(0, y), QPointF(w, y))
    p.setPen(QPen(_ink(210), max(1.0, 1.6 * u)))
    arm = t * 0.22
    for i in range(-1, math.ceil(w / (t * 4)) + 2):
        for j in range(-1, math.ceil(h / (t * 4)) + 2):
            x, y = ox + i * t * 4, oy + j * t * 4
            p.drawLine(QPointF(x - arm, y), QPointF(x + arm, y))
            p.drawLine(QPointF(x, y - arm), QPointF(x, y + arm))
    p.end()
    fade = _radial(w, h, w / 2, h / 2, max(w, h) * 0.8, 0.7).point(lambda v: 40 + v * 0.85)
    return ImageChops.multiply(_to_l(img), fade)


def _spot(rng, w, h, u, d, o):
    cx = rng.uniform(0.15, 0.85) * w
    cy = rng.choice([-0.25, -0.1, 1.1]) * h
    light = _radial(w, h, cx, cy, max(w, h) * (0.6 + d * 0.06), 1.9)
    return light.point(lambda v: v * 0.75)


def _bitmap(rng, w, h, u, d, o):
    px = max(1, round((1 + d * 0.5) * u))
    sw, sh = max(1, w // px), max(1, h // px)
    field = Image.blend(_noise(rng, sw, sh, 1.3, 3),
                        Image.linear_gradient("L").rotate(rng.choice([0, 90, 180, 270])).resize((sw, sh)), 0.5)
    bayer = [[0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26], [12, 44, 4, 36, 14, 46, 6, 38],
             [60, 28, 52, 20, 62, 30, 54, 22], [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
             [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]]
    tile = Image.new("L", (8, 8))
    tile.putdata([int((bayer[y][x] + 0.5) * 4) for y in range(8) for x in range(8)])
    thresh = Image.new("L", (sw, sh))
    for y in range(0, sh, 8):
        for x in range(0, sw, 8):
            thresh.paste(tile, (x, y))
    field = field.point(lambda v: int(v * 0.85))
    bits = ImageChops.subtract(field, thresh).point(lambda v: 255 if v else 0)
    return bits.resize((sw * px, sh * px), Image.NEAREST).crop((0, 0, w, h)) if (sw * px, sh * px) != (w, h) \
        else bits.resize((w, h), Image.NEAREST)


DRAW = {"grimoire": _grimoire, "grain": _grain_design, "lines": _lines, "topo": _topo, "halftone": _halftone,
        "bauhaus": _bauhaus, "fog": _fog, "clover": _clover, "type": _type, "ridges": _ridges, "rings": _rings,
        "maze": _maze, "stars": _stars, "grid": _grid, "spot": _spot, "bitmap": _bitmap}


# ---------------------------------------------------------------- render + save
def options(o: dict) -> dict:
    """Saved options with defaults filled in and out-of-range values pulled back in."""
    o = {**DEFAULTS, **(o or {})}
    o["tone"] = o["tone"] if o["tone"] in TONES else "dark"
    o["size"] = o["size"] if o["size"] in SIZES else "screen"
    for k, lo, hi in (("density", 1, 10), ("grain", 0, 10), ("seed", 1, 9999)):
        try:
            o[k] = max(lo, min(hi, int(o[k])))
        except (TypeError, ValueError):
            o[k] = DEFAULTS[k]
    o["text"] = str(o["text"])[:60]
    return o


def render(design_id: str, o: dict, w: int, h: int) -> Image.Image:
    """The finished wallpaper as a grayscale image of w x h."""
    o = options(o)
    rng = random.Random(f"{design_id}:{o['seed']}")
    u = w / 1920
    ink = DRAW[design_id](rng, w, h, u, o["density"], o).convert("L")
    if ink.size != (w, h):
        ink = ink.resize((w, h), Image.BICUBIC)
    _, bg, fg = TONES[o["tone"]]
    toned = ink.point([round(bg + (fg - bg) * v / 255) for v in range(256)])
    return _grain(random.Random(f"grain:{o['seed']}"), toned, 1.6 + o["grain"] * 4)


def to_qimage(im: Image.Image) -> QImage:
    im = im.convert("RGB")
    return QImage(im.tobytes(), im.width, im.height, im.width * 3, QImage.Format.Format_RGB888).copy()


def pixels(size: str, screen: tuple[int, int]) -> tuple[int, int]:
    if size == "screen":
        return screen
    w, h = size.split("x")
    return int(w), int(h)


def save(design_id: str, o: dict, w: int, h: int) -> Path:
    """Render at w x h into the MuraL library and return the file. The name carries the settings, so the same
    design made twice is the same file (reused, never a pile of copies) and a different one never overwrites it."""
    o = options(o)
    key = {k: o[k] for k in ("tone", "density", "grain", "seed")}
    if design_id == "type":
        key["text"] = o["text"]
    digest = hashlib.sha1(json.dumps([design_id, key, w, h], sort_keys=True).encode()).hexdigest()[:6]
    path = library.LIBRARY / f"{IDS[design_id].name} {o['seed']} {w}x{h} {digest}.png"
    if path.exists():
        return path
    tmp = path.with_name(path.name + ".part")
    render(design_id, o, w, h).save(tmp, "PNG", optimize=False, compress_level=6)
    tmp.replace(path)
    return path
