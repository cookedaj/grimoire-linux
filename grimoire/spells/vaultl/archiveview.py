# SPDX-License-Identifier: GPL-3.0-or-later
"""VaultL's archive views: an archive opens like a folder (ArchivePanel), the jobs bar shows extract and compress
progress with Cancel, and the Compress dialog. All archive work runs on worker threads (archive.py does it);
previews, Open and drags extract single entries into a private cache folder first."""
import os
import secrets
import shutil
import threading
import time
from pathlib import Path

from PySide6.QtCore import (QAbstractTableModel, QEventLoop, QMimeData, QMimeDatabase, QModelIndex, QObject, QSize,
                            Qt, QTimer, QUrl, Signal)
from PySide6.QtGui import QColor, QDesktopServices, QDrag, QGuiApplication, QIcon, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QMenu, QPushButton, QSizePolicy, QSplitter,
                               QToolButton, QTreeView, QVBoxLayout, QWidget)

from grimoire.fsutil import human, tilde
from grimoire.glyphs import glyph
from grimoire.i18n import isolate, ltr, tr, tr_noop
from grimoire.paths import CACHE
from grimoire.spells.vaultl import archive

TEMP = CACHE / "vaultl-archive"                       # preview / open / drag copies, owner-only
PREVIEW_MAX = 64 * 1024 * 1024                        # bigger entries preview on request only
DRAG_MAX = 4 * 1024 * 1024 * 1024
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".avif", ".tif", ".tiff", ".svg"}
TEXT_EXT = {".txt", ".md", ".py", ".json", ".toml", ".yaml", ".yml", ".sh", ".ini", ".cfg", ".conf", ".log", ".csv",
            ".qml", ".js", ".ts", ".rs", ".c", ".h", ".cpp", ".html", ".css", ".xml", ".lua", ".nfo"}
LEVELS = [tr_noop("grimoire.spells.vaultl.archiveview", "Store (no compression)"),
          tr_noop("grimoire.spells.vaultl.archiveview", "Fast"),
          tr_noop("grimoire.spells.vaultl.archiveview", "Normal"),
          tr_noop("grimoire.spells.vaultl.archiveview", "Maximum")]


def temp_dir() -> Path:
    TEMP.mkdir(parents=True, exist_ok=True)
    os.chmod(TEMP, 0o700)
    d = TEMP / secrets.token_hex(6)
    d.mkdir(mode=0o700)
    return d


def clean_temp(older_than: float = 3600):
    """Forget preview/drag copies from earlier (our own cache, never user files)."""
    if not TEMP.is_dir():
        return
    cutoff = time.time() - older_than
    for d in TEMP.iterdir():
        try:
            if d.is_dir() and not d.is_symlink() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


def when(ts) -> str:
    if not ts:
        return ""
    from PySide6.QtCore import QDateTime, QLocale
    return QLocale().toString(QDateTime.fromSecsSinceEpoch(int(ts)), QLocale.FormatType.ShortFormat)


# ================================================================== jobs (progress + cancel)
class _JobSignals(QObject):
    progress = Signal(object, object, str)
    finished = Signal(object)
    failed = Signal(object)


class Bar(QWidget):
    """A thin black & white progress line; value None runs a sliding segment (size unknown)."""

    def __init__(self):
        super().__init__()
        self.value = None
        self.phase = 0.0
        self.setFixedHeight(4)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)

    def _tick(self):
        if self.value is None:
            self.phase = (self.phase + 0.02) % 1.3
            self.update()

    def set(self, value):
        self.value = value
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#262626"))
        p.drawRoundedRect(r, 2, 2)
        p.setBrush(QColor("#f2f2f2"))
        if self.value is None:
            w = r.width() * 0.3
            x = r.width() * (self.phase - 0.3)
        else:
            w = r.width() * max(0.0, min(1.0, self.value))
            x = 0
        if self.isRightToLeft():                       # fills along the reading direction
            x = r.width() - x - w
        p.drawRoundedRect(int(x), 0, int(w), r.height(), 2, 2)


class JobRow(QFrame):
    """One running job: what it does, how far, Cancel."""

    def __init__(self, title: str, progress: archive.Progress):
        super().__init__()
        self.setObjectName("Card")
        self.progress = progress
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 8, 8, 8)
        v.setSpacing(6)
        h = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(glyph("archive", 18).pixmap(18, 18))
        h.addWidget(icon)
        self.title = QLabel(title)
        self.title.setTextFormat(Qt.TextFormat.PlainText)      # archive names come from anyone
        h.addWidget(self.title, 1)
        self.detail = QLabel()
        self.detail.setObjectName("Muted")
        h.addWidget(self.detail)
        self.cancel = QPushButton(tr("grimoire.spells.vaultl.archiveview", "Cancel"))
        self.cancel.clicked.connect(self._cancel)
        h.addWidget(self.cancel)
        v.addLayout(h)
        self.bar = Bar()
        v.addWidget(self.bar)

    def _cancel(self):
        self.progress.cancel()
        self.cancel.setEnabled(False)
        self.detail.setText(tr("grimoire.spells.vaultl.archiveview", "Stopping…"))

    def update_progress(self, done, total, label):
        if total:
            self.bar.set(done / total)
            self.detail.setText(tr("grimoire.spells.vaultl.archiveview", "{done} of {total}").format(
                done=ltr(human(done)), total=ltr(human(total))))
        else:
            self.bar.set(None)
            if done:
                self.detail.setText(ltr(human(done)))
        if label:
            self.title.setToolTip(label)


