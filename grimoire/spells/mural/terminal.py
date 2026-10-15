# SPDX-License-Identifier: GPL-3.0-or-later
"""Terminal tab: Konsole in black & white. Grayscale palettes (dark and light), a few muted monochrome ones,
+ font, size, transparency, padding, cursor, and an optional shell prompt.

Writes ~/.local/share/konsole/Grimoire.profile + Grimoire-<palette>.colorscheme, makes Grimoire the default
profile, and (if a prompt style is chosen) a marked block in ~/.bashrc.
"""
import re
import subprocess

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import tr, tr_noop
from grimoire.paths import HOME
from grimoire.spells.mural.kde import kwrite
from grimoire.spells.mural.screens import (Choice, Design, ScreenTab, WrapButton, WrapCheck, community_designs,
                                           community_entry)
from grimoire.spells.mural.backdrop import wallpaper as _wallpaper
from grimoire.spells.mural.fonts import installed
from grimoire.widgets import Slider

KONSOLE = HOME / ".local/share/konsole"
BASHRC = HOME / ".bashrc"
FONTS = ["IBM Plex Mono", "DM Mono", "Hack", "DejaVu Sans Mono", "Ubuntu Sans Mono", "Noto Sans Mono",
         "Liberation Mono", "Nimbus Mono PS", "JetBrains Mono", "Fira Code"]
CURSORS = {tr_noop("grimoire.spells.mural.terminal", "Block"): 0,
           tr_noop("grimoire.spells.mural.terminal", "I-beam"): 1,
           tr_noop("grimoire.spells.mural.terminal", "Underline"): 2}
PROMPTS = [tr_noop("grimoire.spells.mural.terminal", "Keep mine"), tr_noop("grimoire.spells.mural.terminal", "Minimal"),
           tr_noop("grimoire.spells.mural.terminal", "Clover"), tr_noop("grimoire.spells.mural.terminal", "Two-line"),
           tr_noop("grimoire.spells.mural.terminal", "Lambda"), tr_noop("grimoire.spells.mural.terminal", "Arrow"),
           tr_noop("grimoire.spells.mural.terminal", "Frame"), tr_noop("grimoire.spells.mural.terminal", "Clock")]
DEFAULTS = {"font": "IBM Plex Mono", "size": 12, "transparency": 0, "blur": True, "padding": 14,
            "cursor": "Block", "prompt": "Keep mine"}
BLOCK_START, BLOCK_END = "# >>> grimoire prompt >>>", "# <<< grimoire prompt <<<"

