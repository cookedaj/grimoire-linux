# SPDX-License-Identifier: GPL-3.0-or-later
"""GameL page: every installed game (Steam and its non-Steam shortcuts, Heroic, Lutris, itch, Bottles, Roblox,
Flatpak and native menu games) in one grid or list, with search, sorting and a details panel (play, Protontricks,
open its folder in VaultL); plus the MangoHud overlay, Performance mode (both manual switches) and the Proton panel.

The library is read on a worker thread each time the page is shown; covers are turned gray (and cached) on a worker
too. Nothing here changes anything on its own when a game starts.
"""
import html
import os

from PySide6.QtCore import QDate, QLocale, QObject, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QStackedWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from grimoire import i18n
from grimoire.fsutil import human, tilde
from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.gamel import launch, library, overlay, proton
from grimoire.spells.gamel.library import SOURCES, Game
from grimoire.spells.gamel.protonview import ProtonPanel
from grimoire.widgets import Switch

COVER = QSize(240, 360)          # covers are made at this size, then shown smaller
GRID_ICON = QSize(120, 180)
# shown with tr("grimoire.spells.gamel.page", …); launcher names stay as they are
FILTERS = [("all", tr_noop("grimoire.spells.gamel.page", "All games")),
           ("steam", "Steam"), ("heroic", "Heroic"), ("lutris", "Lutris"), ("itch", "itch"), ("bottles", "Bottles"),
           ("roblox", "Roblox"), ("flatpak", "Flatpak"), ("native", tr_noop("grimoire.spells.gamel.page", "Native"))]
SORT_NAMES = {"name": tr_noop("grimoire.spells.gamel.page", "Name"),
              "last": tr_noop("grimoire.spells.gamel.page", "Last played"),
              "size": tr_noop("grimoire.spells.gamel.page", "Size"),
              "playtime": tr_noop("grimoire.spells.gamel.page", "Playtime")}


class _Signals(QObject):
    scanned = Signal(object)      # (games, problems)
    covers = Signal(object)       # {key: QImage}
    sized = Signal(object)        # (key, bytes)
    perf = Signal(object)         # (on, result)


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)      # game names, paths and errors come from launcher files
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _date(d) -> str:
    """An older "last played" day, in the app's language."""
    fmt = tr("grimoire.spells.gamel.page", "dd MMM yyyy", "QLocale date format")
    return QLocale().toString(QDate(d.year, d.month, d.day), fmt)


def _ago(ts: float) -> str:
    return library.ago(ts, date=_date)


def _row(title: str, sub: str, *controls, below: QWidget | None = None) -> QFrame:
    row = QFrame()
    row.setObjectName("Row")
    outer = QVBoxLayout(row)
    outer.setContentsMargins(18, 12, 16, 12)
    outer.setSpacing(10)
    lay = QHBoxLayout()
    lay.setSpacing(12)
    text = QVBoxLayout()
    text.setSpacing(3)
    text.addWidget(_label(title, "RowTitle"))
    if sub:
        text.addWidget(_label(sub, "Muted", wrap=True))
    lay.addLayout(text, 1)
    for c in controls:
        lay.addWidget(c, 0, Qt.AlignmentFlag.AlignVCenter)
    outer.addLayout(lay)
    if below:
        outer.addWidget(below)
    return row


