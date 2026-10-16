# SPDX-License-Identifier: GPL-3.0-or-later
"""PDFs through QtPdf (pdfium): loading, page sizes, the outline, links, rendering, text and search.

QtPdf comes from Ubuntu's python3-pyside6.qtpdf package; without it ReadL still reads EPUB, Markdown and text and
shows the apt command for PDFs. pdfium is guarded by one global lock inside QtPdf, so rendering runs on one worker
thread of its own (RENDER, a pool of one): pages come back in the order they were asked for and the UI thread only
waits on the lock for the short text calls (selection, a search hit's boxes). Every coordinate here is in PDF
points from the page's top-left corner.
"""
import re

from PySide6.QtCore import QModelIndex, QPointF, QRectF, QSize, QThreadPool
from PySide6.QtGui import QImage, QPainter

from grimoire.i18n import tr

APT = "sudo apt install python3-pyside6.qtpdf"
RENDER = QThreadPool()
RENDER.setMaxThreadCount(1)
MAX_SIDE = 12000                 # never render a page bigger than this many pixels on a side


def available() -> bool:
    try:
        import PySide6.QtPdf  # noqa: F401
        return True
    except ImportError:
        return False


class PdfError(Exception):
    pass


class NeedsPassword(PdfError):
    pass


class Doc:
    """An open PDF. load() runs on a worker; after it, page_count/sizes/outline/title are plain Python."""

    def __init__(self, path: str):
        self.path = path
        self.doc = None
        self.page_count = 0
        self.sizes: list[tuple[float, float]] = []
        self.labels: list[str] = []
        self.outline: list[tuple[int, str, int, float]] = []    # (level, title, page, y in points)
        self.title = ""
        self.author = ""
        self._links: dict[int, list] = {}
        self._text: dict[int, str] = {}
        self._lines: dict[int, list] = {}

    def load(self, password: str = ""):
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtPdf import QPdfDocument
        doc = QPdfDocument()
        if password:
            doc.setPassword(password)
        err = doc.load(self.path)
        E = QPdfDocument.Error
        if err == E.IncorrectPassword:
            raise NeedsPassword(tr("grimoire.spells.readl.pdfdoc", "This PDF is locked with a password."))
        if err != E.None_:
            msg = {E.FileNotFound: tr("grimoire.spells.readl.pdfdoc", "The file isn't there any more."),
                   E.InvalidFileFormat: tr("grimoire.spells.readl.pdfdoc", "This isn't a readable PDF file."),
                   E.UnsupportedSecurityScheme: tr("grimoire.spells.readl.pdfdoc",
                                                   "This PDF uses a kind of protection ReadL can't open.")}
            raise PdfError(msg.get(err, tr("grimoire.spells.readl.pdfdoc", "This PDF can't be opened.")))
        self.doc = doc
        self.page_count = doc.pageCount()
        if self.page_count <= 0:
            raise PdfError(tr("grimoire.spells.readl.pdfdoc", "This PDF has no pages."))
        for i in range(self.page_count):
            s = doc.pagePointSize(i)
            w, h = s.width(), s.height()
            self.sizes.append((w, h) if w > 1 and h > 1 else (612.0, 792.0))
            self.labels.append(doc.pageLabel(i) or str(i + 1))
        F = QPdfDocument.MetaDataField
        self.title = " ".join(str(doc.metaData(F.Title) or "").split())[:300]
        self.author = " ".join(str(doc.metaData(F.Author) or "").split())[:200]
        self.outline = self._read_outline()
        app = QCoreApplication.instance()
        if app is not None:
            doc.moveToThread(app.thread())      # made on a worker: hand it to the UI thread, which deletes it

    def _read_outline(self):
        from PySide6.QtPdf import QPdfBookmarkModel
        model = QPdfBookmarkModel()
        model.setDocument(self.doc)
        R = QPdfBookmarkModel.Role
        out = []

        def walk(parent, level):
            for row in range(model.rowCount(parent)):
                if len(out) >= 10000:
                    return
                ix = model.index(row, 0, parent)
                title = " ".join(str(model.data(ix, R.Title.value) or "").split())[:300]
                page = model.data(ix, R.Page.value)
                loc = model.data(ix, R.Location.value)
                y = float(loc.y()) if isinstance(loc, QPointF) else 0.0
                if title and isinstance(page, int) and 0 <= page < self.page_count:
                    out.append((level, title, page, max(0.0, y)))
                if level < 10:
                    walk(ix, level + 1)
        walk(QModelIndex(), 0)
        return out

    def close(self):
        if self.doc is not None:
            self.doc.close()
            self.doc.deleteLater()
            self.doc = None

    # ------------------------------------------------------------ pictures
    def render(self, page: int, scale: float) -> QImage:
        """The page at scale pixels per point (worker thread)."""
        w, h = self.sizes[page]
        f = min(scale, MAX_SIDE / max(w, h))
        size = QSize(max(1, round(w * f)), max(1, round(h * f)))
        doc = self.doc
        if doc is None:
            return QImage()
        img = doc.render(page, size)
        out = QImage(size, QImage.Format.Format_RGB32)      # pdfium leaves the paper transparent: make it white
        out.fill(0xFFFFFFFF)
        if not img.isNull():
            p = QPainter(out)
            p.drawImage(0, 0, img)
            p.end()
        return out

    # ------------------------------------------------------------ text
    def text(self, page: int) -> str:
        if page not in self._text:
            sel = self.doc.getAllText(page) if self.doc is not None else None
            self._text[page] = sel.text() if sel is not None else ""
        return self._text[page]

    def lines(self, page: int) -> list[tuple[int, int, QRectF]]:
        """(start, length, box) of each text line on the page (UI thread, cached: ~40 small calls a page)."""
        if page not in self._lines:
            text = self.text(page)
            out = []
            for m in re.finditer(r"[^\r\n]+", text):
                if len(out) >= 3000:
                    break
                box = self.doc.getSelectionAtIndex(page, m.start(), m.end() - m.start()).boundingRectangle()
                if box.width() > 0 and box.height() > 0:
                    out.append((m.start(), m.end() - m.start(), box))
            self._lines[page] = out
        return self._lines[page]

    def index_at(self, page: int, p: QPointF) -> int:
        """The character index nearest to p, in reading order: a point in a margin or between lines snaps to the
        nearest line's start or end, like selecting in a text editor."""
        lines = self.lines(page) if self.doc is not None else []
        if not lines:
            return 0
        line = None
        for ln in lines:
            if ln[2].top() - 2 <= p.y() <= ln[2].bottom() + 2:
                if line is None or abs(ln[2].center().y() - p.y()) < abs(line[2].center().y() - p.y()):
                    line = ln
        if line is None:
            after = [ln for ln in lines if ln[2].top() > p.y()]
            if not after:
                return lines[-1][0] + lines[-1][1]
            return min(after, key=lambda ln: (ln[2].top(), ln[0]))[0]
        start, length, box = line
        if p.x() <= box.left():
            return start
        if p.x() >= box.right():
            return start + length
        cy = box.center().y()
        sel = self.doc.getSelection(page, QPointF(box.left() + 0.5, cy), QPointF(p.x(), cy))
        end = sel.endIndex() if sel.isValid() else start
        return max(start, min(start + length, end))

    def select(self, page: int, a: QPointF, b: QPointF) -> tuple[str, list[QRectF]]:
        if self.doc is None:
            return "", []
        i, j = sorted((self.index_at(page, a), self.index_at(page, b)))
        if j <= i:
            return "", []
        sel = self.doc.getSelectionAtIndex(page, i, j - i)
        return _clean(sel.text()), [p.boundingRect() for p in sel.bounds()]

    def span_rects(self, page: int, start: int, length: int) -> list[QRectF]:
        if self.doc is None or length <= 0:
            return []
        sel = self.doc.getSelectionAtIndex(page, start, length)
        return [p.boundingRect() for p in sel.bounds()]

    def word_at(self, page: int, p: QPointF) -> tuple[str, list[QRectF]]:
        """The word under p (double click)."""
        if self.doc is None:
            return "", []
        text = self.text(page)
        i = self.index_at(page, p)
        if not (0 <= i < len(text)) or text[i].isspace():
            return "", []
        a = i
        while a > 0 and not text[a - 1].isspace():
            a -= 1
        b = i
        while b < len(text) and not text[b].isspace():
            b += 1
        word = text[a:b].strip("\"'“”‘’()[]{}<>,.;:!?")
        lead = text[a:b].find(word) if word else 0
        return word, self.span_rects(page, a + lead, len(word))

    def find(self, page: int, needle: str) -> list[tuple[int, int]]:
        """(start, length) of each case-insensitive match on the page; line breaks match spaces."""
        text = self.text(page)
        if not needle.strip() or not text:
            return []
        pattern = r"\s+".join(re.escape(w) for w in needle.split())
        return [(m.start(), m.end() - m.start()) for m in re.finditer(pattern, text, re.IGNORECASE)][:2000]

    # ------------------------------------------------------------ links
    def links(self, page: int) -> list[tuple[QRectF, int, float, str]]:
        """[(rect, target page or -1, target y, url)] on a page (UI thread, cached)."""
        if page in self._links or self.doc is None:
            return self._links.get(page, [])
        from PySide6.QtPdf import QPdfLinkModel
        model = QPdfLinkModel()
        model.setDocument(self.doc)
        model.setPage(page)
        R = QPdfLinkModel.Role
        out = []
        for row in range(min(model.rowCount(QModelIndex()), 2000)):
            ix = model.index(row, 0, QModelIndex())
            rect = model.data(ix, R.Rectangle.value)
            target = model.data(ix, R.Page.value)
            loc = model.data(ix, R.Location.value)
            url = model.data(ix, R.Url.value)
            url = url.toString() if hasattr(url, "toString") else str(url or "")
            if isinstance(rect, QRectF):
                out.append((rect, target if isinstance(target, int) else -1,
                            float(loc.y()) if isinstance(loc, QPointF) else 0.0, url))
        self._links[page] = out
        return out


def _clean(text: str) -> str:
    """pdfium separates words with tabs and lines with CRLF."""
    return text.replace("\r\n", "\n").replace("\t", " ")