# ANSI order: black red green yellow blue magenta cyan white -> distinct grays (or shades of one muted tint).
# A color is a gray level (int) or "#rrggbb".
#                 bg     fg    ansi (normal)                                   dark?
PALETTES = {      # ids never change: saved looks and shared setups name them
    "ink":       (0x00, 0xe6, [0x2a, 0xb4, 0xd4, 0xec, 0x8c, 0xa6, 0xc6, 0xe6], True),
    "graphite":  (0x1c, 0xcf, [0x3c, 0xa4, 0xc0, 0xd8, 0x86, 0x9a, 0xb4, 0xcf], True),
    "slate":     (0x2a, 0xf0, [0x4a, 0xbc, 0xd8, 0xf4, 0x9a, 0xb0, 0xcc, 0xf0], True),
    "fog":       (0x3a, 0xe2, [0x58, 0xc2, 0xd8, 0xf0, 0xa2, 0xb6, 0xcc, 0xe2], True),
    "stark":     (0x00, 0xff, [0x50, 0xff, 0xe4, 0xff, 0xb4, 0xd0, 0xf0, 0xff], True),
    "paper":     (0xfa, 0x1a, [0x1a, 0x5a, 0x40, 0x2c, 0x70, 0x50, 0x60, 0xb4], False),
    "newsprint": (0xe6, 0x26, [0x26, 0x60, 0x48, 0x36, 0x76, 0x58, 0x68, 0xa8], False),
    "phosphor":  ("#070b07", "#a6c9a0", ["#1f2a1e", "#7ea078", "#9dc496", "#c4e4be", "#6a8a64", "#86a880",
                                         "#94b88e", "#a6c9a0"], True),
    "amber":     ("#0d0a06", "#dcb174", ["#2c2216", "#a8834e", "#c99e62", "#f0cc94", "#8c6c40", "#b48c56",
                                         "#c49a60", "#dcb174"], True),
    "ink-muted": (0x00, 0xe6, ["#2a2a2a", "#b48282", "#8fae8f", "#c8ba8c", "#8296b0", "#a68ca6", "#88abab",
                               "#e6e6e6"], True),
}
DESIGNS = [
    Design("ink", tr_noop("grimoire.spells.mural.terminal", "Ink"), tr_noop(
        "grimoire.spells.mural.terminal", "Pure black, soft white text. Every color becomes its own shade of gray.")),
    Design("graphite", tr_noop("grimoire.spells.mural.terminal", "Graphite"), tr_noop(
        "grimoire.spells.mural.terminal", "Charcoal background with gentle gray text. Easy on the eyes at night.")),
    Design("slate", tr_noop("grimoire.spells.mural.terminal", "Slate"), tr_noop(
        "grimoire.spells.mural.terminal", "A dark gray slate with bright chalk-white text.")),
    Design("fog", tr_noop("grimoire.spells.mural.terminal", "Fog"), tr_noop(
        "grimoire.spells.mural.terminal", "Mid gray and low contrast: calm and soft for long sessions.")),
    Design("stark", tr_noop("grimoire.spells.mural.terminal", "Stark"), tr_noop(
        "grimoire.spells.mural.terminal", "Black and pure white at full contrast, for the sharpest possible text.")),
    Design("paper", tr_noop("grimoire.spells.mural.terminal", "Paper"), tr_noop(
        "grimoire.spells.mural.terminal", "White page, near-black ink. Grays in reverse for daylight.")),
    Design("newsprint", tr_noop("grimoire.spells.mural.terminal", "Newsprint"), tr_noop(
        "grimoire.spells.mural.terminal", "Light gray paper with charcoal text: bright but never glaring.")),
    Design("phosphor", tr_noop("grimoire.spells.mural.terminal", "Phosphor"), tr_noop(
        "grimoire.spells.mural.terminal", "An old green-screen monitor, muted: every color is a shade of soft green.")),
    Design("amber", tr_noop("grimoire.spells.mural.terminal", "Amber"), tr_noop(
        "grimoire.spells.mural.terminal", "A muted amber monochrome screen, warm and quiet.")),
    Design("ink-muted", tr_noop("grimoire.spells.mural.terminal", "Ink Muted"), tr_noop(
        "grimoire.spells.mural.terminal", "Ink with faded real colors, for when you need red and green told apart.")),
]
SAMPLE = [("prompt", "ls"), ("ls", ""), ("prompt", "git status"), ("out", "On branch main"),
          ("out", "Changes not staged for commit:"), ("mod", "	modified:   grimoire/spells/mural/terminal.py"),
          ("prompt", "python3 -c 'print(\"surpass your limits\")'"), ("out", "surpass your limits"),
          ("prompt", "")]


def _c(v) -> tuple[int, int, int]:
    """A palette color as (r, g, b): a gray level or "#rrggbb"."""
    if isinstance(v, int):
        return v, v, v
    if isinstance(v, tuple):
        return v
    q = QColor(v)
    return q.red(), q.green(), q.blue()


def _mix(a, b, t: float) -> tuple[int, int, int]:
    """t of a + (1 - t) of b."""
    return tuple(int(x * t + y * (1 - t)) for x, y in zip(_c(a), _c(b)))


def _shift(v, d: int) -> tuple[int, int, int]:
    return tuple(min(255, max(0, x + d)) for x in _c(v))


def _rgb(v) -> str:
    return ",".join(str(x) for x in _c(v))


