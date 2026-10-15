# SPDX-License-Identifier: GPL-3.0-or-later
"""Icons tab: the icon theme. Your current theme, Grimoire's monochrome themes (Breeze toned to grays by icongen,
written into ~/.local/share/icons on Apply), other themes on this PC and community icon packs. Previews draw real
icons from each theme's own files (following its Inherits= chain for anything it doesn't include).
"""
from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QGridLayout, QLabel

from grimoire.i18n import tr, tr_noop
from grimoire.paths import HOME
from grimoire.spells.mural import icongen
from grimoire.spells.mural import store as community
from grimoire.spells.mural.kde import kread, run_tool
from grimoire.spells.mural.screens import Choice, Design, ScreenTab, WrapCheck, by_line

USER_ICONS = HOME / ".local/share/icons"
SEARCH = [USER_ICONS, HOME / ".icons", Path("/usr/share/icons")]
FLATPAK = [Path("/var/lib/flatpak/exports/share/icons/hicolor"),       # Flatpak apps register icons here
           HOME / ".local/share/flatpak/exports/share/icons/hicolor"]
CHANGE_ICONS = "/usr/lib/x86_64-linux-gnu/libexec/plasma-changeicons"
SAMPLE = [
    ("system-file-manager", tr_noop("grimoire.spells.mural.icons", "Files")),
    ("utilities-terminal", tr_noop("grimoire.spells.mural.icons", "Terminal")),
    ("firefox", "Firefox"),
    ("systemsettings", tr_noop("grimoire.spells.mural.icons", "Settings")),
    ("steam", "Steam"),
    ("com.discordapp.Discord", "Discord"),
    ("com.spotify.Client", "Spotify"),
    ("com.obsproject.Studio", "OBS"),
    ("folder", tr_noop("grimoire.spells.mural.icons", "Folder")),
    ("user-home", tr_noop("grimoire.spells.mural.icons", "Home")),
    ("folder-download", tr_noop("grimoire.spells.mural.icons", "Downloads")),
    ("user-trash", tr_noop("grimoire.spells.mural.icons", "Trash")),
    ("text-x-generic", tr_noop("grimoire.spells.mural.icons", "Text")),
    ("image-x-generic", tr_noop("grimoire.spells.mural.icons", "Image")),
    ("video-x-generic", tr_noop("grimoire.spells.mural.icons", "Video")),
    ("audio-x-generic", tr_noop("grimoire.spells.mural.icons", "Audio")),
    ("application-x-executable", tr_noop("grimoire.spells.mural.icons", "App")),
    ("preferences-desktop-wallpaper", tr_noop("grimoire.spells.mural.icons", "Wallpaper")),
]
DESIGNS = [          # Grimoire's own; ids never change (saved looks and shared setups name them)
    Design("Grimoire-Icons-Gray", "Grimoire Gray",
           tr_noop("grimoire.spells.mural.icons", "Breeze's icons in true grays: every color becomes its own shade, "
                   "so nothing loses its shape.")),
    Design("Grimoire-Icons-Ink", "Grimoire Ink",
           tr_noop("grimoire.spells.mural.icons", "High contrast: five bold steps from black to white, like a print.")),
    Design("Grimoire-Icons-Silver", "Grimoire Silver",
           tr_noop("grimoire.spells.mural.icons", "Light, soft grays that glow on a black panel.")),
    Design("Grimoire-Icons-Graphite", "Grimoire Graphite",
           tr_noop("grimoire.spells.mural.icons", "Deep charcoal grays that sit quietly on light backgrounds.")),
    Design("Grimoire-Icons-Negative", "Grimoire Negative",
           tr_noop("grimoire.spells.mural.icons", "Grays turned inside out like a photo negative: white paper "
                   "becomes black.")),
    Design("Grimoire-Icons-Stencil", "Grimoire Stencil",
           tr_noop("grimoire.spells.mural.icons", "Pure black and white only, cut like a stencil. Striking and "
                   "graphic.")),
]
BASES = [("dark", tr_noop("grimoire.spells.mural.icons", "Dark panels")),
         ("light", tr_noop("grimoire.spells.mural.icons", "Light panels"))]