class Jobs(QWidget):
    """The column of running jobs under the file views. `start()` runs fn(progress) on its own thread (archives
    can take minutes; the shared pools stay free for thumbnails) and calls done/failed on the UI thread."""

    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 0, 18, 8)
        self.lay.setSpacing(6)
        self.running: list[tuple[JobRow, _JobSignals]] = []
        self.hide()

    def start(self, title: str, fn, done, failed, show=True) -> archive.Progress:
        sig = _JobSignals()
        progress = archive.Progress(lambda d, t, l: sig.progress.emit(d, t, l))
        row = JobRow(title, progress)
        sig.progress.connect(row.update_progress)

        def finish(result, ok):
            self._remove(row, sig)
            (done if ok else failed)(result)

        sig.finished.connect(lambda r: finish(r, True))
        sig.failed.connect(lambda e: finish(e, False))
        self.running.append((row, sig))
        if show:
            self.lay.addWidget(row)
            self.show()

        def work():
            try:
                result = fn(progress)
            except archive.ArchiveError as e:
                sig.failed.emit(e)
                return
            except Exception as e:                      # never leave a row spinning
                import traceback
                traceback.print_exc()
                sig.failed.emit(archive.ArchiveError(str(e)))
                return
            sig.finished.emit(result)

        threading.Thread(target=work, daemon=True, name="vaultl-archive").start()
        return progress

    def _remove(self, row, sig):
        self.running = [(r, s) for r, s in self.running if r is not row]
        row.setParent(None)
        row.deleteLater()
        self.setVisible(any(r.parent() is self for r, _ in self.running))

    def cancel_all(self):
        for row, _ in self.running:
            row.progress.cancel()


# ================================================================== entries model
class EntryModel(QAbstractTableModel):
    COLUMNS = [tr_noop("grimoire.spells.vaultl.archiveview", "Name"),
               tr_noop("grimoire.spells.vaultl.archiveview", "Size"),
               tr_noop("grimoire.spells.vaultl.archiveview", "Packed"),
               tr_noop("grimoire.spells.vaultl.archiveview", "Modified")]

    def __init__(self):
        super().__init__()
        self.rows: list[archive.Entry] = []
        self.mime = QMimeDatabase()
        self.icons: dict[str, QIcon] = {}
        self.sort_col, self.sort_order = 0, Qt.SortOrder.AscendingOrder

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = list(rows)
        self._sort()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 4

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return tr("grimoire.spells.vaultl.archiveview", self.COLUMNS[section])
        return None

    def entry(self, index) -> archive.Entry:
        return self.rows[index.row()]

    def icon(self, e: archive.Entry) -> QIcon:
        if e.is_dir:
            return glyph("folder", 20)
        mt = self.mime.mimeTypeForFile(e.name, QMimeDatabase.MatchMode.MatchExtension)
        key = mt.iconName()
        if key not in self.icons:
            icon = QIcon.fromTheme(key, QIcon.fromTheme(mt.genericIconName()))
            self.icons[key] = icon if not icon.isNull() else glyph("document", 20)
        return self.icons[key]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        e = self.rows[index.row()]
        c = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if c == 0:
                return e.name.rpartition("/")[2]
            if c == 1:
                return "" if e.is_dir else (ltr(human(e.size)) if e.size >= 0 else "?")
            if c == 2:
                return ltr(human(e.packed)) if e.packed >= 0 and not e.is_dir else ""
            if c == 3:
                return when(e.mtime)
        elif role == Qt.ItemDataRole.DecorationRole and c == 0:
            return self.icon(e)
        elif role == Qt.ItemDataRole.ToolTipRole and c == 0:
            bits = [e.name.rpartition("/")[2]]
            if e.encrypted:
                bits.append(tr("grimoire.spells.vaultl.archiveview", "Encrypted"))
            if e.link:
                bits.append(tr("grimoire.spells.vaultl.archiveview", "Link"))
            return " · ".join(bits)
        elif role == Qt.ItemDataRole.TextAlignmentRole and c in (1, 2):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def flags(self, index):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        self.layoutAboutToBeChanged.emit()
        self.sort_col, self.sort_order = column, order
        self._sort()
        self.layoutChanged.emit()

    def _sort(self):
        key = {0: lambda e: e.name.rpartition("/")[2].casefold(), 1: lambda e: e.size,
               2: lambda e: e.packed, 3: lambda e: e.mtime or 0}[self.sort_col]
        rev = self.sort_order == Qt.SortOrder.DescendingOrder
        self.rows.sort(key=key, reverse=rev)
        self.rows.sort(key=lambda e: not e.is_dir)                 # folders first, stable

    def supportedDragActions(self):
        return Qt.DropAction.CopyAction


