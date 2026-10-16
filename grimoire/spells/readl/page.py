# SPDX-License-Identifier: GPL-3.0-or-later
"""ReadL page: the library (what you read lately, with covers and how far you got) and the reader.

The recent list and covers are read on worker threads; a file that moved shows dimmed until it comes back or you take
it off the list (the file itself is never touched).
"""
import os
import time
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListView,
                               QListWidget, QListWidgetItem, QMenu, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.fsutil import tilde
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.readl import covers, library, pdfdoc
from grimoire.spells.readl.reader import Reader

ICON = QSize(120, 170)
FILTER = "*.pdf *.epub *.md *.markdown *.txt"


class _Sig(QObject):
    listed = Signal(object)          # [(entry, exists)]
    covers = Signal(object)          # {path: QImage}


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _own(text: str) -> str:
    """A title or path in a right-to-left layout: kept in its own direction, but the line still starts at the right
    like the labels around it."""
    return "\u200f" + i18n.isolate(text) if i18n.rtl() else text


def ago(ts: float) -> str:
    d = max(0, time.time() - ts)
    if d < 3600:
        return tr("grimoire.spells.readl.page", "just now")
    if d < 86400:
        return tr("grimoire.spells.readl.page", "%n hour(s) ago", n=int(d // 3600))
    if d < 86400 * 60:
        return tr("grimoire.spells.readl.page", "%n day(s) ago", n=int(d // 86400))
    return tr("grimoire.spells.readl.page", "%n month(s) ago", n=int(d // (86400 * 30)))


def progress_text(e: dict) -> str:
    if e["progress"] >= 0.995:
        return tr("grimoire.spells.readl.page", "Finished")
    if e["progress"] < 0.005:
        return tr("grimoire.spells.readl.page", "Not started")
    return tr("grimoire.spells.readl.page", "{pct}% read").format(pct=max(1, round(e["progress"] * 100)))


def with_bar(img: QImage, progress: float, size: QSize, dim=False) -> QPixmap:
    """The cover at size, with a thin reading-progress line along its foot."""
    dpr = QApplication.instance().devicePixelRatio() if QApplication.instance() else 1.0
    pm = QPixmap(size * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(0, 0, size.width(), size.height())
    if img is not None and not img.isNull():
        p.drawImage(r, img)
    else:
        p.fillRect(r, QColor("#141414"))
    if dim:
        p.fillRect(r, QColor(0, 0, 0, 160))
    if progress > 0:
        p.fillRect(QRectF(0, r.height() - 4, r.width(), 4), QColor(0, 0, 0, 200))
        p.fillRect(QRectF(0, r.height() - 4, r.width() * min(1.0, progress), 4), QColor("#f2f2f2"))
    p.setPen(QColor("#262626"))
    p.drawRect(r.adjusted(0.5, 0.5, -0.5, -0.5))
    p.end()
    return pm


class LibraryView(QWidget):
    open_path = Signal(str)
    open_dialog = Signal()

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.entries: list = []
        self.exists: dict = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 18)
        root.setSpacing(16)
        head = QHBoxLayout()
        head.setSpacing(10)
        title = _label("ReadL", "Title")
        head.addWidget(title)
        head.addStretch(1)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("grimoire.spells.readl.page", "Filter by title or author"))
        self.filter.setClearButtonEnabled(True)
        self.filter.setMinimumWidth(240)
        self.filter.setMaximumWidth(320)
        self.filter.textChanged.connect(lambda _: self.fill())
        head.addWidget(self.filter)
        open_btn = QPushButton(tr("grimoire.spells.readl.page", "Open a file…"))
        open_btn.setObjectName("Primary")
        open_btn.setToolTip("Ctrl+O")
        open_btn.clicked.connect(self.open_dialog.emit)
        head.addWidget(open_btn)
        root.addLayout(head)

        # the book you were reading
        self.hero = QFrame()
        self.hero.setObjectName("Row")
        hl = QHBoxLayout(self.hero)
        hl.setContentsMargins(16, 16, 20, 16)
        hl.setSpacing(18)
        self.hero_cover = QLabel()
        self.hero_cover.setFixedSize(ICON * 0.8)
        hl.addWidget(self.hero_cover)
        text = QVBoxLayout()
        text.setSpacing(4)
        text.addWidget(_label(tr("grimoire.spells.readl.page", "CONTINUE READING"), "Section"))
        self.hero_title = _label("", "SectionTitle", wrap=True)
        self.hero_sub = _label("", "Muted", wrap=True)
        self.hero_where = _label("", "Muted", wrap=True)
        for w in (self.hero_title, self.hero_sub, self.hero_where):
            text.addWidget(w)
        text.addStretch(1)
        hl.addLayout(text, 1)
        self.hero_btn = QPushButton(tr("grimoire.spells.readl.page", "Continue"))
        self.hero_btn.setObjectName("Primary")
        self.hero_btn.clicked.connect(lambda: self.entries and self.open_path.emit(self.entries[0]["path"]))
        hl.addWidget(self.hero_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.hero)

        self.section = _label(tr("grimoire.spells.readl.page", "RECENT"), "Section")
        root.addWidget(self.section)
        self.grid = QListWidget()
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setIconSize(ICON)
        self.grid.setGridSize(QSize(ICON.width() + 34, ICON.height() + 62))
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setUniformItemSizes(True)
        self.grid.setWordWrap(True)
        self.grid.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.grid.setSpacing(6)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._menu)
        self.grid.itemActivated.connect(self._activated)
        self.grid.itemClicked.connect(self._activated)
        root.addWidget(self.grid, 1)

        self.empty = QWidget()
        el = QVBoxLayout(self.empty)
        el.addStretch(1)
        for t, name in ((tr("grimoire.spells.readl.page", "Nothing here yet"), "PageHeading"),
                        (tr("grimoire.spells.readl.page", "Open a PDF, EPUB, Markdown or text file, or drop one "
                                                          "here. ReadL remembers where you stopped."), "Muted")):
            lab = _label(t, name, wrap=True)
            lab.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            el.addWidget(lab)
        el.addStretch(2)
        root.addWidget(self.empty, 1)

        self.hint = QFrame()
        self.hint.setObjectName("Row")
        nl = QHBoxLayout(self.hint)
        nl.setContentsMargins(16, 10, 12, 10)
        nl.addWidget(_label(tr("grimoire.spells.readl.page", "PDFs need QtPdf. Install it with:"), "Muted"))
        cmd = _label(pdfdoc.APT, "Value")
        cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        nl.addWidget(cmd, 1)
        copy = QPushButton(tr("grimoire.spells.readl.page", "Copy command"))
        copy.clicked.connect(lambda: QApplication.clipboard().setText(pdfdoc.APT))
        nl.addWidget(copy)
        self.hint.setVisible(not pdfdoc.available())
        root.addWidget(self.hint)
        self.pix: dict = {}

    # ------------------------------------------------------------ filling
    def set_entries(self, listed):
        self.entries = [e for e, _ in listed]
        self.exists = {e["path"]: ok for e, ok in listed}
        self.fill()

    def fill(self):
        q = self.filter.text().strip().lower()
        shown = [e for e in self.entries if not q or q in e["title"].lower() or q in e["author"].lower()
                 or q in os.path.basename(e["path"]).lower()]
        self.grid.clear()
        for e in shown:
            ok = self.exists.get(e["path"], True)
            sub = progress_text(e) if ok else tr("grimoire.spells.readl.page", "Not found")
            it = QListWidgetItem(self.icon(e), f"{e['title']}\n{sub}")
            it.setData(Qt.ItemDataRole.UserRole, e["path"])
            it.setToolTip("\n".join(x for x in (e["title"], e["author"], tilde(e["path"]),
                                                 tr("grimoire.spells.readl.page", "Opened {when}")
                                                 .format(when=ago(e["opened"])) if e["opened"] else "") if x))
            if not ok:
                it.setForeground(QColor("#5a5a5a"))
            self.grid.addItem(it)
        has = bool(self.entries)
        self.grid.setVisible(has)
        self.section.setVisible(has)
        self.empty.setVisible(not has)
        self.hero.setVisible(has and not q)
        if has:
            e = self.entries[0]
            ok = self.exists.get(e["path"], True)
            self.hero_cover.setPixmap(with_bar(self.page.covers.get(e["path"]), e["progress"], ICON * 0.8, not ok))
            self.hero_title.setText(_own(e["title"]))
            self.hero_sub.setText(_own(e["author"] or tilde(e["path"])))
            where = progress_text(e)
            if e["pages"] and e["kind"] == "pdf" and isinstance(e["pos"].get("page"), int):
                where = tr("grimoire.spells.readl.page", "Page {page} of {total}").format(
                    page=e["pos"]["page"] + 1, total=e["pages"]) + " · " + where
            self.hero_where.setText(where if ok else tr("grimoire.spells.readl.page",
                                                         "This file was moved or deleted."))
            self.hero_btn.setEnabled(ok)

    def icon(self, e) -> QIcon:
        ok = self.exists.get(e["path"], True)
        k = (e["path"], round(e["progress"], 3), ok, e["path"] in self.page.covers)
        if k not in self.pix:
            self.pix[k] = QIcon(with_bar(self.page.covers.get(e["path"]), e["progress"], ICON, not ok))
        return self.pix[k]

    def refresh_icons(self):
        for i in range(self.grid.count()):
            it = self.grid.item(i)
            e = next((x for x in self.entries if x["path"] == it.data(Qt.ItemDataRole.UserRole)), None)
            if e:
                it.setIcon(self.icon(e))
        if self.entries:
            e = self.entries[0]
            self.hero_cover.setPixmap(with_bar(self.page.covers.get(e["path"]), e["progress"], ICON * 0.8,
                                               not self.exists.get(e["path"], True)))

    # ------------------------------------------------------------ actions
    def _activated(self, it):
        path = it.data(Qt.ItemDataRole.UserRole)
        if not self.exists.get(path, True) and not os.path.isfile(path):
            self.page.say(tr("grimoire.spells.readl.page", "{name} isn't there any more. Right-click it to take "
                                                           "it off the list.").format(
                name=i18n.isolate(os.path.basename(path))))
            return
        self.open_path.emit(path)

    def _menu(self, pt):
        it = self.grid.itemAt(pt)
        if not it:
            return
        path = it.data(Qt.ItemDataRole.UserRole)
        m = QMenu(self)
        m.addAction(tr("grimoire.spells.readl.page", "Open"), lambda: self._activated(it))
        folder = os.path.dirname(path)
        a = m.addAction(tr("grimoire.spells.readl.page", "Show in folder"),
                        lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))
        a.setEnabled(os.path.isdir(folder))
        m.addAction(tr("grimoire.spells.readl.page", "Copy location"),
                    lambda: QApplication.clipboard().setText(path))
        m.addSeparator()
        m.addAction(tr("grimoire.spells.readl.page", "Remove from list"), lambda: self.page.forget(path))
        m.exec(self.grid.viewport().mapToGlobal(pt))


class ReadLPage(QWidget):
    titleChanged = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.setAcceptDrops(True)
        self.sig = _Sig()
        self.covers: dict = {}
        self._covering: set = set()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.stack = QStackedWidget()
        self.library = LibraryView(self)
        self.reader = Reader()
        self.stack.addWidget(self.library)
        self.stack.addWidget(self.reader)
        root.addWidget(self.stack, 1)
        self.toast = _label("", "Toast", wrap=True)
        self.toast.hide()
        root.addWidget(self.toast)
        self._toast_timer = QTimer(self, singleShot=True, interval=6000, timeout=self.toast.hide)
        self.library.open_path.connect(self.open_file)
        self.library.open_dialog.connect(self.open_dialog)
        self.reader.back.connect(self.show_library)
        self.reader.openRequested.connect(self.open_dialog)
        self.reader.titleChanged.connect(self.titleChanged.emit)
        self.sig.listed.connect(self.library.set_entries)
        self.sig.listed.connect(self._want_covers)
        self.sig.covers.connect(self._covers)
        from PySide6.QtGui import QKeySequence, QShortcut
        sc = QShortcut(QKeySequence("Ctrl+O"), self.library)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.open_dialog)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.reader.save_place)

    # ------------------------------------------------------------ library
    def show_library(self):
        self.stack.setCurrentWidget(self.library)
        self.titleChanged.emit("")
        self.scan()

    def scan(self):
        def work():
            items = library.recent()
            return [(e, os.path.isfile(e["path"])) for e in items]
        POOL.start(Job(work, self.sig.listed.emit))

    def _want_covers(self, listed):
        todo = [(e["path"], e["kind"], e["title"]) for e, ok in listed
                if e["path"] not in self.covers and e["path"] not in self._covering][:60]
        if not todo:
            return
        self._covering.update(p for p, _, _ in todo)

        def work():
            _prune()
            out = {}
            for path, kind, title in todo:
                try:
                    out[path] = covers.make(path, kind, title)
                except Exception:
                    continue
                if len(out) >= 6:                 # show them as they come
                    self.sig.covers.emit(out)
                    out = {}
            return out
        POOL.start(Job(work, self.sig.covers.emit))

    def _covers(self, images: dict):
        self.covers.update(images)
        self._covering.difference_update(images)
        self.library.refresh_icons()

    def forget(self, path: str):
        library.forget(path)
        self.scan()

    # ------------------------------------------------------------ opening
    def open_file(self, path: str):
        path = str(Path(path).expanduser())
        self.stack.setCurrentWidget(self.reader)
        self.covers.pop(library.key(path), None)          # its progress bar changes; the cover is cached on disk
        self.reader.open(path)

    def open_dialog(self):
        last = self.reader.path or (self.library.entries[0]["path"] if self.library.entries else "")
        start = os.path.dirname(last) if last and os.path.isdir(os.path.dirname(last)) else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, tr("grimoire.spells.readl.page", "Open a document"), start,
            tr("grimoire.spells.readl.page", "Documents ({patterns})").format(patterns=FILTER) + ";;"
            + tr("grimoire.spells.readl.page", "All files ({patterns})").format(patterns="*"))
        if path:
            self.open_file(path)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and any(u.isLocalFile() for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if files:
            self.open_file(files[0])

    def say(self, text: str):
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start()

    def showEvent(self, e):
        super().showEvent(e)
        if self.stack.currentWidget() is self.library:
            self.scan()

    def hideEvent(self, e):
        super().hideEvent(e)
        if not self.reader._full:
            self.reader.save_place()


def _prune(keep: int = 400):
    """Old covers go once there are more than keep (they're only a cache of pictures of your files)."""
    d = library.covers_dir()
    try:
        files = sorted(d.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for f in files[keep:]:
        try:
            f.unlink()
        except OSError:
            pass
