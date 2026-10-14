# SPDX-License-Identifier: GPL-3.0-or-later
"""MuraL → Desktop tab: pick wallpapers from the library, build a playlist, apply to the desktop.

Selection order is playlist order: click wallpapers in the order you want them to play.
"""
import subprocess
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from grimoire.i18n import tr
from grimoire.spells.mural import library, plasma
from grimoire.spells.mural.screens import Choice
from grimoire.spells.mural.storeview import StoreView

PATH_ROLE = Qt.ItemDataRole.UserRole


class DesktopTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.setAcceptDrops(True)
        self.settings = plasma.Settings.load()
        self.order: list[str] = []          # selected paths, in the order they were picked
        self._thumb_queue: list[QListWidgetItem] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(36, 8, 24, 24)
        lv.setSpacing(14)
        switch = QHBoxLayout()
        switch.setSpacing(0)
        switch.addStretch(1)
        self._switch = []
        views = (tr("grimoire.spells.mural.desktop", "Library"),
                 tr("grimoire.spells.mural.screens", "Community · top 100"))
        for i, name in enumerate(views):
            b = QPushButton(name)
            b.setObjectName("Segment")
            b.setProperty("pos", "first" if i == 0 else "last")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.clicked.connect(lambda _=False, i=i: self._show_view(i))
            self._switch.append(b)
            switch.addWidget(b)
        lv.addLayout(switch)
        self.views = QStackedWidget()
        self.views.addWidget(self._build_library())
        self.views.addWidget(StoreView(["wallhaven-bw", "wallhaven-bc", "wallpaper"], self.reload))
        lv.addWidget(self.views, 1)
        root.addWidget(left, 1)
        root.addWidget(self._build_panel())

        self.reload()
        self._restore_selection()

    # ------------------------------------------------------------------ layout
    def _build_library(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        sub = QLabel(tr("grimoire.spells.mural.desktop", "Click wallpapers in the order you want them to play. "
                                                    "One = static, several = playlist."))
        sub.setWordWrap(True)
        sub.setObjectName("Subtitle")
        titles.addWidget(sub)
        head.addLayout(titles, 1)
        add = QPushButton(tr("grimoire.spells.mural.desktop", "Add files…"))
        add.clicked.connect(self._add_dialog)
        folder = QPushButton(tr("grimoire.spells.mural.desktop", "Open folder"))
        folder.clicked.connect(lambda: subprocess.Popen(["xdg-open", str(library.LIBRARY)]))
        head.addWidget(folder)
        head.addWidget(add)
        lay.addLayout(head)

        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setMovement(QListWidget.Movement.Static)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.grid.setIconSize(library.THUMB_SIZE)
        self.grid.setGridSize(QSize(library.THUMB_SIZE.width() + 24, library.THUMB_SIZE.height() + 46))
        self.grid.setSpacing(8)
        self.grid.setUniformItemSizes(True)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._context_menu)
        self.grid.itemSelectionChanged.connect(self._selection_changed)
        lay.addWidget(self.grid, 1)

        self.empty = QLabel(tr("grimoire.spells.mural.desktop", "Your library is empty. Drop images or videos here, "
                                                           "or click “Add files…”."))
        self.empty.setWordWrap(True)
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.empty)
        return w

    def _build_panel(self) -> QWidget:
        panel = QFrame()
        self._panel = panel
        panel.setObjectName("Panel")
        panel.setFixedWidth(300)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(14)

        self.count = QLabel()
        self.count.setObjectName("Section")
        lay.addWidget(self.count)
        self.playlist = QLabel()
        self.playlist.setObjectName("Muted")
        self.playlist.setWordWrap(True)
        lay.addWidget(self.playlist)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.interval = QSpinBox()
        self.interval.setRange(1, 1440)
        self.interval.setSuffix(tr("grimoire.spells.mural.desktop", " min"))
        self.fade = QDoubleSpinBox()
        self.fade.setRange(0, 10)
        self.fade.setSingleStep(0.2)
        self.fade.setDecimals(1)
        self.fade.setSuffix(tr("grimoire.spells.mural.desktop", " s"))
        self.order_mode = QComboBox()
        self.order_mode.addItems([tr("grimoire.spells.mural.desktop", "In order"),
                                  tr("grimoire.spells.mural.desktop", "Shuffle")])
        self.fill = Choice([(k, tr("grimoire.spells.mural.plasma", k)) for k in plasma.FILL_MODES])
        form.addRow(tr("grimoire.spells.mural.desktop", "Switch every"), self.interval)
        form.addRow(tr("grimoire.spells.mural.desktop", "Fade"), self.fade)
        form.addRow(tr("grimoire.spells.mural.desktop", "Order"), self.order_mode)
        form.addRow(tr("grimoire.spells.mural.desktop", "Fill"), self.fill)
        lay.addLayout(form)

        self.pause = QCheckBox(tr("grimoire.spells.mural.desktop", "Pause when a window is\nfullscreen or maximized"))
        self.mute = QCheckBox(tr("grimoire.spells.mural.desktop", "Mute videos"))
        lay.addWidget(self.pause)
        lay.addWidget(self.mute)
        lay.addStretch(1)

        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.apply_btn = QPushButton(tr("grimoire.spells.mural.desktop", "Apply to desktop"))
        self.apply_btn.setObjectName("Primary")
        self.apply_btn.setMinimumHeight(40)
        self.apply_btn.clicked.connect(self._apply)
        lay.addWidget(self.apply_btn)

        s = self.settings
        self.interval.setValue(s.interval_min)
        self.fade.setValue(s.fade_s)
        self.order_mode.setCurrentIndex(1 if s.shuffle else 0)
        self.fill.set_value(s.fill)
        self.pause.setChecked(s.pause_fullscreen)
        self.mute.setChecked(s.muted)
        return panel

    def _show_view(self, i: int):
        self.views.setCurrentIndex(i)
        self._panel.setVisible(i == 0)
        for k, b in enumerate(self._switch):
            b.setChecked(k == i)

    # ------------------------------------------------------------------ library
    def reload(self):
        self.grid.blockSignals(True)
        self.grid.clear()
        placeholder = QPixmap(library.THUMB_SIZE)
        placeholder.fill(QColor("#141414"))
        self._thumb_queue = []
        for path in library.items():
            label = ("▶  " if library.is_video(path) else "") + path.stem
            item = QListWidgetItem(QIcon(placeholder), label)
            item.setData(PATH_ROLE, str(path))
            item.setToolTip(path.name)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.grid.addItem(item)
            self._thumb_queue.append(item)
        self.grid.blockSignals(False)
        self.order = [p for p in self.order if Path(p).exists()]
        for i in range(self.grid.count()):
            self.grid.item(i).setSelected(self.grid.item(i).data(PATH_ROLE) in self.order)
        self.empty.setVisible(self.grid.count() == 0)
        self._refresh_panel()
        QTimer.singleShot(0, self._load_next_thumb)

    def _load_next_thumb(self):
        """Load thumbnails one per event-loop tick so the window stays responsive."""
        while self._thumb_queue:
            item = self._thumb_queue.pop(0)
            try:
                img = library.thumbnail(Path(item.data(PATH_ROLE)))
            except RuntimeError:    # item deleted (library reloaded)
                continue
            if not img.isNull():
                pm = QPixmap.fromImage(img)
                icon = QIcon(pm)
                icon.addPixmap(pm, QIcon.Mode.Selected)   # no blue selection tint
                item.setIcon(icon)
            QTimer.singleShot(0, self._load_next_thumb)
            return

    def _add_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, tr("grimoire.spells.mural.desktop", "Add wallpapers"), str(Path.home() / "Pictures"),
            tr("grimoire.spells.mural.desktop", "Images & videos ({patterns})").format(
                patterns="*.png *.jpg *.jpeg *.webp *.bmp *.avif *.mp4 *.webm *.mkv *.mov *.m4v *.gif"))
        if files:
            library.add(files)
            self.reload()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        library.add(u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile())
        self.reload()

    def _context_menu(self, pos):
        item = self.grid.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        remove = menu.addAction(tr("grimoire.spells.mural.desktop", "Remove from library"))
        if menu.exec(self.grid.mapToGlobal(pos)) == remove:
            path = item.data(PATH_ROLE)
            self.order = [p for p in self.order if p != path]
            library.remove(Path(path))
            self.reload()

    # ------------------------------------------------------------------ selection / apply
    def _restore_selection(self):
        self.order = [p for p in self.settings.items if Path(p).exists()]
        self.grid.blockSignals(True)
        for i in range(self.grid.count()):
            item = self.grid.item(i)
            item.setSelected(item.data(PATH_ROLE) in self.order)
        self.grid.blockSignals(False)
        self._refresh_panel()

    def _selection_changed(self):
        selected = {i.data(PATH_ROLE) for i in self.grid.selectedItems()}
        self.order = [p for p in self.order if p in selected] + [p for p in sorted(selected) if p not in self.order]
        self._refresh_panel()

    def _refresh_panel(self):
        n = len(self.order)
        if n == 0:
            self.count.setText(tr("grimoire.spells.mural.desktop", "NOTHING SELECTED"))
        elif n == 1:
            self.count.setText(tr("grimoire.spells.mural.desktop", "1 WALLPAPER"))
        else:
            self.count.setText(tr("grimoire.spells.mural.desktop", "PLAYLIST · %n WALLPAPERS", n=n))
        self.playlist.setText("\n".join(f"{i + 1}.  {Path(p).stem}" for i, p in enumerate(self.order[:8]))
                              + ("\n…" if n > 8 else ""))
        for w in (self.interval, self.order_mode):
            w.setEnabled(n > 1)
        self.apply_btn.setEnabled(n > 0)

    def _apply(self):
        s = plasma.Settings(
            items=list(self.order),
            interval_min=self.interval.value(),
            fade_s=self.fade.value(),
            shuffle=self.order_mode.currentIndex() == 1,
            fill=self.fill.value(),
            pause_fullscreen=self.pause.isChecked(),
            muted=self.mute.isChecked(),
        )
        try:
            plasma.apply(s)
        except (RuntimeError, OSError) as e:
            self.status.setText(tr("grimoire.spells.mural.screens", "Couldn't apply: {error}").format(error=e))
            return
        self.settings = s
        self.status.setText(tr("grimoire.spells.mural.desktop", "Applied to your desktop ✓"))
        QTimer.singleShot(4000, lambda: self.status.setText(""))
