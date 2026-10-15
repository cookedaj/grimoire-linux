# SPDX-License-Identifier: GPL-3.0-or-later
"""Grimoire's own monochrome icon themes: Breeze's colorful icons (apps, folders, file types, devices…) redrawn in
grays with a tone curve, written as a real icon theme that inherits Breeze for everything else.

SVGs are recolored as text (every hex/rgb color through the tone), and for icons of 32 px and up the KDE
color-scheme stylesheet is switched off so folders stay gray instead of taking the accent color; small icons keep it
and still follow the text color. PNGs (app icons from hicolor and Flatpaks) are toned through a gray color table.
No widgets: safe on worker threads.
"""
import os
import re
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QColor, QImage, QPainter

from grimoire.paths import HOME

MARKER = ".grimoire-icons"
COLORFUL = ("apps", "places", "mimetypes", "devices", "categories", "preferences", "emblems", "status", "emotes")
BASES = {"dark": "breeze-dark", "light": "breeze"}
APP_SOURCES = [Path("/usr/share/icons/hicolor"), HOME / ".local/share/icons/hicolor",
               Path("/var/lib/flatpak/exports/share/icons/hicolor"),
               HOME / ".local/share/flatpak/exports/share/icons/hicolor"]


@dataclass(frozen=True)
class Tone:
    name: str
    lo: float = 0.0              # output range: darkest / lightest gray
    hi: float = 1.0
    contrast: float = 1.0        # >1 pushes grays apart around the middle
    levels: int = 0              # >0 posterizes to this many grays
    invert: bool = False

    def __call__(self, v: float) -> float:
        if self.invert:
            v = 1 - v
        if self.contrast != 1:
            v = min(1.0, max(0.0, (v - 0.5) * self.contrast + 0.5))
        if self.levels:
            v = round(v * (self.levels - 1)) / (self.levels - 1)
        return self.lo + (self.hi - self.lo) * v


TONES = {            # ids never change: saved looks and shared setups name them
    "Grimoire-Icons-Gray": Tone("Grimoire Gray"),
    "Grimoire-Icons-Ink": Tone("Grimoire Ink", 0.04, 0.98, contrast=1.6, levels=5),
    "Grimoire-Icons-Silver": Tone("Grimoire Silver", 0.42, 0.97),
    "Grimoire-Icons-Graphite": Tone("Grimoire Graphite", 0.07, 0.62),
    "Grimoire-Icons-Negative": Tone("Grimoire Negative", 0.05, 0.95, invert=True),
    "Grimoire-Icons-Stencil": Tone("Grimoire Stencil", 0.06, 0.96, contrast=2.4, levels=2),
}


def luma(r: int, g: int, b: int) -> float:
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def _gray(tone: Tone, r, g, b) -> int:
    return round(min(1.0, max(0.0, tone(luma(r, g, b)))) * 255)


HEX = re.compile(r"(?<!url\()(?<!href=\")#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_-])")
RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
NAMED = re.compile(r"((?:fill|stroke|stop-color|color)\s*[:=]\s*\"?)(red|green|blue|yellow|orange|purple)\b")
NAMED_RGB = {"red": (255, 0, 0), "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
             "orange": (255, 165, 0), "purple": (128, 0, 128)}
SCHEME = re.compile(r"id=\"current-color-scheme\"")


