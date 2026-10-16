# SPDX-License-Identifier: GPL-3.0-or-later
"""App cards: a list model, a painted card per app (grayscale icon, name, summary, source badges) and the grid view.

Thousands of apps scroll smoothly because nothing is a widget: the delegate paints each visible card, and icons are
decoded on a worker thread the first time a card shows (Icons), then kept. Keyboard: arrows move, Enter opens.
"""
from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QListView, QStyle, QStyledItemDelegate

from grimoire.glyphs import glyph
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.storel import library, media

CARD = QSize(300, 104)
ICON = 52
AppRole = Qt.ItemDataRole.UserRole + 1


def gray(img: QImage) -> QImage:
    """img in grays, keeping its transparency (safe off the UI thread)."""
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    alpha = img.convertToFormat(QImage.Format.Format_Alpha8)
    out = img.convertToFormat(QImage.Format.Format_Grayscale8).convertToFormat(QImage.Format.Format_ARGB32)
    out.setAlphaChannel(alpha)
    return out


def _load(icon: dict, size: int) -> QImage | None:
    """Worker side: the icon file (or the remote one, fetched once) as a scaled grayscale image."""
    path = icon.get("file") or ""
    img = QImage(path) if path else QImage()
    if img.isNull() and icon.get("url") and not icon.get("stock"):
        p = media.get(icon["url"])
        img = QImage(str(p)) if p else QImage()
    if img.isNull():
        return None
    return gray(img.scaled(size * 2, size * 2, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation))


class Icons(QObject):
    """Grayscale app icons by catalog key, loaded once each; ready(key) when one arrives."""
    ready = Signal(str)
    _loaded = Signal(object)

    def __init__(self):
        super().__init__()
        self.cache: dict[str, QPixmap | None] = {}
        self._pending: set[str] = set()
        self._loaded.connect(self._done)
        self.fallback = glyph("storel", ICON).pixmap(ICON * 2, ICON * 2)

    def get(self, app: dict) -> QPixmap | None:
        key = app["key"]
        if key in self.cache:
            return self.cache[key]
        if key in self._pending:
            return None
        icon = app.get("icon") or {}
        if not icon.get("file") and icon.get("stock"):            # a theme icon: QIcon is UI-thread only
            qi = QIcon.fromTheme(icon["stock"])
            if not qi.isNull():
                pm = qi.pixmap(ICON * 2, ICON * 2)
                self.cache[key] = QPixmap.fromImage(gray(pm.toImage())) if not pm.isNull() else None
                if self.cache[key] is not None:
                    return self.cache[key]
            if not icon.get("url"):
                self.cache[key] = None
                return None
        if not icon.get("file") and not icon.get("url"):
            self.cache[key] = None
            return None
        self._pending.add(key)
        POOL.start(Job(lambda: (key, _load(icon, ICON)), self._loaded.emit))
        return None

    def _done(self, result):
        key, img = result
        self._pending.discard(key)
        self.cache[key] = QPixmap.fromImage(img) if img is not None else None
        self.ready.emit(key)


class AppModel(QAbstractListModel):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.apps: list[dict] = []

    def set_apps(self, apps: list[dict]):
        self.beginResetModel()
        self.apps = list(apps)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.apps)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.apps):
            return None
        app = self.apps[index.row()]
        if role == AppRole:
            return app
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            return app["name"]
        if role == Qt.ItemDataRole.ToolTipRole:
            return None
        return None

    def refresh_key(self, key: str):
        for row, a in enumerate(self.apps):
            if a["key"] == key:
                idx = self.index(row)
                self.dataChanged.emit(idx, idx)

    def refresh_all(self):
        if self.apps:
            self.dataChanged.emit(self.index(0), self.index(len(self.apps) - 1))


def badges(page, app: dict) -> list[tuple[str, bool]]:
    """(text, solid) badges: each source the app comes from, and Installed / In queue."""
    out = []
    for name in dict.fromkeys(library.offer_name(o).split(" · ")[0] for o in app["offers"]):
        out.append((name.upper(), False))
    state = page.app_state(app)
    if state == "installed":
        out.insert(0, (tr("grimoire.spells.storel.grid", "INSTALLED"), True))
    elif state == "queued":
        out.insert(0, (tr("grimoire.spells.storel.grid", "IN QUEUE"), True))
    return out


