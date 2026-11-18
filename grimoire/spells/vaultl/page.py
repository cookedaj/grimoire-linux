# SPDX-License-Identifier: GPL-3.0-or-later
"""VaultL: Grimoire's file manager with tidying built in (FileL and TidyL merged). Same system underneath
(the local filesystem via QFileSystemModel, the freedesktop Trash via gio, KDE-compatible clipboard), new black &
white interface. The sidebar's Tidy section swaps the file views for the tidy panels (tidyview.py), and the
watched Downloads folder gets a bar with Tidy now and Undo.

Shortcuts follow Dolphin: Alt+Left/Right/Up, Backspace, F2, Del, Ctrl+C/X/V, Ctrl+A, Ctrl+H, Ctrl+L, Ctrl+F,
Ctrl+Shift+N, F5, F4 (terminal here), Enter to open; plus Ctrl+Z (undo the last trash, move, copy, rename or new
folder), Ctrl+D (duplicate), Ctrl+N (new window), Ctrl+= / Ctrl+- / Ctrl+0 and Ctrl+wheel (icon size).
Drag files onto a folder, a place or a drive to move them (Ctrl: copy, Shift: move; across drives: copy).
The view (grid/details, hidden, preview, sort, icon size) and pinned places last between runs (prefs.py).
"""
import os
import stat
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import (QDir, QEvent, QItemSelectionModel, QMimeData, QMimeDatabase, QModelIndex,
                            QObject, QProcess, QRect, QRectF, QSize, QStorageInfo, Qt, QThreadPool, QTimer, QUrl,
                            Signal)
from PySide6.QtGui import (QAbstractFileIconProvider, QColor, QDesktopServices, QFont, QFontMetrics, QGuiApplication,
                           QIcon, QImage, QImageReader, QKeySequence, QPainter, QPainterPath, QPixmap, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QFileSystemModel, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                               QPushButton, QSplitter, QStackedWidget, QStyle, QStyledItemDelegate, QToolButton,
                               QTreeView, QVBoxLayout, QWidget)

from grimoire.fsutil import human, rename_noreplace, tilde
from grimoire.glyphs import glyph
from grimoire.i18n import isolate, tr, tr_noop
from grimoire.jobs import Job
from grimoire.paths import CACHE, HOME, command
from grimoire.spells.vaultl import archive, archiveview, launch, ops, prefs, runview
from grimoire.spells.vaultl.tidyview import PANELS, TidyPanel, ltr, when
from grimoire.widgets import no_mnemonic, plain_tip

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".avif", ".tif", ".tiff", ".svg"}
TEXT_EXT = {".txt", ".md", ".py", ".lua", ".luau", ".json", ".toml", ".yaml", ".yml", ".sh", ".ini", ".cfg",
            ".conf", ".log", ".csv", ".qml", ".js", ".ts", ".rs", ".c", ".h", ".cpp", ".html", ".css", ".xml"}
PLACES = [(tr_noop("grimoire.spells.vaultl.page", "Home"), "home", "~"),
          (tr_noop("grimoire.spells.vaultl.page", "Desktop"), "desktop", "~/Desktop"),
          (tr_noop("grimoire.spells.vaultl.page", "Repos"), "terminal", "~/Desktop/Repos"),
          (tr_noop("grimoire.spells.vaultl.page", "Documents"), "document", "~/Documents"),
          (tr_noop("grimoire.spells.vaultl.page", "Downloads"), "store", "~/Downloads"),
          (tr_noop("grimoire.spells.vaultl.page", "Pictures"), "mural", "~/Pictures"),
          (tr_noop("grimoire.spells.vaultl.page", "Videos"), "video", "~/Videos"),
          (tr_noop("grimoire.spells.vaultl.page", "Music"), "music", "~/Music"),
          (tr_noop("grimoire.spells.vaultl.page", "Trash"), "trash", str(ops.TRASH_FILES))]
THUMBS = QThreadPool()
EDIT_TRIGGERS = QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.SelectedClicked
THUMBS.setMaxThreadCount(3)
ICON = 72                                             # grid icon size before any zoom
THUMB_SIDE = 192                                      # thumbnails sharp up to the 96 px zoom, fine at 128
THUMB_CACHE = 800                                     # ~150 KB each: the newest 800 stay


class _Signals(QObject):
    thumb = Signal(str, QImage)
    transferred = Signal(int, list, bool, list)   # done, errors, moved (else copied), [(source, result)]
    trashed = Signal(int, list)
    sized = Signal(str, object, object, bool)     # sizes can exceed 32-bit ints; bool: counted to the end
    undone = Signal(str, list, bool)              # what was undone, errors, whether anything came back
    trashed_paths = Signal(list)                  # the originals that went to the Trash (for Undo)


def drop_moves(sources: list[Path], dest: Path, copy_asked: bool) -> bool:
    """Move or copy for a drop, like Dolphin without its menu: Ctrl copies, Shift moves, otherwise a move on the
    same drive and a copy onto another one (a USB stick keeps the original where it was)."""
    mods = QGuiApplication.keyboardModifiers()
    if mods & Qt.KeyboardModifier.ShiftModifier:
        return True
    if copy_asked or mods & Qt.KeyboardModifier.ControlModifier:
        return False
    try:
        dev = dest.stat().st_dev
        return all(src.lstat().st_dev == dev for src in sources)
    except OSError:
        return False


