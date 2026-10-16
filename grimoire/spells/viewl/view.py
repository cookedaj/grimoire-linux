# SPDX-License-Identifier: GPL-3.0-or-later
"""The full view: pictures decoded on worker threads (a small cache holds the neighbours, so next/previous is
instant), and the canvas that shows one with fit/100%/zoom at the pointer (wheel, touchpad pinch, touchscreen pinch),
panning, turns and flips (drawn, not applied to the file until the page saves), and animated GIF/WebP/APNG via QMovie.

Zoom is in device pixels: 100% puts one picture pixel on one screen pixel, also on a HiDPI screen.
"""

from collections import OrderedDict
from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QImageIOHandler, QImageReader, QMovie, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import QWidget

from grimoire.spells.viewl import exif

QImageReader.setAllocationLimit(2048)  # MB; Qt's default 256 refuses big panoramas
MAX_SIDE = 20000  # anything bigger is decoded scaled down to this
CACHE_BYTES = 900 * 2**20  # decoded pictures kept for next/previous
MIN_ZOOM, MAX_ZOOM = 0.02, 32.0


@dataclass
class Decoded:
    image: QImage = field(default_factory=QImage)
    preview: QImage = field(default_factory=QImage)  # a screen-sized copy for fit/zoomed-out views
    size: QSize = field(default_factory=QSize)  # the picture's own size (shown, after EXIF orientation)
    fmt: str = ""
    animated: bool = False
    frames: int = 1
    error: str = ""
    reduced: bool = False  # too big: decoded scaled down

    def nbytes(self) -> int:
        return self.image.sizeInBytes() + self.preview.sizeInBytes()


