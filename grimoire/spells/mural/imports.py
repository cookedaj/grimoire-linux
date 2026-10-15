# SPDX-License-Identifier: GPL-3.0-or-later
"""Import your own designs into a MuraL tab (the Import… button under the big preview).

Pictures go into the MuraL library (library.add), like "Add files…" on the Desktop tab. Themes (an archive, a plain
.colors/.colorscheme file or a folder) go through store.install_from, the same unpacking, checks and copying a
community download gets, and land in the store's registry as item "import:<sha256 prefix>", so the tabs that list
community designs show them with no changes of their own. Nothing from an import is ever run.

Runs on worker threads (no widgets); errors are RuntimeError with a message for the user.
"""
import hashlib
import os
import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QImageReader, QPainter

from grimoire.fsutil import human
from grimoire.i18n import isolate, ltr, tr, tr_noop
from grimoire.paths import DATA
from grimoire.spells.mural import store

ARCHIVES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".tbz")
IMAGES = (".png", ".jpg", ".jpeg", ".webp")
MAX_IMAGE = 100 * 1024 * 1024
MAX_PIXELS = 20000 * 20000               # a tiny file can claim a gigantic picture
PREVIEWS = DATA / "mural" / "imports"
AUTHOR = "Imported"                       # the registry's author field; shown as "Imported by you" (screens.by_line)


@dataclass(frozen=True)
class Importer:
    what: str                   # tr_noop'd: what this tab imports, for messages ("an icon theme")
    kind: str = ""              # store kind for themes ("" = pictures only)
    images: bool = False        # also takes pictures (into the library)
    files: tuple = ()           # plain theme files it takes besides archives and folders


# tab key (ScreenTab.key) → what its Import… button takes
IMPORTERS = {
    "lock": Importer(tr_noop("grimoire.spells.mural.imports", "a picture (PNG, JPEG or WebP)"), images=True),
    "login": Importer(tr_noop("grimoire.spells.mural.imports", "an SDDM login theme or a background picture"), "sddm",
                      images=True),
    "splash": Importer(tr_noop("grimoire.spells.mural.imports", "a Plasma splash screen (look-and-feel package)"),
                       "splash"),
    "boot": Importer(tr_noop("grimoire.spells.mural.imports", "a Plymouth boot theme"), "plymouth"),
    "style": Importer(tr_noop("grimoire.spells.mural.imports", "a Plasma style"), "plasma"),
    "windows": Importer(tr_noop("grimoire.spells.mural.imports", "an Aurorae window decoration"), "aurorae"),
    "colors": Importer(tr_noop("grimoire.spells.mural.imports", "a color scheme (.colors)"), "colors",
                       files=(".colors",)),
    "terminal": Importer(tr_noop("grimoire.spells.mural.imports", "a Konsole color scheme (.colorscheme)"), "konsole",
                         files=(".colorscheme",)),
    "cursor": Importer(tr_noop("grimoire.spells.mural.imports", "a cursor theme"), "cursor"),
    "icons": Importer(tr_noop("grimoire.spells.mural.imports", "an icon theme"), "icons"),
}


def importer(tab_key: str) -> Importer | None:
    return IMPORTERS.get(tab_key)


def name_filter(imp: Importer) -> str:
    """The file dialog's filter for this importer."""
    pats = [f"*{e}" for e in (*(ARCHIVES if imp.kind else ()), *imp.files, *(IMAGES if imp.images else ()))]
    pats += [p.upper() for p in pats if imp.images and p[2:] in ("png", "jpg", "jpeg", "webp")]
    return tr("grimoire.spells.mural.imports", "Importable files ({patterns})").format(patterns=" ".join(pats))


def _suffix(path: Path) -> str:
    name = path.name.lower()
    return next((e for e in ARCHIVES if name.endswith(e)), path.suffix.lower())