class CardDelegate(QStyledItemDelegate):
    def __init__(self, page, icons: Icons):
        super().__init__()
        self.page, self.icons = page, icons

    def sizeHint(self, option, index):
        view = option.widget
        return view.gridSize() if view is not None else CARD

    def paint(self, p: QPainter, option, index):
        app = index.data(AppRole)
        if not app:
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rtl = option.direction == Qt.LayoutDirection.RightToLeft
        r = QRectF(option.rect).adjusted(5, 5, -5, -5)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        focus = bool(option.state & QStyle.StateFlag.State_HasFocus)
        p.setPen(QPen(QColor("#f2f2f2" if selected and focus else "#6a6a6a" if selected or hover else "#1f1f1f"), 1))
        p.setBrush(QColor("#141414" if selected or hover else "#101010"))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)

        def vis(x, w):                      # a span measured from the reading side → screen coordinates
            return r.right() - x - w if rtl else r.left() + x

        pad = 14
        pm = self.icons.get(app) or self.icons.fallback
        icon = QRectF(vis(pad, ICON), r.top() + (r.height() - ICON) / 2, ICON, ICON)
        p.drawPixmap(icon, pm, QRectF(pm.rect()))
        tx = pad + ICON + 14
        tw = r.width() - tx - pad
        # on the reading side whatever the text's own letters are (an English name in Arabic, say)
        align = Qt.AlignmentFlag.AlignAbsolute | (Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)
        f = QFont(option.font)
        f.setPixelSize(14)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        fm = QFontMetrics(f)
        p.setPen(QColor("#ffffff"))
        top = r.top() + 12
        p.drawText(QRectF(vis(tx, tw), top, tw, fm.height()), align | Qt.AlignmentFlag.AlignVCenter,
                   library.isolate(fm.elidedText(app["name"], Qt.TextElideMode.ElideRight, int(tw))))
        top += fm.height() + 2
        f2 = QFont(option.font)
        f2.setPixelSize(12)
        p.setFont(f2)
        fm2 = QFontMetrics(f2)
        p.setPen(QColor("#8c8c8c"))
        lines = _two_lines(app["summary"], fm2, int(tw))
        for ln in lines:
            p.drawText(QRectF(vis(tx, tw), top, tw, fm2.height()), align | Qt.AlignmentFlag.AlignVCenter,
                       library.isolate(ln))
            top += fm2.height()
        # badges along the bottom
        fb = QFont(option.font)
        fb.setPixelSize(9)
        fb.setWeight(QFont.Weight.Bold)
        p.setFont(fb)
        fmb = QFontMetrics(fb)
        x = tx
        y = r.bottom() - 12 - fmb.height()
        for text, solid in badges(self.page, app):
            w = fmb.horizontalAdvance(text) + 12
            if x + w > tx + tw:
                break
            box = QRectF(vis(x, w), y, w, fmb.height() + 4)
            if solid:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#f2f2f2"))
            else:
                p.setPen(QPen(QColor("#3a3a3a"), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
            p.setPen(QColor("#000000" if solid else "#9a9a9a"))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
            x += w + 6
        p.restore()


def _two_lines(text: str, fm: QFontMetrics, width: int) -> list[str]:
    """text wrapped into at most two lines, the second elided."""
    words, lines, cur = (text or "").split(), [], ""
    for i, w in enumerate(words):
        trial = f"{cur} {w}".strip()
        if fm.horizontalAdvance(trial) <= width or not cur:
            cur = trial
            continue
        lines.append(cur)
        if len(lines) == 1:
            rest = " ".join(words[i:])
            lines.append(fm.elidedText(rest, Qt.TextElideMode.ElideRight, width))
            return lines
        cur = w
    if cur:
        lines.append(fm.elidedText(cur, Qt.TextElideMode.ElideRight, width))
    return lines[:2]


class AppGrid(QListView):
    """Cards in rows that fill the width; activated(app) on click or Enter."""
    opened = Signal(object)

    def __init__(self, page, icons: Icons, scroll: bool = True):
        super().__init__()
        self.model_ = AppModel(page)
        self.setModel(self.model_)
        self.setItemDelegate(CardDelegate(page, icons))
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setGridSize(CARD)
        self.setMouseTracking(True)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setStyleSheet("QListView { background: transparent; border: none; }"
                           "QListView::item, QListView::item:selected, QListView::item:hover "
                           "{ border: none; background: transparent; }")
        self.clicked.connect(lambda idx: self.opened.emit(idx.data(AppRole)))
        self.activated.connect(lambda idx: self.opened.emit(idx.data(AppRole)))
        icons.ready.connect(self.model_.refresh_key)
        self.fit = not scroll
        if self.fit:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def set_apps(self, apps: list[dict]):
        self.model_.set_apps(apps)
        self._fit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def _fit(self):
        """Cards stretch to fill each row; inside a page that scrolls itself the grid is as tall as all its cards,
        so it never scrolls on its own."""
        width = self.viewport().width() - 2 or CARD.width()
        per_row = max(1, width // CARD.width())
        cell = QSize(width // per_row, CARD.height())
        if cell != self.gridSize():
            self.setGridSize(cell)
        if self.fit:
            rows = -(-self.model_.rowCount() // per_row)
            self.setFixedHeight(rows * CARD.height() + 4)

    def wheelEvent(self, e):
        if self.fit:
            e.ignore()                       # let the page scroll
            return
        super().wheelEvent(e)
