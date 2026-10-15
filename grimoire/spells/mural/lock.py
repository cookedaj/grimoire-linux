# SPDX-License-Identifier: GPL-3.0-or-later
"""Lock screen tab: black & white backgrounds for Plasma's lock screen (Negative, nine drawn patterns or any
library image), with dim, blur and clock options.

Only the background and the stock lock screen's own options are changed; the unlock UI itself stays
Plasma's, so a bad design can never lock you out.
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
from PySide6.QtCore import QDateTime, QLocale, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import tr, tr_noop
from grimoire.paths import ASSETS, DATA
from grimoire.spells.mural import library
from grimoire.spells.mural.kde import kwrite
from grimoire.spells.mural.screens import Design, ScreenTab, WrapCheck
from grimoire.widgets import Slider

OUT = DATA / "mural" / "screens"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 2560, 1440

DESIGNS = [
    Design("negative", tr_noop("grimoire.spells.mural.lock", "Negative"),
           tr_noop("grimoire.spells.mural.lock",
                   "Anti-Magic inverted: white Asta and wings on pure black. Striking but calm.")),
    Design("eclipse", tr_noop("grimoire.spells.mural.lock", "Eclipse"),
           tr_noop("grimoire.spells.mural.lock", "A black sun with a soft white corona; the clock sits inside it.")),
    Design("contour", tr_noop("grimoire.spells.mural.lock", "Contour"),
           tr_noop("grimoire.spells.mural.lock", "Hairline topographic lines drifting across the dark.")),
    Design("halftone", tr_noop("grimoire.spells.mural.lock", "Halftone"),
           tr_noop("grimoire.spells.mural.lock", "A grid of dots swelling from one corner, like newsprint.")),
    Design("ripple", tr_noop("grimoire.spells.mural.lock", "Ripple"),
           tr_noop("grimoire.spells.mural.lock", "Thin rings spreading out from below the screen and fading.")),
    Design("pinstripe", tr_noop("grimoire.spells.mural.lock", "Pinstripe"),
           tr_noop("grimoire.spells.mural.lock", "Fine scanlines lit from the bottom, dark at the top.")),
    Design("spotlight", tr_noop("grimoire.spells.mural.lock", "Spotlight"),
           tr_noop("grimoire.spells.mural.lock", "One soft pool of light from above, with film grain.")),
    Design("clover", tr_noop("grimoire.spells.mural.lock", "Clover"),
           tr_noop("grimoire.spells.mural.lock", "A huge faint four-leaf clover watermark in the corner.")),
    Design("void", tr_noop("grimoire.spells.mural.lock", "Void"),
           tr_noop("grimoire.spells.mural.lock", "Nearly pure black with the faintest glow. Nothing else.")),
    Design("fog", tr_noop("grimoire.spells.mural.lock", "Fog"),
           tr_noop("grimoire.spells.mural.lock", "Lighter: gray mist fading to black, grainy like film.")),
]


@lru_cache(maxsize=16)
def _covered(name: str, w: int, h: int) -> Image.Image | None:
    """Library image, grayscale, cropped to w x h. Cached: sliders re-render often."""
    p = library.LIBRARY / name
    return _cover(Image.open(p).convert("L"), w, h) if p.exists() else None


def _cover(im: Image.Image, w: int, h: int) -> Image.Image:
    s = max(w / im.width, h / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def _clover_mask(size: int, svg: str = "clover5.svg") -> Image.Image:
    """A Grimoire clover emblem (clover5.svg / clover4.svg) rendered as an L mask (white = clover)."""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    QSvgRenderer(str(ASSETS / svg)).render(p)
    p.end()
    alpha = img.convertToFormat(QImage.Format.Format_Alpha8)
    # Qt pads each row to 4 bytes, so pass the real row stride
    return Image.frombuffer("L", (size, size), bytes(alpha.constBits()), "raw", "L", alpha.bytesPerLine(), 1).copy()


def _noise(w: int, h: int, seed: int) -> Image.Image:
    """Repeatable white noise (previews must not flicker between renders)."""
    return Image.frombytes("L", (w, h), random.Random(seed).randbytes(w * h))


def _smooth(w: int, h: int, seed: int, cells: int) -> Image.Image:
    """Soft value noise: a coarse random grid blown up smoothly, two octaves."""
    out = None
    for i, n in enumerate((cells, cells * 3)):
        gw, gh = n + 2, max(2, round(n * h / w)) + 2
        layer = _noise(gw, gh, seed + i).resize((w, h), Image.BICUBIC, box=(1, 1, gw - 1, gh - 1))
        out = layer if out is None else Image.blend(out, layer, 0.28)
    return ImageOps.autocontrast(out.filter(ImageFilter.GaussianBlur(w / 400)))


def _radial(w: int, h: int, cx: float, cy: float, rx: float, ry: float) -> Image.Image:
    """255 at (cx, cy) falling to 0 at radius (rx, ry), smooth."""
    # radial_gradient is 0 in the middle and 181 at the edge midpoints (it keeps rising into the corners)
    g = Image.radial_gradient("L").point(lambda v: max(0, 255 - v * 255 // 181))
    g = g.resize((max(1, int(rx * 2)), max(1, int(ry * 2))), Image.BILINEAR)
    im = Image.new("L", (w, h), 0)
    im.paste(g, (int(cx - rx), int(cy - ry)))
    return im


def _supersampled(w: int, h: int, draw, ss: int = 2) -> Image.Image:
    """Shapes drawn at ss x the size, then scaled down: smooth hairlines and dots."""
    im = Image.new("L", (w * ss, h * ss), 0)
    draw(ImageDraw.Draw(im), w * ss, h * ss, ss)
    return im.resize((w, h), Image.LANCZOS)


def _contour(w: int, h: int) -> Image.Image:
    """Topographic hairlines: marching squares over a field of soft hills, drawn antialiased by Qt
    (contours traced from pixels would come out stair-stepped)."""
    rng = random.Random(7)
    hills = [(rng.uniform(-0.1, 1.1), rng.uniform(-0.1, 1.1), rng.uniform(0.08, 0.26), rng.uniform(-1, 1))
             for _ in range(22)]
    gw, gh = 192, 108
    aspect = w / h

    def field(x, y):
        return sum(a * math.exp(-(((x - hx) * aspect) ** 2 + (y - hy) ** 2) / (s * s)) for hx, hy, s, a in hills)

    grid = [[field(i / gw, j / gh) for i in range(gw + 1)] for j in range(gh + 1)]
    lo, hi = min(map(min, grid)), max(map(max, grid))
    levels = 26
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    sx, sy = w / gw, h / gh
    for k in range(1, levels):
        v = lo + (hi - lo) * k / levels
        path = QPainterPath()
        for j in range(gh):
            row, nxt = grid[j], grid[j + 1]
            for i in range(gw):
                c = (row[i], row[i + 1], nxt[i + 1], nxt[i])           # corners clockwise from top-left
                pts = []
                for (a, b), (x0, y0, x1, y1) in zip(((0, 1), (1, 2), (2, 3), (3, 0)),
                                                    ((i, j, i + 1, j), (i + 1, j, i + 1, j + 1),
                                                     (i + 1, j + 1, i, j + 1), (i, j + 1, i, j))):
                    if (c[a] < v) != (c[b] < v):
                        t = (v - c[a]) / (c[b] - c[a])
                        pts.append(QPointF((x0 + (x1 - x0) * t) * sx, (y0 + (y1 - y0) * t) * sy))
                for n in range(0, len(pts) - 1, 2):
                    path.moveTo(pts[n])
                    path.lineTo(pts[n + 1])
        major = k % 5 == 0
        tone = int(70 + 130 * k / levels) + (40 if major else 0)
        pen = QPen(QColor(tone, tone, tone), (2.4 if major else 1.3) * w / W * 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawPath(path)
    p.end()
    g = img.convertToFormat(QImage.Format.Format_Grayscale8)
    return Image.frombuffer("L", (w, h), bytes(g.constBits()), "raw", "L", g.bytesPerLine(), 1).copy()


@lru_cache(maxsize=24)
def _pattern(design_id: str, w: int, h: int) -> Image.Image:
    """Grimoire's own drawn backgrounds, grayscale. Cached: the sliders re-render often."""
    u = w / W                                            # 1 at the full 2560 size
    if design_id == "eclipse":
        cx, cy, r = w / 2, h * 0.30, h * 0.20
        glow = _radial(w, h, cx, cy, r * 2.6, r * 2.6).point(lambda v: int(235 * (v / 255) ** 3.2))
        ring = _supersampled(w, h, lambda d, sw, sh, ss: d.ellipse(
            (cx * ss - r * ss, cy * ss - r * ss, cx * ss + r * ss, cy * ss + r * ss), outline=255,
            width=max(1, int(3 * u * ss))))
        im = ImageChops.lighter(glow, ring.filter(ImageFilter.GaussianBlur(2 * u)))
        disc = _supersampled(w, h, lambda d, sw, sh, ss: d.ellipse(
            (cx * ss - r * ss, cy * ss - r * ss, cx * ss + r * ss, cy * ss + r * ss), fill=255))
        return Image.composite(Image.new("L", (w, h), 4), im, disc)
    if design_id == "contour":
        return _contour(w, h)
    if design_id == "halftone":
        def dots(d, sw, sh, ss):
            step = 30 * u * ss
            cols, rows = int(sw / step) + 2, int(sh / step) + 2
            for j in range(rows):
                for i in range(cols):
                    x, y = i * step + (step / 2 if j % 2 else 0), j * step
                    t = max(0.0, 1 - math.hypot(sw - x, sh - y) / (sw * 0.95))     # from the bottom-right
                    rad = step * 0.46 * t ** 1.6
                    if rad > 0.4 * ss:
                        d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=int(70 + 150 * t))
        return _supersampled(w, h, dots)
    if design_id == "ripple":
        def rings(d, sw, sh, ss):
            cx, cy, k = sw * 0.5, sh * 1.18, 0
            r = sh * 0.30
            while r < sw * 1.1:
                fade = max(0.0, 1 - (r - sh * 0.3) / (sw * 0.75))
                d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=int(30 + 170 * fade ** 1.5),
                          width=max(1, int((2.2 if k % 4 == 0 else 1.1) * u * ss)))
                r += 34 * u * ss * (1 + k * 0.035)
                k += 1
        return _supersampled(w, h, rings)
    if design_id == "pinstripe":
        ramp = Image.linear_gradient("L").resize((w, h)).point(lambda v: int(255 * (v / 255) ** 1.8))
        def stripes(d, sw, sh, ss):
            gap = max(2, round(6 * u * ss))
            for y in range(0, sh, gap):
                d.line((0, y, sw, y), fill=255, width=max(1, round(u * ss)))
        lines = _supersampled(w, h, stripes)
        return ImageChops.multiply(lines, ramp).point(lambda v: int(v * 0.75))
    if design_id == "spotlight":
        light = _radial(w, h, w / 2, -h * 0.15, w * 0.55, h * 1.05).point(lambda v: int(150 * (v / 255) ** 1.6))
        grain = _noise(w, h, 3).point(lambda v: (v - 128) // 11 + 12)
        return ImageChops.subtract(ImageChops.add(light, grain), Image.new("L", (w, h), 12))
    if design_id == "clover":
        size = int(h * 1.25)
        mask = _clover_mask(size, "clover4.svg").rotate(18, Image.BICUBIC)
        im = Image.new("L", (w, h), 6)
        im.paste(28, (int(w - size * 0.72), int(h - size * 0.70)), mask)
        small = _clover_mask(max(8, int(h * 0.05)), "clover4.svg")
        im.paste(70, (int(w * 0.06), int(h * 0.07)), small)
        return im
    if design_id == "void":
        return _radial(w, h, w / 2, h * 0.45, w * 0.7, h * 0.85).point(lambda v: int(v / 255 * 14))
    if design_id == "fog":
        ramp = ImageOps.invert(Image.linear_gradient("L")).resize((w, h)).point(
            lambda v: int(205 * (v / 255) ** 1.5))
        mist = _smooth(w, h, 11, 3).point(lambda v: v // 5)
        grain = _noise(w, h, 5).point(lambda v: (v - 128) // 13 + 10)
        return ImageChops.subtract(ImageChops.add(ImageChops.add(ramp, mist), grain), Image.new("L", (w, h), 18))
    return Image.new("L", (w, h), 0)


def render(design_id: str, dim: int, blur: int, w=W, h=H) -> Image.Image:
    """Grayscale lock background. dim 0..90 (%), blur 0..40 (px at 2560 wide)."""
    scale = w / W
    if design_id.startswith("img:"):                    # any image in the MuraL library
        src = _covered(design_id[4:], w, h)
        im = src.copy() if src else Image.new("L", (w, h), 0)
    elif design_id == "negative":                       # Anti-Magic, inverted
        src = _covered("anti-magic.png", w, h)
        im = ImageOps.invert(src).point(lambda v: int(v * 0.7)) if src else Image.new("L", (w, h), 0)
    else:
        im = _pattern(design_id, w, h).copy()
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur * scale))
    if dim:
        im = im.point(lambda v: int(v * (1 - dim / 100)))
    return im


def to_qimage(im: Image.Image) -> QImage:
    im = im.convert("RGB")
    return QImage(im.tobytes(), im.width, im.height, im.width * 3, QImage.Format.Format_RGB888).copy()


class LockTab(ScreenTab):
    key = "lock"
    context = "grimoire.spells.mural.lock"
    subtitle = tr_noop("grimoire.spells.mural.lock", "Background for the lock screen. Plasma's own clock and password "
                       "field sit on top — the preview mocks their position.")
    apply_label = tr_noop("grimoire.spells.mural.lock", "Apply to lock screen")
    store = ["wallhaven-bw", "wallhaven-bc", "wallpaper"]

    def designs(self):
        pics = [p for p in library.items() if not library.is_video(p)]
        blurb = tr("grimoire.spells.mural.lock", "From your MuraL library (wallpapers you add or install from "
                                                 "Community show up here).")
        return DESIGNS + [Design(f"img:{p.name}", p.stem, blurb) for p in pics]

    def build_options(self, lay):
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        self.dim = Slider(0, 90, "%", self.changed)
        self.blur = Slider(0, 40, " px", self.changed)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.lock", "Dim")), 0, 0)
        grid.addWidget(self.dim, 0, 1)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.lock", "Blur")), 1, 0)
        grid.addWidget(self.blur, 1, 1)
        lay.addLayout(grid)
        self.clock = WrapCheck(tr("grimoire.spells.mural.lock", "Always show the clock"))
        self.clock_idle = WrapCheck(tr("grimoire.spells.mural.lock", "Hide clock when idle"))
        self.media = WrapCheck(tr("grimoire.spells.mural.lock", "Show media controls"))
        for c in (self.clock, self.clock_idle, self.media):
            c.toggled.connect(self.changed)
            lay.addWidget(c)

    def options(self):
        return {"dim": self.dim.value(), "blur": self.blur.value(), "clock": self.clock.isChecked(),
                "clock_idle": self.clock_idle.isChecked(), "media": self.media.isChecked()}

    def set_options(self, o):
        self.dim.setValue(o.get("dim", 20))
        self.blur.setValue(o.get("blur", 0))
        self.clock.setChecked(o.get("clock", True))
        self.clock_idle.setChecked(o.get("clock_idle", False))
        self.media.setChecked(o.get("media", False))

    def preview(self, design, o):
        img = to_qimage(render(design.id, o.get("dim", 20), o.get("blur", 0), 1280, 720))
        if o.get("clock", True):
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            now, locale = QDateTime.currentDateTime(), QLocale()      # Plasma shows them in your language
            p.setPen(QColor(255, 255, 255, 235))
            p.setFont(QFont("IBM Plex Sans", 56, QFont.Weight.Light))
            p.drawText(QRect(0, 170, 1280, 90), Qt.AlignmentFlag.AlignHCenter,
                       locale.toString(now.time(), QLocale.FormatType.ShortFormat))
            p.setFont(QFont("IBM Plex Sans", 15))
            p.setPen(QColor(255, 255, 255, 190))
            p.drawText(QRect(0, 262, 1280, 30), Qt.AlignmentFlag.AlignHCenter,
                       locale.toString(now.date(), QLocale.FormatType.LongFormat))
            p.end()
        return img

    def apply(self, design, o):
        path = OUT / ("lock-" + design.id.replace("img:", "img-").replace("/", "_") + ".png")
        render(design.id, o["dim"], o["blur"]).save(path, optimize=True)
        url = path.as_uri()
        image = ["Greeter", "Wallpaper", "org.kde.image", "General"]
        lnf = ["Greeter", "LnF", "General"]
        kwrite("kscreenlockerrc", "Greeter", "WallpaperPlugin", "org.kde.image")
        kwrite("kscreenlockerrc", image, "Image", url)
        kwrite("kscreenlockerrc", image, "PreviewImage", url)
        for key, opt in (("alwaysShowClock", "clock"), ("hideClockWhenIdle", "clock_idle"),
                         ("showMediaControls", "media")):
            kwrite("kscreenlockerrc", lnf, key, str(o[opt]).lower(), "bool")
        return tr("grimoire.spells.mural.lock", "Applied ✓  Lock with Meta+L to see it.")
