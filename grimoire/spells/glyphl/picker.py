# SPDX-License-Identifier: GPL-3.0-or-later
"""The picker itself, shared by the hotkey popup and the hub page: search, categories, the character grid, skin
tones and the info pane. Emoji are drawn with the color emoji font; everything around them stays black & white.

The emoji dictionary and the Unicode name index load on a worker thread (once per process) and searches run there
too, so typing never waits on them; results from an older query are dropped by their token.
"""
from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, QRectF, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QKeySequence, QPainter, QPen, QShortcut, QTextOption
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListView, QListWidget, QListWidgetItem, QMenu, QStyle, QStyledItemDelegate,
                               QToolButton, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.glyphs import glyph
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.glyphl import data, store
from grimoire.spells.glyphl.blocks import BLOCKS

EMOJI_FAMILIES = ["Noto Color Emoji"]
TEXT_FAMILIES = ["IBM Plex Sans", "DejaVu Sans", "Noto Sans", "Noto Sans Symbols", "Noto Sans Symbols2",
                 "Noto Sans Math"]
CELL = 46
HANDS = "✋"                                        # ✋ shows the skin tone on its button
_shared: dict = {}                                      # the loaded data, shared by every picker in this process
SAVER = QThreadPool()                                   # one thread: saves land in the order they were made
SAVER.setMaxThreadCount(1)


def _font(families: list[str], px: int) -> QFont:
    f = QFont()
    f.setFamilies(families)
    f.setPixelSize(px)
    return f


def _ltr_option() -> QTextOption:
    """Characters are drawn left to right even in Arabic or Urdu, so ( [ « aren't swapped for their mirror image."""
    o = QTextOption(Qt.AlignmentFlag.AlignCenter)
    o.setTextDirection(Qt.LayoutDirection.LeftToRight)
    o.setWrapMode(QTextOption.WrapMode.NoWrap)
    return o


def _line(text: str) -> str:
    """A label line that starts with an isolated name or code: a right-to-left mark first, so in Arabic or Urdu it
    still lines up on the right like the rest of the pane."""
    return "\u200f" + text if i18n.rtl() else text


def _load():
    lang = i18n.loaded() or i18n.current()
    return {"emoji": data.EmojiSet(lang), "names": data.Names()}


class _Signals(QObject):
    loaded = Signal(object)
    found = Signal(object)
    saved = Signal(object)


# ---------------------------------------------------------------- the grid
class GlyphModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.items: list[str] = []
        self.tone = 0
        self.emoji: data.EmojiSet | None = None

    def set_items(self, items: list[str]):
        self.beginResetModel()
        self.items = items
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def shown(self, text: str) -> str:
        """text in the chosen skin tone, when it's a base emoji that has tones."""
        e = self.emoji.get(text) if self.emoji and self.tone else None
        return e.toned(self.tone) if e and e.text == text else text

    def is_emoji(self, text: str) -> bool:
        """Drawn in color: a fully-qualified emoji (☑ alone is a text symbol, ☑️ the emoji)."""
        return bool(self.emoji and text in self.emoji.by_text) or data.VS16 in text \
            or any(c in data.TONES for c in text) or (len(text) == 1 and 0x1F300 <= ord(text) <= 0x1FAFF)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.items):
            return None
        text = self.shown(self.items[index.row()])
        if role == Qt.ItemDataRole.DisplayRole:
            return text
        if role == Qt.ItemDataRole.ToolTipRole:
            return data.name_of(text, self.emoji)
        return None


