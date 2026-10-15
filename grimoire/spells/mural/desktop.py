# SPDX-License-Identifier: GPL-3.0-or-later
"""MuraL → Desktop tab: pick wallpapers from the library, build a playlist, apply to the desktop.

Selection order is playlist order: click wallpapers in the order you want them to play.
The Generate view draws black & white wallpapers (wallgen.py) at the screen's resolution into the library.
"""
import subprocess
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMenu, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from grimoire.i18n import ltr, tr, tr_noop
from grimoire.spells.mural import backdrop, library, plasma, wallgen
from grimoire.spells.mural.screens import Choice, ScreenTab, WrapButton, WrapCheck, load_state, save_state
from grimoire.spells.mural.storeview import StoreView
from grimoire.widgets import Slider, segments

PATH_ROLE = Qt.ItemDataRole.UserRole


class DesktopTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.setAcceptDrops(True)
        self.settings = plasma.Settings.load()
        self.order: list[str] = []          # selected paths, in the order they were picked
        self._thumb_queue: list[QListWidgetItem] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        switch = QHBoxLayout()
        switch.setContentsMargins(36, 8, 24, 0)
        switch.setSpacing(0)
        switch.addStretch(1)
        self._switch = []
        views = (tr("grimoire.spells.mural.desktop", "Library"),
                 tr("grimoire.spells.mural.desktop", "Generate"),
                 tr("grimoire.spells.mural.screens", "Community · top 100"))
        for i, name in enumerate(views):
            b = QPushButton(name)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.clicked.connect(lambda _=False, i=i: self._show_view(i))
            self._switch.append(b)
            switch.addWidget(b)
        segments(self._switch)
        root.addLayout(switch)

        self.views = QStackedWidget()
        lib_page = QWidget()
        lib_row = QHBoxLayout(lib_page)
        lib_row.setContentsMargins(0, 0, 0, 0)
        lib_row.setSpacing(0)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(36, 14, 24, 24)
        lv.addWidget(self._build_library())
        lib_row.addWidget(left, 1)
        lib_row.addWidget(self._build_panel())
        self.views.addWidget(lib_page)
        self.generate = GenerateTab(self._generated)
        self.views.addWidget(self.generate)
        store = QWidget()
        sv = QVBoxLayout(store)
        sv.setContentsMargins(36, 14, 24, 24)
        sv.addWidget(StoreView(["wallhaven-bw", "wallhaven-bc", "wallpaper"], self.reload))
        self.views.addWidget(store)
        root.addWidget(self.views, 1)

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

        self.pause = WrapCheck(tr("grimoire.spells.mural.desktop", "Pause when a window is\nfullscreen or maximized"))
        self.mute = WrapCheck(tr("grimoire.spells.mural.desktop", "Mute videos"))
        lay.addWidget(self.pause)
        lay.addWidget(self.mute)
        lay.addStretch(1)

        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
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
        for k, b in enumerate(self._switch):
            b.setChecked(k == i)

    def _generated(self, applied: bool):
        """A generated wallpaper landed in the library (and maybe on the desktop): show it there."""
        if applied:
            self.settings = plasma.Settings.load()
            self.reload()
            self._restore_selection()
        else:
            self.reload()

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


