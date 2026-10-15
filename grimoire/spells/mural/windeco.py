# SPDX-License-Identifier: GPL-3.0-or-later
"""Generates MuraL's own black & white window decorations as Aurorae themes (KWin's SVG decoration engine).

A theme is a folder in ~/.local/share/aurorae/themes/<ident>/: decoration.svg (a 9-slice frame: title bar row on
top, thin sides; "decoration-inactive-*" for unfocused windows), one SVG per title bar button (FrameSvg prefixes
active/hover/pressed/inactive, only the -center element), <ident>rc (sizes, title text colors) and metadata.
The window shadow is painted into the frame's padding. Everything is drawn here from a Deco, so nothing is
downloaded and every color stays a gray.
"""
import json
import shutil
from dataclasses import dataclass

from grimoire.paths import HOME

THEMES = HOME / ".local/share/aurorae/themes"
PREFIX = "grimoire-deco"                    # our generated themes: grimoire-deco, grimoire-deco-b
STATES = ("active", "hover", "pressed", "inactive")
BUTTONS = ("close", "minimize", "maximize", "restore", "alldesktops", "keepabove", "keepbelow", "shade", "help")


@dataclass(frozen=True)
class Deco:
    bar: str                   # title bar (and frame) of the focused window
    bar_inactive: str
    ink: str                   # glyphs and title text, focused
    ink_inactive: str
    button: str                # "line" glyphs, "circle" (hover disc), "dots", "box", "tile", "bold"
    radius: int = 6            # top corner radius
    title: int = 30            # title bar height at default size
    glyph: float = 1.5         # glyph stroke width
    separator: str = ""        # a line under the title bar ("" = none)
    hover: str = ""            # hover background ("" = derived from ink)
    close: str = ""            # the close button's own fill ("" = like the others)


# ids never change once added (saved looks and shared setups use them)
DECOS = {
    "monolith": Deco("#0a0a0a", "#141414", "#e8e8e8", "#7a7a7a", "circle"),
    "dots":     Deco("#0c0c0c", "#151515", "#e8e8e8", "#6e6e6e", "dots", radius=8),
    "boxed":    Deco("#000000", "#111111", "#f0f0f0", "#707070", "box", radius=0),
    "paper":    Deco("#f4f4f4", "#e2e2e2", "#111111", "#8a8a8a", "circle", separator="#d0d0d0"),
    "slim":     Deco("#050505", "#101010", "#d8d8d8", "#666666", "line", radius=0, title=22, glyph=1.2),
    "stencil":  Deco("#1c1c1c", "#242424", "#ffffff", "#808080", "bold", radius=4, title=32, glyph=2.6,
                     close="#ffffff"),
    "tiles":    Deco("#000000", "#0e0e0e", "#e8e8e8", "#6e6e6e", "tile", radius=0, title=32, hover="#2a2a2a",
                     close="#e8e8e8"),
}
SCALES = {"Tiny": 0.75, "Small": 0.875, "Default": 1.0, "Large": 1.25}
PAD = 14                       # shadow room around the window (svg px)
SIDE = 4                       # smallest frame column/row in the SVG grid
# the Windows tab's Border option (English keys) → frame width at the sides, at the bottom (px)
BORDERS = {"None": (0, 0), "No sides": (0, 4), "Tiny": (2, 2), "Normal": (4, 4), "Large": (8, 8)}


def _rgba(hex_color: str, alpha=255) -> str:
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha}"


def _light(hex_color: str) -> bool:
    return int(hex_color.lstrip("#")[0:2], 16) > 0x80


def metrics(d: Deco, scale: float, border: str = "No sides") -> dict:
    """Pixel sizes for one design at one button size and border."""
    side, bottom = BORDERS.get(border, BORDERS["No sides"])
    title = round(d.title * scale)
    tile = d.button == "tile"
    button = title if tile else max(12, min(title - round(8 * scale), round(20 * scale)))
    return {"title": title, "button": button, "button_w": round(button * 1.45) if tile else button,
            "spacing": 0 if tile else max(2, round(6 * scale)), "edge": 0 if tile else max(4, round(8 * scale)),
            "radius": round(d.radius * scale), "side": side, "bottom": bottom}


# ---------------------------------------------------------------- frame
def _grid(m: dict) -> tuple[int, int]:
    """Frame cell sizes: corner columns (and the bottom row) are C wide, the top row `top` tall."""
    return PAD + max(SIDE, m["radius"], m["side"], m["bottom"]), PAD + m["title"]


