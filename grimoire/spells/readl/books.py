# SPDX-License-Identifier: GPL-3.0-or-later
"""Reflowing documents (EPUB, Markdown, plain text) as a list of chapters the book view shows one at a time.

Everything here runs on BOOK, a worker pool of one (a zip file isn't safe to read from two threads), and hands the
view finished pieces: sanitized HTML, its plain text for search, and images already decoded. The view's document
refuses every resource that isn't one of those images, so nothing is ever fetched from the network or the disk.
"""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QThreadPool
from PySide6.QtGui import QImage, QImageReader

from grimoire.i18n import tr
from grimoire.spells.readl import epub

BOOK = QThreadPool()
BOOK.setMaxThreadCount(1)
MAX_TEXT = 32 << 20             # a Markdown or text file
MAX_PIXELS = 40_000_000
MAX_SIDE = 2000                 # images are shown at most this big


@dataclass
class Piece:
    """One chapter, ready to show."""
    kind: str                   # "html", "markdown" or "plain"
    content: str
    text: str                   # plain text, for search
    images: dict = field(default_factory=dict)      # url -> QImage


def decode_image(data: bytes, max_side: int = MAX_SIDE) -> QImage:
    """Raster image bytes → a QImage no bigger than max_side, refusing decompression bombs (header checked first)."""
    if not data:
        return QImage()
    buf = QBuffer()
    buf.setData(QByteArray(data))
    buf.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buf)
    reader.setDecideFormatFromContent(True)
    if bytes(reader.format()).lower() not in (b"png", b"jpeg", b"jpg", b"gif", b"bmp", b"webp"):
        return QImage()
    size = reader.size()
    if not size.isValid() or size.width() * size.height() > MAX_PIXELS:
        return QImage()
    if max(size.width(), size.height()) > max_side:
        size.scale(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio)
        reader.setScaledSize(size)
    img = reader.read()
    return img if not img.isNull() else QImage()


class Source:
    """What the book view reads from: chapters, a table of contents, metadata."""
    kind = ""
    title = ""
    author = ""
    chapters: list = []                  # titles (may be "")
    toc: list = []                       # [(level, title, chapter, fragment)]
    weights: list = []                   # each chapter's share of the whole, for progress

    def piece(self, index: int) -> Piece:
        raise NotImplementedError

    def text(self, index: int) -> str:
        """A chapter's plain text, for search (worker thread)."""
        raise NotImplementedError

    def cover(self) -> QImage:
        return QImage()

    def close(self):
        pass


class EpubSource(Source):
    kind = "epub"

    def __init__(self, path: str):
        self.book = epub.open_book(path)
        b = self.book
        self.title, self.author = b.title or Path(path).stem, b.author
        self.chapters = [c.title for c in b.spine]
        self.toc = [(lvl, title, b.chapter_index(member), frag) for lvl, title, member, frag in b.toc
                    if b.chapter_index(member) >= 0]
        if not self.toc:
            self.toc = [(0, t or tr("grimoire.spells.readl.books", "Part {n}").format(n=i + 1), i, "")
                        for i, t in enumerate(self.chapters)]
        sizes = [max(1, b.zf.getinfo(c.href).file_size) for c in b.spine]
        total = sum(sizes)
        self.weights = [s / total for s in sizes]
        self._texts = {}

    def piece(self, index: int) -> Piece:
        page = epub.chapter(self.book, index)
        images = {}
        for ref, member in list(page.images.items())[:400]:
            img = decode_image(epub.image_bytes(self.book, member))
            if not img.isNull():
                images[ref] = img
        return Piece("html", page.html, page.text, images)

    def text(self, index: int) -> str:
        if index not in self._texts:
            self._texts[index] = epub.chapter(self.book, index).text
        return self._texts[index]

    def cover(self) -> QImage:
        if self.book.cover:
            return decode_image(epub.image_bytes(self.book, self.book.cover), 800)
        return QImage()

    def close(self):
        self.book.close()


def read_text(path: str) -> str:
    if os.path.getsize(path) > MAX_TEXT:
        raise epub.EpubError(tr("grimoire.spells.readl.books", "This file is too large to show (over 32 MB)."))
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-16") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig",):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1")


IMG_REFS = re.compile(r"""!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+["'][^)]*["'])?\s*\)"""
                      r"""|<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']""", re.I)


class TextSource(Source):
    """A Markdown or plain text file: one chapter; Markdown headings make the table of contents."""

    def __init__(self, path: str, kind: str):
        self.path, self.kind = path, kind
        self.body = read_text(path)
        self.title = Path(path).stem
        self.chapters = [""]
        self.weights = [1.0]
        self.toc = []
        if kind == "markdown":
            fence = False
            n = 0
            for line in self.body.splitlines():
                if line.lstrip().startswith(("```", "~~~")):
                    fence = not fence
                    continue
                m = None if fence else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
                if m:
                    self.toc.append((len(m.group(1)) - 1, m.group(2)[:300], 0, f"h:{n}"))
                    n += 1
            if self.toc and self.toc[0][0] == 0:
                self.title = self.toc[0][1]

    def text(self, index: int) -> str:
        return self.body

    def piece(self, index: int) -> Piece:
        if self.kind != "markdown":
            return Piece("plain", self.body, self.body)
        return Piece("markdown", self.body, self.body, self._images())

    def _images(self) -> dict:
        """Images next to the Markdown file (in its folder or below), never from elsewhere or the network."""
        folder = os.path.realpath(os.path.dirname(self.path))
        out = {}
        for m in IMG_REFS.finditer(self.body):
            ref = m.group(1) or m.group(2)
            if not ref or ref in out or re.match(r"^[a-z][a-z0-9+.-]*:", ref, re.I) or ref.startswith("/"):
                continue
            from urllib.parse import unquote
            target = os.path.realpath(os.path.join(folder, unquote(ref.split("#")[0].split("?")[0])))
            if not target.startswith(folder + os.sep) or not os.path.isfile(target):
                continue
            try:
                if os.path.getsize(target) > 32 << 20:
                    continue
                img = decode_image(Path(target).read_bytes())
            except OSError:
                continue
            if not img.isNull():
                out[ref] = img
            if len(out) >= 200:
                break
        return out


def open_source(path: str, kind: str) -> Source:
    if kind == "epub":
        return EpubSource(path)
    return TextSource(path, kind)