class EntryView(QTreeView):
    """Details list of one folder inside the archive; dragging extracts the selection first."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    def startDrag(self, actions):
        self.panel.drag_out()


# ================================================================== the panel
class ArchivePanel(QWidget):
    """An archive opened like a folder: breadcrumbs inside it, details list, preview, Extract here / Extract to."""
    message = Signal(str)                                  # for the page's status line
    leave = Signal()                                       # back out to the folder view

    def __init__(self, jobs: Jobs):
        super().__init__()
        self.jobs = jobs
        self.path: Path | None = None
        self.reader: archive.Reader | None = None
        self.folder = ""                                   # current folder inside the archive ("" = top)
        self.history: list[str] = []
        self.loading: archive.Progress | None = None
        self.preview_job: archive.Progress | None = None   # the preview being extracted (one at a time)
        self.preview_req = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 10)
        lay.setSpacing(10)
        lay.addLayout(self._toolbar())
        self.note = self._note()
        lay.addWidget(self.note)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(1)
        self.model = EntryModel()
        self.view = EntryView(self)
        self.view.setObjectName("FileDetails")
        self.view.setModel(self.model)
        self.view.setRootIsDecorated(False)
        self.view.setItemsExpandable(False)
        self.view.setUniformRowHeights(True)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.view.setIconSize(QSize(20, 20))
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setDragEnabled(True)
        self.view.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._menu)
        self.view.activated.connect(self._activated)
        self.view.selectionModel().selectionChanged.connect(lambda *_: (self._preview(), self._status()))
        h = self.view.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c, w in ((1, 100), (2, 100), (3, 170)):
            self.view.setColumnWidth(c, w)
        split.addWidget(self.view)
        self.preview = self._preview_pane()
        split.addWidget(self.preview)
        split.setStretchFactor(0, 1)
        split.setSizes([900, 280])
        lay.addWidget(split, 1)
        self.status = QLabel()
        self.status.setObjectName("Muted")
        lay.addWidget(self.status)
        for label in (self.note_text, self.pv_text, self.pv_name, self.pv_info, self.status):
            label.setTextFormat(Qt.TextFormat.PlainText)   # entry names, file contents and 7z's errors are anyone's

    # ------------------------------------------------------------ layout
    def _tool(self, icon, tip, slot) -> QToolButton:
        b = QToolButton()
        b.setObjectName("Tool")
        b.setIcon(glyph(icon, 18))
        b.setIconSize(QSize(18, 18))
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.clicked.connect(slot)
        return b

    def _toolbar(self):
        bar = QHBoxLayout()
        bar.setSpacing(4)
        self.back_btn = self._tool("back", tr("grimoire.spells.vaultl.archiveview", "Back (Alt+Left)"), self.back)
        self.up_btn = self._tool("up", tr("grimoire.spells.vaultl.archiveview", "Up (Alt+Up)"), self.up)
        bar.addWidget(self.back_btn)
        bar.addWidget(self.up_btn)
        bar.addSpacing(6)
        self.crumbs = QFrame()
        self.crumbs.setObjectName("Crumbs")
        self.crumbs.setFixedHeight(34)
        self.crumb_lay = QHBoxLayout(self.crumbs)
        self.crumb_lay.setContentsMargins(6, 0, 6, 0)
        self.crumb_lay.setSpacing(0)
        bar.addWidget(self.crumbs, 1)
        bar.addSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.vaultl.archiveview", "Search this folder"))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(glyph("search", 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(lambda _: self._fill())
        bar.addWidget(self.search)
        bar.addSpacing(6)
        self.here_btn = QPushButton(tr("grimoire.spells.vaultl.archiveview", "Extract here"))
        self.here_btn.setObjectName("Primary")
        self.here_btn.setToolTip(tr("grimoire.spells.vaultl.archiveview",
                                    "Extract everything (or the selection) next to the archive"))
        self.here_btn.clicked.connect(lambda: self.extract_selected(None))
        self.to_btn = QPushButton(tr("grimoire.spells.vaultl.archiveview", "Extract to…"))
        self.to_btn.clicked.connect(self.extract_to)
        bar.addWidget(self.here_btn)
        bar.addWidget(self.to_btn)
        return bar

    def _note(self) -> QFrame:
        """Shown while reading, and for a missing tool, a password or a damaged archive."""
        w = QFrame()
        w.setObjectName("Card")
        h = QHBoxLayout(w)
        h.setContentsMargins(14, 8, 8, 8)
        self.note_icon = QLabel()
        self.note_icon.setPixmap(glyph("archive", 18).pixmap(18, 18))
        h.addWidget(self.note_icon)
        self.note_text = QLabel()
        self.note_text.setWordWrap(True)
        self.note_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        h.addWidget(self.note_text, 1)
        self.note_btn = QPushButton()
        self.note_btn.clicked.connect(lambda: self._note_action())
        h.addWidget(self.note_btn)
        self._note_action = lambda: None
        w.hide()
        return w

    def _show_note(self, text: str, button: str = "", action=None):
        self.note_text.setText(text)
        self.note_btn.setVisible(bool(button))
        self.note_btn.setText(button)
        self._note_action = action or (lambda: None)
        self.note.show()

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
        self.pv_text.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)   # never grows the window
        self.pv_text.setMinimumHeight(120)
        self.pv_name = QLabel()
        self.pv_name.setObjectName("Section")
        self.pv_name.setWordWrap(True)
        self.pv_info = QLabel()
        self.pv_info.setObjectName("Muted")
        self.pv_info.setWordWrap(True)
        self.pv_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        for x in (self.pv_image, self.pv_text, self.pv_name, self.pv_info):
            v.addWidget(x)
        self.pv_text.hide()
        v.addStretch(1)
        self.pv_open = QPushButton(tr("grimoire.spells.vaultl.archiveview", "Open"))
        self.pv_open.setObjectName("Primary")
        self.pv_open.setToolTip(tr("grimoire.spells.vaultl.archiveview",
                                   "Opens a copy: changes to it don't go back into the archive"))
        self.pv_open.clicked.connect(lambda: self.open_entries(self.selected()[:1]))
        v.addWidget(self.pv_open)
        return w

    # ------------------------------------------------------------ opening
    def open(self, path: Path):
        """Read path's table of contents off the UI thread, then show its top folder."""
        self.close_archive()
        clean_temp()
        self.path = path
        self.folder = ""
        self.history = [""]
        self.model.set_rows([])
        self._crumbs()
        self._set_enabled(False)
        self.status.clear()
        self.pv_name.setText(path.name)
        self.pv_info.setText(ltr(tilde(path)))
        self.pv_image.setPixmap(glyph("archive", 96).pixmap(96, 96, QIcon.Mode.Active))
        self.pv_text.hide()
        self.pv_open.hide()
        self._load()

    def _load(self, password: str | None = None):
        path = self.path
        self._show_note(tr("grimoire.spells.vaultl.archiveview", "Reading {name}…").format(name=isolate(path.name)),
                        tr("grimoire.spells.vaultl.archiveview", "Cancel"), self._cancel_load)

        def work(progress):
            r = archive.reader(path, password)
            r.listing(progress)
            return r

        self.loading = self.jobs.start("", work, lambda r: self._loaded(path, r),
                                       lambda e: self._load_failed(path, e, password), show=False)

    def _cancel_load(self):
        if self.loading:
            self.loading.cancel()
        self.leave.emit()

    def _loaded(self, path: Path, r: archive.Reader):
        if path != self.path:
            return                                       # another archive was opened meanwhile
        self.loading = None
        self.reader = r
        self.note.hide()
        lst = r.listing()
        if lst.unsafe:
            self._show_note(tr("grimoire.spells.vaultl.archiveview",
                               "%n entry(s) with unsafe names (absolute paths or \"..\") are hidden and won't be "
                               "extracted.", n=lst.unsafe))
        self._set_enabled(True)
        self.go("", record=False)
        self.view.setFocus()

    def _load_failed(self, path: Path, e: Exception, password):
        if path != self.path:
            return
        self.loading = None
        if isinstance(e, archive.Cancelled):
            return
        if isinstance(e, archive.NeedPassword):
            self._show_note(str(e), tr("grimoire.spells.vaultl.archiveview", "Enter password…"),
                            lambda: self._ask_password_then(self._load))
            if not e.wrong:
                QTimer.singleShot(0, lambda: self._ask_password_then(self._load))
            return
        if isinstance(e, archive.Missing):
            cmd = e.command
            self._show_note(tr("grimoire.spells.vaultl.archiveview", "{problem} Install it with: {command}").format(
                problem=str(e), command=ltr(cmd)), tr("grimoire.spells.vaultl.archiveview", "Copy command"),
                lambda: (QGuiApplication.clipboard().setText(cmd),
                         self.message.emit(tr("grimoire.spells.vaultl.archiveview", "Command copied."))))
            return
        self._show_note(tr("grimoire.spells.vaultl.archiveview", "Can't open {name}: {error}").format(
            name=isolate(path.name), error=str(e)))

    def _ask_password_then(self, fn):
        pw, ok = QInputDialog.getText(self, tr("grimoire.spells.vaultl.archiveview", "Password"),
                                      tr("grimoire.spells.vaultl.archiveview", "Password for {name}:").format(
                                          name=isolate(self.path.name if self.path else "")),
                                      QLineEdit.EchoMode.Password)
        if ok and pw:
            fn(pw)

    def close_archive(self):
        if self.loading:
            self.loading.cancel()
            self.loading = None
        self._stop_preview()
        self.path = None
        self.reader = None
        self.note.hide()

    def _set_enabled(self, on: bool):
        for w in (self.here_btn, self.to_btn, self.search, self.view, self.up_btn):
            w.setEnabled(on)

    # ------------------------------------------------------------ navigation
    def go(self, folder: str, record=True):
        if record and folder != self.folder:
            self.history.append(folder)
        self.folder = folder
        if self.search.text():
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
        self._fill()
        self._crumbs()
        self.up_btn.setEnabled(bool(folder))

    def _fill(self):
        if not self.reader:
            return
        rows = self.reader.listing().children(self.folder)
        text = self.search.text().casefold()
        if text:
            rows = [e for e in rows if text in e.name.rpartition("/")[2].casefold()]
        self.model.set_rows(rows)
        self._preview()
        self._status()

    def _crumbs(self):
        while self.crumb_lay.count():
            w = self.crumb_lay.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        if not self.path:
            return
        parts = [("", self.path.name)]
        if self.folder:
            bits = self.folder.split("/")
            parts += [("/".join(bits[:i + 1]), b) for i, b in enumerate(bits)]
        for i, (target, label) in enumerate(parts):
            if i:
                sep = QLabel("‹" if self.isRightToLeft() else "›")
                sep.setObjectName("Muted")
                self.crumb_lay.addWidget(sep)
            b = QPushButton(label)
            b.setObjectName("Crumb")
            b.setFlat(True)
            if i == 0:
                b.setIcon(glyph("archive", 16))
            b.clicked.connect(lambda _=False, t=target: self.go(t))
            self.crumb_lay.addWidget(b)
        self.crumb_lay.addStretch(1)

    def back(self):
        if len(self.history) > 1:
            self.history.pop()
            self.go(self.history[-1], record=False)
        else:
            self.leave.emit()

    def up(self):
        if self.folder:
            self.go(self.folder.rpartition("/")[0])
        else:
            self.leave.emit()

    def key(self, keys: str):
        """The page's shortcuts, while an archive is showing."""
        typing = self.focusWidget() is self.search
        if keys == "Alt+Left":
            self.back()
        elif keys == "Alt+Up" or (keys == "Backspace" and not typing):
            self.up()
        elif keys == "Ctrl+F":
            self.search.setFocus()
            self.search.selectAll()
        elif keys == "Ctrl+A" and not typing:
            self.view.selectAll()
        elif keys == "Escape":
            if self.search.text():
                self.search.clear()
            else:
                self.view.clearSelection()
        elif keys == "F11":
            self.preview.setVisible(not self.preview.isVisible())
            self._preview()
        elif keys == "Ctrl+C" and not typing:
            self.copy_names()

    # ------------------------------------------------------------ selection, preview, status
    def selected(self) -> list[archive.Entry]:
        return [self.model.entry(i) for i in self.view.selectionModel().selectedRows(0)]

    def _status(self):
        if not self.reader:
            return
        lst = self.reader.listing()
        files, size = lst.total()
        text = tr("grimoire.spells.vaultl.archiveview", "%n item(s)", n=self.model.rowCount())
        sel = self.selected()
        if sel:
            text += "   ·   " + tr("grimoire.spells.vaultl.archiveview", "%n selected", n=len(sel))
        text += "   ·   " + tr("grimoire.spells.vaultl.archiveview", "%n file(s), {size} unpacked", n=files).format(
            size=ltr(human(size)))
        if lst.encrypted:
            text += "   ·   " + tr("grimoire.spells.vaultl.archiveview", "Encrypted")
        self.status.setText(text)

    def _stop_preview(self):
        if self.preview_job:
            self.preview_job.cancel()
            self.preview_job = None

    def _preview(self):
        if not self.preview.isVisible() or not self.reader:
            return
        self.preview_req += 1
        self._stop_preview()                               # arrowing through a tar.xz: only the last one runs
        sel = self.selected()
        self.pv_text.hide()
        self.pv_text.clear()
        self.pv_open.setVisible(len(sel) == 1)
        if len(sel) != 1:
            self.pv_name.setText(self.path.name)
            lst = self.reader.listing()
            files, size = lst.total()
            packed = self.path.stat().st_size if self.path.exists() else 0
            lines = [tr("grimoire.spells.vaultl.archiveview", "Archive · %n file(s)", n=files),
                     tr("grimoire.spells.vaultl.archiveview", "{size} unpacked · {packed} packed").format(
                         size=ltr(human(size)), packed=ltr(human(packed)))]
            if sel:
                lines.insert(0, tr("grimoire.spells.vaultl.archiveview", "%n selected", n=len(sel)))
            lines.append(ltr(tilde(self.path)))
            self.pv_info.setText("\n".join(lines))
            self.pv_image.setPixmap(glyph("archive", 96).pixmap(96, 96, QIcon.Mode.Active))
            return
        e = sel[0]
        self.pv_name.setText(e.name.rpartition("/")[2])
        lines = []
        if e.is_dir:
            n = len(self.reader.listing().children(e.name))
            lines.append(tr("grimoire.spells.vaultl.archiveview", "Folder · %n item(s)", n=n))
            self.pv_image.setPixmap(glyph("folder", 96).pixmap(96, 96, QIcon.Mode.Active))
        else:
            kind = self.model.mime.mimeTypeForFile(e.name, QMimeDatabase.MatchMode.MatchExtension).comment()
            lines.append(" · ".join(x for x in ((ltr(human(e.size)) if e.size >= 0 else ""), kind) if x))
            if e.packed >= 0:
                lines.append(tr("grimoire.spells.vaultl.archiveview", "{size} packed").format(
                    size=ltr(human(e.packed))))
            self.pv_image.setPixmap(self.model.icon(e).pixmap(96, 96))
            ext = Path(e.name).suffix.lower()
            if (ext in IMAGE_EXT or ext in TEXT_EXT) and 0 <= e.size <= PREVIEW_MAX and not e.link \
                    and not (e.encrypted and not self.reader.password):
                self._load_preview(e, self.preview_req)
        if e.encrypted:
            lines.append(tr("grimoire.spells.vaultl.archiveview", "Encrypted"))
        if e.mtime:
            lines.append(tr("grimoire.spells.vaultl.archiveview", "Modified {when}").format(when=when(e.mtime)))
        lines.append(ltr(e.name))
        self.pv_info.setText("\n".join(lines))

    def _load_preview(self, e: archive.Entry, req: int):
        """Extract one entry to the private cache and show it (image or the start of a text)."""
        r, base = self.reader, e.name.rpartition("/")[0]

        def work(progress):
            d = temp_dir()
            res = archive.extract(r, d, [e.name], base, progress, private=True)
            p = res.placed[0] if res.placed else None
            if p is None or not p.is_file():
                return None, None, d
            if Path(e.name).suffix.lower() in IMAGE_EXT:
                reader = QImageReader(str(p))
                reader.setAutoTransform(True)
                if reader.size().isValid():
                    reader.setScaledSize(reader.size().scaled(QSize(240, 240), Qt.AspectRatioMode.KeepAspectRatio))
                return reader.read(), None, d
            with open(p, "rb") as f:
                text = f.read(4000).decode("utf-8", "replace")[:1500]
                return None, "\n".join(text.splitlines()[:40]), d

        def done(result):
            img, text, d = result
            if req != self.preview_req:
                return
            self.preview_job = None
            if img is not None and not img.isNull():
                self.pv_image.setPixmap(QPixmap.fromImage(img))
            elif text is not None:
                self.pv_text.setText(text)
                self.pv_text.show()
                self.pv_image.setPixmap(self.model.icon(e).pixmap(56, 56))

        self.preview_job = self.jobs.start("", work, done, lambda err: None, show=False)

    # ------------------------------------------------------------ actions
    def _activated(self, index):
        e = self.model.entry(index)
        if e.is_dir:
            self.go(e.name)
        else:
            self.open_entries([e])

    def _password_first(self, entries, then) -> bool:
        """Ask for the password when entries need one we don't have yet. False: the user cancelled."""
        if self.reader and any(e.encrypted for e in entries) and not self.reader.password:
            pw, ok = QInputDialog.getText(self, tr("grimoire.spells.vaultl.archiveview", "Password"),
                                          tr("grimoire.spells.vaultl.archiveview", "Password for {name}:").format(
                                              name=isolate(self.path.name)), QLineEdit.EchoMode.Password)
            if not ok or not pw:
                return False
            self.reader.password = pw
        return True

    def _failed(self, e: Exception, retry=None):
        if isinstance(e, archive.Cancelled):
            self.message.emit(str(e))
            return
        if isinstance(e, archive.NeedPassword) and self.reader:
            self.reader.password = None
            if retry:
                self.message.emit(str(e))
                pw, ok = QInputDialog.getText(self, tr("grimoire.spells.vaultl.archiveview", "Password"),
                                              str(e), QLineEdit.EchoMode.Password)
                if ok and pw:
                    self.reader.password = pw
                    retry()
                return
        if isinstance(e, archive.Missing):
            self.message.emit(tr("grimoire.spells.vaultl.archiveview", "{problem} Install it with: {command}").format(
                problem=str(e), command=ltr(e.command)))
            return
        self.message.emit(str(e))

    def open_entries(self, entries):
        """Open a copy of one file in its usual app (folders open here)."""
        if not entries or not self.reader:
            return
        e = entries[0]
        if e.is_dir:
            self.go(e.name)
            return
        if not self._password_first([e], None):
            return
        r, base = self.reader, e.name.rpartition("/")[0]

        def work(progress):
            d = temp_dir()
            return archive.extract(r, d, [e.name], base, progress, private=True), d

        def done(result):
            res, d = result
            if res.placed:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(res.placed[0])))

        self.jobs.start(tr("grimoire.spells.vaultl.archiveview", "Opening {name}…").format(
            name=isolate(e.name.rpartition("/")[2])), work, done,
            lambda err: self._failed(err, lambda: self.open_entries([e])), show=e.size > 8 * 1024 * 1024)

    def extract_selected(self, dest: Path | None):
        """Extract the selection (or, with nothing selected, the whole archive) into dest, else next to it."""
        if not self.reader:
            return
        sel = self.selected()
        names = [e.name for e in sel] or None
        dest = dest or self.path.parent
        if not self._password_first(sel or list(self.reader.listing().entries.values()), None):
            return
        start_extract(self.jobs, self.reader, dest, names, self.folder if names else "", self.message.emit,
                      lambda err: self._failed(err, lambda: self.extract_selected(dest)))

    def extract_to(self):
        if not self.reader:
            return
        d = QFileDialog.getExistingDirectory(self, tr("grimoire.spells.vaultl.archiveview", "Extract to"),
                                             str(self.path.parent))
        if d:
            self.extract_selected(Path(d))

    def copy_names(self):
        sel = self.selected()
        if sel:
            QGuiApplication.clipboard().setText("\n".join(e.name for e in sel))
            self.message.emit(tr("grimoire.spells.vaultl.archiveview", "Names copied."))

    def drag_out(self):
        """Extract the selection to the private cache (with progress; the window keeps responding), then drag
        the copies out like files."""
        sel = self.selected()
        if not sel or not self.reader:
            return
        size = sum(max(e.size, 0) for e in self.reader.listing().under([e.name for e in sel]))
        if size > DRAG_MAX:
            self.message.emit(tr("grimoire.spells.vaultl.archiveview",
                                 "Too big to drag ({size}): use Extract to… instead.").format(size=ltr(human(size))))
            return
        if not self._password_first(sel, None):
            return
        loop = QEventLoop()
        box = {}
        r, names, base = self.reader, [e.name for e in sel], self.folder

        def work(progress):
            d = temp_dir()
            return archive.extract(r, d, names, base, progress), d

        def done(result):
            box["ok"] = result
            loop.quit()

        def failed(err):
            box["err"] = err
            loop.quit()

        self.jobs.start(tr("grimoire.spells.vaultl.archiveview", "Preparing %n item(s) to drag…", n=len(sel)),
                        work, done, failed, show=size > 16 * 1024 * 1024)
        loop.exec()
        if "err" in box:
            self._failed(box["err"])
            return
        res, d = box["ok"]
        if not res.placed:
            return
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(p)) for p in res.placed])
        drag = QDrag(self.view)
        drag.setMimeData(data)
        drag.setPixmap((glyph("archive", 32) if len(sel) > 1 else self.model.icon(sel[0])).pixmap(32, 32))
        drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)

    def _menu(self, pos):
        idx = self.view.indexAt(pos)
        if not idx.isValid():
            self.view.clearSelection()
        sel = self.selected()
        m = QMenu(self)
        if sel:
            m.addAction(tr("grimoire.spells.vaultl.archiveview", "Open"), lambda: self.open_entries(sel[:1]))
            m.addSeparator()
            m.addAction(glyph("archive", 16), tr("grimoire.spells.vaultl.archiveview", "Extract here"),
                        lambda: self.extract_selected(None))
            m.addAction(tr("grimoire.spells.vaultl.archiveview", "Extract to…"), self.extract_to)
            m.addSeparator()
            m.addAction(tr("grimoire.spells.vaultl.archiveview", "Copy name") + "\tCtrl+C", self.copy_names)
        else:
            m.addAction(glyph("archive", 16), tr("grimoire.spells.vaultl.archiveview", "Extract all here"),
                        lambda: self.extract_selected(None))
            m.addAction(tr("grimoire.spells.vaultl.archiveview", "Extract all to…"), self.extract_to)
            if self.folder:
                m.addSeparator()
                m.addAction(glyph("up", 16), tr("grimoire.spells.vaultl.archiveview", "Up") + "\tAlt+Up", self.up)
        m.addSeparator()
        m.addAction(tr("grimoire.spells.vaultl.archiveview", "Close archive"), self.leave.emit)
        m.exec(self.view.viewport().mapToGlobal(pos))


