# SPDX-License-Identifier: GPL-3.0-or-later
"""Markdown preview and export, on Qt's own Markdown reader (QTextDocument.setMarkdown).

prepare() (no Qt, runs on a worker) turns Obsidian syntax into plain Markdown: [[links]] become note: links, #tags
become tag: links, and local images (![[pic.png]], ![](pic.png)) get notel-img: names whose pixels load_images()
reads on the worker too. The preview only ever shows those: remote images are never fetched (a placeholder says so),
and links open only when clicked: notes in NoteL, web links in the browser.
"""
import base64
import os
import re
from pathlib import Path
from urllib.parse import quote, unquote

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QRectF, QSize, Qt, QUrl, Signal
from PySide6.QtGui import (QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextBlockFormat,
                           QTextCharFormat, QTextCursor, QTextDocument, QTextFormat, QTextFrameFormat,
                           QTextImageFormat, QTextLength, QTextTable)
from PySide6.QtWidgets import QTextBrowser

from grimoire.i18n import MONO, SANS, tr
from grimoire.spells.notel import store

IMG = "notel-img"
MAX_IMAGE = 40 << 20              # bytes on disk
MAX_WIDTH = 1600                  # pixels kept in memory per image
MAX_PREVIEW = 4 << 20             # characters rendered; longer notes show their start
SEGMENT = re.compile(r"(`+)(?:(?!\1).)+?\1|!?\[\[[^\[\]\n]+\]\]|!?\[[^\]\n]*\]\([^)\n]*\)|<[a-z]+://[^>\s]+>"
                     r"|\b[a-z][a-z0-9+.-]*://[^\s<>()]+")


def _link_text(t: str) -> str:
    return re.sub(r"([\[\]\\*_`])", r"\\\1", t)


def _after_quote(out: list) -> bool:
    """The last text line written was a block quote and a blank line follows it."""
    if not out or out[-1].strip():
        return False
    last = next((x for x in reversed(out) if x.strip()), "")
    return last.lstrip().startswith(">")


def prepare(text: str, snap=None, rel: str = "", base: Path | None = None) -> tuple[str, dict]:
    """(plain Markdown, {notel-img name: image Path}) for a note. snap (an index.Snapshot) resolves [[links]] and
    attachments; base is the folder relative image paths start from when the file isn't in the vault."""
    images: dict[str, Path] = {}

    def image(target: str) -> str:
        target = unquote(target.strip().split("|")[0].strip())
        p = None
        if snap is not None:
            p = snap.resolve_file(target, rel)
        if p is None and base is not None and not target.startswith("/") and ".." not in target.split("/"):
            cand = base / target
            p = cand if cand.is_file() else None
        if p is None:
            return ""
        name = f"{IMG}:{len(images)}"
        images[name] = p
        return name

    def piece(seg: str) -> str:
        if seg.startswith("`") or re.match(r"<?[a-z][a-z0-9+.-]*://", seg):
            return seg
        m = re.fullmatch(r"(!?)\[\[([^\[\]|#^\n]*)(#[^\[\]|\n]*)?(?:\|([^\[\]\n]*))?\]\]", seg)
        if m:
            embed, target, heading, alias = m.group(1), m.group(2).strip(), m.group(3) or "", m.group(4)
            if embed and target.lower().endswith(store.IMAGE_EXT):
                name = image(target)
                return f"![{_link_text(target)}]({name})" if name else f"![{_link_text(target)}](missing:)"
            label = alias.strip() if alias and alias.strip() else target + heading.replace("#", " › ", 1) \
                if heading else target
            return f"[{_link_text(label or heading)}](note:{quote(target, safe='/')})" if target else \
                _link_text(label or heading)
        m = re.fullmatch(r"!\[([^\]\n]*)\]\(<?([^)>\n]*?)>?(?:\s+\"[^\"]*\")?\)", seg)
        if m and not re.match(r"[a-z][a-z0-9+.-]*:", m.group(2)):
            name = image(m.group(2))
            return f"![{m.group(1)}]({name or 'missing:'})"
        return seg

    def tags(seg: str) -> str:
        return store.TAG.sub(lambda m: f"[#{m.group(1)}](tag:{quote(m.group(1), safe='/')})", seg)

    front, body = store.split_frontmatter(text[:MAX_PREVIEW])
    out = []
    if front.strip():
        out += ["```yaml", front.rstrip("\n"), "```", ""]
    fence = ""
    for line in body.split("\n"):
        f = store.FENCE.match(line)
        if fence:
            if f and f.group(1)[0] == fence[0] and len(f.group(1)) >= len(fence):
                fence = ""
            out.append(line)
            continue
        if f:
            fence = f.group(1)
            out.append(line)
            continue
        if line.startswith(("    ", "\t")) and out and not out[-1].strip():
            out.append(line)                                    # an indented code block
            continue
        if line.lstrip().startswith("|") and _after_quote(out):
            out += ["\u200b", ""]           # Qt's reader breaks a table's first cell right after a quote
        pos, parts = 0, []
        for m in SEGMENT.finditer(line):
            parts.append(tags(line[pos:m.start()]))
            parts.append(piece(m.group(0)))
            pos = m.end()
        parts.append(tags(line[pos:]))
        out.append("".join(parts))
    return "\n".join(out), images


