# SPDX-License-Identifier: GPL-3.0-or-later
"""The Community view inside a MuraL tab: browse the top 100 of a store category and install items.

Store traffic runs on its own thread pool (NET), never on jobs.POOL: a hundred slow thumbnail downloads there used
to hold every spell's background work (previews, Apply) for tens of seconds. Listings come from store.top's disk
cache (6 h) and stay in memory for the session; thumbnails are fetched, decoded and letterboxed into card images
off the UI thread, only for the cards on screen (plus one screen ahead), and kept in memory and on disk (store
.thumbnail, 14 days). prefetch() warms the default listings and their first cards when MuraL opens; it never
downloads an item. When the app quits, shutdown() drops queued store work and waits briefly for running requests,
so no worker is still starting work while Python shuts down.
"""
import threading
import webbrowser
from collections import OrderedDict

from PySide6.QtCore import QCoreApplication, QObject, QRect, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6 import QtGui
from PySide6.QtGui import QColor, QIcon, QImage, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from grimoire.i18n import tr, tr_noop
from grimoire.jobs import Job
from grimoire.spells.mural import store

CARD = QSize(232, 146)
NET = QThreadPool()                       # store listings + thumbnails (network-bound; not the app's shared POOL)
NET.setMaxThreadCount(8)
IN_FLIGHT = 8                             # thumbnail requests one view has running at a time
FIRST_CARDS = 12                          # cards prefetch() warms per category: about one screen
_LISTS: dict[tuple, list] = {}            # (category, sort, search) → items, this session
_CARDS: "OrderedDict[str, QImage]" = OrderedDict()   # thumbnail URL → finished card image (LRU)
_CARDS_MAX = 800
_cards_lock = threading.Lock()
_url_locks: dict[str, threading.Lock] = {}
_prefetched = False
_stopping = threading.Event()             # set by shutdown(): workers start nothing new
_hooked = False
QUIT_WAIT_MS = 2000                       # how long quitting waits for running store requests
SORTS = {"down": tr_noop("grimoire.spells.mural.storeview", "Most downloaded"),          # store sort id → label
         "high": tr_noop("grimoire.spells.mural.storeview", "Best rated"),
         "new": tr_noop("grimoire.spells.mural.storeview", "Newest")}


class _Signals(QObject):
    listed = Signal(int, object)          # generation, list[Item] or Exception
    thumb = Signal(int, int, QImage)      # generation, row, card image
    installed = Signal(bool, str)


