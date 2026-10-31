# SPDX-License-Identifier: GPL-3.0-or-later
"""The seek bar: a thin line that thickens under the pointer, the time under the pointer in a bubble above it
(with a preview frame for local videos when ffmpeg is there), click or drag to seek.

Time runs left to right in every language, like the other meters and graphs in Grimoire."""
from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from grimoire.spells.playl.media import clock

HEIGHT = 22
LINE, LINE_HOVER = 3, 5


class SeekBar(QWidget):
    seek = Signal(float)              # released (or clicked): exact seek
    scrub = Signal(float)             # dragging: quick seeks while the button is down
    hovered = Signal(float)           # time under the pointer (for previews)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setMouseTracking(True)
        self.setFixedHeight(HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.length = 0.0
        self.pos_ = 0.0
        self.hover: float | None = None
        self.dragging = False
        self.preview: "Bubble | None" = None

    def sizeHint(self):
        return QSize(300, HEIGHT)

    def set_length(self, length: float):
        self.length = max(0.0, length or 0.0)
        self.setEnabled(self.length > 0)
        self.update()

    def set_position(self, pos: float):
        if not self.dragging:
            self.pos_ = max(0.0, pos or 0.0)
            self.update()

    def _time_at(self, x: float) -> float:
        w = max(1, self.width() - 12)
        return max(0.0, min(1.0, (x - 6) / w)) * self.length

    def mouseMoveEvent(self, e):
        if not self.length:
            return
        t = self._time_at(e.position().x())
        self.hover = t
        if self.dragging:
            self.pos_ = t
            self.scrub.emit(t)
        self.hovered.emit(t)
        if self.preview:
            self.preview.show_at(self, e.position().x(), t)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.length:
            self.dragging = True
            self.pos_ = self._time_at(e.position().x())
            self.scrub.emit(self.pos_)
            self.update()

    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.dragging = False
            self.pos_ = self._time_at(e.position().x())
            self.seek.emit(self.pos_)
            self.update()

    def leaveEvent(self, e):
        self.hover = None
        if self.preview:
            self.preview.hide()
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        thick = LINE_HOVER if (self.hover is not None or self.dragging) else LINE
        y = self.height() / 2
        left, w = 6.0, max(1.0, self.width() - 12.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 60))
        p.drawRoundedRect(QRectF(left, y - thick / 2, w, thick), thick / 2, thick / 2)
        if not self.length:
            return
        frac = max(0.0, min(1.0, self.pos_ / self.length))
        if self.hover is not None:
            p.setBrush(QColor(255, 255, 255, 70))
            hx = w * max(0.0, min(1.0, self.hover / self.length))
            if hx > w * frac:
                p.drawRoundedRect(QRectF(left + w * frac, y - thick / 2, hx - w * frac, thick), thick / 2, thick / 2)
        p.setBrush(QColor("#f2f2f2"))
        p.drawRoundedRect(QRectF(left, y - thick / 2, w * frac, thick), thick / 2, thick / 2)
        if self.hover is not None or self.dragging:
            p.drawEllipse(QRectF(left + w * frac - 6, y - 6, 12, 12))


class Bubble(QWidget):
    """The time (and preview frame) above the seek bar; a child of the stage so it can float over the video."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.text = ""
        self.image: QImage | None = None
        self.hide()

    def set_image(self, img: QImage | None):
        self.image = img
        self._fit()
        self.update()

    def _fit(self):
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(self.text) + 18
        if self.image is not None and not self.image.isNull():
            self.resize(max(tw, self.image.width() + 8), self.image.height() + fm.height() + 16)
        else:
            self.resize(tw, fm.height() + 10)

    def show_at(self, bar: QWidget, x: float, t: float):
        self.text = clock(t)
        self._fit()
        parent = self.parentWidget()
        at = bar.mapTo(parent, QPoint(int(x), 0))
        left = max(4, min(parent.width() - self.width() - 4, at.x() - self.width() // 2))
        self.move(left, at.y() - self.height() - 6)
        self.raise_()
        self.show()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 6, 6)
        p.fillPath(path, QColor(10, 10, 10, 235))
        p.setPen(QColor("#3a3a3a"))
        p.drawPath(path)
        fm = self.fontMetrics()
        top = 4
        if self.image is not None and not self.image.isNull():
            p.drawImage(QPoint((self.width() - self.image.width()) // 2, 4), self.image)
            top = self.image.height() + 8
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(0, top, self.width(), fm.height() + 4), Qt.AlignmentFlag.AlignCenter, self.text)
