# SPDX-License-Identifier: GPL-3.0-or-later
"""EPUB books, read defensively. No Qt.

An EPUB is a zip of XHTML chapters listed by an OPF file. Nothing is ever extracted to disk: members are looked up by
exact name in the zip's own index, every read is capped (the declared sizes in a zip can lie, so the cap is counted
while inflating), and the archive is refused up front when it is too big, has too many entries or compresses too
well to be honest (zip bombs). XML with entity declarations is refused before parsing (billion laughs); expat never
fetches external entities. Chapters are rebuilt from an allowlist of tags and attributes by sanitize(): no scripts,
styles, forms, frames or event handlers survive, links are rewritten (inside the book, or plain http(s)/mailto), and
images may only come from inside the book. The reader (bookview.py) also refuses every resource it didn't register.
"""
import html
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from grimoire.i18n import tr

MAX_FILE = 1 << 30              # the .epub itself
MAX_ENTRIES = 20000
MAX_TOTAL = 2 << 30             # sum of the declared uncompressed sizes
MAX_MEMBER = 64 << 20           # one chapter or image, counted while inflating
MAX_XML = 8 << 20               # container.xml, the OPF, the NCX
MAX_RATIO = 400                 # uncompressed / compressed for one big member
IMAGE_SIGS = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM")
NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container", "opf": "http://www.idpf.org/2007/opf",
      "dc": "http://purl.org/dc/elements/1.1/", "ncx": "http://www.daisy.org/z3986/2005/ncx/"}


class EpubError(Exception):
    """A book ReadL won't open; the message is for the reader."""


@dataclass
class Chapter:
    href: str                   # the member name inside the zip
    title: str = ""


@dataclass
class Book:
    path: str
    title: str = ""
    author: str = ""
    language: str = ""
    spine: list = field(default_factory=list)     # [Chapter]
    toc: list = field(default_factory=list)       # [(level, title, member, fragment)]
    cover: str = ""                               # member name of the cover image
    zf: zipfile.ZipFile | None = None
    names: set = field(default_factory=set)

    # ------------------------------------------------------------ reading members
    def read(self, name: str, limit: int = MAX_MEMBER) -> bytes:
        """One member's bytes, refusing anything over limit however the zip describes it."""
        if name not in self.names:
            raise EpubError(tr("grimoire.spells.readl.epub", "The book refers to a file it doesn't contain."))
        info = self.zf.getinfo(name)
        if info.file_size > limit or (info.compress_size and info.file_size > (1 << 20)
                                      and info.file_size / info.compress_size > MAX_RATIO):
            raise EpubError(tr("grimoire.spells.readl.epub", "A part of this book is too large to open safely."))
        out = bytearray()
        try:
            with self.zf.open(info) as f:
                while chunk := f.read(1 << 16):
                    out += chunk
                    if len(out) > limit:
                        raise EpubError(tr("grimoire.spells.readl.epub",
                                           "A part of this book is too large to open safely."))
        except (zipfile.BadZipFile, OSError, RuntimeError, EOFError, ValueError) as e:
            if isinstance(e, EpubError):
                raise
            raise EpubError(tr("grimoire.spells.readl.epub", "This book is damaged.")) from e
        return bytes(out)

    def resolve(self, base: str, ref: str) -> tuple[str, str]:
        """(member, fragment) for a relative reference inside the book; member is "" when it points outside it."""
        try:
            parts = urlsplit(ref)
        except ValueError:
            return "", ""
        if parts.scheme or parts.netloc:
            return "", ""
        frag = unquote(parts.fragment)
        if not parts.path:
            return base, frag
        target = unquote(parts.path)
        if target.startswith("/") or "\\" in target or "\0" in target:
            return "", ""
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(base), target))
        if joined.startswith("../") or joined == ".." or joined.startswith("/"):
            return "", ""
        return (joined if joined in self.names else ""), frag

    def close(self):
        if self.zf:
            self.zf.close()
            self.zf = None

    def chapter_index(self, member: str) -> int:
        return next((i for i, c in enumerate(self.spine) if c.href == member), -1)


def _xml(data: bytes) -> ET.Element:
    if len(data) > MAX_XML:
        raise EpubError(tr("grimoire.spells.readl.epub", "This book's index is too large."))
    if re.search(rb"<!ENTITY", data, re.I):
        raise EpubError(tr("grimoire.spells.readl.epub", "This book's index declares entities, which ReadL refuses."))
    try:
        return ET.fromstring(data)
    except ET.ParseError as e:
        raise EpubError(tr("grimoire.spells.readl.epub", "This book's index can't be read.")) from e


