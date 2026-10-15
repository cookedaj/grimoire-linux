# SPDX-License-Identifier: GPL-3.0-or-later
"""Colors tab: KDE color schemes for every window and app: black & white ones first, then a few muted tones.

Generates ~/.local/share/color-schemes/Grimoire<Name>.colors and applies it with plasma-apply-colorscheme.
Every role (links, warnings, focus…) maps to a gray, so nothing on screen keeps a hue; a toned design only
tints those grays slightly (TONES), it never brings back colored roles.
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import tr, tr_noop

from grimoire.paths import DATA, HOME
from grimoire.spells.mural.backdrop import wallpaper as _wallpaper
from grimoire.spells.mural.kde import kread, run_tool
from grimoire.spells.mural.screens import Choice, Design, ScreenTab, WrapButton, community_designs, community_entry

SCHEMES = HOME / ".local/share/color-schemes"
PREVIOUS = DATA / "mural" / "colors-previous.txt"
DEFAULTS = {"titlebar": "Match", "accent": "Design"}
ACCENTS = [tr_noop("grimoire.spells.mural.colors", "Design"), tr_noop("grimoire.spells.mural.colors", "White"),
           tr_noop("grimoire.spells.mural.colors", "Light gray"), tr_noop("grimoire.spells.mural.colors", "Mid gray"),
           tr_noop("grimoire.spells.mural.colors", "Dark gray"), tr_noop("grimoire.spells.mural.colors", "Black")]
ACCENT_GRAYS = {"White": 0xf0, "Light gray": 0xc0, "Mid gray": 0x80, "Dark gray": 0x40, "Black": 0x10}
TITLEBARS = [tr_noop("grimoire.spells.mural.colors", "Match"), tr_noop("grimoire.spells.mural.colors", "Black")]

#            window view  button header select sel-text text  muted dark
PALETTES = {
    "obsidian": (0x0e, 0x08, 0x18, 0x0a, 0xf0, 0x00, 0xe8, 0x80, True),
    "graphite": (0x1c, 0x14, 0x27, 0x17, 0x4c, 0xff, 0xe2, 0x8a, True),
    "slate":    (0x2b, 0x23, 0x36, 0x26, 0xd8, 0x10, 0xdc, 0x94, True),
    "silver":   (0xd4, 0xe4, 0xc6, 0xca, 0x2a, 0xff, 0x14, 0x60, False),
    "paper":    (0xf3, 0xff, 0xe8, 0xec, 0x1a, 0xff, 0x10, 0x70, False),
    "ink":      (0x04, 0x00, 0x12, 0x00, 0xff, 0x00, 0xf4, 0x86, True),
    "fog":      (0xb4, 0xc4, 0xa6, 0xaa, 0x26, 0xff, 0x0c, 0x48, False),
    "newsprint": (0xee, 0xfa, 0xe2, 0x10, 0x10, 0xff, 0x0e, 0x66, False),
    "steel":    (0x1e, 0x16, 0x2a, 0x19, 0xb4, 0x08, 0xe0, 0x8a, True),
    "moss":     (0x22, 0x1a, 0x2e, 0x1c, 0xa8, 0x06, 0xdc, 0x8c, True),
    "clay":     (0x24, 0x1b, 0x30, 0x1e, 0xc0, 0x10, 0xe2, 0x90, True),
    "sepia":    (0xec, 0xf6, 0xe0, 0xe4, 0x3a, 0xff, 0x1c, 0x70, False),
}
# a toned design's tint, (r, g, b) offsets added to each gray: strongest on mid grays, so black and white stay
# nearly neutral and text keeps its contrast
TONES = {
    "steel": (-8, 0, 16),
    "moss":  (-6, 10, -5),
    "clay":  (12, 3, -10),
    "sepia": (14, 5, -16),
}
DESIGNS = [
    Design("obsidian", tr_noop("grimoire.spells.mural.colors", "Obsidian"), tr_noop(
        "grimoire.spells.mural.colors", "Near-black everywhere, pure white selection. The boldest monochrome.")),
    Design("graphite", tr_noop("grimoire.spells.mural.colors", "Graphite"), tr_noop(
        "grimoire.spells.mural.colors", "Charcoal grays with a soft gray selection. Calm and balanced.")),
    Design("slate", tr_noop("grimoire.spells.mural.colors", "Slate"), tr_noop(
        "grimoire.spells.mural.colors",
        "Lighter dark grays with a bright selection. Easy contrast for long sessions.")),
    Design("silver", tr_noop("grimoire.spells.mural.colors", "Silver"), tr_noop(
        "grimoire.spells.mural.colors", "Light gray surfaces with near-black selection. A gentle light theme.")),
    Design("paper", tr_noop("grimoire.spells.mural.colors", "Paper"), tr_noop(
        "grimoire.spells.mural.colors", "White paper and black ink. Crisp light theme.")),
    Design("ink", tr_noop("grimoire.spells.mural.colors", "Ink"), tr_noop(
        "grimoire.spells.mural.colors", "Pure black surfaces and pure white text. Highest contrast, made for OLED "
                                        "screens.")),
    Design("fog", tr_noop("grimoire.spells.mural.colors", "Fog"), tr_noop(
        "grimoire.spells.mural.colors", "Mid-gray surfaces with black text. Light, but never glaring.")),
    Design("newsprint", tr_noop("grimoire.spells.mural.colors", "Newsprint"), tr_noop(
        "grimoire.spells.mural.colors", "White pages under solid black title bars, like a printed front page.")),
    Design("steel", tr_noop("grimoire.spells.mural.colors", "Steel"), tr_noop(
        "grimoire.spells.mural.colors", "Muted tone: charcoal with a cool blue-gray cast.")),
    Design("moss", tr_noop("grimoire.spells.mural.colors", "Moss"), tr_noop(
        "grimoire.spells.mural.colors", "Muted tone: dark grays with a faint green cast.")),
    Design("clay", tr_noop("grimoire.spells.mural.colors", "Clay"), tr_noop(
        "grimoire.spells.mural.colors", "Muted tone: warm dark grays, like unglazed clay.")),
    Design("sepia", tr_noop("grimoire.spells.mural.colors", "Sepia"), tr_noop(
        "grimoire.spells.mural.colors", "Muted tone: aged paper and brown-black ink. A warm light theme.")),
]
EFFECTS = """[ColorEffects:Disabled]
Color=56,56,56
ColorAmount=0
ColorEffect=0
ContrastAmount=0.65
ContrastEffect=1
IntensityAmount=0.1
IntensityEffect=2

