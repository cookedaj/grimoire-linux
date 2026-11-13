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

Every tab also gets, for free:
  Import…  under the big preview, when imports.IMPORTERS lists the tab's key (pictures or theme archives/folders).
  Reset    above Apply: puts back what was active before the last Apply (HISTORY keeps the last few, per tab),
           through the tab's own apply(); before MuraL's first Apply that's the tab's own `_restore` (its
           "Restore previous …" button), when it has one. With nothing applied it just reverts the panel.
"""
import json
import threading
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap, QTextLayout, QTextOption
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFrame,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from grimoire.i18n import isolate, tr
from grimoire.jobs import POOL, Job
from grimoire.paths import CONFIG, DATA
from grimoire.widgets import segments

STATE = CONFIG / "mural-screens.json"
HISTORY = DATA / "mural" / "history.json"     # per tab: what was active before each of the last Applies
HISTORY_KEEP = 5
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
        state = json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in state.items() if isinstance(v, dict)} if isinstance(state, dict) else {}


def save_state(key: str, value: dict):
    state = load_state()
    state[key] = value
    STATE.write_text(json.dumps(state, indent=2))


def load_history(key: str) -> list[dict]:
    """[{design (None = nothing MuraL applied), options}], oldest first."""
    try:
        hist = json.loads(HISTORY.read_text()).get(key, [])
        return [h for h in hist if isinstance(h, dict)]
    except (OSError, ValueError, AttributeError):
        return []


def save_history(key: str, hist: list[dict]):
    try:
        data = json.loads(HISTORY.read_text())
        data = data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        data = {}
    data[key] = hist[-HISTORY_KEEP:]
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(HISTORY)


def community_designs(kind: str) -> list[Design]:
    """Store items of this kind that are installed, as designs (ids start with "store:")."""
    from grimoire.spells.mural import store
    return [Design(f"store:{e['key']}", e["name"], by_line(e)) for e in store.installed(kind)]


def by_line(entry: dict) -> str:
    """The blurb of an installed community item (or one you imported)."""
    if str(entry.get("item", "")).startswith("import:"):
        return tr("grimoire.spells.mural.screens", "Imported by you")
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
    imported = str(entry.get("item", "")).startswith("import:")
    line = (tr("grimoire.spells.mural.screens", "{name}   ·   imported") if imported
            else tr("grimoire.spells.mural.screens", "{name}   ·   community theme by {author}") if author else
            tr("grimoire.spells.mural.screens", "{name}   ·   community theme"))
    p.drawText(0, h - 50, w, 40, Qt.AlignmentFlag.AlignCenter,
               line.format(name=isolate(entry.get("name", "")), author=isolate(author)))
    p.end()
    return img


def placeholder(size: QSize = THUMB) -> QPixmap:
    pm = QPixmap(size)
    pm.fill(QColor("#111111"))
    return pm


class _Signals(QObject):
    image = Signal(int, str, QImage)          # generation, slot ("big" or design index), image
    applied = Signal(bool, str)               # ok, message
    finished = Signal(bool, str)              # ok, message from a background() action
    imported = Signal(object)                 # imports.run()'s result


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
        self._sig.imported.connect(self._on_imported)
        self._after_background = None                 # Reset's follow-up to a tab's own restore
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
                b.setCheckable(True)
                b.setChecked(i == 0)
                b.clicked.connect(lambda _=False, i=i: self.show_view(i))
                self._switch.append(b)
                switch.addWidget(b)
            segments(self._switch)
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
        self._build_import(ll)

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
        self.reset_btn = QPushButton(tr("grimoire.spells.mural.screens", "Reset"))
        self.reset_btn.setToolTip(tr("grimoire.spells.mural.screens", "Put back what you had before your last Apply"))
        self.reset_btn.setMinimumHeight(34)
        self.reset_btn.clicked.connect(self.reset)
        pl.addWidget(self.reset_btn)
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

    def reload_designs(self, select: list[str] | None = None):
        """Called after a community install/uninstall or an import: rebuild the gallery, keep the selection (or
        select the first of `select`'s ids that's there)."""
        keep = self.current().id if self._designs else None
        self._designs = self.designs()
        ids = {d.id for d in self._designs}
        self._fill(next((i for i in select or () if i in ids), keep))

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
    def _apply(self, _=False, reset: bool = False):
        d, opts, sig = self.current(), self.options(), self._sig
        if d is None:
            self.status.setText(tr("grimoire.spells.mural.screens", "Nothing to apply yet: get one from Community."))
            return
        saved = load_state().get(self.key) or {}
        before = {"design": saved.get("design"), "options": saved.get("options") or {}}
        self._pending = (d, opts, before, reset)
        self._busy(True)
        self.status.setText(self.shown(self.apply_busy) or tr("grimoire.spells.mural.screens", "Applying…"))

        def work():
            try:
                return True, self.apply(d, opts) or tr("grimoire.spells.mural.screens", "Applied ✓")
            except Exception as e:        # anything else would leave the button stuck on "Applying…"
                return False, tr("grimoire.spells.mural.screens", "Couldn't apply: {error}").format(error=e)

        POOL.start(Job(work, lambda result: sig.applied.emit(*result)))

    def _on_applied(self, ok: bool, msg: str):
        self._busy(False)
        self.status.setText(msg)
        if ok:
            d, opts, before, reset = self._pending
            hist = load_history(self.key)
            if reset:                            # that entry is now what's active: the next Reset goes further back
                hist = hist[:-1]
                self.status.setText(tr("grimoire.spells.mural.screens", "Restored ✓  Back to {name}.")
                                    .format(name=isolate(self.shown(d.name))))
            elif before != {"design": d.id, "options": opts}:
                hist.append(before)
            save_history(self.key, hist)
            self.applied = d.id
            save_state(self.key, {"design": d.id, "options": opts})
            self._label_in_use()

    def _busy(self, busy: bool):
        self.apply_btn.setEnabled(not busy)
        self.reset_btn.setEnabled(not busy)

    # ---- reset
    def confirm(self, text: str) -> bool:
        """Ask before Reset changes anything (tests swap this out)."""
        box = QMessageBox(QMessageBox.Icon.Question, tr("grimoire.spells.mural.screens", "Reset"), text,
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, self)
        box.button(QMessageBox.StandardButton.Yes).setText(tr("grimoire.spells.mural.screens", "Reset"))
        box.button(QMessageBox.StandardButton.Cancel).setText(tr("grimoire.spells.mural.screens", "Cancel"))
        box.setTextFormat(Qt.TextFormat.PlainText)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _original_restore(self):
        """The tab's own way back to what you had before MuraL (its "Restore previous …" action), if any."""
        for name in ("restore_original", "_restore"):
            fn = getattr(self, name, None)
            if callable(fn):
                return fn
        return None

    def _design(self, design_id) -> Design | None:
        return next((d for d in self._designs if d.id == design_id), None)

    def _select(self, design_id, opts: dict):
        """Show design + options in the gallery and panel, without applying."""
        self._loading = True
        self.set_options(opts)
        self._loading = False
        ids = [d.id for d in self._designs]
        row = ids.index(design_id) if design_id in ids else 0
        self.gallery.blockSignals(True)
        self.gallery.setCurrentRow(row)
        self.gallery.blockSignals(False)
        self._selected(row, render=False)
        self._rerender()

    def reset(self):
        """Undo the last Apply (see the module docstring)."""
        hist = load_history(self.key)
        if not hist:
            saved = load_state().get(self.key) or {}
            if not self.confirm(tr("grimoire.spells.mural.screens",
                                   "Put this panel back to what's in use now? Changes you haven't applied are lost.")):
                return
            self._select(saved.get("design") or "", saved.get("options") or {})
            self.status.setText(
                tr("grimoire.spells.mural.screens", "Panel reset to what's in use.") if saved.get("design") else
                tr("grimoire.spells.mural.screens", "Panel reset. Nothing was applied yet, so nothing else changed."))
            return
        prev = hist[-1]
        if not prev.get("design"):                     # before the last Apply, MuraL had applied nothing here
            restore = self._original_restore()
            if restore is None:
                if self.confirm(tr("grimoire.spells.mural.screens", "Before your last Apply this was the system's own "
                                        "setting, and this tab can't put that back by itself. Reset "
                                        "the panel to what's in use instead?")):
                    saved = load_state().get(self.key) or {}
                    self._select(saved.get("design") or "", saved.get("options") or {})
                    self.status.setText(tr("grimoire.spells.mural.screens",
                                           "Panel reset. What's applied didn't change."))
                return
            if not self.confirm(tr("grimoire.spells.mural.screens",
                                   "Put back what you had before MuraL changed this?")):
                return
            self._after_background = self._reset_to_original
            restore()
            if self.apply_btn.isEnabled():              # it didn't start anything (nothing to restore)
                self._after_background = None
            return
        design = self._design(prev["design"])
        if design is None:
            self.status.setText(tr("grimoire.spells.mural.screens", "Can't reset: what you had before ({design}) "
                                   "isn't available any more.")
                                .format(design=isolate(prev["design"])))
            return
        if not self.confirm(tr("grimoire.spells.mural.screens", "Go back to {name} as it was before your last Apply?")
                            .format(name=isolate(self.shown(design.name)))):
            return
        self._select(design.id, prev.get("options") or {})
        self._apply(reset=True)

    def _reset_to_original(self, ok: bool):
        if not ok:
            return
        save_history(self.key, load_history(self.key)[:-1])
        saved = load_state().get(self.key) or {}
        self.applied = None
        save_state(self.key, {"design": None, "options": saved.get("options") or {}})
        self._label_in_use()                 # the status line already holds the tab's own "… restored" note

    def background(self, fn, busy: str):
        """Run fn() (returns a status message, raises on failure) on a worker thread, Apply disabled meanwhile."""
        sig = self._sig
        self._busy(True)
        self.status.setText(busy)

        def work():
            try:
                return True, fn()
            except Exception as e:
                return False, tr("grimoire.spells.mural.screens", "Couldn't restore: {error}").format(error=e)

        POOL.start(Job(work, lambda result: sig.finished.emit(*result)))

    def _on_finished(self, ok: bool, msg: str):
        self._busy(False)
        self.status.setText(msg or "")
        after, self._after_background = self._after_background, None
        if after:
            after(ok)

    # ---- import
    def _build_import(self, lay):
        """The Import… row under the big preview, start-aligned (mirrors by itself in right-to-left languages)."""
        from grimoire.spells.mural import imports
        self._importer = imports.importer(self.key)
        if self._importer is None:
            return
        row = QHBoxLayout()
        row.setSpacing(12)
        self.import_btn = QPushButton(tr("grimoire.spells.mural.screens", "Import…"))
        self.import_btn.setToolTip(tr("grimoire.spells.mural.screens", "Add your own: {what}")
                                   .format(what=tr("grimoire.spells.mural.imports", self._importer.what)))
        self.import_btn.clicked.connect(self._import_clicked)
        self.import_msg = QLabel()
        self.import_msg.setObjectName("Muted")
        self.import_msg.setWordWrap(True)
        self.import_msg.setTextFormat(Qt.TextFormat.PlainText)     # quotes file names: never as HTML
        row.addWidget(self.import_btn)
        row.addWidget(self.import_msg, 1)
        lay.addLayout(row)

    def _import_clicked(self):
        imp = self._importer
        if not imp.kind:                                          # pictures only: straight to the file picker
            self._pick_files()
            return
        menu = QMenu(self)
        menu.addAction(tr("grimoire.spells.mural.screens", "From a file…"), self._pick_files)
        menu.addAction(tr("grimoire.spells.mural.screens", "From a folder…"), self._pick_folder)
        menu.exec(self.import_btn.mapToGlobal(self.import_btn.rect().bottomLeft()))

    def _pick_files(self):
        from grimoire.spells.mural import imports
        paths, _ = QFileDialog.getOpenFileNames(self, tr("grimoire.spells.mural.screens", "Import"), "",
                                                imports.name_filter(self._importer))
        if paths:
            self.import_paths(paths)

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, tr("grimoire.spells.mural.screens", "Import a folder"))
        if path:
            self.import_paths([path])

    def import_paths(self, paths: list[str]):
        """Import files/folders on a worker thread; the result lands in _on_imported."""
        from grimoire.spells.mural import imports
        sig, key = self._sig, self.key
        self.import_btn.setEnabled(False)
        self.import_msg.setText(tr("grimoire.spells.mural.screens", "Importing…"))
        POOL.start(Job(lambda: imports.run(key, paths), sig.imported.emit))

    def _on_imported(self, result: dict):
        self.import_btn.setEnabled(True)
        names = [e["name"] for e in result["entries"]] + [n.rsplit(".", 1)[0] for n in result["images"]]
        select = [i for e in result["entries"] for i in (f"store:{e['key']}", e["ident"])]
        select += [f"img:{n}" for n in result["images"]]
        if names:
            self.reload_designs(select)
            bg = getattr(self, "bg", None)         # a tab whose options pick a library picture (Login's Background)
            if result["images"] and isinstance(bg, Choice):
                for n in result["images"]:
                    if bg.findData(n) < 0:
                        bg.insertItem(max(0, bg.count() - 1), n, n)
                bg.set_value(result["images"][-1])
        msgs = []
        if names:
            msgs.append(tr("grimoire.spells.mural.screens", "Imported {names}. Press Apply to use it.")
                        .format(names=", ".join(isolate(n) for n in names)))
        msgs += result["errors"]
        self.import_msg.setText("\n".join(msgs))