def _text(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def open_book(path: str) -> Book:
    """Check the zip and read the OPF: metadata, spine and table of contents. The Book keeps the zip open."""
    import os
    try:
        if os.path.getsize(path) > MAX_FILE:
            raise EpubError(tr("grimoire.spells.readl.epub", "This book is too large."))
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile, ValueError) as e:
        if isinstance(e, EpubError):
            raise
        raise EpubError(tr("grimoire.spells.readl.epub", "This isn't a readable EPUB file.")) from e
    try:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_TOTAL:
            raise EpubError(tr("grimoire.spells.readl.epub", "This book has too much inside it to open safely."))
        book = Book(path=path, zf=zf, names={i.filename for i in infos if not i.is_dir()})
        container = _xml(book.read("META-INF/container.xml", MAX_XML))
        root = container.find(".//c:rootfile", NS)
        opf_name = root.get("full-path", "") if root is not None else ""
        opf_name = posixpath.normpath(opf_name) if opf_name else ""
        if opf_name not in book.names:
            raise EpubError(tr("grimoire.spells.readl.epub", "This book has no table of its contents (OPF)."))
        _read_opf(book, opf_name)
        if not book.spine:
            raise EpubError(tr("grimoire.spells.readl.epub", "This book has no chapters."))
        return book
    except EpubError:
        zf.close()
        raise
    except Exception as e:                  # anything odd in a hostile file is a refusal, never a crash
        zf.close()
        raise EpubError(tr("grimoire.spells.readl.epub", "This book is damaged.")) from e


def _read_opf(book: Book, opf_name: str):
    opf = _xml(book.read(opf_name, MAX_XML))
    meta = opf.find("opf:metadata", NS)
    if meta is not None:
        book.title = _text(meta.find("dc:title", NS))[:300]
        book.author = ", ".join(_text(a) for a in meta.findall("dc:creator", NS))[:200]
        book.language = _text(meta.find("dc:language", NS))[:20]
    manifest = {}
    for item in opf.findall("opf:manifest/opf:item", NS):
        member, _ = book.resolve(opf_name, item.get("href", ""))
        manifest[item.get("id", "")] = (member, item.get("media-type", ""), item.get("properties", ""))
    cover_id = ""
    if meta is not None:
        for m in meta.findall("opf:meta", NS):
            if m.get("name") == "cover":
                cover_id = m.get("content", "")
    for iid, (member, mt, props) in manifest.items():
        if member and ("cover-image" in props.split() or iid == cover_id) and mt.startswith("image/"):
            book.cover = member
    spine = opf.find("opf:spine", NS)
    seen = set()
    if spine is not None:
        for ref in spine.findall("opf:itemref", NS):
            member, mt, _ = manifest.get(ref.get("idref", ""), ("", "", ""))
            if member and member not in seen and ("html" in mt or member.lower().endswith((".xhtml", ".html",
                                                                                            ".htm"))):
                seen.add(member)
                book.spine.append(Chapter(member))
    nav = next((m for m, mt, props in manifest.values() if m and "nav" in props.split()), "")
    if nav:
        book.toc = _nav_toc(book, nav)
    if not book.toc and spine is not None:
        ncx = manifest.get(spine.get("toc", ""), ("",))[0] or next(
            (m for m, mt, _ in manifest.values() if mt == "application/x-dtbncx+xml" and m), "")
        if ncx:
            book.toc = _ncx_toc(book, ncx)
    titles = {}
    for _, title, member, _frag in book.toc:
        titles.setdefault(member, title)
    for ch in book.spine:
        ch.title = titles.get(ch.href, "")


def _ncx_toc(book: Book, member: str) -> list:
    out = []
    try:
        root = _xml(book.read(member, MAX_XML))
    except EpubError:
        return out

    def walk(el, level):
        for p in el.findall("ncx:navPoint", NS):
            label = _text(p.find("ncx:navLabel/ncx:text", NS))
            src = p.find("ncx:content", NS)
            target, frag = book.resolve(member, src.get("src", "")) if src is not None else ("", "")
            if label and target and len(out) < 5000:
                out.append((level, label[:300], target, frag))
            if level < 8:
                walk(p, level + 1)
    nav_map = root.find("ncx:navMap", NS)
    if nav_map is not None:
        walk(nav_map, 0)
    return out


