# SPDX-License-Identifier: GPL-3.0-or-later
"""Video frames: mpv renders on its own thread into an offscreen OpenGL framebuffer, we read each frame back into a
QImage and a plain QWidget paints it.

Why not draw straight to the screen: PySide6's QOpenGLWidget isn't packaged here, and both a QOpenGLWindow and Qt 6's
QVideoWidget are native child windows, which on Wayland no widget can be drawn over (so no controls on the video).
One GPU→CPU copy per frame at the view's size costs a millisecond or two; decoding stays on the GPU (nvdec).
Without a usable OpenGL context (some VMs, the offscreen platform without EGL) mpv's software renderer takes over.
"""
import ctypes
import threading

from PySide6.QtCore import QObject, QRectF, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QImage, QOffscreenSurface, QOpenGLContext, QPainter
from PySide6.QtWidgets import QWidget

from grimoire.spells.playl import mpv

GL_FRAMEBUFFER, GL_RGBA, GL_UNSIGNED_BYTE, GL_NO_ERROR = 0x8D40, 0x1908, 0x1401, 0
_READ = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint,
                         ctypes.c_void_p)
_BIND = ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.c_uint)
_ERR = ctypes.CFUNCTYPE(ctypes.c_uint)


class Renderer(QObject):
    """Owns mpv's render context on a dedicated thread. frame_ready fires (at most one pending) when take() has a
    new frame; mpv's update callback and size changes are queued onto the thread."""
    frame_ready = Signal()
    _kick = Signal()
    _setup = Signal()
    _resize = Signal(int, int)

    def __init__(self, core: mpv.MPV):
        super().__init__()
        self.core = core
        self.ctx = ctypes.c_void_p()
        self.size = (0, 0)
        self.mode = ""                     # "gl" or "sw" once set up
        self._lock = threading.Lock()
        self._latest: QImage | None = None
        self._pending = False
        self._alive = True
        self._fbo = None
        self.thread = QThread()
        self.thread.setObjectName("playl-render")
        # surfaces belong to the GUI thread; the context moves to the render thread before it's used
        self.surface = QOffscreenSurface()
        self.surface.create()
        self.gl = QOpenGLContext()
        if not (self.surface.isValid() and self.gl.create()):
            self.gl = None
        else:
            self.gl.moveToThread(self.thread)
        self.moveToThread(self.thread)
        self._kick.connect(self._render, Qt.ConnectionType.QueuedConnection)
        self._setup.connect(self._create, Qt.ConnectionType.QueuedConnection)
        self._resize.connect(self._resized, Qt.ConnectionType.QueuedConnection)
        self._ready = threading.Event()
        self.thread.start()
        self._setup.emit()
        self._ready.wait(5)               # mpv's video output needs the context before the first file opens

    # ------------------------------------------------------------ UI side
    def resize(self, w: int, h: int):
        self._resize.emit(max(2, w), max(2, h))

    def take(self) -> QImage | None:
        with self._lock:
            self._pending = False
            return self._latest

    def stop(self) -> bool:
        """Free the render context (before the core is destroyed) and end the thread. False when the render thread
        didn't answer in time: the context may still be alive, so the core must not be destroyed under it."""
        if not self._alive:
            return not self.ctx
        self._alive = False
        done = threading.Event()
        self._teardown_done = done
        self._kick.emit()                  # wakes _render, which tears down because _alive is False
        freed = done.wait(3)
        self.thread.quit()
        self.thread.wait(3000)
        return freed

    # ------------------------------------------------------------ render thread
    def _create(self):
        try:
            self._make_context()
        finally:
            self._ready.set()

    def _make_context(self):
        try:                               # the GL path draws into a QOpenGLFramebufferObject (python3-pyside6.qtopengl)
            import PySide6.QtOpenGL  # noqa: F401
            has_fbo = True
        except ImportError:
            has_fbo = False
        if has_fbo and self.gl is not None and self.gl.makeCurrent(self.surface):
            gl = self.gl

            def proc(_ctx, name):
                return gl.getProcAddress(name) or 0
            self._proc = mpv.GET_PROC(proc)
            self._init = mpv.GLInit(self._proc, None, None)
            api = ctypes.c_char_p(b"opengl")
            if self.core.L.mpv_render_context_create(ctypes.byref(self.ctx), self.core.h,
                                                     mpv.params((mpv.R_API_TYPE, api), (mpv.R_GL_INIT, self._init))) >= 0:
                self.mode = "gl"
                self._read = _READ(gl.getProcAddress(b"glReadPixels"))
                self._bind = _BIND(gl.getProcAddress(b"glBindFramebuffer"))
                self._err = _ERR(gl.getProcAddress(b"glGetError"))
        if not self.mode:
            api = ctypes.c_char_p(b"sw")
            if self.core.L.mpv_render_context_create(ctypes.byref(self.ctx), self.core.h,
                                                     mpv.params((mpv.R_API_TYPE, api))) < 0:
                return                     # no video at all: audio still plays
            self.mode = "sw"
        self._update_cb = mpv.CALLBACK(lambda _d: self._kick.emit())
        self.core.L.mpv_render_context_set_update_callback(self.ctx, self._update_cb, None)

    def _resized(self, w: int, h: int):
        if (w, h) != self.size:
            self.size = (w, h)
            self._fbo = None
            self._render(force=True)

    def _render(self, force=False):
        if not self._alive:
            self._teardown()
            return
        if not self.ctx or not self.mode:
            return
        flags = self.core.L.mpv_render_context_update(self.ctx)
        if not (flags & mpv.RENDER_FRAME or force) or self.size[0] < 2:
            return
        img = self._draw_gl() if self.mode == "gl" else self._draw_sw()
        if img is None:
            return
        with self._lock:
            self._latest = img
            wake = not self._pending
            self._pending = True
        if wake:
            self.frame_ready.emit()

    def _draw_gl(self) -> QImage | None:
        from PySide6.QtOpenGL import QOpenGLFramebufferObject
        w, h = self.size
        self.gl.makeCurrent(self.surface)
        if self._fbo is None:
            self._fbo = QOpenGLFramebufferObject(w, h)
        fbo = mpv.GLFbo(self._fbo.handle(), w, h, 0)
        flip = ctypes.c_int(0)                       # glReadPixels starts at the bottom row, so no flip
        self.core.L.mpv_render_context_render(self.ctx, mpv.params((mpv.R_GL_FBO, fbo), (mpv.R_FLIP_Y, flip)))
        img = QImage(w, h, QImage.Format.Format_RGBX8888)
        buf = (ctypes.c_char * img.sizeInBytes()).from_buffer(img.bits())
        self._bind(GL_FRAMEBUFFER, self._fbo.handle())
        self._read(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, ctypes.addressof(buf))
        del buf
        if self._err() != GL_NO_ERROR:
            img = self._fbo.toImage(False)           # GL's bottom-up flip, which mpv's rows don't need
            img = img.flipped(Qt.Orientation.Vertical) if hasattr(img, "flipped") else img.mirrored(False, True)
        img.convertTo(QImage.Format.Format_RGB32)    # the UI paints it without converting
        return img

    def _draw_sw(self) -> QImage | None:
        w, h = self.size
        img = QImage(w, h, QImage.Format.Format_RGB32)
        buf = (ctypes.c_char * img.sizeInBytes()).from_buffer(img.bits())
        size = (ctypes.c_int * 2)(w, h)
        fmt = ctypes.c_char_p(b"bgr0")               # QImage RGB32 in memory on little-endian
        stride = ctypes.c_size_t(img.bytesPerLine())
        ptr = ctypes.c_void_p(ctypes.addressof(buf))
        rc = self.core.L.mpv_render_context_render(self.ctx, mpv.params(
            (mpv.R_SW_SIZE, size), (mpv.R_SW_FORMAT, fmt), (mpv.R_SW_STRIDE, stride), (mpv.R_SW_POINTER, ptr)))
        del buf
        return img if rc >= 0 else None

    def _teardown(self):
        if self.ctx:
            if self.mode == "gl":
                self.gl.makeCurrent(self.surface)
            self.core.L.mpv_render_context_free(self.ctx)
            self.ctx = ctypes.c_void_p()
            self._fbo = None
            if self.mode == "gl":
                self.gl.doneCurrent()
        done = getattr(self, "_teardown_done", None)
        if done:
            done.set()


class VideoView(QWidget):
    """Paints the latest frame on black. mpv already letterboxes into the frame, so it just fills the widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer: Renderer | None = None
        self.image: QImage | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setMinimumSize(QSize(160, 90))

    def attach(self, renderer: Renderer | None):
        self.renderer = renderer
        self.image = None
        if renderer:
            renderer.frame_ready.connect(self._new_frame)
            self._sized()
        self.update()

    def clear(self):
        self.image = None
        self.update()

    def _new_frame(self):
        if self.renderer:
            img = self.renderer.take()
            if img is not None:
                self.image = img
                self.update()

    def _sized(self):
        if self.renderer:
            r = self.devicePixelRatioF()
            self.renderer.resize(round(self.width() * r), round(self.height() * r))

    def resizeEvent(self, e):
        self._sized()
        super().resizeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#000000"))
        img = self.image
        if img is None or img.isNull():
            return
        # until the next frame arrives at the new size, show the old one scaled to fit
        r = self.devicePixelRatioF()
        iw, ih = img.width() / r, img.height() / r
        s = min(self.width() / iw, self.height() / ih)
        w, h = iw * s, ih * s
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, abs(s - 1) > 0.01)
        p.drawImage(QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h), img)