def make_cover(g: Game) -> QImage:
    """The game's cover in grays on a dark tile (a wide header is fitted in the middle); without one, its name.
    Painting on a QImage is safe off the UI thread."""
    img = QImage(COVER, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor("#141414"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    src = QImage(g.cover) if g.cover else QImage()
    icon = QImage(g.icon) if g.icon and src.isNull() else QImage()
    if not src.isNull():
        gray = src.convertToFormat(QImage.Format.Format_Grayscale8)
        portrait = src.height() >= src.width()
        mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding if portrait else Qt.AspectRatioMode.KeepAspectRatio
        scaled = gray.scaled(COVER, mode, Qt.TransformationMode.SmoothTransformation)
        p.drawImage((COVER.width() - scaled.width()) // 2, (COVER.height() - scaled.height()) // 2, scaled)
    else:
        p.setPen(QColor("#2a2a2a"))
        p.drawRect(QRectF(0.5, 0.5, COVER.width() - 1, COVER.height() - 1))
        f = QFont("IBM Plex Sans")
        f.setPixelSize(26)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor("#d0d0d0"))
        box = QRectF(20, 20, COVER.width() - 40, COVER.height() - 80)
        if not icon.isNull():                              # an app icon in grays above the name
            side = 112
            small = icon.scaled(QSize(side, side), Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
            ic = small.convertToFormat(QImage.Format.Format_Grayscale8).convertToFormat(QImage.Format.Format_ARGB32)
            ic.setAlphaChannel(small.convertToFormat(QImage.Format.Format_Alpha8))     # keep its transparency
            p.drawImage((COVER.width() - ic.width()) // 2, 70 + (side - ic.height()) // 2, ic)
            f.setPixelSize(22)
            p.setFont(f)
            box = QRectF(20, 200, COVER.width() - 40, COVER.height() - 260)
            p.drawText(box, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                       g.name)
        else:
            p.drawText(box, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, g.name)
        f.setPixelSize(14)
        f.setWeight(QFont.Weight.Medium)
        source = g.source_name.upper()
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, i18n.spacing(source, 2))
        p.setFont(f)
        p.setPen(QColor("#6f6f6f"))
        p.drawText(QRectF(0, COVER.height() - 50, COVER.width(), 30), Qt.AlignmentFlag.AlignCenter, source)
    p.end()
    return img


class _Item(QTreeWidgetItem):
    """Keeps the library's own order; the sort menu decides it."""

    def __lt__(self, other):
        return False


# ---------------------------------------------------------------- library
class LibraryPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.s = overlay.load()
        self.source = "all"
        self.games: list[Game] = []
        self.shown: list[Game] = []
        self.current: Game | None = None
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(12)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.gamel.page", "Search your games"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self.fill())
        bar.addWidget(self.search, 1)
        self.sort = QComboBox()
        for key, name in SORT_NAMES.items():
            self.sort.addItem(tr("grimoire.spells.gamel.page", name), key)
        self.sort.setCurrentIndex(list(SORT_NAMES).index(self.s["sort"]))
        self.sort.setToolTip(tr("grimoire.spells.gamel.page", "Sort by"))
        self.sort.currentIndexChanged.connect(self._sorted)
        bar.addWidget(self.sort)
        self.view_btns = {}
        for key, icon, tip in (("grid", "grid", tr("grimoire.spells.gamel.page", "Covers")),
                               ("list", "list", tr("grimoire.spells.gamel.page", "List"))):
            b = QToolButton()
            b.setObjectName("Tool")
            b.setIcon(glyph(icon, 18))
            b.setCheckable(True)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, k=key: self.set_view(k))
            bar.addWidget(b)
            self.view_btns[key] = b
        refresh = QToolButton()
        refresh.setObjectName("Tool")
        refresh.setIcon(glyph("update", 18))
        refresh.setToolTip(tr("grimoire.spells.gamel.page", "Look for games again"))
        refresh.clicked.connect(self.page.scan)
        bar.addWidget(refresh)
        left.addLayout(bar)

        self.views = QStackedWidget()
        self.grid = QListWidget()
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setIconSize(GRID_ICON)
        self.grid.setGridSize(QSize(146, 236))
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setUniformItemSizes(True)
        self.grid.setWordWrap(True)
        self.grid.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.grid.setSpacing(4)
        self.grid.currentRowChanged.connect(lambda r: self.select(self.shown[r] if 0 <= r < len(self.shown) else None))
        self.grid.itemActivated.connect(lambda _: self.play())
        self.list = QTreeWidget()
        self.list.setHeaderLabels([tr("grimoire.spells.gamel.page", "Name"),
                                   tr("grimoire.spells.gamel.page", "Launcher"),
                                   tr("grimoire.spells.gamel.page", "Size"),
                                   tr("grimoire.spells.gamel.page", "Playtime"),
                                   tr("grimoire.spells.gamel.page", "Last played")])
        self.list.setRootIsDecorated(False)
        self.list.setUniformRowHeights(True)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 5):
            self.list.header().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.list.currentItemChanged.connect(
            lambda it, _: self.select(self.shown[self.list.indexOfTopLevelItem(it)] if it else None))
        self.list.itemActivated.connect(lambda *_: self.play())
        self.empty = _label("", "Muted", wrap=True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (self.grid, self.list, self.empty):
            self.views.addWidget(w)
        left.addWidget(self.views, 1)
        root.addLayout(left, 1)

        # details
        self.panel = QFrame()
        self.panel.setObjectName("Row")
        self.panel.setFixedWidth(300)
        dl = QVBoxLayout(self.panel)
        dl.setContentsMargins(18, 18, 18, 18)
        dl.setSpacing(10)
        self.big = QLabel()
        self.big.setFixedSize(180, 270)
        self.big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.addWidget(self.big, 0, Qt.AlignmentFlag.AlignHCenter)
        self.d_name = _label("", "SectionTitle", wrap=True)
        dl.addWidget(self.d_name)
        self.d_source = _label("", "Badge")
        dl.addWidget(self.d_source, 0, Qt.AlignmentFlag.AlignLeft)
        info = QGridLayout()
        info.setHorizontalSpacing(12)
        info.setVerticalSpacing(6)
        self.d = {}
        start = Qt.AlignmentFlag.AlignAbsolute | (Qt.AlignmentFlag.AlignRight if QApplication.isRightToLeft()
                                                  else Qt.AlignmentFlag.AlignLeft)
        self.d_keys = {}
        for r, (key, name) in enumerate((("path", tr("grimoire.spells.gamel.page", "Folder")),
                                         ("size", tr("grimoire.spells.gamel.page", "Size")),
                                         ("playtime", tr("grimoire.spells.gamel.page", "Playtime")),
                                         ("last", tr("grimoire.spells.gamel.page", "Last played")),
                                         ("tool", tr("grimoire.spells.gamel.page", "Runs with")))):
            k = _label(name, "Muted")
            info.addWidget(k, r, 0, Qt.AlignmentFlag.AlignTop)
            v = _label("", "", wrap=True)
            v.setAlignment(start)              # a path or "3.0 GB" would else sit on the left in right-to-left
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            info.addWidget(v, r, 1)
            self.d[key] = v
            self.d_keys[key] = k
        info.setColumnStretch(1, 1)
        dl.addLayout(info)
        self.d_note = _label("", "Muted", wrap=True)
        dl.addWidget(self.d_note)
        dl.addStretch(1)
        self.d_hint = _label("", "Muted", wrap=True)
        dl.addWidget(self.d_hint)
        self.copy_btn = QPushButton(tr("grimoire.spells.gamel.page", "Copy launch option"))
        self.copy_btn.setToolTip(overlay.STEAM_OPTION)
        self.copy_btn.clicked.connect(self.page.copy_option)
        dl.addWidget(self.copy_btn)
        self.tricks_btn = QPushButton("Protontricks")
        self.tricks_btn.setToolTip(tr("grimoire.spells.gamel.page", "Winetricks for this game's Proton prefix"))
        self.tricks_btn.clicked.connect(self.protontricks)
        dl.addWidget(self.tricks_btn)
        self.folder_btn = QPushButton(glyph("vault", 16),
                                      "  " + tr("grimoire.spells.gamel.page", "Open folder in VaultL"))
        self.folder_btn.clicked.connect(self.open_folder)
        dl.addWidget(self.folder_btn)
        self.play_btn = QPushButton(tr("grimoire.spells.gamel.page", "Play"))
        self.play_btn.setObjectName("Primary")
        self.play_btn.setMinimumHeight(40)
        self.play_btn.clicked.connect(self.play)
        dl.addWidget(self.play_btn)
        root.addWidget(self.panel)
        self.set_view(self.s["view"], save=False)
        self.select(None)

    # ------------------------------------------------------------ filling
    def set_games(self, games: list[Game]):
        self.games = games
        self.fill()

    def _sorted(self):
        self._save("sort", self.sort.currentData())
        self.fill()

    def _save(self, key, value):
        self.s = overlay.load() | {key: value}
        try:
            overlay.save(self.s)
        except OSError:
            pass

    def set_view(self, view: str, save=True):
        for k, b in self.view_btns.items():
            b.setChecked(k == view)
        if save:
            self._save("view", view)
        self.s["view"] = view
        self._show_view()

    def _show_view(self):
        if not self.shown:
            self.views.setCurrentWidget(self.empty)
        else:
            self.views.setCurrentWidget(self.grid if self.s["view"] == "grid" else self.list)

    def fill(self):
        want = self.current.key if self.current else None
        q = self.search.text().strip().casefold()
        games = [g for g in self.games if (self.source == "all" or g.source == self.source)
                 and (not q or q in g.name.casefold())]
        self.shown = library.sort_games(games, self.sort.currentData())
        self.grid.blockSignals(True)
        self.list.blockSignals(True)
        self.grid.clear()
        self.list.clear()
        for g in self.shown:
            it = QListWidgetItem(self.page.icon(g), g.name)
            it.setToolTip(f"<p>{html.escape(g.name)}</p>")         # a name is never markup
            it.setSizeHint(QSize(146, 236))
            self.grid.addItem(it)
            row = _Item([g.name, g.source_name, human(self.page.size_of(g)) if self.page.size_of(g) else "–",
                         library.hours(g.playtime) if g.playtime else "–",
                         _ago(g.last_played) if g.tracked else "–"])
            for c in (2, 3):
                row.setTextAlignment(c, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.list.addTopLevelItem(row)
        self.grid.blockSignals(False)
        self.list.blockSignals(False)
        if not self.games:
            self.empty.setText(tr("grimoire.spells.gamel.page", "No games found. GameL looks for Steam, Heroic, "
                                                                "Lutris, itch and Bottles libraries in their usual "
                                                                "places (their Flatpak versions too), Roblox through "
                                                                "Sober and Vinegar, and games in the app menu."))
        else:
            self.empty.setText(tr("grimoire.spells.gamel.page", "No game matches “{query}”.").format(
                query=self.search.text().strip()))
        self._show_view()
        keys = [g.key for g in self.shown]
        idx = keys.index(want) if want in keys else (0 if keys else -1)
        if idx >= 0:
            self.grid.setCurrentRow(idx)
            self.list.setCurrentItem(self.list.topLevelItem(idx))
        self.select(self.shown[idx] if idx >= 0 else None)

    def refresh_icons(self):
        for i, g in enumerate(self.shown):
            self.grid.item(i).setIcon(self.page.icon(g))
        if self.current:
            self.select(self.current)

    # ------------------------------------------------------------ details
    def select(self, g: Game | None):
        self.current = g
        if g and self.grid.currentRow() != self.shown.index(g):
            self.grid.blockSignals(True)
            self.grid.setCurrentRow(self.shown.index(g))
            self.grid.blockSignals(False)
        if g and self.list.indexOfTopLevelItem(self.list.currentItem()) != self.shown.index(g):
            self.list.blockSignals(True)
            self.list.setCurrentItem(self.list.topLevelItem(self.shown.index(g)))
            self.list.blockSignals(False)
        self.panel.setVisible(g is not None)
        if not g:
            return
        self.big.setPixmap(self.page.pixmap(g).scaled(self.big.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation))
        self.d_name.setText(g.name)
        self.d_source.setText(g.source_name.upper())
        self.d["path"].setText(tilde(g.path) if g.path else tr("grimoire.spells.gamel.page", "Not known"))
        size = self.page.size_of(g)
        if size:
            self.d["size"].setText(human(size))
        elif os.path.isabs(g.path):
            self.d["size"].setText(tr("grimoire.spells.gamel.page", "Counting…"))
            self.page.count_size(g)
        else:
            self.d["size"].setText(tr("grimoire.spells.gamel.page", "Not known"))
        self.d["playtime"].setText(library.hours(g.playtime))
        self.d["last"].setText(_ago(g.last_played) if g.tracked else tr("grimoire.spells.gamel.page", "Not known"))
        tool = self.page.tool_of(g)
        self.d["tool"].setText(tool)
        self.d["tool"].setVisible(bool(tool))
        self.d_keys["tool"].setVisible(bool(tool))
        self.tricks_btn.setVisible(g.source == "steam" and not g.extra.get("shortcut")
                                   and bool(launch.protontricks_argv(g.id)))
        self.d_note.setText(g.note)
        self.d_note.setVisible(bool(g.note))
        steam_hint = g.source == "steam" and overlay.load()["mangohud"] and overlay.installed()
        self.d_hint.setText(tr("grimoire.spells.gamel.page", "For MangoHud in this game, add “{option}” to its launch "
                                                             "options in Steam.").format(option=overlay.STEAM_OPTION))
        self.d_hint.setVisible(steam_hint)
        self.copy_btn.setVisible(steam_hint)
        self.folder_btn.setEnabled(os.path.isabs(g.path))
        self.play_btn.setText(tr("grimoire.spells.gamel.page", "Play"))

    def update_size(self, key: str):
        for i, g in enumerate(self.shown):
            if g.key == key:
                size = self.page.size_of(g)
                self.list.topLevelItem(i).setText(2, human(size) if size else "–")
                if self.current and self.current.key == key:
                    self.d["size"].setText(human(size) if size else tr("grimoire.spells.gamel.page", "Not known"))

    def play(self):
        g = self.current
        if not g:
            return
        try:
            launch.play(g)
        except (OSError, ValueError) as e:
            self.page.say(tr("grimoire.spells.gamel.page", "Couldn't start {name}: {error}").format(
                name=g.name, error=e))
            return
        if g.source != "steam" and launch.game_env(g):
            text = tr("grimoire.spells.gamel.page", "Starting {name} through {launcher}, with MangoHud.")
        else:
            text = tr("grimoire.spells.gamel.page", "Starting {name} through {launcher}.")
        self.page.say(text.format(name=g.name, launcher=g.source_name))

    def protontricks(self):
        g = self.current
        if not g:
            return
        try:
            launch.protontricks(g.id)
        except (OSError, ValueError) as e:
            self.page.say(tr("grimoire.spells.gamel.page", "Couldn't open Protontricks: {error}").format(error=e))
            return
        text = tr("grimoire.spells.gamel.page", "Opening Protontricks for {name}. If it says there's no prefix, "
                                                "start the game once first.")
        self.page.say(text.format(name=i18n.isolate(g.name)))

    def open_folder(self):
        if self.current and self.current.path:
            try:
                launch.open_folder(self.current.path)
            except OSError as e:
                self.page.say(tr("grimoire.spells.gamel.page", "Couldn't open VaultL: {error}").format(error=e))


# ---------------------------------------------------------------- overlay
class OverlayPanel(QScrollArea):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 20)
        col.setSpacing(8)
        s = overlay.load()

        intro = tr("grimoire.spells.gamel.page", "MangoHud shows FPS, frame times, CPU and GPU load and temperature, "
                                                 "RAM and VRAM over a game, in a black & white style. It's a manual "
                                                 "switch: GameL never turns it, the crosshair, optimizations or "
                                                 "anything else on by itself when a game starts.")
        col.addWidget(_label(intro, "Subtitle", wrap=True))
        self.missing = _row(tr("grimoire.spells.gamel.page", "MangoHud isn't installed"),
                            tr("grimoire.spells.gamel.page", "Install it, then come back here:"),
                            below=_label("sudo apt install mangohud", "Mono"))
        col.addWidget(self.missing)

        self.switch = Switch()
        self.switch.setChecked(s["mangohud"])
        self.switch.toggled.connect(self._toggle)
        col.addWidget(_row(tr("grimoire.spells.gamel.page", "MangoHud overlay"),
                           tr("grimoire.spells.gamel.page", "On: GameL writes its style to "
                                                            "~/.config/MangoHud/MangoHud.conf and starts Heroic and "
                                                            "Lutris games with MANGOHUD=1. Off: games GameL starts "
                                                            "don't get it."),
                           self.switch))

        self.key = QComboBox()
        self.key.setEditable(True)
        for k in ("Shift_R+F12", "Shift_L+F12", "F12", "Control_R+F12", "Shift_R+F10"):
            self.key.addItem(k)
        self.key.setCurrentText(s["toggle"])
        self.key.setFixedWidth(170)
        self.key.lineEdit().editingFinished.connect(self._key)
        self.key.activated.connect(lambda _: self._key())
        col.addWidget(_row(tr("grimoire.spells.gamel.page", "Show or hide key"),
                           tr("grimoire.spells.gamel.page", "Press it in a game to hide the overlay or bring it back"),
                           self.key))

        self.pos = QComboBox()
        for k, name in overlay.POSITIONS.items():
            self.pos.addItem(tr("grimoire.spells.gamel.overlay", name), k)
        self.pos.setCurrentIndex(list(overlay.POSITIONS).index(s["position"]))
        self.pos.setMinimumWidth(170)          # grows for longer names in other languages
        self.pos.currentIndexChanged.connect(lambda _: self._set("position", self.pos.currentData()))
        col.addWidget(_row(tr("grimoire.spells.gamel.page", "Position"),
                           tr("grimoire.spells.gamel.page", "Which corner of the screen it sits in"), self.pos))

        self.compact = Switch()
        self.compact.setChecked(s["compact"])
        self.compact.toggled.connect(lambda on: self._set("compact", on))
        col.addWidget(_row(tr("grimoire.spells.gamel.page", "Compact"),
                           tr("grimoire.spells.gamel.page", "One thin row along the edge instead of a table"),
                           self.compact))

        col.addSpacing(10)
        col.addWidget(_label(tr("grimoire.spells.gamel.page", "MangoHud for Steam games"), "SectionTitle"))
        steam = QWidget()
        sl = QHBoxLayout(steam)
        sl.setContentsMargins(0, 0, 0, 0)
        opt = _label(overlay.STEAM_OPTION, "Mono")
        opt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        sl.addWidget(opt, 1)
        copy = QPushButton(tr("grimoire.spells.gamel.page", "Copy"))
        copy.clicked.connect(self.page.copy_option)
        sl.addWidget(copy)
        col.addWidget(_row(tr("grimoire.spells.gamel.page", "Add a launch option in Steam"),
                           tr("grimoire.spells.gamel.page", "Steam starts its games itself, so GameL can't hand "
                                                            "MangoHud to them. In Steam, right-click a game, choose "
                                                            "Properties, and under General put this in Launch options. "
                                                            "It uses the same style."),
                           below=steam))
        col.addWidget(_row(tr("grimoire.spells.gamel.page", "Heroic and Lutris"),
                           tr("grimoire.spells.gamel.page", "If Heroic or Lutris is already open, the game starts from "
                                                            "that window and may start without MangoHud. Both also "
                                                            "have a MangoHud switch in each game's settings.")))
        self.state = _label("", "Muted", wrap=True)
        col.addWidget(self.state)
        col.addStretch(1)
        self.setWidget(inner)

    def load(self):
        ok = overlay.installed()
        self.missing.setVisible(not ok)
        self.switch.setEnabled(ok)
        path = overlay.conf_path()
        if overlay.ours():
            self.state.setText(tr("grimoire.spells.gamel.page", "GameL's style is in {path}.").format(path=tilde(path)))
        elif path.exists():
            self.state.setText(tr("grimoire.spells.gamel.page", "{path} is your own; turning the overlay on moves it "
                                                                "aside first.").format(path=tilde(path)))
        else:
            self.state.setText("")

    def _toggle(self, on: bool):
        try:
            moved = overlay.set_overlay(on)
        except OSError as e:
            self.page.say(tr("grimoire.spells.gamel.page", "Couldn't write MangoHud's settings: {error}").format(
                error=e))
            self.switch.setChecked(not on)
            return
        if moved:
            self.page.say(tr("grimoire.spells.gamel.page", "Your own MangoHud.conf was kept as {name}.").format(
                name=moved.name))
        elif on:
            self.page.say(tr("grimoire.spells.gamel.page", "MangoHud overlay on."))
        else:
            self.page.say(tr("grimoire.spells.gamel.page", "MangoHud overlay off."))
        self.load()
        self.page.panels["library"].select(self.page.panels["library"].current)

    def _key(self):
        text = self.key.currentText().strip()
        if not overlay.KEY_RE.match(text):
            self.page.say(tr("grimoire.spells.gamel.page", "“{key}” isn't a key MangoHud knows. Use names like "
                                                           "Shift_R+F12.").format(key=text))
            self.key.setCurrentText(overlay.load()["toggle"])
            return
        self._set("toggle", text)

    def _set(self, key, value):
        s = overlay.load() | {key: value}
        try:
            if s["mangohud"]:
                moved = overlay.write_conf(s)
                if moved:
                    self.page.say(tr("grimoire.spells.gamel.page", "Your own MangoHud.conf was kept as {name}.").format(
                        name=moved.name))
            overlay.save(s)
        except OSError as e:
            self.page.say(tr("grimoire.spells.gamel.page", "Couldn't save: {error}").format(error=e))
        self.load()


# ---------------------------------------------------------------- performance mode
class PerfPanel(QScrollArea):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 20)
        col.setSpacing(8)
        from grimoire.spells.optimizel import perfmode
        intro = tr("grimoire.spells.gamel.page", "A few of OptimizeL's switches for gaming, turned on together while "
                                                 "you play. It's the same Performance mode as the tray's. Manual only: "
                                                 "starting a game never turns it on, and turning it off puts back only "
                                                 "what it changed.")
        col.addWidget(_label(intro, "Subtitle", wrap=True))
        self.btn = QPushButton()
        self.btn.setObjectName("Primary")
        self.btn.setMinimumWidth(130)
        self.btn.clicked.connect(self.toggle)
        sub = tr("grimoire.spells.gamel.page", "Switches on: {list}. Turning off split-lock throttling asks for your "
                                               "password.").format(list=perfmode.describe(perfmode.IDS))
        self.row = _row(tr("grimoire.spells.gamel.page", "Performance mode"), sub, self.btn)
        col.addWidget(self.row)
        self.state = _label("", "Muted", wrap=True)
        col.addWidget(self.state)
        col.addStretch(1)
        self.setWidget(inner)
        page.sig.perf.connect(self._done)

    def load(self):
        from grimoire.spells.optimizel import perfmode
        d = perfmode.load()
        self.btn.setEnabled(True)
        self.btn.setText(tr("grimoire.spells.gamel.page", "Turn off") if d["on"]
                         else tr("grimoire.spells.gamel.page", "Turn on"))
        if d["on"] and d["changed"]:
            self.state.setText(tr("grimoire.spells.gamel.page", "On. GameL turned on: {list}.").format(
                list=perfmode.describe(d["changed"])))
        elif d["on"]:
            self.state.setText(tr("grimoire.spells.gamel.page", "On. Everything it switches was already on, so turning "
                                                                "it off changes nothing."))
        else:
            self.state.setText(tr("grimoire.spells.gamel.page", "Off."))

    def toggle(self):
        from grimoire.spells.optimizel import perfmode
        on = not perfmode.is_on()
        self.btn.setEnabled(False)
        self.btn.setText(tr("grimoire.spells.gamel.page", "Turning on…") if on
                         else tr("grimoire.spells.gamel.page", "Turning off…"))

        def work():
            try:
                return on, (perfmode.turn_on() if on else perfmode.turn_off())
            except Exception as e:                    # any failure comes back as a message, never a stuck button
                return on, {"changed": [], "left": [], "problems": [str(e)]}
        POOL.start(Job(work, self.page.sig.perf.emit))

    def _done(self, result):
        from grimoire.spells.optimizel import perfmode
        on, r = result
        changed = perfmode.describe(r["changed"])
        if on and r["changed"]:
            text = tr("grimoire.spells.gamel.page", "Turned on: {list}.").format(list=changed)
        elif on:
            text = tr("grimoire.spells.gamel.page", "Everything it switches was already on, or doesn't apply here.")
        elif r["changed"]:
            text = tr("grimoire.spells.gamel.page", "Turned back off: {list}.").format(list=changed)
        else:
            text = tr("grimoire.spells.gamel.page", "Nothing to turn back.")
        if not on and r.get("left"):
            text += " " + tr("grimoire.spells.gamel.page", "Still on: {list}.").format(
                list=perfmode.describe(r["left"]))
        if r["problems"]:
            text += " " + tr("grimoire.spells.gamel.page", "Problems: {list}").format(list="; ".join(r["problems"]))
        self.page.say(text)
        self.load()


# ---------------------------------------------------------------- the page
class GameLPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.sig = _Signals()
        self.games: list[Game] = []
        self.mapping: dict = {}                     # Steam's CompatToolMapping: tool -> app ids
        self._images: dict[str, QImage] = {}       # _ck(game) -> gray cover, kept across rescans
        self._pix: dict[str, QPixmap] = {}
        self._sizes: dict[str, int] = {}
        self._counting: str | None = None           # the one game whose folder is being counted
        self._scanning = False
        self._again = False                         # a scan was asked for while one was running

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        nav = QFrame()
        nav.setObjectName("SubNav")
        nav.setMinimumWidth(210)               # grows for longer names in other languages
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(12, 26, 12, 16)
        nl.setSpacing(2)
        nl.addWidget(_label("GameL", "Title"))
        nl.addSpacing(12)
        nl.addWidget(_label(tr("grimoire.spells.gamel.page", "LIBRARY"), "NavSection"))
        self.nav: dict[str, QPushButton] = {}
        for fid, name in FILTERS:
            b = QPushButton(glyph("game" if fid == "all" else "grid", 18),
                            "  " + tr("grimoire.spells.gamel.page", name))
            b.setObjectName("SubNavItem")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, f=fid: self.show_panel("library", f))
            nl.addWidget(b)
            b.setVisible(fid == "all")                 # the others show once a scan finds their games
            self.nav[fid] = b
        nl.addSpacing(10)
        nl.addWidget(_label(tr("grimoire.spells.gamel.page", "WHILE YOU PLAY"), "NavSection"))
        for pid, name, icon in (("overlay", tr("grimoire.spells.gamel.page", "Overlay"), "system"),
                                ("perf", tr("grimoire.spells.gamel.page", "Performance mode"), "optimize"),
                                ("proton", "Proton", "proton")):
            if pid == "proton":
                nl.addSpacing(10)
                nl.addWidget(_label(tr("grimoire.spells.gamel.page", "COMPATIBILITY"), "NavSection"))
            b = QPushButton(glyph(icon, 18), "  " + name)
            b.setObjectName("SubNavItem")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, p=pid: self.show_panel(p))
            nl.addWidget(b)
            self.nav[pid] = b
        nl.addStretch(1)
        self.foot = _label("", "Tiny", wrap=True)
        nl.addWidget(self.foot)
        root.addWidget(nav)

        right = QVBoxLayout()
        right.setContentsMargins(32, 26, 32, 18)
        right.setSpacing(14)
        self.heading = _label("", "PageHeading")
        right.addWidget(self.heading)
        self.stack = QStackedWidget()
        self.panels = {"library": LibraryPanel(self), "overlay": OverlayPanel(self), "perf": PerfPanel(self),
                       "proton": ProtonPanel(self)}
        for p in self.panels.values():
            self.stack.addWidget(p)
        right.addWidget(self.stack, 1)
        self.toast = _label("", "Toast", wrap=True)
        self.toast.setTextFormat(Qt.TextFormat.PlainText)      # carries game names
        self.toast.hide()
        right.addWidget(self.toast)
        self._toast_timer = QTimer(self, singleShot=True, interval=7000, timeout=self.toast.hide)
        root.addLayout(right, 1)

        self.sig.scanned.connect(self._scanned)
        self.sig.covers.connect(self._covers)
        self.sig.sized.connect(self._sized)
        self.show_panel("library", "all")

    # ------------------------------------------------------------ navigation
    def show_panel(self, pid: str, source: str | None = None):
        for k, b in self.nav.items():
            b.setChecked(k == (source if pid == "library" else pid))
        if pid == "library":
            lib = self.panels["library"]
            lib.source = source or "all"
            self.heading.setText(tr("grimoire.spells.gamel.page", dict(FILTERS)[lib.source]))
            lib.fill()
        else:
            self.heading.setText({"overlay": tr("grimoire.spells.gamel.page", "Overlay"),
                                  "perf": tr("grimoire.spells.gamel.page", "Performance mode"),
                                  "proton": "Proton"}[pid])
            self.panels[pid].load()
        self.stack.setCurrentWidget(self.panels[pid])

    # ------------------------------------------------------------ library and covers
    def scan(self):
        if self._scanning:
            self._again = True
            return
        self._scanning = True
        POOL.start(Job(lambda: (*library.scan(), proton.mapping()), self.sig.scanned.emit))

    def _scanned(self, result):
        self._scanning = False
        if self._again:
            self._again = False
            self.scan()
        games, problems, self.mapping = result
        self.games = games
        counts = {src: sum(g.source == src for g in games) for src in SOURCES}
        lib = self.panels["library"]
        for fid, name in FILTERS:
            n = len(games) if fid == "all" else counts[fid]
            self.nav[fid].setText("  {name}   {n}".format(name=tr("grimoire.spells.gamel.page", name), n=n))
            self.nav[fid].setVisible(fid == "all" or n > 0 or lib.source == fid)   # only launchers with games
        self.foot.setText("; ".join(problems))
        self.panels["library"].set_games(games)
        todo = [g for g in games if self._ck(g) not in self._images]
        if todo:
            POOL.start(Job(lambda: {self._ck(g): make_cover(g) for g in todo}, self.sig.covers.emit))

    def _covers(self, images: dict):
        self._images.update(images)
        for k in images:
            self._pix.pop(k, None)
        self.panels["library"].refresh_icons()

    @staticmethod
    def _ck(g: Game) -> str:
        """Covers are cached per game and image file, so a cover Steam downloads later replaces the placeholder."""
        return f"{g.key}\n{g.cover}\n{g.icon}"

    def pixmap(self, g: Game) -> QPixmap:
        ck = self._ck(g)
        if ck not in self._pix:
            img = self._images.get(ck)
            if img is None:
                pm = QPixmap(COVER)
                pm.fill(QColor("#141414"))
                return pm
            self._pix[ck] = QPixmap.fromImage(img)
        return self._pix[ck]

    def icon(self, g: Game):
        from PySide6.QtGui import QIcon
        return QIcon(self.pixmap(g).scaled(GRID_ICON * 2, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))

    def tool_of(self, g: Game) -> str:
        """The compatibility tool Steam was told to run this game with ("" when it wasn't, or isn't Steam's)."""
        if g.source != "steam":
            return ""
        for name, ids in self.mapping.items():
            if g.id in ids:
                return name
        default = next((name for name, ids in self.mapping.items() if "0" in ids), "")
        return tr("grimoire.spells.gamel.page", "{tool} (Steam's default)").format(tool=default) if default else ""

    def size_of(self, g: Game) -> int:
        return g.size or self._sizes.get(g.key, 0)

    def count_size(self, g: Game):
        """Counts only the selected game's folder: picking another one (or leaving the page) stops the count, so
        arrowing through the list doesn't fill the shared pool with 20-second walks."""
        if g.key == self._counting or g.key in self._sizes or not os.path.isabs(g.path):
            return
        self._counting = g.key
        key, path = g.key, g.path
        stop = lambda: self._counting != key                   # noqa: E731 (read on the worker: a str compare)
        POOL.start(Job(lambda: (key, library.folder_size(path, stop=stop)), self.sig.sized.emit))

    def _sized(self, result):
        key, size = result
        if self._counting == key:
            self._counting = None
        if size is None:                                        # stopped: counted again when picked again
            return
        self._sizes[key] = size
        self.panels["library"].update_size(key)

    # ------------------------------------------------------------ helpers
    def copy_option(self):
        QApplication.clipboard().setText(overlay.STEAM_OPTION)
        self.say(tr("grimoire.spells.gamel.page", "Copied “{option}”. Paste it into the game's Launch options in "
                                                  "Steam.").format(option=overlay.STEAM_OPTION))

    def say(self, text: str):
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._counting = None                                   # stops a folder count still running

    def showEvent(self, e):
        super().showEvent(e)
        self.scan()
        lib = self.panels["library"]
        if lib.current and not self.size_of(lib.current):
            self.count_size(lib.current)
        if self.stack.currentWidget() is not self.panels["library"]:
            self.stack.currentWidget().load()
