# SPDX-License-Identifier: GPL-3.0-or-later
"""Thumbnails, made on worker threads and kept on disk in the freedesktop thumbnail cache
(~/.cache/thumbnails/large/<md5 of the file URI>.png, checked by Thumb::MTime): the same cache Dolphin, Gwenview and
VaultL's KDE neighbours use, so a folder they've already shown opens instantly here, and the other way round.

The newest request is served first (a stack, not a queue): scrolling quickly through thousands of pictures makes the
ones on screen now, not the ones scrolled past a second ago.
"""

import hashlib
import os
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QImage, QImageReader

SIZE = 256  # "large" in the spec


def base() -> Path:
    """Read late, so a sandbox XDG_CACHE_HOME in tests is honoured."""
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "thumbnails"


def cache_file(path: Path, kind: str = "large") -> Path:
    uri = QUrl.fromLocalFile(str(path)).toEncoded().data()
    return base() / kind / (hashlib.md5(uri).hexdigest() + ".png")


def _cached(path: Path, mtime: float) -> QImage:
    for kind in ("large", "x-large"):
        f = cache_file(path, kind)
        if f.is_file():
            img = QImage(str(f))
            if not img.isNull() and img.text("Thumb::MTime") == str(int(mtime)):
                return img
    return QImage()


def make(path: Path, mtime: float, size: int, write: bool = True) -> QImage:
    """The cached thumbnail when it's fresh, else a new one (decoded at reduced size where the format allows it,
    shown the way EXIF says to) written to the cache. A null QImage when the file can't be read."""
    if path.is_relative_to(base()):
        write = False  # never thumbnail the thumbnails
    else:
        img = _cached(path, mtime)
        if not img.isNull():
            return img
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    full = reader.size()
    if full.isValid() and (full.width() > SIZE or full.height() > SIZE):
        reader.setScaledSize(full.scaled(QSize(SIZE, SIZE), Qt.AspectRatioMode.KeepAspectRatio))
    img = reader.read()
    if img.isNull():
        return img
    if img.width() > SIZE or img.height() > SIZE:  # plugins that ignore setScaledSize
        img = img.scaled(SIZE, SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    if write:
        _write(path, mtime, size, img, full)
    return img


def _write(path: Path, mtime: float, size: int, img: QImage, full: QSize):
    out = cache_file(path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        thumb = QImage(img)
        thumb.setText("Thumb::URI", QUrl.fromLocalFile(str(path)).toEncoded().data().decode())
        thumb.setText("Thumb::MTime", str(int(mtime)))
        thumb.setText("Thumb::Size", str(size))
        if full.isValid():
            thumb.setText("Thumb::Image::Width", str(full.width()))
            thumb.setText("Thumb::Image::Height", str(full.height()))
        thumb.setText("Software", "Grimoire Linux ViewL")
        tmp = out.with_name(f".{out.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        if thumb.save(str(tmp), "PNG"):
            os.chmod(tmp, 0o600)
            os.replace(tmp, out)  # readers never see half a file
        else:
            tmp.unlink(missing_ok=True)
    except OSError:
        pass


class Loader(QObject):
    """ready(path, image) for each request(); image is null when the file couldn't be read."""

    ready = Signal(str, QImage)
    WORKERS = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._stack: list[tuple[str, float, int]] = []
        self._queued: set[str] = set()
        self._running = 0
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(self.WORKERS)

    def request(self, path: str, mtime: float, size: int):
        with self._lock:
            if path in self._queued and self._stack and self._stack[-1][0] == path:
                return
            self._queued.add(path)
            self._stack.append((path, mtime, size))  # an older copy further down is skipped later
            if self._running < self.WORKERS:
                self._running += 1
                self.pool.start(_Worker(self))

    def clear(self):
        """Forget what hasn't started (a new folder was opened)."""
        with self._lock:
            self._stack.clear()
            self._queued.clear()

    def _next(self):
        with self._lock:
            while self._stack:
                job = self._stack.pop()
                if job[0] in self._queued:
                    self._queued.discard(job[0])
                    return job
            self._running -= 1
            return None


class _Worker(QRunnable):
    def __init__(self, loader: Loader):
        super().__init__()
        self.loader = loader

    def run(self):
        while True:
            try:
                job = self.loader._next()
            except RuntimeError:  # the loader was deleted with its page
                return
            if job is None:
                return
            path, mtime, size = job
            try:
                img = make(Path(path), mtime, size)
            except Exception:  # a broken plugin must not stop the other thumbnails
                img = QImage()
            try:
                self.loader.ready.emit(path, img)
            except RuntimeError:
                return
