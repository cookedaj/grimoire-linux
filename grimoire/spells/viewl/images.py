# SPDX-License-Identifier: GPL-3.0-or-later
"""ViewL's files: which ones are pictures (every format Qt's image plugins read, incl. kimageformats' AVIF, HEIF,
JPEG XL and camera RAW), a folder's listing and sort orders, settings (`viewl.json`) and the home page's status line.
Runs off the UI thread; no widgets here."""

import json
import os
import re
import stat
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from grimoire.fsutil import tilde
from grimoire.i18n import tr, tr_noop
from grimoire.paths import CONFIG

SETTINGS = CONFIG / "viewl.json"
DEFAULTS = {
    "folder": "",
    "recent": [],
    "sort": "name",
    "reverse": False,
    "interval": 4,
    "shuffle": False,
    "info": False,
    "size": 1,
}
SORTS = {
    "name": tr_noop("grimoire.spells.viewl.images", "Name"),
    "date": tr_noop("grimoire.spells.viewl.images", "Date modified"),
    "size": tr_noop("grimoire.spells.viewl.images", "Size"),
    "type": tr_noop("grimoire.spells.viewl.images", "Type"),
}
# formats some Qt builds read but that aren't pictures anyone browses
SKIP = {
    "cur",
    "ani",
    "pic",
    "bw",
    "rgb",
    "rgba",
    "sgi",
    "im1",
    "im8",
    "im24",
    "im32",
    "sun",
    "ras",
    "iff",
    "ilbm",
    "lbm",
    "wbmp",
    "pxr",
    "sct",
    "pdd",
    "psdt",
}
# extensions an add-on (kimageformat6-plugins) teaches Qt: named in the "can't open" message when it's missing
PLUGIN_EXT = {
    "avif",
    "heic",
    "heif",
    "jxl",
    "kra",
    "ora",
    "xcf",
    "psd",
    "exr",
    "hdr",
    "qoi",
    "raw",
    "cr2",
    "cr3",
    "nef",
    "arw",
    "dng",
    "orf",
    "rw2",
    "raf",
    "pef",
    "srw",
    "jp2",
    "dds",
    "pcx",
    "tga",
}
PLUGIN_HINT = "sudo apt install kimageformat6-plugins"


@lru_cache(maxsize=1)
def extensions() -> frozenset[str]:
    """Lower-case extensions (no dot) Qt can read here. Asked once: plugins don't change while we run."""
    from PySide6.QtGui import QImageReader

    found = {bytes(f).decode().lower() for f in QImageReader.supportedImageFormats()}
    if "jpeg" in found:
        found |= {"jpg", "jpe", "jfif"}
    if "tiff" in found:
        found.add("tif")
    return frozenset(found - SKIP)


def is_image(name: str) -> bool:
    ext = name.rpartition(".")[2].lower()
    return "." in name and ext in extensions()


@dataclass
class Entry:
    path: Path
    is_dir: bool
    size: int = 0
    mtime: float = 0.0

    @property
    def name(self) -> str:
        return self.path.name


_DIGITS = re.compile(r"(\d+)")


def natural(name: str):
    """'img2' before 'img10', case-insensitive."""
    return [int(t) if t.isdigit() else t.casefold() for t in _DIGITS.split(name)]


def listing(folder: Path, hidden: bool = False) -> list[Entry]:
    """The folder's subfolders and pictures (regular files only: a FIFO named .png would block a reader forever).
    Raises OSError when the folder can't be read."""
    out = []
    with os.scandir(folder) as it:
        for e in it:
            if not hidden and e.name.startswith("."):
                continue
            try:
                if e.is_dir():
                    out.append(Entry(Path(e.path), True))
                elif is_image(e.name):
                    st = e.stat()
                    if stat.S_ISREG(st.st_mode):
                        out.append(Entry(Path(e.path), False, st.st_size, st.st_mtime))
            except OSError:
                continue
    return out


def sort(entries: list[Entry], key: str, reverse: bool) -> list[Entry]:
    """Folders first (always by name), then pictures by key."""
    dirs = sorted((e for e in entries if e.is_dir), key=lambda e: natural(e.name))
    files = [e for e in entries if not e.is_dir]
    if key == "date":
        files.sort(key=lambda e: (e.mtime, natural(e.name)))
    elif key == "size":
        files.sort(key=lambda e: (e.size, natural(e.name)))
    elif key == "type":
        files.sort(key=lambda e: (e.path.suffix.lower(), natural(e.name)))
    else:
        files.sort(key=lambda e: natural(e.name))
    if reverse:
        files.reverse()
    return dirs + files


def load() -> dict:
    try:
        data = json.loads(SETTINGS.read_text())
    except (OSError, ValueError):
        data = {}
    s = dict(DEFAULTS)
    if isinstance(data, dict):
        for k, v in data.items():
            if k in DEFAULTS and type(v) is type(DEFAULTS[k]):
                s[k] = v
    s["recent"] = [r for r in s["recent"] if isinstance(r, str)][:6]
    s["interval"] = min(60, max(1, s["interval"]))
    s["size"] = min(2, max(0, s["size"]))
    if s["sort"] not in SORTS:
        s["sort"] = "name"
    return s


def save(s: dict):
    tmp = SETTINGS.with_name(SETTINGS.name + ".tmp")
    try:
        tmp.write_text(json.dumps({k: s[k] for k in DEFAULTS}, indent=2))
        os.replace(tmp, SETTINGS)
    except OSError:
        pass


def remember(s: dict, folder: Path):
    """The last folder opened and the few before it (the sidebar's Recent)."""
    f = str(folder)
    s["folder"] = f
    s["recent"] = [f] + [r for r in s["recent"] if r != f][:5]
    save(s)


def default_folder() -> Path:
    pics = Path.home() / "Pictures"
    return pics if pics.is_dir() else Path.home()


def status_line() -> str:
    s = load()
    folder = Path(s["folder"]) if s["folder"] else default_folder()
    n = 0
    try:
        with os.scandir(folder) as it:
            for i, e in enumerate(it):
                if i > 20000:
                    break
                n += not e.name.startswith(".") and is_image(e.name)
    except OSError:
        return tr("grimoire.spells.viewl.images", "Open a picture or a folder to start")
    from grimoire.i18n import ltr

    return tr("grimoire.spells.viewl.images", "%n picture(s) in {folder}", n=n).format(folder=ltr(tilde(folder)))
