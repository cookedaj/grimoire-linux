# SPDX-License-Identifier: GPL-3.0-or-later
"""ViewL page: browse a folder as a grid of thumbnails, open a picture full size with a strip of its neighbours,
turn/flip/zoom it, run a slideshow, see its info, and sort it (rename, Trash, copy/move, set as wallpaper, mark up
in ShotL's editor, show in VaultL).

Every disk read happens on a worker: folder listings (jobs.POOL), thumbnails (thumbs.Loader), decoding
(view.Decoder), EXIF (infoview.gather) and the file changes in ops.py. Nothing changes a file without a click, and
turns stay on screen until Save (which asks first) or Save as.

Keys in the full view: ←/→ (also PgUp/PgDn, Space, Backspace) previous/next, Home/End, +/- zoom, 0 fit, 1 100%,
R/L turn, H/V flip, I info, F/F11 full screen, F5 slideshow, Ctrl+C copy, E mark up, Del Trash, F2 rename,
Ctrl+S save, Ctrl+Shift+S save as, P pause an animation, Esc back.
"""

import random
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import (
    QAbstractListModel,
    QFileSystemWatcher,
    QMimeData,
    QModelIndex,
    QObject,
    QProcess,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from grimoire import i18n
from grimoire.fsutil import tilde
from grimoire.glyphs import glyph
from grimoire.i18n import isolate, ltr, tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.paths import DATA, command
from grimoire.spells.viewl import exif, images, ops, thumbs
from grimoire.spells.viewl.infoview import InfoPanel, gather
from grimoire.spells.viewl.view import Canvas, Decoded, Decoder
from grimoire.widgets import plain_tip

SIZES = (112, 160, 224)  # grid thumbnail boxes: small, medium, large
STRIP = 72
THUMB_CACHE = 1500  # pixmaps kept in memory (~100 KB each)
INTERVALS = (2, 3, 4, 5, 8, 10, 15, 30)
PLACES = [
    (tr_noop("grimoire.spells.viewl.page", "Pictures"), "mural", "~/Pictures"),
    (tr_noop("grimoire.spells.viewl.page", "Screenshots"), "shot", "~/Pictures/Screenshots"),
    (tr_noop("grimoire.spells.viewl.page", "Wallpapers"), "desktop", "@wallpapers"),
    (tr_noop("grimoire.spells.viewl.page", "Downloads"), "store", "~/Downloads"),
    (tr_noop("grimoire.spells.viewl.page", "Desktop"), "desktop", "~/Desktop"),
    (tr_noop("grimoire.spells.viewl.page", "Home"), "home", "~"),
]


def _place(spec: str) -> Path:
    if spec == "@wallpapers":
        return DATA / "mural" / "library"
    return Path(spec).expanduser()


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)  # file and folder names
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _tool(icon: str, tip: str, slot=None, checkable=False) -> QToolButton:
    b = QToolButton()
    b.setObjectName("Tool")
    b.setIcon(glyph(icon, 18))
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keys belong to the picture
    if slot:
        b.clicked.connect(lambda _=False: slot())
    return b


def _sep() -> QFrame:
    f = QFrame()
    f.setFixedSize(1, 20)
    f.setStyleSheet("background: #262626;")
    return f


class _Signals(QObject):
    scanned = Signal(int, object, object)  # generation, folder, entries or an error text
    info = Signal(object, object)  # path, info dict
    done = Signal(object)  # (kind, result) of a file change


# ---------------------------------------------------------------- grid and strip
class EntryModel(QAbstractListModel):
    def __init__(self, page):
        super().__init__(page)
        self.entries: list[images.Entry] = []

    def set(self, entries):
        self.beginResetModel()
        self.entries = list(entries)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.entries):
            return None
        e = self.entries[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return e.name
        if role == Qt.ItemDataRole.UserRole:
            return e
        return None

    def flags(self, index):
        return super().flags(index) | Qt.ItemFlag.ItemIsDragEnabled

    def mimeTypes(self):
        return ["text/uri-list"]

    def mimeData(self, indexes):
        """Dragged out: plain file URLs, so VaultL, Dolphin or a chat app takes the files."""
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(self.entries[i.row()].path)) for i in indexes if i.isValid()])
        return data


