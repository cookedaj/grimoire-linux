# SPDX-License-Identifier: GPL-3.0-or-later
"""The PDF page view: single page, continuous or two pages side by side; fit width, fit page or a zoom; day, night
(inverted) or paper (soft gray) pages; text selection, search hits and links.

Pages are drawn from a cache of rendered pixmaps. A missing one is asked of the Renderer (pdfdoc.RENDER, one worker
thread) and a lower-resolution copy, or a blank sheet, stands in until it arrives, so scrolling never waits. Requests
for pages that scrolled out of sight before their turn are dropped on the worker.
"""
from collections import OrderedDict

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QColor, QDesktopServices, QGuiApplication, QImage, QKeySequence, QPainter, QPen,
                           QPixmap)
from PySide6.QtWidgets import QAbstractScrollArea, QApplication

from grimoire.spells.readl import pdfdoc
from grimoire.widgets import plain_tip

GAP = 14                          # between pages, logical px
MARGIN = 18
BG = {"day": "#0b0b0b", "night": "#000000", "paper": "#0b0b0b"}
PAPER = {"day": "#ffffff", "night": "#141414", "paper": "#e2e2e2"}
CACHE_BYTES = 320 << 20


def tint(img: QImage, mode: str) -> QImage:
    """Night: inverted, whites softened to light gray. Paper: the white page multiplied to a soft gray. Safe on a
    worker thread (QImage + QPainter on an image)."""
    if mode == "day" or img.isNull():
        return img
    img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if mode == "night":
        img.invertPixels(QImage.InvertMode.InvertRgb)
    p = QPainter(img)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
    p.fillRect(img.rect(), QColor("#d6d6d6" if mode == "night" else "#e2e2e2"))
    p.end()
    return img


class Renderer(QObject):
    """Rendered pages for one document, shared by the page view and the thumbnails."""
    ready = Signal(object)          # key (page, pixel scale ×100, mode)

    def __init__(self, doc: pdfdoc.Doc):
        super().__init__()
        self.doc = doc
        self.cache: OrderedDict = OrderedDict()
        self.bytes = 0
        self.pending: set = set()
        self.view_wanted: set = set()    # keys still worth rendering (read on the worker): the page view's
        self.thumb_wanted: set = set()   # and the thumbnails'
        self.alive = True
        self._done.connect(self._arrived, Qt.ConnectionType.QueuedConnection)

    _done = Signal(object)

    @staticmethod
    def key(page: int, scale: float, mode: str):
        return (page, max(1, round(scale * 100)), mode)

    def get(self, key) -> QPixmap | None:
        pm = self.cache.get(key)
        if pm is not None:
            self.cache.move_to_end(key)
        return pm

    def nearest(self, page: int, mode: str) -> QPixmap | None:
        """The sharpest cached picture of the page in this mode, whatever its scale (a stand-in)."""
        best = None
        for (p, s, m), pm in self.cache.items():
            if p == page and m == mode and (best is None or s > best[0]):
                best = (s, pm)
        return best[1] if best else None

    def request(self, key, urgent=False, thumb=False):
        (self.thumb_wanted if thumb else self.view_wanted).add(key)
        if key in self.cache or key in self.pending:
            return
        self.pending.add(key)
        page, s, mode = key
        doc = self.doc

        def work():
            if not self.alive or (key not in self.view_wanted and key not in self.thumb_wanted):
                return key, None
            return key, tint(doc.render(page, s / 100), mode)
        from grimoire.jobs import Job
        pdfdoc.RENDER.start(Job(work, self._done.emit), 1 if urgent else 0)

    def _arrived(self, result):
        key, img = result
        self.pending.discard(key)
        if img is None or img.isNull() or not self.alive:
            return
        pm = QPixmap.fromImage(img)
        self.cache[key] = pm
        self.bytes += pm.width() * pm.height() * 4
        while self.bytes > CACHE_BYTES and len(self.cache) > 4:
            _, old = self.cache.popitem(last=False)
            self.bytes -= old.width() * old.height() * 4
        self.ready.emit(key)

    def close(self):
        self.alive = False
        self.view_wanted, self.thumb_wanted = set(), set()
        self.cache.clear()