DEFAULTS = {"base": "dark", "apps": True}
SKIP = {"hicolor", "locolor", "default"}
SIZE_ORDER = ["scalable", "96", "64", "48", "256", "128", "32", "96x96", "64x64", "48x48", "256x256", "128x128"]


def theme_dir(name: str) -> Path | None:
    return next((base / name for base in SEARCH if (base / name / "index.theme").is_file()), None)


def theme_name(name: str) -> str:
    d = theme_dir(name)
    if not d:
        return name
    c = ConfigParser(interpolation=None, strict=False)
    c.read(d / "index.theme", encoding="utf-8")
    return c.get("Icon Theme", "Name", fallback=name)


@lru_cache(maxsize=32)
def _index(theme: str) -> dict:
    """icon name -> best file in this theme (prefers scalable, then larger sizes)."""
    d = theme_dir(theme)
    found: dict[str, tuple[int, Path]] = {}
    if not d:
        return {}
    for f in d.rglob("*"):
        if f.suffix not in (".svg", ".png") or not f.is_file():
            continue
        path = str(f)
        rank = next((i for i, s in enumerate(SIZE_ORDER) if f"/{s}/" in path), 99)
        if f.stem not in found or rank < found[f.stem][0]:
            found[f.stem] = (rank, f)
    return {k: v[1] for k, v in found.items()}


def find_icon(theme: str, name: str, seen=None) -> Path | None:
    seen = seen or set()
    if theme in seen:
        return None
    seen.add(theme)
    hit = _index(theme).get(name)
    if hit:
        return hit
    d = theme_dir(theme)
    if d:
        c = ConfigParser(interpolation=None, strict=False)
        c.read(d / "index.theme", encoding="utf-8")
        for parent in c.get("Icon Theme", "Inherits", fallback="hicolor").split(","):
            hit = find_icon(parent.strip(), name, seen)
            if hit:
                return hit
    for base in FLATPAK:                                   # last resort: the app's own Flatpak icon
        for sub in ("scalable/apps", "512x512/apps", "256x256/apps", "128x128/apps", "64x64/apps", "48x48/apps"):
            for ext in (".svg", ".png"):
                if (base / sub / f"{name}{ext}").is_file():
                    return base / sub / f"{name}{ext}"
    return None


def current() -> str:
    return kread("kdeglobals", "Icons", "Theme") or "breeze"


def generated(theme: str) -> bool:
    return theme in icongen.TONES


def installed_themes() -> list[str]:
    """Icon themes on this PC that a person would pick (not hidden, has icon folders), by folder name."""
    found = {}
    for base in reversed(SEARCH):                      # user folders win over system ones with the same name
        if not base.is_dir():
            continue
        for d in base.iterdir():
            if d.name in SKIP or not (d / "index.theme").is_file():
                continue
            c = ConfigParser(interpolation=None, strict=False)
            try:
                c.read(d / "index.theme", encoding="utf-8")
            except (OSError, ValueError):
                continue
            if (c.has_option("Icon Theme", "Directories")
                    and c.get("Icon Theme", "Hidden", fallback="false").lower() != "true"):
                found[d.name] = True
    return sorted(found, key=str.lower)


def _draw(p: QPainter, path: Path | None, rect: QRectF, tone):
    if path is None:
        p.setPen(QColor(90, 90, 90))
        p.drawRoundedRect(rect, 12, 12)
    elif path.suffix == ".svg":
        QSvgRenderer(icongen.toned_svg_bytes(path, tone, False) if tone else str(path)).render(p, rect)
    else:
        img = QImage(str(path))
        p.drawImage(rect, icongen.tone_image(img, tone) if tone and not img.isNull() else img)