def _frame_parts(prefix: str, d: Deco, m: dict, active: bool) -> tuple[list[str], list[str]]:
    """The 9 tiles of one frame (prefix "decoration" or "decoration-inactive"), drawn on a 3x3 grid:
    columns C | 10 | C wide, rows PAD+title | 10 | C tall (C = shadow room + the wider of side and corner radius).
    Every prefix uses the same coordinates: Plasma renders each tile by its id, so they may overlap."""
    bar = d.bar if active else d.bar_inactive
    r, L, mid = m["radius"], 10, 10
    C, top = _grid(m)
    xs, ws = (0, C, C + L), (C, L, C)
    ys, hs = (0, top, top + mid), (top, mid, C)
    names = (("topleft", "top", "topright"), ("left", "center", "right"), ("bottomleft", "bottom", "bottomright"))
    win = (PAD, PAD, 2 * C + L - 2 * PAD, top + mid + C - 2 * PAD)    # the window's own rectangle in the grid
    wx, wy, ww, wh = win
    shadow = 0.38 if active else 0.24
    fade = f'stop-color="#000" stop-opacity="{shadow}"/><stop offset="1" stop-color="#000" stop-opacity="0"/>'
    defs = [f'<linearGradient id="{prefix}-{name}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"><stop offset="0" {fade}'
            f'</linearGradient>' for name, (x1, y1, x2, y2) in (("v-top", (0, 1, 0, 0)), ("v-bottom", (0, 0, 0, 1)),
                                                                ("v-left", (1, 0, 0, 0)), ("v-right", (0, 0, 1, 0)))]
    parts = []
    for row in range(3):
        for col in range(3):
            name = names[row][col]
            x, y, w, h = xs[col], ys[row], ws[col], hs[row]
            body = []
            # shadow: radial in the corners, linear along the edges, nothing in the middle. Every tile's shapes stay
            # inside its own cell: Plasma takes the frame's margins from the tiles' sizes.
            if row != 1 and col != 1:                           # corner: a cell-sized rect, radial fill
                round_top = r and row == 0
                cx = (wx + r if col == 0 else wx + ww - r) if round_top else (wx if col == 0 else wx + ww)
                cy = wy + r if round_top else (wy if row == 0 else wy + wh)
                rad = PAD + (r if round_top else 0)
                gid = f"{prefix}-c{row}{col}"
                defs.append(f'<radialGradient id="{gid}" cx="{cx}" cy="{cy}" r="{rad}" gradientUnits="userSpaceOnUse">'
                            f'<stop offset="{(rad - PAD) / rad:.3f}" {fade}</radialGradient>')
                body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{gid})"/>')
            elif row == 1 and col != 1:                         # left/right edge
                gx = 0 if col == 0 else x + w - PAD
                grad = "v-left" if col == 0 else "v-right"
                body.append(f'<rect x="{gx}" y="{y}" width="{PAD}" height="{h}" fill="url(#{prefix}-{grad})"/>')
            elif row != 1:                                      # top/bottom edge
                gy = 0 if row == 0 else y + h - PAD
                grad = "v-top" if row == 0 else "v-bottom"
                body.append(f'<rect x="{x}" y="{gy}" width="{w}" height="{PAD}" fill="url(#{prefix}-{grad})"/>')
            # the window's own frame inside this tile
            fx1, fy1 = max(x, wx), max(y, wy)
            fx2, fy2 = min(x + w, wx + ww), min(y + h, wy + wh)
            if fx2 > fx1 and fy2 > fy1:
                rounded = r and row == 0 and col != 1
                if rounded:
                    cx = wx + r if col == 0 else wx + ww - r
                    cy = wy + r
                    path = (f"M{fx1},{fy2} L{fx1},{cy} A{r},{r} 0 0 1 {cx},{wy} L{fx2},{wy} L{fx2},{fy2} Z"
                            if col == 0 else
                            f"M{fx1},{fy2} L{fx1},{wy} L{cx},{wy} A{r},{r} 0 0 1 {fx2},{cy} L{fx2},{fy2} Z")
                    body.append(f'<path d="{path}" fill="{bar}"/>')
                else:
                    body.append(f'<rect x="{fx1}" y="{fy1}" width="{fx2 - fx1}" height="{fy2 - fy1}" fill="{bar}"/>')
                if d.separator and row == 0:
                    body.append(f'<rect x="{fx1}" y="{fy2 - 1}" width="{fx2 - fx1}" height="1" fill="{d.separator}"/>')
            parts.append(f'<g id="{prefix}-{name}">{"".join(body)}</g>')
    return defs, parts


def decoration_svg(d: Deco, m: dict) -> str:
    defs, parts = [], []
    for prefix, active in (("decoration", True), ("decoration-inactive", False)):
        dd, pp = _frame_parts(prefix, d, m, active)
        defs += dd
        parts += pp
    C, top = _grid(m)
    size_w, size_h = 2 * C + 10, top + 10 + C
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size_w}" height="{size_h}">'
            f'<defs>{"".join(defs)}</defs>{"".join(parts)}</svg>')