def recolor_svg(text: str, tone: Tone, keep_scheme: bool) -> str:
    def hexrep(m):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        v = _gray(tone, int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        return f"#{v:02x}{v:02x}{v:02x}"

    def rgbrep(m):
        v = _gray(tone, *(min(255, int(x)) for x in m.groups()))
        return m.group(0).split("(")[0] + f"({v},{v},{v}"

    text = HEX.sub(hexrep, text)
    text = RGB.sub(rgbrep, text)
    text = NAMED.sub(lambda m: m.group(1) + "#{0:02x}{0:02x}{0:02x}".format(_gray(tone, *NAMED_RGB[m.group(2)])),
                     text)
    if not keep_scheme:                                # KDE would paint ColorScheme-Accent parts in the accent color
        text = SCHEME.sub('id="grimoire-fixed-colors"', text)
    return text


def tone_image(img: QImage, tone: Tone) -> QImage:
    """A raster icon in the tone's grays, alpha kept."""
    src = img.convertToFormat(QImage.Format.Format_ARGB32)
    gray = src.convertToFormat(QImage.Format.Format_Grayscale8)
    w, h, bpl = gray.width(), gray.height(), gray.bytesPerLine()
    data = bytes(gray.constBits())[: bpl * h]
    idx = QImage(data, w, h, bpl, QImage.Format.Format_Indexed8)
    idx.setColorTable([QColor(g, g, g).rgb() for g in (round(min(1, max(0, tone(i / 255))) * 255)
                                                       for i in range(256))])
    out = idx.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    p.drawImage(0, 0, src)                              # keep the original's transparency
    p.end()
    return out


def keeps_scheme(rel: str) -> bool:
    """Small icons (16-24 px) are near-symbolic: they keep following the color scheme's text color."""
    size = rel.split("/")[1] if "/" in rel else ""
    return size.split("@")[0] in ("8", "12", "16", "22", "24")


def toned_svg_bytes(path: Path, tone: Tone, keep_scheme=True) -> QByteArray:
    return QByteArray(recolor_svg(path.read_text(encoding="utf-8", errors="replace"), tone, keep_scheme).encode())


def is_ours(folder: Path) -> bool:
    return (folder / MARKER).is_file()


def _write(path: Path, data: bytes):
    if path.is_symlink():
        path.unlink()                                   # inside our own generated folder only
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _sections(base_dir: Path) -> dict:
    c = ConfigParser(interpolation=None, strict=False)
    c.optionxform = str
    c.read(base_dir / "index.theme", encoding="utf-8")
    return {s: dict(c[s]) for s in c.sections() if s != "Icon Theme"}


def write_theme(theme: str, base: str, apps: bool, dest_root: Path, search: list[Path]) -> Path:
    """Write (or refresh) dest_root/<theme>: base's colorful icons toned, plus other themes' app icons when apps.
    Never touches a folder we didn't make."""
    tone = TONES[theme]
    base_dir = next((d / base for d in search if (d / base / "index.theme").is_file()), None)
    if base_dir is None:
        raise RuntimeError(f"the {base} icon theme isn't installed")
    folder = dest_root / theme
    if folder.exists() and not is_ours(folder):
        raise RuntimeError(f"{folder} isn't a Grimoire icon theme; not overwriting it")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / MARKER).write_text("Generated by Grimoire Linux → MuraL → Icons. Safe to delete.\n")
    sections, used = _sections(base_dir), {}
    for top in COLORFUL:
        root = base_dir / top
        if not root.is_dir():
            continue
        for sub in sorted(p for p in root.iterdir() if p.is_dir()):
            rel = f"{top}/{sub.name}"
            if rel not in sections:
                continue
            out = folder / rel
            out.mkdir(parents=True, exist_ok=True)
            used[rel] = sections[rel]
            keep = keeps_scheme(rel)
            for f in sub.iterdir():
                if f.name.endswith("-symbolic.svg") or f.suffix not in (".svg", ".png"):
                    continue
                target = out / f.name
                if f.is_symlink():
                    link = os.readlink(f)
                    if link.endswith("-symbolic.svg"):     # not copied: let the base theme answer
                        continue
                    if "/" not in link:                     # a link to a sibling: same link in our copy
                        if not (target.is_symlink() and os.readlink(target) == link):
                            if target.is_symlink() or target.exists():
                                target.unlink()
                            target.symlink_to(link)
                        continue
                    f = f.resolve()
                    if not f.is_file():
                        continue
                if f.suffix == ".svg":
                    _write(target, recolor_svg(f.read_text(encoding="utf-8", errors="replace"), tone, keep).encode())
                else:
                    img = QImage(str(f))
                    if not img.isNull():
                        tone_image(img, tone).save(str(target.with_suffix(".tmp.png")), "PNG")
                        target.with_suffix(".tmp.png").replace(target)
    if apps:
        used.update(_app_icons(folder, tone))
    dirs = sorted(used)
    lines = [f"[Icon Theme]\nName={tone.name}\nComment=Monochrome icons by Grimoire Linux\n"
             f"Inherits={base},hicolor\nDirectories={','.join(dirs)}\n"]
    for d in dirs:
        lines.append(f"[{d}]\n" + "".join(f"{k}={v}\n" for k, v in used[d].items()))
    _write(folder / "index.theme", "\n".join(lines).encode())
    return folder


def _app_icons(folder: Path, tone: Tone) -> dict:
    """Other themes' app icons (hicolor, Flatpaks) toned into extra/<size>; returns their index sections."""
    used = {}
    for src in APP_SOURCES:
        if not src.is_dir():
            continue
        for size_dir in src.iterdir():
            apps = size_dir / "apps"
            if not apps.is_dir():
                continue
            if size_dir.name == "scalable":
                rel, sec = "extra/scalable", {"Size": "64", "Context": "Applications", "Type": "Scalable",
                                              "MinSize": "16", "MaxSize": "512"}
            else:
                n = size_dir.name.split("x")[0]
                if not n.isdigit():
                    continue
                rel, sec = f"extra/{n}", {"Size": n, "Context": "Applications", "Type": "Fixed"}
            out = folder / rel
            out.mkdir(parents=True, exist_ok=True)
            used[rel] = sec
            for f in apps.iterdir():
                if f.name.endswith("-symbolic.svg") or f.suffix not in (".svg", ".png"):
                    continue
                target = out / f.name
                f = f.resolve()
                if not f.is_file():
                    continue
                try:
                    if f.suffix == ".svg":
                        _write(target, recolor_svg(f.read_text(encoding="utf-8", errors="replace"), tone,
                                                   False).encode())
                    else:
                        img = QImage(str(f))
                        if not img.isNull():
                            tone_image(img, tone).save(str(target.with_suffix(".tmp.png")), "PNG")
                            target.with_suffix(".tmp.png").replace(target)
                except OSError:
                    continue                                    # an unreadable icon is skipped, not fatal
    return used
