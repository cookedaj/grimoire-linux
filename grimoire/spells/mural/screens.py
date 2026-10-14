# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared UI for MuraL's design tabs: a big live preview, a gallery of design cards,
adjustments + Apply on the right. Previews and Apply run on worker threads so the window never freezes.

A tab subclasses ScreenTab and implements:
    designs()          -> list[Design]
    build_options(lay) -> add adjustment widgets; call self.changed() when they change
    options()          -> dict of current adjustment values (saved with the choice)
    set_options(dict)  -> load saved values into the widgets
    preview(design, options) -> QImage (16:9) for the big preview      } called on worker threads:
    thumbnail(design, options) -> QImage for the gallery card         } must not touch widgets
    apply(design, options)   -> do it; return a status message; raise RuntimeError on failure (worker thread)
Slow extra actions (e.g. a "Restore" button) go through self.background(fn, busy_text) so the window never freezes.
"""
import json
import threading
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap, QTextLayout, QTextOption
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout,
                               QWidget)

from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.paths import CONFIG

STATE = CONFIG / "mural-screens.json"
THUMB = QSize(184, 104)


@dataclass(frozen=True)
class Design:
    """name and blurb stay English (a tab's DESIGNS mark them with tr_noop in the tab's own context); the tab
    translates them where they're shown, so ids and scheme names built from them never change with the language."""
    id: str
    name: str
    blurb: str


class Choice(QComboBox):
    """A drop-down of stored values shown translated: value() is the stored value, never the shown text."""

    def __init__(self, items, on_change=None):
        super().__init__()
        for value, label in items:
            self.addItem(label, value)
        if on_change:
            self.currentIndexChanged.connect(on_change)

    def value(self):
        return self.currentData()

    def set_value(self, value):
        i = self.findData(value)
        if i >= 0:
            self.setCurrentIndex(i)


def _lines(text: str, font: QFont, width: float) -> str:
    """text broken into lines that fit width; QTextLayout picks break points that suit any script."""
    out = []
    for para in text.split("\n"):
        layout = QTextLayout(para, font)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        layout.beginLayout()
        while (line := layout.createLine()).isValid():
            line.setLineWidth(width)
            out.append(para[line.textStart():line.textStart() + line.textLength()].strip())
        layout.endLayout()
    return "\n".join(out)


class _Wrapping:
    """A button whose label wraps instead of being cut off: translations run long and the options panel is fixed.
    The width comes from the layout (Ignored policy); the label is rewrapped to it on every resize."""
    _base = QAbstractButton

    def _setup(self, text: str):
        self._full, self._overhead = text, None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def setText(self, text: str):
        self._full, self._overhead = text, None
        self._rewrap()

    def _rewrap(self):
        fm = self.fontMetrics()
        widest = lambda t: max(fm.horizontalAdvance(l) for l in t.split("\n"))
        if self._overhead is None:                # indicator, padding: measured on the whole text
            self._base.setText(self, self._full)
            self._overhead = self._base.sizeHint(self).width() - widest(self._full)
        room = self.width() - self._overhead - 2
        fits = self.width() <= 0 or widest(self._full) <= room
        self._base.setText(self, self._full if fits else _lines(self._full, self.font(), max(40, room)))

    def resizeEvent(self, e):
        self._base.resizeEvent(self, e)
        self._rewrap()

    def changeEvent(self, e):
        self._base.changeEvent(self, e)
        if e.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._overhead = None


class WrapCheck(_Wrapping, QCheckBox):
    _base = QCheckBox

    def __init__(self, text: str):
        QCheckBox.__init__(self, text)
        self._setup(text)


class WrapButton(_Wrapping, QPushButton):
    _base = QPushButton

    def __init__(self, text: str):
        QPushButton.__init__(self, text)
        self._setup(text)


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(key: str, value: dict):
    state = load_state()
    state[key] = value
    STATE.write_text(json.dumps(state, indent=2))


def community_designs(kind: str) -> list[Design]:
    """Store items of this kind that are installed, as designs (ids start with "store:")."""
    from grimoire.spells.mural import store
    return [Design(f"store:{e['key']}", e["name"], by_line(e)) for e in store.installed(kind)]


