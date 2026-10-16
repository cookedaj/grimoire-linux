# SPDX-License-Identifier: GPL-3.0-or-later
"""The text editor: a QPlainTextEdit with line numbers, the current line marked, smart Enter/Tab for lists and
code, Markdown shortcuts, [[link]] completion, Ctrl+click to follow links, and the find/replace bar."""
import re

from PySide6.QtCore import QRect, QRegularExpression, QSize, QStringListModel, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QPainter, QTextCursor,
                           QTextFormat, QTextOption)
from PySide6.QtWidgets import (QCompleter, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QTextEdit,
                               QToolButton, QWidget)

from grimoire.glyphs import glyph
from grimoire.i18n import MONO, SANS, tr
from grimoire.spells.notel.highlight import Highlighter

LOCAL_QSS = """
QPlainTextEdit#Editor { background: #0b0b0b; border: none; color: #dcdcdc;
                        selection-background-color: #3a3a3a; selection-color: #ffffff; }
QFrame#FindBar { background: #070707; border-top: 1px solid #161616; }
QToolButton#Opt { border: 1px solid #262626; border-radius: 6px; padding: 3px 7px; color: #8c8c8c;
                  font-family: "IBM Plex Mono"; font-size: 11px; }
QToolButton#Opt:checked { background: #f2f2f2; color: #000000; border-color: #f2f2f2; }
QToolButton#Opt:hover { border-color: #8a8a8a; }
"""
COMMENT = {"python": "#", "shell": "#", "yaml": "#", "ini": "#", "clike": "//"}
LIST = re.compile(r"^(\s*)([-*+]|(\d{1,9})([.)]))(\s+)(\[[ xX]\]\s+)?")
WIKI_OPEN = re.compile(r"\[\[([^\[\]|#\n]*)$")
LINK_AT = re.compile(r"!?\[\[([^\[\]\n]+)\]\]|\[[^\]\n]*\]\(([^)\s]+)\)|<?(https?://[^\s<>()\[\]]+)>?")


class _Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, e):
        self.editor.paint_gutter(e)


