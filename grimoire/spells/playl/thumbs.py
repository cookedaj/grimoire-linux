# SPDX-License-Identifier: GPL-3.0-or-later
"""Seek-bar previews: one small frame at the time under the pointer, grabbed by ffmpeg on a worker thread.

Only for local video files and only when ffmpeg is installed (the time is shown either way). Requests are coalesced:
while one grab runs, only the newest request waits; results are kept per file in a small memory cache, keyed by a
time step of about 1/200 of the length so hovering back and forth doesn't run ffmpeg again.
"""
import shutil
import subprocess
from collections import OrderedDict

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from grimoire.jobs import POOL, Job

WIDTH = 192
CACHE_SIZE = 120


class Thumbnailer(QObject):
    ready = Signal(str, float, object)          # entry, time, QImage
    _done = Signal(object)

    def __init__(self):
        super().__init__()
        self.ffmpeg = shutil.which("ffmpeg")
        self.cache: OrderedDict = OrderedDict()
        self.busy = False
        self.waiting = None
        self._done.connect(self._finished)

    def available(self) -> bool:
        return bool(self.ffmpeg)

    @staticmethod
    def step(length: float) -> float:
        return max(1.0, (length or 0) / 200)

    def request(self, entry: str, t: float, length: float):
        """Ask for the frame near t; ready fires with it (maybe later, maybe from the cache right away)."""
        if not self.ffmpeg or not entry:
            return
        step = self.step(length)
        key = (entry, int(t / step))
        if key in self.cache:
            self.cache.move_to_end(key)
            self.ready.emit(entry, t, self.cache[key])
            return
        if self.busy:
            self.waiting = (entry, t, length)
            return
        self.busy = True
        at = key[1] * step + step / 2
        POOL.start(Job(lambda: (key, t, self._grab(entry, at)), self._done.emit))

    def _grab(self, entry: str, at: float):
        try:
            out = subprocess.run([self.ffmpeg, "-nostdin", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", entry,
                                  "-frames:v", "1", "-an", "-sn", "-vf", f"scale={WIDTH}:-2", "-f", "image2pipe",
                                  "-c:v", "bmp", "-"], capture_output=True, timeout=6)
        except (OSError, subprocess.TimeoutExpired):
            return None
        img = QImage.fromData(out.stdout, "BMP") if out.returncode == 0 and out.stdout else QImage()
        return None if img.isNull() else img

    def _finished(self, result):
        self.busy = False
        key, t, img = result
        if img is not None:
            self.cache[key] = img
            while len(self.cache) > CACHE_SIZE:
                self.cache.popitem(last=False)
            self.ready.emit(key[0], t, img)
        if self.waiting:
            w, self.waiting = self.waiting, None
            self.request(*w)

    def clear(self):
        self.cache.clear()
        self.waiting = None