class ThumbDelegate(QStyledItemDelegate):
    def __init__(self, page, strip=False):
        super().__init__(page)
        self.page, self.strip = page, strip

    def box(self) -> int:
        return STRIP if self.strip else SIZES[self.page.s["size"]]

    def sizeHint(self, option, index):
        b = self.box()
        return QSize(b + 8, b + 8) if self.strip else QSize(b + 18, b + 46)

    def paint(self, p: QPainter, option, index):
        e: images.Entry = index.data(Qt.ItemDataRole.UserRole)
        if e is None:
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = option.rect.adjusted(3, 3, -3, -3)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if self.strip:
            current = index.row() == self.page.cur
            pm = self.page.thumb(e)
            area = QRectF(r)
            if pm:
                scaled = pm.size().scaled(r.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding)
                src = QRectF(
                    (scaled.width() - r.width()) / 2, (scaled.height() - r.height()) / 2, r.width(), r.height()
                )
                k = pm.width() / max(1, scaled.width())
                src = QRectF(src.x() * k, src.y() * k, src.width() * k, src.height() * k)
                clip = QPainterPath()
                clip.addRoundedRect(area, 6, 6)
                p.setClipPath(clip)
                p.drawPixmap(area, pm, src)
                if not current:
                    p.fillRect(area, QColor(0, 0, 0, 110))  # the current one stands out
                p.setClipping(False)
            else:
                p.fillRect(area, QColor("#141414"))
            if current or hover:
                p.setPen(QColor("#ffffff" if current else "#5a5a5a"))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(area.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)
            p.restore()
            return
        if selected or hover:
            path = QPainterPath()
            path.addRoundedRect(QRectF(r), 10, 10)
            p.fillPath(path, QColor("#232323" if selected else "#141414"))
        b = self.box()
        icon = QRect(r.center().x() - b // 2, r.y() + 6, b, b)
        if e.is_dir:
            g = int(b * 0.55)
            glyph("folder", 48).paint(
                p,
                QRect(icon.center().x() - g // 2, icon.center().y() - g // 2, g, g),
                mode=QIcon.Mode.Active if selected else QIcon.Mode.Normal,
            )
        else:
            pm = self.page.thumb(e)
            if pm:
                s = pm.size().scaled(icon.size(), Qt.AspectRatioMode.KeepAspectRatio)
                target = QRect(icon.x() + (b - s.width()) // 2, icon.y() + (b - s.height()) // 2, s.width(), s.height())
                p.drawPixmap(target, pm)
            elif str(e.path) in self.page.failed:
                glyph("document", 48).paint(p, icon.adjusted(b // 4, b // 4, -b // 4, -b // 4))
            else:
                p.fillRect(icon.adjusted(b // 8, b // 8, -b // 8, -b // 8), QColor("#121212"))
        p.setPen(QColor("#ffffff" if selected else "#bdbdbd"))
        fm = QFontMetrics(option.font)
        text = QRect(r.x() + 6, icon.bottom() + 6, r.width() - 12, fm.height() * 2 + 2)
        p.drawText(
            text,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            fm.elidedText(e.name, Qt.TextElideMode.ElideMiddle, text.width()),
        )
        p.restore()


# ---------------------------------------------------------------- full screen
class FullWindow(QWidget):
    """A borderless full-screen window the canvas moves into (works the same in the hub and alone)."""

    closing = Signal()

    def __init__(self):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("ViewL")
        self.setStyleSheet("background: #000000;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

    def closeEvent(self, e):
        self.closing.emit()
        super().closeEvent(e)


class RenameDialog(QDialog):
    def __init__(self, parent, name: str):
        super().__init__(parent)
        self.setWindowTitle(tr("grimoire.spells.viewl.page", "Rename"))
        lay = QVBoxLayout(self)
        lay.addWidget(_label(tr("grimoire.spells.viewl.page", "New name"), "Muted"))
        self.edit = QLineEdit(name)
        self.edit.setMinimumWidth(380)
        stem = Path(name).stem if Path(name).suffix else name
        self.edit.setSelection(0, len(stem))  # the extension stays put unless you mean it
        lay.addWidget(self.edit)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText(tr("grimoire.spells.viewl.page", "Rename"))
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)


# ---------------------------------------------------------------- the page
class ViewLPage(QWidget):
    title_changed = Signal(str)

    def __init__(self, start: Path | None = None, standalone: bool = False):
        super().__init__()
        self.setObjectName("Page")
        self.setAcceptDrops(True)
        self.standalone = standalone
        self.s = images.load()
        self.sig = _Signals()
        self.sig.scanned.connect(self._scanned)
        self.sig.info.connect(self._info_ready)
        self.sig.done.connect(self._done)
        self.folder: Path | None = None
        self.all: list[images.Entry] = []  # the folder, sorted
        self.entries: list[images.Entry] = []  # after the filter (grid)
        self.images: list[images.Entry] = []  # pictures only (strip, next/previous)
        self.cur = -1
        self.orient = 1  # the user's unsaved turns of the current picture
        self.gen = 0
        self.mode = "browse"
        self._pending_select: Path | None = None
        self._pending_view = False
        self._busy = False
        self.pix: OrderedDict[str, QPixmap] = OrderedDict()
        self.failed: set[str] = set()
        self.full: FullWindow | None = None
        self.loader = thumbs.Loader(self)
        self.loader.ready.connect(self._thumb_ready)
        self.decoder = Decoder(self)
        self.decoder.ready.connect(self._decoded)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(lambda _: self._rescan_timer.start())
        self._rescan_timer = QTimer(self, singleShot=True, interval=500, timeout=self.rescan)
        self.slide = QTimer(self, timeout=self._slide_next)
        self._cursor_timer = QTimer(self, singleShot=True, interval=2000, timeout=self._hide_cursor)
        self._toast_timer = QTimer(self, singleShot=True, interval=5000, timeout=lambda: self.toast.hide())

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_nav())
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_browse())
        self.stack.addWidget(self._build_viewer())
        right.addWidget(self.stack, 1)
        self.toast = _label("", "Toast", wrap=True)
        self.toast.hide()
        tl = QHBoxLayout()
        tl.setContentsMargins(24, 0, 24, 12)
        tl.addWidget(self.toast)
        right.addLayout(tl)
        root.addLayout(right, 1)
        self._build_actions()
        self._set_mode("browse")
        self.open_path(start or Path(self.s["folder"] or images.default_folder()))

    # ---------------------------------------------------------------- building
    def _build_nav(self) -> QFrame:
        self.nav = QFrame()
        self.nav.setObjectName("SubNav")
        self.nav.setMinimumWidth(200)
        nl = QVBoxLayout(self.nav)
        nl.setContentsMargins(12, 26, 12, 16)
        nl.setSpacing(2)
        nl.addWidget(_label("ViewL", "Title"))
        nl.addSpacing(12)
        nl.addWidget(_label(tr("grimoire.spells.viewl.page", "PLACES"), "NavSection"))
        self.place_btns: list[tuple[QPushButton, Path]] = []
        for name, icon, spec in PLACES:
            path = _place(spec)
            b = QPushButton(glyph(icon, 18), "  " + tr("grimoire.spells.viewl.page", name))
            b.setObjectName("SubNavItem")
            b.setCheckable(True)
            b.setToolTip(plain_tip(tilde(path)))
            b.clicked.connect(lambda _=False, p=path: self.open_path(p))
            b.setVisible(path.is_dir())
            nl.addWidget(b)
            self.place_btns.append((b, path))
        nl.addSpacing(10)
        nl.addWidget(_label(tr("grimoire.spells.viewl.page", "RECENT"), "NavSection"))
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(2)
        nl.addLayout(self.recent_box)
        nl.addStretch(1)
        other = QPushButton(glyph("folder", 18), "  " + tr("grimoire.spells.viewl.page", "Open a folder…"))
        other.setObjectName("SubNavItem")
        other.clicked.connect(self.choose_folder)
        nl.addWidget(other)
        return self.nav

    def _build_browse(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(32, 26, 32, 12)
        lay.setSpacing(12)
        head = QHBoxLayout()
        self.heading = _label("", "PageHeading")
        head.addWidget(self.heading, 1)
        self.count = _label("", "Muted")
        head.addWidget(self.count)
        lay.addLayout(head)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.up_btn = _tool("up", tr("grimoire.spells.viewl.page", "Up a folder (Backspace)"), self.go_up)
        bar.addWidget(self.up_btn)
        self.crumb = _label("", "Muted")
        self.crumb.setTextFormat(Qt.TextFormat.PlainText)
        bar.addWidget(self.crumb, 1)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("grimoire.spells.viewl.page", "Filter by name"))
        self.filter.setClearButtonEnabled(True)
        self.filter.setMaximumWidth(260)
        self.filter.textChanged.connect(lambda _: self._apply_filter())
        bar.addWidget(self.filter)
        self.sort = QComboBox()
        for key, name in images.SORTS.items():
            self.sort.addItem(tr("grimoire.spells.viewl.images", name), key)
        self.sort.setCurrentIndex(list(images.SORTS).index(self.s["sort"]))
        self.sort.setToolTip(tr("grimoire.spells.viewl.page", "Sort by"))
        self.sort.currentIndexChanged.connect(self._sorted)
        bar.addWidget(self.sort)
        self.rev = _tool("down", tr("grimoire.spells.viewl.page", "Reverse the order"), self._reversed, checkable=True)
        self.rev.setChecked(self.s["reverse"])
        bar.addWidget(self.rev)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(0, 2)
        self.size_slider.setPageStep(1)
        self.size_slider.setFixedWidth(80)
        self.size_slider.setValue(self.s["size"])
        self.size_slider.setToolTip(tr("grimoire.spells.viewl.page", "Thumbnail size"))
        self.size_slider.valueChanged.connect(self._resized)
        bar.addWidget(self.size_slider)
        bar.addWidget(_tool("play", tr("grimoire.spells.viewl.page", "Slideshow (F5)"), self.start_slideshow))
        lay.addLayout(bar)

        self.grid_model = EntryModel(self)
        self.grid = QListView()
        self.grid.setObjectName("FileGrid")
        self.grid.setModel(self.grid_model)
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setUniformItemSizes(True)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.grid.setDragEnabled(True)
        self.grid.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.grid.setMouseTracking(True)
        self.grid.setSpacing(2)
        self.grid.setItemDelegate(ThumbDelegate(self))
        self.grid.activated.connect(self._grid_activated)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._grid_menu)
        lay.addWidget(self.grid, 1)
        self.empty = _label("", "Muted", wrap=True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.hide()
        lay.addWidget(self.empty, 1)
        return w

    def _build_viewer(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.vbar = QFrame()
        self.vbar.setStyleSheet(
            "QToolButton::menu-indicator { image: none; width: 0; }"
            'QToolButton#Tool[popupMode="1"] { padding-right: 14px; }'
            "QToolButton::menu-button { border: none; width: 12px; }"
            "QToolButton::menu-arrow { image: none; }"
        )
        bar = QHBoxLayout(self.vbar)
        bar.setContentsMargins(14, 10, 14, 10)
        bar.setSpacing(4)
        bar.addWidget(_tool("grid", tr("grimoire.spells.viewl.page", "Back to the folder (Esc)"), self.back_to_folder))
        bar.addWidget(_tool("back", tr("grimoire.spells.viewl.page", "Previous picture"), lambda: self.step(-1)))
        bar.addWidget(_tool("forward", tr("grimoire.spells.viewl.page", "Next picture"), lambda: self.step(1)))
        names = QVBoxLayout()
        names.setSpacing(0)
        self.name = _label("", "RowTitle")
        self.name.setMinimumWidth(80)
        names.addWidget(self.name)
        self.where = _label("", "Muted")
        names.addWidget(self.where)
        bar.addSpacing(8)
        bar.addLayout(names, 1)
        self.zoom_btn = QToolButton()
        self.zoom_btn.setObjectName("Tool")
        self.zoom_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.zoom_btn.setToolTip(tr("grimoire.spells.viewl.page", "Zoom"))
        self.zoom_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        zm = QMenu(self.zoom_btn)
        zm.addAction(tr("grimoire.spells.viewl.page", "Fit to the window"), lambda: self.canvas.set_fit())
        for pct in (25, 50, 100, 200, 400):
            zm.addAction(
                tr("grimoire.spells.viewl.page", "{pct}%").format(pct=pct), lambda z=pct / 100: self.canvas.set_zoom(z)
            )
        self.zoom_btn.setMenu(zm)
        self.zoom_btn.setMinimumWidth(64)
        bar.addWidget(self.zoom_btn)
        bar.addWidget(
            _tool("zoomout", tr("grimoire.spells.viewl.page", "Zoom out (-)"), lambda: self.canvas.zoom_by(1 / 1.25))
        )
        bar.addWidget(
            _tool("zoomin", tr("grimoire.spells.viewl.page", "Zoom in (+)"), lambda: self.canvas.zoom_by(1.25))
        )
        bar.addWidget(_tool("fit", tr("grimoire.spells.viewl.page", "Fit (0)"), lambda: self.canvas.set_fit()))
        bar.addWidget(
            _tool(
                "actual", tr("grimoire.spells.viewl.page", "Actual size, 100% (1)"), lambda: self.canvas.set_zoom(1.0)
            )
        )
        bar.addSpacing(6)
        bar.addWidget(_sep())
        bar.addSpacing(6)
        bar.addWidget(_tool("rotl", tr("grimoire.spells.viewl.page", "Turn left (L)"), lambda: self.turn("ccw")))
        bar.addWidget(_tool("rotr", tr("grimoire.spells.viewl.page", "Turn right (R)"), lambda: self.turn("cw")))
        bar.addWidget(
            _tool("fliph", tr("grimoire.spells.viewl.page", "Flip left to right (H)"), lambda: self.turn("fliph"))
        )
        bar.addWidget(
            _tool("flipv", tr("grimoire.spells.viewl.page", "Flip upside down (V)"), lambda: self.turn("flipv"))
        )
        bar.addSpacing(6)
        bar.addWidget(_sep())
        bar.addSpacing(6)
        self.pause_btn = _tool("pause", tr("grimoire.spells.viewl.page", "Pause the animation (P)"), self.toggle_pause)
        bar.addWidget(self.pause_btn)
        self.slide_btn = QToolButton()
        self.slide_btn.setObjectName("Tool")
        self.slide_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slide_btn.setIcon(glyph("play", 18))
        self.slide_btn.setToolTip(tr("grimoire.spells.viewl.page", "Slideshow (F5)"))
        self.slide_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.slide_btn.clicked.connect(self.start_slideshow)
        self.slide_btn.setMenu(self._slide_menu())
        bar.addWidget(self.slide_btn)
        bar.addWidget(_tool("fullscreen", tr("grimoire.spells.viewl.page", "Full screen (F)"), self.toggle_fullscreen))
        self.info_btn = _tool("preview", tr("grimoire.spells.viewl.page", "Info (I)"), self.toggle_info, checkable=True)
        self.info_btn.setChecked(self.s["info"])
        bar.addWidget(self.info_btn)
        more = QToolButton()
        more.setObjectName("Tool")
        more.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        more.setIcon(glyph("more", 18))
        more.setToolTip(tr("grimoire.spells.viewl.page", "More"))
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu = QMenu(more)
        self.more_menu.aboutToShow.connect(lambda: self._fill_menu(self.more_menu, self.current_paths()))
        more.setMenu(self.more_menu)
        bar.addWidget(more)
        lay.addWidget(self.vbar)

        self.pending = QFrame()
        self.pending.setObjectName("Row")
        self.pending.setProperty("pending", "true")
        pl = QHBoxLayout(self.pending)
        pl.setContentsMargins(14, 8, 10, 8)
        self.pending_text = _label("", wrap=True)
        pl.addWidget(self.pending_text, 1)
        self.save_btn = QPushButton(tr("grimoire.spells.viewl.page", "Save"))
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(lambda: self.save(ask=True))
        self.saveas_btn = QPushButton(tr("grimoire.spells.viewl.page", "Save as…"))
        self.saveas_btn.clicked.connect(self.save_as)
        undo = QPushButton(tr("grimoire.spells.viewl.page", "Undo turns"))
        undo.clicked.connect(self.reset_turns)
        for b in (self.save_btn, self.saveas_btn, undo):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            pl.addWidget(b)
        holder = QHBoxLayout()
        holder.setContentsMargins(14, 0, 14, 8)
        holder.addWidget(self.pending)
        lay.addLayout(holder)

        self.middle = QHBoxLayout()
        self.middle.setSpacing(0)
        self.canvas = Canvas()
        self.canvas.zoomed.connect(self._zoomed)
        self.canvas.activated.connect(self.toggle_fullscreen)
        self.canvas.step.connect(self.step)
        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._canvas_menu)
        self.canvas.installEventFilter(self)
        self.middle.addWidget(self.canvas, 1)
        self.info = InfoPanel()
        self.info.setVisible(self.s["info"])
        self.middle.addWidget(self.info)
        lay.addLayout(self.middle, 1)

        self.strip_model = EntryModel(self)
        self.strip = QListView()
        self.strip.setModel(self.strip_model)
        self.strip.setFlow(QListView.Flow.LeftToRight)
        self.strip.setWrapping(False)
        self.strip.setUniformItemSizes(True)
        self.strip.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.strip.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.strip.setFixedHeight(STRIP + 26)
        self.strip.setMouseTracking(True)
        self.strip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.strip.setItemDelegate(ThumbDelegate(self, strip=True))
        self.strip.setStyleSheet(
            "QListView { background: #070707; border-top: 1px solid #161616; }"
            "QListView::item, QListView::item:selected, QListView::item:hover "
            "{ border: none; background: transparent; padding: 0; }"
        )
        self.strip.clicked.connect(lambda i: self.show_image(i.row()))
        lay.addWidget(self.strip)
        return w

    def _slide_menu(self) -> QMenu:
        m = QMenu(self)
        m.addSection(tr("grimoire.spells.viewl.page", "Change picture every"))
        self.interval_actions = []
        for sec in INTERVALS:
            a = m.addAction(tr("grimoire.spells.viewl.page", "%n second(s)", n=sec))
            a.setCheckable(True)
            a.setChecked(sec == self.s["interval"])
            a.triggered.connect(lambda _=False, v=sec: self._set_interval(v))
            self.interval_actions.append((a, sec))
        m.addSeparator()
        shuffle = m.addAction(tr("grimoire.spells.viewl.page", "Shuffle"))
        shuffle.setCheckable(True)
        shuffle.setChecked(self.s["shuffle"])
        shuffle.toggled.connect(self._set_shuffle)
        return m

    def _build_actions(self):
        """Keyboard shortcuts, shared by the page and the full-screen window."""
        rtl = i18n.rtl()
        back, fwd = ("Right", "Left") if rtl else ("Left", "Right")  # the strip runs right to left there
        spec = [
            ("prev", [back, "PgUp", "Backspace"], lambda: self.step(-1), True),
            ("next", [fwd, "PgDown", "Space"], self._space_or_next, True),
            ("first", ["Home"], lambda: self.show_image(0), True),
            ("last", ["End"], lambda: self.show_image(len(self.images) - 1), True),
            ("zin", ["+", "=", "Ctrl++", "Ctrl+="], lambda: self.canvas.zoom_by(1.25), True),
            ("zout", ["-", "Ctrl+-"], lambda: self.canvas.zoom_by(1 / 1.25), True),
            ("fit", ["0", "Ctrl+0"], lambda: self.canvas.set_fit(), True),
            ("actual", ["1", "Ctrl+1"], lambda: self.canvas.set_zoom(1.0), True),
            ("cw", ["R", "Ctrl+R"], lambda: self.turn("cw"), True),
            ("ccw", ["L", "Ctrl+L"], lambda: self.turn("ccw"), True),
            ("fliph", ["H"], lambda: self.turn("fliph"), True),
            ("flipv", ["V"], lambda: self.turn("flipv"), True),
            ("info", ["I"], self.toggle_info, True),
            ("full", ["F", "F11"], self.toggle_fullscreen, True),
            ("pause", ["P"], self.toggle_pause, True),
            ("edit", ["E"], self.edit, True),
            ("save", ["Ctrl+S"], lambda: self.save(ask=True), True),
            ("saveas", ["Ctrl+Shift+S"], self.save_as, True),
            ("esc", ["Esc"], self.escape, False),
            ("slideshow", ["F5"], self.start_slideshow, False),
            ("copy", ["Ctrl+C"], self.copy, False),
            ("trash", ["Del"], self.trash, False),
            ("rename", ["F2"], self.rename, False),
            ("up", ["Alt+Up"], self.go_up, False),
            ("find", ["Ctrl+F"], self._focus_filter, False),
            ("open", ["Ctrl+O"], self.choose_folder, False),
        ]
        self.acts: dict[str, QAction] = {}
        self.view_only: list[QAction] = []
        for key, keys, slot, view_only in spec:
            a = QAction(self)
            a.setShortcuts([QKeySequence(k) for k in keys])
            a.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            a.triggered.connect(lambda _=False, f=slot: f())
            self.addAction(a)
            self.acts[key] = a
            if view_only:
                self.view_only.append(a)
        self.acts["browse_up"] = a = QAction(self)  # Backspace goes up a folder in the grid
        a.setShortcut(QKeySequence("Backspace"))
        a.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        a.triggered.connect(self.go_up)
        self.grid.addAction(a)

    # ---------------------------------------------------------------- folders
    def open_path(self, path: Path):
        path = Path(path).expanduser()
        if path.is_dir():
            self.open_folder(path)
        elif path.is_file():
            self.open_folder(path.parent, select=path, view=True)
        else:
            self.say(tr("grimoire.spells.viewl.page", "{path} isn't there").format(path=ltr(tilde(path))))
            if self.folder is None:
                self.open_folder(images.default_folder())

    def open_folder(self, folder: Path, select: Path | None = None, view: bool = False):
        if not self.settle():
            return
        if self.slide.isActive():
            self.stop_slideshow()
        folder = folder.resolve() if folder.exists() else folder
        same = folder == self.folder
        if not same:
            self.loader.clear()
            if self.watcher.directories():
                self.watcher.removePaths(self.watcher.directories())
            self.watcher.addPath(str(folder))
            self.folder = folder
            self.filter.blockSignals(True)
            self.filter.clear()
            self.filter.blockSignals(False)
        self._pending_select, self._pending_view = select, view
        if not view and self.mode != "browse":
            self._set_mode("browse")
        self.heading.setText(isolate(folder.name or str(folder)))  # stays on the start side in RTL
        self.crumb.setText(ltr(tilde(folder)))  # a path reads left to right in Arabic and Urdu too
        self.up_btn.setEnabled(folder.parent != folder)
        for b, p in self.place_btns:
            b.setChecked(p == folder)
        self.rescan()

    def rescan(self):
        if self.folder is None:
            return
        self.gen += 1
        gen, folder, sig = self.gen, self.folder, self.sig

        def work():
            try:
                return images.listing(folder)
            except OSError as e:
                return e.strerror or str(e)

        POOL.start(Job(work, lambda r: sig.scanned.emit(gen, folder, r)))

    def _scanned(self, gen: int, folder: Path, result):
        if gen != self.gen or folder != self.folder:
            return
        if isinstance(result, str):
            self.all = []
            self._apply_filter()
            self.empty.setText(tr("grimoire.spells.viewl.page", "Can't read this folder: {error}").format(error=result))
            return
        images.remember(self.s, folder)
        self._fill_recent()
        old = self.images[self.cur].path if 0 <= self.cur < len(self.images) else None
        self.all = images.sort(result, self.s["sort"], self.s["reverse"])
        self._apply_filter()
        select, view = self._pending_select, self._pending_view
        self._pending_select, self._pending_view = None, False
        if select is not None:
            i = next((n for n, e in enumerate(self.images) if e.path == select), -1)
            if view and i >= 0:
                self.show_image(i, ask=False)
                self._set_mode("view")
            elif i >= 0:
                self._select_in_grid(select)
            return
        if self.mode == "view":  # the folder changed under an open picture
            i = next((n for n, e in enumerate(self.images) if e.path == old), -1)
            if i >= 0:
                self.cur = i
                self._update_labels()
                self._sync_strip()
            elif self.images:
                self.show_image(min(max(self.cur, 0), len(self.images) - 1), ask=False)
            else:
                self.cur = -1
                self._set_mode("browse")

    def _apply_filter(self):
        text = self.filter.text().strip().casefold()
        self.entries = [e for e in self.all if not text or text in e.name.casefold()]
        self.images = [e for e in self.all if not e.is_dir]
        self.grid_model.set(self.entries)
        self.strip_model.set(self.images)
        n_pics = sum(1 for e in self.entries if not e.is_dir)
        self.count.setText(tr("grimoire.spells.viewl.page", "%n picture(s)", n=n_pics))
        nothing = not self.entries
        self.grid.setVisible(not nothing)
        self.empty.setVisible(nothing)
        self.empty.setText(
            tr("grimoire.spells.viewl.page", "Nothing matches “{text}”").format(text=self.filter.text())
            if text
            else tr("grimoire.spells.viewl.page", "No pictures in this folder")
        )
        if self.mode == "view":
            self._sync_strip()

    def _sorted(self, _i):
        self.s["sort"] = self.sort.currentData()
        images.save(self.s)
        self._resort()

    def _reversed(self):
        self.s["reverse"] = self.rev.isChecked()
        images.save(self.s)
        self._resort()

    def _resort(self):
        old = self.images[self.cur].path if 0 <= self.cur < len(self.images) else None
        self.all = images.sort(self.all, self.s["sort"], self.s["reverse"])
        self._apply_filter()
        if old:
            self.cur = next((n for n, e in enumerate(self.images) if e.path == old), self.cur)
            self._update_labels()
            self._sync_strip()

    def _resized(self, v: int):
        self.s["size"] = v
        images.save(self.s)
        self.grid.setItemDelegate(ThumbDelegate(self))  # new size hints
        self.grid.doItemsLayout()

    def _fill_recent(self):
        while self.recent_box.count():
            w = self.recent_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        places = {p for _, p in self.place_btns}
        for r in [Path(r) for r in self.s["recent"] if Path(r) not in places][:5]:
            b = QPushButton(glyph("folder", 18), "  " + (r.name or str(r)))
            b.setObjectName("SubNavItem")
            b.setCheckable(True)
            b.setChecked(r == self.folder)
            b.setToolTip(plain_tip(tilde(r)))
            b.clicked.connect(lambda _=False, p=r: self.open_path(p))
            self.recent_box.addWidget(b)

    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(
            self, tr("grimoire.spells.viewl.page", "Open a folder"), str(self.folder or Path.home())
        )
        if d:
            self.open_folder(Path(d))

    def go_up(self):
        if self.mode == "view":
            self.back_to_folder()
            return
        if self.folder and self.folder.parent != self.folder:
            child = self.folder
            self.open_folder(self.folder.parent, select=child)

    def _select_in_grid(self, path: Path):
        for n, e in enumerate(self.entries):
            if e.path == path:
                idx = self.grid_model.index(n)
                self.grid.setCurrentIndex(idx)
                self.grid.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)
                return

    def _grid_activated(self, index: QModelIndex):
        e: images.Entry = index.data(Qt.ItemDataRole.UserRole)
        if e.is_dir:
            self.open_folder(e.path)
            return
        i = next((n for n, x in enumerate(self.images) if x.path == e.path), -1)
        if i >= 0:
            self.show_image(i)
            self._set_mode("view")

    def _focus_filter(self):
        if self.mode == "browse":
            self.filter.setFocus()
            self.filter.selectAll()

    # ---------------------------------------------------------------- modes
    def _set_mode(self, mode: str):
        self.mode = mode
        view = mode == "view"
        self.stack.setCurrentIndex(1 if view else 0)
        self.nav.setVisible(not view)
        for a in self.view_only:
            a.setEnabled(view)
        self.acts["browse_up"].setEnabled(not view)
        if view:
            self.canvas.setFocus()
            self._sync_strip()
        else:
            self.canvas.clear()
            self.grid.setFocus()
            self.title_changed.emit(self.folder.name if self.folder else "")

    def back_to_folder(self):
        if not self.settle():
            return
        path = self.images[self.cur].path if 0 <= self.cur < len(self.images) else None
        self.stop_slideshow()
        self.exit_fullscreen()
        self._set_mode("browse")
        if path:
            self._select_in_grid(path)

    def escape(self):
        if self.slide.isActive():
            self.stop_slideshow()
            self.exit_fullscreen()
        elif self.full:
            self.exit_fullscreen()
        elif self.mode == "view":
            self.back_to_folder()
        elif self.filter.text():
            self.filter.clear()

    # ---------------------------------------------------------------- thumbnails
    def thumb(self, e: images.Entry) -> QPixmap | None:
        key = str(e.path)
        pm = self.pix.get(key)
        if pm is not None:
            self.pix.move_to_end(key)
            return pm
        if key not in self.failed:
            self.loader.request(key, e.mtime, e.size)
        return None

    def _thumb_ready(self, path: str, img: QImage):
        if img.isNull():
            self.failed.add(path)
        else:
            self.pix[path] = QPixmap.fromImage(img)
            while len(self.pix) > THUMB_CACHE:
                self.pix.popitem(last=False)
            if (
                0 <= self.cur < len(self.images)
                and str(self.images[self.cur].path) == path
                and self.canvas.placeholder is False
                and not self.canvas.has_picture()
                and not self.canvas.message[0]
            ):
                self._placeholder(self.images[self.cur])
        self.grid.viewport().update()
        self.strip.viewport().update()

    # ---------------------------------------------------------------- the picture
    def current(self) -> images.Entry | None:
        return self.images[self.cur] if 0 <= self.cur < len(self.images) else None

    def current_paths(self) -> list[Path]:
        if self.mode == "view":
            e = self.current()
            return [e.path] if e else []
        return [
            i.data(Qt.ItemDataRole.UserRole).path
            for i in self.grid.selectionModel().selectedIndexes()
            if not i.data(Qt.ItemDataRole.UserRole).is_dir
        ]

    def _key(self, e: images.Entry):
        return (str(e.path), e.mtime)

    def show_image(self, i: int, ask: bool = True):
        if not self.images:
            return
        i = max(0, min(i, len(self.images) - 1))
        if ask and i != self.cur and not self.settle():
            return
        self.cur = i
        self.orient = 1
        self.canvas.orient = 1
        e = self.images[i]
        self._update_labels()
        self._sync_strip()
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen:
            g = screen.size() * screen.devicePixelRatio()
            self.decoder.side = max(1600, min(4096, max(g.width(), g.height())))
        d = self.decoder.get(self._key(e))
        if d is not None:
            self._present(e, d)
        else:
            self._placeholder(e)
            self.decoder.request(self._key(e), first=True)
        for n in (i + 1, i - 1, i + 2):  # the neighbours, so next/previous is instant
            if 0 <= n < len(self.images):
                self.decoder.request(self._key(self.images[n]))
        self._refresh_info()
        self._update_pending()

    def _placeholder(self, e: images.Entry):
        pm = self.pix.get(str(e.path))
        if pm is not None:
            self.canvas.show_placeholder(pm.toImage(), QSize())
        else:
            self.canvas.clear()

    def _decoded(self, key, d: Decoded):
        e = self.current()
        if e and key == self._key(e) and self.mode == "view":
            self._present(e, d)

    def _present(self, e: images.Entry, d: Decoded):
        if d.error or d.image.isNull():
            ext = e.path.suffix.lower().lstrip(".")
            detail = tr("grimoire.spells.viewl.page", "The file may be damaged or in a format Qt can't read.")
            if d.error:
                detail += "\n" + ltr(d.error)  # Qt's own reason, in English
            if ext in images.PLUGIN_EXT and ext not in images.extensions():
                detail = tr(
                    "grimoire.spells.viewl.page", "Reading this format needs Qt's extra image plugins: {command}"
                ).format(command=ltr(images.PLUGIN_HINT))
            self.canvas.clear(
                tr("grimoire.spells.viewl.page", "Couldn't open {name}").format(name=isolate(e.name)), detail
            )
            self.pause_btn.hide()
            self.zoom_btn.setText("–")
            return
        self.canvas.show_decoded(d)
        if d.animated:
            self.canvas.play(str(e.path))
        self.pause_btn.setVisible(d.animated)
        self.pause_btn.setIcon(glyph("pause", 18))
        self.canvas.set_orient(self.orient)

    def _update_labels(self):
        e = self.current()
        if not e:
            return
        self.name.setText(e.name)
        self.where.setText(
            tr("grimoire.spells.viewl.page", "{n} of {total}").format(n=self.cur + 1, total=len(self.images))
            + "  ·  "
            + ltr(tilde(e.path.parent))
        )
        self.title_changed.emit(e.name)

    def _sync_strip(self):
        if 0 <= self.cur < self.strip_model.rowCount():
            idx = self.strip_model.index(self.cur)
            self.strip.setCurrentIndex(idx)
            self.strip.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.strip.viewport().update()

    def _zoomed(self, z: float, fit: bool):
        self.zoom_btn.setText(tr("grimoire.spells.viewl.page", "{pct}%").format(pct=max(1, round(z * 100))))

    def step(self, d: int):
        if not self.images:
            return
        n = self.cur + d
        if 0 <= n < len(self.images):
            self.show_image(n)
            if self.slide.isActive():
                self.slide.start()  # a manual step restarts the countdown

    def _space_or_next(self):
        if self.slide.isActive() or self._slide_paused:
            self.pause_slideshow()
        else:
            self.step(1)

    def toggle_pause(self):
        if self.canvas.movie:
            self.canvas.toggle_pause()
            self.pause_btn.setIcon(glyph("play" if self.canvas.paused() else "pause", 18))

    # ---------------------------------------------------------------- turns
    def turn(self, op: str):
        if not self.current() or not self.canvas.has_picture():
            return
        self.orient = exif.compose(self.orient, op)
        self.canvas.set_orient(self.orient)
        if self.canvas.fit:
            self.canvas.set_fit()
        self._update_pending()

    def reset_turns(self):
        self.orient = 1
        self.canvas.set_orient(1)
        self.canvas.set_fit()
        self._update_pending()

    def _update_pending(self):
        e = self.current()
        show = self.orient != 1 and e is not None
        self.pending.setVisible(show)
        if not show:
            return
        animated = self.canvas.movie is not None
        if animated:
            self.pending_text.setText(
                tr("grimoire.spells.viewl.page", "Turned on screen only: animated pictures can't be saved turned here")
            )
        elif ops.lossless(e.path, e.path):
            self.pending_text.setText(
                tr(
                    "grimoire.spells.viewl.page",
                    "Turned, not saved yet · JPEGs are saved losslessly: only the orientation tag changes",
                )
            )
        elif ops.writable(e.path.suffix):
            self.pending_text.setText(tr("grimoire.spells.viewl.page", "Turned, not saved yet"))
        else:
            self.pending_text.setText(
                tr(
                    "grimoire.spells.viewl.page",
                    "Turned, not saved yet · this format can't be written here, use Save as",
                )
            )
        self.save_btn.setEnabled(
            not animated and not self._busy and (ops.lossless(e.path, e.path) or ops.writable(e.path.suffix))
        )
        self.saveas_btn.setEnabled(not animated and not self._busy)

    def settle(self) -> bool:
        """Before leaving a turned picture: Save / Save as / Discard / Cancel. True when it's fine to go on."""
        e = self.current()
        if self.orient == 1 or e is None or self.canvas.movie is not None or self.mode != "view":
            return True
        box = QMessageBox(
            QMessageBox.Icon.NoIcon,
            "ViewL",
            tr("grimoire.spells.viewl.page", "Save the turned {name}?").format(name=isolate(e.name)),
            parent=self,
        )
        box.setTextFormat(Qt.TextFormat.PlainText)  # a file name like "<b>x</b>.jpg" is no markup
        box.setInformativeText(
            tr("grimoire.spells.viewl.page", "Save replaces the file; the original goes to the Trash.")
        )
        save = box.addButton(tr("grimoire.spells.viewl.page", "Save"), QMessageBox.ButtonRole.AcceptRole)
        save.setEnabled(ops.lossless(e.path, e.path) or ops.writable(e.path.suffix))
        save_as = box.addButton(tr("grimoire.spells.viewl.page", "Save as…"), QMessageBox.ButtonRole.ActionRole)
        discard = box.addButton(tr("grimoire.spells.viewl.page", "Discard"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(save if save.isEnabled() else save_as)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            if not self.save(ask=False):  # another change still running: keep the turn, stay here
                return False
        elif clicked is save_as:
            if not self.save_as():
                return False
        elif clicked is not discard:
            return False
        self.orient = 1
        self._update_pending()
        return True

    def save(self, ask: bool) -> bool:
        """True when the save started."""
        e = self.current()
        if not e or self.orient == 1 or self._busy or not self.save_btn.isEnabled():
            return False
        if ask:
            box = QMessageBox(
                QMessageBox.Icon.NoIcon,
                "ViewL",
                tr("grimoire.spells.viewl.page", "Replace {name} with the turned picture?").format(
                    name=isolate(e.name)
                ),
                parent=self,
            )
            box.setTextFormat(Qt.TextFormat.PlainText)  # a file name like "<b>x</b>.jpg" is no markup
            box.setInformativeText(
                tr("grimoire.spells.viewl.page", "The original goes to the Trash, so you can get it back.")
            )
            ok = box.addButton(tr("grimoire.spells.viewl.page", "Replace"), QMessageBox.ButtonRole.AcceptRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(ok)
            box.exec()
            if box.clickedButton() is not ok:
                return False
        orient, path = self.orient, e.path
        self._run("saved", lambda: ops.save_turned(path, orient))
        self.orient = 1  # the canvas keeps showing the turn until the saved file is reloaded
        self._update_pending()
        return True

    def save_as(self) -> bool:
        e = self.current()
        if not e or self._busy:
            return False
        kinds = ";;".join(
            [
                tr("grimoire.spells.viewl.page", "Same format") + f" (*{e.path.suffix})",
                tr("grimoire.spells.viewl.page", "PNG image") + " (*.png)",
                tr("grimoire.spells.viewl.page", "JPEG image") + " (*.jpg)",
                tr("grimoire.spells.viewl.page", "WebP image") + " (*.webp)",
            ]
        )
        start = str(e.path.with_name(f"{e.path.stem} (2){e.path.suffix}"))
        name, chosen = QFileDialog.getSaveFileName(
            self,
            tr("grimoire.spells.viewl.page", "Save the picture as"),
            start,
            kinds,
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not name:
            return False
        dest = Path(name)
        if not dest.suffix:
            dest = dest.with_suffix(chosen.rpartition("*")[2].rstrip(")") or e.path.suffix)
        if not ops.lossless(e.path, dest) and not ops.writable(dest.suffix):
            self.say(
                tr("grimoire.spells.viewl.page", "{ext} files can't be written here; pick PNG or JPEG").format(
                    ext=dest.suffix
                )
            )
            return False
        orient, src = self.orient, e.path
        self._run("saved_as", lambda: ops.save_turned(src, orient, dest) if orient != 1 else ops.save_copy(src, dest))
        self.orient = 1
        self.canvas.set_orient(1)
        self._update_pending()
        return True

    # ---------------------------------------------------------------- other actions
    def _run(self, kind: str, fn):
        """A file change on a worker; _done() gets (kind, result or OSError text)."""
        self._busy = True
        sig = self.sig

        def work():
            try:
                return kind, fn()
            except Exception as err:  # anything else would leave _busy set and every later change refused
                return kind, err

        POOL.start(Job(work, lambda r: sig.done.emit(r)))

    def _done(self, result):
        kind, value = result
        self._busy = False
        self._update_pending()
        if isinstance(value, Exception):
            self.say(
                tr("grimoire.spells.viewl.page", "That didn't work: {error}").format(
                    error=str(value) or type(value).__name__
                )
            )
            if kind == "saved" and self.current():  # show the file as it really is again
                self._pending_select, self._pending_view = self.current().path, self.mode == "view"
            self.rescan()
            return
        if kind in ("saved", "saved_as"):
            self.decoder.forget(str(value))
            self.pix.pop(str(value), None)
            self.failed.discard(str(value))
            self.say(tr("grimoire.spells.viewl.page", "Saved {name}").format(name=isolate(Path(value).name)))
            self._pending_select, self._pending_view = Path(value), self.mode == "view"  # reload / go to it
            self.rescan()
        elif kind == "trashed":
            if value:
                self.say("\n".join(value))
            self.rescan()
        elif kind == "renamed":
            self._pending_select, self._pending_view = Path(value), self.mode == "view"
            self.rescan()
        elif kind == "transfer":
            done, errors, move = value
            text = (
                tr("grimoire.spells.viewl.page", "Moved %n picture(s)", n=done)
                if move
                else tr("grimoire.spells.viewl.page", "Copied %n picture(s)", n=done)
            )
            self.say("\n".join([text] + errors[:4]))
            self.rescan()
        elif kind == "wallpaper":
            self.say(tr("grimoire.spells.viewl.page", "Set as your wallpaper. It's in MuraL's library too."))

    def say(self, text: str):
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start()

    def copy(self):
        paths = self.current_paths()
        if not paths:
            return
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
        if self.mode == "view" and self.canvas.full and not self.canvas.full.isNull():
            img = self.canvas.full.toImage()
            if self.orient != 1:
                a, b, c, d = exif.ORIENT[self.orient]
                img = img.transformed(QTransform(a, c, b, d, 0, 0))
            data.setImageData(img)  # paste into a chat or an editor gets the pixels
        QGuiApplication.clipboard().setMimeData(data)
        self.say(
            tr("grimoire.spells.viewl.page", "Copied")
            if self.mode == "view"
            else tr("grimoire.spells.viewl.page", "Copied %n file(s)", n=len(paths))
        )

    def trash(self):
        paths = self.current_paths()
        if not paths or self._busy:
            return
        if self.mode == "view":
            self.orient = 1  # nothing to save on a picture that's going
            e = self.current()
            self.images.pop(self.cur)
            self.strip_model.set(self.images)
            if self.images:
                self.show_image(min(self.cur, len(self.images) - 1), ask=False)
            else:
                self.cur = -1
                self._set_mode("browse")
            self.say(tr("grimoire.spells.viewl.page", "Moved {name} to the Trash").format(name=isolate(e.name)))
        else:
            self.say(tr("grimoire.spells.viewl.page", "Moved %n picture(s) to the Trash", n=len(paths)))
        self._run("trashed", lambda: ops.to_trash(paths))

    def rename(self):
        paths = self.current_paths()
        if len(paths) != 1 or self._busy or not self.settle():
            return
        p = paths[0]
        dlg = RenameDialog(self, p.name)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name = dlg.edit.text()
        self.decoder.forget(str(p))
        self._run("renamed", lambda: ops.rename(p, name))

    def transfer(self, move: bool):
        paths = self.current_paths()
        if not paths or self._busy or not self.settle():
            return
        title = (
            tr("grimoire.spells.viewl.page", "Move to a folder")
            if move
            else tr("grimoire.spells.viewl.page", "Copy to a folder")
        )
        d = QFileDialog.getExistingDirectory(self, title, str(self.folder or Path.home()))
        if not d:
            return
        dest = Path(d)
        self._run("transfer", lambda: (*ops.transfer(paths, dest, move), move))

    def set_wallpaper(self):
        paths = self.current_paths()
        if len(paths) != 1:
            return
        p = paths[0]
        box = QMessageBox(
            QMessageBox.Icon.NoIcon,
            "ViewL",
            tr("grimoire.spells.viewl.page", "Make {name} the wallpaper on every desktop?").format(
                name=isolate(p.name)
            ),
            parent=self,
        )
        box.setTextFormat(Qt.TextFormat.PlainText)  # a file name like "<b>x</b>.jpg" is no markup
        box.setInformativeText(
            tr("grimoire.spells.viewl.page", "A copy goes into MuraL's library, so it stays even if this file moves.")
        )
        ok = box.addButton(tr("grimoire.spells.viewl.page", "Set as wallpaper"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(ok)
        box.exec()
        if box.clickedButton() is not ok:
            return
        orient = self.orient if self.mode == "view" else 1
        self._run("wallpaper", lambda: ops.set_wallpaper(p, orient))

    def show_in_vaultl(self, path: Path | None = None):
        paths = [path] if path else self.current_paths()
        target = paths[0] if paths else self.folder
        if target:
            QProcess.startDetached(str(command("grimoire-vaultl")), [str(target)])

    def edit(self):
        """Mark the picture up in ShotL's editor; it saves next to the original as "name (2).png"."""
        e = self.current()
        if not e:
            return
        d = self.decoder.get(self._key(e))
        if d is None or d.image.isNull():
            self.say(tr("grimoire.spells.viewl.page", "Still opening this picture; try again in a moment"))
            return
        try:
            from grimoire.spells.shotl.editor import Editor
        except ImportError as err:
            self.say(tr("grimoire.spells.viewl.page", "ShotL's editor isn't available: {error}").format(error=err))
            return
        img = d.image
        if self.orient != 1:
            a, b, c, dd = exif.ORIENT[self.orient]
            img = img.transformed(QTransform(a, c, b, dd, 0, 0))
        self.exit_fullscreen()
        win = EditorWindow(self.window())
        ed = Editor()
        ed.setContentsMargins(16, 12, 16, 8)
        ed.load(img, e.path)
        ed.closed.connect(win.close)
        ed.toast.connect(lambda t: win.statusBar().showMessage(t, 5000))
        ed.saved.connect(
            lambda p: (
                self.rescan(),
                self.say(tr("grimoire.spells.viewl.page", "Saved {name}").format(name=isolate(Path(p).name))),
            )
        )

        def took(new):
            ed.load(new)
            ed.canvas.setFocus()

        def new_shot(mode):
            from grimoire.spells.shotl import newshot

            newshot.run(win, mode, took, ed.toast.emit)

        ed.new_requested.connect(new_shot)
        win.ed = ed
        win.setCentralWidget(ed)
        win.setWindowTitle(f"{e.name} — ShotL")
        win.resize(min(1400, max(900, img.width() // 2 + 120)), min(900, max(600, img.height() // 2 + 180)))
        win.show()
        ed.canvas.setFocus()

    # ---------------------------------------------------------------- menus
    def _fill_menu(self, m: QMenu, paths: list[Path]):
        m.clear()
        one = len(paths) == 1
        view = self.mode == "view"
        if not paths:
            m.addAction(tr("grimoire.spells.viewl.page", "Nothing selected")).setEnabled(False)
            return
        if not view and one:
            m.addAction(
                tr("grimoire.spells.viewl.page", "Open"), lambda: self._grid_activated(self.grid.currentIndex())
            )
        m.addAction(glyph("copies", 16), tr("grimoire.spells.viewl.page", "Copy") + "\tCtrl+C", self.copy)
        if view:
            m.addAction(glyph("pencil", 16), tr("grimoire.spells.viewl.page", "Mark up in ShotL") + "\tE", self.edit)
        if one:
            m.addAction(glyph("desktop", 16), tr("grimoire.spells.viewl.page", "Set as wallpaper…"), self.set_wallpaper)
        m.addSeparator()
        if view:
            m.addAction(tr("grimoire.spells.viewl.page", "Save as…") + "\tCtrl+Shift+S", self.save_as)
        if one:
            m.addAction(tr("grimoire.spells.viewl.page", "Rename…") + "\tF2", self.rename)
        m.addAction(tr("grimoire.spells.viewl.page", "Copy to a folder…"), lambda: self.transfer(False))
        m.addAction(tr("grimoire.spells.viewl.page", "Move to a folder…"), lambda: self.transfer(True))
        m.addAction(glyph("vault", 16), tr("grimoire.spells.viewl.page", "Show in VaultL"), self.show_in_vaultl)
        m.addSeparator()
        m.addAction(glyph("trash", 16), tr("grimoire.spells.viewl.page", "Move to the Trash") + "\tDel", self.trash)

    def _grid_menu(self, pos):
        idx = self.grid.indexAt(pos)
        if idx.isValid() and not self.grid.selectionModel().isSelected(idx):
            self.grid.setCurrentIndex(idx)
        e = idx.data(Qt.ItemDataRole.UserRole) if idx.isValid() else None
        m = QMenu(self)
        if e is not None and e.is_dir:
            m.addAction(tr("grimoire.spells.viewl.page", "Open"), lambda: self.open_folder(e.path))
            m.addAction(
                glyph("vault", 16),
                tr("grimoire.spells.viewl.page", "Show in VaultL"),
                lambda: self.show_in_vaultl(e.path),
            )
        else:
            self._fill_menu(m, self.current_paths())
        m.exec(self.grid.viewport().mapToGlobal(pos))

    def _canvas_menu(self, pos):
        m = QMenu(self)
        self._fill_menu(m, self.current_paths())
        m.exec(self.canvas.mapToGlobal(pos))

    # ---------------------------------------------------------------- info
    def toggle_info(self):
        on = not self.s["info"]
        self.info.setVisible(on)
        self.info_btn.setChecked(on)
        self.s["info"] = on
        images.save(self.s)
        self._refresh_info()

    def _refresh_info(self):
        e = self.current()
        if not e or not self.s["info"]:  # (isVisible() is False until the view is on screen)
            return
        path, sig = e.path, self.sig
        POOL.start(Job(lambda: gather(path), lambda info: sig.info.emit(path, info)))

    def _info_ready(self, path: Path, info: dict):
        e = self.current()
        if e and e.path == path:
            self.info.show_info(info)

    # ---------------------------------------------------------------- full screen and slideshow
    def toggle_fullscreen(self):
        if self.full:
            self.exit_fullscreen()
        elif self.mode == "view":
            self.enter_fullscreen()

    def enter_fullscreen(self):
        if self.full or self.mode != "view":
            return
        self.full = FullWindow()
        for a in self.actions():
            self.full.addAction(a)
        self.full.closing.connect(self._full_closed)
        self.middle.removeWidget(self.canvas)
        self.full.layout().addWidget(self.canvas)
        self.canvas.black = True
        self.full.showFullScreen()
        self.canvas.setFocus()
        self._cursor_timer.start()

    def exit_fullscreen(self):
        if not self.full:
            return
        full, self.full = self.full, None
        full.closing.disconnect(self._full_closed)
        full.layout().removeWidget(self.canvas)
        self.middle.insertWidget(0, self.canvas, 1)
        self.canvas.black = False
        self.canvas.unsetCursor()
        self._cursor_timer.stop()
        full.hide()
        full.deleteLater()
        self.canvas.show()
        self.canvas.setFocus()
        if self.slide.isActive():
            self.stop_slideshow()

    def _full_closed(self):
        QTimer.singleShot(0, self.exit_fullscreen)

    def _hide_cursor(self):
        if self.full:
            self.canvas.setCursor(Qt.CursorShape.BlankCursor)

    def eventFilter(self, obj, ev):
        if obj is self.canvas and self.full and ev.type() == ev.Type.MouseMove:
            self.canvas.unsetCursor()
            self._cursor_timer.start()
        return False

    _slide_paused = False

    def start_slideshow(self):
        if self.mode != "view":
            sel = self.current_paths()
            i = next((n for n, e in enumerate(self.images) if sel and e.path == sel[0]), 0)
            if not self.images:
                return
            self.show_image(i)
            self._set_mode("view")
        if not self.settle():
            return
        self._slide_paused = False
        self.enter_fullscreen()
        self.slide.start(self.s["interval"] * 1000)
        self.canvas.flash(tr("grimoire.spells.viewl.page", "Slideshow · Space pauses · Esc stops"))

    def pause_slideshow(self):
        if self.slide.isActive():
            self.slide.stop()
            self._slide_paused = True
            self.canvas.flash(tr("grimoire.spells.viewl.page", "Paused · Space goes on"))
        elif self._slide_paused:
            self._slide_paused = False
            self.slide.start(self.s["interval"] * 1000)
            self.canvas.flash(tr("grimoire.spells.viewl.page", "Slideshow · Space pauses · Esc stops"))

    def stop_slideshow(self):
        self.slide.stop()
        self._slide_paused = False

    def _slide_next(self):
        if len(self.images) < 2:
            self.stop_slideshow()
            return
        if self.s["shuffle"]:
            n = random.choice([k for k in range(len(self.images)) if k != self.cur])
        else:
            n = (self.cur + 1) % len(self.images)  # round and round
        self.show_image(n, ask=False)

    def _set_interval(self, v: int):
        self.s["interval"] = v
        images.save(self.s)
        for a, sec in self.interval_actions:
            a.setChecked(sec == v)
        if self.slide.isActive():
            self.slide.start(v * 1000)

    def _set_shuffle(self, on: bool):
        self.s["shuffle"] = on
        images.save(self.s)

    # ---------------------------------------------------------------- drops and closing
    def dragEnterEvent(self, e):
        if (
            e.mimeData().hasUrls()
            and any(u.isLocalFile() for u in e.mimeData().urls())
            and e.source() not in (self.grid, self.strip)
        ):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.isLocalFile():
                self.open_path(Path(u.toLocalFile()))
                break

    def can_close(self) -> bool:
        return self.settle()

    def hideEvent(self, e):
        if self.slide.isActive() and not self.full:
            self.stop_slideshow()
        super().hideEvent(e)


class EditorWindow(QMainWindow):
    """ShotL's editor in its own window; closing asks about unsaved marks like ShotL does."""

    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Window)
        self.ed = None

    def closeEvent(self, e):
        if self.ed is None:
            return super().closeEvent(e)
        self.ed.blockSignals(True)
        ok = not self.ed.unsaved() or self.ed.request_close()
        self.ed.blockSignals(False)
        e.accept() if ok else e.ignore()