# ---------------------------------------------------------------- pictures
def _image_magic(head: bytes) -> bool:
    return (head.startswith(b"\x89PNG\r\n\x1a\n") or head.startswith(b"\xff\xd8\xff")
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP"))


def check_image(path: Path):
    """Raise RuntimeError unless path is a PNG/JPEG/WebP picture of a sane size that Qt can read."""
    if path.suffix.lower() not in IMAGES:
        raise RuntimeError(tr("grimoire.spells.mural.imports", "{file} isn't a PNG, JPEG or WebP picture.")
                           .format(file=isolate(path.name)))
    if path.stat().st_size > MAX_IMAGE:
        raise RuntimeError(tr("grimoire.spells.mural.imports", "{file} is too big (the limit is {limit}).")
                           .format(file=isolate(path.name), limit=ltr(human(MAX_IMAGE))))
    with open(path, "rb") as f:
        head = f.read(16)
    reader = QImageReader(str(path))
    size = reader.size() if _image_magic(head) else QSize()     # the header only: nothing decoded yet
    if size.isValid() and size.width() * size.height() > MAX_PIXELS:
        raise RuntimeError(tr("grimoire.spells.mural.imports", "{file} is too large a picture ({size}).")
                           .format(file=isolate(path.name), size=ltr(f"{size.width()}×{size.height()}")))
    if not size.isValid() or not reader.canRead():
        raise RuntimeError(tr("grimoire.spells.mural.imports", "{file} isn't a picture Grimoire can read.")
                           .format(file=isolate(path.name)))


def import_image(path: Path) -> Path:
    """Check and copy a picture into the MuraL library; returns its library path."""
    from grimoire.spells.mural import library
    check_image(path)
    added = library.add([path])
    if not added:
        raise RuntimeError(tr("grimoire.spells.mural.imports", "Couldn't add {file} to the library.")
                           .format(file=isolate(path.name)))
    return added[0]


# ---------------------------------------------------------------- themes
def _digest(path: Path) -> str:
    """Identifies an import, so importing the same thing again updates it instead of clashing with itself."""
    h = hashlib.sha256()
    if path.is_dir():
        for here, dirs, files in os.walk(path):
            dirs.sort()
            for n in sorted(files):
                p = Path(here) / n
                try:
                    h.update(f"{p.relative_to(path)}\0{p.lstat().st_size}\0".encode())
                except OSError:
                    pass
    else:
        with open(path, "rb") as f:
            while chunk := f.read(1 << 20):
                h.update(chunk)
    return h.hexdigest()


def import_theme(imp: Importer, path: Path) -> list[dict]:
    """Install a theme archive, theme file or folder of the tab's kind; returns the registry entries."""
    what = tr("grimoire.spells.mural.imports", imp.what)
    if not path.is_dir():
        if _suffix(path) not in (*ARCHIVES, *imp.files):
            raise RuntimeError(tr("grimoire.spells.mural.imports",
                                  "{file} isn't {what}. Pick an archive (.zip, .tar.gz, .tar.xz…) or a folder.")
                               .format(file=isolate(path.name), what=what))
        if path.stat().st_size > store.MAX_ARCHIVE:
            raise RuntimeError(tr("grimoire.spells.mural.imports", "{file} is too big (the limit is {limit}).")
                               .format(file=isolate(path.name), limit=ltr(human(store.MAX_ARCHIVE))))
        if _suffix(path) in ARCHIVES and not (zipfile.is_zipfile(path) or tarfile.is_tarfile(path)):
            raise RuntimeError(tr("grimoire.spells.mural.imports", "{file} isn't a valid archive (it may be damaged).")
                               .format(file=isolate(path.name)))
    sha = _digest(path)[:16]
    item_id = f"import:{sha}"
    name = path.name[:-len(_suffix(path))] if not path.is_dir() and _suffix(path) else path.name
    work = store.STORE_CACHE / "imports" / sha
    try:
        entries = store.install_from(imp.kind, path, item_id, name or "import", AUTHOR, work=work)
    except store.Unusable:
        raise RuntimeError(tr("grimoire.spells.mural.imports", "Didn't find {what} in {file}.")
                           .format(what=what, file=isolate(path.name))) from None
    except (RuntimeError, OSError, EOFError, ValueError) as e:   # unsafe or damaged archives, name clashes
        raise RuntimeError(tr("grimoire.spells.mural.imports", "Couldn't import {file}: {error}")
                           .format(file=isolate(path.name), error=e)) from None
    finally:
        shutil.rmtree(work, ignore_errors=True)
    for e in entries:
        if not e.get("preview") and imp.kind in ("colors", "konsole"):
            e["preview"] = swatch(e)
            store._record(e)
    return entries


def _ini_colors(entry: dict) -> list[QColor]:
    """A scheme's main colors, in file order, for its swatch."""
    ini = store._ini(Path(entry["path"]))
    out = []
    for section in ini.sections():
        for key in ("BackgroundNormal", "ForegroundNormal", "Color", "DecorationFocus"):
            raw = ini.get(section, key, fallback="")
            parts = [p.strip() for p in raw.split(",")[:3]]
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                out.append(QColor(*(min(255, int(p)) for p in parts)))
    return out[:16]


def swatch(entry: dict) -> str:
    """A preview for a color scheme with no picture: its colors as bars, its name underneath."""
    colors = _ini_colors(entry) or [QColor("#222222")]
    w, h = 1280, 720
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor("#0b0b0b"))
    p = QPainter(img)
    bar = (w - 160) / len(colors)
    for i, c in enumerate(colors):
        p.fillRect(QRectF(80 + i * bar, 120, bar, 420), c)
    p.setPen(QColor("#e8e8e8"))
    p.setFont(QFont("IBM Plex Sans", 26))
    p.drawText(QRectF(0, 580, w, 60), Qt.AlignmentFlag.AlignCenter, entry["name"])
    p.end()
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    out = PREVIEWS / (hashlib.sha1(entry["key"].encode()).hexdigest()[:16] + ".png")
    img.scaled(QSize(960, 540), Qt.AspectRatioMode.KeepAspectRatio,
               Qt.TransformationMode.SmoothTransformation).save(str(out))
    return str(out)


# ---------------------------------------------------------------- one call for the tab
def run(tab_key: str, paths: list[str]) -> dict:
    """Import paths for a tab. Returns {"images": [library names], "entries": [registry entries],
    "errors": [messages]}; never raises."""
    imp = IMPORTERS[tab_key]
    out = {"images": [], "entries": [], "errors": []}
    for raw in paths:
        path = Path(raw)
        try:
            if not path.exists():
                raise RuntimeError(tr("grimoire.spells.mural.imports", "{file} doesn't exist any more.")
                                   .format(file=isolate(path.name)))
            if imp.images and not path.is_dir() and path.suffix.lower() in IMAGES:
                out["images"].append(import_image(path).name)
            elif imp.kind:
                out["entries"] += import_theme(imp, path)
            else:
                raise RuntimeError(tr("grimoire.spells.mural.imports", "{file} isn't {what}.")
                                   .format(file=isolate(path.name), what=tr("grimoire.spells.mural.imports", imp.what)))
        except RuntimeError as e:
            out["errors"].append(str(e))
        except Exception as e:            # anything unexpected: a message, never a crash or a half-import
            out["errors"].append(tr("grimoire.spells.mural.imports", "Couldn't import {file}: {error}")
                                 .format(file=isolate(path.name), error=e))
    return out