def load_images(paths: dict, cache: dict | None = None) -> dict:
    """{name: QImage} for prepare()'s images, scaled down to MAX_WIDTH; cache maps (path, mtime) -> QImage across
    renders. Safe on a worker thread (QImage, not QPixmap)."""
    out = {}
    for name, p in paths.items():
        try:
            st = os.stat(p)
        except OSError:
            continue
        key = (str(p), st.st_mtime_ns)
        if cache is not None and key in cache:
            out[name] = cache[key]
            continue
        if st.st_size > MAX_IMAGE:
            continue
        img = QImage(str(p))
        if img.isNull():
            continue
        if img.width() > MAX_WIDTH:
            img = img.scaledToWidth(MAX_WIDTH, Qt.TransformationMode.SmoothTransformation)
        out[name] = img
        if cache is not None:
            if len(cache) > 200:
                cache.clear()
            cache[key] = img
    return out


def placeholder(text: str, width: int = 360) -> QImage:
    """The gray box shown instead of an image that wasn't loaded (remote, missing or too big)."""
    img = QImage(QSize(width, 64), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor("#101010"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor("#2e2e2e"))
    p.drawRoundedRect(QRectF(0.5, 0.5, width - 1, 63), 6, 6)
    f = QFont(SANS)
    f.setPixelSize(12)
    p.setFont(f)
    p.setPen(QColor("#8c8c8c"))
    p.drawText(QRectF(12, 0, width - 24, 64), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
    p.end()
    return img


# ---------------------------------------------------------------- the look
DARK = {"text": "#e2e2e2", "muted": "#9a9a9a", "link": "#ffffff", "code_bg": "#161616", "inline_bg": "#1c1c1c",
        "rule": "#2a2a2a", "heading": "#ffffff"}
LIGHT = {"text": "#111111", "muted": "#555555", "link": "#000000", "code_bg": "#f1f1f1", "inline_bg": "#ececec",
         "rule": "#bbbbbb", "heading": "#000000"}


def style(doc: QTextDocument, dark: bool = True, size: int = 14):
    """Black & white on top of Qt's Markdown formats: no blue links, gray code blocks and quotes, ruled tables."""
    c = DARK if dark else LIGHT
    base = QFont(SANS)
    base.setPixelSize(size)
    doc.setDefaultFont(base)
    doc.setDocumentMargin(24 if dark else 0)
    cur = QTextCursor(doc)
    cur.beginEditBlock()
    block = doc.begin()
    while block.isValid():
        bf = block.blockFormat()
        new = QTextBlockFormat()
        level = bf.headingLevel()
        code = bf.hasProperty(QTextFormat.Property.BlockCodeFence) or bf.nonBreakableLines()
        quote_level = bf.intProperty(QTextFormat.Property.BlockQuoteLevel)
        if code:
            new.setBackground(QColor(c["code_bg"]))
            new.setLeftMargin(4)
            new.setRightMargin(4)
        if level:
            new.setTopMargin(18 if level <= 2 else 12)
            new.setBottomMargin(6)
        if quote_level:
            new.setLeftMargin(24 * quote_level)
        new.setLineHeight(135 if not code else 115, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        bc = QTextCursor(block)
        if bc.currentTable() is None:            # table cells keep Qt's spacing (taller lines misalign them)
            bc.mergeBlockFormat(new)
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid():
                cf = frag.charFormat()
                fix = QTextCharFormat()
                if cf.isAnchor():
                    fix.setForeground(QColor(c["link"]))
                    fix.setFontUnderline(True)
                elif level:
                    fix.setForeground(QColor(c["heading"]))
                elif quote_level:
                    fix.setForeground(QColor(c["muted"]))
                else:
                    fix.setForeground(QColor(c["text"]))
                if cf.fontFixedPitch() or code:
                    fix.setFontFamilies([MONO, "monospace"])
                    if not code:
                        fix.setBackground(QColor(c["inline_bg"]))
                if level:
                    fix.setFontWeight(QFont.Weight.DemiBold)
                fc = QTextCursor(doc)
                fc.setPosition(frag.position())
                fc.setPosition(frag.position() + frag.length(), QTextCursor.MoveMode.KeepAnchor)
                fc.mergeCharFormat(fix)
            it += 1
        block = block.next()
    for frame in doc.rootFrame().childFrames():
        if isinstance(frame, QTextTable):
            tf = frame.format()
            tf.setBorder(1)
            tf.setBorderBrush(QColor(c["rule"]))
            tf.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
            tf.setBorderCollapse(True)
            tf.setCellPadding(6)
            tf.setCellSpacing(0)
            tf.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
            frame.setFormat(tf)
            for col in range(frame.columns()):         # Qt's reader leaves a quote's margins on a table after it
                for row in range(frame.rows()):
                    cell = frame.cellAt(row, col)
                    cc = cell.firstCursorPosition()
                    bf = cc.blockFormat()
                    bf.setTopMargin(0)
                    bf.setBottomMargin(0)
                    cc.setBlockFormat(bf)
                    if row == 0:
                        cc.setPosition(cell.lastCursorPosition().position(), QTextCursor.MoveMode.KeepAnchor)
                        bold = QTextCharFormat()
                        bold.setFontWeight(QFont.Weight.DemiBold)
                        bold.setForeground(QColor(c["heading"]))
                        cc.mergeCharFormat(bold)
    cur.endEditBlock()


def build(text: str, snap=None, rel: str = "", base: Path | None = None, dark: bool = True, size: int = 14,
          cache: dict | None = None) -> tuple[str, dict]:
    """(Markdown, {name: QImage}) ready for render(); the slow part, for a worker."""
    md, paths = prepare(text, snap, rel, base)
    return md, load_images(paths, cache)


def render(doc: QTextDocument, md: str, dark: bool = True, size: int = 14):
    doc.setMarkdown(md, QTextDocument.MarkdownFeature.MarkdownDialectGitHub)
    style(doc, dark, size)


class Preview(QTextBrowser):
    """The rendered note. link(QUrl) fires on a click; hovered(str) says where a link goes."""
    link = Signal(QUrl)
    hovered = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Preview")
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setStyleSheet("QTextBrowser#Preview { background: #0b0b0b; border: none; color: #e2e2e2; "
                           "selection-background-color: #3a3a3a; selection-color: #ffffff; }")
        self.images: dict = {}
        self.anchorClicked.connect(self.link.emit)
        self.highlighted.connect(lambda u: self.hovered.emit(u.toString() if not u.isEmpty() else ""))
        self.size = 14

    def show_markdown(self, md: str, images: dict, size: int = 14):
        bar = self.verticalScrollBar()
        at = bar.value() / max(1, bar.maximum()) if bar.maximum() else 0.0
        self.images = images
        self.size = size
        render(self.document(), md, True, size)
        bar.setValue(round(at * bar.maximum()))

    def loadResource(self, kind, url: QUrl):
        if kind == QTextDocument.ResourceType.ImageResource.value or kind == QTextDocument.ResourceType.ImageResource:
            name = url.toString()
            if name in self.images:
                return self.images[name]
            if url.scheme() in ("http", "https", "ftp"):
                return placeholder(tr("grimoire.spells.notel.preview", "Remote image not loaded: {host}")
                                   .format(host=url.host()))
            return placeholder(tr("grimoire.spells.notel.preview", "Image not found"))
        return None                      # never fetch anything else (style sheets, remote documents)


# ---------------------------------------------------------------- export
def _document(text, snap, rel, base, title) -> QTextDocument:
    md, images = build(text, snap, rel, base, dark=False)
    doc = QTextDocument()
    for name, img in images.items():
        doc.addResource(QTextDocument.ResourceType.ImageResource.value, QUrl(name), img)
    render(doc, md, dark=False, size=13)
    doc.setMetaInformation(QTextDocument.MetaInformation.DocumentTitle, title)
    return doc, images


def _png_data(img: QImage) -> str:
    buf = QByteArray()
    dev = QBuffer(buf)
    dev.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(dev, "PNG")
    return "data:image/png;base64," + base64.b64encode(bytes(buf)).decode()


def export_html(text: str, dest: Path, snap=None, rel: str = "", base: Path | None = None, title: str = ""):
    """A self-contained HTML page (images inlined), written atomically. Worker-safe."""
    doc, images = _document(text, snap, rel, base, title)
    cur = QTextCursor(doc)
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            fmt = frag.charFormat()
            if fmt.isImageFormat():
                img_fmt = fmt.toImageFormat()
                name = img_fmt.name()
                new = QTextImageFormat(img_fmt)
                new.setName(_png_data(images[name]) if name in images else "")
                cur.setPosition(frag.position())
                cur.setPosition(frag.position() + frag.length(), QTextCursor.MoveMode.KeepAnchor)
                cur.setCharFormat(new)
            it += 1
        block = block.next()
    html = doc.toHtml()
    html = html.replace("<head>", "<head><meta name=\"viewport\" content=\"width=device-width\"/>"
                        "<style>body{max-width:46em;margin:2em auto;padding:0 1em;}</style>", 1)
    store.write_atomic(dest, html.encode())


def export_pdf(text: str, dest: Path, snap=None, rel: str = "", base: Path | None = None, title: str = ""):
    """An A4 PDF with page breaks, black on white, written to a temp file and renamed. Worker-safe."""
    doc, _ = _document(text, snap, rel, base, title)
    tmp = dest.with_name(f".{dest.name}.notel-{os.getpid()}.tmp")
    writer = QPdfWriter(str(tmp))
    writer.setTitle(title)
    writer.setCreator("NoteL · Grimoire Linux")
    writer.setResolution(300)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                     QMarginsF(18, 18, 18, 18), QPageLayout.Unit.Millimeter))
    try:
        doc.print_(writer)
        del writer                       # finishes the file
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