# ================================================================== from the folder view
def outcome(res: archive.Result, dest: Path) -> str:
    """What an extraction did, for the status line."""
    if not res.placed:
        return tr("grimoire.spells.vaultl.archiveview", "Nothing to extract.")
    msg = tr("grimoire.spells.vaultl.archiveview", "Extracted to {path}.").format(
        path=ltr(tilde(res.placed[0] if len(res.placed) == 1 else dest)))
    skipped = res.skipped + res.unsafe
    if skipped:
        msg += "  " + tr("grimoire.spells.vaultl.archiveview",
                         "Left out %n unsafe or special entry(s) (links leaving the folder, devices, "
                         "absolute paths).", n=skipped)
    return msg


def start_extract(jobs: Jobs, r: archive.Reader, dest: Path, names, base, say, failed):
    """One extraction from an open archive, in the jobs bar; say() gets the outcome."""
    jobs.start(tr("grimoire.spells.vaultl.archiveview", "Extracting {name}").format(name=isolate(r.path.name)),
               lambda progress: archive.extract(r, dest, names, base, progress),
               lambda res: say(outcome(res, dest)), failed)


def extract_files(page, paths: list[Path], dest: Path | None = None):
    """Extract here / Extract to… on archives picked in the folder view: each archive in turn, in the jobs bar.
    A password-protected one asks first (its listing is read on the worker; the question comes back here)."""
    for p in paths:
        _extract_one(page, p, dest or p.parent, None)


