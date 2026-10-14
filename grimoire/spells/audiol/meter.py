# SPDX-License-Identifier: GPL-3.0-or-later
"""Level meters: a `pw-record` child reading one device at 8 kHz mono (an output through its monitor, so nothing
you hear changes), peaks worked out here, drawn as a thin white bar. Runs only while its panel is on screen;
reading a microphone is its own opt-in button, since Plasma shows the mic as in use while it runs.
"""
import array
import math

from PySide6.QtCore import QObject, QProcess, QRectF, QSize, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from grimoire.spells.audiol import pw

RATE = 8000
FLOOR = -60.0                     # dB shown as an empty bar


def peak_db(data: bytes) -> float:
    """The loudest s16 sample in data, in dBFS (FLOOR for silence)."""
    a = array.array("h")
    a.frombytes(data[:len(data) // 2 * 2])
    if not a:
        return FLOOR
    peak = max(max(a), -min(a)) / 32768
    return max(FLOOR, 20 * math.log10(peak)) if peak > 0 else FLOOR


def command(target: str, output: bool) -> list[str]:
    props = "{ node.name = %s-meter node.dont-reconnect = true %s}" % (
        pw.OWN_PREFIX, "stream.capture.sink = true " if output else "")
    return ["pw-record", "--target", target, "-P", props, "--rate", str(RATE), "--channels", "1",
            "--format", "s16", "--latency", "40ms", "--raw", "-"]


class LevelReader(QObject):
    """level(dB) about 20 times a second while running."""
    level = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc: QProcess | None = None
        self.target = ""
        self.buf = b""
        self._decay = FLOOR
        self.tick = QTimer(self, interval=50, timeout=self._emit)

    def start(self, target: str, output: bool):
        if self.proc and self.target == target:
            return
        self.stop()
        self.target = target
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        args = command(target, output)
        self.proc.start(args[0], args[1:])
        self.tick.start()

    def stop(self):
        self.tick.stop()
        if self.proc:
            self.proc.readyReadStandardOutput.disconnect()
            self.proc.terminate()                       # SIGTERM: pw-record closes its stream and exits
            if not self.proc.waitForFinished(500):
                self.proc.kill()
            self.proc.deleteLater()
            self.proc = None
        self.target = ""
        self._decay = FLOOR
        self.level.emit(FLOOR)

    def running(self) -> bool:
        return self.proc is not None

    def _read(self):
        if self.proc:
            self.buf += bytes(self.proc.readAllStandardOutput())

    def _emit(self):
        db = peak_db(self.buf)
        self.buf = b""
        self._decay = max(db, self._decay - 3.0)       # falls back smoothly instead of flickering
        self.level.emit(self._decay)


class LevelBar(QWidget):
    """A thin horizontal bar: dark track, white fill up to the level."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = FLOOR
        self.setFixedHeight(4)

    def sizeHint(self):
        return QSize(120, 4)

    def set_level(self, db: float):
        if abs(db - self.db) > 0.2:
            self.db = db
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(0, 0, 0, 0))
        p.setBrush(QColor("#1f1f1f"))
        r = QRectF(0, 0, self.width(), self.height())
        p.drawRoundedRect(r, 2, 2)
        frac = max(0.0, min(1.0, (self.db - FLOOR) / -FLOOR))
        if frac > 0:
            p.setBrush(QColor("#f2f2f2"))
            p.drawRoundedRect(QRectF(0, 0, self.width() * frac, self.height()), 2, 2)
