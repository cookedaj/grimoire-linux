# SPDX-License-Identifier: GPL-3.0-or-later
"""The reader: one open document with its toolbar, side panel, search and footer, plus fullscreen reading.

PDFs go to PageView (rendered pages); EPUB, Markdown and text go to BookView (reflowing text, a chapter at a time).
Opening, chapter loading and search all run on worker threads and come back through signals tagged with a
generation number, so an answer for a document that was closed in the meantime is simply dropped.
"""
import os
import re

from PySide6.QtCore import QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QSplitter,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.fsutil import tilde
from grimoire.glyphs import glyph
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.readl import library, pdfdoc

ZOOMS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0)
MEASURES = {"narrow": 600, "medium": 720, "wide": 920}


class _Sig(QObject):
    loaded = Signal(object)          # (gen, kind, obj or Exception)
    piece = Signal(object)           # (gen, index, piece or Exception)
    found = Signal(object)           # (gen, search id, {where: [hits]}, done)


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def tool(icon: str, tip: str, slot=None, checkable=False) -> QToolButton:
    b = QToolButton()
    b.setObjectName("Tool")
    b.setIcon(glyph(icon, 18))
    b.setIconSize(QSize(18, 18))
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    if slot:
        b.clicked.connect(slot)
    return b


class Notice(QWidget):
    """A centered message in place of the document: loading, an error, a password, the QtPdf package."""
    password = Signal(str)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(56, 48, 56, 48)
        lay.addStretch(1)
        self.heading = _label("", "PageHeading", wrap=True)
        self.text = _label("", "Muted", wrap=True)
        for w in (self.heading, self.text):
            w.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lay.addWidget(w)
        lay.addSpacing(10)
        self.cmd = _label("", "Mono")
        self.cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.cmd, 0, Qt.AlignmentFlag.AlignHCenter)
        self.copy = QPushButton(tr("grimoire.spells.readl.reader", "Copy command"))
        self.copy.clicked.connect(lambda: QApplication.clipboard().setText(self.cmd.text()))
        lay.addWidget(self.copy, 0, Qt.AlignmentFlag.AlignHCenter)
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw.setPlaceholderText(tr("grimoire.spells.readl.reader", "Password"))
        self.pw.setMaximumWidth(320)
        self.pw.returnPressed.connect(lambda: self.password.emit(self.pw.text()))
        lay.addWidget(self.pw, 0, Qt.AlignmentFlag.AlignHCenter)
        self.unlock = QPushButton(tr("grimoire.spells.readl.reader", "Open"))
        self.unlock.setObjectName("Primary")
        self.unlock.clicked.connect(lambda: self.password.emit(self.pw.text()))
        lay.addWidget(self.unlock, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(2)

    def show_message(self, heading: str, text: str = "", cmd: str = "", password=False):
        self.heading.setText(heading)
        self.text.setText(text)
        self.text.setVisible(bool(text))
        self.cmd.setText(cmd)
        self.cmd.setVisible(bool(cmd))
        self.copy.setVisible(bool(cmd))
        self.pw.clear()
        self.pw.setVisible(password)
        self.unlock.setVisible(password)
        if password:
            QTimer.singleShot(0, self.pw.setFocus)


class Reader(QWidget):
    back = Signal()                  # show the library
    titleChanged = Signal(str)
    openRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Reader")
        self.sig = _Sig()
        self.sig.loaded.connect(self._loaded)
        self.sig.piece.connect(self._piece)
        self.sig.found.connect(self._found)
        self.s = library.settings()
        self.gen = 0
        self.path = ""
        self.kind = ""
        self.doc = None              # pdfdoc.Doc
        self.renderer = None
        self.source = None           # books.Source
        self.view = None
        self.entry = {}
        self.chapter = -1
        self._after_piece = None
        self.search_id = 0
        self.hits: list = []         # [(page or chapter, index)] in reading order
        self.hit_map: dict = {}
        self.hit_pos = -1
        self.search_done = True
        self._full = None            # (parent, index in its layout) while fullscreen

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.bar = self._make_bar()
        root.addWidget(self.bar)
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        from grimoire.spells.readl.sidebar import Sidebar
        self.side = Sidebar()
        self.side.go_toc.connect(self._go_toc)
        self.side.go_page.connect(lambda p: self.view.go(p) if self.kind == "pdf" and self.view else None)
        self.side.go_mark.connect(self.go_pos)
        self.side.add_mark.connect(self.add_bookmark)
        self.side.remove_mark.connect(self._remove_mark)
        self.side.rename_mark.connect(self._rename_mark)
        self.split.addWidget(self.side)
        self.stack = QStackedWidget()
        self.notice = Notice()
        self.notice.password.connect(lambda pw: self.open(self.path, password=pw))
        self.stack.addWidget(self.notice)
        self.split.addWidget(self.stack)
        self.split.setStretchFactor(1, 1)
        self.split.setSizes([260, 1000])
        root.addWidget(self.split, 1)
        foot = QFrame()
        foot.setObjectName("ReadFoot")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(16, 5, 16, 6)
        self.find_status = _label("", "Tiny")
        self.where = _label("", "Tiny")
        fl.addWidget(self.find_status)
        fl.addStretch(1)
        fl.addWidget(self.where)
        self.foot = foot
        root.addWidget(foot)
        self.side.setVisible(self.s["sidebar"])

        self._save_timer = QTimer(self, singleShot=True, interval=700, timeout=self.save_place)
        self._where_timer = QTimer(self, singleShot=True, interval=120,
                                   timeout=lambda: self.view is not None and self.kind == "pdf"
                                   and self._moved(self.view.page))
        self._search_timer = QTimer(self, singleShot=True, interval=280, timeout=self._start_search)
        self._bar_timer = QTimer(self, singleShot=True, interval=1200, timeout=self._hide_bar)
        self._shortcuts()
        self.setStyleSheet(i18n.qss("""
            QFrame#ReadBar { background: #070707; border-bottom: 1px solid #161616; }
            QFrame#ReadSide { background: #070707; border-right: 1px solid #161616; }
            QFrame#ReadFoot { background: #070707; border-top: 1px solid #141414; }
            QFrame#ReadFoot QLabel { color: #7a7a7a; font-size: 11px; }
            QLabel#ReadTitle { color: #d6d6d6; font-weight: 600; }
            QLineEdit#PageBox { padding: 3px 6px; min-height: 16px; }
            QToolButton#ZoomBtn { border: 1px solid #262626; border-radius: 6px; padding: 4px 8px; color: #bdbdbd; }
            QToolButton#ZoomBtn:hover { border-color: #8a8a8a; color: #ffffff; }
            QToolButton#ZoomBtn::menu-indicator { image: none; width: 0; }
            QTreeWidget#ReadToc, QListWidget#ReadThumbs, QListWidget#ReadMarks { background: transparent;
                border: none; }
            QTreeWidget#ReadToc::item { padding: 4px 2px; color: #a8a8a8; }
            QTreeWidget#ReadToc::item:selected { background: #1a1a1a; color: #ffffff; }
            QListWidget#ReadThumbs::item { color: #6f6f6f; }
            QListWidget#ReadMarks::item { padding: 8px; color: #bdbdbd; }
        """))

    # ------------------------------------------------------------ toolbar
    def _make_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("ReadBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(4)
        lay.addWidget(tool("back", tr("grimoire.spells.readl.reader", "Library (Ctrl+W)"), self.go_back))
        self.side_btn = tool("sidebar", tr("grimoire.spells.readl.reader", "Side panel (F9)"), self.toggle_side,
                             checkable=True)
        self.side_btn.setChecked(self.s["sidebar"])
        lay.addWidget(self.side_btn)
        lay.addSpacing(6)
        self.title = _label("", "ReadTitle")
        self.title.setMinimumWidth(80)
        lay.addWidget(self.title, 1)
        # where you are
        self.page_box = QLineEdit()
        self.page_box.setObjectName("PageBox")
        self.page_box.setFixedWidth(56)
        self.page_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_box.setToolTip(tr("grimoire.spells.readl.reader", "Go to page (Ctrl+G)"))
        self.page_box.returnPressed.connect(self._page_entered)
        self.page_of = _label("", "Muted")
        lay.addWidget(self.page_box)
        lay.addWidget(self.page_of)
        lay.addSpacing(10)
        # zoom
        self.zoom_out = tool("zoomout", tr("grimoire.spells.readl.reader", "Smaller (Ctrl+-)"), lambda: self.zoom(-1))
        self.zoom_btn = QToolButton()
        self.zoom_btn.setObjectName("ZoomBtn")
        self.zoom_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.zoom_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.zoom_menu = QMenu(self.zoom_btn)
        self.zoom_btn.setMenu(self.zoom_menu)
        self.zoom_in = tool("zoomin", tr("grimoire.spells.readl.reader", "Bigger (Ctrl++)"), lambda: self.zoom(1))
        for w in (self.zoom_out, self.zoom_btn, self.zoom_in):
            lay.addWidget(w)
        lay.addSpacing(10)
        # layout and colors
        self.layout_btns = {}
        for lid, icon, tip in (("single", "single", tr("grimoire.spells.readl.reader", "One page (Ctrl+1)")),
                               ("continuous", "continuous",
                                tr("grimoire.spells.readl.reader", "Continuous (Ctrl+2)")),
                               ("two", "twopage", tr("grimoire.spells.readl.reader", "Two pages (Ctrl+3)"))):
            b = tool(icon, tip, lambda _=False, x=lid: self.set_layout(x), checkable=True)
            self.layout_btns[lid] = b
            lay.addWidget(b)
        lay.addSpacing(10)
        self.mode_btns = {}
        for mid, icon, tip in (("day", "day", tr("grimoire.spells.readl.reader", "Day: white pages")),
                               ("paper", "paper", tr("grimoire.spells.readl.reader", "Paper: soft gray pages")),
                               ("night", "night", tr("grimoire.spells.readl.reader", "Night: inverted (Ctrl+I)"))):
            b = tool(icon, tip, lambda _=False, x=mid: self.set_mode(x), checkable=True)
            self.mode_btns[mid] = b
            lay.addWidget(b)
        lay.addSpacing(10)
        self.mark_btn = tool("bookmark", tr("grimoire.spells.readl.reader", "Bookmark this place (Ctrl+B)"),
                             self.toggle_bookmark, checkable=True)
        lay.addWidget(self.mark_btn)
        self.find = QLineEdit()
        self.find.setPlaceholderText(tr("grimoire.spells.readl.reader", "Find (Ctrl+F)"))
        self.find.setClearButtonEnabled(True)
        self.find.setMinimumWidth(150)
        self.find.setMaximumWidth(240)
        self.find.textChanged.connect(lambda _: self._search_timer.start())
        self.find.returnPressed.connect(lambda: self.next_hit(-1 if QApplication.keyboardModifiers()
                                                              & Qt.KeyboardModifier.ShiftModifier else 1))
        self.find.installEventFilter(self)
        lay.addWidget(self.find)
        self.full_btn = tool("fullscreen", tr("grimoire.spells.readl.reader", "Fullscreen reading (F11)"),
                             self.toggle_fullscreen)
        lay.addWidget(self.full_btn)
        self._sync_buttons()
        return bar

    def _sync_buttons(self):
        for k, b in self.layout_btns.items():
            b.setChecked(k == self.s["layout"])
        for k, b in self.mode_btns.items():
            b.setChecked(k == self.s["mode"])
        pdf = self.kind == "pdf"
        ready = self.view is not None                  # nothing to zoom, mark or search before a document shows
        for b in self.layout_btns.values():
            b.setVisible(pdf and ready)
        self.page_box.setVisible(pdf and ready)
        for w in (self.zoom_out, self.zoom_btn, self.zoom_in, self.page_of):
            w.setVisible(ready)
        for w in (self.mark_btn, self.find, self.side_btn):
            w.setEnabled(ready)
        if not self._full and hasattr(self, "side"):   # the side panel only once there's something to list
            self.side.setVisible(ready and self.s["sidebar"])
        self._zoom_menu()

    def _zoom_menu(self):
        m = self.zoom_menu
        m.clear()
        if self.kind == "pdf":
            m.addAction(tr("grimoire.spells.readl.reader", "Fit width"), lambda: self.set_fit("width"))
            m.addAction(tr("grimoire.spells.readl.reader", "Fit page"), lambda: self.set_fit("page"))
            m.addSeparator()
            for z in ZOOMS:
                m.addAction(f"{round(z * 100)}%", lambda x=z: self.set_fit("custom", x * self._dpi()))
        else:
            for fid, name in (("serif", tr("grimoire.spells.readl.reader", "Serif font")),
                              ("sans", tr("grimoire.spells.readl.reader", "Sans font"))):
                a = m.addAction(name, lambda x=fid: self.set_book(font=x))
                a.setCheckable(True)
                a.setChecked(self.s["font"] == fid)
            m.addSeparator()
            for key, name in (("narrow", tr("grimoire.spells.readl.reader", "Narrow column")),
                              ("medium", tr("grimoire.spells.readl.reader", "Medium column")),
                              ("wide", tr("grimoire.spells.readl.reader", "Wide column"))):
                a = m.addAction(name, lambda x=MEASURES[key]: self.set_book(measure=x))
                a.setCheckable(True)
                a.setChecked(self.s["measure"] == MEASURES[key])
            m.addSeparator()
            m.addAction(tr("grimoire.spells.readl.reader", "Reset text size"), lambda: self.set_book(scale=1.0))
        self._zoom_text()

    def _zoom_text(self):
        if self.view is None:
            self.zoom_btn.setText("")
        elif self.kind == "pdf":
            v = self.view
            text = {"width": tr("grimoire.spells.readl.reader", "Fit width"),
                    "page": tr("grimoire.spells.readl.reader", "Fit page")}.get(v.fit, "")
            self.zoom_btn.setText(text or f"{round(v.scale / self._dpi() * 100)}%")
        else:
            self.zoom_btn.setText(f"{round(self.s['font_scale'] * 100)}%")

    def _dpi(self) -> float:
        """Pixels per point at 100% (real size on this screen)."""
        return max(0.5, self.logicalDpiY() / 72)

    def _shortcuts(self):
        ctx = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for keys, slot in (((QKeySequence.StandardKey.Find, "Ctrl+F"), self.focus_find),
                           (("F3",), lambda: self.next_hit(1)), (("Shift+F3",), lambda: self.next_hit(-1)),
                           (("Ctrl+G",), self.focus_page), (("Ctrl+B", "Ctrl+D"), self.toggle_bookmark),
                           (("F9",), self.toggle_side), (("F11", "Ctrl+Shift+F"), self.toggle_fullscreen),
                           (("Ctrl++", "Ctrl+="), lambda: self.zoom(1)), (("Ctrl+-",), lambda: self.zoom(-1)),
                           (("Ctrl+0",), self.zoom_reset), (("Ctrl+I",), self.toggle_night),
                           (("Ctrl+1",), lambda: self.set_layout("single")),
                           (("Ctrl+2",), lambda: self.set_layout("continuous")),
                           (("Ctrl+3",), lambda: self.set_layout("two")),
                           (("Ctrl+W", "Alt+Left"), self.go_back), (("Ctrl+O",), self.openRequested.emit),
                           (("Escape",), self.escape)):
            for k in keys:
                sc = QShortcut(QKeySequence(k), self)
                sc.setContext(ctx)
                sc.activated.connect(slot)

    # ------------------------------------------------------------ opening
    def open(self, path: str, password: str = ""):
        path = library.key(path)
        if path != self.path or not password:
            self.close_doc()
        self.path = path
        self.kind = library.kind_of(path)
        self.entry = library.entry(path)
        self._password_tried = bool(password)
        self.gen += 1
        gen = self.gen
        self.title.setText(os.path.basename(path))
        self.titleChanged.emit(os.path.basename(path))
        self._sync_buttons()
        self.stack.setCurrentWidget(self.notice)
        if not os.path.isfile(path):
            self.notice.show_message(tr("grimoire.spells.readl.reader", "This file isn't there any more"),
                                     tr("grimoire.spells.readl.reader", "It was moved, renamed or deleted: {path}")
                                     .format(path=i18n.ltr(tilde(path))))
            return
        if not self.kind:
            self.notice.show_message(tr("grimoire.spells.readl.reader", "ReadL can't open this kind of file"),
                                     tr("grimoire.spells.readl.reader", "It reads PDF, EPUB, Markdown and text."))
            return
        if self.kind == "pdf" and not pdfdoc.available():
            self.notice.show_message(tr("grimoire.spells.readl.reader", "PDFs need one more package"),
                                     tr("grimoire.spells.readl.reader",
                                        "ReadL draws PDFs with QtPdf, which isn't installed. Install it from a "
                                        "terminal, then open the file again. EPUB, Markdown and text work "
                                        "without it."), pdfdoc.APT)
            return
        self.notice.show_message(tr("grimoire.spells.readl.reader", "Opening…"))
        kind = self.kind

        def work():
            try:
                if kind == "pdf":
                    d = pdfdoc.Doc(path)
                    d.load(password)
                    return gen, kind, d
                from grimoire.spells.readl.books import open_source
                return gen, kind, open_source(path, kind)
            except Exception as e:                 # every failure becomes a message, never a stuck "Opening…"
                return gen, kind, e
        if kind == "pdf":
            POOL.start(Job(work, self.sig.loaded.emit))
        else:
            from grimoire.spells.readl.books import BOOK
            BOOK.start(Job(work, self.sig.loaded.emit))

    def _loaded(self, result):
        gen, kind, obj = result
        if gen != self.gen:
            if hasattr(obj, "close"):
                obj.close()
            return
        if isinstance(obj, Exception):
            if isinstance(obj, pdfdoc.NeedsPassword):
                self.notice.show_message(tr("grimoire.spells.readl.reader", "This PDF is locked"),
                                         tr("grimoire.spells.readl.reader", "That password didn't work. Try again.")
                                         if self._password_tried else
                                         tr("grimoire.spells.readl.reader", "Type its password to read it."),
                                         password=True)
                return
            from grimoire.spells.readl.epub import EpubError
            msg = str(obj) if isinstance(obj, (pdfdoc.PdfError, EpubError)) else \
                tr("grimoire.spells.readl.reader", "It may be damaged, or not what its name says.")
            if isinstance(obj, OSError):
                msg = tr("grimoire.spells.readl.reader", "It couldn't be read: {error}").format(
                    error=obj.strerror or str(obj))
            self.notice.show_message(tr("grimoire.spells.readl.reader", "This file can't be opened"), msg)
            return
        title = ""
        if kind == "pdf":
            self.doc = obj
            title = obj.title or os.path.splitext(os.path.basename(self.path))[0]
            self._build_pdf()
            author, pages = obj.author, obj.page_count
        else:
            self.source = obj
            title = obj.title or os.path.splitext(os.path.basename(self.path))[0]
            self._build_book()
            author, pages = obj.author, len(obj.chapters)
        self.title.setText(title)
        self.title.setToolTip(self.path)
        self.titleChanged.emit(title)
        self.entry = library.opened(self.path, title=title, author=author, kind=kind, pages=pages)
        self._refresh_marks()
        self._sync_buttons()
        if self.find.text().strip():
            self._start_search()

    def _build_pdf(self):
        from grimoire.spells.readl.pageview import PageView, Renderer
        self.renderer = Renderer(self.doc)
        v = PageView(self.renderer)
        v.layout_mode, v.mode = self.s["layout"], self.s["mode"]
        v.fit = self.entry.get("fit", "width")
        v.zoom = self.entry.get("zoom", 1.0) * self._dpi() if v.fit == "custom" else 1.0
        self.view = v
        self.stack.addWidget(v)
        self.stack.setCurrentWidget(v)
        v.relayout()
        pos = self.entry.get("pos") or {}
        page = pos.get("page", 0) if isinstance(pos.get("page"), int) else 0
        page = max(0, min(self.doc.page_count - 1, page))
        y = float(pos.get("y", 0) or 0)
        v.go(page, y * self.doc.sizes[page][1], emit=False)
        v.pageChanged.connect(self._moved)
        v.verticalScrollBar().valueChanged.connect(lambda _: self._where_timer.start())
        v.zoomChanged.connect(self._zoomed)
        self.side.set_toc([(lvl, t, ("page", p, y)) for lvl, t, p, y in self.doc.outline])
        self.side.set_pages(self.renderer, self.doc.sizes, self.doc.labels)
        self._moved(v.page)
        v.setFocus()

    def _build_book(self):
        from grimoire.spells.readl.bookview import BookView
        v = BookView()
        v.mode, v.font_kind, v.scale, v.measure = (self.s["mode"], self.s["font"], self.s["font_scale"],
                                                   self.s["measure"])
        v.edge.connect(self._edge)
        v.moved.connect(self._book_moved)
        v.anchorClicked.connect(self._link)
        v.installEventFilter(self)
        v.viewport().installEventFilter(self)
        self.view = v
        self.stack.addWidget(v)
        self.side.set_toc([(lvl, t, ("chapter", ch, frag)) for lvl, t, ch, frag in self.source.toc])
        self.side.set_pages(None, [], [])
        pos = self.entry.get("pos") or {}
        ch = pos.get("chapter", 0) if isinstance(pos.get("chapter"), int) else 0
        ch = max(0, min(len(self.source.chapters) - 1, ch))
        y = float(pos.get("y", 0) or 0)
        self.load_chapter(ch, lambda: v.go_fraction(y))

    def close_doc(self):
        """Save the place and let go of the document."""
        if self.view is not None:
            self.save_place()
            self.stack.removeWidget(self.view)
            if self.kind == "pdf":
                self.view.close()
            self.view.deleteLater()
            self.view = None
        if self.renderer is not None:
            self.renderer.close()
            self.renderer = None
        self.side.set_pages(None, [], [])
        self.side.set_toc([])
        self.side.set_marks([], self._describe)
        if self.doc is not None:
            doc = self.doc
            self.doc = None
            # closed on the render thread, after the renders already queued for it (they return at once now)
            pdfdoc.RENDER.start(Job(doc.close, lambda _: None))
        if self.source is not None:
            src = self.source
            self.source = None
            from grimoire.spells.readl.books import BOOK
            BOOK.start(Job(src.close, lambda _: None))
        self.gen += 1
        self.chapter = -1
        self.hits, self.hit_map, self.hit_pos = [], {}, -1
        self.find_status.setText("")
        self.where.setText("")

    # ------------------------------------------------------------ chapters (books)
    def load_chapter(self, index: int, then=None):
        if self.source is None:
            return
        index = max(0, min(len(self.source.chapters) - 1, index))
        if index == self.chapter and self.view is not None and self.stack.currentWidget() is self.view:
            if then:
                then()
            return
        self._after_piece = then
        gen, src = self.gen, self.source
        from grimoire.spells.readl.books import BOOK

        def work():
            try:
                return gen, index, src.piece(index)
            except Exception as e:
                return gen, index, e
        BOOK.start(Job(work, self.sig.piece.emit))

    def _piece(self, result):
        gen, index, piece = result
        if gen != self.gen or self.view is None:
            return
        if isinstance(piece, Exception):
            from grimoire.spells.readl.epub import EpubError
            self.stack.setCurrentWidget(self.notice)
            self.notice.show_message(tr("grimoire.spells.readl.reader", "This chapter can't be shown"),
                                     str(piece) if isinstance(piece, EpubError) else "")
            return
        self.chapter = index
        self.view.show_piece(piece)
        self.stack.setCurrentWidget(self.view)

        then, self._after_piece = self._after_piece, None
        if then:
            QTimer.singleShot(0, then)
        if self.find.text().strip() and len(self.source.chapters) == 1:
            self._start_search()
        elif self.find.text().strip():
            n = self.view.mark(self.find.text())
            if self.hit_pos >= 0 and self.hits[self.hit_pos][0] == index and n:
                k = min(n - 1, self.hits[self.hit_pos][1])
                QTimer.singleShot(0, lambda: self.view is not None and self.view.show_hit(k))   # once laid out
        self._book_moved()
        self.view.setFocus()

    def _edge(self, d: int):
        if self.source is None:
            return
        nxt = self.chapter + d
        if 0 <= nxt < len(self.source.chapters):
            y = 1.0 if d < 0 else 0.0
            self.load_chapter(nxt, lambda: self.view.go_fraction(y))

    def _book_moved(self):
        if self.source is None or self.view is None or self.chapter < 0:
            return
        n = len(self.source.chapters)
        pct = round(self._progress() * 100)
        title = self.source.chapters[self.chapter] if self.chapter < n else ""
        if n > 1:
            text = tr("grimoire.spells.readl.reader", "Chapter {n} of {total}").format(n=self.chapter + 1, total=n)
            if title:
                text = f"{i18n.isolate(title)} · {text}"
        else:
            text = ""
        self.where.setText(" · ".join(t for t in (text, f"{pct}%") if t))
        self.page_of.setText(f"{pct}%")
        frac = self.view.fraction()
        self.side.follow(lambda t: t[1] < self.chapter or (t[1] == self.chapter and not t[2]))
        self._mark_state({"chapter": self.chapter, "y": frac})
        self._save_timer.start()

    def _link(self, url: QUrl):
        s = url.toString()
        if s.startswith("readl:") and self.source is not None and hasattr(self.source, "book"):
            member, _, frag = s[len("readl:"):].partition("#")
            idx = self.source.book.chapter_index(member)
            if idx >= 0:
                self.load_chapter(idx, (lambda: self.view.scrollToAnchor(frag)) if frag else
                                  (lambda: self.view.go_fraction(0)))
        elif s.startswith("#") and self.view is not None:
            self.view.scrollToAnchor(s[1:])
        elif url.scheme() in ("http", "https", "mailto"):
            QDesktopServices.openUrl(url)

    # ------------------------------------------------------------ places
    def position(self) -> dict:
        if self.view is None:
            return {}
        if self.kind == "pdf":
            return self.view.position()
        return {"chapter": max(0, self.chapter), "y": self.view.fraction()}

    def _progress(self) -> float:
        if self.view is None:
            return 0.0
        if self.kind == "pdf":
            return self.view.progress()
        w = self.source.weights
        done = sum(w[:self.chapter]) + w[self.chapter] * self.view.fraction() if 0 <= self.chapter < len(w) else 0
        return max(0.0, min(1.0, done))

    def save_place(self):
        if self.view is None or not self.path or (self.kind != "pdf" and self.chapter < 0):
            return
        fields = {"pos": self.position(), "progress": round(self._progress(), 4)}
        if self.kind == "pdf":
            fields["fit"] = self.view.fit
            fields["zoom"] = round(self.view.scale / self._dpi(), 4)
        try:
            self.entry = library.update(self.path, **fields)
        except OSError:
            pass

    def go_pos(self, pos: dict):
        if self.view is None or not isinstance(pos, dict):
            return
        if self.kind == "pdf" and isinstance(pos.get("page"), int):
            page = max(0, min(self.doc.page_count - 1, pos["page"]))
            self.view.go(page, float(pos.get("y", 0)) * self.doc.sizes[page][1])
        elif self.kind != "pdf" and isinstance(pos.get("chapter"), int):
            y = float(pos.get("y", 0))
            self.load_chapter(pos["chapter"], lambda: self.view.go_fraction(y))
        self.view.setFocus()

    def _go_toc(self, target):
        if self.view is None or not target:
            return
        if target[0] == "page":
            _, page, y = target
            self.view.go(page, y)
        else:
            _, ch, frag = target
            if frag.startswith("h:"):
                self.load_chapter(ch, lambda: self.view.go_heading(int(frag[2:])))
            elif frag:
                self.load_chapter(ch, lambda: self.view.scrollToAnchor(frag))
            else:
                self.load_chapter(ch, lambda: self.view.go_fraction(0))
        self.view.setFocus()

    def _moved(self, page: int):
        if self.doc is None:
            return
        n = self.doc.page_count
        label = self.doc.labels[page]
        if not (self.page_box.hasFocus() and self.page_box.isModified()):     # not while you type a page
            self.page_box.setText(label)
        self.page_of.setText(tr("grimoire.spells.readl.reader", "of {total}").format(total=n))
        pct = round(self.view.progress() * 100)
        where = tr("grimoire.spells.readl.reader", "Page {page} of {total}").format(page=page + 1, total=n)
        if label != str(page + 1):
            where = f"{i18n.isolate(label)} · {where}"
        self.where.setText(f"{where} · {pct}%")
        self.side.mark_page(page)
        self.side.follow(lambda t: t[1] <= page)
        self._mark_state(self.view.position())
        self._save_timer.start()

    def _page_entered(self):
        if self.doc is None:
            return
        text = self.page_box.text().strip()
        page = -1
        if text in self.doc.labels:
            page = self.doc.labels.index(text)
        elif text.isdigit():
            page = int(text) - 1
        if 0 <= page < self.doc.page_count:
            self.view.go(page)
            self.view.setFocus()
        else:
            self.page_box.setText(self.doc.labels[self.view.page])

    def focus_page(self):
        if self.kind == "pdf":
            self.page_box.setFocus()
            self.page_box.selectAll()

    # ------------------------------------------------------------ bookmarks
    def _describe(self, pos: dict) -> str:
        if "page" in pos and self.doc is not None and isinstance(pos["page"], int) \
                and 0 <= pos["page"] < self.doc.page_count:
            return tr("grimoire.spells.readl.reader", "Page {page}").format(page=self.doc.labels[pos["page"]])
        if "chapter" in pos and self.source is not None:
            return tr("grimoire.spells.readl.reader", "Chapter {n} · {pct}%").format(
                n=int(pos["chapter"]) + 1, pct=round(float(pos.get("y", 0)) * 100))
        return ""

    def _near(self, a: dict, b: dict) -> bool:
        """The same place, give or take a few lines."""
        if "page" in a:
            return a.get("page") == b.get("page") and abs(float(a.get("y", 0)) - float(b.get("y", 0))) < 0.08
        return a.get("chapter") == b.get("chapter") and abs(float(a.get("y", 0)) - float(b.get("y", 0))) < 0.02

    def _mark_state(self, pos: dict):
        self.mark_btn.setChecked(any(self._near(b["pos"], pos) for b in self.entry.get("bookmarks", [])))

    def toggle_bookmark(self):
        pos = self.position()
        if not pos:
            return
        near = [b for b in self.entry.get("bookmarks", []) if self._near(b["pos"], pos)]
        if near:
            for b in near:
                library.remove_bookmark(self.path, b["pos"])
        else:
            self.add_bookmark()
            return
        self._refresh_marks()

    def add_bookmark(self):
        pos = self.position()
        if not pos:
            return
        if self.kind == "pdf":
            label = self._section(lambda t: t[1] <= pos["page"]) or \
                tr("grimoire.spells.readl.reader", "Page {page}").format(page=self.doc.labels[pos["page"]])
        else:
            label = self.source.chapters[self.chapter] if 0 <= self.chapter < len(self.source.chapters) else ""
            label = label or self._section(lambda t: t[1] <= self.chapter) or \
                tr("grimoire.spells.readl.reader", "Chapter {n}").format(n=self.chapter + 1)
        library.add_bookmark(self.path, pos, label)
        self._refresh_marks()
        if self.side.isHidden():
            self.toggle_side()
        self.side.show_tab("bookmarks")

    def _section(self, before) -> str:
        best = ""
        entries = (self.doc.outline and [(t, ("page", p, y)) for _, t, p, y in self.doc.outline]) \
            if self.kind == "pdf" else [(t, ("chapter", c, f)) for _, t, c, f in self.source.toc]
        for title, target in entries or []:
            if before(target):
                best = title
        return best

    def _remove_mark(self, pos):
        library.remove_bookmark(self.path, pos)
        self._refresh_marks()

    def _rename_mark(self, pos, label):
        library.rename_bookmark(self.path, pos, label)
        self._refresh_marks()

    def _refresh_marks(self):
        self.entry = library.entry(self.path)
        self.side.set_marks(self.entry.get("bookmarks", []), self._describe)
        pos = self.position()
        if pos:
            self._mark_state(pos)

    # ------------------------------------------------------------ view options
    def set_layout(self, layout: str):
        if self.kind != "pdf" or self.view is None:
            return
        self.s["layout"] = layout
        library.save_settings(layout=layout)
        self.view.set_options(layout=layout)
        self._sync_buttons()

    def set_mode(self, mode: str):
        self.s["mode"] = mode
        library.save_settings(mode=mode)
        if self.view is not None:
            if self.kind == "pdf":
                self.view.set_options(mode=mode)
            else:
                self.view.apply(mode=mode)
                if self.find.text().strip():
                    self.view._paint_hits()
        self._sync_buttons()

    def toggle_night(self):
        self.set_mode("day" if self.s["mode"] == "night" else "night")

    def set_fit(self, fit: str, zoom: float | None = None):
        if self.kind == "pdf" and self.view is not None:
            self.view.set_options(fit=fit, zoom=zoom)

    def set_book(self, font=None, measure=None, scale=None):
        changes = {k: v for k, v in (("font", font), ("measure", measure), ("font_scale", scale)) if v}
        self.s.update(changes)
        library.save_settings(**changes)
        if self.view is not None and self.kind != "pdf":
            self.view.apply(font=font, measure=measure, scale=scale)
        self._zoom_menu()

    def zoom(self, d: int):
        if self.view is None:
            return
        if self.kind == "pdf":
            self.view.set_options(fit="custom", zoom=self.view.scale * (1.2 if d > 0 else 1 / 1.2))
        else:
            self.set_book(scale=round(max(0.6, min(2.6, self.s["font_scale"] + 0.1 * d)), 2))

    def zoom_reset(self):
        if self.kind == "pdf":
            self.set_fit("width")
        else:
            self.set_book(scale=1.0)

    def _zoomed(self):
        self._zoom_text()
        self._save_timer.start()

    def toggle_side(self):
        on = self.side.isHidden()
        self.side.setVisible(on)
        self.side_btn.setChecked(on)
        self.s["sidebar"] = on
        library.save_settings(sidebar=on)

    # ------------------------------------------------------------ search
    def focus_find(self):
        if self._full and self.bar.isHidden():
            self.bar.show()
        self.find.setFocus()
        self.find.selectAll()

    def eventFilter(self, obj, e):
        from PySide6.QtCore import QEvent
        if obj is self.find and e.type() == QEvent.Type.KeyPress:
            if e.key() == Qt.Key.Key_Escape:
                if self.find.text():
                    self.find.clear()
                elif self.view is not None:
                    self.view.setFocus()
                return True
            if e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self.next_hit(1 if e.key() == Qt.Key.Key_Down else -1)
                return True
        if self.kind != "pdf" and self.view is not None and obj in (self.view, self.view.viewport()) \
                and e.type() == QEvent.Type.Wheel and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1 if e.angleDelta().y() > 0 else -1)
            return True
        return super().eventFilter(obj, e)

    def _start_search(self):
        needle = self.find.text().strip()
        self.search_id += 1
        sid, gen = self.search_id, self.gen
        self.hits, self.hit_map, self.hit_pos = [], {}, -1
        if self.kind == "pdf" and self.view is not None:
            self.view.set_hits({})
        elif self.view is not None and self.kind:
            self.view.mark("")
        if not needle or self.view is None:
            self.find_status.setText("")
            return
        self.search_done = False
        self.find_status.setText(tr("grimoire.spells.readl.reader", "Searching…"))
        alive = lambda: self.search_id == sid and self.gen == gen      # noqa: E731 (read on the worker)
        emit = self.sig.found.emit
        if self.kind == "pdf":
            doc, start = self.doc, self.view.page
            order = list(range(start, doc.page_count)) + list(range(0, start))

            def work():
                batch = {}
                for n, page in enumerate(order):
                    if not alive():
                        return gen, sid, {}, True
                    hits = doc.find(page, needle)
                    if hits:
                        batch[page] = hits
                    if batch and (len(batch) >= 8 or n % 40 == 39):
                        emit((gen, sid, batch, False))
                        batch = {}
                return gen, sid, batch, True
            POOL.start(Job(work, emit))
        elif self.source is None:
            return
        elif len(self.source.chapters) == 1:            # Markdown and text: the shown document is the whole file
            n = self.view.mark(needle)
            self._found((gen, sid, {0: list(range(n))} if n else {}, True))
        else:
            src, start = self.source, max(0, self.chapter)
            rx = re.compile(r"\s+".join(re.escape(w) for w in needle.split()), re.IGNORECASE)

            def work():
                found = {}
                order = list(range(start, len(src.chapters))) + list(range(0, start))
                for ch in order:
                    if not alive():
                        return gen, sid, {}, True
                    try:
                        text = src.text(ch)
                    except Exception:
                        continue
                    n = sum(1 for _ in rx.finditer(text))
                    if n:
                        found[ch] = list(range(min(n, 5000)))
                return gen, sid, found, True
            from grimoire.spells.readl.books import BOOK
            BOOK.start(Job(work, emit))

    def _found(self, result):
        gen, sid, batch, done = result
        if gen != self.gen or sid != self.search_id:
            return
        cur = self.hits[self.hit_pos] if self.hit_pos >= 0 else None
        self.hit_map.update(batch)
        self.hits = [(where, i) for where in sorted(self.hit_map) for i in range(len(self.hit_map[where]))]
        self.hit_pos = self.hits.index(cur) if cur in self.hits else -1
        self.search_done = done
        if self.kind == "pdf":
            self.view.set_hits(self.hit_map, self.view.current_hit)
        if self.hit_pos < 0 and self.hits:
            here = self.view.page if self.kind == "pdf" else self.chapter
            self.hit_pos = next((i for i, h in enumerate(self.hits) if h[0] >= here), 0)
            self._show_hit()
        elif self.kind != "pdf" and self.chapter in batch:
            self.view.mark(self.find.text())
        self._find_text()

    def _find_text(self):
        if not self.find.text().strip():
            self.find_status.setText("")
        elif not self.hits:
            self.find_status.setText(tr("grimoire.spells.readl.reader", "Searching…") if not self.search_done
                                     else tr("grimoire.spells.readl.reader", "No matches"))
        else:
            text = tr("grimoire.spells.readl.reader", "Match {n} of {total}").format(
                n=self.hit_pos + 1, total=len(self.hits))
            if not self.search_done:
                text += " · " + tr("grimoire.spells.readl.reader", "still searching…")
            self.find_status.setText(text)

    def next_hit(self, d: int):
        if not self.hits:
            if self.find.text().strip() and self.search_done:
                self._start_search()
            return
        self.hit_pos = (self.hit_pos + d) % len(self.hits)
        self._show_hit()
        self._find_text()

    def _show_hit(self):
        where, idx = self.hits[self.hit_pos]
        if self.kind == "pdf":
            self.view.show_hit(where, idx)
        elif where == self.chapter:
            n = self.view.mark(self.find.text())
            self.view.show_hit(min(idx, n - 1))
        else:
            self.load_chapter(where)

    # ------------------------------------------------------------ fullscreen and leaving
    def toggle_fullscreen(self):
        if self._full:
            self._leave_fullscreen()
            return
        parent = self.parentWidget()
        if parent is None or parent.layout() is None:
            return
        lay = parent.layout()
        self._full = (parent, lay.indexOf(self), self.side.isVisible())
        lay.removeWidget(self)
        self.setParent(None)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle(self.title.text())
        self.bar.hide()
        self.side.hide()
        self.foot.hide()
        self.setMouseTracking(True)
        self.showFullScreen()
        if self.view is not None:
            self.view.setFocus()
            self.view.setMouseTracking(True)
            self.view.viewport().installEventFilter(self._bar_peek)

    def _leave_fullscreen(self):
        parent, index, side = self._full
        self._full = None
        self.hide()
        self.setWindowFlag(Qt.WindowType.Window, False)
        self.setParent(parent)
        lay = parent.layout()
        if hasattr(lay, "insertWidget"):
            lay.insertWidget(index, self)
        else:
            lay.addWidget(self)
        self.bar.show()
        self.foot.show()
        self.side.setVisible(side)
        self.show()
        if hasattr(parent, "setCurrentWidget"):
            parent.setCurrentWidget(self)
        if self.view is not None:
            self.view.setFocus()

    @property
    def _bar_peek(self):
        """In fullscreen the toolbar comes back while the pointer is at the top edge."""
        reader = self

        class Peek(QObject):
            def eventFilter(self, obj, e):
                from PySide6.QtCore import QEvent
                if reader._full and e.type() == QEvent.Type.MouseMove:
                    if e.position().y() < 6 and reader.bar.isHidden():
                        reader.bar.show()
                    elif e.position().y() > 80 and not reader.bar.isHidden() and not reader.find.hasFocus():
                        reader._bar_timer.start()
                return False
        if not hasattr(self, "_peek"):
            self._peek = Peek(self)
        return self._peek

    def _hide_bar(self):
        if self._full and not self.find.hasFocus() and not self.bar.underMouse():
            self.bar.hide()

    def escape(self):
        if self._full:
            self._leave_fullscreen()
        elif self.find.text():
            self.find.clear()

    def go_back(self):
        if self._full:
            self._leave_fullscreen()
        self.close_doc()                  # saves the place; the library reopens it where you were
        self.path = ""
        self.back.emit()

    def closeEvent(self, e):
        if self._full:                       # closing the fullscreen window: back into the page
            e.ignore()
            self._leave_fullscreen()
            return
        self.save_place()
        super().closeEvent(e)
