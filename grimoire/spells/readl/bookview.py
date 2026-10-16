# SPDX-License-Identifier: GPL-3.0-or-later
"""The reflowing view for EPUB, Markdown and text: one chapter at a time in a centered column, day/night/paper
colors, a serif or sans font at any size, search highlights, and chapter turns at either end.

loadResource() serves only the images books.py decoded for this chapter: remote URLs, file paths and anything else
an HTML document might ask for get nothing. Links never open by themselves (setOpenLinks(False)); the reader decides.
"""
from PySide6.QtCore import QPoint, QRegularExpression, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QColor, QFont, QImage, QPalette, QTextBlockFormat, QTextCharFormat, QTextCursor,
                           QTextDocument)
from PySide6.QtWidgets import QTextBrowser, QTextEdit

COLORS = {"day": ("#ffffff", "#141414", "#555555"), "night": ("#0b0b0b", "#cfcfcf", "#8c8c8c"),
          "paper": ("#e2e2e2", "#1a1a1a", "#5a5a5a")}          # page, text, quieter text
SERIF = ["Noto Serif", "DejaVu Serif", "Liberation Serif", "serif"]
BASE_PX = 17
BLANK = QImage(1, 1, QImage.Format.Format_ARGB32)
BLANK.fill(0)


def pattern(needle: str) -> str:
    """Case-insensitive, spaces match any run of white space (also across line breaks)."""
    return r"\s+".join(QRegularExpression.escape(w) for w in needle.split())