def fit(img: QImage, size: QSize) -> QPixmap:
    """Letterbox an image onto a dark card of `size`."""
    pm = QPixmap(size)
    pm.fill(QColor("#111111"))
    if not img.isNull():
        scaled = img.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        p = QPainter(pm)
        p.drawImage((size.width() - scaled.width()) // 2, (size.height() - scaled.height()) // 2, scaled)
        p.end()
    return pm


def _label(it: store.Item, installed: bool) -> str:
    stats = f"{it.downloads:,} ↓" + (f"  ·  {it.score}%" if it.score else "")
    return f"{'✓ ' if installed else ''}{it.name}\n{stats}"


def _cached_card(url: str) -> QImage | None:
    with _cards_lock:
        img = _CARDS.get(url)
        if img is not None:
            _CARDS.move_to_end(url)
        return img


def card_image(url: str) -> QImage:
    """The finished card for a thumbnail URL (download if needed, decode at card size, letterbox). Worker threads
    only; the same URL is never fetched twice at once."""
    if (img := _cached_card(url)) is not None:
        return img
    with _cards_lock:
        lock = _url_locks.setdefault(url, threading.Lock())
    with lock:
        if (img := _cached_card(url)) is not None:
            return img
        path = store.thumbnail(url) if url else None
        src = QImage()
        if path:
            reader = QImageReader(str(path))
            size = reader.size()
            if size.isValid():                     # decode straight at card size: no full-size image in memory
                reader.setScaledSize(size.scaled(CARD, Qt.AspectRatioMode.KeepAspectRatio))
            src = reader.read()
        card = QImage(CARD, QImage.Format.Format_RGB32)
        card.fill(QColor("#111111"))
        if not src.isNull():
            scaled = src.scaled(CARD, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p = QPainter(card)
            p.drawImage((CARD.width() - scaled.width()) // 2, (CARD.height() - scaled.height()) // 2, scaled)
            p.end()
        if path:                                   # a failed download isn't cached: the next look tries again
            with _cards_lock:
                _CARDS[url] = card
                while len(_CARDS) > _CARDS_MAX:
                    _CARDS.popitem(last=False)
        return card


def _safe_card(url: str) -> QImage:
    """card_image that never raises: a view counts on every request coming back."""
    try:
        return card_image(url)
    except Exception as e:
        print(f"MuraL store thumbnail failed: {e}")
        return QImage()


def _listing(cat: store.Category, sort: str, search: str, fresh: bool = False) -> list:
    """Worker threads: the listing, from memory, the disk cache or the store."""
    key = (cat.key, sort, search)
    if not fresh and key in _LISTS:
        return _LISTS[key]
    items = store.top(cat, sort, search, fresh=fresh)
    _LISTS[key] = items
    return items


def shutdown(wait_ms: int = QUIT_WAIT_MS):
    """App quit: nothing new starts, queued store work is dropped, running requests get wait_ms to finish."""
    _stopping.set()
    NET.clear()
    NET.waitForDone(wait_ms)


def _start(job: Job, priority: int):
    """NET.start, unless the app is quitting; hooks shutdown() to the app's quit the first time."""
    global _hooked
    if _stopping.is_set():
        return
    if not _hooked and (app := QCoreApplication.instance()) is not None:
        _hooked = True
        app.aboutToQuit.connect(shutdown)
    try:
        NET.start(job, priority)
    except RuntimeError:                        # the pool went with the app while a prefetch was still queueing
        pass


def prefetch(keys=None):
    """Warm the default listing of each category and its first cards, in the background, once per run. Only
    listings and thumbnails: never an item's files. Cards go on NET at low priority, behind what a view asks for."""
    global _prefetched
    if _prefetched:
        return
    _prefetched = True
    cats = [store.CATEGORIES[k] for k in (keys or store.CATEGORIES)]

    def work():
        for cat in cats:
            if _stopping.is_set():
                return
            try:
                items = _listing(cat, "down", "")
            except Exception:                   # offline: the view will say so when it's opened
                continue
            for it in items[:FIRST_CARDS]:
                _start(Job(lambda url=it.preview: None if _stopping.is_set() else _safe_card(url), lambda _: None), -1)

    _start(Job(work, lambda _: None), -1)


class StoreView(QWidget):
    """on_installed() is called after an install/uninstall so the tab can refresh its designs."""

    def __init__(self, category_keys: list[str], on_installed):
        super().__init__()
        self.cats = [store.CATEGORIES[k] for k in category_keys]
        self.on_installed = on_installed
        self.items: list[store.Item] = []
        self._gen = 0
        self._sig = _Signals()
        self._sig.listed.connect(self._on_listed)
        self._sig.thumb.connect(self._on_thumb)
        self._sig.installed.connect(self._on_installed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.category = QComboBox()
        self.category.addItems([tr("grimoire.spells.mural.store", c.title) for c in self.cats])
        self.category.setVisible(len(self.cats) > 1)
        self.sort = QComboBox()
        for sort, label in SORTS.items():
            self.sort.addItem(tr("grimoire.spells.mural.storeview", label), sort)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.mural.storeview", "Search…"))
        self.search.setClearButtonEnabled(True)
        self.bw = QCheckBox(tr("grimoire.spells.mural.storeview", "Convert to black & white"))
        self.bw.setChecked(True)
        for w in (self.category, self.sort, self.search):
            bar.addWidget(w)
        bar.addWidget(self.bw)
        bar.addStretch(1)
        self.count = QLabel()
        self.count.setObjectName("Muted")
        self.count.setTextFormat(Qt.TextFormat.PlainText)
        bar.addWidget(self.count)
        self.refresh_btn = QPushButton(tr("grimoire.spells.mural.storeview", "Refresh"))
        self.refresh_btn.setToolTip(tr("grimoire.spells.mural.storeview", "Ask the store again (lists are kept for "
                                                                          "6 hours)"))
        self.refresh_btn.clicked.connect(lambda: self.refresh(fresh=True))
        bar.addWidget(self.refresh_btn)
        lay.addLayout(bar)
        self._search_timer = QTimer(self, singleShot=True, interval=450, timeout=self.refresh)
        self.category.currentIndexChanged.connect(self.refresh)
        self.sort.currentIndexChanged.connect(self.refresh)
        self.search.textChanged.connect(lambda _: self._search_timer.start())

        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.setIconSize(CARD)
        self.grid.setGridSize(QSize(CARD.width() + 16, CARD.height() + 52))
        self.grid.setUniformItemSizes(True)
        self.grid.setWordWrap(True)
        self.grid.currentRowChanged.connect(self._select)
        self.grid.itemDoubleClicked.connect(lambda _: self._install())
        self.grid.verticalScrollBar().valueChanged.connect(lambda _: self._pump_later())
        lay.addWidget(self.grid, 1)
        self._pending: list[int] = []             # rows whose card isn't shown yet
        self._inflight = 0
        self._pump_timer = QTimer(self, singleShot=True, interval=40, timeout=self._pump)

        detail = QFrame()
        detail.setObjectName("Card")
        dl = QHBoxLayout(detail)
        dl.setContentsMargins(18, 12, 12, 12)
        info = QVBoxLayout()
        info.setSpacing(2)
        self.d_name = QLabel(tr("grimoire.spells.mural.storeview", "Pick something to see details"))
        self.d_name.setObjectName("Section")
        self.d_meta = QLabel()
        self.d_meta.setObjectName("Muted")
        self.d_meta.setWordWrap(True)
        for lab in (self.d_name, self.d_meta):    # names and authors come from the store: never as HTML
            lab.setTextFormat(Qt.TextFormat.PlainText)
        info.addWidget(self.d_name)
        info.addWidget(self.d_meta)
        dl.addLayout(info, 1)
        self.page_btn = QPushButton(tr("grimoire.spells.mural.storeview", "Store page"))
        self.page_btn.clicked.connect(self._open_page)
        self.install_btn = QPushButton(tr("grimoire.spells.mural.storeview", "Install"))
        self.install_btn.setObjectName("Primary")
        self.install_btn.setMinimumWidth(130)
        self.install_btn.clicked.connect(self._install)
        dl.addWidget(self.page_btn)
        dl.addWidget(self.install_btn)
        lay.addWidget(detail)
        self._busy = False
        self._select(-1)
        self._loaded = False

    def showEvent(self, e):
        super().showEvent(e)
        if not self._loaded:              # only hit the network once the user opens Community
            self._loaded = True
            self.refresh()
        else:
            self._pump_later()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._pump_later()

    def cat(self) -> store.Category:
        return self.cats[max(0, self.category.currentIndex())]

    # ---- listing
    def refresh(self, fresh: bool = False):
        self._gen += 1
        gen, cat, sort, q, sig = self._gen, self.cat(), self.sort.currentData(), self.search.text().strip(), self._sig
        self.bw.setVisible(cat.kind == "wallpaper")
        self.grid.clear()
        self.items, self._pending = [], []
        if not fresh and (cat.key, sort, q) in _LISTS:          # seen this session: no thread, no wait
            self._on_listed(gen, _LISTS[(cat.key, sort, q)])
            return
        self.count.setText(tr("grimoire.spells.mural.storeview", "Loading…"))
        self.refresh_btn.setEnabled(False)

        def work():
            try:
                return _listing(cat, sort, q, fresh)
            except Exception as e:      # network errors are shown, not raised
                return e

        _start(Job(work, lambda r: sig.listed.emit(gen, r)), 1)

    def _on_listed(self, gen, result):
        if gen != self._gen:
            return
        self.refresh_btn.setEnabled(True)
        if isinstance(result, Exception):
            self.count.setText(tr("grimoire.spells.mural.storeview", "Couldn't reach the store: {error}")
                               .format(error=result))
            return
        self.items = result
        self.count.setText(tr("grimoire.spells.mural.storeview", "Top %n", n=len(result)))
        placeholder = QIcon(fit(QImage(), CARD))
        installed = {e["item"] for e in store.registry().values()}
        self.grid.setUpdatesEnabled(False)
        for i, it in enumerate(result):
            card = _cached_card(it.preview)
            row = QListWidgetItem(QIcon(QPixmap.fromImage(card)) if card is not None else placeholder,
                                  _label(it, it.id in installed))
            row.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            row.setToolTip(QtGui.Qt.convertFromPlainText(str(it.summary or it.name)))   # store text: never HTML
            self.grid.addItem(row)
            if card is None:
                self._pending.append(i)
        self.grid.setUpdatesEnabled(True)
        self._pump_later()

    # ---- thumbnails: the cards on screen first, one screen ahead, a few at a time
    def _pump_later(self):
        if self._pending:
            self._pump_timer.start()

    def _pump(self):
        if not self.isVisible() or not self._pending:
            return
        view = self.grid.viewport().rect()
        ahead = QRect(view.x(), view.y(), view.width(), view.height() * 2)
        wanted = [r for r in self._pending if r < self.grid.count()
                  and self.grid.visualItemRect(self.grid.item(r)).intersects(ahead)]
        gen, sig = self._gen, self._sig
        while wanted and self._inflight < IN_FLIGHT:
            r = wanted.pop(0)
            self._pending.remove(r)
            self._inflight += 1
            url = self.items[r].preview
            _start(Job(lambda url=url: _safe_card(url), lambda img, r=r: sig.thumb.emit(gen, r, img)), 1)

    def _on_thumb(self, gen, row, img):
        self._inflight = max(0, self._inflight - 1)
        if gen == self._gen and row < self.grid.count() and not img.isNull():
            self.grid.item(row).setIcon(QIcon(QPixmap.fromImage(img)))
        self._pump_later()

    # ---- detail / install
    def _current(self) -> store.Item | None:
        r = self.grid.currentRow()
        return self.items[r] if 0 <= r < len(self.items) else None

    def _select(self, _row):
        it = self._current()
        self.install_btn.setEnabled(it is not None and not self._busy)
        self.page_btn.setEnabled(bool(it and it.page))
        if not it:
            return
        self.d_name.setText(it.name.upper())
        bits = [tr("grimoire.spells.mural.storeview", "by {author}").format(author=it.author) if it.author else "",
                tr("grimoire.spells.mural.storeview", "%n download(s)", n=it.downloads),
                tr("grimoire.spells.mural.storeview", "rated {score}%").format(score=it.score) if it.score else "",
                it.summary]
        self.d_meta.setText("  ·  ".join(b for b in bits if b))
        self._label_install(it)

    def _label_install(self, it: store.Item):
        installed = store.is_installed(it.id)
        self.install_btn.setText(tr("grimoire.spells.mural.storeview", "Uninstall") if installed
                                 else tr("grimoire.spells.mural.storeview", "Install"))

    def _open_page(self):
        it = self._current()
        if it and it.page.startswith(("https://", "http://")):     # store data: never hand xdg-open a file or app URL
            webbrowser.open(it.page)

    def _install(self):
        it, cat, bw, sig = self._current(), self.cat(), self.bw.isChecked(), self._sig
        if not it or self._busy:          # a double-click while one runs would race it in the same work folder
            return
        self._busy = True
        self.install_btn.setEnabled(False)
        removing = store.is_installed(it.id)
        self.install_btn.setText(tr("grimoire.spells.mural.storeview", "Removing…") if removing
                                 else tr("grimoire.spells.mural.storeview", "Installing…"))

        def work():
            try:
                if removing:
                    for key, e in list(store.registry().items()):
                        if e["item"] == it.id:
                            store.uninstall(key)
                    return True, tr("grimoire.spells.mural.storeview", "Removed {name}").format(name=it.name)
                entries = store.install(cat, it, to_bw=bw)
                names = ", ".join(e["name"] for e in entries)
                return True, tr("grimoire.spells.mural.storeview", "Installed {name} — it's now in Designs")\
                    .format(name=names)
            except Exception as e:
                return False, tr("grimoire.spells.mural.storeview", "Couldn't install {name}: {error}")\
                    .format(name=it.name, error=e)

        _start(Job(work, lambda r: sig.installed.emit(*r)), 2)

    def _on_installed(self, ok, msg):
        self._busy = False
        self.d_meta.setText(msg)
        row = self.grid.currentRow()
        if ok and 0 <= row < len(self.items):
            it = self.items[row]
            self.grid.item(row).setText(_label(it, store.is_installed(it.id)))
        self.install_btn.setEnabled(True)
        it = self._current()
        if it:
            self._label_install(it)
        if ok:
            self.on_installed()
