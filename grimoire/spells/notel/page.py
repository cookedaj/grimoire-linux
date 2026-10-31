# SPDX-License-Identifier: GPL-3.0-or-later
"""NoteL page: the notes folder in a sidebar (pinned notes, folders, tags, full-text search), tabs of open files with
an editor, a live preview or both side by side, backlinks, find/replace, and the settings.

Every file read, save, scan, search, preview render and export runs on a worker; the UI thread only builds widgets.
Saves go through one writer thread, so two saves of the same file can never cross. Notes autosave a moment after
you stop typing; other files save with Ctrl+S unless "Autosave other files" is on. A file that changed on disk
since NoteL read it is never overwritten: its tab shows a bar to reload theirs, keep yours or keep both.
"""
import os
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QFileSystemWatcher, QObject, QRect, QSize, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QScrollArea,
                               QSpinBox, QSplitter, QStackedWidget, QStyle, QStyledItemDelegate, QTabBar,
                               QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from grimoire import i18n, widgets
from grimoire.fsutil import free_name, tilde, trash
from grimoire.glyphs import glyph
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.paths import command
from grimoire.spells.notel import highlight, index, preview, store
from grimoire.spells.notel.editor import Editor, FindBar
from grimoire.widgets import Switch

AUTOSAVE_MS = 900
BIG_HIGHLIGHT = 3 << 20          # no syntax colors past this (keeps typing fast in huge files)
WRITER = QThreadPool()
WRITER.setMaxThreadCount(1)      # saves one at a time, in order
ROLE = Qt.ItemDataRole.UserRole
LOCAL_QSS = """
QFrame#NoteBar { background: #070707; border-bottom: 1px solid #161616; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: #8c8c8c; border: none; border-bottom: 2px solid transparent;
               padding: 9px 6px 9px 14px; max-width: 240px; }
QTabBar::tab:hover { color: #ffffff; }
QTabBar::tab:selected { color: #ffffff; border-bottom: 2px solid #ffffff; }
QFrame#NoteStatus { background: #070707; border-top: 1px solid #161616; }
QTreeWidget#Notes, QListWidget#Tags, QListWidget#Results, QListWidget#Backlinks {
    background: transparent; border: none; outline: none; }
QTreeWidget#Notes::item { padding: 4px 2px; border-radius: 6px; color: #a8a8a8; }
QTreeWidget#Notes::item:hover { background: #101010; color: #ffffff; }
QTreeWidget#Notes::item:selected { background: #1a1a1a; color: #ffffff; }
QListWidget#Tags::item, QListWidget#Results::item, QListWidget#Backlinks::item {
    padding: 6px 8px; border: none; border-radius: 6px; color: #a8a8a8; }
QListWidget#Tags::item:hover, QListWidget#Results::item:hover, QListWidget#Backlinks::item:hover {
    background: #101010; color: #ffffff; }
QListWidget#Tags::item:selected, QListWidget#Results::item:selected, QListWidget#Backlinks::item:selected {
    background: #1a1a1a; color: #ffffff; border: none; }
QFrame#LinksPanel { background: #080808; border-top: 1px solid #161616; }
QPushButton#Flat { border: none; padding: 2px 6px; color: #8c8c8c; font-size: 11px; }
QPushButton#Flat:hover { color: #ffffff; }
QPushButton#Flat:checked { color: #ffffff; }
"""


class _Sig(QObject):
    done = Signal(object)        # (callback, result) from run()


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)        # note names and paths are the user's
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _tool(icon: str, tip: str, slot, size=18) -> QToolButton:
    b = QToolButton()
    b.setObjectName("Tool")
    b.setIcon(glyph(icon, size))
    b.setIconSize(QSize(size, size))
    b.setToolTip(tip)
    b.clicked.connect(lambda _=False: slot())
    return b


