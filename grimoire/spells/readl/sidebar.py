# SPDX-License-Identifier: GPL-3.0-or-later
"""The reader's side panel: table of contents, page thumbnails (PDF) and bookmarks."""
from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QInputDialog, QLabel, QListView, QListWidget,
                               QListWidgetItem, QMenu, QPushButton, QStackedWidget, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout)

from grimoire.i18n import tr
from grimoire.widgets import segments

THUMB_W = 132


class Sidebar(QFrame):
    go_toc = Signal(object)          # the toc entry's target
    go_page = Signal(int)
    go_mark = Signal(object)         # a bookmark's pos
    add_mark = Signal()
    remove_mark = Signal(object)
    rename_mark = Signal(object, str)

    def __init__(self):
        super().__init__()
        self.setObjectName("ReadSide")
        self.setMinimumWidth(220)
        self.renderer = None
        self.sizes = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 12, 10, 10)
        lay.setSpacing(10)
        tabs = QHBoxLayout()
        tabs.setSpacing(0)
        self.tabs = {}
        for tid, name in (("contents", tr("grimoire.spells.readl.sidebar", "Contents")),
                          ("pages", tr("grimoire.spells.readl.sidebar", "Pages")),
                          ("bookmarks", tr("grimoire.spells.readl.sidebar", "Bookmarks"))):
            b = QPushButton(name)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, t=tid: self.show_tab(t))
            tabs.addWidget(b, 1)
            self.tabs[tid] = b
        lay.addLayout(tabs)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)

        self.toc = QTreeWidget()
        self.toc.setHeaderHidden(True)
        self.toc.setObjectName("ReadToc")
        self.toc.setIndentation(14)
        self.toc.setUniformRowHeights(True)
        self.toc.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.toc.itemActivated.connect(lambda it, _c: self.go_toc.emit(it.data(0, Qt.ItemDataRole.UserRole)))
        self.toc.itemClicked.connect(lambda it, _c: self.go_toc.emit(it.data(0, Qt.ItemDataRole.UserRole)))
        self.toc_empty = QLabel(tr("grimoire.spells.readl.sidebar", "This document has no table of contents."))
        self.toc_empty.setObjectName("Muted")
        self.toc_empty.setWordWrap(True)
        self.toc_empty.setAlignment(Qt.AlignmentFlag.AlignTop)
        toc_box = QStackedWidget()
        toc_box.addWidget(self.toc)
        toc_box.addWidget(self.toc_empty)
        self.toc_box = toc_box

        self.pages = QListWidget()
        self.pages.setObjectName("ReadThumbs")
        self.pages.setViewMode(QListView.ViewMode.IconMode)
        self.pages.setFlow(QListView.Flow.TopToBottom)
        self.pages.setWrapping(False)
        self.pages.setMovement(QListView.Movement.Static)
        self.pages.setResizeMode(QListView.ResizeMode.Adjust)
        self.pages.setUniformItemSizes(True)
        self.pages.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.pages.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.pages.itemClicked.connect(lambda it: self.go_page.emit(it.data(Qt.ItemDataRole.UserRole)))
        self.pages.itemActivated.connect(lambda it: self.go_page.emit(it.data(Qt.ItemDataRole.UserRole)))
        self.pages.verticalScrollBar().valueChanged.connect(lambda _: self._thumb_timer.start())
        self._thumb_timer = QTimer(self, singleShot=True, interval=80, timeout=self._want_thumbs)
        self._thumb_keys = {}

        marks = QFrame()
        ml = QVBoxLayout(marks)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(8)
        self.marks = QListWidget()
        self.marks.setObjectName("ReadMarks")
        self.marks.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.marks.customContextMenuRequested.connect(self._mark_menu)
        self.marks.itemActivated.connect(lambda it: self.go_mark.emit(it.data(Qt.ItemDataRole.UserRole)))
        self.marks.itemClicked.connect(lambda it: self.go_mark.emit(it.data(Qt.ItemDataRole.UserRole)))
        self.marks_empty = QLabel(tr("grimoire.spells.readl.sidebar",
                                     "No bookmarks yet. Ctrl+B marks the place you're reading."))
        self.marks_empty.setObjectName("Muted")
        self.marks_empty.setWordWrap(True)
        add = QPushButton(tr("grimoire.spells.readl.sidebar", "Bookmark this place"))
        add.clicked.connect(self.add_mark.emit)
        ml.addWidget(self.marks, 1)
        ml.addWidget(self.marks_empty)
        ml.addStretch(0)
        ml.addWidget(add)

        for w in (toc_box, self.pages, marks):
            self.stack.addWidget(w)
        segments(list(self.tabs.values()))
        self.show_tab("contents")

    # ------------------------------------------------------------ tabs
    def show_tab(self, tid: str):
        if tid == "pages" and self.renderer is None:
            tid = "contents"
        for k, b in self.tabs.items():
            b.setChecked(k == tid)
        self.stack.setCurrentIndex(("contents", "pages", "bookmarks").index(tid))
        self.current = tid
        if tid == "pages":
            self._thumb_timer.start()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Delete and self.marks.hasFocus() and self.marks.currentItem():
            self.remove_mark.emit(self.marks.currentItem().data(Qt.ItemDataRole.UserRole))
            return
        super().keyPressEvent(e)

    # ------------------------------------------------------------ contents
    def set_toc(self, entries: list):
        """entries: [(level, title, target)]."""
        self.toc.clear()
        self._toc_items = []
        parents = []
        for level, title, target in entries:
            while parents and parents[-1][0] >= level:
                parents.pop()
            item = QTreeWidgetItem([title])
            item.setToolTip(0, title)
            item.setData(0, Qt.ItemDataRole.UserRole, target)
            if parents:
                parents[-1][1].addChild(item)
            else:
                self.toc.addTopLevelItem(item)
            parents.append((level, item))
            self._toc_items.append((target, item))
        self.toc.expandToDepth(0)
        self.toc_box.setCurrentIndex(0 if entries else 1)

    def follow(self, before):
        """Mark the section being read: the last entry for which before(target) is true."""
        cur = None
        for target, item in getattr(self, "_toc_items", []):
            if before(target):
                cur = item
        if cur is not None and cur is not self.toc.currentItem():
            self.toc.blockSignals(True)
            self.toc.setCurrentItem(cur)
            self.toc.scrollToItem(cur)
            self.toc.blockSignals(False)

    # ------------------------------------------------------------ pages
    def set_pages(self, renderer, sizes: list, labels: list):
        self.renderer, self.sizes = renderer, sizes
        self.pages.clear()
        self._thumb_keys = {}
        self.tabs["pages"].setVisible(renderer is not None)
        segments([b for b in self.tabs.values() if not b.isHidden()])
        if renderer is None:
            if self.current == "pages":
                self.show_tab("contents")
            return
        renderer.ready.connect(self._thumb_ready)
        h = max(int(THUMB_W * s[1] / s[0]) for s in sizes[:200])
        self.pages.setIconSize(QSize(THUMB_W, h))
        self.pages.setGridSize(QSize(THUMB_W + 24, h + 34))
        blank = QPixmap(THUMB_W, h)
        blank.fill(QColor("#161616"))
        icon = QIcon(blank)
        for i, label in enumerate(labels):
            it = QListWidgetItem(icon, label)
            it.setData(Qt.ItemDataRole.UserRole, i)
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.pages.addItem(it)
        self._thumb_timer.start()

    def mark_page(self, page: int):
        if 0 <= page < self.pages.count():
            self.pages.blockSignals(True)
            self.pages.setCurrentRow(page)
            if self.current == "pages":
                self.pages.scrollToItem(self.pages.item(page), QAbstractItemView.ScrollHint.EnsureVisible)
            self.pages.blockSignals(False)

    def _want_thumbs(self):
        if self.renderer is None or self.current != "pages" or not self.isVisible():
            return
        vp = self.pages.viewport().rect()
        first = self.pages.indexAt(vp.topLeft() + QPoint(4, 4)).row()
        last = self.pages.indexAt(vp.bottomLeft() + QPoint(4, -4)).row()
        if first < 0:
            first = 0
        if last < 0:
            last = min(self.pages.count() - 1, first + 8)
        dpr = self.devicePixelRatioF()
        want = set()
        from grimoire.spells.readl.pageview import Renderer
        for i in range(max(0, first - 2), min(self.pages.count(), last + 3)):
            if i in self._thumb_keys and self._thumb_keys[i] is None:
                continue                                       # already shown
            key = Renderer.key(i, THUMB_W * dpr / self.sizes[i][0], "day")
            self._thumb_keys[i] = key
            want.add(key)
            pm = self.renderer.get(key)
            if pm is not None:
                self._thumb_ready(key)
            else:
                self.renderer.request(key, thumb=True)
        self.renderer.thumb_wanted = want

    def _thumb_ready(self, key):
        page = key[0]
        if self._thumb_keys.get(page) != key:
            return
        pm = self.renderer.get(key) if self.renderer else None
        if pm is None:
            return
        pm = QPixmap(pm)
        pm.setDevicePixelRatio(self.devicePixelRatioF())
        icon = QIcon(pm)
        icon.addPixmap(pm, QIcon.Mode.Selected)          # no tint over the current page
        self.pages.item(page).setIcon(icon)
        self._thumb_keys[page] = None

    def showEvent(self, e):
        super().showEvent(e)
        self._thumb_timer.start()

    # ------------------------------------------------------------ bookmarks
    def set_marks(self, marks: list, describe):
        self.marks.clear()
        for b in marks:
            it = QListWidgetItem(f"{b['label']}\n{describe(b['pos'])}")
            it.setData(Qt.ItemDataRole.UserRole, b["pos"])
            it.setToolTip(b["label"])
            self.marks.addItem(it)
        self.marks.setVisible(bool(marks))
        self.marks_empty.setVisible(not marks)

    def _mark_menu(self, pt):
        it = self.marks.itemAt(pt)
        if not it:
            return
        pos = it.data(Qt.ItemDataRole.UserRole)
        m = QMenu(self)
        m.addAction(tr("grimoire.spells.readl.sidebar", "Go there"), lambda: self.go_mark.emit(pos))
        m.addAction(tr("grimoire.spells.readl.sidebar", "Rename…"), lambda: self._rename(it, pos))
        m.addSeparator()
        m.addAction(tr("grimoire.spells.readl.sidebar", "Remove bookmark"), lambda: self.remove_mark.emit(pos))
        m.exec(self.marks.viewport().mapToGlobal(pt))

    def _rename(self, it, pos):
        old = it.toolTip()
        text, ok = QInputDialog.getText(self, tr("grimoire.spells.readl.sidebar", "Rename bookmark"),
                                        tr("grimoire.spells.readl.sidebar", "Name"), text=old)
        if ok and text.strip():
            self.rename_mark.emit(pos, text.strip())
