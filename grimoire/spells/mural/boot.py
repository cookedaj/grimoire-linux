# SPDX-License-Identifier: GPL-3.0-or-later
"""Boot tab: Grimoire's Plymouth boot animations, built on Plymouth's stock "two-step" engine
(the one Kubuntu's own logo uses), so password prompts and messages keep working.

Each design is a looping throbber rendered here frame by frame (throbber-NNNN.png); every design installs the
same way, as the "grimoire" theme, so the root helper needs nothing new. Installing needs root (pkexec).
"""
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QMovie, QPainter
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import tr, tr_noop

from grimoire.paths import CACHE
from grimoire.spells.mural.lock import _clover_mask, to_qimage
from grimoire.spells.mural.kde import run_root
from grimoire.spells.mural.screens import (Choice, Design, ScreenTab, WrapButton, WrapCheck, community_designs,
                                           community_entry)

WORK = CACHE / "boot"
FRAMES = 48                                   # two-step loops the throbber; ~1.6 s at 30 fps
SIZES = {tr_noop("grimoire.spells.mural.boot", "Small"): 0.75, tr_noop("grimoire.spells.mural.boot", "Medium"): 1.0,
         tr_noop("grimoire.spells.mural.boot", "Large"): 1.35}
POSITIONS = {tr_noop("grimoire.spells.mural.boot", "Center"): 0.5, tr_noop("grimoire.spells.mural.boot", "Lower"): 0.62}
DEFAULTS = {"size": "Medium", "position": "Center", "firmware_logo": False}
SS = 3                                        # supersampling for smooth edges

DESIGNS = [
    Design("pulse", tr_noop("grimoire.spells.mural.boot", "Pulse"),
           tr_noop("grimoire.spells.mural.boot", "The five-leaf clover breathing slowly in the dark.")),
    Design("arc", tr_noop("grimoire.spells.mural.boot", "Arc"),
           tr_noop("grimoire.spells.mural.boot", "A hairline ring with one bright arc sweeping round it.")),
    Design("orbit", tr_noop("grimoire.spells.mural.boot", "Orbit"),
           tr_noop("grimoire.spells.mural.boot", "The clover standing still while a small dot circles it.")),
    Design("dots", tr_noop("grimoire.spells.mural.boot", "Dots"),
           tr_noop("grimoire.spells.mural.boot", "Three dots swelling and fading one after another.")),
    Design("scanner", tr_noop("grimoire.spells.mural.boot", "Scanner"),
           tr_noop("grimoire.spells.mural.boot", "A short bright segment gliding back and forth along a hairline.")),
    Design("ripple", tr_noop("grimoire.spells.mural.boot", "Ripple"),
           tr_noop("grimoire.spells.mural.boot", "Rings spreading out from the middle and fading away.")),
    Design("spin", tr_noop("grimoire.spells.mural.boot", "Spin"),
           tr_noop("grimoire.spells.mural.boot", "The four-leaf clover turning slowly on its stem.")),
    Design("ticks", tr_noop("grimoire.spells.mural.boot", "Ticks"),
           tr_noop("grimoire.spells.mural.boot",
                   "Twelve short ticks in a circle, the bright one leaving a fading trail.")),
    Design("eclipse", tr_noop("grimoire.spells.mural.boot", "Eclipse"),
           tr_noop("grimoire.spells.mural.boot", "A white moon crossed again and again by a black shadow.")),
]
# frames per loop when a design wants a slower one than FRAMES (two-step plays the throbber at ~30 fps)
LOOP = {"spin": 96, "eclipse": 72}

_clover_cache: dict[tuple[str, int], Image.Image] = {}


def _clover(size: int, leaves=5) -> Image.Image:
    key = (str(leaves), size)
    if key not in _clover_cache:
        _clover_cache[key] = _clover_mask(size, "clover5.svg" if leaves == 5 else "clover4.svg")
    return _clover_cache[key]