class GridDelegate(QStyledItemDelegate):
    """Icon-grid cells: rounded selection, real thumbnails for images (generated off the UI thread)."""

    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.cache: dict[str, QPixmap] = {}
        self.pending: set[str] = set()
        self.icon = ICON                                  # the grid's zoom (prefs.ICON_SIZES)

    def grid_size(self) -> QSize:
        return QSize(self.icon + 56, self.icon + 60)      # 72 → 128 x 132, the original grid

    def sizeHint(self, option, index):
        return self.grid_size()

    def paint(self, p: QPainter, option, index):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = option.rect.adjusted(4, 4, -4, -4)
        selected = option.state & QStyle.StateFlag.State_Selected
        hover = option.state & QStyle.StateFlag.State_MouseOver
        if selected or hover:
            path = QPainterPath()
            path.addRoundedRect(QRectF(r), 10, 10)
            p.fillPath(path, QColor("#232323" if selected else "#141414"))
        model: QFileSystemModel = index.model()
        fpath = model.filePath(index)
        size = self.icon
        icon_rect = QRect(r.center().x() - size // 2, r.y() + 8, size, size)
        pm = self._thumb(fpath) if Path(fpath).suffix.lower() in IMAGE_EXT else None
        if pm is not None:
            scaled = pm.scaled(icon_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(icon_rect.x() + (size - scaled.width()) // 2,
                         icon_rect.y() + (size - scaled.height()) // 2, scaled)
        elif model.isDir(index):
            glyph("folder", size).paint(p, icon_rect, mode=QIcon.Mode.Active if selected else QIcon.Mode.Normal)
        elif archive.is_archive(Path(fpath)):                 # zip, tar, 7z, rar: they open like folders here
            glyph("archive", size).paint(p, icon_rect, mode=QIcon.Mode.Active if selected else QIcon.Mode.Normal)
        else:
            icon = model.fileIcon(index)
            (icon if not icon.isNull() and icon.availableSizes() else glyph("document", size)).paint(p, icon_rect)
        p.setPen(QColor("#ffffff" if selected else "#d6d6d6"))
        f = QFont(option.font)
        p.setFont(f)
        fm = QFontMetrics(f)
        text_rect = QRect(r.x() + 4, icon_rect.bottom() + 6, r.width() - 8, fm.height() * 2 + 2)
        name = isolate(model.fileName(index))          # RTL: ".cache" must not read "cache."
        lines = fm.elidedText(name, Qt.TextElideMode.ElideMiddle, text_rect.width() * 2 - 12)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWrapAnywhere,
                   lines)
        p.restore()

    def _thumb(self, fpath: str) -> QPixmap | None:
        if fpath in self.cache:
            return self.cache[fpath]
        if fpath not in self.pending:
            self.pending.add(fpath)
            sig = self.page._sig

            def work():
                try:
                    if not stat.S_ISREG(os.stat(fpath).st_mode):     # a FIFO named .png would block forever
                        return QImage()
                except OSError:
                    return QImage()
                reader = QImageReader(fpath)
                reader.setAutoTransform(True)
                size = reader.size()
                if size.isValid():
                    reader.setScaledSize(size.scaled(QSize(THUMB_SIDE, THUMB_SIDE), Qt.AspectRatioMode.KeepAspectRatio))
                return reader.read()

            THUMBS.start(Job(work, lambda img: sig.thumb.emit(fpath, img)))
        return None

    def ready(self, fpath: str, img: QImage):
        self.pending.discard(fpath)
        if not img.isNull():
            self.cache[fpath] = QPixmap.fromImage(img)
            while len(self.cache) > THUMB_CACHE:              # forget the oldest, not every photo seen
                del self.cache[next(iter(self.cache))]
            self.page.grid.viewport().update()


class NameDelegate(QStyledItemDelegate):
    """Details view text laid out on its own, so an RTL UI doesn't move ".cache"'s dot to the end (names: by their
    first letter) or turn "13 Nov 2026 17:55" and "0 bytes" around (sizes and dates: left to right). Only the painted
    text: editing and type-to-find keep the plain name."""

    def __init__(self, parent, as_ltr=False):
        super().__init__(parent)
        self.as_ltr = as_ltr

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.text = ltr(option.text) if self.as_ltr and option.text else isolate(option.text)


class TypeNames(QAbstractFileIconProvider):
    """The Type column in the user's language: Qt's own names ("Folder", "png File") have no translations, the
    shared-mime-info comments ("PNG image", "صورة PNG") do. Matched by name only (no file is opened) since
    QFileSystemModel asks from its gatherer thread for every file; sorting by Type follows the same names."""

    def __init__(self):
        super().__init__()
        self.mimes = QMimeDatabase()
        self.folder = tr("grimoire.spells.vaultl.page", "Folder")

    def type(self, info):
        if info.isDir():
            return self.folder
        mime = self.mimes.mimeTypeForFile(info.fileName(), QMimeDatabase.MatchMode.MatchExtension)
        return super().type(info) if mime.isDefault() else mime.comment()     # unknown: Qt's "xyz File" names it


class FileModel(QFileSystemModel):
    """QFileSystemModel whose drag & drop respects the Trash: a drop into it goes through gio trash (so the item
    gets its .trashinfo and Restore can put it back), and nothing is moved out of or around inside it (that
    would orphan the records; Restore and Delete forever are the ways out). Other copies and moves go through
    ops.transfer like Paste: Qt's own drop silently fails on a name clash, a folder copy or a move to
    another drive."""
    trash_drop = Signal(list)
    transfer_drop = Signal(list, str, bool)           # sources, destination folder, move
    refused = Signal(str)

    def dropMimeData(self, data, action, row, column, parent):
        dest = Path(self.filePath(parent)) if parent.isValid() else None
        sources = [Path(u.toLocalFile()) for u in data.urls() if u.isLocalFile()]
        loose = [p for p in sources if not ops.in_trash(p)]
        if dest is not None and ops.in_trash(dest):
            if loose:
                self.trash_drop.emit(loose)
            else:
                self.refused.emit(tr("grimoire.spells.vaultl.page",
                                     "Items in the Trash stay where they are. Use Restore to put them back."))
            return False                              # gio trash did the move; the view has nothing to do
        if len(loose) != len(sources):
            self.refused.emit(tr("grimoire.spells.vaultl.page",
                                 "Items in the Trash can't be dragged out. Use Restore to put them back."))
            return False
        if action in (Qt.DropAction.CopyAction, Qt.DropAction.MoveAction) and dest is not None:
            if sources and dest.is_dir():
                self.transfer_drop.emit(sources, str(dest),
                                        drop_moves(sources, dest, action == Qt.DropAction.CopyAction))
            return False                              # ops.transfer does the work in the background
        return super().dropMimeData(data, action, row, column, parent)


class VaultLPage(QWidget):
    def __init__(self, start: str | Path | None = None, standalone: bool = False):
        super().__init__()
        self.setObjectName("Page")
        self._sig = _Signals()
        self.history: list[Path] = []
        self.hist_i = -1
        self.prefs = prefs.load()
        self.show_hidden = self.prefs["hidden"]
        self.undo_stack: list[tuple] = []                 # (kind, data, label), newest last
        self.standalone = standalone                      # own window: the title follows the folder
        self.cwd = HOME

        self.model = FileModel(self)
        self.type_names = TypeNames()                     # kept here: the model doesn't own its provider
        self.model.setIconProvider(self.type_names)
        self.model.trash_drop.connect(self._trash_paths)
        self.model.transfer_drop.connect(lambda srcs, dest, move: self._transfer(srcs, Path(dest), move))
        self.model.refused.connect(lambda msg: self._tell(msg))
        self.model.setRootPath("/")
        self.model.setReadOnly(False)                     # rename + drag & drop moves
        self.model.setNameFilterDisables(False)
        self._apply_filter()

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.tidy = TidyPanel()                           # before the sidebar: the Downloads bar reads its settings
        self.tidy.changed.connect(self._refresh_tidy_bar)
        self.tidy.reveal.connect(lambda p: self.reveal(Path(p)))
        root.addWidget(self._sidebar())

        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(18, 14, 18, 10)
        ml.setSpacing(10)
        ml.addLayout(self._toolbar())
        self.trash_bar = self._trash_bar()
        ml.addWidget(self.trash_bar)
        self.tidy_bar = self._tidy_bar()
        ml.addWidget(self.tidy_bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(1)
        self.views = QStackedWidget()
        self.grid = self._make_grid()
        self.details = self._make_details()
        self.views.addWidget(self.grid)
        self.views.addWidget(self.details)
        split.addWidget(self.views)
        self.preview = self._preview_pane()
        split.addWidget(self.preview)
        split.setStretchFactor(0, 1)
        split.setSizes([900, 280])
        ml.addWidget(split, 1)
        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setTextFormat(Qt.TextFormat.PlainText)     # file names and archive errors are anyone's
        self._hold = 0.0
        self._hold_timer = QTimer(self, singleShot=True, timeout=self._update_status)
        ml.addWidget(self.status)
        self.body = QStackedWidget()                      # 0: files, 1: tidy panels, 2: inside an archive
        self.body.addWidget(main)
        self.body.addWidget(self.tidy)
        self.jobs = archiveview.Jobs()                    # extract/compress progress, under whichever view shows
        self.archive_panel = archiveview.ArchivePanel(self.jobs)
        self.archive_panel.message.connect(self._say)
        self.archive_panel.leave.connect(self._leave_archive)
        self.body.addWidget(self.archive_panel)
        self.body.currentChanged.connect(self._body_changed)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self.body, 1)
        column.addWidget(self.jobs)
        root.addLayout(column, 1)

        self._sig.thumb.connect(self.grid_delegate.ready)
        self._sig.transferred.connect(self._transfer_done)
        self._sig.sized.connect(self._folder_sized)
        self._sig.trashed.connect(self._trash_done)
        self._sig.undone.connect(self._undone)
        self._sig.trashed_paths.connect(self._trashed)
        self.model.fileRenamed.connect(self._renamed)
        self.model.directoryLoaded.connect(lambda _: self._update_status())
        self._shortcuts()
        self._restore_prefs()
        self.navigate(Path(start).expanduser() if start else HOME)

    # ================================================================== layout
    def _sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("SubNav")
        side.setFixedWidth(200)
        v = QVBoxLayout(side)
        v.setContentsMargins(12, 18, 12, 14)
        v.setSpacing(4)
        title = QLabel("VaultL")
        title.setObjectName("Title")
        v.addWidget(title)
        v.addSpacing(10)
        label = QLabel(tr("grimoire.spells.vaultl.page", "PLACES"))
        label.setObjectName("NavSection")
        v.addWidget(label)
        self.places = QListWidget()
        self.places.setObjectName("Places")
        self.places.setIconSize(QSize(18, 18))
        self.places.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.places.itemClicked.connect(lambda it: self.navigate(Path(it.data(Qt.ItemDataRole.UserRole))))
        self._side_list(self.places)
        self._fill_places()
        v.addWidget(self.places)
        tl = QLabel(tr("grimoire.spells.vaultl.page", "TIDY"))
        tl.setObjectName("NavSection")
        v.addWidget(tl)
        self.tools = QListWidget()
        self.tools.setObjectName("Places")
        self.tools.setIconSize(QSize(18, 18))
        for i, (name, icon, _, _) in enumerate(PANELS):
            it = QListWidgetItem(glyph(icon, 18), tr("grimoire.spells.vaultl.tidyview", name))
            it.setData(Qt.ItemDataRole.UserRole, i)
            self.tools.addItem(it)
        self.tools.setFixedHeight(len(PANELS) * 36 + 4)
        self.tools.itemClicked.connect(lambda it: self.show_tidy(it.data(Qt.ItemDataRole.UserRole)))
        v.addWidget(self.tools)
        dl = QLabel(tr("grimoire.spells.vaultl.page", "DRIVES"))
        dl.setObjectName("NavSection")
        v.addWidget(dl)
        self.drives = QListWidget()
        self.drives.setObjectName("Places")
        self.drives.setIconSize(QSize(18, 18))
        self.drives.itemClicked.connect(lambda it: self.navigate(Path(it.data(Qt.ItemDataRole.UserRole))))
        self._side_list(self.drives)
        v.addWidget(self.drives, 1)                     # the drives take what's left (and scroll when many)
        self._fill_drives()
        return side

    def _side_list(self, lst: QListWidget):
        """Places and Drives: drop files on an entry to move them there (onto Trash: Move to Trash); right-click
        for Open in new window and pinning."""
        lst.setAcceptDrops(True)
        lst.viewport().setAcceptDrops(True)
        lst.viewport().installEventFilter(self)
        lst.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lst.customContextMenuRequested.connect(lambda pos, w=lst: self._side_menu(w, pos))

    def _fill_places(self):
        self.places.clear()
        rows = [(tr("grimoire.spells.vaultl.page", name), icon, Path(path).expanduser(), False)
                for name, icon, path in PLACES[:-1]]
        rows += [(Path(p).name or p, "folder", Path(p), True) for p in self.prefs["places"]]
        rows.append((tr("grimoire.spells.vaultl.page", PLACES[-1][0]), "trash", ops.TRASH_FILES, False))
        for name, icon, path, pinned in rows:
            if path.exists() or icon == "trash":        # e.g. no Repos folder: no shortcut
                it = QListWidgetItem(glyph(icon, 18), name)
                it.setData(Qt.ItemDataRole.UserRole, str(path))
                it.setData(Qt.ItemDataRole.UserRole + 1, pinned)
                if pinned:
                    it.setToolTip(plain_tip(tilde(path)))
                self.places.addItem(it)
        self.places.setFixedHeight(self.places.count() * 36 + 4)    # every place in view, Trash too: no inner scroll
        if hasattr(self, "cwd"):
            self._mark_place()

    def _mark_place(self):
        for i in range(self.places.count()):
            it = self.places.item(i)
            it.setSelected(Path(it.data(Qt.ItemDataRole.UserRole)) == self.cwd)

    def pin(self, path: Path):
        if str(path) not in self.prefs["places"]:
            self.prefs = prefs.update(places=[*prefs.load()["places"], str(path)][:prefs.MAX_PLACES])
            self._fill_places()

    def unpin(self, path: Path):
        self.prefs = prefs.update(places=[p for p in prefs.load()["places"] if p != str(path)])
        self._fill_places()

    def _side_menu(self, lst: QListWidget, pos):
        it = lst.itemAt(pos)
        if not it:
            return
        path = Path(it.data(Qt.ItemDataRole.UserRole))
        m = QMenu(self)
        m.addAction(tr("grimoire.spells.vaultl.page", "Open"), lambda: self.navigate(path))
        m.addAction(tr("grimoire.spells.vaultl.page", "Open in new window"), lambda: self.new_window(path))
        if it.data(Qt.ItemDataRole.UserRole + 1):
            m.addSeparator()
            m.addAction(tr("grimoire.spells.vaultl.page", "Remove from Places"), lambda: self.unpin(path))
        m.exec(lst.viewport().mapToGlobal(pos))

    def _fill_drives(self):
        self.drives.clear()
        seen = set()
        for vol in sorted(QStorageInfo.mountedVolumes(), key=lambda v: len(v.rootPath())):
            dev = bytes(vol.device()).decode(errors="ignore")
            root = vol.rootPath()
            cloud = bytes(vol.fileSystemType()) == b"fuse.rclone"      # CloudL's mounts (and any rclone mount)
            if not vol.isValid() or not vol.isReady() or not (dev.startswith("/dev/") or cloud) or "/snap" in root \
                    or root.startswith("/boot"):
                continue
            if dev in seen:                                  # same disk mounted twice (e.g. / and a subvolume)
                continue
            seen.add(dev)
            name = Path(root).name if cloud else vol.displayName() or Path(root).name
            if root == "/":
                name = tr("grimoire.spells.vaultl.page", "System")
            free = tr("grimoire.spells.vaultl.page", "{size} free").format(size=ltr(human(vol.bytesAvailable())))
            it = QListWidgetItem(glyph("cloud" if cloud else "drive", 18), f"{name}\n{free}")
            it.setData(Qt.ItemDataRole.UserRole, root)
            it.setToolTip(tr("grimoire.spells.vaultl.page", "{path}  ·  {free} free of {total}").format(
                path=ltr(root), free=ltr(human(vol.bytesAvailable())), total=ltr(human(vol.bytesTotal()))))
            self.drives.addItem(it)

    def _tool(self, icon, tip, slot, checkable=False) -> QToolButton:
        b = QToolButton()
        b.setObjectName("Tool")
        b.setIcon(glyph(icon, 18))
        b.setIconSize(QSize(18, 18))
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setAutoRaise(True)
        b.clicked.connect(slot)
        return b

    def _toolbar(self):
        bar = QHBoxLayout()
        bar.setSpacing(4)
        self.back_btn = self._tool("back", tr("grimoire.spells.vaultl.page", "Back (Alt+Left)"), self.back)
        self.fwd_btn = self._tool("forward", tr("grimoire.spells.vaultl.page", "Forward (Alt+Right)"), self.forward)
        self.up_btn = self._tool("up", tr("grimoire.spells.vaultl.page", "Up (Alt+Up)"), self.up)
        for b in (self.back_btn, self.fwd_btn, self.up_btn):
            bar.addWidget(b)
        bar.addSpacing(6)
        self.path_stack = QStackedWidget()
        self.path_stack.setFixedHeight(34)
        self.crumbs = QFrame()
        self.crumbs.setObjectName("Crumbs")
        self.crumb_lay = QHBoxLayout(self.crumbs)
        self.crumb_lay.setContentsMargins(6, 0, 6, 0)
        self.crumb_lay.setSpacing(0)
        self.path_edit = QLineEdit()
        self.path_edit.returnPressed.connect(self._path_entered)
        self.path_edit.editingFinished.connect(lambda: self.path_stack.setCurrentIndex(0))
        self.path_stack.addWidget(self.crumbs)
        self.path_stack.addWidget(self.path_edit)
        self.crumbs.mouseDoubleClickEvent = lambda e: self.edit_path()
        bar.addWidget(self.path_stack, 1)
        bar.addSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.vaultl.page", "Search this folder"))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(glyph("search", 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(self._filter_names)
        bar.addWidget(self.search)
        bar.addSpacing(6)
        self.new_btn = self._tool("newfolder", tr("grimoire.spells.vaultl.page", "New folder (Ctrl+Shift+N)"),
                                  self.new_folder)
        self.grid_btn = self._tool("grid", tr("grimoire.spells.vaultl.page", "Grid"), lambda: self.set_view(0), True)
        self.list_btn = self._tool("list", tr("grimoire.spells.vaultl.page", "Details"), lambda: self.set_view(1), True)
        self.hidden_btn = self._tool("hidden", tr("grimoire.spells.vaultl.page", "Show hidden files (Ctrl+H)"),
                                     self.toggle_hidden, True)
        self.prev_btn = self._tool("preview", tr("grimoire.spells.vaultl.page", "Preview panel (F11)"),
                                   self.toggle_preview, True)
        self.prev_btn.setChecked(True)
        for b in (self.new_btn, self.grid_btn, self.list_btn, self.hidden_btn, self.prev_btn):
            bar.addWidget(b)
        self.grid_btn.setChecked(True)
        return bar

    def _trash_bar(self) -> QWidget:
        w = QFrame()
        w.setObjectName("Card")
        h = QHBoxLayout(w)
        h.setContentsMargins(14, 8, 8, 8)
        t = QLabel(tr("grimoire.spells.vaultl.page", "Trash · items here can be restored to where they came from"))
        t.setObjectName("Muted")
        t.setWordWrap(True)
        h.addWidget(t, 1)
        restore = QPushButton(tr("grimoire.spells.vaultl.page", "Restore selected"))
        restore.clicked.connect(self.restore_selected)
        empty = QPushButton(tr("grimoire.spells.vaultl.page", "Empty Trash…"))
        empty.clicked.connect(self.empty_trash)
        h.addWidget(restore)
        h.addWidget(empty)
        w.hide()
        return w

    def _tidy_bar(self) -> QWidget:
        """Shown while browsing the folder auto-tidy watches (Downloads)."""
        w = QFrame()
        w.setObjectName("Card")
        h = QHBoxLayout(w)
        h.setContentsMargins(14, 8, 8, 8)
        icon = QLabel()
        icon.setPixmap(glyph("tidy", 18).pixmap(18, 18))
        h.addWidget(icon)
        self.tidy_note = QLabel()
        self.tidy_note.setTextFormat(Qt.TextFormat.PlainText)
        self.tidy_note.setObjectName("Muted")
        self.tidy_note.setWordWrap(True)
        h.addWidget(self.tidy_note, 1)
        for text, slot in ((tr("grimoire.spells.vaultl.page", "Undo last tidy"), self.tidy.undo),
                           (tr("grimoire.spells.vaultl.page", "Tidy now"), self.tidy.tidy_now),
                           (tr("grimoire.spells.vaultl.page", "Rules"), lambda: self.show_tidy(0))):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, slot=slot: self._tidy_action(slot))
            h.addWidget(b)
        w.hide()
        return w

    def _tidy_action(self, slot):
        msg = slot()
        if isinstance(msg, str):
            self._tell(msg)

    def _refresh_tidy_bar(self):
        watched = self.body.currentIndex() == 0 and self.cwd == self.tidy.watch_dir()
        self.tidy_bar.setVisible(watched)
        if watched:
            self.tidy_note.setText(tr("grimoire.spells.vaultl.page",
                                      "Auto-tidy is on for this folder · new downloads get sorted by type")
                                   if self.tidy.auto_on
                                   else tr("grimoire.spells.vaultl.page",
                                           "Auto-tidy is paused for this folder · new downloads get sorted by type"))

    def _common_view(self, view: QAbstractItemView):
        view.setModel(self.model)
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setDragEnabled(True)
        view.setAcceptDrops(True)
        view.setDropIndicatorShown(True)
        view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        view.setDefaultDropAction(Qt.DropAction.MoveAction)
        view.setEditTriggers(EDIT_TRIGGERS)
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        view.customContextMenuRequested.connect(lambda pos, v=view: self._menu(v, pos))
        view.activated.connect(self.open_index)
        view.setFrameShape(QFrame.Shape.NoFrame)

    def _make_grid(self) -> QListView:
        g = QListView()
        g.setObjectName("FileGrid")
        g.setViewMode(QListView.ViewMode.IconMode)
        g.setResizeMode(QListView.ResizeMode.Adjust)
        g.setMovement(QListView.Movement.Snap)
        self.grid_delegate = GridDelegate(self)
        g.setGridSize(self.grid_delegate.grid_size())
        g.setUniformItemSizes(True)
        g.setWordWrap(True)
        g.setMouseTracking(True)
        g.setSpacing(4)
        g.setItemDelegate(self.grid_delegate)
        g.viewport().installEventFilter(self)             # Ctrl+wheel zooms
        self._common_view(g)
        g.setMovement(QListView.Movement.Static)
        return g

    def _make_details(self) -> QTreeView:
        t = QTreeView()
        t.setObjectName("FileDetails")
        self._common_view(t)
        t.setRootIsDecorated(False)
        t.setItemsExpandable(False)
        t.setUniformRowHeights(True)
        t.setSortingEnabled(True)
        t.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        t.setIconSize(QSize(20, 20))
        t.setAlternatingRowColors(False)
        t.setItemDelegateForColumn(0, NameDelegate(t))
        if self.isRightToLeft():
            for c in (1, 3):                                  # size, date modified
                t.setItemDelegateForColumn(c, NameDelegate(t, as_ltr=True))
        h = t.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c, w in ((1, 100), (2, 150), (3, 170)):
            t.setColumnWidth(c, w)
        return t

    def _preview_pane(self) -> QWidget:
        w = QFrame()
        w.setObjectName("Panel")
        w.setMinimumWidth(240)
        v = QVBoxLayout(w)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(10)
        self.pv_image = QLabel()
        self.pv_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pv_image.setMinimumHeight(180)
        self.pv_text = QLabel()
        self.pv_text.setObjectName("Mono")
        self.pv_text.setWordWrap(True)
        self.pv_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.pv_name = QLabel()
        self.pv_name.setObjectName("Section")
        self.pv_name.setWordWrap(True)
        self.pv_info = QLabel()
        self.pv_info.setObjectName("Muted")
        self.pv_info.setWordWrap(True)
        self.pv_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        for x in (self.pv_image, self.pv_text, self.pv_name, self.pv_info):
            v.addWidget(x)
        for x in (self.pv_text, self.pv_name, self.pv_info):
            x.setTextFormat(Qt.TextFormat.PlainText)            # a file named <h1>… or holding HTML stays text
        self.pv_text.hide()
        v.addStretch(1)
        self.pv_open = QPushButton(tr("grimoire.spells.vaultl.page", "Open"))
        self.pv_open.setObjectName("Primary")
        self.pv_open.clicked.connect(lambda: [self.open_path(p) for p in self.selected()[:1]])
        v.addWidget(self.pv_open)
        return w

    # ================================================================== navigation
    def view(self) -> QAbstractItemView:
        return self.views.currentWidget()

    def navigate(self, path: Path, record=True):
        path = Path(path)
        if not path.is_dir():
            self._tell(tr("grimoire.spells.vaultl.page", "Can't open {path}").format(path=ltr(tilde(path))))
            return
        self.cwd = path
        try:                                              # TerminalL's "New tab in VaultL's folder" reads this
            (CACHE / "vaultl-folder").write_text(str(path))
        except OSError:
            pass
        self.body.setCurrentIndex(0)
        self.tools.clearSelection()
        if record:
            del self.history[self.hist_i + 1:]
            self.history.append(path)
            self.hist_i = len(self.history) - 1
        if self.search.text():
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
            self.model.setNameFilters([])
        self._apply_filter()
        idx = self.model.index(str(path))
        for v in (self.grid, self.details):
            v.setRootIndex(idx)
            v.clearSelection()
        self._crumbs()
        self.back_btn.setEnabled(self.hist_i > 0)
        self.fwd_btn.setEnabled(self.hist_i < len(self.history) - 1)
        self.up_btn.setEnabled(path != path.parent)
        trash = ops.in_trash(path)
        self.trash_bar.setVisible(trash)
        for v in (self.grid, self.details):           # in the Trash: no dragging out, no renaming (Restore instead)
            v.setDragEnabled(not trash)
            v.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers if trash else EDIT_TRIGGERS)
        self._refresh_tidy_bar()
        self._mark_place()
        self._update_preview()
        self._update_status()
        self._update_title()

    def _update_title(self):
        if self.standalone and self.window() is not self:
            where = self.tidy.title.text() if self.body.currentIndex() == 1 else (self.cwd.name or str(self.cwd))
            if self.body.currentIndex() == 2 and self.archive_panel.path:
                where = self.archive_panel.path.name
            self.window().setWindowTitle(f"{where} — VaultL")

    def show_tidy(self, i: int):
        self.body.setCurrentIndex(1)
        self.tidy.show_panel(i)
        self.tidy.refresh_auto()
        self.places.clearSelection()
        self.tools.setCurrentRow(i)
        self._update_title()

    # ================================================================== archives (archiveview.py)
    def open_archive(self, p: Path):
        """Browse inside an archive like a folder; Back or Up at its top returns here."""
        self.body.setCurrentIndex(2)
        self.places.clearSelection()
        self.tools.clearSelection()
        self.archive_panel.open(p)
        self._update_title()

    def _leave_archive(self):
        p = self.archive_panel.path
        self.body.setCurrentIndex(0)
        self._update_title()
        if p is not None and p.parent == self.cwd:
            idx = self.model.index(str(p))
            if idx.isValid():
                self.view().setCurrentIndex(idx)
        self.view().setFocus()

    def _body_changed(self, i: int):
        if i != 2:
            self.archive_panel.close_archive()

    def _say(self, msg: str):
        (self.archive_panel.status if self.body.currentIndex() == 2 else self.status).setText(msg)

    def extract_selected(self, ask=False):
        archives = [p for p in self.selected() if p.is_file() and archive.is_archive(p)]
        if not archives:
            return
        dest = None
        if ask:
            d = QFileDialog.getExistingDirectory(self, tr("grimoire.spells.vaultl.page", "Extract to"), str(self.cwd))
            if not d:
                return
            dest = Path(d)
        archiveview.extract_files(self, archives, dest)

    def compress_selected(self):
        archiveview.compress(self, self.selected())

    def reveal(self, path: Path):
        """Open path's folder in the file views with path selected."""
        self.navigate(path.parent)
        QTimer.singleShot(200, lambda: self.view().setCurrentIndex(self.model.index(str(path))))

    def back(self):
        if self.hist_i > 0:
            came_from = self.cwd
            self.hist_i -= 1
            self.navigate(self.history[self.hist_i], record=False)
            self._select_when_listed(came_from)

    def forward(self):
        if self.hist_i < len(self.history) - 1:
            self.hist_i += 1
            self.navigate(self.history[self.hist_i], record=False)

    def up(self):
        if self.cwd != self.cwd.parent:
            came_from = self.cwd
            self.navigate(self.cwd.parent)
            self._select_when_listed(came_from)

    def _select_when_listed(self, path: Path, tries: int = 20):
        """Up/Back: the folder you came out of is selected, so Enter goes straight back in (as in Dolphin).
        QFileSystemModel lists in the background, so wait for the row."""
        if path.parent != self.cwd:
            return
        if self.model.index(str(path)).isValid():
            self._select([path])
        elif tries:
            QTimer.singleShot(50, lambda: self._select_when_listed(path, tries - 1))

    def _crumbs(self):
        while self.crumb_lay.count():
            w = self.crumb_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        parts = []
        p = self.cwd
        while True:
            parts.append(p)
            if p == HOME or p == p.parent:
                break
            p = p.parent
        for i, part in enumerate(reversed(parts)):
            label = "/" if part == part.parent else part.name
            if part == HOME:
                label = tr("grimoire.spells.vaultl.page", "Home")
            if part == ops.TRASH_FILES:
                label = tr("grimoire.spells.vaultl.page", "Trash")
            b = QPushButton(no_mnemonic(isolate(label)))                  # RTL: ".cache" keeps its dot in front
            b.setObjectName("Crumb")
            b.setFlat(True)
            b.clicked.connect(lambda _=False, part=part: self.navigate(part))
            if i:
                sep = QLabel("‹" if self.isRightToLeft() else "›")    # points along the reading direction
                sep.setObjectName("Muted")
                self.crumb_lay.addWidget(sep)
            self.crumb_lay.addWidget(b)
        self.crumb_lay.addStretch(1)

    def edit_path(self):
        self.path_edit.setText(str(self.cwd))
        self.path_stack.setCurrentIndex(1)
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def _path_entered(self):
        p = Path(self.path_edit.text().strip()).expanduser()
        self.path_stack.setCurrentIndex(0)
        if p.is_dir():
            self.navigate(p)
        elif p.exists():
            self.navigate(p.parent)
            self.open_path(p)
        else:
            self._tell(tr("grimoire.spells.vaultl.page", "No such folder: {path}").format(path=ltr(tilde(p))))

    # ================================================================== view options
    def set_view(self, i: int, save=True):
        keep = self.selected()                            # the same items stay selected in the other view
        self.views.setCurrentIndex(i)
        self.grid_btn.setChecked(i == 0)
        self.list_btn.setChecked(i == 1)
        self.view().setRootIndex(self.model.index(str(self.cwd)))
        self._select(keep)
        if save:
            self.prefs = prefs.update(view=i)

    def _select(self, paths: list[Path]):
        view = self.view()
        sm = view.selectionModel()
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        sm.clearSelection()
        for n, p in enumerate(paths):
            idx = self.model.index(str(p))
            if idx.isValid():
                sm.select(idx, flags)
                if n == 0:
                    view.setCurrentIndex(idx)
                    view.scrollTo(idx)

    def _apply_filter(self):
        """Hidden files show when asked, and always inside a hidden folder (the Trash is under ~/.local): once
        ~ is listed without them, QFileSystemModel can't reach a path below a hidden folder at all."""
        f = QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs
        if self.show_hidden or any(part.startswith(".") for part in self.cwd.parts):
            f |= QDir.Filter.Hidden
        if f != self.model.filter():
            self.model.setFilter(f)
            if hasattr(self, "details"):                  # re-filter now, not on the next event loop pass
                hh = self.details.header()
                self.model.sort(hh.sortIndicatorSection(), hh.sortIndicatorOrder())

    def toggle_hidden(self):
        self.show_hidden = not self.show_hidden
        self.hidden_btn.setChecked(self.show_hidden)
        self._apply_filter()
        self.prefs = prefs.update(hidden=self.show_hidden)

    def toggle_preview(self):
        self.preview.setVisible(not self.preview.isVisible())
        self.prev_btn.setChecked(self.preview.isVisible())
        self.prefs = prefs.update(preview=self.preview.isVisible())
        self._update_preview()

    def _filter_names(self, text: str):
        self.model.setNameFilters([f"*{text}*"] if text else [])

    # ================================================================== selection / preview / status
    def selected(self) -> list[Path]:
        sm = self.view().selectionModel()
        rows = sm.selectedRows(0) if isinstance(self.view(), QTreeView) else sm.selectedIndexes()
        return [Path(self.model.filePath(i)) for i in rows]

    def _connect_selection(self):
        for v in (self.grid, self.details):
            v.selectionModel().selectionChanged.connect(lambda *_: (self._update_preview(), self._update_status()))

    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_sel_hooked", False):
            self._sel_hooked = True
            self._connect_selection()
        QTimer.singleShot(0, self._update_preview)      # the panel was hidden until now
        self._update_title()                            # the first folder opened before we had a window

    def _update_preview(self):
        if not self.preview.isVisible():
            return
        sel = self.selected()
        p = sel[0] if len(sel) == 1 else self.cwd
        self.pv_image.clear()
        self.pv_text.clear()
        self.pv_text.hide()
        self.pv_open.setVisible(len(sel) == 1)
        try:
            st = p.stat()
        except OSError:
            return
        self.pv_name.setText(p.name or str(p))
        lines = []
        if p.is_dir():
            try:
                n = sum(1 for _ in p.iterdir())
                lines.append(tr("grimoire.spells.vaultl.page", "Folder · %n item(s)", n=n))
            except OSError:                               # e.g. a folder you can't read
                lines.append(tr("grimoire.spells.vaultl.page", "Folder · can't read its contents"))
            self.pv_image.setPixmap(glyph("folder", 96).pixmap(96, 96, QIcon.Mode.Active))
            sig = self._sig
            THUMBS.start(Job(lambda p=p: ops.folder_size(p), lambda r, p=p: sig.sized.emit(str(p), *r)))
        else:
            lines.append(f"{ltr(human(st.st_size))} · {self.model.type(self.model.index(str(p)))}")
            ext = p.suffix.lower() if stat.S_ISREG(st.st_mode) else ""   # reading a FIFO/device would hang the UI
            if ext in IMAGE_EXT:
                reader = QImageReader(str(p))
                reader.setAutoTransform(True)
                if reader.size().isValid():
                    lines.append(f"{reader.size().width()} × {reader.size().height()}")
                    reader.setScaledSize(reader.size().scaled(QSize(240, 240), Qt.AspectRatioMode.KeepAspectRatio))
                img = reader.read()
                if not img.isNull():
                    self.pv_image.setPixmap(QPixmap.fromImage(img))
            elif ext in TEXT_EXT and st.st_size < 2_000_000:
                try:
                    head = p.read_text(errors="replace")[:1500]
                except OSError:
                    head = ""
                self.pv_text.setText(head)
                self.pv_text.show()
                self.pv_image.setPixmap(self.model.fileIcon(self.model.index(str(p))).pixmap(56, 56))
            elif archive.is_archive(p):
                self.pv_image.setPixmap(glyph("archive", 96).pixmap(96, 96, QIcon.Mode.Active))
            else:
                self.pv_image.setPixmap(self.model.fileIcon(self.model.index(str(p))).pixmap(96, 96))
        if ops.in_trash(p) and p != ops.TRASH_FILES:
            orig = ops.original_location(p)
            if orig:
                lines.append(tr("grimoire.spells.vaultl.page",
                                "Was in {folder}").format(folder=ltr(tilde(Path(orig).parent))))
        lines.append(tr("grimoire.spells.vaultl.page", "Modified {when}").format(when=when(st.st_mtime)))
        lines.append(ltr(tilde(p)))
        self._pv_lines = lines
        self.pv_info.setText("\n".join(lines))
        self._pv_path = str(p)

    def _folder_sized(self, path: str, size: int, files: int, complete: bool):
        """Folder sizes are counted off the UI thread; fill them into the preview when ready. A count cut short
        (huge folder, or "/") shows as "about N+"; a folder that can't be sized (/proc…) shows none."""
        if getattr(self, "_pv_path", None) == path and self._pv_lines and (complete or files):
            lines = list(self._pv_lines)
            lines[0] += " · " + (ltr(human(size)) if complete else tr("grimoire.spells.vaultl.page",
                                                                 "about {size}+").format(size=ltr(human(size))))
            self.pv_info.setText("\n".join(lines))

    def _update_status(self):
        root = self.view().rootIndex()
        n = self.model.rowCount(root)
        sel = self.selected()
        free = QStorageInfo(str(self.cwd)).bytesAvailable()
        text = tr("grimoire.spells.vaultl.page", "%n item(s)", n=n)
        if sel:
            size = 0
            for p in sel:
                try:
                    size += p.stat().st_size if p.is_file() else 0
                except OSError:                           # deleted since it was selected
                    pass
            text += "   ·   " + (tr("grimoire.spells.vaultl.page",
                                    "%n selected ({size})", n=len(sel)).format(size=ltr(human(size))) if size
                                 else tr("grimoire.spells.vaultl.page", "%n selected", n=len(sel)))
        text += "   ·   " + tr("grimoire.spells.vaultl.page", "{size} free").format(size=ltr(human(free)))
        wait = self._hold - time.monotonic()
        if wait > 0:                                      # a message ("Moved 3 items.") stays readable first
            self._hold_timer.start(int(wait * 1000) + 50)
            return
        self.status.setText(text)

    def _tell(self, msg: str):
        """A result or problem in the status line, kept for a few seconds before the item counts come back."""
        self.status.setText(msg)
        self._hold = time.monotonic() + 4

    # ================================================================== actions
    def open_index(self, index: QModelIndex):
        self.open_path(Path(self.model.filePath(index)))

    def open_path(self, p: Path):
        """Folders open here; programs, scripts and launchers get a question first (runview.py: KIO refuses to
        start executables we hand it); everything else opens in its usual app."""
        if runview.open_program(self, p, self.status.setText, self.navigate):
            return
        if p.is_file() and archive.is_archive(p) and not ops.in_trash(p):
            self.open_archive(p)
        elif p.is_dir():
            self.navigate(p)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def new_folder(self):
        try:
            made = ops.new_folder(self.cwd, tr("grimoire.spells.vaultl.page", "New Folder"))
        except OSError as e:
            self._tell(tr("grimoire.spells.vaultl.page",
                                   "Couldn't create a folder: {error}").format(error=e.strerror or e))
            return
        self._remember("new", [made], tr("grimoire.spells.vaultl.page", "New folder"))
        QTimer.singleShot(150, lambda: self._edit_new(made))

    def _edit_new(self, made: Path):
        idx = self.model.index(str(made))
        if idx.isValid():
            self.view().setCurrentIndex(idx)
            self.view().edit(idx)

    def rename(self):
        if ops.in_trash(self.cwd):
            self._tell(tr("grimoire.spells.vaultl.page",
                                   "Items in the Trash can't be renamed. Restore them first."))
            return
        sel = self.selected()
        if len(sel) == 1:
            self.view().edit(self.model.index(str(sel[0])))
        elif len(sel) > 1:
            self._tell(tr("grimoire.spells.vaultl.page", "Pick a single item to rename."))

    def copy(self, cut=False):
        sel = self.selected()
        if not sel:
            return
        if cut and any(ops.in_trash(p) for p in sel):     # a cut-paste would leave the .trashinfo behind
            self._tell(tr("grimoire.spells.vaultl.page",
                                   "Items in the Trash can only be restored or deleted forever."))
            return
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(p)) for p in sel])
        data.setData("application/x-kde-cutselection", b"1" if cut else b"0")   # understood by Dolphin too
        QGuiApplication.clipboard().setMimeData(data)
        self._tell(tr("grimoire.spells.vaultl.page", "Cut %n item(s)", n=len(sel)) if cut
                            else tr("grimoire.spells.vaultl.page", "Copied %n item(s)", n=len(sel)))

    def paste(self):
        data = QGuiApplication.clipboard().mimeData()
        if not data or not data.hasUrls():
            return
        if ops.in_trash(self.cwd):
            self._tell(tr("grimoire.spells.vaultl.page",
                                   "Can't paste into the Trash. Use Move to Trash instead."))
            return
        sources = [Path(u.toLocalFile()) for u in data.urls() if u.isLocalFile()]
        move = bytes(data.data("application/x-kde-cutselection")) == b"1"
        self._transfer(sources, self.cwd, move)
        if move:
            QGuiApplication.clipboard().clear()

    def _transfer(self, sources: list[Path], dest: Path, move: bool):
        """Paste and drag & drop: copy or move in the background, never over an existing name."""
        sig = self._sig
        self._tell(tr("grimoire.spells.vaultl.page", "Moving %n item(s)…", n=len(sources)) if move
                            else tr("grimoire.spells.vaultl.page", "Copying %n item(s)…", n=len(sources)))
        made: list = []
        THUMBS.start(Job(lambda: ops.transfer(sources, dest, move, made=made),
                          lambda r: sig.transferred.emit(r[0], r[1], move, made)))

    def _transfer_done(self, done: int, errors: list, moved: bool, made: list):
        if made:
            self._remember("move" if moved else "copy", made if moved else [m[1] for m in made],
                           tr("grimoire.spells.vaultl.page", "Move %n item(s)", n=len(made)) if moved
                           else tr("grimoire.spells.vaultl.page", "Copy %n item(s)", n=len(made)))
        msg = tr("grimoire.spells.vaultl.page", "Moved %n item(s).", n=done) if moved \
            else tr("grimoire.spells.vaultl.page", "Copied %n item(s).", n=done)
        if errors:
            msg += "  " + tr("grimoire.spells.vaultl.page", "Problems: {list}").format(list="; ".join(errors[:3]))
        self._tell(msg)

    def trash_selected(self):
        sel = self.selected()
        if not sel:
            return
        if ops.in_trash(self.cwd):
            self.delete_forever()
            return
        self._trash_paths(sel)

    def _trash_paths(self, paths: list):
        """Move to Trash (the key, the menu, a drop onto the Trash): gio trash in the background, so a big
        selection doesn't freeze the window; Ctrl+Z puts them back."""
        sig = self._sig
        paths = [Path(p) for p in paths]
        self._tell(tr("grimoire.spells.vaultl.page", "Moving %n item(s) to the Trash…", n=len(paths)))

        def done(errors):
            failed = {e.split(":", 1)[0] for e in errors}
            sig.trashed.emit(len(paths) - len(errors), errors)
            sig.trashed_paths.emit([p for p in paths if p.name not in failed])

        THUMBS.start(Job(lambda: ops.trash(paths), done))

    def _trashed(self, gone: list):
        if gone:
            self._remember("trash", gone, tr("grimoire.spells.vaultl.page", "Move %n item(s) to the Trash",
                                             n=len(gone)))

    def _trash_done(self, done: int, errors: list):
        self._tell(tr("grimoire.spells.vaultl.page", "Moved %n item(s) to the Trash.", n=done)
                            + ("  " + tr("grimoire.spells.vaultl.page",
                                         "Problems: {list}").format(list="; ".join(errors[:2])) if errors else ""))

    def delete_forever(self):
        sel = [p for p in self.selected() if p.parent.resolve() == ops.TRASH_FILES.resolve()]
        if not sel:
            self._tell(tr("grimoire.spells.vaultl.page",
                                   "Pick items at the top of the Trash to delete forever."))
            return
        if QMessageBox.warning(self, tr("grimoire.spells.vaultl.page", "Delete forever?"),
                               tr("grimoire.spells.vaultl.page",
                                  "Permanently delete %n item(s)?\n\nThis can't be undone.", n=len(sel)),
                               QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
                               QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        errors = ops.delete_forever(sel)
        self._tell(tr("grimoire.spells.vaultl.page", "Deleted %n item(s) forever.", n=len(sel) - len(errors))
                            + ("  " + tr("grimoire.spells.vaultl.page",
                                         "Couldn't delete: {list}").format(list="; ".join(errors[:2])) if errors
                               else ""))

    def restore_selected(self):
        sel = self.selected()
        if not sel:
            return
        errors = ops.restore(sel)
        self._tell(tr("grimoire.spells.vaultl.page", "Restored %n item(s).", n=len(sel) - len(errors))
                            + ("  " + tr("grimoire.spells.vaultl.page",
                                         "Problems: {list}").format(list="; ".join(errors[:2])) if errors else ""))

    def empty_trash(self):
        n = len(list(ops.TRASH_FILES.iterdir())) if ops.TRASH_FILES.exists() else 0
        if not n:
            self._tell(tr("grimoire.spells.vaultl.page", "The Trash is already empty."))
            return
        if QMessageBox.warning(self, tr("grimoire.spells.vaultl.page", "Empty Trash?"),
                               tr("grimoire.spells.vaultl.page",
                                  "Permanently delete the %n item(s) in the Trash?\n\nThis can't be undone.", n=n),
                               QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
                               QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        errors = ops.empty_trash()
        self._tell(tr("grimoire.spells.vaultl.page",
                               "Couldn't delete %n item(s), kept in the Trash: {list}", n=len(errors)).format(
            list="; ".join(errors[:3])) if errors else tr("grimoire.spells.vaultl.page", "Trash emptied."))

    def terminal_here(self):
        """Grimoire's own TerminalL when it's there, else Konsole."""
        term = command("grimoire-terminall")
        if term.exists():
            QProcess.startDetached(str(term), [str(self.cwd)])          # absolute: never read as an option
        else:
            subprocess.Popen(["konsole", "--workdir", str(self.cwd)], start_new_session=True)

    def copy_path(self):
        sel = self.selected() or [self.cwd]
        QGuiApplication.clipboard().setText("\n".join(str(p) for p in sel))
        self._tell(tr("grimoire.spells.vaultl.page", "Path copied."))

    def _menu(self, view, pos):
        idx = view.indexAt(pos)
        if idx.isValid() and not view.selectionModel().isSelected(idx):
            view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect
                                         | QItemSelectionModel.SelectionFlag.Rows)
        sel = self.selected() if idx.isValid() else []
        m = QMenu(self)
        trash_mode = ops.in_trash(self.cwd)
        if sel:
            m.addAction(tr("grimoire.spells.vaultl.page", "Open"), lambda: [self.open_path(p) for p in sel])
            if len(sel) == 1 and sel[0].is_file():
                self._open_with_menu(m.addMenu(tr("grimoire.spells.vaultl.page", "Open with")), sel[0])
            if len(sel) == 1 and sel[0].is_dir() and not trash_mode:
                m.addAction(tr("grimoire.spells.vaultl.page", "Open in new window"), lambda: self.new_window(sel[0]))
                if str(sel[0]) not in self.prefs["places"]:
                    m.addAction(tr("grimoire.spells.vaultl.page", "Add to Places"), lambda: self.pin(sel[0]))
            m.addSeparator()
            if trash_mode:
                m.addAction(tr("grimoire.spells.vaultl.page", "Restore"), self.restore_selected)
                m.addAction(tr("grimoire.spells.vaultl.page", "Copy") + "\tCtrl+C", self.copy)
                m.addSeparator()
                m.addAction(glyph("trash", 16), tr("grimoire.spells.vaultl.page", "Delete forever…") + "\tDel",
                            self.delete_forever)
            else:
                m.addAction(tr("grimoire.spells.vaultl.page", "Cut") + "\tCtrl+X", lambda: self.copy(cut=True))
                m.addAction(tr("grimoire.spells.vaultl.page", "Copy") + "\tCtrl+C", self.copy)
                m.addAction(tr("grimoire.spells.vaultl.page", "Duplicate") + "\tCtrl+D", self.duplicate)
                if len(sel) == 1:
                    m.addAction(tr("grimoire.spells.vaultl.page", "Rename") + "\tF2", self.rename)
                m.addAction(tr("grimoire.spells.vaultl.page", "Copy path"), self.copy_path)
                m.addSeparator()
                if any(p.is_file() and archive.is_archive(p) for p in sel):
                    if len(sel) == 1:
                        m.addAction(glyph("archive", 16), tr("grimoire.spells.vaultl.page", "Browse archive"),
                                    lambda: self.open_archive(sel[0]))
                    m.addAction(tr("grimoire.spells.vaultl.page", "Extract here"), self.extract_selected)
                    m.addAction(tr("grimoire.spells.vaultl.page", "Extract to…"), lambda: self.extract_selected(True))
                m.addAction(tr("grimoire.spells.vaultl.page", "Compress…"), self.compress_selected)
                m.addSeparator()
                m.addAction(glyph("trash", 16), tr("grimoire.spells.vaultl.page", "Move to Trash") + "\tDel",
                            self.trash_selected)
        else:
            if self.undo_stack:
                m.addAction(tr("grimoire.spells.vaultl.page", "Undo: {what}").format(what=self.undo_stack[-1][2])
                            + "\tCtrl+Z", self.undo)
                m.addSeparator()
            m.addAction(glyph("newfolder", 16), tr("grimoire.spells.vaultl.page", "New folder") + "\tCtrl+Shift+N",
                        self.new_folder)
            paste = m.addAction(tr("grimoire.spells.vaultl.page", "Paste") + "\tCtrl+V", self.paste)
            data = QGuiApplication.clipboard().mimeData()
            paste.setEnabled(bool(data and data.hasUrls()) and not trash_mode)
            m.addSeparator()
            m.addAction(glyph("terminal", 16), tr("grimoire.spells.vaultl.page", "Open terminal here") + "\tF4",
                        self.terminal_here)
            m.addAction(tr("grimoire.spells.vaultl.page", "Copy path"), self.copy_path)
            hidden = m.addAction(tr("grimoire.spells.vaultl.page", "Show hidden files") + "\tCtrl+H",
                                 self.toggle_hidden)
            hidden.setCheckable(True)
            hidden.setChecked(self.show_hidden)
            sort = m.addMenu(tr("grimoire.spells.vaultl.page", "Sort by"))
            col = self.details.header().sortIndicatorSection()
            for i, name in enumerate((tr("grimoire.spells.vaultl.page", "Name"),
                                      tr("grimoire.spells.vaultl.page", "Size"),
                                      tr("grimoire.spells.vaultl.page", "Type"),
                                      tr("grimoire.spells.vaultl.page", "Date modified"))):
                a = sort.addAction(name, lambda i=i: self.sort_by(i))
                a.setCheckable(True)
                a.setChecked(i == col)
            sort.addSeparator()
            desc = sort.addAction(tr("grimoire.spells.vaultl.page", "Reverse order"), lambda: self.sort_by(col))
            desc.setCheckable(True)
            desc.setChecked(self.details.header().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder)
            m.addAction(tr("grimoire.spells.vaultl.page", "Open in new window") + "\tCtrl+N",
                        lambda: self.new_window(self.cwd))
            if str(self.cwd) not in self.prefs["places"] and not trash_mode:
                m.addAction(tr("grimoire.spells.vaultl.page", "Add to Places"), lambda: self.pin(self.cwd))
            if trash_mode:
                m.addSeparator()
                m.addAction(tr("grimoire.spells.vaultl.page", "Empty Trash…"), self.empty_trash)
        m.addSeparator()
        m.addAction(tr("grimoire.spells.vaultl.page", "Properties") + "\tAlt+Return", self.properties)
        target = sel[0] if len(sel) == 1 else self.cwd
        m.addAction(tr("grimoire.spells.vaultl.page", "Show in Dolphin"),
                    lambda: subprocess.Popen(["dolphin", "--select", str(target)], start_new_session=True))
        m.exec(view.viewport().mapToGlobal(pos))

    def _open_with_menu(self, menu: QMenu, p: Path):
        """Apps the system registers for this file type (gio mime), launched with gio."""
        mime = QMimeDatabase().mimeTypeForFile(str(p)).name()
        out = subprocess.run(["gio", "mime", mime], capture_output=True, text=True).stdout
        apps = []
        for line in out.splitlines():
            line = line.strip()
            if line.endswith(".desktop") and line not in apps and ":" not in line:
                apps.append(line)
        for desktop_id in apps[:12]:
            info = launch.desktop_file(desktop_id)
            if not info:
                continue
            name = next((l[5:] for l in info.read_text(errors="ignore").splitlines() if l.startswith("Name=")),
                        desktop_id)
            menu.addAction(no_mnemonic(name), lambda info=info: subprocess.Popen(["gio", "launch", str(info), str(p)],
                                                                    start_new_session=True))
        if not apps:
            menu.addAction(tr("grimoire.spells.vaultl.page", "No apps registered for this type")).setEnabled(False)

    def properties(self):
        target = (self.selected() or [self.cwd])[0]
        subprocess.Popen(["kioclient", "openProperties", QUrl.fromLocalFile(str(target)).toString()],
                         start_new_session=True)

    # ================================================================== drops on the sidebar, Ctrl+wheel zoom
    def eventFilter(self, obj, e):
        t = e.type()
        if not hasattr(self, "drives") or not hasattr(self, "grid"):    # events while the page is being built
            return super().eventFilter(obj, e)
        if obj is self.grid.viewport() and t == QEvent.Type.Wheel \
                and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1 if e.angleDelta().y() > 0 else -1)
            return True
        side = next((w for w in (self.places, self.drives) if obj is w.viewport()), None)
        if side is not None and t in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            it = side.itemAt(e.position().toPoint())
            ok = e.mimeData().hasUrls() and it is not None
            if not ok:
                e.ignore()
                return True
            dest = Path(it.data(Qt.ItemDataRole.UserRole))
            sources = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
            if t != QEvent.Type.Drop:
                side.setCurrentItem(it)                       # shows where it'll land
                e.acceptProposedAction()
                return True
            e.acceptProposedAction()
            QTimer.singleShot(0, lambda: self._drop_on_place(sources, dest))   # after the drag has finished
            return True
        return super().eventFilter(obj, e)

    def _drop_on_place(self, sources: list[Path], dest: Path):
        if not sources:
            return
        if dest.resolve() == ops.TRASH_FILES.resolve():
            self._trash_paths([p for p in sources if not ops.in_trash(p)])
        elif any(ops.in_trash(p) for p in sources):
            self._tell(tr("grimoire.spells.vaultl.page",
                                   "Items in the Trash can't be dragged out. Use Restore to put them back."))
        else:
            self._transfer(sources, dest, drop_moves(sources, dest, False))
        self._mark_place()

    # ================================================================== how the window was left
    def _restore_prefs(self):
        self.hidden_btn.setChecked(self.show_hidden)
        self.set_view(self.prefs["view"], save=False)
        if not self.prefs["preview"]:
            self.preview.setVisible(False)
            self.prev_btn.setChecked(False)
        order = Qt.SortOrder.DescendingOrder if self.prefs["sort_desc"] else Qt.SortOrder.AscendingOrder
        self.details.sortByColumn(self.prefs["sort_col"], order)
        self.details.header().sortIndicatorChanged.connect(
            lambda col, o: setattr(self, "prefs", prefs.update(sort_col=col,
                                                               sort_desc=o == Qt.SortOrder.DescendingOrder)))
        self._set_icon(self.prefs["icon"], save=False)

    def zoom(self, step: int):
        sizes = prefs.ICON_SIZES
        i = sizes.index(self.grid_delegate.icon) if self.grid_delegate.icon in sizes else 1
        self._set_icon(sizes[max(0, min(len(sizes) - 1, i + step))] if step else 72)

    def _set_icon(self, size: int, save=True):
        self.grid_delegate.icon = size
        self.grid.setGridSize(self.grid_delegate.grid_size())
        self.grid.doItemsLayout()
        if save:
            self.prefs = prefs.update(icon=size)

    def sort_by(self, col: int):
        hh = self.details.header()
        same = hh.sortIndicatorSection() == col
        flip = Qt.SortOrder.DescendingOrder if hh.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder \
            else Qt.SortOrder.AscendingOrder
        self.details.sortByColumn(col, flip if same else Qt.SortOrder.AscendingOrder)   # again: reverse

    # ================================================================== undo
    def _remember(self, kind: str, data, label: str):
        self.undo_stack.append((kind, data, label))
        del self.undo_stack[:-20]

    def _renamed(self, folder: str, old: str, new: str):
        if old != new:
            self._remember("rename", (Path(folder) / old, Path(folder) / new),
                           tr("grimoire.spells.vaultl.page", "Rename"))

    def undo(self):
        if not self.undo_stack:
            self._tell(tr("grimoire.spells.vaultl.page", "Nothing to undo."))
            return
        kind, data, label = self.undo_stack.pop()
        sig = self._sig

        def work():
            errors = []
            if kind == "trash":                           # data: the original paths
                found = ops.trashed_from(data)
                errors = ops.restore(found)
                if len(found) < len(data):
                    errors.append(tr("grimoire.spells.vaultl.page", "%n item(s) no longer in the Trash",
                                     n=len(data) - len(found)))
            elif kind == "move":                          # data: [(original, where it went)]
                for src, dest in data:
                    try:
                        if not (dest.exists() or dest.is_symlink()):
                            raise OSError(tr("grimoire.spells.vaultl.page", "it's gone"))
                        ops.transfer([dest], src.parent, True, made=(made := []))
                        if made and made[0][1].name != src.name:       # the old name was taken meanwhile
                            errors.append(tr("grimoire.spells.vaultl.page", "{name}: put back as {new}").format(
                                name=src.name, new=made[0][1].name))
                    except OSError as e:
                        errors.append(f"{dest.name}: {e.strerror or e}")
            elif kind in ("copy", "new"):                 # data: paths made; they go to the Trash, never deleted
                errors = ops.trash([p for p in data if p.exists() or p.is_symlink()])
            elif kind == "rename":
                old, new = data
                try:
                    rename_noreplace(new, old)
                except OSError as e:
                    errors.append(f"{new.name}: {e.strerror or e}")
            return errors

        self._tell(tr("grimoire.spells.vaultl.page", "Undoing: {what}…").format(what=label))
        count = 1 if kind == "rename" else len(data)
        THUMBS.start(Job(work, lambda errors: sig.undone.emit(label, errors, len(errors) < count)))

    def _undone(self, label: str, errors: list, any_back: bool):
        msg = tr("grimoire.spells.vaultl.page", "Undone: {what}").format(what=label) if any_back else \
            tr("grimoire.spells.vaultl.page", "Couldn't undo: {what}").format(what=label)
        if errors:
            msg += "  " + tr("grimoire.spells.vaultl.page", "Problems: {list}").format(list="; ".join(errors[:3]))
        self._tell(msg)

    # ================================================================== more ways to open
    def new_window(self, path: Path | None = None):
        """Another VaultL window on path (the selected folder, else this one)."""
        if path is None:
            sel = [p for p in self.selected() if p.is_dir()]
            path = sel[0] if len(sel) == 1 else self.cwd
        QProcess.startDetached(str(command("grimoire-vaultl")), ["--", str(path)])

    def duplicate(self):
        sel = self.selected()
        if not sel or ops.in_trash(self.cwd):
            return
        self._transfer(sel, self.cwd, False)

    def _shortcuts(self):
        def sc(keys, fn):
            s = QShortcut(QKeySequence(keys), self)
            s.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            s.activated.connect(lambda: fn() if self.body.currentIndex() == 0         # never behind a tidy panel
                                else self.archive_panel.key(keys) if self.body.currentIndex() == 2 else None)

        sc("Alt+Left", self.back)
        sc("Alt+Right", self.forward)
        sc("Alt+Up", self.up)
        sc("Backspace", lambda: None if self.focusWidget() in (self.search, self.path_edit) else self.back())
        sc("F2", self.rename)
        sc("Delete", self.trash_selected)
        sc("Ctrl+C", lambda: None if self.focusWidget() in (self.search, self.path_edit) else self.copy())
        sc("Ctrl+X", lambda: None if self.focusWidget() in (self.search, self.path_edit) else self.copy(cut=True))
        sc("Ctrl+V", lambda: None if self.focusWidget() in (self.search, self.path_edit) else self.paste())
        sc("Ctrl+A", lambda: self.view().selectAll())
        sc("Ctrl+H", self.toggle_hidden)
        sc("Ctrl+L", self.edit_path)
        sc("Ctrl+F", lambda: (self.search.setFocus(), self.search.selectAll()))
        sc("Ctrl+Shift+N", self.new_folder)
        sc("F4", self.terminal_here)
        sc("F5", lambda: (self._fill_drives(), self.tidy.refresh_auto(), self.navigate(self.cwd, record=False)))
        sc("F11", self.toggle_preview)
        sc("Alt+Return", self.properties)
        sc("Escape", lambda: (self.path_stack.setCurrentIndex(0), self.view().clearSelection()))
        sc("Ctrl+Z", lambda: None if self.focusWidget() in (self.search, self.path_edit) else self.undo())
        sc("Ctrl+D", lambda: None if self.focusWidget() in (self.search, self.path_edit) else self.duplicate())
        sc("Ctrl+N", lambda: self.new_window(self.cwd))
        for keys, step in (("Ctrl+=", 1), ("Ctrl++", 1), ("Ctrl+-", -1), ("Ctrl+0", 0)):
            sc(keys, lambda step=step: self.zoom(step))