def qcolor(v, alpha=255) -> QColor:
    return QColor(*_c(v), alpha)


def colorscheme(pid: str, o: dict) -> str:
    bg, fg, ansi, dark = PALETTES[pid]
    lines = []

    def group(name, v):
        lines.append(f"[{name}]\nColor={_rgb(v)}\n")

    group("Background", bg)
    group("BackgroundIntense", bg)
    group("BackgroundFaint", bg)
    group("Foreground", fg)
    group("ForegroundIntense", (_shift(fg, 40) if not isinstance(fg, int) else 0xff) if dark else 0x00)
    group("ForegroundFaint", _mix(fg, bg, 0.6))
    for i, v in enumerate(ansi):
        group(f"Color{i}", v)
        group(f"Color{i}Intense", _shift(v, 24 if dark else -24))
        group(f"Color{i}Faint", _mix(v, bg, 0.6))
    opacity = 1 - o["transparency"] / 100
    name = next((d.name for d in DESIGNS if d.id == pid), pid.title())
    lines.append(f"[General]\nDescription=Grimoire {name}\nOpacity={opacity:.2f}\n"
                 f"Blur={'true' if o['blur'] and opacity < 1 else 'false'}\nWallpaper=\n")
    return "\n".join(lines)


def profile(pid: str, o: dict) -> str:
    return f"""[Appearance]
ColorScheme=Grimoire-{pid}
Font={o['font']},{o['size']},-1,5,400,0,0,0,0,0
LineSpacing=2

[Cursor Options]
CursorShape={CURSORS[o['cursor']]}

[General]
Name=Grimoire
Parent=FALLBACK/
TerminalMargin={o['padding']}
TerminalCenter=false

[Scrolling]
HistorySize=10000
ScrollBarPosition=2
"""


def prompt_block(style: str) -> str:
    ps1 = {
        "Minimal": r"PS1='\[\e[2m\]\W\[\e[0m\] ❯ '",
        "Clover": r"PS1='\[\e[1m\]♣\[\e[0m\] \W › '",
        "Two-line": r"PS1='\n\[\e[2m\]\w\[\e[0m\]\n❯ '",
        "Lambda": r"PS1='\[\e[1m\]λ\[\e[0m\] \W '",
        "Arrow": r"PS1='\[\e[2m\]\W\[\e[0m\] → '",
        "Frame": r"PS1='\n┌─ \[\e[1m\]\w\[\e[0m\]\n└─❯ '",
        "Clock": r"PS1='\[\e[2m\]\A\[\e[0m\] \W ❯ '",
    }[style]
    return f"{BLOCK_START}\n# Written by Grimoire → MuraL → Terminal. Delete this block to undo.\n{ps1}\n{BLOCK_END}\n"


def write_prompt(style: str):
    text = BASHRC.read_text() if BASHRC.exists() else ""
    if style == "Keep mine" and BLOCK_START not in text:
        return                                          # nothing of ours in there: don't touch the file
    text = re.sub(rf"\n?{re.escape(BLOCK_START)}.*?{re.escape(BLOCK_END)}\n?", "\n", text, flags=re.S).rstrip() + "\n"
    if style != "Keep mine":
        text += "\n" + prompt_block(style)
    BASHRC.write_text(text)


def _prompt_text(style: str) -> list[tuple[str, int]]:
    """(text, ansi color index or -1 for fg) runs for the preview prompt."""
    if style == "Minimal":
        return [("Repo", 8), (" ❯ ", -1)]
    if style == "Clover":
        return [("♣", -2), (" Repo › ", -1)]
    if style == "Two-line":
        return [("~/Projects", 8), ("\n❯ ", -1)]
    if style == "Lambda":
        return [("λ", -2), (" Repo ", -1)]
    if style == "Arrow":
        return [("Repo", 8), (" → ", -1)]
    if style == "Frame":
        return [("┌─ ", -1), ("~/Projects", -2), ("\n└─❯ ", -1)]
    if style == "Clock":
        return [("21:47", 8), (" Repo ❯ ", -1)]
    return [("you@grimoire", 2), (":", -1), ("~/Projects", 4), ("$ ", -1)]