class PageView(QAbstractScrollArea):
    pageChanged = Signal(int)
    zoomChanged = Signal()
    selectionChanged = Signal(str)

    def __init__(self, renderer: Renderer, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)     # pages read left to right in every language
        self.r = renderer
        self.doc = renderer.doc
        self.layout_mode = "continuous"
        self.fit = "width"
        self.zoom = 1.0                  # pixels per point when fit == "custom"
        self.mode = "day"
        self.scale = 1.0
        self.rects: list[QRectF | None] = []
        self.content = QSize(0, 0)
        self.page = 0
        self.hits: dict[int, list] = {}  # page -> [(start, length)]
        self.current_hit: tuple | None = None   # (page, index)
        self._hit_rects: dict = {}
        self.sel_rects: dict[int, list] = {}
        self.sel_text = ""
        self._press = None               # (page, point) where a drag began
        self._press_pos = None
        self._dragging = False
        self.setFrameShape(QAbstractScrollArea.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setMouseTracking(True)
        self.verticalScrollBar().valueChanged.connect(self._scrolled)
        self.horizontalScrollBar().valueChanged.connect(lambda _: self.viewport().update())
        self.r.ready.connect(self._ready)
        self._relayout_timer = QTimer(self, singleShot=True, interval=0, timeout=self.relayout)

    # ------------------------------------------------------------ layout
    def set_options(self, layout=None, fit=None, zoom=None, mode=None):
        anchor = self.position()
        if layout:
            self.layout_mode = layout
        if fit:
            self.fit = fit
        if zoom is not None:
            self.zoom = max(0.1, min(8.0, zoom))
        if mode:
            self.mode = mode
        self.relayout()
        self.go(anchor["page"], anchor["y"] * self.doc.sizes[anchor["page"]][1])
        self.zoomChanged.emit()

    def _rows(self) -> list[list[int]]:
        n = self.doc.page_count
        if self.layout_mode == "two":
            return [[i, i + 1] if i + 1 < n else [i] for i in range(0, n, 2)]
        if self.layout_mode == "single":
            return [[self.page]] if self.layout_mode == "single" and self.page < n else []
        return [[i] for i in range(n)]

    def _fit_scale(self) -> float:
        vw = max(50, self.viewport().width() - 2 * MARGIN)
        vh = max(50, self.viewport().height() - 2 * MARGIN)
        sizes = self.doc.sizes
        if self.layout_mode == "two":
            p = self.page - self.page % 2
            pair = sizes[p:p + 2]
            sw = (vw - GAP * (len(pair) - 1)) / sum(s[0] for s in pair)
            h = max(s[1] for s in pair)
        elif self.layout_mode == "single":
            w, h = sizes[self.page]
            sw = vw / w
        else:
            sw = vw / max(s[0] for s in sizes)
            h = sizes[self.page][1]
        return sw if self.fit == "width" else min(sw, vh / h)

    def relayout(self):
        if not self.doc.page_count:
            return
        self.scale = self._fit_scale() if self.fit in ("width", "page") else self.zoom
        self.scale = max(0.05, min(8.0, self.scale))
        s = self.scale
        self.rects = [None] * self.doc.page_count
        y = MARGIN
        width = 0
        rows = self._rows()
        for row in rows:
            w = sum(self.doc.sizes[i][0] * s for i in row) + GAP * (len(row) - 1)
            h = max(self.doc.sizes[i][1] * s for i in row)
            width = max(width, w)
            x = 0
            for i in row:
                pw, ph = self.doc.sizes[i][0] * s, self.doc.sizes[i][1] * s
                self.rects[i] = QRectF(x, y + (h - ph) / 2, pw, ph)
                x += pw + GAP
            y += h + GAP
        total_w = width + 2 * MARGIN
        vw = self.viewport().width()
        off = max(MARGIN, (max(vw, total_w) - width) / 2)
        for row in rows:                      # center each row
            rw = sum(self.doc.sizes[i][0] * s for i in row) + GAP * (len(row) - 1)
            dx = off + (width - rw) / 2
            for i in row:
                self.rects[i].translate(dx, 0)
        self.content = QSize(int(max(vw, total_w)), int(y - GAP + MARGIN))
        self._hit_rects.clear()
        vb, hb = self.verticalScrollBar(), self.horizontalScrollBar()
        vb.setRange(0, max(0, self.content.height() - self.viewport().height()))
        vb.setPageStep(self.viewport().height())
        vb.setSingleStep(48)
        hb.setRange(0, max(0, self.content.width() - vw))
        hb.setPageStep(vw)
        hb.setSingleStep(48)
        self.viewport().update()

    def resizeEvent(self, e):
        anchor = self.position() if self.rects else None
        super().resizeEvent(e)
        self.relayout()
        if anchor:
            self.go(anchor["page"], anchor["y"] * self.doc.sizes[anchor["page"]][1], emit=False)

    # ------------------------------------------------------------ position
    def _origin(self) -> QPointF:
        return QPointF(self.horizontalScrollBar().value(), self.verticalScrollBar().value())

    def visible_pages(self) -> list[int]:
        top = self.verticalScrollBar().value()
        bottom = top + self.viewport().height()
        return [i for i, r in enumerate(self.rects) if r is not None and r.bottom() >= top and r.top() <= bottom]

    def _top_page(self) -> int:
        top = self.verticalScrollBar().value() + min(60, self.viewport().height() / 4)
        best = None
        for i, r in enumerate(self.rects):
            if r is None:
                continue
            if r.top() > top + 0.5 and best is not None:
                break
            if best is None or r.top() > self.rects[best].top() + 0.5:   # the first page of a two-page row
                best = i
        return self.page if best is None else best

    def position(self) -> dict:
        """{"page": n, "y": fraction of that page above the top of the view}."""
        if not self.rects or self.rects[self.page] is None:
            return {"page": self.page, "y": 0.0}
        p = self._top_page() if self.layout_mode != "single" else self.page
        r = self.rects[p]
        y = (self.verticalScrollBar().value() - r.top()) / max(1.0, r.height())
        return {"page": p, "y": round(max(0.0, min(1.0, y)), 4)}

    def progress(self) -> float:
        n = self.doc.page_count
        pos = self.position()
        return min(1.0, (pos["page"] + pos["y"]) / max(1, n - 1)) if n > 1 else 1.0

    def go(self, page: int, y_points: float = 0.0, emit=True, center=False):
        page = max(0, min(self.doc.page_count - 1, page))
        if self.layout_mode == "single" and page != self.page or not self.rects or self.rects[page] is None:
            self.page = page
            self.relayout()
        self.page = page
        r = self.rects[page]
        y = r.top() + y_points * self.scale
        if center:
            y -= self.viewport().height() / 3
        elif y_points <= 0:
            y = r.top() - (MARGIN if page == 0 or self.layout_mode == "single" else GAP / 2)
        self.verticalScrollBar().setValue(int(y))
        self.viewport().update()
        if emit:
            self.pageChanged.emit(page)

    def _scrolled(self, _):
        if self.layout_mode != "single":
            p = self._top_page()
            if p != self.page:
                self.page = p
                self.pageChanged.emit(p)
        self.viewport().update()

    def step_page(self, d: int):
        if self.layout_mode == "two":
            base = self.page - self.page % 2
            self.go(base + 2 * d)
        else:
            self.go(self.page + d)

    # ------------------------------------------------------------ painting
    def _ready(self, key):
        if key[2] == self.mode and key[0] < len(self.rects) and self.rects[key[0]] is not None:
            self.viewport().update()

    def paintEvent(self, _):
        p = QPainter(self.viewport())
        p.fillRect(self.viewport().rect(), QColor(BG[self.mode]))
        if not self.rects:
            return
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        o = self._origin()
        dpr = self.devicePixelRatioF()
        rs = self.scale * dpr
        visible = self.visible_pages()
        wanted = set()
        for i in visible:
            r = self.rects[i].translated(-o)
            key = Renderer.key(i, rs, self.mode)
            wanted.add(key)
            pm = self.r.get(key)
            if pm is None:
                stand = self.r.nearest(i, self.mode)
                if stand is not None:
                    p.drawPixmap(r, stand, QRectF(stand.rect()))
                else:
                    p.fillRect(r, QColor(PAPER[self.mode]))
                self.r.request(key, urgent=True)
            else:
                p.drawPixmap(r, pm, QRectF(pm.rect()))
            p.setPen(QPen(QColor("#202020"), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(-0.5, -0.5, 0.5, 0.5))
            self._paint_marks(p, i, r)
        for i in self._neighbours(visible):           # the pages either side, ahead of time
            key = Renderer.key(i, rs, self.mode)
            wanted.add(key)
            self.r.request(key)
        self.r.view_wanted = wanted

    def _neighbours(self, visible):
        if not visible:
            return []
        n = self.doc.page_count
        if self.layout_mode == "single":
            return [i for i in (self.page - 1, self.page + 1) if 0 <= i < n]
        lo, hi = visible[0], visible[-1]
        return [i for i in (lo - 1, hi + 1, hi + 2) if 0 <= i < n]

    def _paint_marks(self, p: QPainter, page: int, r: QRectF):
        s = self.scale

        def box(rect: QRectF) -> QRectF:
            return QRectF(r.left() + rect.left() * s, r.top() + rect.top() * s, rect.width() * s,
                          rect.height() * s).adjusted(-1, -1, 1, 1)
        if page in self.hits:
            light = self.mode == "night"
            for idx, (start, length) in enumerate(self.hits[page]):
                k = (page, start, length)
                if k not in self._hit_rects:
                    self._hit_rects[k] = self.doc.span_rects(page, start, length)
                current = self.current_hit == (page, idx)
                for rect in self._hit_rects[k]:
                    b = box(rect)
                    if current:
                        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
                        p.fillRect(b, QColor("#ffffff"))
                        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                    else:
                        p.setPen(QPen(QColor("#ffffff" if light else "#000000"), 1.2))
                        p.setBrush(QColor(255, 255, 255, 40) if light else QColor(0, 0, 0, 30))
                        p.drawRect(b)
        for rect in self.sel_rects.get(page, []):
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
            p.fillRect(box(rect), QColor("#c8c8c8"))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    # ------------------------------------------------------------ search
    def set_hits(self, hits: dict, current=None):
        self.hits = hits
        self.current_hit = current
        self._hit_rects.clear()
        self.viewport().update()

    def show_hit(self, page: int, idx: int):
        self.current_hit = (page, idx)
        start, length = self.hits[page][idx]
        rects = self.doc.span_rects(page, start, length)
        self._hit_rects[(page, start, length)] = rects
        if self.layout_mode == "single" and page != self.page:
            self.page = page
            self.relayout()
        self.page = page
        r = self.rects[page]
        if rects:
            top = r.top() + rects[0].top() * self.scale
            vb = self.verticalScrollBar()
            if not (vb.value() + 40 <= top <= vb.value() + self.viewport().height() - 60):
                vb.setValue(int(top - self.viewport().height() / 3))
            left = r.left() + rects[0].left() * self.scale
            hb = self.horizontalScrollBar()
            if not (hb.value() <= left <= hb.value() + self.viewport().width() - 40):
                hb.setValue(int(left - self.viewport().width() / 3))
        else:
            self.go(page, emit=False)
        self.pageChanged.emit(page)
        self.viewport().update()

    # ------------------------------------------------------------ mouse
    def _hit_page(self, pos) -> tuple[int, QPointF] | None:
        c = QPointF(pos) + self._origin()
        for i, r in enumerate(self.rects):
            if r is not None and r.adjusted(-GAP / 2, -GAP / 2, GAP / 2, GAP / 2).contains(c):
                pt = (c - r.topLeft()) / self.scale
                w, h = self.doc.sizes[i]
                return i, QPointF(max(0, min(w, pt.x())), max(0, min(h, pt.y())))
        return None

    def _link_at(self, pos):
        hit = self._hit_page(pos)
        if not hit:
            return None
        page, pt = hit
        for rect, target, y, url in self.doc.links(page):
            if rect.contains(pt):
                return target, y, url
        return None

    def mousePressEvent(self, e):
        self.setFocus()
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = self._hit_page(e.position())
            self._press_pos = e.position()
            self._dragging = False
        elif e.button() == Qt.MouseButton.MiddleButton:
            self._press_pos = e.position()
            self._pan = (self.horizontalScrollBar().value(), self.verticalScrollBar().value())
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.MiddleButton and self._press_pos is not None:
            d = e.position() - self._press_pos
            self.horizontalScrollBar().setValue(int(self._pan[0] - d.x()))
            self.verticalScrollBar().setValue(int(self._pan[1] - d.y()))
            return
        if e.buttons() & Qt.MouseButton.LeftButton and self._press:
            if not self._dragging and (e.position() - self._press_pos).manhattanLength() < 4:
                return
            self._dragging = True
            self._autoscroll(e.position())
            end = self._hit_page(e.position())
            if end:
                self._select(self._press, end)
            return
        link = self._link_at(e.position())
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if link else Qt.CursorShape.IBeamCursor
                                  if self._hit_page(e.position()) else Qt.CursorShape.ArrowCursor)
        if link and link[2]:
            self.viewport().setToolTip(plain_tip(link[2]))
        else:
            self.viewport().setToolTip("")

    def _autoscroll(self, pos):
        vb = self.verticalScrollBar()
        if pos.y() < 10:
            vb.setValue(vb.value() - 24)
        elif pos.y() > self.viewport().height() - 10:
            vb.setValue(vb.value() + 24)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.MiddleButton:
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        if e.button() == Qt.MouseButton.LeftButton and not self._dragging and self._press_pos is not None:
            link = self._link_at(e.position())
            if link:
                target, y, url = link
                if target >= 0:
                    self.go(target, max(0.0, y - 24))         # a little above the target line
                elif url.lower().startswith(("http://", "https://", "mailto:")):
                    QDesktopServices.openUrl(QUrl(url))
            elif self.sel_rects:
                self.clear_selection()
        self._press = None
        self._dragging = False
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        hit = self._hit_page(e.position())
        if hit:
            word, rects = self.doc.word_at(*hit)
            if word:
                self.sel_rects = {hit[0]: rects}
                self.sel_text = word
                self._selected()

    def _select(self, a, b):
        (pa, qa), (pb, qb) = (a, b) if (a[0], a[1].y()) <= (b[0], b[1].y()) else (b, a)
        texts, rects = [], {}
        for page in range(pa, pb + 1):
            w, h = self.doc.sizes[page]
            start = qa if page == pa else QPointF(0, 0)
            end = qb if page == pb else QPointF(w, h)
            text, rs = self.doc.select(page, start, end)
            if text:
                texts.append(text)
            if rs:
                rects[page] = rs
        self.sel_rects = rects
        self.sel_text = "\n".join(texts)
        self._selected()

    def _selected(self):
        self.viewport().update()
        self.selectionChanged.emit(self.sel_text)
        if self.sel_text and QGuiApplication.clipboard().supportsSelection():
            QGuiApplication.clipboard().setText(self.sel_text, QGuiApplication.clipboard().Mode.Selection)

    def clear_selection(self):
        self.sel_rects, self.sel_text = {}, ""
        self.viewport().update()
        self.selectionChanged.emit("")

    def select_page(self):
        w, h = self.doc.sizes[self.page]
        self._select((self.page, QPointF(0, 0)), (self.page, QPointF(w, h)))

    def copy(self):
        if self.sel_text:
            QApplication.clipboard().setText(self.sel_text)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            d = e.angleDelta().y()
            if d:
                self.set_options(fit="custom", zoom=self.scale * (1.1 if d > 0 else 1 / 1.1))
            return
        if self.layout_mode == "single":
            vb = self.verticalScrollBar()
            d = e.angleDelta().y()
            if d < 0 and vb.value() >= vb.maximum() and self.page < self.doc.page_count - 1:
                self.go(self.page + 1)
                return
            if d > 0 and vb.value() <= vb.minimum() and self.page > 0:
                self.go(self.page - 1, self.doc.sizes[self.page - 1][1])
                self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
                return
        super().wheelEvent(e)

    # ------------------------------------------------------------ keys
    def keyPressEvent(self, e):
        if e.matches(QKeySequence.StandardKey.Copy):
            self.copy()
            return
        if e.matches(QKeySequence.StandardKey.SelectAll):
            self.select_page()
            return
        k, mods = e.key(), e.modifiers()
        vb, hb = self.verticalScrollBar(), self.horizontalScrollBar()
        page_step = max(40, self.viewport().height() - 48)
        K = Qt.Key
        if k in (K.Key_PageDown, K.Key_Space) and not (k == K.Key_Space and mods & Qt.KeyboardModifier.ShiftModifier):
            if vb.value() >= vb.maximum() and self.layout_mode == "single":
                self.step_page(1)
            else:
                vb.setValue(vb.value() + page_step)
        elif k in (K.Key_PageUp, K.Key_Space):
            if vb.value() <= vb.minimum() and self.layout_mode == "single" and self.page > 0:
                self.go(self.page - 1)
                vb.setValue(vb.maximum())
            else:
                vb.setValue(vb.value() - page_step)
        elif k == K.Key_Down:
            vb.setValue(vb.value() + 48)
        elif k == K.Key_Up:
            vb.setValue(vb.value() - 48)
        elif k in (K.Key_Right, K.Key_Left):
            forward = k == K.Key_Right
            if hb.maximum() > 0 and not mods & Qt.KeyboardModifier.AltModifier:
                hb.setValue(hb.value() + (48 if forward else -48))
            else:
                self.step_page(1 if forward else -1)
        elif k == K.Key_Home:
            self.go(0)
        elif k == K.Key_End:
            self.go(self.doc.page_count - 1)
        elif k == K.Key_Escape and self.sel_rects:
            self.clear_selection()
        else:
            super().keyPressEvent(e)

    def close(self):
        self.r.close()