def _extract_one(page, p: Path, dest: Path, password):
    def work(progress):
        r = archive.reader(p, password)
        return archive.extract(r, dest, progress=progress)

    def done(res: archive.Result):
        start_done(page, res, dest)

    def failed(e):
        if isinstance(e, archive.NeedPassword):
            pw, ok = QInputDialog.getText(page, tr("grimoire.spells.vaultl.archiveview", "Password"),
                                          tr("grimoire.spells.vaultl.archiveview", "Password for {name}:").format(
                                              name=isolate(p.name)) if not e.wrong else str(e),
                                          QLineEdit.EchoMode.Password)
            if ok and pw:
                _extract_one(page, p, dest, pw)
            return
        if isinstance(e, archive.Missing):
            page.status.setText(tr("grimoire.spells.vaultl.archiveview", "{problem} Install it with: {command}").format(
                problem=str(e), command=ltr(e.command)))
            return
        page.status.setText(tr("grimoire.spells.vaultl.archiveview", "Can't extract {name}: {error}").format(
            name=isolate(p.name), error=str(e)))

    page.jobs.start(tr("grimoire.spells.vaultl.archiveview", "Extracting {name}").format(name=isolate(p.name)),
                    work, done, failed)


def start_done(page, res: archive.Result, dest: Path):
    _say_after_reveal(page, outcome(res, dest), res.placed[0] if res.placed else None)