def by_line(entry: dict) -> str:
    """The blurb of an installed community item."""
    if entry.get("author"):
        return tr("grimoire.spells.mural.screens", "Community · by {author}").format(author=entry["author"])
    return tr("grimoire.spells.mural.screens", "Community · unknown author")


def community_entry(design_id: str) -> dict | None:
    from grimoire.spells.mural import store
    return store.registry().get(design_id.removeprefix("store:"))


def community_preview(design_id: str, w=1280, h=720) -> QImage:
    """The store's own preview image, letterboxed on black, with the name underneath."""
    entry = community_entry(design_id) or {}
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor("#0b0b0b"))
    src = QImage(entry["preview"]) if entry.get("preview") else QImage()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    if not src.isNull():
        scaled = src.scaled(QSize(w, h - 60), Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        p.drawImage((w - scaled.width()) // 2, (h - 60 - scaled.height()) // 2, scaled)
    p.setPen(QColor("#9a9a9a"))
    author = entry.get("author")
    line = (tr("grimoire.spells.mural.screens", "{name}   ·   community theme by {author}") if author else
            tr("grimoire.spells.mural.screens", "{name}   ·   community theme"))
    p.drawText(0, h - 50, w, 40, Qt.AlignmentFlag.AlignCenter, line.format(name=entry.get("name", ""), author=author))
    p.end()
    return img


def placeholder(size: QSize = THUMB) -> QPixmap:
    pm = QPixmap(size)
    pm.fill(QColor("#111111"))
    return pm


class _Signals(QObject):
    image = Signal(int, str, QImage)          # generation, slot ("big" or design index), image
    applied = Signal(bool, str)               # ok, message
    finished = Signal(str)                    # message from a background() action


_render_locks: dict[str, threading.Lock] = {}
_render_locks_guard = threading.Lock()


def render_lock(key: str) -> threading.Lock:
    """One lock per output file, so two threads never build the same preview at once."""
    with _render_locks_guard:
        return _render_locks.setdefault(key, threading.Lock())


class ScreenTab(QWidget):
    key = "screen"            # state key
    context = "grimoire.spells.mural.screens"   # the tab module's tr() context: its texts below are tr_noop'd in it
    subtitle = ""
    apply_label = ""          # "" = "Apply"
    apply_busy = ""           # "" = "Applying…"
    store: list[str] = []      # store category keys for the Community view (empty = no Community view)

    def shown(self, text: str) -> str:
        """A text this tab marked with tr_noop (its subtitle, labels, design names), in the user's language."""
        return tr(self.context, text) if text else text

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        saved = load_state().get(self.key, {})
        self._designs = self.designs()
        self.applied = saved.get("design")
        self._gen = 0                                   # bumps on every change; stale renders are dropped
        self._big_seq = 0                               # bumps per big preview: only the newest one is shown
        self._big_image: QImage | None = None
        self._sig = _Signals()
        self._sig.image.connect(self._on_image)
        self._sig.applied.connect(self._on_applied)
        self._sig.finished.connect(self._on_finished)
        self._render_timer = QTimer(self, singleShot=True, interval=150, timeout=self._rerender)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        left = QWidget()
        outer = QVBoxLayout(left)
        outer.setContentsMargins(36, 8, 24, 24)
        outer.setSpacing(14)
        head = QHBoxLayout()
        sub = QLabel(self.shown(self.subtitle))
        sub.setObjectName("Subtitle")
        sub.setWordWrap(True)
        head.addWidget(sub, 1)
        self.views = QStackedWidget()
        if self.store:
            switch = QHBoxLayout()
            switch.setSpacing(0)
            self._switch = []
            for i, name in enumerate((tr("grimoire.spells.mural.screens", "Designs"),
                                      tr("grimoire.spells.mural.screens", "Community · top 100"))):
                b = QPushButton(name)
                b.setObjectName("Segment")
                b.setProperty("pos", "first" if i == 0 else "last")
                b.setCheckable(True)
                b.setChecked(i == 0)
                b.clicked.connect(lambda _=False, i=i: self.show_view(i))
                self._switch.append(b)
                switch.addWidget(b)
            head.addLayout(switch)
        outer.addLayout(head)
        outer.addWidget(self.views, 1)

        designs_view = QWidget()
        ll = QVBoxLayout(designs_view)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(14)
        self.views.addWidget(designs_view)

        self.big = QLabel()
        self.big.setMinimumHeight(300)
        self.big.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(self.big, 3)

        self.gallery = QListWidget()
        self.gallery.setViewMode(QListWidget.ViewMode.IconMode)
        self.gallery.setFlow(QListWidget.Flow.LeftToRight)
        self.gallery.setWrapping(False)
        self.gallery.setMovement(QListWidget.Movement.Static)
        self.gallery.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.gallery.setIconSize(THUMB)
        self.gallery.setGridSize(QSize(THUMB.width() + 14, THUMB.height() + 42))
        self.gallery.setFixedHeight(THUMB.height() + 52)
        self.gallery.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery.currentRowChanged.connect(self._selected)
        ll.addWidget(self.gallery)
        if self.store:
            from grimoire.spells.mural.storeview import StoreView     # lazy: storeview imports this module
            self.views.addWidget(StoreView(self.store, self.reload_designs))
        root.addWidget(left, 1)

        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setFixedWidth(300)
        self._panel = panel
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(24, 24, 24, 24)
        pl.setSpacing(10)
        self.name = QLabel()
        self.name.setObjectName("Section")
        self.blurb = QLabel()
        self.blurb.setObjectName("Muted")
        self.blurb.setWordWrap(True)
        for lab in (self.name, self.blurb):       # community names and authors come from the store: never as HTML
            lab.setTextFormat(Qt.TextFormat.PlainText)
        pl.addWidget(self.name)
        pl.addWidget(self.blurb)
        pl.addSpacing(10)
        self.build_options(pl)
        pl.addStretch(1)
        self.status = QLabel()
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)       # error messages can quote file names from downloads
        pl.addWidget(self.status)
        self.apply_btn = QPushButton(self.shown(self.apply_label) or tr("grimoire.spells.mural.screens", "Apply"))
        self.apply_btn.setObjectName("Primary")
        self.apply_btn.setMinimumHeight(40)
        self.apply_btn.clicked.connect(self._apply)
        pl.addWidget(self.apply_btn)
        root.addWidget(panel)

        self._loading = True
        self.set_options(saved.get("options", {}))
        self._loading = False
        self._fill(self.applied)

    def _fill(self, select_id):
        self.gallery.blockSignals(True)
        self.gallery.clear()
        for d in self._designs:
            item = QListWidgetItem(QIcon(placeholder()), self.shown(d.name))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.gallery.addItem(item)
        self._label_in_use()
        ids = [d.id for d in self._designs]
        self.gallery.setCurrentRow(ids.index(select_id) if select_id in ids else 0)
        self.gallery.blockSignals(False)
        self._selected(self.gallery.currentRow(), render=False)
        self._rerender()

    def reload_designs(self):
        """Called after a community install/uninstall: rebuild the gallery, keep the selection."""
        keep = self.current().id if self._designs else None
        self._designs = self.designs()
        self._fill(keep)

    def show_view(self, i: int):
        self.views.setCurrentIndex(i)
        self._panel.setVisible(i == 0)            # the store gets the full width
        for k, b in enumerate(self._switch):
            b.setChecked(k == i)

    # ---- subclass hooks
    def designs(self) -> list[Design]:
        raise NotImplementedError

    def build_options(self, lay):
        pass

    def options(self) -> dict:
        return {}

    def set_options(self, opts: dict):
        pass

    def preview(self, design: Design, opts: dict) -> QImage:
        raise NotImplementedError

    def thumbnail(self, design: Design, opts: dict) -> QImage:
        """Image for the gallery card (defaults to the full preview)."""
        return self.preview(design, opts)

    def apply(self, design: Design, opts: dict) -> str | None:
        raise NotImplementedError

    # ---- rendering (worker threads)
    def changed(self, *_):
        if not self._loading:
            self._render_timer.start()

    def current(self) -> Design | None:
        if not self._designs:                  # e.g. no cursor themes installed at all
            return None
        return self._designs[max(0, min(self.gallery.currentRow(), len(self._designs) - 1))]

    def _submit(self, slot: str, fn):
        if slot == "big":                    # picking A then B quickly: A's slower render must not land last
            self._big_seq += 1
            slot = f"big{self._big_seq}"
        gen, sig = self._gen, self._sig

        def work():
            try:
                return fn()
            except Exception as e:       # a broken preview must never take the app down
                print(f"MuraL preview failed ({self.key}/{slot}): {e}")
                return QImage()

        POOL.start(Job(work, lambda img: sig.image.emit(gen, slot, img)))

    def _rerender(self):
        """Options changed: re-render the big preview first, then every card."""
        self._gen += 1
        opts = self.options()
        design = self.current()
        if design is not None:
            self._submit("big", lambda: self._preview(design, opts))
        for i, d in enumerate(self._designs):
            self._submit(str(i), lambda d=d: self._thumb(d, opts))

    def _preview(self, d: Design, opts: dict) -> QImage:
        return community_preview(d.id) if d.id.startswith("store:") else self.preview(d, opts)

    def _thumb(self, d: Design, opts: dict) -> QImage:
        return community_preview(d.id, 640, 360) if d.id.startswith("store:") else self.thumbnail(d, opts)

    def _on_image(self, gen: int, slot: str, img: QImage):
        big = slot.startswith("big")
        stale = slot != f"big{self._big_seq}" if big else int(slot) >= self.gallery.count()
        if gen != self._gen or img.isNull() or stale:
            return
        if big:
            self._big_image = img
            self._show_big()
        else:
            pm = QPixmap.fromImage(img.scaled(THUMB, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                              Qt.TransformationMode.SmoothTransformation))
            self.gallery.item(int(slot)).setIcon(QIcon(pm))

    def _selected(self, row, render=True):
        if row < 0:
            return
        d = self._designs[row]
        self.name.setText(self.shown(d.name).upper())
        self.blurb.setText(self.shown(d.blurb))
        if render:
            opts = self.options()
            self._submit("big", lambda: self._preview(d, opts))

    def _show_big(self):
        if self._big_image is None:
            return
        w = max(200, self.big.width())
        h = max(120, self.big.height())
        pm = QPixmap.fromImage(self._big_image.scaled(QSize(w, h), Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation))
        p = QPainter(pm)                         # hairline frame so dark designs don't melt into the page
        p.setPen(QColor("#2a2a2a"))
        p.drawRect(0, 0, pm.width() - 1, pm.height() - 1)
        p.end()
        self.big.setPixmap(pm)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._show_big()

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._show_big)    # sizes are only final once the tab is on screen

    def _label_in_use(self):
        for i, d in enumerate(self._designs):
            name = self.shown(d.name)
            self.gallery.item(i).setText(tr("grimoire.spells.mural.screens", "{name}  ·  in use").format(name=name)
                                         if d.id == self.applied else name)

    # ---- apply (worker thread)
    def _apply(self):
        d, opts, sig = self.current(), self.options(), self._sig
        if d is None:
            self.status.setText(tr("grimoire.spells.mural.screens", "Nothing to apply yet: get one from Community."))
            return
        self._pending = (d, opts)
        self.apply_btn.setEnabled(False)
        self.status.setText(self.shown(self.apply_busy) or tr("grimoire.spells.mural.screens", "Applying…"))

        def work():
            try:
                return True, self.apply(d, opts) or tr("grimoire.spells.mural.screens", "Applied ✓")
            except Exception as e:        # anything else would leave the button stuck on "Applying…"
                return False, tr("grimoire.spells.mural.screens", "Couldn't apply: {error}").format(error=e)

        POOL.start(Job(work, lambda result: sig.applied.emit(*result)))

    def _on_applied(self, ok: bool, msg: str):
        self.apply_btn.setEnabled(True)
        self.status.setText(msg)
        if ok:
            d, opts = self._pending
            self.applied = d.id
            save_state(self.key, {"design": d.id, "options": opts})
            self._label_in_use()

    def background(self, fn, busy: str):
        """Run fn() (returns a status message, raises on failure) on a worker thread, Apply disabled meanwhile."""
        sig = self._sig
        self.apply_btn.setEnabled(False)
        self.status.setText(busy)

        def work():
            try:
                return fn()
            except Exception as e:
                return tr("grimoire.spells.mural.screens", "Couldn't restore: {error}").format(error=e)

        POOL.start(Job(work, lambda msg: sig.finished.emit(msg)))

    def _on_finished(self, msg: str):
        self.apply_btn.setEnabled(True)
        self.status.setText(msg)