# ---------------------------------------------------------------- buttons
def _glyph(kind: str, s: float, color: str, width: float, cx: float, cy: float) -> str:
    """A line glyph for one button, centered on (cx, cy), about s wide."""
    h = s / 2
    line = f'fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "close":
        return (f'<path d="M{cx - h},{cy - h} L{cx + h},{cy + h} M{cx - h},{cy + h} L{cx + h},{cy - h}" {line}/>')
    if kind == "minimize":
        return f'<path d="M{cx - h},{cy + h * .15} L{cx + h},{cy + h * .15}" {line}/>'
    if kind == "maximize":
        return f'<rect x="{cx - h}" y="{cy - h}" width="{s}" height="{s}" rx="{s * .12}" {line}/>'
    if kind == "restore":
        k = s * .78
        return (f'<rect x="{cx - h}" y="{cy - h + s - k}" width="{k}" height="{k}" rx="{s * .1}" {line}/>'
                f'<path d="M{cx - h + s - k},{cy - h + s - k} L{cx - h + s - k},{cy - h} L{cx + h},{cy - h} '
                f'L{cx + h},{cy - h + k} L{cx - h + k},{cy - h + k}" {line}/>')
    if kind == "alldesktops":
        return (f'<circle cx="{cx}" cy="{cy}" r="{h}" {line}/>'
                f'<circle cx="{cx}" cy="{cy}" r="{h * .3}" fill="{color}"/>')
    if kind == "keepabove":
        return f'<path d="M{cx - h},{cy + h * .4} L{cx},{cy - h * .4} L{cx + h},{cy + h * .4}" {line}/>'
    if kind == "keepbelow":
        return f'<path d="M{cx - h},{cy - h * .4} L{cx},{cy + h * .4} L{cx + h},{cy - h * .4}" {line}/>'
    if kind == "shade":
        return f'<path d="M{cx - h},{cy - h * .5} L{cx + h},{cy - h * .5} M{cx - h},{cy + h * .3} L{cx + h},{cy + h * .3}" {line}/>'
    # help: a question mark
    return (f'<path d="M{cx - h * .55},{cy - h * .35} A{h * .55},{h * .55} 0 1 1 {cx},{cy + h * .15} '
            f'L{cx},{cy + h * .35}" {line}/><circle cx="{cx}" cy="{cy + h * .85}" r="{width * .6}" fill="{color}"/>')


def _state(kind: str, d: Deco, m: dict, state: str) -> str:
    """The -center element of one button in one state (active, hover, pressed, inactive)."""
    w, hgt = m["button_w"], m["button"]
    cx, cy = w / 2, hgt / 2
    ink = d.ink_inactive if state == "inactive" else d.ink
    bg_ink = d.bar if state != "inactive" else d.bar_inactive
    g = max(6.0, hgt * (0.36 if d.button != "tile" else 0.3))
    width = d.glyph * hgt / 20 if d.button != "tile" else d.glyph
    out = [f'<rect x="0" y="0" width="{w}" height="{hgt}" fill="#000" fill-opacity="0"/>']   # the element's full size
    close = kind == "close"
    if d.button == "circle":
        if state in ("hover", "pressed"):
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{hgt / 2}" fill="{ink}" '
                       f'fill-opacity="{1 if state == "hover" else 0.7}"/>')
            ink = bg_ink
        out.append(_glyph(kind, g, ink, width, cx, cy))
    elif d.button == "dots":
        light = {"close": d.ink, "minimize": "#8a8a8a", "maximize": "#5a5a5a"}.get(kind, "#5a5a5a")
        fill = d.ink_inactive if state == "inactive" else light
        opacity = 0.6 if state == "inactive" else 1
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{hgt * .3}" fill="{fill}" fill-opacity="{opacity}"/>')
        if state in ("hover", "pressed"):
            out.append(_glyph(kind, hgt * .26, d.bar, max(1.0, width * .9), cx, cy))
    elif d.button == "box":
        k = hgt * .82
        fill = ink if state in ("hover", "pressed") else "none"
        out.append(f'<rect x="{cx - k / 2 + .5}" y="{cy - k / 2 + .5}" width="{k - 1}" height="{k - 1}" '
                   f'fill="{fill}" stroke="{ink}" stroke-width="1"/>')
        out.append(_glyph(kind, g * .9, bg_ink if fill != "none" else ink, width, cx, cy))
    elif d.button == "tile":
        if state in ("hover", "pressed"):
            fill = d.close if close and d.close else (d.hover or "#2a2a2a")
            out.append(f'<rect x="0" y="0" width="{w}" height="{hgt}" fill="{fill}"/>')
            if close and d.close:
                ink = d.bar
        out.append(_glyph(kind, hgt * .3, ink, width, cx, cy))
    elif d.button == "bold":
        if close and d.close and state != "inactive":
            k = hgt * .9
            out.append(f'<rect x="{cx - k / 2}" y="{cy - k / 2}" width="{k}" height="{k}" rx="{k * .12}" '
                       f'fill="{d.close}" fill-opacity="{0.85 if state == "pressed" else 1}"/>')
            ink = d.bar
        elif state in ("hover", "pressed"):
            k = hgt * .9
            out.append(f'<rect x="{cx - k / 2}" y="{cy - k / 2}" width="{k}" height="{k}" rx="{k * .12}" '
                       f'fill="{d.ink}" fill-opacity="0.18"/>')
        out.append(_glyph(kind, g * .9, ink, width, cx, cy))
    else:                                                   # "line": glyph only, a faint square on hover
        if state in ("hover", "pressed"):
            out.append(f'<rect x="0" y="0" width="{w}" height="{hgt}" rx="2" fill="{d.ink}" fill-opacity="0.16"/>')
        out.append(_glyph(kind, g, ink, width, cx, cy))
    return f'<g id="{state}-center">{"".join(out)}</g>'


