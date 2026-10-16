# SPDX-License-Identifier: GPL-3.0-or-later
"""Library covers: a PDF's first page, an EPUB's cover image, or the title set in type, always in grays. Made on a
worker (QImage and QPainter on images are thread-safe) and kept in CACHE/readl/covers by file, size and date, so a
changed file gets a new cover."""
import hashlib
import os
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter

from grimoire import i18n
from grimoire.spells.readl import library

SIZE = QSize(240, 340)
KIND_LABEL = {"pdf": "PDF", "epub": "EPUB", "markdown": "MD", "text": "TXT"}      # file types: not translated


def cache_path(path: str) -> Path | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    h = hashlib.sha1(f"{path}\n{st.st_size}\n{st.st_mtime_ns}".encode()).hexdigest()
    return library.covers_dir() / f"{h}.png"


def _source_image(path: str, kind: str) -> QImage:
    try:
        if kind == "pdf":
            from grimoire.spells.readl import pdfdoc
            if not pdfdoc.available():
                return QImage()
            d = pdfdoc.Doc(path)
            d.load()
            try:
                w, h = d.sizes[0]
                return d.render(0, SIZE.height() * 2 / h if h else 1.0)
            finally:
                d.close()
        if kind == "epub":
            from grimoire.spells.readl.books import EpubSource
            src = EpubSource(path)
            try:
                return src.cover()
            finally:
                src.close()
    except Exception:              # a damaged file just gets a typeset cover
        return QImage()
    return QImage()


def make(path: str, kind: str, title: str) -> QImage:
    """The cover (from the cache when it's there)."""
    cached = cache_path(path)
    if cached and cached.is_file():
        img = QImage(str(cached))
        if not img.isNull():
            return img
    img = QImage(SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor("#141414"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    src = _source_image(path, kind) if os.path.isfile(path) else QImage()
    if not src.isNull():
        gray = src.convertToFormat(QImage.Format.Format_Grayscale8)
        scaled = gray.scaled(SIZE, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                             Qt.TransformationMode.SmoothTransformation)
        p.drawImage((SIZE.width() - scaled.width()) // 2, 0, scaled)
    else:
        p.setPen(QColor("#2a2a2a"))
        p.drawRect(QRectF(0.5, 0.5, SIZE.width() - 1, SIZE.height() - 1))
        f = QFont("IBM Plex Sans")
        f.setPixelSize(24)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor("#d6d6d6"))
        p.drawText(QRectF(22, 28, SIZE.width() - 44, SIZE.height() - 100),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, title)
        label = KIND_LABEL.get(kind, "")
        f.setPixelSize(12)
        f.setWeight(QFont.Weight.Medium)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, i18n.spacing(label, 2))
        p.setFont(f)
        p.setPen(QColor("#6f6f6f"))
        p.drawText(QRectF(22, SIZE.height() - 46, SIZE.width() - 44, 24), Qt.AlignmentFlag.AlignLeft, label)
        p.drawLine(22, SIZE.height() - 54, 60, SIZE.height() - 54)
    p.end()
    if cached and not src.isNull():          # typeset covers are cheap; only pictures are worth keeping
        cached.parent.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(f".{os.getpid()}.tmp.png")
        if img.save(str(tmp), "PNG"):
            tmp.replace(cached)
    return img