def render(theme: str, o: dict | None = None, w=1280, h=720, sample=SAMPLE, cols=6, size=84, labels=True) -> QImage:
    """A grid of real icons. Grimoire's themes are toned on the fly from their base theme, exactly as Apply
    writes them (app icons from other themes too, when that's on)."""
    o = {**DEFAULTS, **(o or {})}
    tone, source = None, theme
    if generated(theme):
        tone, source = icongen.TONES[theme], icongen.BASES[o["base"]]
    light = generated(theme) and o["base"] == "light"
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(236, 236, 236) if light else QColor(10, 10, 10))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    rows = (len(sample) + cols - 1) // cols
    cell_w, cell_h = w / (cols + 1), (h - 40) / rows
    base_dirs = {theme_dir(source), theme_dir("breeze")} - {None}
    for k, (name, label) in enumerate(sample):
        cx = cell_w * (k % cols + 1)
        cy = 20 + cell_h * (k // cols + 0.42)
        rect = QRectF(cx - size / 2, cy - size / 2, size, size)
        path = find_icon(source, name)
        from_base = path is not None and any(b in path.parents for b in base_dirs)
        _draw(p, path, rect, tone if tone and (from_base or o["apps"]) else None)
        if labels:
            p.setPen(QColor(90, 90, 90) if light else QColor(140, 140, 140))
            p.setFont(QFont("IBM Plex Sans", 10))
            p.drawText(QRectF(cx - 80, cy + size / 2 + 10, 160, 22), Qt.AlignmentFlag.AlignCenter,
                       tr("grimoire.spells.mural.icons", label))
    p.end()
    return img


class IconsTab(ScreenTab):
    key = "icons"
    context = "grimoire.spells.mural.icons"
    subtitle = tr_noop("grimoire.spells.mural.icons", "Your icon theme. Previews draw real icons from each theme's "
                       "files. Grimoire's monochrome themes are made on your PC when you apply them.")
    apply_label = tr_noop("grimoire.spells.mural.icons", "Apply icons")
    apply_busy = tr_noop("grimoire.spells.mural.icons", "Applying… making a theme takes a few seconds.")
    store = ["icons"]

    def designs(self):
        cur = current()
        own = [] if generated(cur) else [
            Design(cur, theme_name(cur), tr("grimoire.spells.mural.icons", "The icon theme you're using now."))]
        community_ids = {e["ident"] for e in community.installed("icons")}
        others = [Design(t, theme_name(t), tr("grimoire.spells.mural.icons", "Installed on this PC."))
                  for t in installed_themes()
                  if t != cur and not generated(t) and t not in community_ids]
        return own + DESIGNS + others + [Design(e["ident"], e["name"], by_line(e))
                                         for e in community.installed("icons") if e["ident"] != cur]

    def build_options(self, lay):
        grid = QGridLayout()
        self.base = Choice([(k, tr("grimoire.spells.mural.icons", v)) for k, v in BASES], self.changed)
        self.base_label = QLabel(tr("grimoire.spells.mural.icons", "Made for"))
        grid.addWidget(self.base_label, 0, 0)
        grid.addWidget(self.base, 0, 1)
        lay.addLayout(grid)
        self.apps = WrapCheck(tr("grimoire.spells.mural.icons", "Gray app icons from other themes too"))
        self.apps.toggled.connect(self.changed)
        lay.addWidget(self.apps)
        self.gallery.currentRowChanged.connect(self._update_options)

    def showEvent(self, e):
        super().showEvent(e)
        self._update_options()

    def _update_options(self, *_):
        d = self.current()
        own = bool(d and generated(d.id))
        for wdg in (self.base, self.base_label, self.apps):
            wdg.setVisible(own)

    def options(self):
        return {"base": self.base.value(), "apps": self.apps.isChecked()}

    def set_options(self, o):
        o = {**DEFAULTS, **o}
        self.base.set_value(o["base"])
        self.apps.setChecked(bool(o["apps"]))

    def preview(self, design, o):
        return render(design.id, o)

    def thumbnail(self, design, o):
        """Cards show eight icons big enough to tell the themes apart."""
        return render(design.id, o, 640, 360, SAMPLE[:8], cols=4, size=96, labels=False)

    def apply(self, design, o):
        o = {**DEFAULTS, **o}
        if generated(design.id):
            icongen.write_theme(design.id, icongen.BASES[o["base"]], bool(o["apps"]), USER_ICONS, SEARCH)
            _index.cache_clear()
        run_tool([CHANGE_ICONS, design.id])
        return tr("grimoire.spells.mural.icons", "Applied ✓")