def button_svg(kind: str, d: Deco, m: dict) -> str:
    """Every state of one button, stacked at the same spot (rendered one id at a time)."""
    body = "".join(_state(kind, d, m, state) for state in STATES)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{m["button_w"]}" height="{m["button"]}">{body}</svg>'


def rc_text(d: Deco, m: dict, align: str) -> str:
    T, B = m["title"], m["button"]
    margin = (T - B) // 2
    edge = m["edge"]
    return f"""[General]
ActiveTextColor={_rgba(d.ink)}
InactiveTextColor={_rgba(d.ink_inactive)}
TitleAlignment={align}
TitleVerticalAlignment=Center
Animation=120
Shadow=true
DecorationPosition=0

[Layout]
BorderLeft={m['side']}
BorderRight={m['side']}
BorderBottom={m['bottom']}
TitleEdgeTop=0
TitleEdgeBottom=0
TitleEdgeLeft={edge}
TitleEdgeRight={edge}
TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=0
TitleEdgeLeftMaximized={edge}
TitleEdgeRightMaximized={edge}
TitleBorderLeft=10
TitleBorderRight=10
TitleHeight={T}
ButtonWidth={m['button_w']}
ButtonWidthMenu={B}
ButtonHeight={B}
ButtonSpacing={m['spacing']}
ButtonMarginTop={margin}
ButtonMarginTopMaximized={margin}
ExplicitButtonSpacer=10
PaddingTop={PAD}
PaddingBottom={PAD}
PaddingLeft={PAD}
PaddingRight={PAD}
"""


def build(deco_id: str, ident: str, size="Default", align="Center", border="No sides"):
    """Write the Aurorae theme `ident` for this design (sizes, borders and title alignment baked in)."""
    d = DECOS[deco_id]
    m = metrics(d, SCALES.get(size, 1.0), border)
    dest = THEMES / ident
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    (dest / "decoration.svg").write_text(decoration_svg(d, m))
    for kind in BUTTONS:
        (dest / f"{kind}.svg").write_text(button_svg(kind, d, m))
    (dest / f"{ident}rc").write_text(rc_text(d, m, align))
    name = f"Grimoire {deco_id.title()}"
    (dest / "metadata.json").write_text(json.dumps({
        "KPlugin": {"Id": ident, "Name": name, "Description": "Black & white window decoration from Grimoire MuraL",
                    "Authors": [{"Name": "cookedaj"}], "License": "GPL-3.0-or-later", "Version": "1.0"},
        "KPackageStructure": "KWin/Aurorae",
    }, indent=2))
    (dest / "metadata.desktop").write_text(
        f"[Desktop Entry]\nName={name}\nX-KDE-PluginInfo-Name={ident}\nX-KDE-PluginInfo-Author=cookedaj\n"
        "X-KDE-PluginInfo-License=GPL-3.0-or-later\nX-KDE-PluginInfo-Version=1.0\n")


def next_ident(current_theme: str) -> str:
    """Alternate between two folder names, so KWin never keeps a cached copy of the theme it shows now."""
    return f"{PREFIX}-b" if current_theme == f"__aurorae__svg__{PREFIX}" else PREFIX


def remove_unused(in_use: str | None):
    """Remove our own generated theme folders except the one in use (None: a Breeze or community design is)."""
    for ident in (PREFIX, f"{PREFIX}-b"):
        if ident != in_use:
            shutil.rmtree(THEMES / ident, ignore_errors=True)