[ColorEffects:Inactive]
ChangeSelectionColor=true
Color=112,111,110
ColorAmount=0.025
ColorEffect=2
ContrastAmount=0.1
ContrastEffect=2
Enable=false
IntensityAmount=0
IntensityEffect=0
"""


def rgb(v: float, tone: tuple = (0, 0, 0)) -> tuple[int, int, int]:
    """A gray, tinted by a design's tone (none for the black & white designs)."""
    v = max(0, min(255, int(v)))
    weight = 0.45 + 0.55 * (1 - abs(v - 128) / 128)
    return tuple(max(0, min(255, round(v + t * weight))) for t in tone)


def _g(v: float, tone: tuple = (0, 0, 0)) -> str:
    return ",".join(map(str, rgb(v, tone)))


def palette(pid: str, o: dict) -> dict:
    window, view, button, header, sel, sel_text, text, muted, dark = PALETTES[pid]
    accent = o.get("accent", "Design")
    if accent in ACCENT_GRAYS:
        sel = ACCENT_GRAYS[accent]
        sel_text = 0x00 if sel > 0x90 else 0xff
    if o.get("titlebar") == "Black":
        header = 0x05
    return dict(window=window, view=view, button=button, header=header, sel=sel, sel_text=sel_text,
                text=text, muted=muted, dark=dark, tone=TONES.get(pid, (0, 0, 0)))


def scheme_text(pid: str, o: dict, name: str, ident: str) -> str:
    c = palette(pid, o)
    dark = c["dark"]
    tg = lambda v: _g(v, c["tone"])                    # every gray below carries the design's tone
    alt = 10 if dark else -10                          # alternating-row offset
    focus = c["sel"]
    hover = (c["sel"] + c["text"]) / 2

    def group(title, bg, fg, muted=c["muted"], fg_active=None):
        header_text = fg if not (title.startswith("Colors:Header") and c["header"] < 0x40) else 0xe8
        return f"""[{title}]
BackgroundAlternate={tg(bg + alt)}
BackgroundNormal={tg(bg)}
DecorationFocus={tg(focus)}
DecorationHover={tg(hover)}
ForegroundActive={tg(fg_active if fg_active is not None else header_text)}
ForegroundInactive={tg(muted)}
ForegroundLink={tg(header_text)}
ForegroundNegative={tg(0xc8 if dark else 0x30)}
ForegroundNeutral={tg(0xb0 if dark else 0x48)}
ForegroundNormal={tg(header_text)}
ForegroundPositive={tg(0xd8 if dark else 0x24)}
ForegroundVisited={tg(muted)}
"""

    header_fg = 0xe8 if c["header"] < 0x40 else c["text"]
    parts = [
        EFFECTS,
        group("Colors:Button", c["button"], c["text"]),
        group("Colors:Complementary", 0x0b, 0xe8, 0x80),
        group("Colors:Header", c["header"], c["text"]),
        group("Colors:Header][Inactive", c["header"], c["text"]),
        group("Colors:Selection", c["sel"], c["sel_text"], muted=c["sel_text"], fg_active=c["sel_text"]),
        group("Colors:Tooltip", c["window"], c["text"]),
        group("Colors:View", c["view"], c["text"]),
        group("Colors:Window", c["window"], c["text"]),
        f"[General]\nColorScheme={ident}\nName={name}\nshadeSortColumn=true\n",
        "[KDE]\ncontrast=4\n",
        f"""[WM]
activeBackground={tg(c['header'])}
activeBlend={tg(header_fg)}
activeForeground={tg(header_fg)}
inactiveBackground={tg(c['header'])}
inactiveBlend={tg(c['muted'])}
inactiveForeground={tg(c['muted'])}
""",
    ]
    return "\n".join(parts)