class Editor(QPlainTextEdit):
    """One open file. link(target) fires on Ctrl+click on a [[link]], a Markdown link or a URL."""
    link = Signal(str)
    zoom = Signal(int)                 # +1 / -1 / 0 (reset)

    def __init__(self, lang: str = "", note: bool = False):
        super().__init__()
        self.setObjectName("Editor")
        self.setStyleSheet(LOCAL_QSS)
        self.lang, self.note = lang, note
        self.highlighter = Highlighter(self.document(), lang)
        self.show_numbers = True
        self.indent = "    "
        self._found: list = []          # extra selections for find matches
        self.gutter = _Gutter(self)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)     # gutter on the left, code reads left to right
        self.blockCountChanged.connect(self._margins)
        self.updateRequest.connect(self._scroll_gutter)
        self.cursorPositionChanged.connect(self._mark_line)
        self.setCenterOnScroll(False)
        self.document().setDocumentMargin(10)
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setMaxVisibleItems(10)
        self.completer.activated.connect(self._complete)
        self.completer.popup().setStyleSheet("QListView { background: #121212; border: 1px solid #2e2e2e; "
                                             "color: #dcdcdc; padding: 4px; }"
                                             "QListView::item:selected { background: #2a2a2a; color: #ffffff; }")
        self.names = QStringListModel(self)
        self.completer.setModel(self.names)
        self._margins()
        self._mark_line()

    # ------------------------------------------------------------ look
    def configure(self, mono: bool, numbers: bool, wrap: bool, size: int):
        fixed = mono or not self.note
        f = QFont()
        f.setFamilies([MONO, "monospace"] if fixed else [SANS])
        f.setPixelSize(size)
        f.setFixedPitch(fixed)
        self.setFont(f)
        # the app's style sheet sets every widget's font, so the editor's own has to come through one too
        family = f'"{MONO}", monospace' if fixed else f'"{SANS}"'
        self.setStyleSheet(LOCAL_QSS + f"QPlainTextEdit#Editor {{ font-family: {family}; font-size: {size}px; }}")
        self.setTabStopDistance(QFontMetricsF(f).horizontalAdvance(" ") * 4)
        self.show_numbers = numbers
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if wrap else QPlainTextEdit.LineWrapMode.NoWrap)
        opt = self.document().defaultTextOption()
        # notes follow each paragraph's own direction (Arabic lines read right to left); code is always LTR
        opt.setTextDirection(Qt.LayoutDirection.LayoutDirectionAuto if self.note else Qt.LayoutDirection.LeftToRight)
        opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere if wrap else QTextOption.WrapMode.NoWrap)
        self.document().setDefaultTextOption(opt)
        self._margins()
        self.gutter.update()

    def set_language(self, lang: str):
        self.lang = lang
        self.highlighter.set_language(lang)

    def detect_indent(self):
        """Tabs when the file indents with tabs, else 2 or 4 spaces as it mostly does."""
        text = self.toPlainText()[:200000]
        tabs = len(re.findall(r"^\t", text, re.M))
        twos = len(re.findall(r"^  \S", text, re.M))
        fours = len(re.findall(r"^    \S", text, re.M))
        if tabs > max(twos, fours):
            self.indent = "\t"
        elif self.lang in ("yaml", "json") or (twos > fours * 2 and twos > 3):
            self.indent = "  "
        else:
            self.indent = "    "

    # ------------------------------------------------------------ gutter and current line
    def gutter_width(self) -> int:
        if not self.show_numbers:
            return 0
        digits = max(3, len(str(self.blockCount())))
        return 18 + self.fontMetrics().horizontalAdvance("9") * digits

    def _margins(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _scroll_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._margins()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, e):
        if not self.show_numbers:
            return
        p = QPainter(self.gutter)
        p.fillRect(e.rect(), QColor("#080808"))
        block = self.firstVisibleBlock()
        n = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        f = QFont(self.font())
        f.setFamilies([MONO, "monospace"])
        f.setPixelSize(max(9, self.font().pixelSize() - 2))
        p.setFont(f)
        h = self.fontMetrics().height()
        while block.isValid() and top <= e.rect().bottom():
            if block.isVisible() and bottom >= e.rect().top():
                p.setPen(QColor("#e8e8e8" if n == current else "#444444"))
                p.drawText(0, top, self.gutter.width() - 10, h,
                           Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignRight
                           | Qt.AlignmentFlag.AlignVCenter, str(n + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            n += 1

    def _mark_line(self):
        line = QTextEdit.ExtraSelection()
        line.format.setBackground(QColor("#121212"))
        line.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        line.cursor = self.textCursor()
        line.cursor.clearSelection()
        self.setExtraSelections([line] + self._found)
        if self.show_numbers:
            self.gutter.update()

    def set_found(self, selections: list):
        self._found = selections
        self._mark_line()

    # ------------------------------------------------------------ keys
    def keyPressEvent(self, e):
        popup = self.completer.popup()
        if popup.isVisible() and e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab,
                                             Qt.Key.Key_Escape, Qt.Key.Key_Up, Qt.Key.Key_Down):
            e.ignore()                     # the completer's popup handles these
            return
        mods = e.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        ctrl = Qt.KeyboardModifier.ControlModifier
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not mods & ctrl:
            self._newline()
            return
        if e.key() == Qt.Key.Key_Tab and not mods:
            self._indent(False)
            return
        if e.key() == Qt.Key.Key_Backtab:
            self._indent(True)
            return
        if mods == ctrl and self.lang == "markdown" and e.key() in (Qt.Key.Key_B, Qt.Key.Key_I, Qt.Key.Key_K):
            self._wrap({Qt.Key.Key_B: ("**", "**"), Qt.Key.Key_I: ("*", "*"), Qt.Key.Key_K: ("[", "]()")}[e.key()])
            return
        if mods == ctrl and e.key() == Qt.Key.Key_Slash and self.lang in COMMENT:
            self._toggle_comment()
            return
        if mods == ctrl and e.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Minus, Qt.Key.Key_0):
            self.zoom.emit({Qt.Key.Key_Minus: -1, Qt.Key.Key_0: 0}.get(e.key(), 1))
            return
        super().keyPressEvent(e)
        if self.note and e.text() and (e.text() == "[" or popup.isVisible() or e.key() == Qt.Key.Key_Backspace):
            self._maybe_complete()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom.emit(1 if e.angleDelta().y() > 0 else -1)
            return
        super().wheelEvent(e)

    def _newline(self):
        c = self.textCursor()
        line = c.block().text()
        col = c.positionInBlock()
        before = line[:col]
        lead = re.match(r"\s*", before).group(0)
        c.beginEditBlock()
        if self.lang == "markdown":
            m = LIST.match(line)
            if m and col >= m.end():
                if not line[m.end():].strip() and col == len(line):       # an empty item ends the list
                    c.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                    c.removeSelectedText()
                    c.endEditBlock()
                    return
                marker = m.group(2)
                if m.group(3):
                    marker = f"{int(m.group(3)) + 1}{m.group(4)}"
                box = "[ ] " if m.group(6) else ""
                c.insertText("\n" + m.group(1) + marker + m.group(5) + box)
                c.endEditBlock()
                self.setTextCursor(c)
                return
        extra = ""
        if self.lang in ("python", "yaml") and before.rstrip().endswith(":"):
            extra = self.indent
        elif self.lang in ("clike", "json", "css") and before.rstrip().endswith(("{", "[", "(")):
            extra = self.indent
        c.insertText("\n" + lead + extra)
        c.endEditBlock()
        self.setTextCursor(c)
        self.ensureCursorVisible()

    def _lines(self, c: QTextCursor):
        doc = self.document()
        a = doc.findBlock(c.selectionStart())
        b = doc.findBlock(c.selectionEnd() - (1 if c.hasSelection() and c.selectionEnd() > c.selectionStart()
                                              and doc.findBlock(c.selectionEnd()).position() == c.selectionEnd()
                                              else 0))
        blocks = []
        while a.isValid():
            blocks.append(a)
            if a == b:
                break
            a = a.next()
        return blocks

    def _indent(self, out: bool):
        c = self.textCursor()
        list_item = self.lang == "markdown" and LIST.match(c.block().text())
        if not out and not c.hasSelection() and not list_item:
            c.insertText(self.indent if self.indent == "\t" else
                         " " * (len(self.indent) - c.positionInBlock() % len(self.indent)))
            return
        c.beginEditBlock()
        for block in self._lines(c):
            text = block.text()
            bc = QTextCursor(block)
            if out:
                m = re.match(r"\t| {1,%d}" % len(self.indent.expandtabs(4)), text)
                if m:
                    bc.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, m.end())
                    bc.removeSelectedText()
            else:
                bc.insertText(self.indent if not list_item or self.indent == "\t" else "  " if
                              self.indent == "  " else "    ")
        c.endEditBlock()

    def _wrap(self, marks):
        c = self.textCursor()
        text = c.selectedText()
        c.beginEditBlock()
        c.insertText(marks[0] + text + marks[1])
        if not text:
            c.movePosition(QTextCursor.MoveOperation.Left, n=len(marks[1]))
        elif marks[1] == "]()":
            c.movePosition(QTextCursor.MoveOperation.Left)
        c.endEditBlock()
        self.setTextCursor(c)

    def _toggle_comment(self):
        mark = COMMENT[self.lang]
        c = self.textCursor()
        blocks = [b for b in self._lines(c) if b.text().strip()]
        if not blocks:
            return
        remove = all(b.text().lstrip().startswith(mark) for b in blocks)
        col = min(len(b.text()) - len(b.text().lstrip()) for b in blocks)
        c.beginEditBlock()
        for b in blocks:
            bc = QTextCursor(b)
            if remove:
                at = b.text().index(mark)
                bc.setPosition(b.position() + at)
                n = len(mark) + (1 if b.text()[at + len(mark):at + len(mark) + 1] == " " else 0)
                bc.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, n)
                bc.removeSelectedText()
            else:
                bc.setPosition(b.position() + col)
                bc.insertText(mark + " ")
        c.endEditBlock()

    # ------------------------------------------------------------ [[link]] completion
    def set_names(self, names: list[str]):
        self.names.setStringList(names)

    def _maybe_complete(self):
        c = self.textCursor()
        before = c.block().text()[:c.positionInBlock()]
        m = WIKI_OPEN.search(before)
        if not m:
            self.completer.popup().hide()
            return
        self.completer.setCompletionPrefix(m.group(1))
        if self.completer.completionCount() == 0:
            self.completer.popup().hide()
            return
        rect = self.cursorRect()
        rect.setWidth(min(420, max(260, self.completer.popup().sizeHintForColumn(0) + 30)))
        self.completer.complete(rect)

    def _complete(self, name: str):
        c = self.textCursor()
        before = c.block().text()[:c.positionInBlock()]
        m = WIKI_OPEN.search(before)
        if not m:
            return
        c.beginEditBlock()
        c.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(m.group(1)))
        after = c.block().text()[c.positionInBlock() + len(c.selectedText()):]
        c.insertText(name + ("" if after.startswith("]]") else "]]"))
        c.endEditBlock()
        self.setTextCursor(c)

    # ------------------------------------------------------------ Ctrl+click on links
    def link_at(self, pos) -> str:
        c = self.cursorForPosition(pos)
        text, col = c.block().text(), c.positionInBlock()
        for m in LINK_AT.finditer(text):
            if m.start() <= col <= m.end():
                if m.group(1):
                    return "[[" + m.group(1) + "]]"
                return m.group(2) or m.group(3)
        return ""

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        on = bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier) and bool(self.link_at(e.position().toPoint()))
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if on else Qt.CursorShape.IBeamCursor)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.modifiers() & Qt.KeyboardModifier.ControlModifier \
                and not self.textCursor().hasSelection():
            target = self.link_at(e.position().toPoint())
            if target:
                self.link.emit(target)
                return
        super().mouseReleaseEvent(e)