class GlyphDelegate(QStyledItemDelegate):
    def __init__(self, model: GlyphModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.emoji_font = _font(EMOJI_FAMILIES, 26)
        self.text_font = _font(TEXT_FAMILIES, 23)
        self.small = _font(["IBM Plex Mono"], 9)
        self.option = _ltr_option()

    def sizeHint(self, option, index):
        return QSize(CELL, CELL)

    def paint(self, p: QPainter, opt, index):
        text = index.data() or ""
        r = QRectF(opt.rect).adjusted(2, 2, -2, -2)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if opt.state & QStyle.StateFlag.State_Selected:
            p.setPen(QPen(QColor("#f2f2f2"), 1))
            p.setBrush(QColor("#161616"))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        elif opt.state & QStyle.StateFlag.State_MouseOver:
            p.setPen(QPen(QColor("#3a3a3a"), 1))
            p.setBrush(QColor("#111111"))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        if data.invisible(text):                          # spaces and controls: their code point, small
            p.setPen(QPen(QColor("#5a5a5a"), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(7, 9, -7, -9), 4, 4)
            p.setFont(self.small)
            p.setPen(QColor("#a8a8a8"))
            p.drawText(r, f"{ord(text):04X}", self.option)
        else:
            emoji = self.model.is_emoji(text)
            p.setFont(self.emoji_font if emoji else self.text_font)
            p.setPen(QColor("#ececec"))
            p.drawText(r, "◌" + text if data.combining(text) else text, self.option)
        p.restore()


class Grid(QListView):
    copy = Signal(object)          # QModelIndex
    typed = Signal(str)            # printable text typed here goes to the search
    up_out = Signal()
    escape = Signal()

    def __init__(self):
        super().__init__()
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setGridSize(QSize(CELL, CELL))
        self.setWrapping(True)
        self.setSpacing(0)
        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QListView { background: transparent; border: none; outline: none; }")
        self.clicked.connect(self.copy.emit)

    def columns(self) -> int:
        return max(1, self.viewport().width() // CELL)

    def keyPressEvent(self, e):
        key, mods = e.key(), e.modifiers()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self.currentIndex().isValid():
            self.copy.emit(self.currentIndex())
        elif key == Qt.Key.Key_Escape:
            self.escape.emit()
        elif key == Qt.Key.Key_Up and self.currentIndex().row() < self.columns():
            self.up_out.emit()
        elif e.text() and e.text().isprintable() and not mods & (Qt.KeyboardModifier.ControlModifier |
                                                                 Qt.KeyboardModifier.AltModifier |
                                                                 Qt.KeyboardModifier.MetaModifier):
            self.typed.emit(e.text())
        else:
            super().keyPressEvent(e)


class Preview(QWidget):
    """The chosen character, big."""

    def __init__(self, model: GlyphModel):
        super().__init__()
        self.model = model
        self.text = ""
        self.setFixedSize(64, 64)

    def set_text(self, text: str):
        self.text = text
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor("#262626"), 1))
        p.setBrush(QColor("#0e0e0e"))
        p.drawRoundedRect(r, 10, 10)
        if not self.text:
            return
        if data.invisible(self.text):
            p.setFont(_font(["IBM Plex Mono"], 13))
            p.setPen(QColor("#a8a8a8"))
            p.drawText(r, f"{ord(self.text):04X}", _ltr_option())
            return
        emoji = self.model.is_emoji(self.text)
        p.setFont(_font(EMOJI_FAMILIES if emoji else TEXT_FAMILIES, 38 if emoji else 40))
        p.setPen(QColor("#ffffff"))
        p.drawText(r, "◌" + self.text if data.combining(self.text) else self.text, _ltr_option())


# ---------------------------------------------------------------- the picker
class Picker(QWidget):
    copied = Signal(str)
    escape = Signal()

    def __init__(self, popup: bool = False):
        super().__init__()
        self.popup = popup
        self.s = store.load()
        self.sig = _Signals()
        self.sig.loaded.connect(self._loaded)
        self.sig.found.connect(self._found)
        self._token = 0
        self._category = self.s["category"]
        self._hover = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.glyphl.picker", "Search emoji, symbols and names, or "
                                                                           "type U+2192"))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(glyph("search", 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setMinimumHeight(36)
        self.search.textChanged.connect(lambda: self._debounce.start())
        self.search.returnPressed.connect(self._copy_current)
        self.search.installEventFilter(self)
        top.addWidget(self.search, 1)
        self.tone_btn = QToolButton()
        self.tone_btn.setObjectName("Tool")
        self.tone_btn.setStyleSheet('QToolButton { font-family: "Noto Color Emoji"; font-size: 20px; '
                                    'padding: 0 4px; }')
        self.tone_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.tone_btn.setToolTip(tr("grimoire.spells.glyphl.picker", "Skin tone for people and hands"))
        self.tone_btn.setMinimumSize(40, 36)
        menu = QMenu(self.tone_btn)
        for tone in range(6):
            act = menu.addAction(f"{HANDS}{data.TONES[tone - 1] if tone else ''}   "
                                 f"{tr('grimoire.spells.glyphl.data', data.TONE_NAMES[tone])}")
            act.triggered.connect(lambda _=False, t=tone: self.set_tone(t))
        self.tone_btn.setMenu(menu)
        top.addWidget(self.tone_btn)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(10)
        self.cats = QListWidget()
        self.cats.setObjectName("Places")
        self.cats.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.cats.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fill_categories()
        self.cats.currentItemChanged.connect(self._category_clicked)
        self.cats.itemClicked.connect(self._category_clicked)       # the current one again: back from a search
        body.addWidget(self.cats)

        right = QVBoxLayout()
        right.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.heading = QLabel()
        self.heading.setObjectName("RowTitle")
        head.addWidget(self.heading)
        self.count = QLabel()
        self.count.setObjectName("Muted")
        head.addWidget(self.count)
        head.addStretch(1)
        self.block = QComboBox()
        self.block.setMaxVisibleItems(20)
        for lo, hi, name in BLOCKS:
            self.block.addItem(f"{name}  ·  {lo:04X}–{hi:04X}")
        self.block.currentIndexChanged.connect(self._block_chosen)
        self.block.hide()
        head.addWidget(self.block, 2)
        right.addLayout(head)

        self.model = GlyphModel()
        self.model.tone = self.s["tone"]
        self.grid = Grid()
        self.grid.setModel(self.model)
        self.grid.setItemDelegate(GlyphDelegate(self.model, self.grid))
        self.grid.copy.connect(lambda ix: self.copy_text(ix.data()))
        self.grid.typed.connect(self._typed)
        self.grid.up_out.connect(self.search.setFocus)
        self.grid.escape.connect(self._escape)
        self.grid.entered.connect(lambda ix: self._show_info(ix.data() or ""))
        self.grid.viewport().installEventFilter(self)
        self.grid.selectionModel().currentChanged.connect(lambda ix, _o: self._show_info(ix.data() or ""))
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._context_menu)
        right.addWidget(self.grid, 1)
        self.empty = QLabel()
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.hide()
        right.addWidget(self.empty, 1)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        root.addWidget(self._info_pane())

        foot = QHBoxLayout()
        foot.setSpacing(12)
        self.hint = QLabel(tr("grimoire.spells.glyphl.picker", "Click or Enter copies · Ctrl+D stars · Ctrl+PgDown "
                                                               "next category"))
        self.hint.setObjectName("Muted")
        foot.addWidget(self.hint, 1)
        self.close_box = QCheckBox(tr("grimoire.spells.glyphl.picker", "Close after copying"))
        self.close_box.setChecked(self.s["close"])
        self.close_box.setToolTip(tr("grimoire.spells.glyphl.picker",
                                     "Copies and closes, so you can paste with Ctrl+V right away. KDE on Wayland "
                                     "doesn't let an app type into another app's window (wtype and ydotool don't "
                                     "work there), so GlyphL can't paste for you."))
        self.close_box.toggled.connect(self._close_toggled)
        self.close_box.setVisible(popup)
        foot.addWidget(self.close_box)
        root.addLayout(foot)
        self._hint_text = self.hint.text()
        self._hint_timer = QTimer(self, singleShot=True, interval=2200,
                                  timeout=lambda: self.hint.setText(self._hint_text))

        self._debounce = QTimer(self, singleShot=True, interval=90, timeout=self._run_search)
        for keys, fn in ((QKeySequence.StandardKey.Find, self.focus_search), ("Ctrl+L", self.focus_search),
                         ("Ctrl+D", self._toggle_favorite), ("Ctrl+PgDown", lambda: self._step_category(1)),
                         ("Ctrl+PgUp", lambda: self._step_category(-1)), ("Ctrl+Shift+C", self._copy_code)):
            sc = QShortcut(QKeySequence(keys), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
        self._update_tone_button()

        if "emoji" in _shared:
            self._loaded(_shared, start=False)
        else:
            POOL.start(Job(_load, self.sig.loaded.emit))
        self._select_category(self._category)

    # ------------------------------------------------------------ building
    def _info_pane(self) -> QFrame:
        pane = QFrame()
        pane.setObjectName("Row")
        lay = QHBoxLayout(pane)
        lay.setContentsMargins(10, 10, 12, 10)
        lay.setSpacing(12)
        self.preview = Preview(self.model)
        lay.addWidget(self.preview)
        text = QVBoxLayout()
        text.setSpacing(3)
        self.info_name = QLabel()
        self.info_name.setObjectName("RowTitle")
        self.info_name.setWordWrap(True)
        self.info_name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(self.info_name)
        self.info_codes = QLabel()
        self.info_codes.setObjectName("Value")
        self.info_codes.setWordWrap(True)
        self.info_codes.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(self.info_codes)
        self.info_block = QLabel()
        self.info_block.setObjectName("Muted")
        text.addWidget(self.info_block)
        lay.addLayout(text, 1)
        self.star = QToolButton()
        self.star.setObjectName("Tool")
        self.star.setCheckable(True)
        self.star.setIcon(glyph("star", 20))
        self.star.setIconSize(QSize(20, 20))
        self.star.clicked.connect(self._toggle_favorite)
        lay.addWidget(self.star, 0, Qt.AlignmentFlag.AlignVCenter)
        self.copy_btn = QToolButton()
        self.copy_btn.setText(tr("grimoire.spells.glyphl.picker", "Copy"))
        self.copy_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.copy_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.copy_btn.setMinimumHeight(34)
        self.copy_btn.clicked.connect(lambda: self.copy_text(self._info_text))
        self.copy_menu = QMenu(self.copy_btn)
        self._fill_copy_menu(self.copy_menu, lambda: self._info_text)
        self.copy_btn.setMenu(self.copy_menu)
        lay.addWidget(self.copy_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self._info_text = ""
        self._show_info("")
        return pane

    def _fill_copy_menu(self, menu: QMenu, current):
        for label, how in ((tr("grimoire.spells.glyphl.picker", "Copy the character"), "char"),
                           (tr("grimoire.spells.glyphl.picker", "Copy the code point (U+…)"), "code"),
                           (tr("grimoire.spells.glyphl.picker", "Copy the HTML entity"), "html"),
                           (tr("grimoire.spells.glyphl.picker", "Copy the name"), "name")):
            menu.addAction(label).triggered.connect(lambda _=False, h=how: self._copy_as(current(), h))

    def _fill_categories(self):
        def header(text):
            it = QListWidgetItem(text.upper())
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            f = it.font()
            f.setPixelSize(10)
            f.setBold(True)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, i18n.spacing(text, 1))
            it.setFont(f)
            it.setForeground(QColor("#555555"))
            self.cats.addItem(it)

        def add(cid, text):
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, cid)
            self.cats.addItem(it)

        add("recent", tr("grimoire.spells.glyphl.picker", "Recent"))
        add("favorites", tr("grimoire.spells.glyphl.picker", "Favorites"))
        add("picks", tr("grimoire.spells.glyphl.picker", "Grimoire picks"))
        header(tr("grimoire.spells.glyphl.picker", "Emoji"))
        for g, label in data.GROUPS.items():
            add(f"emoji:{g}", tr("grimoire.spells.glyphl.data", label))
        header(tr("grimoire.spells.glyphl.picker", "Symbols"))
        for cid, (label, _fn) in data.SYMBOLS.items():
            add(f"sym:{cid}", tr("grimoire.spells.glyphl.data", label))
        header(tr("grimoire.spells.glyphl.picker", "Unicode"))
        add("blocks", tr("grimoire.spells.glyphl.picker", "All blocks"))
        width = max(self.cats.fontMetrics().horizontalAdvance(self.cats.item(i).text())
                    for i in range(self.cats.count()))
        self.cats.setFixedWidth(min(220, max(150, width + 40)))

    # ------------------------------------------------------------ data
    def _loaded(self, loaded, start=True):
        _shared.update(loaded)
        self.model.emoji = _shared["emoji"]
        if self.search.text().strip():
            self._run_search()
        else:
            self._show_category(self._category)

    @property
    def emoji(self) -> data.EmojiSet | None:
        return _shared.get("emoji")

    def _category_items(self, cid: str) -> list[str]:
        if cid == "recent":
            return list(self.s["recent"])
        if cid == "favorites":
            return list(self.s["favorites"])
        if cid == "picks":
            return data.symbols("picks")
        if cid.startswith("emoji:"):
            return [e.text for e in self.emoji.groups.get(int(cid[6:]), [])] if self.emoji else []
        if cid.startswith("sym:"):
            return data.symbols(cid[4:])
        if cid == "blocks":
            return data.block_chars(max(0, self.block.currentIndex()))
        return []

    def _select_category(self, cid: str):
        for i in range(self.cats.count()):
            if self.cats.item(i).data(Qt.ItemDataRole.UserRole) == cid:
                if self.cats.currentRow() == i:
                    self._category_clicked(self.cats.item(i))
                else:
                    self.cats.setCurrentRow(i)
                return
        self.cats.setCurrentRow(0)

    def _category_clicked(self, item, _old=None):
        cid = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not cid:
            return
        self._category = cid
        if self.s["category"] != cid:
            self.s["category"] = cid
            self._save()
        if self.search.text():
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
        self._show_category(cid)

    def _step_category(self, step: int):
        row = self.cats.currentRow()
        for _ in range(self.cats.count()):
            row = (row + step) % self.cats.count()
            if self.cats.item(row).flags() & Qt.ItemFlag.ItemIsSelectable:
                self.cats.setCurrentRow(row)
                return

    def _show_category(self, cid: str):
        item = self.cats.currentItem()
        self.heading.setText(item.text() if item else "")
        self.block.setVisible(cid == "blocks")
        if cid.startswith("emoji:") and not self.emoji:
            self._set_items([], tr("grimoire.spells.glyphl.picker", "Loading the emoji…"))
            return
        items = self._category_items(cid)
        empty = {"recent": tr("grimoire.spells.glyphl.picker", "Characters you copy show up here."),
                 "favorites": tr("grimoire.spells.glyphl.picker", "Star a character (Ctrl+D) to keep it here.")}
        self._set_items(items, empty.get(cid, tr("grimoire.spells.glyphl.picker", "Nothing here.")))

    def _block_chosen(self, _i):
        if self._category == "blocks" and not self.search.text():
            self._show_category("blocks")

    def show_block_of(self, text: str):
        """Open the block browser on the block holding text (the info pane's block line)."""
        i = data.block_index(ord(text[0])) if text else -1
        if i < 0:
            return
        self.block.blockSignals(True)
        self.block.setCurrentIndex(i)
        self.block.blockSignals(False)
        self._select_category("blocks")
        row = self.model.items.index(text) if text in self.model.items else 0
        self.grid.setCurrentIndex(self.model.index(row))
        self.grid.scrollTo(self.model.index(row))

    def _set_items(self, items: list[str], empty_text: str = ""):
        self.model.set_items(items)
        self.count.setText(i18n.ltr(f"{len(items):,}") if items else "")
        self.grid.setVisible(bool(items))
        self.empty.setVisible(not items)
        self.empty.setText(empty_text)
        if items:
            self.grid.setCurrentIndex(self.model.index(0))
            self.grid.scrollToTop()
        else:
            self._show_info("")

    # ------------------------------------------------------------ search
    def _run_search(self):
        q = self.search.text().strip()
        if not q:
            self._show_category(self._category)
            return
        self._token += 1
        token, emoji, names = self._token, self.emoji, _shared.get("names")
        if emoji is None:
            hits = data.direct(q, None)                   # a code point works before the index is ready
            self._found((token, hits, True))
            return
        POOL.start(Job(lambda: (token, data.search(q, emoji, names), False), self.sig.found.emit))

    def _found(self, result):
        token, hits, loading = result
        if token != self._token or not self.search.text().strip():
            return
        self.heading.setText(tr("grimoire.spells.glyphl.picker", "Results"))
        self.block.hide()
        text = tr("grimoire.spells.glyphl.picker", "Still loading the names, one moment…") if loading else \
            tr("grimoire.spells.glyphl.picker", "Nothing matches. Try another word, English names, or a code point "
                                                "like U+2192.")
        self._set_items(hits, text)

    def _typed(self, text: str):
        self.search.setFocus()
        self.search.insert(text)

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def eventFilter(self, obj, e):
        if obj is self.search and e.type() == e.Type.KeyPress:
            key = e.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_PageDown) and self.model.items:
                self.grid.setFocus()
                if not self.grid.currentIndex().isValid():
                    self.grid.setCurrentIndex(self.model.index(0))
                return True
            if key == Qt.Key.Key_Escape:
                self._escape()
                return True
        elif e.type() == e.Type.Leave and hasattr(self, "grid") and obj is self.grid.viewport():
            self._show_info(self.grid.currentIndex().data() or "")
        return super().eventFilter(obj, e)

    def _escape(self):
        if self.search.text():
            self.search.clear()
            self.search.setFocus()
        else:
            self.escape.emit()

    def reset(self):
        """Fresh for the next time the popup shows: empty search, the last category, focus in the search."""
        self.s = store.load()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self._select_category(self._category)
        self.search.setFocus()

    # ------------------------------------------------------------ the info pane
    def _show_info(self, text: str):
        self._info_text = text
        self.preview.set_text(text)
        has = bool(text)
        self.star.setEnabled(has)
        self.copy_btn.setEnabled(has)
        if not has:
            self.info_name.setText(tr("grimoire.spells.glyphl.picker", "Pick a character"))
            self.info_codes.setText(tr("grimoire.spells.glyphl.picker", "Its code point, UTF-8 bytes and HTML "
                                                                        "entity show here."))
            self.info_block.setText("")
            self.star.setChecked(False)
            return
        self.info_name.setText(_line(i18n.isolate(data.name_of(text, self.emoji))))
        self.info_codes.setText(_line(i18n.ltr(f"{data.codepoints(text)}   ·   UTF-8 {data.utf8(text)}   ·   "
                                               f"{data.entity(text)}")))
        block = data.block_name(text)
        self.info_block.setText(_line(i18n.isolate(block)) if len(text) == 1 or not self.model.is_emoji(text) else
                                tr("grimoire.spells.glyphl.picker", "Emoji sequence of %n code point(s)",
                                   n=len(text)))
        self.star.setChecked(text in self.s["favorites"])
        self.star.setToolTip(tr("grimoire.spells.glyphl.picker", "Remove from favorites (Ctrl+D)")
                             if text in self.s["favorites"] else
                             tr("grimoire.spells.glyphl.picker", "Add to favorites (Ctrl+D)"))

    def _context_menu(self, pos):
        ix = self.grid.indexAt(pos)
        if not ix.isValid():
            return
        text = ix.data()
        menu = QMenu(self)
        self._fill_copy_menu(menu, lambda: text)
        menu.addSeparator()
        fav = text in self.s["favorites"]
        menu.addAction(tr("grimoire.spells.glyphl.picker", "Remove from favorites") if fav else
                       tr("grimoire.spells.glyphl.picker", "Add to favorites")).triggered.connect(
            lambda: self._toggle_favorite(text))
        if len(text) == 1:
            menu.addAction(tr("grimoire.spells.glyphl.picker", "Show its Unicode block")).triggered.connect(
                lambda: self.show_block_of(text))
        if self._category == "recent" and not self.search.text():
            menu.addAction(tr("grimoire.spells.glyphl.picker", "Forget it")).triggered.connect(
                lambda: self._forget(text))
        menu.exec(self.grid.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------ actions
    def copy_text(self, text: str | None, remember: bool = True):
        if not text:
            return
        board = QGuiApplication.clipboard()
        board.setText(text)
        if board.supportsSelection():                     # middle-click paste too
            board.setText(text, board.Mode.Selection)
        if remember:
            store.used(self.s, text)
            self._save()
        self.hint.setText(tr("grimoire.spells.glyphl.picker", "Copied {char} · paste it with Ctrl+V").format(
            char=i18n.isolate(text)))
        self._hint_timer.start()
        self.copied.emit(text)

    def _copy_current(self):
        ix = self.grid.currentIndex()
        if ix.isValid():
            self.copy_text(ix.data())

    def _copy_code(self):
        self._copy_as(self.grid.currentIndex().data(), "code")

    def _copy_as(self, text: str | None, how: str):
        if not text:
            return
        if how == "char":
            self.copy_text(text)
            return
        value = {"code": data.codepoints(text), "html": data.entity(text), "name": data.name_of(text, self.emoji)}[how]
        self.copy_text(value, remember=False)

    def _toggle_favorite(self, text: str | None = None):
        text = text if isinstance(text, str) else (self._info_text or self.grid.currentIndex().data())
        if not text:
            return
        store.toggle_favorite(self.s, text)
        self._save()
        if self._category == "favorites" and not self.search.text():
            row = self.grid.currentIndex().row()
            self._show_category("favorites")
            if self.model.items:
                self.grid.setCurrentIndex(self.model.index(min(max(row, 0), len(self.model.items) - 1)))
        self._show_info(self._info_text)

    def _forget(self, text: str):
        self.s["recent"] = [t for t in self.s["recent"] if t != text]
        self._save()
        self._show_category("recent")

    def set_tone(self, tone: int):
        self.s["tone"] = tone
        self.model.tone = tone
        self._save()
        self._update_tone_button()
        self.grid.viewport().update()
        self._show_info(self.grid.currentIndex().data() or "")

    def _update_tone_button(self):
        tone = self.s["tone"]
        self.tone_btn.setText(HANDS + (data.TONES[tone - 1] if tone else ""))

    def _close_toggled(self, on: bool):
        self.s["close"] = on
        self._save()

    def _save(self):
        snapshot = {k: (list(v) if isinstance(v, list) else v) for k, v in self.s.items()}
        SAVER.start(Job(lambda: store.save(snapshot), lambda _r: None))