class GenerateTab(ScreenTab):
    """Generated black & white wallpapers: pick a design, tune it, and it's drawn at your screen's resolution into
    the library (so it joins playlists, Looks and shared setups like any other picture)."""
    key = "wallgen"
    context = "grimoire.spells.mural.desktop"          # wallgen.DESIGNS are marked in this context too
    subtitle = tr_noop("grimoire.spells.mural.desktop", "Wallpapers drawn for your screen, in black & white. "
                       "Each one is saved to your library.")
    apply_label = tr_noop("grimoire.spells.mural.desktop", "Set as wallpaper")
    apply_busy = tr_noop("grimoire.spells.mural.desktop", "Drawing…")

    def __init__(self, on_generated):
        self._on_generated = on_generated
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            size = screen.size() * screen.devicePixelRatio()
            self._screen = (max(640, size.width()), max(360, size.height()))
        else:
            self._screen = (1920, 1080)
        self._file = None
        super().__init__()
        saved = load_state().get(self.key, {})
        if plasma.Settings.load().items != [saved.get("file")]:       # the desktop shows something else now
            self.applied = None
            self._label_in_use()

    def designs(self):
        return wallgen.DESIGNS

    def build_options(self, lay):
        c = "grimoire.spells.mural.desktop"
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        self.tone = Choice([(k, tr(c, v[0])) for k, v in wallgen.TONES.items()], self.changed)
        self.density = Slider(1, 10, "", self.changed)
        self.grain = Slider(0, 10, "", self.changed)
        self.seed = QSpinBox()
        self.seed.setRange(1, 9999)
        self.seed.valueChanged.connect(self.changed)
        shuffle = QPushButton(tr(c, "Shuffle"))
        shuffle.setToolTip(tr(c, "Another variation of this design"))
        shuffle.clicked.connect(self._shuffle)
        seed_row = QHBoxLayout()
        seed_row.setSpacing(6)
        seed_row.addWidget(self.seed, 1)
        seed_row.addWidget(shuffle)
        self.text = QLineEdit()
        self.text.setMaxLength(60)
        self.text.setPlaceholderText("GRIMOIRE")
        self.text.textEdited.connect(self.changed)
        sw, sh = self._screen
        sizes = [("screen", tr(c, "Your screen ({size})").format(size=ltr(f"{sw} × {sh}")))]
        sizes += [(k, ltr(k.replace("x", " × "))) for k in wallgen.SIZES[1:]]
        self.size = Choice(sizes, self.changed)
        rows = [(tr(c, "Tone"), self.tone), (tr(c, "Density"), self.density), (tr(c, "Grain"), self.grain),
                (tr(c, "Variation"), seed_row), (tr(c, "Words"), self.text), (tr(c, "Size"), self.size)]
        for r, (label, w) in enumerate(rows):
            grid.addWidget(QLabel(label), r, 0)
            if isinstance(w, QHBoxLayout):
                grid.addLayout(w, r, 1)
            else:
                grid.addWidget(w, r, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        lay.addSpacing(6)
        self.add_btn = WrapButton(tr(c, "Add to library only"))
        self.add_btn.clicked.connect(self._add_only)
        lay.addWidget(self.add_btn)

    def options(self):
        return {"tone": self.tone.value(), "density": self.density.value(), "grain": self.grain.value(),
                "seed": self.seed.value(), "text": self.text.text(), "size": self.size.value()}

    def set_options(self, o):
        o = wallgen.options(o)
        self.tone.set_value(o["tone"])
        self.density.setValue(o["density"])
        self.grain.setValue(o["grain"])
        self.seed.setValue(o["seed"])
        self.text.setText(o["text"])
        self.size.set_value(o["size"])

    def _shuffle(self):
        import random
        self.seed.setValue(random.randint(1, 9999))

    def _selected(self, row, render=True):
        super()._selected(row, render)
        d = self.current()
        self.text.setEnabled(d is not None and d.id == "type")        # only Typography uses words

    def preview(self, design, o):
        return wallgen.to_qimage(wallgen.render(design.id, o, 1280, 720))

    def thumbnail(self, design, o):
        return wallgen.to_qimage(wallgen.render(design.id, o, 640, 360))

    def _make(self, design, o):
        w, h = wallgen.pixels(o.get("size", "screen"), self._screen)
        return wallgen.save(design.id, o, w, h)

    def apply(self, design, o):
        path = self._make(design, o)
        s = plasma.Settings.load()            # keep the fill, fade and video choices; just one picture now
        s.items = [str(path)]
        plasma.apply(s)
        backdrop.wallpaper.cache_clear()
        self._file = str(path)
        return tr("grimoire.spells.mural.desktop", "Set as your wallpaper ✓  (saved in your library)")

    def _on_applied(self, ok, msg):
        super()._on_applied(ok, msg)
        if ok:
            d, opts = self._pending
            save_state(self.key, {"design": d.id, "options": opts, "file": self._file})
        self._on_generated(ok)

    def _add_only(self):
        d, o = self.current(), self.options()

        def work():
            try:
                path = self._make(d, o)
            except (OSError, ValueError) as e:
                return tr("grimoire.spells.mural.desktop", "Couldn't save it: {error}").format(error=e)
            return tr("grimoire.spells.mural.desktop", "Added to your library: {name}").format(name=path.stem)

        self.add_btn.setEnabled(False)
        self.background(work, tr("grimoire.spells.mural.desktop", "Drawing…"))

    def _on_finished(self, msg):
        super()._on_finished(msg)
        self.add_btn.setEnabled(True)
        self._on_generated(False)