# ---------------------------------------------------------------- find and replace
class FindBar(QFrame):
    """Find (Ctrl+F) and replace (Ctrl+H) in the current editor: case, whole word and regex switches, every match
    marked, "3 of 12", Enter / Shift+Enter for next / previous, Esc to close."""
    MAX_MARKS = 5000

    def __init__(self, editor_of):
        super().__init__()
        self.setObjectName("FindBar")
        self.setStyleSheet(LOCAL_QSS)
        self.editor_of = editor_of            # () -> the current Editor or None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(6)
        self.find = QLineEdit()
        self.find.setPlaceholderText(tr("grimoire.spells.notel.editor", "Find"))
        self.find.setClearButtonEnabled(True)
        self.find.setMinimumWidth(180)
        self.find.textChanged.connect(lambda _: self.refresh(move=True))
        self.find.returnPressed.connect(lambda: self.step(1))
        self.replace = QLineEdit()
        self.replace.setPlaceholderText(tr("grimoire.spells.notel.editor", "Replace with"))
        self.replace.setMinimumWidth(160)
        self.replace.returnPressed.connect(self.replace_one)
        lay.addWidget(self.find, 2)
        self.opts = {}
        for key, label, tip in (("case", "Aa", tr("grimoire.spells.notel.editor", "Match case")),
                                ("word", "W", tr("grimoire.spells.notel.editor", "Whole words")),
                                ("regex", ".*", tr("grimoire.spells.notel.editor", "Regular expression"))):
            b = QToolButton()
            b.setObjectName("Opt")
            b.setLayoutDirection(Qt.LayoutDirection.LeftToRight)      # ".*" must not turn into "*."
            b.setText(label)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.toggled.connect(lambda _: self.refresh(move=True))
            lay.addWidget(b)
            self.opts[key] = b
        self.count = QLabel()
        self.count.setObjectName("Muted")
        lay.addWidget(self.count)
        for icon, tip, d in (("up", tr("grimoire.spells.notel.editor", "Previous (Shift+Enter)"), -1),
                             ("down", tr("grimoire.spells.notel.editor", "Next (Enter)"), 1)):
            b = QToolButton()
            b.setObjectName("Tool")
            b.setIcon(glyph(icon, 16))
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, d=d: self.step(d))
            lay.addWidget(b)
        lay.addSpacing(8)
        lay.addWidget(self.replace, 2)
        self.one = QToolButton()
        self.one.setText(tr("grimoire.spells.notel.editor", "Replace"))
        self.one.setObjectName("Opt")
        self.one.clicked.connect(self.replace_one)
        self.all = QToolButton()
        self.all.setText(tr("grimoire.spells.notel.editor", "Replace all"))
        self.all.setObjectName("Opt")
        self.all.clicked.connect(self.replace_all)
        lay.addWidget(self.one)
        lay.addWidget(self.all)
        close = QToolButton()
        close.setObjectName("Tool")
        close.setIcon(glyph("close", 14))
        close.setToolTip(tr("grimoire.spells.notel.editor", "Close (Esc)"))
        close.clicked.connect(self.close_bar)
        lay.addWidget(close)
        self._timer = QTimer(self, singleShot=True, interval=250, timeout=lambda: self.refresh(move=False))
        self.hide()

    def open_bar(self, replace: bool):
        ed = self.editor_of()
        if not ed:
            return
        for w in (self.replace, self.one, self.all):
            w.setVisible(replace)
        sel = ed.textCursor().selectedText()
        if sel and "\u2029" not in sel:
            self.find.setText(sel)
        self.show()
        (self.replace if replace and self.find.text() else self.find).setFocus()
        self.find.selectAll()
        self.refresh(move=False)

    def close_bar(self):
        self.hide()
        ed = self.editor_of()
        if ed:
            ed.set_found([])
            ed.setFocus()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close_bar()
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.step(-1)
            return
        super().keyPressEvent(e)

    def edited(self):
        """The text changed: recount soon (not on every key)."""
        if self.isVisible() and self.find.text():
            self._timer.start()

    def regex(self) -> QRegularExpression | None:
        text = self.find.text()
        if not text:
            return None
        pattern = text if self.opts["regex"].isChecked() else QRegularExpression.escape(text)
        if self.opts["word"].isChecked():
            pattern = rf"\b(?:{pattern})\b"
        opts = QRegularExpression.PatternOption.UseUnicodePropertiesOption
        if not self.opts["case"].isChecked():
            opts |= QRegularExpression.PatternOption.CaseInsensitiveOption
        rx = QRegularExpression(pattern, opts)
        return rx if rx.isValid() else None

    def _matches(self, ed, rx) -> list[tuple[int, int]]:
        out = []
        it = rx.globalMatch(ed.toPlainText())
        while it.hasNext() and len(out) < self.MAX_MARKS:
            m = it.next()
            if m.capturedLength() == 0:
                continue
            out.append((m.capturedStart(), m.capturedEnd()))
        return out

    def refresh(self, move: bool):
        ed = self.editor_of()
        if not ed or not self.isVisible():
            return
        rx = self.regex()
        bad = bool(self.find.text()) and rx is None
        self.find.setStyleSheet("border-color: #8a8a8a;" if bad else "")
        if rx is None:
            ed.set_found([])
            self.count.setText(tr("grimoire.spells.notel.editor", "Not a valid pattern") if bad else "")
            return
        spans = self._matches(ed, rx)
        marks = []
        for a, b in spans:
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#3a3a3a"))
            sel.format.setForeground(QColor("#ffffff"))
            sel.cursor = QTextCursor(ed.document())
            sel.cursor.setPosition(a)
            sel.cursor.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
            marks.append(sel)
        ed.set_found(marks)
        if move and spans:
            pos = ed.textCursor().selectionStart()
            target = next((s for s in spans if s[0] >= pos), spans[0])
            self._select(ed, target)
        self._count(ed, spans)

    def _count(self, ed, spans):
        if not spans:
            self.count.setText(tr("grimoire.spells.notel.editor", "No matches"))
            return
        c = ed.textCursor()
        at = next((i for i, s in enumerate(spans) if s == (c.selectionStart(), c.selectionEnd())), None)
        more = "+" if len(spans) >= self.MAX_MARKS else ""
        if at is None:
            self.count.setText(tr("grimoire.spells.notel.editor", "%n match(es)", n=len(spans)) + more)
        else:
            self.count.setText(tr("grimoire.spells.notel.editor", "{i} of {n}").format(i=at + 1,
                                                                                      n=f"{len(spans)}{more}"))

    @staticmethod
    def _select(ed, span):
        c = ed.textCursor()
        c.setPosition(span[0])
        c.setPosition(span[1], QTextCursor.MoveMode.KeepAnchor)
        ed.setTextCursor(c)
        ed.centerCursor()

    def step(self, d: int):
        ed = self.editor_of()
        rx = self.regex()
        if not ed or rx is None:
            return
        spans = self._matches(ed, rx)
        if not spans:
            self._count(ed, spans)
            return
        c = ed.textCursor()
        if d > 0:
            target = next((s for s in spans if s[0] >= c.selectionEnd() and s != (c.selectionStart(),
                                                                                  c.selectionEnd())), spans[0])
        else:
            target = next((s for s in reversed(spans) if s[1] <= c.selectionStart()), spans[-1])
        self._select(ed, target)
        self._count(ed, spans)

    def _replacement(self, whole: str, span) -> str:
        """The replace text; with regex on, \\1…\\9 (or $1…$9) take the match's groups."""
        text = self.replace.text()
        if not self.opts["regex"].isChecked():
            return text
        m = self.regex().match(whole, span[0])
        return re.sub(r"\\(\d)|\$(\d)|\\n|\\t", lambda g: m.captured(int(g.group(1) or g.group(2)))
                      if (g.group(1) or g.group(2)) else {"\\n": "\n", "\\t": "\t"}[g.group(0)], text)

    def replace_one(self):
        ed = self.editor_of()
        rx = self.regex()
        if not ed or rx is None or ed.isReadOnly():
            return
        spans = self._matches(ed, rx)
        c = ed.textCursor()
        cur = (c.selectionStart(), c.selectionEnd())
        if cur in spans:
            c.insertText(self._replacement(ed.toPlainText(), cur))
            ed.setTextCursor(c)
        self.refresh(move=False)
        self.step(1)

    def replace_all(self):
        ed = self.editor_of()
        rx = self.regex()
        if not ed or rx is None or ed.isReadOnly():
            return
        spans = self._matches(ed, rx)
        if not spans:
            return
        whole = ed.toPlainText()
        texts = [self._replacement(whole, s) for s in spans]
        c = QTextCursor(ed.document())
        c.beginEditBlock()                                   # one undo step for all of them
        for (a, b), t in zip(reversed(spans), reversed(texts)):
            c.setPosition(a)
            c.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
            c.insertText(t)
        c.endEditBlock()
        self.count.setText(tr("grimoire.spells.notel.editor", "Replaced %n match(es)", n=len(spans)))
        ed.set_found([])
