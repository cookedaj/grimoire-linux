# SPDX-License-Identifier: GPL-3.0-or-later
"""Cover art for the chrome: found by library.art_bytes, turned grayscale (Grimoire is black & white; the video
itself stays in color) and cached as a 512 px PNG in CACHE/playl/art. QImage only, so it runs on worker threads."""
import hashlib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from grimoire import paths
from grimoire.spells.playl import library

ART_DIR = paths.CACHE / "playl" / "art"
SIZE = 512


def _name(key: str) -> Path:
    return ART_DIR / (hashlib.sha1(key.encode("utf-8", "surrogateescape")).hexdigest() + ".png")


def cover(path: str, key: str = "") -> Path | None:
    """A grayscale cover for the audio file at path (key: its album, so one album shares one file), or None.
    Call on a worker thread: it may read the file's tags and decode an image."""
    out = _name(key or path)
    missing = out.with_suffix(".none")
    if out.exists():
        return out
    if missing.exists():
        return None
    ART_DIR.mkdir(parents=True, exist_ok=True)
    data = library.art_bytes(path)
    img = QImage.fromData(data) if data else QImage()
    if img.isNull():
        missing.touch()
        return None
    if max(img.width(), img.height()) > SIZE:
        img = img.scaled(SIZE, SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    img = img.convertToFormat(QImage.Format.Format_Grayscale8)
    tmp = out.with_suffix(".tmp")
    if not img.save(str(tmp), "PNG"):
        return None
    tmp.replace(out)
    return out


def forget():
    """Drop the "no cover" marks (after a rescan, new covers may have appeared)."""
    try:
        for p in ART_DIR.glob("*.none"):
            p.unlink()                     # our own cache markers, not user files
    except OSError:
        pass