def render(pid: str, o: dict, w=1280, h=720) -> QImage:
    o = {**DEFAULTS, **o}
    bg, fg, ansi, dark = PALETTES[pid]
    img = _wallpaper(w, h).copy()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.fillRect(img.rect(), QColor(0, 0, 0, 120))

    win = QRectF(w * 0.12, h * 0.12, w * 0.76, h * 0.76)
    shape = QPainterPath()
    shape.addRoundedRect(win, 10, 10)
    p.setClipPath(shape)
    title_h = 34
    p.fillRect(QRectF(win.x(), win.y(), win.width(), title_h), QColor(18, 18, 18) if dark else QColor(228, 228, 228))
    alpha = int(255 * (1 - o["transparency"] / 100))
    body = QRectF(win.x(), win.y() + title_h, win.width(), win.height() - title_h)
    p.fillRect(body, qcolor(bg, alpha))
    p.setClipping(False)
    p.setPen(QColor(255, 255, 255, 30) if dark else QColor(0, 0, 0, 40))
    p.drawPath(shape)
    p.setPen(QColor(150, 150, 150))
    p.setFont(QFont("IBM Plex Sans", 10))
    p.drawText(QRectF(win.x(), win.y(), win.width(), title_h), Qt.AlignmentFlag.AlignCenter, "Repo : bash — Konsole")

    def col(i):
        if i == -1:
            return qcolor(fg)
        if i == -2:                                     # intense foreground
            return qcolor(_shift(fg, 40 if dark else -40) if not isinstance(fg, int) else (0xff if dark else 0))
        if i == 8:                                      # "faint" text
            return qcolor(_mix(fg, bg, 0.6))
        return qcolor(ansi[i])

    font = QFont(o["font"], 1)
    font.setPixelSize(int(o["size"] * 1.25))
    p.setFont(font)
    fm = QFontMetricsF(font)
    line_h = fm.height() + 3
    x0 = body.x() + o["padding"] * 0.9
    x, y = x0, body.y() + o["padding"] * 0.9 + fm.ascent()

    def run(text, color):
        nonlocal x, y
        for k, part in enumerate(text.split("\n")):
            if k:
                x, y = x0, y + line_h
            p.setPen(col(color))
            p.drawText(QRectF(x, y - fm.ascent(), 2000, line_h), part)
            x += fm.horizontalAdvance(part)

    for kind, text in SAMPLE:
        if kind == "prompt":
            for t, c in _prompt_text(o["prompt"]):
                run(t, c)
            run(text, -1)
            if not text:                                # cursor on the last prompt
                cw = fm.horizontalAdvance("M")
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col(-1))
                shape_c = o["cursor"]
                if shape_c == "Block":
                    p.drawRect(QRectF(x, y - fm.ascent(), cw, fm.height()))
                elif shape_c == "I-beam":
                    p.drawRect(QRectF(x, y - fm.ascent(), 2, fm.height()))
                else:
                    p.drawRect(QRectF(x, y + fm.descent() - 2, cw, 2))
        elif kind == "ls":
            for name, c in (("Desktop", 4), ("Documents", 4), ("Downloads", 4), ("Repo", 4),
                            ("clover.png", 5), ("notes.txt", -1)):
                run(name + "  ", c)
        elif kind == "mod":
            run(text, 1)
        else:
            run(text, -1)
        x, y = x0, y + line_h
    p.end()
    return img


