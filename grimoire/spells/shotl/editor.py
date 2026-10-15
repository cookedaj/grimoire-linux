# SPDX-License-Identifier: GPL-3.0-or-later
"""The editor: crop, arrows, boxes, freehand, text, pixelate and highlight, in white, grays or black only.
Edits are a list of operations replayed over the untouched capture, so undo/redo is just moving along that list and
nothing is baked in until you save or copy. A crop is an operation too; later marks use the cropped coordinates."""
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QPainter, QPainterPath, QPen, QPolygonF, QShortcut
from PySide6.QtWidgets import (QBoxLayout, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from grimoire.fsutil import tilde
from grimoire.i18n import tr, tr_noop
from grimoire.spells.shotl import capture, shots
from grimoire.spells.shotl.icons import icon
from grimoire.spells.shotl.newshot import NewButton
from grimoire.theme import FONT
from grimoire.widgets import segments

TOOLS = [("crop", tr_noop("grimoire.spells.shotl.editor", "Crop  (C)")),          # tips: tr() where shown
         ("arrow", tr_noop("grimoire.spells.shotl.editor", "Arrow  (A)")),
         ("box", tr_noop("grimoire.spells.shotl.editor", "Box  (B)")),
         ("pen", tr_noop("grimoire.spells.shotl.editor", "Freehand  (P)")),
         ("text", tr_noop("grimoire.spells.shotl.editor", "Text  (T)")),
         ("pixelate", tr_noop("grimoire.spells.shotl.editor", "Pixelate a region  (X)")),
         ("highlight", tr_noop("grimoire.spells.shotl.editor", "Highlight  (H)"))]
KEYS = {"C": "crop", "A": "arrow", "B": "box", "P": "pen", "T": "text", "X": "pixelate", "H": "highlight"}
COLORS = ["#ffffff", "#c8c8c8", "#8c8c8c", "#4a4a4a", "#000000"]       # black & white only, by design
SIZES = {"S": 3, "M": 6, "L": 10}


@dataclass
class Op:
    kind: str
    color: str = "#ffffff"
    width: float = 6
    pts: list = field(default_factory=list)       # QPointF, image coordinates at the time of the op
    text: str = ""

    def rect(self) -> QRectF:
        return QRectF(self.pts[0], self.pts[-1]).normalized() if self.pts else QRectF()


def _contrast(color: str) -> QColor:
    return QColor("#000000") if QColor(color).lightness() > 110 else QColor("#ffffff")


def text_font(width: float) -> QFont:
    f = QFont(FONT)
    f.setPixelSize(int(12 + width * 3))
    f.setWeight(QFont.Weight.DemiBold)
    return f


def pixelate(img: QImage, r: QRectF, width: float):
    rr = r.toRect().intersected(img.rect())
    if rr.width() < 2 or rr.height() < 2:
        return
    block = max(12, min(rr.width(), rr.height()) // 5, int(width * 3))     # coarse enough that text can't be read
    part = img.copy(rr)
    small = part.scaled(max(1, rr.width() // block), max(1, rr.height() // block),
                        Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    big = small.scaled(rr.width(), rr.height(), Qt.AspectRatioMode.IgnoreAspectRatio,
                       Qt.TransformationMode.FastTransformation)
    p = QPainter(img)
    p.drawImage(rr.topLeft(), big)
    p.end()


def draw(p: QPainter, op: Op, preview=False):
    """Paint one mark (not crop/pixelate) in image coordinates."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    col = QColor(op.color)
    pen = QPen(col, op.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    if op.kind == "arrow" and len(op.pts) >= 2:
        a, b = op.pts[0], op.pts[-1]
        d = b - a
        length = max(1e-6, (d.x() ** 2 + d.y() ** 2) ** .5)
        u = QPointF(d.x() / length, d.y() / length)
        head = min(length * .6, 10 + op.width * 3.2)
        n = QPointF(-u.y(), u.x())
        base = b - u * head
        p.setPen(pen)
        p.drawLine(a, b - u * (head * .6))
        p.setPen(QPen(col, 1))
        p.setBrush(col)
        p.drawPolygon(QPolygonF([b, base + n * head * .55, base - n * head * .55]))
    elif op.kind == "box" and len(op.pts) >= 2:
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(op.rect())
    elif op.kind == "pen" and op.pts:
        p.setPen(pen)
        path = QPainterPath(op.pts[0])
        for pt in op.pts[1:]:
            path.lineTo(pt)
        if len(op.pts) == 1:
            path.lineTo(op.pts[0] + QPointF(.1, 0))
        p.drawPath(path)
    elif op.kind == "highlight" and len(op.pts) >= 2:
        fill = QColor(col)
        fill.setAlphaF(.38)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawRect(op.rect())
    elif op.kind == "text" and op.text:
        p.setFont(text_font(op.width))
        path = QPainterPath()
        fm_ascent = p.fontMetrics().ascent()
        for i, line in enumerate(op.text.split("\n")):
            path.addText(op.pts[0] + QPointF(0, fm_ascent + i * p.fontMetrics().lineSpacing()), p.font(), line)
        p.setPen(QPen(_contrast(op.color), max(2.0, op.width * .5), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)                       # an outline in the opposite tone keeps text readable anywhere
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawPath(path)
    elif preview and op.kind in ("crop", "pixelate") and len(op.pts) >= 2:
        p.setPen(QPen(QColor("#ffffff"), 0, Qt.PenStyle.DashLine))
        p.setBrush(QColor(255, 255, 255, 30) if op.kind == "pixelate" else Qt.BrushStyle.NoBrush)
        p.drawRect(op.rect())


def render(base: QImage, ops: list[Op]) -> QImage:
    img = base.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    for op in ops:
        if op.kind == "crop":
            r = op.rect().toRect().intersected(img.rect())
            if r.width() > 1 and r.height() > 1:
                img = img.copy(r)
        elif op.kind == "pixelate":
            pixelate(img, op.rect(), op.width)
        else:
            p = QPainter(img)
            draw(p, op)
            p.end()
    return img


class Canvas(QWidget):
    """Shows the current render fitted to the space and turns mouse drags into operations."""
    changed = Signal()

    def __init__(self, editor):
        super().__init__()
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)   # a chart/canvas: never mirrored in RTL
        self.ed = editor
        self.setMinimumSize(320, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.cur: Op | None = None
        self.entry: QLineEdit | None = None
        self.entry_at = QPointF()
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _geom(self):
        img = self.ed.rendered
        k = min((self.width() - 32) / max(1, img.width()), (self.height() - 32) / max(1, img.height()), 2.0)
        k = max(k, 0.05)
        w, h = img.width() * k, img.height() * k
        return k, QPointF((self.width() - w) / 2, (self.height() - h) / 2)

    def to_img(self, pos: QPointF) -> QPointF:
        k, off = self._geom()
        img = self.ed.rendered
        pt = (pos - off) / k
        return QPointF(min(max(pt.x(), 0), img.width()), min(max(pt.y(), 0), img.height()))

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#080808"))
        img = self.ed.rendered
        k, off = self._geom()
        target = QRectF(off.x(), off.y(), img.width() * k, img.height() * k)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(target, img)
        p.setPen(QPen(QColor("#262626"), 1))
        p.drawRect(target.adjusted(-1, -1, 0, 0))
        if self.cur:
            p.save()
            p.translate(off)
            p.scale(k, k)
            if self.cur.kind == "crop" and len(self.cur.pts) >= 2:   # dim what the crop drops
                r = self.cur.rect()
                path = QPainterPath()
                path.addRect(QRectF(img.rect()))
                inner = QPainterPath()
                inner.addRect(r)
                p.fillPath(path.subtracted(inner), QColor(0, 0, 0, 150))
            draw(p, self.cur, preview=True)
            p.restore()

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.commit_text()
        pt = self.to_img(e.position())
        tool = self.ed.tool
        if tool == "text":
            self._start_text(e.position(), pt)
            return
        self.cur = Op(tool, self.ed.color, self.ed.width, [pt])
        self.update()

    def mouseMoveEvent(self, e):
        if self.cur:
            pt = self.to_img(e.position())
            if self.cur.kind == "pen":
                self.cur.pts.append(pt)
            else:
                self.cur.pts[1:] = [pt]
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self.cur:
            return
        op, self.cur = self.cur, None
        r = op.rect()
        if op.kind == "pen" or (len(op.pts) >= 2 and (r.width() > 3 and r.height() > 3
                                                       or op.kind == "arrow" and max(r.width(), r.height()) > 3)):
            self.ed.push(op)                       # a stray click doesn't leave an empty mark behind
            if op.kind == "crop":
                self.ed.set_tool(self.ed.last_mark)  # one crop at a time; back to marking up
        self.update()

    # text: a borderless line edit on the canvas, committed on Enter or when focus leaves
    def _start_text(self, wpos: QPointF, pt: QPointF):
        k, _ = self._geom()
        self.entry = QLineEdit(self)
        self.entry.setObjectName("CanvasText")
        f = text_font(self.ed.width)
        f.setPixelSize(max(10, int(f.pixelSize() * k)))
        self.entry.setFont(f)
        c = self.ed.color
        self.entry.setStyleSheet(f"QLineEdit#CanvasText {{ background: rgba(0,0,0,90); color: {c}; "
                                 f"border: 1px dashed #8c8c8c; border-radius: 0; padding: 0 2px; }}")
        self.entry.setPlaceholderText(tr("grimoire.spells.shotl.editor", "Type, then Enter"))
        self.entry.move(wpos.toPoint() - self.entry.rect().topLeft())
        self.entry.resize(max(220, int(self.width() - wpos.x() - 8)) if wpos.x() < self.width() - 230 else 220,
                          self.entry.sizeHint().height())
        self.entry_at = pt
        self.entry.returnPressed.connect(self.commit_text)
        self.entry.show()
        self.entry.setFocus()

    def commit_text(self):
        if not self.entry:
            return
        entry, self.entry = self.entry, None
        text = entry.text().strip()
        entry.hide()
        entry.deleteLater()
        if text:
            self.ed.push(Op("text", self.ed.color, self.ed.width, [self.entry_at], text))

    def cancel_text(self):
        if self.entry:
            self.entry.hide()
            self.entry.deleteLater()
            self.entry = None


class Editor(QWidget):
    """Edits one image. Emits saved(Path) after writing a file, closed() when the user is done with it, and
    new_requested(mode) when they asked for another shot (after settling unsaved work); the host takes it and load()s
    the result here."""
    saved = Signal(object)
    closed = Signal()
    toast = Signal(str)
    new_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base = QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
        self.ops: list[Op] = []
        self.redo_ops: list[Op] = []
        self.rendered = self.base
        self.source: Path | None = None             # the file this came from, None for a fresh capture
        self.saved_at = 0                           # len(ops) when last written/copied (what "unsaved" means)
        self.handled = False                        # a fresh capture copied or saved at least once
        self.tool, self.color, self.width = "arrow", COLORS[0], SIZES["M"]
        self.last_mark = "arrow"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        bar = QFrame()
        bar.setObjectName("Row")
        self.bar_lay = QBoxLayout(QBoxLayout.Direction.LeftToRight, bar)
        self.bar_lay.setContentsMargins(8, 6, 8, 6)
        self.bar_lay.setSpacing(2)
        self._tools_w = QWidget()
        bl = QHBoxLayout(self._tools_w)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(2)
        self.new_btn = NewButton(tr("grimoire.spells.shotl.editor", "New"))
        self.new_btn.requested.connect(self.new_shot)
        bl.addWidget(self.new_btn)
        bl.addWidget(self._sep())
        self.tools = QButtonGroup(self)
        for name, tip in TOOLS:
            b = self._tool(name, tr("grimoire.spells.shotl.editor", tip), checkable=True)
            b.setChecked(name == self.tool)
            b.clicked.connect(lambda _=False, n=name: self.set_tool(n))
            self.tools.addButton(b)
            bl.addWidget(b)
        bl.addWidget(self._sep())
        self.swatches = QButtonGroup(self)
        for c in COLORS:
            s = QToolButton()
            s.setObjectName("Swatch")
            s.setCheckable(True)
            s.setChecked(c == self.color)
            s.setFixedSize(26, 26)
            s.setToolTip(tr("grimoire.spells.shotl.editor", "White") if c == "#ffffff"
                         else tr("grimoire.spells.shotl.editor", "Black") if c == "#000000"
                         else tr("grimoire.spells.shotl.editor", "Gray"))
            s.setStyleSheet(f"QToolButton#Swatch {{ background: {c}; border: 2px solid #2e2e2e; border-radius: 13px; }}"
                            f"QToolButton#Swatch:checked {{ border: 2px solid #ffffff; }}"
                            f"QToolButton#Swatch:hover {{ border-color: #8a8a8a; }}")
            s.clicked.connect(lambda _=False, col=c: self._set_color(col))
            self.swatches.addButton(s)
            bl.addWidget(s)
        bl.addWidget(self._sep())
        self.sizes = QButtonGroup(self)
        segs = []
        names = {"S": tr("grimoire.spells.shotl.editor", "S", "small size"),
                 "M": tr("grimoire.spells.shotl.editor", "M", "medium size"),
                 "L": tr("grimoire.spells.shotl.editor", "L", "large size")}
        for label, w in SIZES.items():
            b = QPushButton(names[label])
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setChecked(w == self.width)
            segs.append(b)
            b.setToolTip(tr("grimoire.spells.shotl.editor", "Line and text size"))
            b.clicked.connect(lambda _=False, v=w: setattr(self, "width", v))
            self.sizes.addButton(b)
            bl.addWidget(b)
        segments(segs)
        bl.addWidget(self._sep())
        self.undo_btn = self._tool("undo", tr("grimoire.spells.shotl.editor", "Undo  (Ctrl+Z)"))
        self.undo_btn.clicked.connect(self.undo)
        self.redo_btn = self._tool("redo", tr("grimoire.spells.shotl.editor", "Redo  (Ctrl+Shift+Z)"))
        self.redo_btn.clicked.connect(self.redo)
        bl.addWidget(self.undo_btn)
        bl.addWidget(self.redo_btn)
        bl.addStretch(1)
        self.copy_btn = QPushButton(tr("grimoire.spells.shotl.editor", "Copy"))
        self.copy_btn.setToolTip(tr("grimoire.spells.shotl.editor", "Copy the image  (Ctrl+C)"))
        self.copy_btn.clicked.connect(self.copy)
        self.save_as_btn = QPushButton(tr("grimoire.spells.shotl.editor", "Save as…"))
        self.save_as_btn.clicked.connect(self.save_as)
        self.save_btn = QPushButton(tr("grimoire.spells.shotl.editor", "Save"))
        self.save_btn.setObjectName("Primary")
        self.save_btn.setToolTip(tr("grimoire.spells.shotl.editor", "Save into your shots folder  (Ctrl+S)"))
        self.save_btn.clicked.connect(self.save)
        self.close_btn = QPushButton(tr("grimoire.spells.shotl.editor", "Done"))
        self.close_btn.clicked.connect(self.request_close)
        self._acts_w = QWidget()
        al = QHBoxLayout(self._acts_w)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(2)
        for b in (self.copy_btn, self.save_as_btn, self.save_btn, self.close_btn):
            al.addWidget(b)
        self.bar_lay.addWidget(self._tools_w, 1)
        self.bar_lay.addWidget(self._acts_w, 0, Qt.AlignmentFlag.AlignTrailing)
        bar.setMinimumWidth(max(self._tools_w.sizeHint().width(), self._acts_w.sizeHint().width()) + 16)
        lay.addWidget(bar)
        self.canvas = Canvas(self)
        lay.addWidget(self.canvas, 1)
        self.info = QLabel()
        self.info.setObjectName("Muted")
        lay.addWidget(self.info)

        for seq, slot in ((QKeySequence.StandardKey.Undo, self.undo), (QKeySequence.StandardKey.Redo, self.redo),
                          ("Ctrl+Y", self.redo), (QKeySequence.StandardKey.Copy, self.copy),
                          (QKeySequence.StandardKey.Save, self.save), ("Ctrl+Shift+S", self.save_as),
                          ("Esc", self._escape)):
            QShortcut(QKeySequence(seq), self, slot, context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.new_key = QShortcut(QKeySequence(QKeySequence.StandardKey.New), self, self.new_btn.trigger,
                                 context=Qt.ShortcutContext.WindowShortcut)    # the hub page turns it off: it has its own
        for key, name in KEYS.items():
            QShortcut(QKeySequence(key), self.canvas, lambda n=name: self.set_tool(n),
                      context=Qt.ShortcutContext.WidgetShortcut)
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._refresh()

    def resizeEvent(self, e):
        """In longer languages the save buttons drop to a second row instead of making the window wider."""
        need = self._tools_w.sizeHint().width() + self._acts_w.sizeHint().width() + 18
        d = QBoxLayout.Direction.LeftToRight if self.contentsRect().width() >= need \
            else QBoxLayout.Direction.TopToBottom
        if self.bar_lay.direction() != d:
            self.bar_lay.setDirection(d)
        super().resizeEvent(e)

    def _tool(self, name, tip, checkable=False) -> QToolButton:
        b = QToolButton()
        b.setObjectName("Tool")
        b.setIcon(icon(name, 20))
        b.setIconSize(QSize(20, 20))
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setAutoRaise(True)
        return b

    def _sep(self) -> QFrame:
        s = QFrame()
        s.setObjectName("Rule")
        s.setFixedSize(1, 22)
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.addWidget(s)
        return w

    # ---------------------------------------------------------------- state
    def load(self, img: QImage, source: Path | None = None):
        self.canvas.cancel_text()
        self.base = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.ops, self.redo_ops = [], []
        self.source = source
        self.saved_at = 0
        self.handled = source is not None
        self._refresh()

    def unsaved(self) -> bool:
        return len(self.ops) != self.saved_at or not self.handled

    def set_tool(self, name: str):
        self.canvas.commit_text()
        self.tool = name
        if name != "crop":
            self.last_mark = name
        for b, (n, _) in zip(self.tools.buttons(), TOOLS):
            b.setChecked(n == name)

    def _set_color(self, c: str):
        self.color = c

    def push(self, op: Op):
        self.ops.append(op)
        self.redo_ops.clear()
        self._refresh()

    def undo(self):
        self.canvas.cancel_text()
        if self.ops:
            self.redo_ops.append(self.ops.pop())
            self._refresh()

    def redo(self):
        if self.redo_ops:
            self.ops.append(self.redo_ops.pop())
            self._refresh()

    def _refresh(self):
        self.rendered = render(self.base, self.ops)
        self.undo_btn.setEnabled(bool(self.ops))
        self.redo_btn.setEnabled(bool(self.redo_ops))
        bits = [f"{self.rendered.width()} × {self.rendered.height()}",
                shots.ltr(tilde(self.source)) if self.source else tr("grimoire.spells.shotl.editor", "Not saved yet")]
        if self.ops:
            bits.append(tr("grimoire.spells.shotl.editor", "%n edit(s)", n=len(self.ops)))
        self.info.setText("  ·  ".join(bits))
        self.canvas.update()

    def image(self) -> QImage:
        self.canvas.commit_text()
        return render(self.base, self.ops).convertToFormat(QImage.Format.Format_ARGB32)

    # ---------------------------------------------------------------- output
    def copy(self):
        capture.copy_image(self.image())
        if not self.source:                        # copying a fresh capture counts as dealing with it
            self.saved_at, self.handled = len(self.ops), True
        self.toast.emit(tr("grimoire.spells.shotl.editor", "Copied to the clipboard"))

    def _write(self, dest: Path) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        fmt = "JPG" if dest.suffix.lower() in (".jpg", ".jpeg") else "PNG"
        if not self.image().save(str(dest), fmt):
            shots.release(dest)
            QMessageBox.warning(self, "ShotL", tr("grimoire.spells.shotl.editor", "Couldn't write {path}")
                                .format(path=shots.ltr(tilde(dest))))
            return False
        self.source = dest
        self.saved_at = len(self.ops)
        self.handled = True
        shots.add(dest)
        self._refresh()
        self.saved.emit(dest)
        self.toast.emit(tr("grimoire.spells.shotl.editor", "Saved {path}").format(path=shots.ltr(tilde(dest))))
        return True

    def save(self) -> bool:
        """A fresh capture gets a dated name; an edited file is saved beside it as 'name (2).png', never over it."""
        if self.source and not self.unsaved():
            self.toast.emit(tr("grimoire.spells.shotl.editor", "Already saved as {path}")
                            .format(path=shots.ltr(tilde(self.source))))
            return True
        if not self.source:
            return self._write(shots.new_path())
        dest = self.source
        if dest.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            dest = dest.with_suffix(".png")
        return self._write(shots.claim(dest))

    def save_as(self) -> bool:
        start = str(self.source or shots.new_path(reserve=False))
        kinds = ";;".join((tr("grimoire.spells.shotl.editor", "PNG image") + " (*.png)",
                           tr("grimoire.spells.shotl.editor", "JPEG image") + " (*.jpg)"))
        name, _ = QFileDialog.getSaveFileName(self, tr("grimoire.spells.shotl.editor", "Save screenshot"), start, kinds,
                                              options=QFileDialog.Option.DontConfirmOverwrite)
        if not name:
            return False
        dest = Path(name)
        if dest.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            dest = dest.with_suffix(".png")
        return self._write(shots.claim(dest))        # an existing name becomes "name (2).png"

    def _escape(self):
        if self.canvas.entry:
            self.canvas.cancel_text()
        elif self.canvas.cur:
            self.canvas.cur = None
            self.canvas.update()
        else:
            self.request_close()

    def settle(self, ask: str) -> bool:
        """Save / Discard / Cancel when there's unsaved work. True when it's fine to drop the current image."""
        self.canvas.commit_text()
        if not self.unsaved():
            return True
        box = QMessageBox(QMessageBox.Icon.NoIcon, "ShotL", ask,      # no theme icon: they're colored
                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                          | QMessageBox.StandardButton.Cancel, self)
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        ans = box.exec()
        return ans == QMessageBox.StandardButton.Discard or (ans == QMessageBox.StandardButton.Save and self.save())

    def request_close(self) -> bool:
        """Ask before dropping unsaved work. True when it's fine to close."""
        if not self.settle(tr("grimoire.spells.shotl.editor", "Save this screenshot before closing?") if not self.source
                           else tr("grimoire.spells.shotl.editor", "Save your edits before closing?")):
            return False
        self.saved_at = len(self.ops)
        self.handled = True
        self.closed.emit()
        return True

    def new_shot(self, mode: str):
        """The New button or Ctrl+N: settle unsaved work, then let the host capture into this editor."""
        if self.settle(tr("grimoire.spells.shotl.editor", "Save this screenshot before taking a new one?")
                       if not self.source
                       else tr("grimoire.spells.shotl.editor", "Save your edits before taking a new one?")):
            self.new_requested.emit(mode)