def decode(path: str, preview_side: int) -> Decoded:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    out = Decoded(fmt=bytes(reader.format()).decode().upper())
    size = reader.size()
    count = reader.imageCount()
    out.animated = reader.supportsAnimation() and count != 1
    out.frames = count
    if size.isValid() and max(size.width(), size.height()) > MAX_SIDE:
        reader.setScaledSize(size.scaled(QSize(MAX_SIDE, MAX_SIDE), Qt.AspectRatioMode.KeepAspectRatio))
        out.reduced = True
    img = reader.read()
    if img.isNull():
        out.error = reader.errorString()
        return out
    alpha = img.hasAlphaChannel()
    img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied if alpha else QImage.Format.Format_RGB32)
    out.image = img
    out.size = _shown(size, reader) if out.reduced else img.size()  # reduced: still say the real size
    if max(img.width(), img.height()) > preview_side * 1.25:
        out.preview = img.scaled(
            preview_side, preview_side, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    return out


def _shown(size: QSize, reader: QImageReader) -> QSize:
    """reader.size() is the stored size; EXIF turns of 90° swap it."""
    t = reader.transformation()
    if t & QImageIOHandler.Transformation.TransformationRotate90:  # 90, 270 and the transposes
        return QSize(size.height(), size.width())
    return size


class _DecodeJob(QRunnable):
    def __init__(self, decoder, path, key, side):
        super().__init__()
        self.decoder, self.path, self.key, self.side = decoder, path, key, side

    def run(self):
        try:
            result = decode(self.path, self.side)
        except Exception as e:  # a broken plugin: show it, keep going
            result = Decoded(error=str(e))
        try:
            self.decoder.decoded.emit(self.key, result)
        except RuntimeError:
            pass


class Decoder(QObject):
    """Decodes pictures on two worker threads; ready(key, Decoded) on the UI thread. key = (path, mtime)."""

    ready = Signal(object, object)
    decoded = Signal(object, object)  # from the workers

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cache: OrderedDict = OrderedDict()
        self.pending: set = set()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.side = 2560
        self.decoded.connect(self._done)

    def get(self, key) -> Decoded | None:
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def request(self, key, first: bool = False):
        if key in self.cache or key in self.pending:
            return
        self.pending.add(key)
        self.pool.start(_DecodeJob(self, str(key[0]), key, self.side), 1 if first else 0)

    def forget(self, path: str):
        for k in [k for k in self.cache if k[0] == path]:
            del self.cache[k]

    def _done(self, key, result: Decoded):
        self.pending.discard(key)
        self.cache[key] = result
        total = sum(d.nbytes() for d in self.cache.values())
        while total > CACHE_BYTES and len(self.cache) > 1:
            _, old = self.cache.popitem(last=False)
            total -= old.nbytes()
        self.ready.emit(key, result)


def _matrix(orient: int) -> QTransform:
    a, b, c, d = exif.ORIENT[orient]
    return QTransform(a, c, b, d, 0, 0)


class Canvas(QWidget):
    """Shows one picture. Signals: zoomed(zoom in device pixels, fit), activated() on double-click,
    step(+1/-1) for the mouse's back/forward buttons."""

    zoomed = Signal(float, bool)
    activated = Signal()
    step = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)  # a canvas: never mirrored
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.grabGesture(Qt.GestureType.PinchGesture)
        self.setMinimumSize(200, 150)
        self.full = QPixmap()  # the decoded picture
        self.small = QPixmap()  # its screen-sized copy (or a blurry thumbnail while it decodes)
        self.size_ = QSize()  # the picture's size, before the user's turns
        self.placeholder = False
        self.movie: QMovie | None = None
        self.orient = 1  # the user's turns and flips, as an EXIF orientation value
        self.fit = True
        self.zoom = 1.0  # device pixels per picture pixel
        self.offset = QPointF()  # the picture's centre, from the canvas centre (logical px)
        self.message = ("", "")
        self.hint = ""
        self.black = False  # full screen: pure black around the picture
        self._drag: QPointF | None = None
        self._sharp: tuple | None = None  # (key, QPixmap) exactly scaled for the current zoom
        self._settle = QTimer(self, singleShot=True, interval=160, timeout=self._make_sharp)
        self._hint_timer = QTimer(self, singleShot=True, interval=2200, timeout=self._clear_hint)

    # ---------------------------------------------------------------- content
    def clear(self, title: str = "", detail: str = ""):
        self._stop_movie()
        self.full, self.small, self.size_ = QPixmap(), QPixmap(), QSize()
        self.placeholder = False
        self.message = (title, detail)
        self._sharp = None
        self.update()

    def show_placeholder(self, thumb: QImage, size: QSize):
        """A thumbnail scaled up while the real picture decodes, so the switch feels instant."""
        self._stop_movie()
        self.full = QPixmap()
        self.small = QPixmap.fromImage(thumb)
        self.size_ = size if size.isValid() else thumb.size()
        self.placeholder = True
        self.message = ("", "")
        self._sharp = None
        self.update()

    def show_decoded(self, d: Decoded, keep_view: bool = False):
        self._stop_movie()
        self.full = QPixmap.fromImage(d.image)
        self.small = QPixmap.fromImage(d.preview) if not d.preview.isNull() else QPixmap()
        self.size_ = d.image.size()
        self.placeholder = False
        self.message = ("", "")
        self._sharp = None
        if not keep_view:
            self.fit = True
            self.offset = QPointF()
        self._changed()

    def play(self, path: str) -> bool:
        """Animated pictures run through QMovie (frames decoded as they're shown)."""
        self._stop_movie()
        movie = QMovie(path, parent=self)
        if not movie.isValid():
            movie.deleteLater()
            return False
        movie.setCacheMode(QMovie.CacheMode.CacheNone)
        self.movie = movie
        movie.frameChanged.connect(self._frame)
        movie.start()
        return True

    def paused(self) -> bool:
        return bool(self.movie) and self.movie.state() == QMovie.MovieState.Paused

    def toggle_pause(self):
        if self.movie:
            self.movie.setPaused(self.movie.state() == QMovie.MovieState.Running)

    def _frame(self, _n):
        if not self.movie:
            return
        pm = self.movie.currentPixmap()
        first = self.full.isNull() or self.placeholder or pm.size() != self.size_
        self.full = pm
        self.small = QPixmap()
        self.size_ = pm.size()
        self.placeholder = False
        self._sharp = None
        if first:
            self._changed()
        else:
            self.update()

    def _stop_movie(self):
        if self.movie:
            self.movie.stop()
            self.movie.frameChanged.disconnect(self._frame)
            self.movie.deleteLater()
            self.movie = None

    def set_orient(self, orient: int):
        self.orient = orient
        self._sharp = None
        self._changed()

    def flash(self, text: str):
        """A short note over the picture (the slideshow's "Esc stops")."""
        self.hint = text
        self._hint_timer.start()
        self.update()

    def _clear_hint(self):
        self.hint = ""
        self.update()

    # ---------------------------------------------------------------- geometry
    def has_picture(self) -> bool:
        return self.size_.isValid() and not (self.full.isNull() and self.small.isNull())

    def shown_size(self) -> QSize:
        """The picture's size after the user's turns."""
        if self.orient >= 5:
            return QSize(self.size_.height(), self.size_.width())
        return QSize(self.size_)

    def dpr(self) -> float:
        return self.devicePixelRatioF() or 1.0

    def fit_zoom(self) -> float:
        s = self.shown_size()
        if s.isEmpty():
            return 1.0
        d = self.dpr()
        z = min(self.width() * d / s.width(), self.height() * d / s.height())
        return min(z, 1.0)  # small pictures stay at 100% instead of being blown up

    def current_zoom(self) -> float:
        return self.fit_zoom() if self.fit else self.zoom

    def _scale(self) -> float:
        """Logical px per picture pixel."""
        return self.current_zoom() / self.dpr()

    def _clamp(self):
        s, k = self.shown_size(), self._scale()
        w, h = s.width() * k, s.height() * k
        mx, my = max(0.0, (w - self.width()) / 2), max(0.0, (h - self.height()) / 2)
        self.offset = QPointF(min(mx, max(-mx, self.offset.x())), min(my, max(-my, self.offset.y())))

    def _changed(self):
        self._clamp()
        self._sharp = None
        self._settle.start()
        self.update()
        self.zoomed.emit(self.current_zoom(), self.fit)

    def set_fit(self):
        self.fit = True
        self.offset = QPointF()
        self._changed()

    def set_zoom(self, z: float, at: QPointF | None = None):
        if not self.has_picture():
            return
        old = self._scale()
        z = min(MAX_ZOOM, max(min(MIN_ZOOM, self.fit_zoom()), z))
        self.fit = False
        self.zoom = z
        p = (at if at is not None else QPointF(self.width() / 2, self.height() / 2)) - QPointF(
            self.width() / 2, self.height() / 2
        )
        if old > 0:
            self.offset = p - (p - self.offset) * (self._scale() / old)
        self._changed()

    def zoom_by(self, factor: float, at: QPointF | None = None):
        self.set_zoom(self.current_zoom() * factor, at)

    def pan(self, dx: float, dy: float):
        self.offset += QPointF(dx, dy)
        self._clamp()
        self.update()

    # ---------------------------------------------------------------- painting
    def _source(self) -> tuple[QPixmap, float]:
        """(pixmap, picture pixels per pixmap pixel): the screen-sized copy when it's enough for this zoom."""
        need = self.current_zoom() * self.size_.width()
        if not self.small.isNull() and (self.full.isNull() or need <= self.small.width() * 1.02):
            return self.small, self.size_.width() / max(1, self.small.width())
        return self.full, self.size_.width() / max(1, self.full.width())

    def _make_sharp(self):
        """Once the zoom settles below 100%, scale the picture once with a proper filter (QPainter's bilinear
        sampling shimmers on big reductions)."""
        if not self.has_picture() or self.placeholder or self.movie or self.current_zoom() >= 1.0:
            return
        src, per = self._source()
        z = self.current_zoom()
        w, h = round(self.size_.width() * z), round(self.size_.height() * z)
        if w < 1 or h < 1 or w > 12000 or h > 12000:
            return
        key = (src.cacheKey(), w, h)
        if self._sharp and self._sharp[0] == key:
            return
        pm = src.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        pm.setDevicePixelRatio(self.dpr())
        self._sharp = (key, pm)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#000000" if self.black else "#0b0b0b"))
        if self.has_picture():
            p.save()
            p.translate(self.width() / 2 + self.offset.x(), self.height() / 2 + self.offset.y())
            p.setTransform(_matrix(self.orient), True)
            k = self._scale()
            w, h = self.size_.width() * k, self.size_.height() * k
            sharp = self._sharp[1] if self._sharp and not self.placeholder else None
            if sharp is not None and abs(sharp.width() / self.dpr() - w) < 1.5:
                p.drawPixmap(QPointF(-w / 2, -h / 2), sharp)
            else:
                src, _ = self._source()
                smooth = self.current_zoom() < 3 or self.placeholder
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)
                p.drawPixmap(QRectF(-w / 2, -h / 2, w, h), src, QRectF(src.rect()))
                if not self.placeholder and self.current_zoom() < 1.0:
                    self._settle.start()
            p.restore()
        title, detail = self.message
        if title:
            f = QFont(self.font())
            f.setPixelSize(17)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            p.setPen(QColor("#e8e8e8"))
            box = QRectF(40, 0, self.width() - 80, self.height() / 2 - 6)
            p.drawText(
                box, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom | Qt.TextFlag.TextWordWrap, title
            )
            f.setPixelSize(13)
            f.setWeight(QFont.Weight.Normal)
            p.setFont(f)
            p.setPen(QColor("#8c8c8c"))
            p.drawText(
                QRectF(40, self.height() / 2 + 6, self.width() - 80, self.height() / 2 - 20),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                detail,
            )
        if self.hint:
            f = QFont(self.font())
            f.setPixelSize(13)
            p.setFont(f)
            r = p.fontMetrics().boundingRect(self.hint).adjusted(-16, -9, 16, 9)
            r.moveCenter(self.rect().center())
            r.moveBottom(self.height() - 36)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QColor("#2e2e2e"))
            p.setBrush(QColor(0, 0, 0, 210))
            p.drawRoundedRect(QRectF(r), 8, 8)
            p.setPen(QColor("#e8e8e8"))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.hint)
        p.end()

    def resizeEvent(self, e):
        self._clamp()
        self._sharp = None
        self._settle.start()
        if self.fit:
            self.zoomed.emit(self.current_zoom(), True)
        super().resizeEvent(e)

    # ---------------------------------------------------------------- input
    def _bigger_than_view(self) -> bool:
        s, k = self.shown_size(), self._scale()
        return s.width() * k > self.width() + 0.5 or s.height() * k > self.height() + 0.5

    def wheelEvent(self, e):
        touchpad = e.phase() != Qt.ScrollPhase.NoScrollPhase or not e.pixelDelta().isNull()
        if touchpad and not e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            d = e.pixelDelta()
            self.pan(d.x(), d.y())  # two fingers move a zoomed-in picture around
            e.accept()
            return
        steps = e.angleDelta().y() / 120 or e.angleDelta().x() / 120
        if steps:
            self.zoom_by(1.2**steps, e.position())
        e.accept()

    def event(self, e):
        t = e.type()
        if t == QEvent.Type.NativeGesture:
            if e.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                self.zoom_by(1 + e.value(), e.position())
                return True
            if e.gestureType() == Qt.NativeGestureType.SmartZoomNativeGesture:
                self.set_fit() if not self.fit else self.set_zoom(1.0, e.position())
                return True
        elif t == QEvent.Type.Gesture:
            pinch = e.gesture(Qt.GestureType.PinchGesture)
            if pinch:
                at = self.mapFromGlobal(pinch.centerPoint().toPoint())
                f = pinch.scaleFactor()
                if f > 0:
                    self.zoom_by(f, QPointF(at))
                e.accept()
                return True
        return super().event(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._bigger_than_view():
            self._drag = e.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif e.button() == Qt.MouseButton.BackButton:
            self.step.emit(-1)
        elif e.button() == Qt.MouseButton.ForwardButton:
            self.step.emit(1)
        elif e.button() == Qt.MouseButton.MiddleButton:
            self.set_fit() if not self.fit else self.set_zoom(1.0, e.position())
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            d = e.position() - self._drag
            self._drag = e.position()
            self.pan(d.x(), d.y())
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor if self._bigger_than_view() else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._drag is not None:
            self._drag = None
            self.setCursor(Qt.CursorShape.OpenHandCursor if self._bigger_than_view() else Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