def _rgba(w, h):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def _paste_white(canvas: Image.Image, mask: Image.Image, center, alpha=1.0):
    m = mask.point(lambda v: int(v * alpha))
    x, y = int(center[0] - m.width / 2), int(center[1] - m.height / 2)
    canvas.paste(Image.new("RGBA", m.size, (255, 255, 255, 255)), (x, y), m)


def _done(img: Image.Image, w, h) -> Image.Image:
    return img.resize((w, h), Image.LANCZOS)


def frames(design_id: str, scale: float) -> list[Image.Image]:
    """The looping animation for one design, as RGBA frames on transparent."""
    n = LOOP.get(design_id, FRAMES)
    return [_frame(design_id, scale, i / n) for i in range(n)]


def _frame(design_id: str, scale: float, t: float) -> Image.Image:
    """One frame at t (0..1 around the loop). Drawn SS times larger, then scaled down for smooth edges."""
    wave = 0.5 - 0.5 * math.cos(2 * math.pi * t)          # 0→1→0
    w = h = int(200 * scale)
    if design_id == "scanner":
        w, h = int(320 * scale), int(40 * scale)
    c = _rgba(w, h)
    d = ImageDraw.Draw(c)
    k = scale * SS                                        # design units → canvas pixels
    cx, cy = w * SS / 2, h * SS / 2
    white = lambda a: (255, 255, 255, int(255 * a))

    def circle(r, **kw):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), **kw)

    if design_id == "arc":
        r, lw = 62 * k, max(1, int(2.2 * k))
        circle(r, outline=white(0.18), width=lw)
        start = t * 360 - 90
        d.arc((cx - r, cy - r, cx + r, cy + r), start, start + 80, fill=white(1), width=lw)
    elif design_id == "orbit":
        circle(70 * k, outline=white(0.16), width=max(1, int(1.6 * k)))
        _paste_white(c, _clover(int(64 * k)), (cx, cy), 0.95)
        a = 2 * math.pi * t - math.pi / 2
        x, y, r = cx + 70 * k * math.cos(a), cy + 70 * k * math.sin(a), 6 * k
        d.ellipse((x - r, y - r, x + r, y + r), fill=white(1))
    elif design_id == "dots":
        for i in range(3):
            v = 0.5 - 0.5 * math.cos(2 * math.pi * (t - i / 6))
            x, r = cx + (i - 1) * 34 * k, (5 + 4 * v) * k
            d.ellipse((x - r, cy - r, x + r, cy + r), fill=white(0.3 + 0.7 * v))
    elif design_id == "scanner":
        lw = max(1, int(1.6 * k))
        d.line((0, cy, w * SS, cy), fill=white(0.16), width=lw)
        pos = 0.5 - 0.5 * math.cos(2 * math.pi * t)       # eases in and out at each end
        seg = 70 * k
        x = pos * (w * SS - seg)
        d.line((x, cy, x + seg, cy), fill=white(1), width=max(1, int(3 * k)))
    elif design_id == "ripple":
        for i in range(3):
            p = (t + i / 3) % 1
            r = (18 + 78 * p) * k
            circle(r, outline=white((1 - p) ** 1.5), width=max(1, int(2 * k)))
        circle(7 * k, fill=white(1))
    elif design_id == "spin":
        m = _clover(int(104 * k), leaves=4).rotate(-360 * t, Image.BICUBIC)
        _paste_white(c, m, (cx, cy))
    elif design_id == "ticks":
        head = t * 12
        for i in range(12):
            age = (head - i) % 12                            # 0 = the bright one, then its trail
            a = 2 * math.pi * i / 12 - math.pi / 2
            r0, r1 = 40 * k, 66 * k
            d.line((cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
                   fill=white(max(0.14, 1 - age / 7)), width=max(1, int(5 * k)))
    elif design_id == "eclipse":
        r = 44 * k
        circle(r, fill=white(1))
        sx = cx + (2 * t - 1) * 2.2 * r * 1.05              # the shadow crosses from left to right
        d.ellipse((sx - r * 1.02, cy - r * 1.02, sx + r * 1.02, cy + r * 1.02), fill=(0, 0, 0, 0))
        circle(r, outline=white(0.22), width=max(1, int(1.6 * k)))
    else:                                                 # Pulse: the clover breathing
        size = int(96 * k * (0.96 + 0.06 * wave))
        _paste_white(c, _clover(size), (cx, cy), 0.75 + 0.25 * wave)
    return _done(c, w, h)


def preview(design_id: str, opts: dict, frame: int = FRAMES // 3, w=1280, h=720) -> Image.Image:
    o = {**DEFAULTS, **opts}
    scale = SIZES[o["size"]] * (w / 1920)
    f = frames(design_id, scale)[frame]
    bg = Image.new("RGB", (w, h), (0, 0, 0))
    bg.paste(f, (int(w / 2 - f.width / 2), int(h * POSITIONS[o["position"]] - f.height / 2)), f)
    return bg


def _dialog_assets(dest: Path):
    """Minimal black & white password box assets for two-step."""
    entry = Image.new("RGBA", (360, 40), (0, 0, 0, 0))
    ImageDraw.Draw(entry).rectangle((0, 39, 359, 39), fill=(200, 200, 200, 255))
    entry.save(dest / "entry.png")
    bullet = Image.new("RGBA", (14, 14), (0, 0, 0, 0))
    ImageDraw.Draw(bullet).ellipse((3, 3, 10, 10), fill=(255, 255, 255, 255))
    bullet.save(dest / "bullet.png")
    lock = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    lock.paste(Image.new("RGBA", (40, 40), (255, 255, 255, 255)), (0, 0), _clover(40))
    lock.save(dest / "lock.png")


def stage(design_id: str, opts: dict, dest: Path):
    o = {**DEFAULTS, **opts}
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for i, f in enumerate(frames(design_id, SIZES[o["size"]] * 1.333)):   # tuned for 2560x1440
        f.save(dest / f"throbber-{i + 1:04d}.png")
    _dialog_assets(dest)
    fw = "true" if o["firmware_logo"] else "false"
    (dest / "grimoire.plymouth").write_text(f"""[Plymouth Theme]
Name=Grimoire
Description=Grimoire MuraL boot animation ({design_id})
ModuleName=two-step

[two-step]
Font=IBM Plex Sans 12
TitleFont=IBM Plex Sans Light 30
ImageDir=/usr/share/plymouth/themes/grimoire
DialogHorizontalAlignment=.5
DialogVerticalAlignment=.72
TitleHorizontalAlignment=.5
TitleVerticalAlignment=.38
HorizontalAlignment=.5
VerticalAlignment={POSITIONS[o["position"]]}
WatermarkHorizontalAlignment=.5
WatermarkVerticalAlignment=.96
Transition=none
TransitionDuration=0.0
BackgroundStartColor=0x000000
BackgroundEndColor=0x000000
DialogClearsFirmwareBackground=true
MessageBelowAnimation=true

[boot-up]
UseEndAnimation=false
UseFirmwareBackground={fw}

[shutdown]
UseEndAnimation=false
UseFirmwareBackground={fw}

[reboot]
UseEndAnimation=false
UseFirmwareBackground={fw}

[updates]
SuppressMessages=true
""")


class BootTab(ScreenTab):
    key = "boot"
    context = "grimoire.spells.mural.boot"
    subtitle = tr_noop("grimoire.spells.mural.boot", "What you see while Linux starts and shuts down (Plymouth). "
                       "Installing rebuilds the boot image, so it asks for your password and takes about a "
                       "minute.")
    apply_label = tr_noop("grimoire.spells.mural.boot", "Install boot screen")
    apply_busy = tr_noop("grimoire.spells.mural.boot",
                         "Installing… enter your password, then this takes about a minute.")
    store = ["plymouth"]

    def designs(self):
        WORK.mkdir(parents=True, exist_ok=True)
        return DESIGNS + community_designs("plymouth")

    def build_options(self, lay):
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        self.size = Choice([(k, tr("grimoire.spells.mural.boot", k)) for k in SIZES], self.changed)
        self.position = Choice([(k, tr("grimoire.spells.mural.boot", k)) for k in POSITIONS], self.changed)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.boot", "Size")), 0, 0)
        grid.addWidget(self.size, 0, 1)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.boot", "Position")), 1, 0)
        grid.addWidget(self.position, 1, 1)
        lay.addLayout(grid)
        self.firmware = WrapCheck(tr("grimoire.spells.mural.boot", "Keep the motherboard logo"))
        self.firmware.toggled.connect(self.changed)
        lay.addWidget(self.firmware)
        lay.addSpacing(6)
        play = WrapButton(tr("grimoire.spells.mural.boot", "Play animation"))
        play.clicked.connect(self._play)
        lay.addWidget(play)
        restore = WrapButton(tr("grimoire.spells.mural.boot", "Restore previous boot screen"))
        restore.clicked.connect(self._restore)
        lay.addWidget(restore)

    def options(self):
        return {"size": self.size.value(), "position": self.position.value(),
                "firmware_logo": self.firmware.isChecked()}

    def set_options(self, o):
        o = {**DEFAULTS, **o}
        self.size.set_value(o["size"])
        self.position.set_value(o["position"])
        self.firmware.setChecked(o["firmware_logo"])

    def preview(self, design, o):
        img = to_qimage(preview(design.id, o))
        if o.get("firmware_logo"):                      # drawn by Qt: PIL's font has no other scripts
            p = QPainter(img)
            p.setPen(QColor(90, 90, 90))
            p.setFont(QFont("IBM Plex Sans", 11))
            p.drawText(QRectF(0, img.height() * 0.9 - 15, img.width(), 30), Qt.AlignmentFlag.AlignCenter,
                       tr("grimoire.spells.mural.boot", "(motherboard logo)"))
            p.end()
        return img

    def thumbnail(self, design, o):
        """Boot animations are tiny at real size, so cards show a zoomed crop of the middle."""
        img = preview(design.id, {**o, "position": "Center"})
        w, h = img.size
        return to_qimage(img.crop((w * 0.34, h * 0.34, w * 0.66, h * 0.66)))

    def _selected(self, row, render=True):
        self._stop_movie()
        super()._selected(row, render)

    def _rerender(self):
        self._stop_movie()
        super()._rerender()

    def _stop_movie(self):
        movie = getattr(self, "_movie", None)
        if movie:
            movie.stop()
            self._movie = None

    def _play(self):
        """Animate the big preview with the real frames."""
        if self.current().id.startswith("store:"):
            self.status.setText(tr("grimoire.spells.mural.boot",
                                   "Community boot themes can only be previewed by rebooting."))
            return
        o = {**DEFAULTS, **self.options()}
        w = max(320, self.big.width())
        h = int(w * 9 / 16)
        if h > self.big.height():
            h = max(180, self.big.height())
            w = int(h * 16 / 9)
        scale = SIZES[o["size"]] * (w / 1920)
        bg = Image.new("RGB", (w, h), (0, 0, 0))
        shots = []
        for f in frames(self.current().id, scale) * 2:
            s = bg.copy()
            s.paste(f, (int(w / 2 - f.width / 2), int(h * POSITIONS[o["position"]] - f.height / 2)), f)
            shots.append(s)
        gif = WORK / "play.gif"
        shots[0].save(gif, save_all=True, append_images=shots[1:], duration=33, loop=0)
        self._stop_movie()
        self._movie = QMovie(str(gif))
        self.big.setMovie(self._movie)
        self._movie.start()

    def apply(self, design, o):
        if design.id.startswith("store:"):
            entry = community_entry(design.id)
            run_root("plymouth-install", entry["ident"], entry["path"])
            return tr("grimoire.spells.mural.boot", "Installed ✓  You'll see it on your next reboot.")
        staged = WORK / "install"
        stage(design.id, o, staged)
        run_root("plymouth", str(staged))
        return tr("grimoire.spells.mural.boot", "Installed ✓  You'll see it on your next reboot.")

    def _restore(self):
        def work():
            run_root("plymouth-restore")
            return tr("grimoire.spells.mural.boot", "Previous boot screen restored.")
        self.background(work, tr("grimoire.spells.mural.boot",
                                 "Restoring… enter your password, then this takes about a minute."))