def _row(title: str, sub: str, *controls) -> QFrame:
    row = QFrame()
    row.setObjectName("Row")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(18, 12, 16, 12)
    lay.setSpacing(12)
    text = QVBoxLayout()
    text.setSpacing(3)
    text.addWidget(_label(title, "RowTitle"))
    if sub:
        text.addWidget(_label(sub, "Muted", wrap=True))
    lay.addLayout(text, 1)
    for c in controls:
        lay.addWidget(c, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


def _same(a: Path, b: Path) -> bool:
    return os.path.realpath(a) == os.path.realpath(b)


class _ResultDelegate(QStyledItemDelegate):
    """A search hit: the note's name, and under it the first matching line in gray."""

    def sizeHint(self, option, index):
        fm = option.fontMetrics
        lines = 2 if index.data(ROLE + 3) else 1
        return QSize(option.rect.width(), fm.height() * lines + 14 + (2 if lines > 1 else 0))

    def paint(self, p, option, index):
        title, snippet = index.data(ROLE + 2), index.data(ROLE + 3)
        if title is None:                       # "nothing matches"
            return super().paint(p, option, index)
        p.save()
        r = option.rect.adjusted(2, 1, -2, -1)
        if option.state & QStyle.StateFlag.State_Selected:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#1a1a1a"))
            p.drawRoundedRect(r, 6, 6)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#101010"))
            p.drawRoundedRect(r, 6, 6)
        fm = option.fontMetrics
        align = QStyle.visualAlignment(option.direction, Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter
        text = r.adjusted(8, 6, -8, -6)
        line = QRect(text.left(), text.top(), text.width(), fm.height())
        p.setPen(QColor("#ffffff"))
        p.drawText(line, align, fm.elidedText(title, Qt.TextElideMode.ElideRight, line.width()))
        if snippet:
            p.setPen(QColor("#7a7a7a"))
            line.translate(0, fm.height() + 2)
            p.drawText(line, align, fm.elidedText(snippet, Qt.TextElideMode.ElideRight, line.width()))
        p.restore()


class Doc:
    """One open file: its editor, what's on disk (store.Loaded) and its save state."""

    def __init__(self, path: Path, loaded: store.Loaded | None, editor: Editor, in_vault: bool):
        self.path, self.loaded, self.editor, self.in_vault = path, loaded, editor, in_vault
        self.conflict = ""           # "", "changed" or "deleted"
        self.saving = False
        self.landed = None           # what a save wrote, before its answer reaches the UI thread
        self.again = False           # another save was asked for while one ran
        self.closing = False         # close the tab once the save lands
        self.error = ""
        self.timer = QTimer(editor, singleShot=True, interval=AUTOSAVE_MS)

    @property
    def modified(self) -> bool:
        return self.editor.document().isModified()

    @property
    def markdown(self) -> bool:
        return store.is_markdown(self.path)


class NoteLPage(QWidget):
    def __init__(self, standalone: bool = False):
        super().__init__()
        self.setObjectName("Page")
        self.setStyleSheet(LOCAL_QSS)
        self.standalone = standalone
        self.s = store.load()
        self.root = store.vault(self.s)
        self.snap: index.Snapshot | None = None
        self.docs: list[Doc] = []
        self.sig = _Sig()
        self.sig.done.connect(lambda r: r[0](r[1]))
        self._started = False
        self._scanning = False
        self._rescan = False
        self._last_scan = 0.0
        self._search_gen = 0
        self._render_busy = False
        self._render_again = False
        self._image_cache: dict = {}
        self._window = None
        self.fwatch = None
        self.dwatch = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._sidebar())
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self._topbar())
        self.conflict_bar = self._conflict_bar()
        right.addWidget(self.conflict_bar)
        self.body = QStackedWidget()
        self.body.addWidget(self._empty())                       # 0
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.editors = QStackedWidget()
        self.preview = preview.Preview()
        self.preview.link.connect(self.follow_url)
        self.preview.hovered.connect(self._hover)
        self.split.addWidget(self.editors)
        self.split.addWidget(self.preview)
        self.split.setSizes([1, 1])
        work = QWidget()
        wl = QVBoxLayout(work)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        wl.addWidget(self.split, 1)
        self.links_panel = self._links_panel()
        wl.addWidget(self.links_panel)
        self.body.addWidget(work)                                # 1
        self.settings_panel = self._settings()
        self.body.addWidget(self.settings_panel)                 # 2
        right.addWidget(self.body, 1)
        self.find = FindBar(self.editor)
        right.addWidget(self.find)
        right.addWidget(self._statusbar())
        root.addLayout(right, 1)

        self._render_timer = QTimer(self, singleShot=True, interval=250, timeout=self._render)
        self._count_timer = QTimer(self, singleShot=True, interval=350, timeout=self._update_status)
        self._search_timer = QTimer(self, singleShot=True, interval=140, timeout=self._search)
        self._scan_timer = QTimer(self, singleShot=True, interval=700, timeout=self.scan)
        self._tabs_timer = QTimer(self, singleShot=True, interval=800, timeout=self._remember_tabs)
        self._shortcuts()
        self._apply_view()
        self._update_status()

    # ================================================================ building
    def _sidebar(self) -> QFrame:
        nav = QFrame()
        nav.setObjectName("SubNav")
        nav.setMinimumWidth(250)
        nav.setMaximumWidth(340)
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(12, 22, 12, 12)
        nl.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(_label("NoteL", "Title"))
        head.addStretch(1)
        nl.addLayout(head)
        tools = QHBoxLayout()
        tools.setSpacing(2)
        tools.addWidget(_tool("plus", tr("grimoire.spells.notel.page", "New note (Ctrl+N)"), self.new_note))
        tools.addWidget(_tool("calendar", tr("grimoire.spells.notel.page", "Today's note (Ctrl+Shift+D)"), self.daily))
        tools.addWidget(_tool("newfolder", tr("grimoire.spells.notel.page", "New folder"), self.new_folder))
        tools.addWidget(_tool("folder", tr("grimoire.spells.notel.page", "Open a file (Ctrl+O)"), self.open_dialog))
        tools.addStretch(1)
        tools.addWidget(_tool("gear", tr("grimoire.spells.notel.page", "NoteL settings"), self.show_settings))
        nl.addLayout(tools)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.notel.page", "Search notes (Ctrl+Shift+F)"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._query_changed)
        self.search.returnPressed.connect(self._open_first_result)
        self.search.installEventFilter(self)
        nl.addWidget(self.search)
        seg = QHBoxLayout()
        seg.setSpacing(0)
        self.seg_btns = {}
        for key, label in (("notes", tr("grimoire.spells.notel.page", "Notes")),
                           ("tags", tr("grimoire.spells.notel.page", "Tags"))):
            b = QPushButton(label)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.show_side(k))
            seg.addWidget(b, 1)
            self.seg_btns[key] = b
        widgets.segments(list(self.seg_btns.values()))
        self.seg_row = QWidget()
        self.seg_row.setLayout(seg)
        seg.setContentsMargins(0, 0, 0, 0)
        nl.addWidget(self.seg_row)
        self.side = QStackedWidget()
        self.side.setStyleSheet("QStackedWidget { background: transparent; }")
        self.tree = QTreeWidget()
        self.tree.setObjectName("Notes")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setUniformRowHeights(True)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        self.tree.itemClicked.connect(self._tree_clicked)
        self.tree.setExpandsOnDoubleClick(False)
        self.tags = QListWidget()
        self.tags.setObjectName("Tags")
        self.tags.itemClicked.connect(lambda it: self.search.setText("#" + it.data(ROLE)))
        self.results = QListWidget()
        self.results.setObjectName("Results")
        self.results.setItemDelegate(_ResultDelegate(self.results))
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.setMouseTracking(True)
        self.results.itemClicked.connect(self._result_clicked)
        self.results.itemActivated.connect(self._result_clicked)
        for w in (self.tree, self.tags, self.results):
            self.side.addWidget(w)
        nl.addWidget(self.side, 1)
        self.foot = QPushButton()
        self.foot.setObjectName("Link")
        self.foot.setToolTip(tr("grimoire.spells.notel.page", "Change the notes folder"))
        self.foot.clicked.connect(self.show_settings)
        nl.addWidget(self.foot)
        self.show_side(self.s["sidebar"] if self.s["sidebar"] in self.seg_btns else "notes")
        return nav

    def _topbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("NoteBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 0, 10, 0)
        bl.setSpacing(2)
        self.tabs = QTabBar()
        self.tabs.setDrawBase(False)
        self.tabs.setMovable(True)
        self.tabs.setExpanding(False)
        self.tabs.setElideMode(Qt.TextElideMode.ElideMiddle)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.tabMoved.connect(lambda *_: self._tabs_timer.start())
        self.tabs.tabBarClicked.connect(lambda i: self.body.setCurrentIndex(1) if i >= 0 else None)
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._tab_menu)
        self.tabs.installEventFilter(self)
        bl.addWidget(self.tabs, 1)
        self.view_btns = {}
        segs = QHBoxLayout()
        segs.setSpacing(0)
        for key, label, tip in (
                ("edit", tr("grimoire.spells.notel.page", "Edit"), tr("grimoire.spells.notel.page", "Only the editor")),
                ("split", tr("grimoire.spells.notel.page", "Split"),
                 tr("grimoire.spells.notel.page", "Editor and preview side by side")),
                ("read", tr("grimoire.spells.notel.page", "Read"),
                 tr("grimoire.spells.notel.page", "Only the preview (Ctrl+E switches)"))):
            b = QPushButton(label)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, k=key: self.set_view(k))
            segs.addWidget(b)
            self.view_btns[key] = b
        widgets.segments(list(self.view_btns.values()))
        self.doc_tools = QWidget()                       # hidden while no file is open
        tl = QHBoxLayout(self.doc_tools)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(2)
        tl.addSpacing(8)
        tl.addLayout(segs)
        tl.addSpacing(6)
        tl.addWidget(_tool("search", tr("grimoire.spells.notel.page", "Find and replace (Ctrl+F, Ctrl+H)"),
                           lambda: self.find.open_bar(False)))
        self.pin_btn = _tool("pin", tr("grimoire.spells.notel.page", "Pin this note to the top of the list"),
                             self.toggle_pin)
        self.pin_btn.setCheckable(True)
        tl.addWidget(self.pin_btn)
        more = _tool("more", tr("grimoire.spells.notel.page", "More"), lambda: None)
        self.more_menu = QMenu(self)
        self.more_menu.aboutToShow.connect(self._fill_more)
        more.setMenu(self.more_menu)
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0; }")
        tl.addWidget(more)
        bl.addWidget(self.doc_tools)
        bar.setMinimumHeight(46)
        return bar

    def _conflict_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Pending")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 10, 12, 10)
        lay.setSpacing(8)
        self.conflict_text = _label("", "PendingText", wrap=True)
        lay.addWidget(self.conflict_text, 1)
        self.c_buttons = {}
        for key, label in (("reload", tr("grimoire.spells.notel.page", "Reload theirs")),
                           ("copy", tr("grimoire.spells.notel.page", "Keep both")),
                           ("mine", tr("grimoire.spells.notel.page", "Keep mine")),
                           ("again", tr("grimoire.spells.notel.page", "Save it again")),
                           ("close", tr("grimoire.spells.notel.page", "Close tab"))):
            b = QPushButton(label)
            if key in ("copy", "again"):
                b.setObjectName("Primary")
            b.clicked.connect(lambda _=False, k=key: self._resolve(k))
            lay.addWidget(b)
            self.c_buttons[key] = b
        bar.hide()
        return bar

    def _empty(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addStretch(1)
        icon = QLabel()
        icon.setPixmap(glyph("notel", 56).pixmap(56, 56))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon)
        lay.addSpacing(10)
        t = _label(tr("grimoire.spells.notel.page", "No note open"), "SectionTitle")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        self.empty_sub = _label(tr("grimoire.spells.notel.page", "Pick a note on the left, or start one."), "Muted",
                                wrap=True)
        self.empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.empty_sub)
        lay.addSpacing(14)
        row = QHBoxLayout()
        row.addStretch(1)
        new = QPushButton(tr("grimoire.spells.notel.page", "New note"))
        new.setObjectName("Primary")
        new.clicked.connect(self.new_note)
        row.addWidget(new)
        for label, slot in ((tr("grimoire.spells.notel.page", "Today's note"), self.daily),
                            (tr("grimoire.spells.notel.page", "Open a file…"), self.open_dialog)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(2)
        return w

    def _links_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("LinksPanel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(4)
        lay.addWidget(_label(tr("grimoire.spells.notel.page", "LINKED FROM"), "NavSection"))
        self.backlinks = QListWidget()
        self.backlinks.setObjectName("Backlinks")
        self.backlinks.itemClicked.connect(lambda it: self.open_path(Path(it.data(ROLE))))
        lay.addWidget(self.backlinks)
        panel.hide()
        return panel

    def _statusbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("NoteStatus")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 4, 10, 4)
        lay.setSpacing(10)
        self.state = _label("", "Tiny")
        self.state.setMinimumWidth(10)
        lay.addWidget(self.state, 1)
        self.links_btn = QPushButton()
        self.links_btn.setObjectName("Flat")
        self.links_btn.setCheckable(True)
        self.links_btn.setToolTip(tr("grimoire.spells.notel.page", "Show the notes that link here"))
        self.links_btn.toggled.connect(lambda on: self.links_panel.setVisible(on and self.links_btn.isEnabled()))
        lay.addWidget(self.links_btn)
        self.info = _label("", "Tiny")
        lay.addWidget(self.info)
        self._toast_timer = QTimer(self, singleShot=True, interval=6000, timeout=self._update_status)
        return bar

    def _settings(self) -> QWidget:
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(32, 26, 32, 26)
        col.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(_label(tr("grimoire.spells.notel.page", "Settings"), "PageHeading"), 1)
        back = QPushButton(tr("grimoire.spells.notel.page", "Done"))
        back.setObjectName("Primary")
        back.clicked.connect(self.hide_settings)
        top.addWidget(back)
        col.addLayout(top)
        self.vault_label = _label("", "Muted", wrap=True)
        change = QPushButton(tr("grimoire.spells.notel.page", "Change…"))
        change.clicked.connect(self.pick_vault)
        default = QPushButton(tr("grimoire.spells.notel.page", "Use the default"))
        default.clicked.connect(lambda: self.set_vault(""))
        notes_row = _row(tr("grimoire.spells.notel.page", "Notes folder"), "", default, change)
        notes_row.layout().itemAt(0).layout().addWidget(self.vault_label)
        col.addWidget(notes_row)
        col.addWidget(_label(tr("grimoire.spells.notel.page", "Any folder of Markdown files works, an Obsidian vault "
                                                                   "too: NoteL reads and writes plain text files and "
                                                                   "leaves Obsidian's own settings alone."),
                             "Muted", wrap=True))
        self.daily_edit = QLineEdit()
        self.daily_edit.setPlaceholderText(tr("grimoire.spells.notel.page", "the notes folder itself"))
        self.daily_edit.setMinimumWidth(200)
        self.daily_edit.editingFinished.connect(self._daily_folder)
        col.addWidget(_row(tr("grimoire.spells.notel.page", "Daily notes folder"),
                           tr("grimoire.spells.notel.page", "Today's note is named like {example}, in this "
                                                             "folder inside your notes.")
                           .format(example=i18n.ltr("2026-10-15.md")),
                           self.daily_edit))
        self.switches = {}
        for key, title, sub in (
                ("mono", tr("grimoire.spells.notel.page", "Monospace font for notes"),
                 tr("grimoire.spells.notel.page", "Code and other files always use one.")),
                ("line_numbers", tr("grimoire.spells.notel.page", "Line numbers"), ""),
                ("wrap", tr("grimoire.spells.notel.page", "Wrap long lines"), ""),
                ("autosave_files", tr("grimoire.spells.notel.page", "Autosave other files too"),
                 tr("grimoire.spells.notel.page", "Notes always save as you type. Off: files outside your notes "
                                                  "save with Ctrl+S."))):
            sw = Switch()
            sw.setChecked(self.s[key])
            sw.toggled.connect(lambda on, k=key: self._set(k, on))
            self.switches[key] = sw
            col.addWidget(_row(title, sub, sw))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(9, 32)
        self.size_spin.setValue(self.s["font_size"])
        self.size_spin.valueChanged.connect(lambda v: self._set("font_size", v))
        col.addWidget(_row(tr("grimoire.spells.notel.page", "Text size"),
                           tr("grimoire.spells.notel.page", "Ctrl+plus and Ctrl+minus change it too."),
                           self.size_spin))
        col.addStretch(1)
        outer.setWidget(inner)
        return outer

    def _shortcuts(self):
        def key(seq, fn):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
        key("Ctrl+N", self.new_note)
        key("Ctrl+O", self.open_dialog)
        key("Ctrl+S", lambda: self.save_current())
        key("Ctrl+Shift+S", self.save_as)
        key("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex()))
        key("Ctrl+Tab", lambda: self._cycle(1))
        key("Ctrl+Shift+Tab", lambda: self._cycle(-1))
        key("Ctrl+PgDown", lambda: self._cycle(1))
        key("Ctrl+PgUp", lambda: self._cycle(-1))
        key("Ctrl+F", lambda: self.find.open_bar(False))
        key("Ctrl+H", lambda: self.find.open_bar(True))
        key("F3", lambda: self.find.step(1))
        key("Shift+F3", lambda: self.find.step(-1))
        key("Ctrl+Shift+F", self.focus_search)
        key("Ctrl+P", self.focus_search)
        key("Ctrl+E", lambda: self.set_view("edit" if self.s["view"] == "read" else "read"))
        key("Ctrl+Shift+D", self.daily)
        key("F2", self.rename_current)

    # ================================================================ background work
    def run(self, fn, done, writer=False):
        """fn() on a worker, then done(result) here; done gets the exception instead when fn raises."""
        def guarded():
            try:
                return fn()
            except Exception as e:          # handed to done(), which words it for the UI
                return e
        (WRITER if writer else POOL).start(Job(guarded, lambda r: self.sig.done.emit((done, r))))

    def say(self, text: str):
        self.state.setText(text)
        self._toast_timer.start()

    # ================================================================ life cycle
    def showEvent(self, e):
        super().showEvent(e)
        win = self.window()
        if win is not self._window:
            if self._window is not None:
                self._window.removeEventFilter(self)
            self._window = win
            win.installEventFilter(self)
            app = QApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(self.flush, Qt.ConnectionType.UniqueConnection)
        if not self._started:
            self._started = True
            self._restore_tabs()
            self.scan()
        elif time.monotonic() - self._last_scan > 5:
            self.scan()

    def hideEvent(self, e):
        super().hideEvent(e)
        for d in self.docs:
            if d.modified and self._autosaves(d) and not d.conflict:
                self.save(d)

    def eventFilter(self, obj, e):
        t = e.type()
        if obj is self._window:
            if t == QEvent.Type.Close:
                if not self.can_close():
                    e.ignore()
                    return True
            elif t == QEvent.Type.WindowActivate and self._started and time.monotonic() - self._last_scan > 10:
                self.scan()
        elif obj is getattr(self, "search", None) and t == QEvent.Type.KeyPress:
            if e.key() == Qt.Key.Key_Escape:
                self.search.clear()
                ed = self.editor()
                if ed:
                    ed.setFocus()
                return True
            if e.key() == Qt.Key.Key_Down and self.results.isVisible() and self.results.count():
                self.results.setFocus()
                self.results.setCurrentRow(0)
                return True
        elif obj is getattr(self, "tabs", None) and t == QEvent.Type.MouseButtonRelease \
                and e.button() == Qt.MouseButton.MiddleButton:
            i = self.tabs.tabAt(e.position().toPoint())
            if i >= 0:
                self.close_tab(i)
                return True
        return super().eventFilter(obj, e)

    def can_close(self) -> bool:
        """Before the window closes: notes are saved now; files that don't autosave are asked about."""
        ask = []
        for d in list(self.docs):
            if not d.modified:
                continue
            if self._autosaves(d) and not d.conflict and self._save_now(d):
                continue
            ask.append(d)
        if not ask:
            self._remember_tabs()
            return True
        names = "\n".join(f"• {d.path.name}" for d in ask[:12])
        box = QMessageBox(QMessageBox.Icon.Warning, tr("grimoire.spells.notel.page", "Unsaved changes"),
                          tr("grimoire.spells.notel.page", "These files have changes that aren't saved:")
                          + "\n\n" + names,
                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                          | QMessageBox.StandardButton.Cancel, self)
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        answer = box.exec()
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            for d in ask:
                if d.conflict or not self._save_now(d):
                    self.tabs.setCurrentIndex(self._index_of(d))
                    return False
        for d in ask:
            d.editor.document().setModified(False)
        self._remember_tabs()
        return True

    def flush(self):
        """Save every autosaving note right away (the app is quitting)."""
        for d in self.docs:
            if d.modified and self._autosaves(d) and not d.conflict:
                self._save_now(d)
        self._remember_tabs()

    def _save_now(self, d: Doc) -> bool:
        """A save on this thread, for closing: the window is going away, so there's no later to wait for."""
        WRITER.waitForDone(5000)
        base = d.landed if d.saving and d.landed else d.loaded     # a save that landed but wasn't answered yet
        try:
            d.loaded = store.save(d.path, d.editor.toPlainText(), base)
        except store.Conflict as c:
            d.conflict = c.kind
            self._show_conflict()
            return False
        except OSError as e:
            self.say(tr("grimoire.spells.notel.page", "Couldn't save {name}: {error}")
                     .format(name=i18n.isolate(d.path.name), error=e))
            return False
        d.editor.document().setModified(False)
        return True

    # ================================================================ vault scan
    def scan(self):
        if self._scanning:
            self._rescan = True
            return
        self._scanning = True
        self._last_scan = time.monotonic()
        prev, s = self.snap, dict(self.s)

        def work():
            root = store.ensure_vault(s)
            if root is None:
                return None
            snap = index.scan(root, prev)
            last = snap.recent(1)
            store.remember_status(len(snap.notes), last[0].title if last else "")
            return snap
        self.run(work, self._scanned)

    def _scanned(self, snap):
        self._scanning = False
        if isinstance(snap, Exception):
            self.say(tr("grimoire.spells.notel.page", "Couldn't read the notes folder: {error}").format(error=snap))
            snap = None
        self.snap = snap
        self.root = snap.root if snap else store.vault(self.s)
        if snap is None:
            self.foot.setText(tr("grimoire.spells.notel.page", "Notes folder not found: {path}")
                              .format(path=i18n.ltr(tilde(self.root))))
        else:
            n = tr("grimoire.spells.notel.page", "%n note(s)", n=len(snap.notes))
            self.foot.setText(f"{i18n.ltr(tilde(self.root))} · {n}")
        self._fill_tree()
        self._fill_tags()
        names = sorted({n.title for n in snap.notes.values() if store.is_markdown(n.path)}, key=str.lower) \
            if snap else []
        for d in self.docs:
            d.editor.set_names(names)
            d.in_vault = bool(snap) and store.in_vault(d.path, self.root)
        self._watch_dirs()
        if self.search.text().strip():
            self._search()
        self._backlinks()
        self._update_status()
        if self._rescan:
            self._rescan = False
            self.scan()

    def _watch_dirs(self):
        if self.dwatch is None:
            self.dwatch = QFileSystemWatcher(self)
            self.dwatch.directoryChanged.connect(lambda _: self._scan_timer.start())
        old = self.dwatch.directories()
        if old:
            self.dwatch.removePaths(old)
        if self.snap:
            dirs = [str(self.root)] + [str(self.root / f) for f in self.snap.folders[:500]]
            self.dwatch.addPaths(dirs)

    # ================================================================ sidebar
    def show_side(self, key: str):
        for k, b in self.seg_btns.items():
            b.setChecked(k == key)
        if not self.search.text().strip():
            self.side.setCurrentWidget(self.tree if key == "notes" else self.tags)
        if key != self.s["sidebar"]:
            self._set("sidebar", key)

    def _pinned(self) -> list[Path]:
        return [Path(p) for p in self.s["pinned"]]

    def _fill_tree(self):
        open_folders = set()
        it = self.tree.invisibleRootItem()
        stack = [it]
        while stack:
            node = stack.pop()
            for i in range(node.childCount()):
                ch = node.child(i)
                if ch.isExpanded() and ch.data(0, ROLE + 1) == "folder":
                    open_folders.add(ch.data(0, ROLE))
                stack.append(ch)
        first = not self.tree.topLevelItemCount()
        self.tree.clear()
        if not self.snap:
            return
        pins = [p for p in self._pinned() if store.in_vault(p, self.root) and p.exists()]
        if pins:
            group = QTreeWidgetItem([tr("grimoire.spells.notel.page", "PINNED")])
            group.setFlags(Qt.ItemFlag.ItemIsEnabled)
            f = QFont()
            f.setPixelSize(10)
            f.setWeight(QFont.Weight.Bold)
            group.setFont(0, f)
            group.setData(0, ROLE + 1, "group")
            self.tree.addTopLevelItem(group)
            for p in pins:
                item = QTreeWidgetItem([p.stem if store.is_markdown(p) else p.name])
                item.setIcon(0, glyph("pin", 16))
                item.setData(0, ROLE, str(p))
                item.setData(0, ROLE + 1, "note")
                item.setToolTip(0, tilde(p))
                group.addChild(item)
            group.setExpanded(True)
        folders = {"": self.tree.invisibleRootItem()}
        for rel in self.snap.folders:
            parent_rel, _, name = rel.rpartition("/")
            parent = folders.get(parent_rel)
            if parent is None:
                continue
            item = QTreeWidgetItem([name])
            item.setIcon(0, glyph("folder", 16))
            item.setData(0, ROLE, str(self.root / rel))
            item.setData(0, ROLE + 1, "folder")
            parent.addChild(item)
            folders[rel] = item
            if str(self.root / rel) in open_folders:
                item.setExpanded(True)
        for note in self.snap.sorted_notes():
            parent_rel = note.rel.rpartition("/")[0]
            parent = folders.get(parent_rel)
            if parent is None:
                continue
            item = QTreeWidgetItem([note.title])
            item.setIcon(0, glyph("document", 16))
            item.setData(0, ROLE, str(note.path))
            item.setData(0, ROLE + 1, "note")
            item.setToolTip(0, note.rel)
            parent.addChild(item)
        self._sort_tree(self.tree.invisibleRootItem())
        if first:
            cur = self.current()
            if cur:
                self._select_in_tree(cur.path)
        self.tree.setVisible(True)

    @staticmethod
    def _sort_tree(node):
        """Folders first, then notes, each by name (the pinned group stays on top)."""
        kids = [node.takeChild(0) for _ in range(node.childCount())]
        order = {"group": 0, "folder": 1, "note": 2}
        kids.sort(key=lambda it: (order.get(it.data(0, ROLE + 1), 3), it.text(0).lower()))
        for k in kids:
            node.addChild(k)
            if k.data(0, ROLE + 1) == "folder":
                NoteLPage._sort_tree(k)

    def _select_in_tree(self, path: Path):
        target = os.path.realpath(path)
        stack = [self.tree.invisibleRootItem()]
        while stack:
            node = stack.pop()
            for i in range(node.childCount()):
                ch = node.child(i)
                kind, data = ch.data(0, ROLE + 1), ch.data(0, ROLE)
                if kind == "group":
                    continue                              # the folder tree's copy, not the pinned one
                if kind == "note" and data and os.path.realpath(data) == target:
                    p = ch.parent()
                    while p:
                        p.setExpanded(True)
                        p = p.parent()
                    self.tree.setCurrentItem(ch)
                    return
                stack.append(ch)

    def _fill_tags(self):
        self.tags.clear()
        if not self.snap:
            return
        for tag, n in sorted(self.snap.tags.items(), key=lambda t: t[0]):
            item = QListWidgetItem(f"#{tag}   {n}")
            item.setData(ROLE, tag)
            self.tags.addItem(item)
        if not self.snap.tags:
            item = QListWidgetItem(tr("grimoire.spells.notel.page", "No tags yet. Write #idea in a note to tag it."))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.tags.addItem(item)

    def _tree_clicked(self, item, _col=0):
        kind = item.data(0, ROLE + 1)
        if kind == "note":
            mods = QGuiApplication.keyboardModifiers()
            self.open_path(Path(item.data(0, ROLE)), new_tab=bool(mods & Qt.KeyboardModifier.ControlModifier))
        elif kind == "folder":
            item.setExpanded(not item.isExpanded())

    def _tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        kind = item.data(0, ROLE + 1) if item else ""
        path = Path(item.data(0, ROLE)) if item and item.data(0, ROLE) else None
        menu = QMenu(self)
        if kind == "note":
            menu.addAction(tr("grimoire.spells.notel.page", "Open in a new tab"),
                           lambda: self.open_path(path, new_tab=True))
            pinned = str(path) in self.s["pinned"]
            menu.addAction(tr("grimoire.spells.notel.page", "Unpin") if pinned
                           else tr("grimoire.spells.notel.page", "Pin"), lambda: self.toggle_pin(path))
            menu.addAction(tr("grimoire.spells.notel.page", "Rename…"), lambda: self.rename(path))
            menu.addAction(tr("grimoire.spells.notel.page", "Show in VaultL"), lambda: self.reveal(path))
            menu.addSeparator()
            menu.addAction(tr("grimoire.spells.notel.page", "Move to Trash"), lambda: self.remove(path))
        elif kind == "folder":
            menu.addAction(tr("grimoire.spells.notel.page", "New note here"), lambda: self.new_note(path))
            menu.addAction(tr("grimoire.spells.notel.page", "New folder here"), lambda: self.new_folder(path))
            menu.addAction(tr("grimoire.spells.notel.page", "Rename…"), lambda: self.rename(path))
            menu.addAction(tr("grimoire.spells.notel.page", "Show in VaultL"), lambda: self.reveal(path))
            menu.addSeparator()
            menu.addAction(tr("grimoire.spells.notel.page", "Move to Trash"), lambda: self.remove(path))
        else:
            menu.addAction(tr("grimoire.spells.notel.page", "New note"), lambda: self.new_note(self.root))
            menu.addAction(tr("grimoire.spells.notel.page", "New folder"), lambda: self.new_folder(self.root))
            menu.addAction(tr("grimoire.spells.notel.page", "Show in VaultL"), lambda: self.reveal(self.root))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ---------------------------------------------------------------- search
    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _query_changed(self, text: str):
        searching = bool(text.strip())
        self.seg_row.setVisible(not searching)
        if searching:
            self._search_timer.start()
        else:
            self._search_gen += 1
            self.results.clear()
            self.show_side(self.s["sidebar"])

    def _search(self):
        q = self.search.text().strip()
        if not q or not self.snap:
            return
        self._search_gen += 1
        gen, snap = self._search_gen, self.snap
        self.run(lambda: (gen, q, index.search(snap, q)), self._searched)

    def _searched(self, result):
        if isinstance(result, Exception) or result[0] != self._search_gen:
            return
        _, q, hits = result
        self.side.setCurrentWidget(self.results)
        self.results.clear()
        for h in hits:
            lines = [t for _, t in h.lines if t]
            item = QListWidgetItem(h.note.title)
            item.setData(ROLE, str(h.note.path))
            item.setData(ROLE + 2, h.note.title)
            item.setData(ROLE + 3, lines[0][:300] if lines else "")
            item.setToolTip(h.note.rel)
            self.results.addItem(item)
        if not hits:
            item = QListWidgetItem(tr("grimoire.spells.notel.page", "Nothing matches “{query}”.")
                                   .format(query=i18n.isolate(q)))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)

    def _result_clicked(self, item):
        data = item.data(ROLE)
        if not data:
            return
        words, _ = index.terms(self.search.text())
        self.open_path(Path(data), find=words[0] if words else "")

    def _open_first_result(self):
        if self._search_timer.isActive():
            self._search_timer.stop()
            self._search()
            QTimer.singleShot(120, self._open_first_result)
            return
        if self.results.count() and self.results.item(0).data(ROLE):
            self._result_clicked(self.results.item(0))

    # ================================================================ tabs and documents
    def current(self) -> Doc | None:
        i = self.tabs.currentIndex()
        return self.tabs.tabData(i) if i >= 0 else None

    def editor(self) -> Editor | None:
        d = self.current()
        return d.editor if d else None

    def _index_of(self, d: Doc) -> int:
        for i in range(self.tabs.count()):
            if self.tabs.tabData(i) is d:
                return i
        return -1

    def _find_doc(self, path: Path) -> Doc | None:
        return next((d for d in self.docs if _same(d.path, path)), None)

    def _autosaves(self, d: Doc) -> bool:
        return d.in_vault or self.s["autosave_files"]

    def open_paths(self, paths: list):
        """Open files given on the command line (or by another grimoire-notel)."""
        for p in paths:
            self.open_path(Path(p), new_tab=True)

    def open_path(self, path: Path, new_tab: bool = False, find: str = ""):
        existing = self._find_doc(path)
        if existing:
            self.tabs.setCurrentIndex(self._index_of(existing))
            self.body.setCurrentIndex(1)
            self._found(find)
            return
        self.run(lambda: store.read(path), lambda r: self._loaded(path, r, new_tab, find))

    def _loaded(self, path: Path, r, new_tab: bool, find: str):
        if isinstance(r, Exception):
            if isinstance(r, FileNotFoundError):
                msg = tr("grimoire.spells.notel.page", "{name} isn't there any more.").format(
                    name=i18n.isolate(path.name))
            else:
                msg = tr("grimoire.spells.notel.page", "Couldn't open {name}: {error}").format(
                    name=i18n.isolate(path.name), error=r)
            self.say(msg)
            return
        existing = self._find_doc(path)
        if existing:                                     # opened twice quickly
            self.tabs.setCurrentIndex(self._index_of(existing))
            return
        cur = self.current()
        reuse = (not new_tab and cur is not None and cur.in_vault and not cur.modified and not cur.conflict
                 and not cur.saving and store.in_vault(path, self.root))
        d = self._make_doc(path, r)
        if reuse:
            i = self._index_of(cur)
            self._drop(cur)
            self._insert_tab(d, i)
        else:
            self._insert_tab(d, self.tabs.currentIndex() + 1 if self.tabs.count() else 0)
        self._found(find)

    def _make_doc(self, path: Path, loaded: store.Loaded) -> Doc:
        prose = store.is_note(path)
        first = loaded.text.split("\n", 1)[0]
        lang = "markdown" if store.is_markdown(path) else ("" if path.suffix.lower() == ".txt"
                                                            else highlight.language_for(path.name, first))
        if len(loaded.text) > BIG_HIGHLIGHT:
            lang = ""
        ed = Editor(lang, note=prose)
        ed.configure(self.s["mono"], self.s["line_numbers"], self.s["wrap"], self.s["font_size"])
        ed.setPlainText(loaded.text)
        ed.detect_indent()
        ed.document().setModified(False)
        d = Doc(path, loaded, ed, bool(self.snap) and store.in_vault(path, self.root))
        if self.snap:
            ed.set_names(sorted({n.title for n in self.snap.notes.values() if store.is_markdown(n.path)},
                                key=str.lower))
        ed.textChanged.connect(lambda d=d: self._edited(d))
        ed.document().modificationChanged.connect(lambda _m, d=d: self._title(d))
        ed.cursorPositionChanged.connect(lambda: self._count_timer.start())
        ed.link.connect(lambda t, d=d: self.follow_link(t, d))
        ed.zoom.connect(self._zoom)
        d.timer.timeout.connect(lambda d=d: self.save(d))
        self._watch(d)
        return d

    def _insert_tab(self, d: Doc, at: int):
        self.docs.append(d)
        self.editors.addWidget(d.editor)
        i = self.tabs.insertTab(at, d.path.stem if d.markdown else d.path.name)
        self.tabs.setTabData(i, d)
        self.tabs.setTabToolTip(i, tilde(d.path))
        close = _tool("close", tr("grimoire.spells.notel.page", "Close tab (Ctrl+W)"),
                      lambda d=d: self.close_tab(self._index_of(d)), 12)
        self.tabs.setTabButton(i, QTabBar.ButtonPosition.RightSide, close)
        self.tabs.setCurrentIndex(i)
        self._tab_changed(i)
        self.body.setCurrentIndex(1)
        d.editor.setFocus()
        self._tabs_timer.start()

    def _drop(self, d: Doc):
        """Forget a document and its tab (callers made sure nothing unsaved is lost)."""
        d.timer.stop()
        if self.fwatch and str(d.path) in self.fwatch.files():
            self.fwatch.removePath(str(d.path))
        i = self._index_of(d)
        if d in self.docs:
            self.docs.remove(d)
        self.editors.removeWidget(d.editor)
        d.editor.deleteLater()
        if i >= 0:
            self.tabs.removeTab(i)
        self._tabs_timer.start()
        if not self.tabs.count():
            self._tab_changed(-1)

    def _title(self, d: Doc):
        i = self._index_of(d)
        if i < 0:
            return
        name = d.path.stem if d.markdown else d.path.name
        mark = "! " if d.conflict else "• " if d.modified else ""
        self.tabs.setTabText(i, mark + name)
        if d is self.current():
            self._update_status()

    def _tab_changed(self, i: int):
        d = self.tabs.tabData(i) if i >= 0 else None
        if d is None:
            self.body.setCurrentIndex(0 if self.body.currentIndex() != 2 else 2)
            self.pin_btn.setEnabled(False)
            self.doc_tools.hide()
            self.conflict_bar.hide()
            self.find.hide()
            self._backlinks()
            self._update_status()
            self._window_title()
            return
        self.editors.setCurrentWidget(d.editor)
        self.doc_tools.show()
        if self.body.currentIndex() == 0:
            self.body.setCurrentIndex(1)
        self.pin_btn.setEnabled(d.in_vault)
        self.pin_btn.setChecked(str(d.path) in self.s["pinned"])
        self._apply_view()
        self._show_conflict()
        self._backlinks()
        self._update_status()
        self._window_title()
        if self.find.isVisible():
            self.find.refresh(move=False)
        self._tabs_timer.start()

    def _window_title(self):
        if not self.standalone:
            return
        d = self.current()
        self.window().setWindowTitle(f"{d.path.name} — NoteL" if d else "NoteL")

    def _cycle(self, step: int):
        n = self.tabs.count()
        if n:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % n)

    def close_tab(self, i: int):
        d = self.tabs.tabData(i) if i >= 0 else None
        if d is None:
            return
        if d.modified:
            if self._autosaves(d) and not d.conflict:
                d.closing = True
                self.save(d)
                return
            box = QMessageBox(QMessageBox.Icon.Warning, tr("grimoire.spells.notel.page", "Unsaved changes"),
                              tr("grimoire.spells.notel.page", "Save the changes to {name}?")
                              .format(name=i18n.isolate(d.path.name)),
                              QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                              | QMessageBox.StandardButton.Cancel, self)
            if d.conflict:
                box.setText(tr("grimoire.spells.notel.page", "{name} changed on disk too. Close it and lose your "
                                                              "changes?")
                            .format(name=i18n.isolate(d.path.name)))
                box.setStandardButtons(QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            answer = box.exec()
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save:
                d.closing = True
                self.save(d)
                return
        self._drop(d)

    def _tab_menu(self, pos):
        i = self.tabs.tabAt(pos)
        d = self.tabs.tabData(i) if i >= 0 else None
        if d is None:
            return
        menu = QMenu(self)
        menu.addAction(tr("grimoire.spells.notel.page", "Close"), lambda: self.close_tab(self._index_of(d)))
        menu.addAction(tr("grimoire.spells.notel.page", "Close the others"), lambda: [self.close_tab(self._index_of(o))
                                                             for o in list(self.docs) if o is not d])
        menu.addAction(tr("grimoire.spells.notel.page", "Copy the path"),
                       lambda: QGuiApplication.clipboard().setText(str(d.path)))
        menu.addAction(tr("grimoire.spells.notel.page", "Show in VaultL"), lambda: self.reveal(d.path))
        menu.exec(self.tabs.mapToGlobal(pos))

    def _remember_tabs(self):
        paths = [str(self.tabs.tabData(i).path) for i in range(self.tabs.count())]
        cur = self.current()
        if paths != self.s["tabs"] or (cur and str(cur.path) != self.s["current"]):
            self._set("tabs", paths, current=str(cur.path) if cur else "")

    def _restore_tabs(self):
        paths = [Path(p) for p in self.s["tabs"]]
        current = self.s["current"]
        if not paths:
            return

        def work():
            out = []
            for p in paths:
                try:
                    out.append((p, store.read(p)))
                except (OSError, store.NotText):
                    pass
            return out

        def done(result):
            if isinstance(result, Exception):
                return
            for p, loaded in result:
                if not self._find_doc(p):
                    self._insert_tab(self._make_doc(p, loaded), self.tabs.count())
            for i in range(self.tabs.count()):
                if str(self.tabs.tabData(i).path) == current:
                    self.tabs.setCurrentIndex(i)
        self.run(work, done)

    def _found(self, word: str):
        ed = self.editor()
        if not ed or not word:
            return
        c = ed.document().find(word)
        if not c.isNull():
            ed.setTextCursor(c)
            ed.centerCursor()

    # ================================================================ editing and saving
    def _edited(self, d: Doc):
        if self._autosaves(d) and not d.conflict and d.modified:
            d.timer.start()
        if d is self.current():
            self._count_timer.start()
            if self.preview.isVisible() and d.markdown:
                self._render_timer.start()
            self.find.edited()

    def save_current(self):
        d = self.current()
        if not d:
            return
        if d.conflict:
            self._show_conflict()
            return
        self.save(d)

    def save(self, d: Doc, force: bool = False):
        d.timer.stop()
        if d.saving:
            d.again = True
            return
        if d not in self.docs:
            return
        d.saving = True
        text = d.editor.toPlainText()
        rev = d.editor.document().revision()
        path, loaded, snap = d.path, d.loaded, self.snap
        in_vault = d.in_vault

        def work():
            new = d.landed = store.save(path, text, loaded, force)
            return new, (index.with_note(snap, path, text) if snap and in_vault else None)
        self._update_status()
        self.run(work, lambda r: self._saved(d, rev, snap, r, loaded), writer=True)

    def _saved(self, d: Doc, rev: int, base_snap, r, base=None):
        d.saving = False
        d.landed = None
        if d not in self.docs or d.loaded is not base:
            return                    # closed, or _save_now already wrote a newer version while this was on its way
        if isinstance(r, store.Conflict):
            d.conflict = r.kind
            d.closing = False
            self._title(d)
            self._show_conflict()
            if d is not self.current():
                self.say(tr("grimoire.spells.notel.page", "{name} changed on disk: open its tab to choose what "
                                                           "to keep.")
                         .format(name=i18n.isolate(d.path.name)))
            return
        if isinstance(r, Exception):
            d.error = str(r)
            d.closing = False
            self.say(tr("grimoire.spells.notel.page", "Couldn't save {name}: {error}")
                     .format(name=i18n.isolate(d.path.name), error=r))
            self._update_status()
            return
        new, snap = r
        d.loaded, d.error, d.conflict = new, "", ""
        if d.editor.document().revision() == rev:
            d.editor.document().setModified(False)
        if snap is not None and self.snap is base_snap:
            self.snap = snap
            self._backlinks()
        self._watch(d)
        self._title(d)
        self._show_conflict()
        if d.closing and not d.modified:
            self._drop(d)
            return
        if d.again:
            d.again = False
            self.save(d)
        self._update_status()

    def save_as(self):
        d = self.current()
        if not d:
            return
        start = str(free_name(d.path))
        name, _ = QFileDialog.getSaveFileName(self, tr("grimoire.spells.notel.page", "Save as"), start)
        if not name:
            return
        dest = Path(name)
        text = d.editor.toPlainText()
        loaded = d.loaded

        def work():
            if dest.exists() and not _same(dest, d.path):
                trash(dest)                   # the dialog asked before replacing; the old one goes to the Trash
            new = store.save(dest, text, store.Loaded(text, loaded.encoding, loaded.newline, "", (), 0o644)
                             if loaded else None, force=True)
            return new

        def done(r):
            if isinstance(r, Exception):
                self.say(tr("grimoire.spells.notel.page", "Couldn't save {name}: {error}")
                         .format(name=i18n.isolate(dest.name), error=r))
                return
            if self.fwatch and str(d.path) in self.fwatch.files():
                self.fwatch.removePath(str(d.path))
            d.path, d.loaded, d.conflict = dest, r, ""
            d.in_vault = bool(self.snap) and store.in_vault(dest, self.root)
            d.editor.document().setModified(False)
            self._watch(d)
            self._title(d)
            self.tabs.setTabToolTip(self._index_of(d), tilde(dest))
            self._tab_changed(self.tabs.currentIndex())
            self.scan()
        self.run(work, done, writer=True)

    # ---------------------------------------------------------------- changes on disk
    def _watch(self, d: Doc):
        if self.fwatch is None:
            self.fwatch = QFileSystemWatcher(self)
            self.fwatch.fileChanged.connect(self._disk_changed)
        if str(d.path) not in self.fwatch.files() and d.path.exists():
            self.fwatch.addPath(str(d.path))

    def _disk_changed(self, path: str):
        d = self._find_doc(Path(path))
        if not d or d.saving:
            return

        def check():
            try:
                return store.read(Path(path))
            except FileNotFoundError:
                return None
        QTimer.singleShot(150, lambda: self.run(check, lambda r: self._checked(d, r)))   # let a rename finish

    def _checked(self, d: Doc, r):
        if d not in self.docs or d.saving:
            return
        if isinstance(r, Exception):
            return
        if r is None:
            if not d.conflict:
                d.conflict = "deleted"
                self._title(d)
                self._show_conflict()
            return
        self._watch(d)
        if d.loaded and r.digest == d.loaded.digest:
            if d.conflict == "deleted":                 # it came back as it was
                d.conflict = ""
                self._title(d)
                self._show_conflict()
            return
        if d.modified or d.conflict:
            d.conflict = "changed"
            self._title(d)
            self._show_conflict()
            return
        self._replace_text(d, r)
        self.say(tr("grimoire.spells.notel.page", "{name} changed on disk, so NoteL loaded the new version "
                                                   "(Ctrl+Z brings yours back).")
                 .format(name=i18n.isolate(d.path.name)))

    def _replace_text(self, d: Doc, loaded: store.Loaded):
        """Put the disk's text in the editor as one undoable edit, keeping the cursor about where it was."""
        ed = d.editor
        pos = ed.textCursor().position()
        bar = ed.verticalScrollBar().value()
        c = QTextCursor(ed.document())
        c.beginEditBlock()
        c.select(QTextCursor.SelectionType.Document)
        c.insertText(loaded.text)
        c.endEditBlock()
        c.setPosition(min(pos, len(loaded.text)))
        ed.setTextCursor(c)
        ed.verticalScrollBar().setValue(bar)
        d.loaded = loaded
        d.conflict = ""
        d.timer.stop()
        ed.document().setModified(False)
        self._title(d)
        self._show_conflict()

    def _show_conflict(self):
        d = self.current()
        if not d or not d.conflict:
            self.conflict_bar.hide()
            return
        name = i18n.isolate(d.path.name)
        if d.conflict == "deleted":
            self.conflict_text.setText(tr("grimoire.spells.notel.page", "{name} was deleted or moved on disk. "
                                                                     "Your text is still here.")
                                       .format(name=name))
            shown = ("again", "close")
        else:
            self.conflict_text.setText(tr("grimoire.spells.notel.page", "{name} was changed by another program since "
                                                                     "NoteL opened it. "
                                               "Nothing was overwritten.").format(name=name))
            shown = ("reload", "copy", "mine")
        for k, b in self.c_buttons.items():
            b.setVisible(k in shown)
        self.conflict_bar.show()

    def _resolve(self, key: str):
        d = self.current()
        if not d:
            return
        if key == "close":
            d.editor.document().setModified(False)
            self._drop(d)
        elif key in ("again", "mine"):
            d.conflict = ""
            self.save(d, force=True)
        elif key == "reload":
            self.run(lambda: store.read(d.path), lambda r: self._replace_text(d, r) if not isinstance(r, Exception)
                     else self.say(str(r)))
        elif key == "copy":
            text, path = d.editor.toPlainText(), d.path

            def work():
                copy = store.create(path, text)          # free_name: "name (2).md" next to it
                return copy, store.read(path)

            def done(r):
                if isinstance(r, Exception):
                    self.say(tr("grimoire.spells.notel.page", "Couldn't save a copy: {error}").format(error=r))
                    return
                copy, theirs = r
                self._replace_text(d, theirs)
                self.open_path(copy, new_tab=True)
                self.say(tr("grimoire.spells.notel.page", "Your version is in {name}; this tab now shows theirs.")
                         .format(name=i18n.isolate(copy.name)))
                self.scan()
            self.run(work, done, writer=True)

    # ================================================================ view and preview
    def set_view(self, view: str):
        if view != self.s["view"]:
            self._set("view", view)
        self._apply_view()

    def _apply_view(self):
        d = self.current()
        md = bool(d and d.markdown)
        view = self.s["view"] if md else "edit"
        for k, b in self.view_btns.items():
            b.setChecked(k == view)
            b.setEnabled(md)
        self.editors.setVisible(view != "read")
        self.preview.setVisible(view != "edit")
        if view == "split":
            sizes = self.split.sizes()
            if min(sizes) < 120:                       # first time side by side: half and half
                half = max(200, sum(sizes) // 2)
                self.split.setSizes([half, half])
        if view != "edit" and d:
            self._render()
        if view == "read":
            self.preview.setFocus()
        elif d:
            d.editor.setFocus()

    def _render(self):
        d = self.current()
        if not d or not d.markdown or not self.preview.isVisible():
            return
        if self._render_busy:
            self._render_again = True
            return
        self._render_busy = True
        text = d.editor.toPlainText()
        snap = self.snap if d.in_vault else None
        rel = ""
        if snap:
            try:
                rel = d.path.resolve().relative_to(snap.root.resolve()).as_posix()
            except ValueError:
                snap = None
        base, cache = d.path.parent, self._image_cache
        self.run(lambda: (d, preview.build(text, snap, rel, base, cache=cache)), self._rendered)

    def _rendered(self, r):
        self._render_busy = False
        if not isinstance(r, Exception) and r[0] is self.current():
            md, images = r[1]
            self.preview.show_markdown(md, images, self.s["font_size"] + 1)
        if self._render_again:
            self._render_again = False
            self._render()

    def _hover(self, url: str):
        if url:
            self.state.setText(i18n.ltr(url))
        else:
            self._update_status()

    def _zoom(self, step: int):
        size = 14 if step == 0 else min(32, max(9, self.s["font_size"] + step))
        self.size_spin.setValue(size)

    # ================================================================ links
    def follow_url(self, url: QUrl):
        scheme = url.scheme()
        d = self.current()
        if scheme == "note":
            self.follow_link("[[" + QUrl.fromPercentEncoding(url.path().encode()) + "]]", d)
        elif scheme == "tag":
            self.search.setText("#" + QUrl.fromPercentEncoding(url.path().encode()))
        elif scheme in ("http", "https", "mailto"):
            QDesktopServices.openUrl(url)
        elif scheme in ("", "file") and d:
            target = url.toLocalFile() if scheme == "file" else QUrl.fromPercentEncoding(url.path().encode())
            self.follow_link(target, d)

    def follow_link(self, target: str, d: Doc | None):
        """A [[link]], a relative path or a URL from the editor (Ctrl+click) or the preview (click)."""
        if target.startswith(("http://", "https://", "mailto:")):
            QDesktopServices.openUrl(QUrl(target))
            return
        if target.startswith("[["):
            inner = target[2:-2].split("|")[0].split("#")[0].strip()
            if not inner:
                return
            rel = ""
            if d and self.snap and d.in_vault:
                try:
                    rel = d.path.resolve().relative_to(self.snap.root.resolve()).as_posix()
                except ValueError:
                    rel = ""
            hit = self.snap.resolve(inner, rel) if self.snap else None
            if hit:
                self.open_path(self.snap.root / hit, new_tab=True)
                return
            if inner.lower().endswith(store.IMAGE_EXT) and self.snap:
                img = self.snap.resolve_file(inner, rel)
                if img:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(img)))
                return
            self._create_linked(inner)
            return
        if d is None or not target:
            return
        from urllib.parse import unquote
        p = Path(unquote(target))
        p = p if p.is_absolute() else d.path.parent / p
        if store.is_note(p) or highlight.language_for(p.name):
            self.open_path(p, new_tab=True)
        elif p.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def _create_linked(self, target: str):
        """Clicking a link to a note that doesn't exist yet makes it (Obsidian does the same)."""
        if not self.snap:
            return
        parts = [store.safe_link_name(x) for x in target.split("/") if x.strip() and x.strip() not in (".", "..")]
        folder = self.root.joinpath(*parts[:-1]) if len(parts) > 1 else self.root
        name = store.note_name(parts[-1]) if parts else "Untitled.md"
        title = parts[-1] if parts else "Untitled"
        self.run(lambda: store.create(folder / name, f"# {title}\n\n"),
                 lambda r: self._made(r, tr("grimoire.spells.notel.page", "Made the new note {name}.")))

    def _made(self, r, message: str = ""):
        if isinstance(r, Exception):
            self.say(str(r))
            return
        self.open_path(r, new_tab=True)
        if message:
            self.say(message.format(name=i18n.isolate(r.stem)))
        self.scan()

    def _backlinks(self):
        d = self.current()
        self.backlinks.clear()
        rel = ""
        if d and d.in_vault and self.snap:
            try:
                rel = d.path.resolve().relative_to(self.snap.root.resolve()).as_posix()
            except ValueError:
                rel = ""
        refs = self.snap.backlinks.get(rel, []) if rel and self.snap else []
        for r in refs:
            note = self.snap.notes.get(r)
            item = QListWidgetItem(glyph("link", 16), note.title if note else r)
            item.setData(ROLE, str(self.snap.root / r))
            item.setToolTip(r)
            self.backlinks.addItem(item)
        row = self.backlinks.sizeHintForRow(0) if refs else 34
        self.backlinks.setFixedHeight(min(170, row * max(1, len(refs)) + 6))
        self.links_btn.setEnabled(bool(refs))
        self.links_btn.setText(tr("grimoire.spells.notel.page", "%n backlink(s)", n=len(refs)) if rel else "")
        self.links_btn.setVisible(bool(rel))
        self.links_panel.setVisible(bool(refs) and self.links_btn.isChecked() and self.body.currentIndex() == 1)

    # ================================================================ file actions
    def _target_folder(self) -> Path:
        item = self.tree.currentItem()
        if item and item.data(0, ROLE + 1) == "folder" and self.tree.hasFocus():
            return Path(item.data(0, ROLE))
        d = self.current()
        if d and d.in_vault:
            return d.path.parent
        return self.root

    def _ask(self, title: str, label: str, text: str = "") -> str:
        name, ok = QInputDialog.getText(self, title, label, QLineEdit.EchoMode.Normal, text)
        return name.strip() if ok else ""

    def new_note(self, folder: Path | None = None):
        if not self.snap:
            self.say(tr("grimoire.spells.notel.page", "The notes folder isn't there. Pick one in NoteL's settings."))
            return
        folder = folder if isinstance(folder, Path) else self._target_folder()
        name = self._ask(tr("grimoire.spells.notel.page", "New note"), tr("grimoire.spells.notel.page", "Name"),
                         tr("grimoire.spells.notel.page", "Untitled"))
        if not name:
            return
        try:
            file = store.note_name(name)
        except ValueError as e:
            self.say(str(e))
            return
        self.run(lambda: store.create(folder / file), self._made)

    def new_folder(self, parent: Path | None = None):
        if not self.snap:
            return
        parent = parent if isinstance(parent, Path) else self._target_folder()
        name = self._ask(tr("grimoire.spells.notel.page", "New folder"), tr("grimoire.spells.notel.page", "Name"))
        if name:
            self.run(lambda: store.new_folder(parent, name), lambda r: self.say(str(r)) if isinstance(r, Exception)
                     else self.scan())

    def daily(self):
        if not self.snap and store.ensure_vault(self.s) is None:
            self.say(tr("grimoire.spells.notel.page", "The notes folder isn't there. Pick one in NoteL's settings."))
            return
        s, root = dict(self.s), store.vault(self.s)

        def done(r):
            if isinstance(r, Exception):
                self.say(str(r))
                return
            self.open_path(r)
            self.scan()
        self.run(lambda: store.daily(s, root), done)

    def open_dialog(self):
        start = str(self.current().path.parent if self.current() else self.root)
        names, _ = QFileDialog.getOpenFileNames(self, tr("grimoire.spells.notel.page", "Open"), start)
        for n in names:
            self.open_path(Path(n), new_tab=True)

    def rename_current(self):
        d = self.current()
        if d:
            self.rename(d.path)

    def rename(self, path: Path):
        is_dir = path.is_dir()
        old = path.stem if store.is_markdown(path) else path.name
        name = self._ask(tr("grimoire.spells.notel.page", "Rename"), tr("grimoire.spells.notel.page", "New name"), old)
        if not name or name == old:
            return
        for d in self.docs:                              # land pending edits first
            if d.modified and self._autosaves(d) and not d.conflict and (_same(d.path, path) or
                                                                         str(d.path).startswith(str(path) + "/")):
                self._save_now(d)

        def done(r):
            if isinstance(r, Exception):
                self.say(str(r))
                return
            for d in self.docs:
                if _same(d.path, path) or (is_dir and str(d.path).startswith(str(path) + "/")):
                    if self.fwatch and str(d.path) in self.fwatch.files():
                        self.fwatch.removePath(str(d.path))
                    d.path = r / d.path.relative_to(path) if is_dir else r
                    self._watch(d)
                    self._title(d)
                    self.tabs.setTabToolTip(self._index_of(d), tilde(d.path))
            pins = [str(r / Path(p).relative_to(path)) if is_dir and p.startswith(str(path) + "/")
                    else str(r) if p == str(path) else p for p in self.s["pinned"]]
            self._set("pinned", pins)
            self._window_title()
            self.scan()
        self.run(lambda: store.rename(path, name), done)

    def remove(self, path: Path):
        is_dir = path.is_dir()
        name = i18n.isolate(path.name)
        text = (tr("grimoire.spells.notel.page", "Move the folder {name} and everything in it to the Trash?") if is_dir
                else tr("grimoire.spells.notel.page", "Move {name} to the Trash?")).format(name=name)
        if QMessageBox.question(self, tr("grimoire.spells.notel.page", "Move to Trash"), text,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        gone = [d for d in self.docs if _same(d.path, path) or (is_dir and str(d.path).startswith(str(path) + "/"))]
        for d in gone:                                    # no autosave may bring it back
            d.timer.stop()
            d.editor.document().setModified(False)
            self._drop(d)

        def done(r):
            if isinstance(r, Exception):
                self.say(tr("grimoire.spells.notel.page", "Couldn't move {name} to the Trash: {error}")
                         .format(name=name, error=r))
            else:
                self._set("pinned", [p for p in self.s["pinned"] if p != str(path)
                                     and not p.startswith(str(path) + "/")])
                self.say(tr("grimoire.spells.notel.page", "Moved {name} to the Trash.").format(name=name))
            self.scan()
        self.run(lambda: store.remove(path), done, writer=True)

    def toggle_pin(self, path: Path | None = None):
        if not isinstance(path, Path):
            d = self.current()
            if not d or not d.in_vault:
                return
            path = d.path
        pins = list(self.s["pinned"])
        if str(path) in pins:
            pins.remove(str(path))
        else:
            pins.insert(0, str(path))
        self._set("pinned", pins)
        d = self.current()
        self.pin_btn.setChecked(bool(d) and str(d.path) in pins)
        self._fill_tree()

    def reveal(self, path: Path):
        try:
            subprocess.Popen([str(command("grimoire-vaultl")), str(path)], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            self.say(tr("grimoire.spells.notel.page", "Couldn't open VaultL: {error}").format(error=e))

    def _fill_more(self):
        m = self.more_menu
        m.clear()
        d = self.current()
        for label, slot, needs in ((tr("grimoire.spells.notel.page", "Save (Ctrl+S)"), self.save_current, True),
                                   (tr("grimoire.spells.notel.page", "Save as…"), self.save_as, True),
                                   (tr("grimoire.spells.notel.page", "Rename… (F2)"), self.rename_current, True),
                                   (tr("grimoire.spells.notel.page", "Export as PDF…"), lambda: self.export("pdf"),
                                    "md"),
                                   (tr("grimoire.spells.notel.page", "Export as HTML…"), lambda: self.export("html"),
                                    "md"),
                                   (tr("grimoire.spells.notel.page", "Show in VaultL"),
                                    lambda: d and self.reveal(d.path), True),
                                   (tr("grimoire.spells.notel.page", "Move to Trash"),
                                    lambda: d and self.remove(d.path), True)):
            a = m.addAction(label, slot)
            a.setEnabled(bool(d) and (needs is True or d.markdown))
        m.addSeparator()
        m.addAction(tr("grimoire.spells.notel.page", "Settings"), self.show_settings)

    def export(self, kind: str):
        d = self.current()
        if not d:
            return
        suffix = ".pdf" if kind == "pdf" else ".html"
        start = d.path.with_suffix(suffix)
        if not os.access(start.parent, os.W_OK):
            start = store.documents() / start.name
        caption = tr("grimoire.spells.notel.page", "Export as PDF") if kind == "pdf" \
            else tr("grimoire.spells.notel.page", "Export as HTML")
        name, _ = QFileDialog.getSaveFileName(self, caption, str(free_name(start)),
                                              "PDF (*.pdf)" if kind == "pdf" else "HTML (*.html *.htm)")
        if not name:
            return
        dest = Path(name)
        if dest.suffix.lower() not in ((".pdf",) if kind == "pdf" else (".html", ".htm")):
            dest = dest.with_name(dest.name + suffix)
        text, title = d.editor.toPlainText(), d.path.stem
        snap = self.snap if d.in_vault else None
        rel = ""
        if snap:
            try:
                rel = d.path.resolve().relative_to(snap.root.resolve()).as_posix()
            except ValueError:
                snap = None
        base = d.path.parent

        def work():
            if dest.exists():
                trash(dest)                       # replaced only after the dialog asked; the old one is kept
            (preview.export_pdf if kind == "pdf" else preview.export_html)(text, dest, snap, rel, base, title)
            return dest

        def done(r):
            if isinstance(r, Exception):
                self.say(tr("grimoire.spells.notel.page", "Couldn't export: {error}").format(error=r))
            else:
                self.say(tr("grimoire.spells.notel.page", "Exported to {path}.").format(path=i18n.ltr(tilde(r))))
        self.say(tr("grimoire.spells.notel.page", "Exporting…"))
        self.run(work, done, writer=True)

    # ================================================================ settings
    def _set(self, key, value, **more):
        self.s[key] = value
        self.s.update(more)
        s = dict(self.s)

        def done(r):
            if isinstance(r, Exception):
                self.say(tr("grimoire.spells.notel.page", "Couldn't save NoteL's settings: {error}").format(error=r))
        self.run(lambda: store.save_settings(s), done, writer=True)
        if key in ("mono", "line_numbers", "wrap", "font_size"):
            for d in self.docs:
                d.editor.configure(self.s["mono"], self.s["line_numbers"], self.s["wrap"], self.s["font_size"])
            self._render_timer.start()
        if key == "autosave_files":
            for d in self.docs:
                if d.modified:
                    self._edited(d)
            self._update_status()

    def show_settings(self):
        self.vault_label.setText(i18n.ltr(tilde(store.vault(self.s))))
        self.daily_edit.setText(self.s["daily_folder"])
        self.body.setCurrentIndex(2)
        self.find.hide()
        self.conflict_bar.hide()
        self.links_panel.hide()

    def hide_settings(self):
        self.body.setCurrentIndex(1 if self.current() else 0)
        self._show_conflict()
        self._backlinks()

    def pick_vault(self):
        folder = QFileDialog.getExistingDirectory(self, tr("grimoire.spells.notel.page", "Notes folder"),
                                                  str(store.vault(self.s)))
        if folder:
            self.set_vault(folder)

    def set_vault(self, folder: str):
        if folder and Path(folder).resolve() == store.default_vault().resolve():
            folder = ""
        self._set("vault", folder)
        self.vault_label.setText(i18n.ltr(tilde(store.vault(self.s))))
        self.snap = None
        self.search.clear()
        self.scan()

    def _daily_folder(self):
        value = self.daily_edit.text().strip().strip("/")
        if ".." in Path(value).parts:
            value = ""
            self.daily_edit.setText("")
        if value != self.s["daily_folder"]:
            self._set("daily_folder", value)

    # ================================================================ status
    def _update_status(self):
        if self._toast_timer.isActive():
            return self._update_info()
        d = self.current()
        if not d:
            self.state.setText("")
        elif d.conflict:
            self.state.setText(tr("grimoire.spells.notel.page", "Changed on disk: choose above what to keep"))
        elif d.error and d.modified:
            self.state.setText(tr("grimoire.spells.notel.page", "Not saved: {error}").format(error=d.error))
        elif d.saving:
            self.state.setText(tr("grimoire.spells.notel.page", "Saving…"))
        elif d.modified and not self._autosaves(d):
            self.state.setText(tr("grimoire.spells.notel.page", "Edited · Ctrl+S saves (autosave is for notes)"))
        elif d.modified:
            self.state.setText(tr("grimoire.spells.notel.page", "Edited"))
        else:
            self.state.setText(tr("grimoire.spells.notel.page", "Saved"))
        self._update_info()

    def _update_info(self):
        d = self.current()
        if not d:
            self.info.setText("")
            return
        c = d.editor.textCursor()
        doc = d.editor.document()
        bits = []
        if doc.characterCount() < 2_000_000:
            text = c.selectedText().replace(" ", "\n") if c.hasSelection() else d.editor.toPlainText()
            n = store.words(text)
            bits.append(tr("grimoire.spells.notel.page", "%n word(s) selected", n=n) if c.hasSelection()
                        else tr("grimoire.spells.notel.page", "%n word(s)", n=n))
        bits.append(tr("grimoire.spells.notel.page", "Line {line}, column {col}").format(line=c.blockNumber() + 1,
                                                               col=c.positionInBlock() + 1))
        bits.append(highlight.display_name(d.editor.lang, d.path.name) if d.editor.lang or not d.markdown
                    else "Markdown")
        if d.loaded:
            enc = {"utf-8": "UTF-8", "utf-8-sig": "UTF-8 BOM", "latin-1": "Latin-1"}.get(d.loaded.encoding,
                                                                                     d.loaded.encoding)
            bits.append(enc + (" · CRLF" if d.loaded.newline == "\r\n" else ""))
        self.info.setText("   ·   ".join(bits))