def _say_after_reveal(page, msg: str, made: Path | None):
    """Select what was made (when its folder is showing), then say what happened: selecting rewrites the status
    line, so the message goes in after it."""
    page.status.setText(msg)
    if made is not None and page.body.currentIndex() == 0 and page.cwd == made.parent:
        page.reveal(made)
        QTimer.singleShot(400, lambda: page.status.setText(msg))


# ================================================================== compress
class CompressDialog(QDialog):
    """Name, format, level and an optional password; `result_args` holds what to make when accepted."""

    def __init__(self, parent, sources: list[Path]):
        super().__init__(parent)
        self.setObjectName("Page")
        self.setWindowTitle(tr("grimoire.spells.vaultl.archiveview", "Compress"))
        self.setMinimumWidth(480)
        self.sources = sources
        self.formats = archive.formats()
        self.fmt = self.formats[0]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(12)
        title = QLabel(tr("grimoire.spells.vaultl.archiveview", "Compress %n item(s)", n=len(sources)))
        title.setObjectName("SectionTitle")
        lay.addWidget(title)
        where = QLabel(tr("grimoire.spells.vaultl.archiveview", "Saved in {folder}").format(
            folder=ltr(tilde(sources[0].parent))))
        where.setObjectName("Muted")
        where.setWordWrap(True)
        lay.addWidget(where)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(10)
        g.addWidget(QLabel(tr("grimoire.spells.vaultl.archiveview", "Name")), 0, 0)
        self.name = QLineEdit(archive.default_name(sources, self.fmt))
        g.addWidget(self.name, 0, 1)
        g.addWidget(QLabel(tr("grimoire.spells.vaultl.archiveview", "Format")), 1, 0)
        row = QHBoxLayout()
        row.setSpacing(0)
        self.seg = []
        for f in self.formats:
            b = QPushButton(f)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setChecked(f == self.fmt)
            b.clicked.connect(lambda _=False, f=f: self._pick(f))
            row.addWidget(b)
            self.seg.append(b)
        from grimoire.widgets import segments
        segments(self.seg)
        row.addStretch(1)
        g.addLayout(row, 1, 1)
        g.addWidget(QLabel(tr("grimoire.spells.vaultl.archiveview", "Compression")), 2, 0)
        self.level = QComboBox()
        for text in LEVELS:
            self.level.addItem(tr("grimoire.spells.vaultl.archiveview", text))
        self.level.setCurrentIndex(2)
        g.addWidget(self.level, 2, 1)
        g.addWidget(QLabel(tr("grimoire.spells.vaultl.archiveview", "Password")), 3, 0)
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw.setPlaceholderText(tr("grimoire.spells.vaultl.archiveview", "Optional"))
        g.addWidget(self.pw, 3, 1)
        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw2.setPlaceholderText(tr("grimoire.spells.vaultl.archiveview", "Repeat password"))
        g.addWidget(self.pw2, 4, 1)
        lay.addLayout(g)
        self.hint = QLabel()
        self.hint.setObjectName("Muted")
        self.hint.setWordWrap(True)
        self.hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.hint)
        self.error = QLabel()
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.setWordWrap(True)
        self.error.hide()
        lay.addWidget(self.error)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton(tr("grimoire.spells.vaultl.archiveview", "Cancel"))
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton(tr("grimoire.spells.vaultl.archiveview", "Compress"))
        self.ok.setObjectName("Primary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(self.ok)
        lay.addLayout(btns)
        self.result_args = None
        self._pick(self.fmt)
        self.name.setFocus()
        stem_len = len(self.name.text()) - len(archive.FORMATS[self.fmt])
        self.name.setSelection(0, max(stem_len, 0))

    def _pick(self, fmt: str):
        old_ext = archive.FORMATS[self.fmt]
        self.fmt = fmt
        for b, f in zip(self.seg, self.formats):
            b.setChecked(f == fmt)
        name = self.name.text()
        if name.endswith(old_ext):
            self.name.setText(name[:-len(old_ext)] + archive.FORMATS[fmt])
        enc = archive.can_encrypt(fmt)
        self.pw.setEnabled(enc)
        self.pw2.setEnabled(enc)
        if enc:
            self.hint.setText(tr("grimoire.spells.vaultl.archiveview",
                                 "A password encrypts the contents with AES-256 (7z also hides the file names)."))
        elif fmt in (archive.ZIPF, archive.SEVENF):
            self.hint.setText(tr("grimoire.spells.vaultl.archiveview",
                                 "Passwords need 7-Zip. Install it with: {command}").format(
                command=ltr("sudo apt install 7zip")))
        else:
            self.hint.setText(tr("grimoire.spells.vaultl.archiveview",
                                 "tar archives keep Linux permissions and links; they can't carry a password."))

    def _accept(self):
        name = self.name.text().strip()
        if not name or "/" in name or name in (".", ".."):
            return self._err(tr("grimoire.spells.vaultl.archiveview", "Pick a file name (no slashes)."))
        pw = self.pw.text() if self.pw.isEnabled() else ""
        if pw != (self.pw2.text() if self.pw2.isEnabled() else ""):
            return self._err(tr("grimoire.spells.vaultl.archiveview", "The passwords don't match."))
        problem = archive.password_problem(self.fmt, pw)
        if problem:
            return self._err(problem)
        ext = archive.FORMATS[self.fmt]
        if not name.lower().endswith(ext):
            name += ext
        self.result_args = (self.sources[0].parent / name, self.fmt, self.level.currentIndex(), pw)
        self.accept()

    def _err(self, text):
        self.error.setText(text)
        self.error.show()


def compress(page, sources: list[Path]):
    """Ask, then pack in the jobs bar; the new archive gets selected when it's done."""
    if not sources:
        return
    if len({p.parent for p in sources}) > 1:
        page.status.setText(tr("grimoire.spells.vaultl.archiveview", "Pick items from one folder to compress."))
        return
    d = CompressDialog(page, sources)
    if d.exec() != QDialog.DialogCode.Accepted or not d.result_args:
        return
    out, fmt, level, pw = d.result_args

    def done(made: Path):
        _say_after_reveal(page, tr("grimoire.spells.vaultl.archiveview", "Made {name} ({size}).").format(
            name=isolate(made.name), size=ltr(human(made.stat().st_size if made.exists() else 0))), made)

    def failed(e):
        page.status.setText(tr("grimoire.spells.vaultl.archiveview", "Couldn't compress: {error}").format(error=str(e))
                            if not isinstance(e, archive.Cancelled) else str(e))

    page.jobs.start(tr("grimoire.spells.vaultl.archiveview", "Compressing into {name}").format(name=isolate(out.name)),
                    lambda progress: archive.compress(sources, out, fmt, level, pw, progress), done, failed)