class BookView(QTextBrowser):
    edge = Signal(int)                # +1: scrolled past the end, -1: past the start
    moved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.images: dict[str, QImage] = {}
        self.mode = "day"
        self.font_kind = "serif"
        self.scale = 1.0
        self.measure = 720
        self.kind = "html"
        self._hits: list[QTextCursor] = []
        self._current = -1
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUndoRedoEnabled(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.verticalScrollBar().valueChanged.connect(lambda _: self.moved.emit())
        self._fit_timer = QTimer(self, singleShot=True, interval=60, timeout=self._fit_images)

    # ------------------------------------------------------------ resources
    def loadResource(self, kind, url: QUrl):
        """Only this chapter's own decoded images; nothing else, ever."""
        if kind == QTextDocument.ResourceType.ImageResource:
            img = self.images.get(url.toString())
            if img is not None:
                return img
            return BLANK                            # blocked: an empty pixel, not a "broken image" icon
        return None

    # ------------------------------------------------------------ content
    def show_piece(self, piece):
        self.images = piece.images
        self.kind = piece.kind
        self._hits, self._current = [], -1
        doc = self.document()           # one document, reused: it keeps the view's width and asks it for images
        doc.clear()
        doc.setUndoRedoEnabled(False)
        self._style(doc)
        if piece.kind == "html":
            doc.setHtml(piece.content)
        elif piece.kind == "markdown":
            # raw HTML stays text: Qt's Markdown importer can swallow everything after an HTML block
            F = QTextDocument.MarkdownFeature
            doc.setMarkdown(piece.content, F.MarkdownDialectGitHub | F.MarkdownNoHTML)
        else:
            doc.setPlainText(piece.content)
        self._spacing(doc)
        self._margins()
        self._fit_images()
        self.setExtraSelections([])

    def _style(self, doc: QTextDocument):
        page, text, quiet = COLORS[self.mode]
        doc.setDefaultStyleSheet(
            f"a {{ color: {text}; text-decoration: underline; }} "
            f"h1, h2, h3, h4, h5, h6 {{ color: {text}; font-weight: 600; }} "
            f"blockquote {{ color: {quiet}; }} pre, code {{ font-family: 'IBM Plex Mono'; }}")
        f = QFont()
        if self.font_kind == "serif":
            f.setFamilies(SERIF)
        else:
            f.setFamilies(["IBM Plex Sans"])
        f.setPixelSize(max(9, round(BASE_PX * self.scale)))
        if self.kind == "plain":
            f.setFamilies(["IBM Plex Mono"])
            f.setPixelSize(max(9, round((BASE_PX - 3) * self.scale)))
        doc.setDefaultFont(f)
        self._px = f.pixelSize()
        doc.setDocumentMargin(0)
        pal = self.palette()
        for role, color in ((QPalette.ColorRole.Base, page), (QPalette.ColorRole.Window, page),
                            (QPalette.ColorRole.Text, text), (QPalette.ColorRole.Link, text),
                            (QPalette.ColorRole.LinkVisited, text),
                            (QPalette.ColorRole.Highlight, text), (QPalette.ColorRole.HighlightedText, page)):
            pal.setColor(role, QColor(color))
        self.setPalette(pal)
        self.viewport().setPalette(pal)
        self.viewport().setAutoFillBackground(True)
        # the widget's font is what QTextEdit hands its document (the app stylesheet would win over setFont)
        family = ", ".join(f'"{x}"' for x in f.families())
        self.setStyleSheet(f"QTextBrowser {{ background: {page}; color: {text}; border: none; "
                           f"font-family: {family}; font-size: {f.pixelSize()}px; }}")

    def _spacing(self, doc: QTextDocument):
        """Book line spacing on every paragraph; plain text a little tighter."""
        c = QTextCursor(doc)
        c.select(QTextCursor.SelectionType.Document)
        fmt = QTextBlockFormat()
        px = self._px                               # extra space between lines, not a factor: images keep their height
        fmt.setLineHeight(round(px * (0.3 if self.kind == "plain" else 0.45)),
                          QTextBlockFormat.LineHeightTypes.LineDistanceHeight.value)
        c.mergeBlockFormat(fmt)

    def _fit_images(self):
        """Images wider than the column are shown at the column's width."""
        if not self.images:
            return
        doc = self.document()
        width = max(100, self.viewport().width() - 2 * doc.rootFrame().frameFormat().leftMargin() - 4)
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                fmt = frag.charFormat()
                if frag.isValid() and fmt.isImageFormat():
                    img_fmt = fmt.toImageFormat()
                    img = self.images.get(img_fmt.name())
                    if img is not None:
                        w = min(float(img.width()), width)
                        if abs(img_fmt.width() - w) > 0.5:
                            img_fmt.setWidth(w)
                            img_fmt.setHeight(img.height() * w / max(1, img.width()))
                            c = QTextCursor(doc)
                            c.setPosition(frag.position())
                            c.setPosition(frag.position() + frag.length(), QTextCursor.MoveMode.KeepAnchor)
                            c.setCharFormat(img_fmt)
                it += 1
            block = block.next()

    def apply(self, mode=None, font=None, scale=None, measure=None):
        """New look for the current chapter, keeping the place."""
        if mode:
            self.mode = mode
        if font:
            self.font_kind = font
        if scale:
            self.scale = scale
        if measure:
            self.measure = measure
        y = self.fraction()
        self._style(self.document())
        self._margins()
        self.document().adjustSize()
        self.go_fraction(y)

    def resizeEvent(self, e):
        y = self.fraction() if self.document().characterCount() > 1 else 0.0
        super().resizeEvent(e)
        self._margins()
        self._fit_timer.start()
        QTimer.singleShot(0, lambda: self.go_fraction(y))

    def _margins(self):
        """Center a column of the chosen measure with the root frame's side margins (the viewport stays full
        width, so the scroll bar keeps to the window's edge and the whole width scrolls)."""
        side = max(24, (self.viewport().width() - self.measure * max(1.0, self.scale ** 0.5)) / 2)
        root = self.document().rootFrame()
        fmt = root.frameFormat()
        if abs(fmt.leftMargin() - side) > 0.5 or fmt.topMargin() != 28:
            fmt.setLeftMargin(side)
            fmt.setRightMargin(side)
            fmt.setTopMargin(28)
            fmt.setBottomMargin(64)
            root.setFrameFormat(fmt)
            doc = self.document()
            doc.markContentsDirty(0, doc.characterCount())     # lay every block out again, not just the lines
        self._fit_timer.start()

    # ------------------------------------------------------------ position
    def fraction(self) -> float:
        """Where the top of the view is, as a fraction of the chapter's characters (survives resizing)."""
        n = self.document().characterCount()
        if n <= 1:
            return 0.0
        c = self.cursorForPosition(QPoint(4, 4))
        vb = self.verticalScrollBar()
        if vb.value() >= vb.maximum() > 0:
            return 1.0
        return round(c.position() / n, 5)

    def go_fraction(self, y: float):
        vb = self.verticalScrollBar()
        if y >= 1.0:
            vb.setValue(vb.maximum())
            return
        if y <= 0:
            vb.setValue(0)
            return
        c = QTextCursor(self.document())
        c.setPosition(min(self.document().characterCount() - 1, int(y * self.document().characterCount())))
        r = self.cursorRect(c)
        vb.setValue(vb.value() + r.top() - 4)

    def go_heading(self, n: int):
        """The nth heading (Markdown's table of contents)."""
        block = self.document().begin()
        i = 0
        while block.isValid():
            if block.blockFormat().headingLevel() > 0:
                if i == n:
                    c = QTextCursor(block)
                    self.verticalScrollBar().setValue(self.verticalScrollBar().value() + self.cursorRect(c).top() - 8)
                    return
                i += 1
            block = block.next()

    # ------------------------------------------------------------ search
    def mark(self, needle: str) -> int:
        """Highlight every match in this chapter; returns how many."""
        self._hits = []
        if needle.strip():
            rx = QRegularExpression(pattern(needle), QRegularExpression.PatternOption.CaseInsensitiveOption)
            c = self.document().find(rx, 0)
            while not c.isNull() and len(self._hits) < 5000:
                if c.selectionEnd() == c.selectionStart():
                    break
                self._hits.append(c)
                c = self.document().find(rx, c.selectionEnd())
        self._current = -1
        self._paint_hits()
        return len(self._hits)

    def show_hit(self, idx: int):
        if not 0 <= idx < len(self._hits):
            return
        self._current = idx
        self._paint_hits()
        c = self._hits[idx]
        r = self.cursorRect(c)
        vb = self.verticalScrollBar()
        if not (40 <= r.top() <= self.viewport().height() - 60):
            vb.setValue(vb.value() + r.top() - self.viewport().height() // 3)

    def _paint_hits(self):
        page, text, _ = COLORS[self.mode]
        sels = []
        for i, c in enumerate(self._hits):
            s = QTextEdit.ExtraSelection()
            s.cursor = c
            f = QTextCharFormat()
            if i == self._current:
                f.setBackground(QColor(text))
                f.setForeground(QColor(page))
            else:
                f.setBackground(QColor("#7a7a7a" if self.mode == "night" else "#bdbdbd"))
                f.setForeground(QColor(page if self.mode == "night" else text))
            s.format = f
            sels.append(s)
        self.setExtraSelections(sels)

    # ------------------------------------------------------------ keys
    def keyPressEvent(self, e):
        k = e.key()
        K = Qt.Key
        vb = self.verticalScrollBar()
        step = max(40, self.viewport().height() - 56)
        shift = e.modifiers() & Qt.KeyboardModifier.ShiftModifier
        forward = k in (K.Key_PageDown, K.Key_Right) or (k == K.Key_Space and not shift)
        back = k in (K.Key_PageUp, K.Key_Left) or (k == K.Key_Space and shift)
        if forward:
            if vb.value() >= vb.maximum():
                self.edge.emit(1)
            else:
                vb.setValue(vb.value() + step)
        elif back:
            if vb.value() <= vb.minimum():
                self.edge.emit(-1)
            else:
                vb.setValue(vb.value() - step)
        elif k == K.Key_Home and not e.modifiers():
            vb.setValue(0)
        elif k == K.Key_End and not e.modifiers():
            vb.setValue(vb.maximum())
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return                                # the reader zooms (Ctrl+wheel goes to it through the event filter)
        vb = self.verticalScrollBar()
        d = e.angleDelta().y()
        if d < 0 and vb.value() >= vb.maximum():
            self._edge_wheel += 1
        elif d > 0 and vb.value() <= vb.minimum():
            self._edge_wheel -= 1
        else:
            self._edge_wheel = 0
        if abs(self._edge_wheel) >= 3:             # a deliberate push past the end turns the chapter
            self.edge.emit(1 if self._edge_wheel > 0 else -1)
            self._edge_wheel = 0
            return
        super().wheelEvent(e)

    _edge_wheel = 0

