# SPDX-License-Identifier: GPL-3.0-or-later
"""The music library: albums (grayscale covers + a details panel), artists and every song, with search.

Opening it shows the cached scan at once and rescans in the background; covers are read one at a time on a worker
thread as albums come into view, never on the UI thread."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListView,
                               QListWidget, QListWidgetItem, QMenu, QPushButton, QSizePolicy, QSplitter,
                               QStackedWidget, QTableView, QVBoxLayout, QWidget)

from grimoire.glyphs import _pixmap, glyph
from grimoire.i18n import ltr, tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.playl import art, library, media
from grimoire.widgets import plain_tip

VIEWS = ["albums", "artists", "songs"]       # the stack's pages, picked from the page's side bar
TILE = 150
KEY = Qt.ItemDataRole.UserRole


def _placeholder(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor("#1f1f1f"))
    p.setBrush(QColor("#101010"))
    p.drawRoundedRect(1, 1, size - 2, size - 2, 8, 8)
    g = size * 3 // 8
    p.drawPixmap((size - g) // 2, (size - g) // 2, _pixmap("music", "#3a3a3a", g))
    p.end()
    return pm


def _square(path, size: int) -> QPixmap:
    """A cover filling a square tile (cropped to the middle), rounded corners."""
    src = QPixmap(str(path))
    if src.isNull():
        return _placeholder(size)
    src = src.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(src)
    p.setBrushOrigin(-(src.width() - size) // 2, -(src.height() - size) // 2)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, size, size, 8, 8)
    p.end()
    return pm


class Covers(QObject):
    """Reads covers one by one on the pool (newest asks first); loaded(key, path or None) on the UI thread."""
    loaded = Signal(str, object)
    _got = Signal(object)

    def __init__(self):
        super().__init__()
        self.todo: list[tuple[str, str]] = []
        self.known: dict[str, object] = {}
        self.busy = False
        self._got.connect(self._done)

    def want(self, key: str, path: str):
        if key in self.known:
            self.loaded.emit(key, self.known[key])
            return
        self.todo = [t for t in self.todo if t[0] != key] + [(key, path)]
        self._next()

    def _next(self):
        if self.busy or not self.todo:
            return
        self.busy = True
        key, path = self.todo.pop()
        POOL.start(Job(lambda: (key, self._read(key, path)), self._got.emit))

    @staticmethod
    def _read(key, path):
        try:
            return art.cover(path, key)
        except Exception:                 # a broken picture never stops the others
            return None

    def _done(self, result):
        self.busy = False
        key, path = result
        self.known[key] = path
        self.loaded.emit(key, path)
        self._next()


class SongsModel(QAbstractTableModel):
    COLUMNS = [("track", tr_noop("grimoire.spells.playl.libraryview", "#")),
               ("title", tr_noop("grimoire.spells.playl.libraryview", "Title")),
               ("artist", tr_noop("grimoire.spells.playl.libraryview", "Artist")),
               ("album", tr_noop("grimoire.spells.playl.libraryview", "Album")),
               ("duration", tr_noop("grimoire.spells.playl.libraryview", "Length"))]

    def __init__(self, columns=("title", "artist", "album", "duration")):
        super().__init__()
        self.cols = [c for c in self.COLUMNS if c[0] in columns]
        self.rows: list[dict] = []

    def set_rows(self, rows: list[dict]):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.cols)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        t = self.rows[index.row()]
        key = self.cols[index.column()][0]
        if role == Qt.ItemDataRole.DisplayRole:
            if key == "duration":
                return media.clock(t.get("duration")) if t.get("duration") else ""
            if key == "track":
                return str(t["track"]) if t.get("track") else ""
            return t.get(key) or ""
        if role == Qt.ItemDataRole.TextAlignmentRole and key in ("duration", "track"):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole:
            return t["path"]
        if role == Qt.ItemDataRole.ForegroundRole and key in ("artist", "album", "duration", "track"):
            return QColor("#8c8c8c")
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return tr("grimoire.spells.playl.libraryview", self.cols[section][1]).upper()
        return None


class SongsTable(QTableView):
    play = Signal(list, int)
    enqueue = Signal(list)

    def __init__(self, columns=("title", "artist", "album", "duration")):
        super().__init__()
        self.model_ = SongsModel(columns)
        self.setModel(self.model_)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setAlternatingRowColors(False)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(32)
        h = self.horizontalHeader()
        h.setHighlightSections(False)
        for i, (key, _) in enumerate(self.model_.cols):
            h.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch if key in ("title", "artist", "album")
                                   else QHeaderView.ResizeMode.ResizeToContents)
        self.doubleClicked.connect(lambda ix: self.play.emit([t["path"] for t in self.model_.rows], ix.row()))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def set_rows(self, rows):
        self.model_.set_rows(rows)

    def _selected(self) -> list[str]:
        rows = sorted({ix.row() for ix in self.selectionModel().selectedRows()})
        return [self.model_.rows[r]["path"] for r in rows]

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.currentIndex().isValid():
            self.play.emit([t["path"] for t in self.model_.rows], self.currentIndex().row())
            return
        super().keyPressEvent(e)

    def _menu(self, pos):
        ix = self.indexAt(pos)
        if not ix.isValid():
            return
        sel = self._selected() or [self.model_.rows[ix.row()]["path"]]
        m = QMenu(self)
        m.addAction(tr("grimoire.spells.playl.libraryview", "Play"),
                    lambda: self.play.emit([t["path"] for t in self.model_.rows], ix.row()))
        m.addAction(tr("grimoire.spells.playl.libraryview", "Add to the queue"), lambda: self.enqueue.emit(sel))
        m.exec(self.viewport().mapToGlobal(pos))


class AlbumPanel(QFrame):
    """The picked album: cover, names, Play / Add to the queue and its tracks."""
    play = Signal(list, int)
    enqueue = Signal(list)

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.setMinimumWidth(300)
        self.setMaximumWidth(380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(8)
        self.cover = QLabel()
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.cover)
        lay.addSpacing(6)
        self.title = QLabel()
        self.title.setObjectName("SectionTitle")
        self.artist = QLabel()
        self.artist.setObjectName("Muted")
        self.facts = QLabel()
        self.facts.setObjectName("Muted")
        for lab in (self.title, self.artist):
            lab.setWordWrap(True)
            lab.setTextFormat(Qt.TextFormat.PlainText)
        for w in (self.title, self.artist, self.facts):
            lay.addWidget(w)
        row = QHBoxLayout()
        self.play_btn = QPushButton(glyph("play", 14), " " + tr("grimoire.spells.playl.libraryview", "Play"))
        self.play_btn.setObjectName("Primary")
        self.add_btn = QPushButton(tr("grimoire.spells.playl.libraryview", "Add to the queue"))
        row.addWidget(self.play_btn, 1)
        row.addWidget(self.add_btn, 1)
        lay.addLayout(row)
        self.tracks = SongsTable(("track", "title", "duration"))
        self.tracks.play.connect(self.play)
        self.tracks.enqueue.connect(self.enqueue)
        lay.addWidget(self.tracks, 1)
        self.album: dict | None = None
        self.play_btn.clicked.connect(lambda: self.album and self.play.emit(self._paths(), 0))
        self.add_btn.clicked.connect(lambda: self.album and self.enqueue.emit(self._paths()))
        self.show_album(None)

    def _paths(self):
        return [t["path"] for t in self.album["tracks"]]

    def show_album(self, album: dict | None, cover=None):
        self.album = album
        for w in (self.play_btn, self.add_btn, self.tracks):
            w.setEnabled(album is not None)
        if album is None:
            self.cover.setPixmap(_placeholder(220))
            self.title.setText(tr("grimoire.spells.playl.libraryview", "Pick an album"))
            self.artist.setText("")
            self.facts.setText("")
            self.tracks.set_rows([])
            return
        self.set_cover(cover)
        self.title.setText(album["title"])
        self.artist.setText(album["artist"])
        length = sum(t.get("duration") or 0 for t in album["tracks"])
        bits = [tr("grimoire.spells.playl.libraryview", "%n song(s)", n=len(album["tracks"]))]
        if length:
            bits.append(ltr(media.clock(length)))
        if album.get("year"):
            bits.insert(0, ltr(album["year"]))
        self.facts.setText(" · ".join(bits))
        self.tracks.set_rows(album["tracks"])

    def set_cover(self, path):
        self.cover.setPixmap(_square(path, 220) if path else _placeholder(220))


class LibraryPanel(QWidget):
    play = Signal(list, int)              # entries, start
    enqueue = Signal(list)
    _scanned = Signal(object)
    _progress = Signal(int)

    def __init__(self):
        super().__init__()
        self.tracks: list[dict] = []
        self.loaded = False
        self.scanning = False
        self.covers = Covers()
        self.covers.loaded.connect(self._cover)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.playl.libraryview", "Search titles, artists, albums"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._search_timer.start())
        top.addWidget(self.search, 1)
        self.rescan = QPushButton(tr("grimoire.spells.playl.libraryview", "Scan again"))
        self.rescan.setToolTip(tr("grimoire.spells.playl.libraryview", "Look through the library folders again"))
        self.rescan.clicked.connect(lambda: self.scan(force=True))
        top.addWidget(self.rescan)
        lay.addLayout(top)
        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.status)
        self._search_timer = QTimer(self, singleShot=True, interval=150, timeout=self._fill)

        self.stack = QStackedWidget()
        # albums: grid + details
        albums = QSplitter()
        albums.setChildrenCollapsible(False)
        self.grid = QListWidget()
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setIconSize(QSize(TILE, TILE))
        self.grid.setGridSize(QSize(TILE + 26, TILE + 58))
        self.grid.setUniformItemSizes(True)
        self.grid.setWordWrap(True)
        self.grid.setSpacing(4)
        self.grid.currentItemChanged.connect(self._picked)
        self.grid.itemActivated.connect(lambda it: self._play_album(it.data(KEY)))
        self.grid.verticalScrollBar().valueChanged.connect(lambda _v: self._visible_timer.start())
        self.detail = AlbumPanel()
        self.detail.play.connect(self.play)
        self.detail.enqueue.connect(self.enqueue)
        albums.addWidget(self.grid)
        albums.addWidget(self.detail)
        albums.setStretchFactor(0, 1)
        self.stack.addWidget(albums)
        # artists: names + their songs
        artists = QSplitter()
        artists.setChildrenCollapsible(False)
        self.artist_list = QListWidget()
        self.artist_list.setObjectName("Places")
        self.artist_list.setMinimumWidth(200)
        self.artist_list.setMaximumWidth(320)
        self.artist_list.currentItemChanged.connect(self._artist_picked)
        self.artist_songs = SongsTable(("title", "album", "duration"))
        artists.addWidget(self.artist_list)
        artists.addWidget(self.artist_songs)
        artists.setStretchFactor(1, 1)
        self.stack.addWidget(artists)
        # songs
        self.songs = SongsTable()
        self.stack.addWidget(self.songs)
        for t in (self.songs, self.artist_songs):
            t.play.connect(self.play)
            t.enqueue.connect(self.enqueue)
        lay.addWidget(self.stack, 1)
        self.empty = QLabel()
        self.empty.setObjectName("Muted")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.empty.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        lay.addWidget(self.empty)
        self._visible_timer = QTimer(self, singleShot=True, interval=60, timeout=self._want_visible)
        self._albums: dict[str, dict] = {}
        self._items: dict[str, QListWidgetItem] = {}
        self._artists: dict[str, list] = {}
        self._scanned.connect(self._got)
        self._progress.connect(lambda n: self.status.setText(
            tr("grimoire.spells.playl.libraryview", "Scanning… %n song(s) so far", n=n)))
        self.view = "albums"
        self.show_view("albums")

    # ------------------------------------------------------------ loading
    def showEvent(self, e):
        if not self.loaded:
            self.loaded = True
            POOL.start(Job(library.load_cache, lambda tracks: self._scanned.emit(("cache", tracks))))
        super().showEvent(e)

    def scan(self, force=False):
        if self.scanning:
            return
        self.scanning = True
        self.rescan.setEnabled(False)
        roots = media.library_roots()
        self.covers.known = {k: v for k, v in self.covers.known.items() if v}   # albums without one look again

        def work():
            art.forget()                       # a cover may have been added since
            return "scan", library.scan(roots, self._progress.emit)
        if force or not self.tracks:
            self.status.setText(tr("grimoire.spells.playl.libraryview", "Scanning your music…"))
        POOL.start(Job(work, self._scanned.emit))

    def _got(self, result):
        kind, tracks = result
        self.tracks = tracks
        if kind == "scan":
            self.scanning = False
            self.rescan.setEnabled(True)
        self._fill()
        if kind == "cache":
            self.scan()                       # then look for changes in the background
        else:
            self._status()

    def _status(self):
        roots = ", ".join(ltr(r) for r in media.load()["library"])
        line = tr("grimoire.spells.playl.libraryview", "%n song(s) in {folders}", n=len(self.tracks)).format(
            folders=roots)
        if not library.has_mutagen():
            line += "\n" + tr("grimoire.spells.playl.libraryview",
                              "Names come from the file names. For tags, install mutagen: {command}").format(
                command=ltr("sudo apt install python3-mutagen"))
        self.status.setText(line)

    def titles(self) -> dict:
        """path → tags, for the queue's names."""
        return {t["path"]: t for t in self.tracks}

    # ------------------------------------------------------------ views
    def show_view(self, vid: str):
        self.view = vid
        self.stack.setCurrentIndex(VIEWS.index(vid))
        self._want_visible()

    def _filtered(self) -> list[dict]:
        words = self.search.text().lower().split()
        return [t for t in self.tracks if library.matches(t, words)] if words else self.tracks

    def _fill(self):
        tracks = self._filtered()
        has_any = bool(self.tracks)
        self.stack.setVisible(has_any)
        self.empty.setVisible(not has_any)
        if not has_any:
            self.empty.setText(tr("grimoire.spells.playl.libraryview",
                                  "No music found yet. PlayL looks in your library folders (Settings), and "
                                  "~/Music to begin with."))
        # albums
        current = self.grid.currentItem().data(KEY) if self.grid.currentItem() else None
        albums = library.albums(tracks)
        self._albums = {a["key"]: a for a in albums}
        self._items = {}
        self.grid.blockSignals(True)
        self.grid.clear()
        ph = QIcon(_placeholder(TILE))
        for a in albums:
            text = a["title"] + ("\n" + a["artist"] if a["artist"] else "")
            it = QListWidgetItem(ph, text)
            it.setData(KEY, a["key"])
            it.setToolTip(plain_tip(text))
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.grid.addItem(it)
            self._items[a["key"]] = it
            known = self.covers.known.get(a["key"], "")
            if known:
                it.setIcon(QIcon(_square(known, TILE)))
        self.grid.blockSignals(False)
        if current in self._items:
            self.grid.setCurrentItem(self._items[current])
        elif self.grid.count():
            self.grid.setCurrentRow(0)
            self._picked(self.grid.item(0))
        else:
            self.detail.show_album(None)
        # artists
        cur_artist = self.artist_list.currentItem().data(KEY) if self.artist_list.currentItem() else None
        self._artists = dict(library.artists(tracks))
        self.artist_list.blockSignals(True)
        self.artist_list.clear()
        for name, songs in self._artists.items():
            it = QListWidgetItem(name or tr("grimoire.spells.playl.libraryview", "Unknown artist"))
            it.setData(KEY, name)
            self.artist_list.addItem(it)
            if name == cur_artist:
                self.artist_list.setCurrentItem(it)
        if self.artist_list.currentItem() is None and self.artist_list.count():
            self.artist_list.setCurrentRow(0)
        self.artist_list.blockSignals(False)
        self._artist_picked(self.artist_list.currentItem())
        # songs
        self.songs.set_rows(sorted(tracks, key=lambda t: (media._natural(t.get("artist") or "~"),
                                                          media._natural(t.get("album") or ""),
                                                          *library.sort_key(t))))
        self._want_visible()

    def _want_visible(self):
        """Ask for the covers of the albums on screen (and the picked one)."""
        if self.view != "albums" or not self._items:
            return
        vp = self.grid.viewport().rect()
        for key, it in self._items.items():
            if key in self.covers.known:
                continue
            if self.grid.visualItemRect(it).intersects(vp):
                album = self._albums[key]
                self.covers.want(key, album["tracks"][0]["path"])

    def _cover(self, key: str, path):
        it = self._items.get(key)
        if it is not None and path:
            it.setIcon(QIcon(_square(path, TILE)))
        if self.detail.album and self.detail.album["key"] == key:
            self.detail.set_cover(path)

    def _picked(self, it, _prev=None):
        if it is None:
            return
        album = self._albums.get(it.data(KEY))
        self.detail.show_album(album, self.covers.known.get(album["key"]) if album else None)
        if album and album["key"] not in self.covers.known:
            self.covers.want(album["key"], album["tracks"][0]["path"])

    def _artist_picked(self, it, _prev=None):
        songs = self._artists.get(it.data(KEY), []) if it is not None else []
        self.artist_songs.set_rows(songs)

    def _play_album(self, key):
        album = self._albums.get(key)
        if album:
            self.play.emit([t["path"] for t in album["tracks"]], 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._visible_timer.start()
