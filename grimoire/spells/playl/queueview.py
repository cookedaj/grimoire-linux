# SPDX-License-Identifier: GPL-3.0-or-later
"""The queue beside the stage: drag to reorder, double-click to play, Delete to take out, drop files to add."""
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
                               QToolButton, QVBoxLayout)

from grimoire.glyphs import glyph
from grimoire.i18n import tr
from grimoire.spells.playl import media
from grimoire.widgets import plain_tip

ENTRY = Qt.ItemDataRole.UserRole
ROW = Qt.ItemDataRole.UserRole + 1


class QueueList(QListWidget):
    reordered = Signal(list)          # the old row of each entry, in the new order
    dropped = Signal(list)            # paths/URLs dropped from outside

    def __init__(self):
        super().__init__()
        self.setObjectName("Queue")
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setUniformItemSizes(True)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.setIconSize(QSize(14, 14))
        self.model().rowsMoved.connect(lambda *a: QTimer.singleShot(0, self._moved))

    def _moved(self):
        order = [self.item(i).data(ROW) for i in range(self.count())]
        if order != list(range(len(order))):
            self.reordered.emit(order)

    def dragEnterEvent(self, e):
        if e.source() is not self and e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.source() is not self and e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.source() is not self and e.mimeData().hasUrls():
            urls = [u.toLocalFile() if u.isLocalFile() else u.toString() for u in e.mimeData().urls()]
            self.dropped.emit(urls)
            e.acceptProposedAction()
            return
        super().dropEvent(e)


class QueuePanel(QFrame):
    """Lists the player's queue; changes go back to the player, which says when to redraw."""

    def __init__(self, player, open_menu: QMenu | None = None):
        super().__init__()
        self.player = player
        self.setObjectName("Panel")
        self.setMinimumWidth(240)
        self.setMaximumWidth(360)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 16, 10, 12)
        lay.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel(tr("grimoire.spells.playl.queueview", "Queue"))
        title.setObjectName("SectionTitle")
        head.addWidget(title)
        self.count = QLabel()
        self.count.setObjectName("Muted")
        head.addWidget(self.count)
        head.addStretch(1)
        if open_menu is not None:
            add = QToolButton()
            add.setObjectName("Tool")
            add.setIcon(glyph("plus", 18))
            add.setToolTip(tr("grimoire.spells.playl.queueview", "Add to the queue"))
            add.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            add.setMenu(open_menu)
            add.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0; }")
            head.addWidget(add)
        clear = QToolButton()
        clear.setObjectName("Tool")
        clear.setIcon(glyph("close", 18))
        clear.setToolTip(tr("grimoire.spells.playl.queueview", "Clear the queue"))
        clear.clicked.connect(player.clear)
        head.addWidget(clear)
        lay.addLayout(head)
        self.list = QueueList()
        self.list.itemActivated.connect(lambda it: player.play_index(self.list.row(it)))
        self.list.reordered.connect(player.reorder)
        self.list.dropped.connect(lambda paths: player.open(media.gather(paths), replace=False))
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.list, 1)
        self.empty = QLabel(tr("grimoire.spells.playl.queueview",
                               "The queue is empty. Drop files here, or pick songs in the library."))
        self.empty.setObjectName("Muted")
        self.empty.setWordWrap(True)
        lay.addWidget(self.empty)
        self.delete = QAction(self)
        self.delete.setShortcut(Qt.Key.Key_Delete)
        self.delete.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.delete.triggered.connect(self._remove_selected)
        self.list.addAction(self.delete)
        player.queue_changed.connect(self.refresh)
        player.current_changed.connect(self._mark)
        player.media_changed.connect(self._titled)
        self.refresh()

    def _label(self, entry: str) -> str:
        known = self.player.titles.get(entry)
        if known and known.get("title"):
            return " — ".join(x for x in (known.get("artist"), known["title"]) if x)
        return media.display_name(entry)

    def refresh(self):
        self.list.blockSignals(True)
        self.list.clear()
        for i, entry in enumerate(self.player.queue):
            it = QListWidgetItem(self._label(entry))
            it.setData(ENTRY, entry)
            it.setData(ROW, i)
            it.setToolTip(plain_tip(entry))
            self.list.addItem(it)
        self.list.blockSignals(False)
        n = len(self.player.queue)
        self.count.setText(str(n) if n else "")
        self.empty.setVisible(n == 0)
        self._mark(self.player.index)

    def _mark(self, index: int):
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setData(ROW, i)
            cur = i == index
            f = QFont(it.font())
            f.setBold(cur)
            it.setFont(f)
            it.setIcon(glyph("play", 14) if cur else glyph("", 14))
            it.setForeground(QColor("#ffffff") if cur else QColor("#a8a8a8"))
        if 0 <= index < self.list.count():
            self.list.scrollToItem(self.list.item(index))

    def _titled(self, info: dict):
        """mpv found the real title: show it for that row."""
        i = info.get("index", -1) if info else -1
        if 0 <= i < self.list.count() and info.get("title"):
            parts = [info.get("artist"), info["title"]] if info.get("kind") == "audio" else [info["title"]]
            self.list.item(i).setText(" — ".join(x for x in parts if x))

    def _rows(self) -> list[int]:
        return sorted(self.list.row(it) for it in self.list.selectedItems())

    def _remove_selected(self):
        rows = self._rows()
        if rows:
            self.player.remove(rows)

    def _menu(self, pos):
        it = self.list.itemAt(pos)
        m = QMenu(self)
        if it:
            row = self.list.row(it)
            m.addAction(tr("grimoire.spells.playl.queueview", "Play"), lambda: self.player.play_index(row))
            m.addAction(tr("grimoire.spells.playl.queueview", "Remove from the queue"), self._remove_selected)
            m.addSeparator()
        m.addAction(tr("grimoire.spells.playl.queueview", "Clear the queue"), self.player.clear)
        m.exec(self.list.viewport().mapToGlobal(pos))