class TerminalTab(ScreenTab):
    key = "terminal"
    context = "grimoire.spells.mural.terminal"
    subtitle = tr_noop("grimoire.spells.mural.terminal", "Konsole, your terminal. Grayscale palettes turn every color "
                       "into its own shade so output stays readable; a few muted ones add a soft tint. Applies to new "
                       "Konsole windows.")
    apply_label = tr_noop("grimoire.spells.mural.terminal", "Apply to Konsole")
    store = ["konsole"]

    def designs(self):
        return DESIGNS + community_designs("konsole")

    def build_options(self, lay):
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        self.font = Choice([(f, f) for f in FONTS if installed(f) or f == DEFAULTS["font"]], self.changed)
        self.size = Slider(8, 20, " pt", self.changed)
        self.transparency = Slider(0, 60, "%", self.changed)
        self.padding = Slider(0, 40, " px", self.changed)
        self.cursor = Choice([(k, tr("grimoire.spells.mural.terminal", k)) for k in CURSORS], self.changed)
        self.prompt = Choice([(k, tr("grimoire.spells.mural.terminal", k)) for k in PROMPTS], self.changed)
        rows = ((tr("grimoire.spells.mural.terminal", "Font"), self.font),
                (tr("grimoire.spells.mural.terminal", "Size"), self.size),
                (tr("grimoire.spells.mural.terminal", "Transparency"), self.transparency),
                (tr("grimoire.spells.mural.terminal", "Padding"), self.padding),
                (tr("grimoire.spells.mural.terminal", "Cursor"), self.cursor),
                (tr("grimoire.spells.mural.terminal", "Prompt"), self.prompt))
        for r, (name, wdg) in enumerate(rows):
            grid.addWidget(QLabel(name), r, 0)
            grid.addWidget(wdg, r, 1)
        lay.addLayout(grid)
        self.blur = WrapCheck(tr("grimoire.spells.mural.terminal", "Blur behind when transparent"))
        self.blur.toggled.connect(self.changed)
        lay.addWidget(self.blur)
        lay.addSpacing(6)
        test = WrapButton(tr("grimoire.spells.mural.terminal", "Open a Konsole window"))
        test.clicked.connect(lambda: subprocess.Popen(["konsole", "--profile", "Grimoire"],
                                                      start_new_session=True))
        lay.addWidget(test)

    def options(self):
        return {"font": self.font.value(), "size": self.size.value(),
                "transparency": self.transparency.value(), "blur": self.blur.isChecked(),
                "padding": self.padding.value(), "cursor": self.cursor.value(),
                "prompt": self.prompt.value()}

    def set_options(self, o):
        o = {**DEFAULTS, **o}
        if self.font.findData(o["font"]) < 0:            # saved before, uninstalled since: still shown
            self.font.addItem(o["font"], o["font"])
        self.font.set_value(o["font"])
        self.size.setValue(o["size"])
        self.transparency.setValue(o["transparency"])
        self.blur.setChecked(o["blur"])
        self.padding.setValue(o["padding"])
        self.cursor.set_value(o["cursor"])
        self.prompt.set_value(o["prompt"])

    def preview(self, design, o):
        return render(design.id, o)

    def thumbnail(self, design, o):
        """Cards zoom in on the top-left of the terminal so the text is legible."""
        return render(design.id, o).copy(150, 85, 560, 315)

    def apply(self, design, o):
        KONSOLE.mkdir(parents=True, exist_ok=True)
        if design.id.startswith("store:"):           # community scheme + your font/padding/cursor options
            scheme = community_entry(design.id)["ident"]
        else:
            (KONSOLE / f"Grimoire-{design.id}.colorscheme").write_text(colorscheme(design.id, o))
            scheme = f"Grimoire-{design.id}"
        (KONSOLE / "Grimoire.profile").write_text(profile(design.id, o).replace(
            f"ColorScheme=Grimoire-{design.id}", f"ColorScheme={scheme}"))
        kwrite("konsolerc", "Desktop Entry", "DefaultProfile", "Grimoire.profile")
        write_prompt(o["prompt"])
        if o["prompt"] == "Keep mine":
            return tr("grimoire.spells.mural.terminal", "Applied ✓  New Konsole windows use it.")
        return tr("grimoire.spells.mural.terminal", "Applied ✓  New Konsole windows use it. Prompt takes "
                  "effect in new terminals.")