def render(pid: str, o: dict, w=1280, h=720) -> QImage:
    """A mock app window painted with the scheme."""
    c = palette(pid, {**DEFAULTS, **o})

    def q(v, a=255):
        return QColor(*rgb(v, c["tone"]), a)

    img = _wallpaper(w, h).copy()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.fillRect(img.rect(), QColor(0, 0, 0, 110))
    win = QRectF(w * 0.1, h * 0.1, w * 0.8, h * 0.8)
    clip = QPainterPath()
    clip.addRoundedRect(win, 10, 10)
    p.setClipPath(clip)
    p.fillRect(win, q(c["window"]))
    title = QRectF(win.x(), win.y(), win.width(), 38)
    p.fillRect(title, q(c["header"]))
    header_fg = 0xe8 if c["header"] < 0x40 else c["text"]
    p.setFont(QFont("IBM Plex Sans", 10))
    p.setPen(q(header_fg))
    p.drawText(title, Qt.AlignmentFlag.AlignCenter, "Dolphin — Repo")
    for k in range(3):                                  # window buttons
        p.setBrush(q(header_fg, 140))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(win.right() - 26 - k * 24, title.center().y() - 6, 12, 12))

    tool = QRectF(win.x(), title.bottom(), win.width(), 46)
    p.fillRect(tool, q(c["window"]))
    p.setFont(QFont("IBM Plex Sans", 9))
    fm = QFontMetricsF(p.font())
    x = tool.x() + 14
    for label in (tr("grimoire.spells.mural.colors", "Back"), tr("grimoire.spells.mural.colors", "Forward"),
                  tr("grimoire.spells.mural.colors", "New Folder"), tr("grimoire.spells.mural.colors", "Share")):
        r = QRectF(x, tool.y() + 9, 24 + fm.horizontalAdvance(label), 28)
        p.setBrush(q(c["button"]))
        p.setPen(q(c["text"], 40))
        p.drawRoundedRect(r, 5, 5)
        p.setPen(q(c["text"]))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, label)
        x = r.right() + 8
    search = QRectF(tool.right() - 230, tool.y() + 9, 210, 28)
    p.setBrush(q(c["view"]))
    p.setPen(q(c["sel"] if c["dark"] else c["text"], 160))
    p.drawRoundedRect(search, 5, 5)
    p.setPen(q(c["muted"]))
    p.drawText(search.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter,
               tr("grimoire.spells.mural.colors", "Search…"))

    side = QRectF(win.x(), tool.bottom(), 190, win.bottom() - tool.bottom())
    p.fillRect(side, q(c["window"]))
    p.setFont(QFont("IBM Plex Sans", 10))
    places = (tr("grimoire.spells.mural.colors", "Home"), tr("grimoire.spells.mural.colors", "Desktop"),
              tr("grimoire.spells.mural.colors", "Documents"), tr("grimoire.spells.mural.colors", "Downloads"), "Repo",
              tr("grimoire.spells.mural.colors", "Trash"))
    for k, place in enumerate(places):
        r = QRectF(side.x() + 8, side.y() + 10 + k * 32, side.width() - 16, 28)
        if k == 4:
            p.setBrush(q(c["sel"]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 5, 5)
            p.setPen(q(c["sel_text"]))
        else:
            p.setPen(q(c["text"]))
        p.drawText(r.adjusted(12, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter, place)

    view = QRectF(side.right(), tool.bottom(), win.right() - side.right(), side.height())
    p.fillRect(view, q(c["view"]))
    alt = 10 if c["dark"] else -10
    rows = ("Grimoire", "Linux Setup", "assets", "design", "clover5.svg", "notes.md", "wallpaper.png")
    for k, name in enumerate(rows):
        r = QRectF(view.x(), view.y() + k * 34, view.width(), 34)
        if k % 2:
            p.fillRect(r, q(c["view"] + alt))
        if k == 1:
            p.fillRect(r.adjusted(6, 2, -6, -2), q(c["sel"], 90 if c["dark"] else 60))
        p.setPen(q(c["text"]))
        p.drawText(r.adjusted(20, 0, -20, 0), Qt.AlignmentFlag.AlignVCenter, name)
        p.setPen(q(c["muted"]))
        p.drawText(r.adjusted(20, 0, -20, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   tr("grimoire.spells.mural.colors", "folder") if "." not in name
                   else tr("grimoire.spells.mural.colors", "file"))
    btn = QRectF(view.right() - 150, view.bottom() - 52, 130, 34)
    p.setBrush(q(c["sel"]))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(btn, 6, 6)
    p.setPen(q(c["sel_text"]))
    p.drawText(btn, Qt.AlignmentFlag.AlignCenter, tr("grimoire.spells.mural.colors", "Open"))
    p.setClipping(False)
    p.setPen(q(255 if c["dark"] else 0, 40))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(clip)
    p.end()
    return img


def current_scheme() -> str:
    return kread("kdeglobals", "General", "ColorScheme")


class ColorsTab(ScreenTab):
    key = "colors"
    context = "grimoire.spells.mural.colors"
    subtitle = tr_noop("grimoire.spells.mural.colors", "System colors for every window and app. Links, warnings and "
                       "focus all become grays. Grimoire itself keeps its own look.")
    apply_label = tr_noop("grimoire.spells.mural.colors", "Apply colors")
    store = ["colors"]

    def designs(self):
        return DESIGNS + community_designs("colors")

    def build_options(self, lay):
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        self.titlebar = Choice([(k, tr("grimoire.spells.mural.colors", k)) for k in TITLEBARS], self.changed)
        self.accent = Choice([(k, tr("grimoire.spells.mural.colors", k)) for k in ACCENTS], self.changed)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.colors", "Title bars")), 0, 0)
        grid.addWidget(self.titlebar, 0, 1)
        grid.addWidget(QLabel(tr("grimoire.spells.mural.colors", "Selection")), 1, 0)
        grid.addWidget(self.accent, 1, 1)
        lay.addLayout(grid)
        lay.addSpacing(6)
        restore = WrapButton(tr("grimoire.spells.mural.colors", "Restore previous colors"))
        restore.clicked.connect(self._restore)
        lay.addWidget(restore)

    def options(self):
        return {"titlebar": self.titlebar.value(), "accent": self.accent.value()}

    def set_options(self, o):
        o = {**DEFAULTS, **o}
        self.titlebar.set_value(o["titlebar"])
        self.accent.set_value(o["accent"])

    def preview(self, design, o):
        return render(design.id, o)

    def thumbnail(self, design, o):
        """Cards zoom in on the window's title bar, sidebar selection and rows."""
        if design.id.startswith("store:"):
            return self.preview(design, o)
        return render(design.id, o).copy(118, 62, 704, 396)

    def apply(self, design, o):
        SCHEMES.mkdir(parents=True, exist_ok=True)
        cur = current_scheme()
        if not cur.startswith("Grimoire"):
            PREVIOUS.parent.mkdir(parents=True, exist_ok=True)
            PREVIOUS.write_text(cur or "BreezeDark")
        if design.id.startswith("store:"):
            ident = community_entry(design.id)["ident"]
            run_tool(["plasma-apply-colorscheme", ident], ok_if_already=True)
            return tr("grimoire.spells.mural.colors", "Applied ✓")
        # plasma-apply-colorscheme ignores re-applying the current name, so alternate between two names
        base = "Grimoire" + design.name.replace(" ", "")
        ident = base + "B" if cur == base else base
        (SCHEMES / f"{ident}.colors").write_text(scheme_text(design.id, o, f"Grimoire {design.name}", ident))
        run_tool(["plasma-apply-colorscheme", ident])
        for old in SCHEMES.glob("Grimoire*.colors"):    # keep only the active one
            if old.stem != ident:
                old.unlink()
        return tr("grimoire.spells.mural.colors", "Applied ✓  Open apps update right away.")

    def _restore(self):
        prev = PREVIOUS.read_text().strip() if PREVIOUS.exists() else "BreezeDark"

        def work():
            run_tool(["plasma-apply-colorscheme", prev])
            return tr("grimoire.spells.mural.colors", "Restored {scheme}.").format(scheme=prev)
        self.background(work, tr("grimoire.spells.mural.colors", "Restoring…"))