class _NavParser(HTMLParser):
    """The <nav epub:type="toc"> list of an EPUB 3 navigation document: (level, title, href)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_toc = 0
        self.depth = 0
        self.items = []
        self.href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "nav":
            if self.in_toc:
                self.in_toc += 1
            elif "toc" in (a.get("epub:type") or "").split() or a.get("role") == "doc-toc":
                self.in_toc = 1
        elif self.in_toc and tag == "ol":
            self.depth += 1
        elif self.in_toc and tag == "a":
            self.href, self.text = a.get("href") or "", []

    def handle_endtag(self, tag):
        if tag == "nav" and self.in_toc:
            self.in_toc -= 1
        elif self.in_toc and tag == "ol":
            self.depth -= 1
        elif self.in_toc and tag == "a" and self.href is not None:
            title = " ".join("".join(self.text).split())
            if title and len(self.items) < 5000:
                self.items.append((max(0, self.depth - 1), title[:300], self.href))
            self.href = None

    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)


def _nav_toc(book: Book, member: str) -> list:
    try:
        p = _NavParser()
        p.feed(_decode(book.read(member, MAX_XML)))
        p.close()
    except (EpubError, ValueError):
        return []
    out = []
    for level, title, href in p.items:
        target, frag = book.resolve(member, href)
        if target:
            out.append((min(level, 8), title, target, frag))
    return out


def _decode(data: bytes) -> str:
    m = re.search(rb"""encoding=["']([A-Za-z0-9_-]{1,40})["']""", data[:200])
    for enc in ([m.group(1).decode()] if m else []) + ["utf-8"]:
        try:
            return data.decode(enc)
        except (LookupError, UnicodeDecodeError):
            pass
    return data.decode("utf-8", "replace")


# ---------------------------------------------------------------- chapters
KEEP = {"p", "div", "span", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "dl", "dt", "dd",
        "blockquote", "pre", "code", "em", "i", "strong", "b", "u", "s", "strike", "sub", "sup", "small", "big",
        "a", "img", "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "cite", "q", "abbr", "mark",
        "del", "ins", "kbd", "samp", "var", "tt", "center", "font"}
BLOCK_AS_DIV = {"section", "article", "aside", "header", "footer", "figure", "figcaption", "nav", "main", "body",
                "hgroup", "address", "details", "summary", "epub:switch", "epub:default"}
DROP = {"script", "style", "head", "noscript", "iframe", "object", "embed", "video", "audio", "form", "button",
        "select", "textarea", "template", "canvas", "frameset", "frame", "applet", "math", "title", "input",
        "option", "datalist", "dialog", "portal", "epub:case", "rp", "source", "track", "picture", "map"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track",
        "wbr", "image"}
MAX_DEPTH = 40
MAX_CHAPTER = 16 << 20
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


@dataclass
class Page:
    """A sanitized chapter: HTML for QTextDocument, its plain text (search), and the images it shows."""
    html: str
    text: str
    images: dict                    # "readl-img:<n>" -> member name
    anchors: set


class _Sanitizer(HTMLParser):
    def __init__(self, book: Book, base: str, tag: str = ""):
        super().__init__(convert_charrefs=True)
        self.book, self.base, self.tag = book, base, tag
        self.out: list[str] = []
        self.text: list[str] = []
        self.stack: list[str] = []      # open tags we emitted
        self.drop = 0                   # inside a dropped element
        self.images: dict = {}
        self.anchors: set = set()
        self.svg = 0
        self.skipped: dict = {}         # tags left out past MAX_DEPTH, by name, still open

    def _anchor(self, attrs: dict):
        for k in ("id", "name"):
            v = attrs.get(k)
            if v and len(v) < 200 and v not in self.anchors:
                self.anchors.add(v)
                self.out.append(f'<a name="{html.escape(v, True)}"></a>')

    def _img(self, src: str, alt: str, w: str = "", h: str = ""):
        member, _ = self.book.resolve(self.base, src or "")
        if not member:
            if alt:
                self.out.append(html.escape(f"[{alt}]"))
            return
        ref = f"readl-img:{self.tag}{len(self.images)}"     # unique per chapter: documents cache images by name
        self.images[ref] = member
        bits = [f'src="{ref}"']
        if alt:
            bits.append(f'alt="{html.escape(alt[:300], True)}"')
        for name, v in (("width", w), ("height", h)):
            if v and re.fullmatch(r"\d{1,4}", v.strip()):
                bits.append(f'{name}="{min(int(v), 4000)}"')
        self.out.append(f"<img {' '.join(bits)} />")

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = {k.lower(): (v or "") for k, v in attrs}
        if self.drop:
            if tag not in VOID:
                self.drop += 1
            return
        if tag == "svg":                # covers: <svg><image xlink:href="cover.jpg"/></svg>
            self.svg += 1
            return
        if self.svg:
            if tag == "image":
                self._img(a.get("xlink:href") or a.get("href", ""), a.get("alt", ""))
            return
        if tag in DROP:
            self.drop = 0 if tag in VOID else 1
            return
        if tag not in KEEP and tag not in BLOCK_AS_DIV:
            self._anchor(a)
            return                      # unknown inline wrapper: keep its text, drop the tag
        self._anchor(a)
        if tag == "img":
            self._img(a.get("src", ""), a.get("alt", ""), a.get("width", ""), a.get("height", ""))
            return
        if tag in ("br", "hr"):
            self.out.append(f"<{tag} />")
            if tag == "br":
                self.text.append("\n")
            return
        name = "div" if tag in BLOCK_AS_DIV else "span" if tag == "font" else tag
        if len(self.stack) >= MAX_DEPTH and tag != "a":
            self.skipped[name] = self.skipped.get(name, 0) + 1
            return                      # deeper nesting only slows the layout down: keep the text, drop the tag
        bits = []
        if tag == "a":
            href = a.get("href", "").strip()
            link = self._link(href) if href else ""
            if link:
                bits.append(f'href="{html.escape(link, True)}"')
        elif tag in ("td", "th"):
            for k in ("colspan", "rowspan"):
                if re.fullmatch(r"\d{1,3}", a.get(k, "")):
                    bits.append(f'{k}="{a[k]}"')
        elif tag == "ol" and re.fullmatch(r"-?\d{1,6}", a.get("start", "")):
            bits.append(f'start="{a["start"]}"')
        elif tag == "table":
            bits.append('cellpadding="4"')
        self.out.append(f"<{name}{' ' if bits else ''}{' '.join(bits)}>")
        self.stack.append(name)
        if tag in HEADINGS or tag in ("p", "div", "li", "tr", "blockquote", "pre") or tag in BLOCK_AS_DIV:
            self.text.append("\n")

    def _link(self, href: str) -> str:
        low = href.lower()
        if low.startswith(("http://", "https://", "mailto:")):
            return href if len(href) < 2000 and not re.search(r"[\s<>\"]", href) else ""
        member, frag = self.book.resolve(self.base, href)
        if not member:
            return ""
        return "readl:" + member + ("#" + frag if frag else "")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.drop:
            if tag not in VOID:
                self.drop -= 1
            return
        if tag == "svg" and self.svg:
            self.svg -= 1
            return
        if self.svg or tag in VOID:
            return
        name = "div" if tag in BLOCK_AS_DIV else "span" if tag == "font" else tag
        if self.skipped.get(name):
            self.skipped[name] -= 1
            return
        if name in self.stack:          # close whatever was left open inside it (tag soup)
            while self.stack:
                top = self.stack.pop()
                self.out.append(f"</{top}>")
                if top == name:
                    break

    def handle_data(self, data):
        if self.drop or self.svg:
            return
        self.out.append(html.escape(data, False))
        self.text.append(data)


def chapter(book: Book, index: int) -> Page:
    """Chapter index of the spine, sanitized."""
    member = book.spine[index].href
    p = _Sanitizer(book, member, f"{index}-")
    try:
        p.feed(_decode(book.read(member, MAX_CHAPTER)))
        p.close()
    except (ValueError, AssertionError) as e:
        raise EpubError(tr("grimoire.spells.readl.epub", "This chapter can't be read.")) from e
    body = "".join(p.out) + "".join(f"</{t}>" for t in reversed(p.stack))
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.text))
    return Page(f"<html><body>{body}</body></html>", text, p.images, p.anchors)


def image_bytes(book: Book, member: str, limit: int = 32 << 20) -> bytes:
    """An image's bytes when they look like a raster image (PNG, JPEG, GIF, BMP, WebP), else b"". SVG is left out:
    it can pull in other files."""
    try:
        data = book.read(member, limit)
    except EpubError:
        return b""
    if data.startswith(IMAGE_SIGS) or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        return data
    return b""
