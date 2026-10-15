# SPDX-License-Identifier: GPL-3.0-or-later
"""WidgetL's page in Grimoire: a preview of each desktop widget (its real face, rendered by preview.py), install or
update them, and add one to the desktop."""
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from grimoire.i18n import tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.widgetl import preview, widgets

PREVIEW_W, PREVIEW_H = 380, 210          # the box each preview is fitted into on its card

# what to say once a widget is on the desktop (whole sentences, ready for translation)
ADDED = {
    "clock": tr_noop("grimoire.spells.widgetl.page",
                     "Clock is on your desktop. Right-click it and choose Configure for seconds or the 12-hour clock."),
    "system": tr_noop("grimoire.spells.widgetl.page",
                      "System is on your desktop. Right-click it and choose Configure for sparklines or Fahrenheit."),
    "weather": tr_noop("grimoire.spells.widgetl.page",
                       "Weather is on your desktop. Right-click it and choose Configure to pick your place."),
    "nowplaying": tr_noop("grimoire.spells.widgetl.page",
                          "Now Playing is on your desktop. It follows whatever app is playing."),
}


def _label(text="", name="", wrap=True) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)      # notes carry kpackagetool6's and plasmashell's messages
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class _Signals(QObject):
    done = Signal(object)          # (what, error text or "", result)


class Card(QFrame):
    """One widget: its preview, what it shows, how many are on the desktop, and Add to desktop."""

    def __init__(self, w: widgets.Widget, add):
        super().__init__()
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 16)
        lay.setSpacing(6)
        self.image = QLabel(tr("grimoire.spells.widgetl.page", "Rendering the preview…"))
        self.image.setObjectName("Muted")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setFixedHeight(PREVIEW_H)
        self.image.setMinimumWidth(240)
        lay.addWidget(self.image)
        lay.addSpacing(8)
        lay.addWidget(_label(tr("grimoire.spells.widgetl.widgets", w.name), "SectionTitle"))
        lay.addWidget(_label(tr("grimoire.spells.widgetl.widgets", w.blurb), "Muted"))
        lay.addStretch(1)
        row = QHBoxLayout()
        self.state = _label("", "Muted", wrap=False)
        row.addWidget(self.state, 1)
        self.add_btn = QPushButton(tr("grimoire.spells.widgetl.page", "Add to desktop"))
        self.add_btn.clicked.connect(lambda: add(w.id))
        row.addWidget(self.add_btn)
        lay.addLayout(row)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_preview(self, path):
        if not path:
            self.image.setText(tr("grimoire.spells.widgetl.page", "No preview"))
            return
        pm = QPixmap(str(path))
        if pm.isNull():
            self.image.setText(tr("grimoire.spells.widgetl.page", "No preview"))
            return
        pm.setDevicePixelRatio(preview.SCALE)
        size = pm.deviceIndependentSize()
        k = min(PREVIEW_W / size.width(), PREVIEW_H / size.height(), 1.0)
        if k < 1.0:
            pm = pm.scaled(int(pm.width() * k), int(pm.height() * k), Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(preview.SCALE)
        self.image.setPixmap(pm)

    def set_state(self, installed: bool, count: int | None):
        if not installed:
            text = tr("grimoire.spells.widgetl.page", "Not installed yet")
        elif count is None:
            text = tr("grimoire.spells.widgetl.page", "Installed")
        elif count == 0:
            text = tr("grimoire.spells.widgetl.page", "Not on your desktop")
        else:
            text = tr("grimoire.spells.widgetl.page", "On your desktop %n time(s)", n=count)
        self.state.setText(text)


class WidgetLPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.sig = _Signals()
        self.sig.done.connect(self._finished)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        lay = QVBoxLayout(inner)
        lay.setContentsMargins(56, 48, 56, 40)
        lay.setSpacing(6)
        lay.addWidget(_label("WidgetL", "PageHeading"))
        lay.addWidget(_label(tr("grimoire.spells.widgetl.page",
                                "Desktop widgets in black and white: a clock with big thin digits, your system's "
                                "readings, the weather for a place you pick, and what's playing. They're Plasma "
                                "widgets, so once they're on the desktop you move, resize and set them up like any "
                                "other."), "Muted"))
        lay.addSpacing(24)

        lay.addWidget(_label(tr("grimoire.spells.widgetl.page", "WIDGETS"), "Section"))
        self.summary = _label("", "")
        lay.addWidget(self.summary)
        row = QHBoxLayout()
        self.install_btn = QPushButton(tr("grimoire.spells.widgetl.page", "Install widgets"))
        self.install_btn.setObjectName("Primary")
        self.install_btn.clicked.connect(self._install)
        row.addWidget(self.install_btn)
        row.addStretch(1)
        lay.addLayout(row)
        self.note = _label("", "Muted")
        lay.addWidget(self.note)
        lay.addSpacing(18)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.cards = {}
        for i, w in enumerate(widgets.WIDGETS):
            card = Card(w, self._add)
            self.cards[w.id] = card
            grid.addWidget(card, i // 2, i % 2)
        lay.addLayout(grid)
        lay.addSpacing(12)
        lay.addWidget(_label(tr("grimoire.spells.widgetl.page",
                                "You can also add them by hand: right-click the desktop, Add or Manage Widgets, "
                                "and search for \"Grimoire\"."), "Muted"))
        lay.addStretch(1)
        self._previews_started = False
        self.refresh()

    # ---- state ----------------------------------------------------------------------------------------------------

    def refresh(self):
        self._busy(True)
        POOL.start(Job(self._read, lambda r: self.sig.done.emit(("read", "", r))))

    @staticmethod
    def _read() -> dict:
        info = {"installed": {w.id: widgets.is_installed(w.id) for w in widgets.WIDGETS}, "updates": widgets.updates()}
        try:
            info["counts"] = widgets.counts(widgets.scan(timeout=8))
        except (RuntimeError, ValueError) as err:
            info["counts"], info["error"] = None, str(err)
        return info

    def _show(self, info: dict):
        installed, updates, counts = info["installed"], info["updates"], info["counts"]
        n, total = sum(installed.values()), len(installed)
        # separate whole sentences, joined by a space
        if n == 0:
            said = [tr("grimoire.spells.widgetl.page", "Not installed yet. Installing adds them to Plasma's "
                       "widget list; nothing appears on your desktop until you add it.")]
        elif n < total:
            said = [tr("grimoire.spells.widgetl.page", "{n} of {total} widgets installed.").format(n=n, total=total)]
        else:
            said = [tr("grimoire.spells.widgetl.page", "All %n widgets installed.", n=total)]
        if updates:
            said.append(tr("grimoire.spells.widgetl.page", "An update is ready."))
        if counts is not None:
            on = sum(counts.values())
            said.append(tr("grimoire.spells.widgetl.page", "None of them is on your desktop yet.") if on == 0 else
                        tr("grimoire.spells.widgetl.page", "%n widget(s) on your desktop.", n=on))
        else:
            said.append(tr("grimoire.spells.widgetl.page",
                           "Plasma isn't answering, so the desktop can't be read right now."))
        self.summary.setText(" ".join(said))
        self.install_btn.setText(tr("grimoire.spells.widgetl.page", "Install widgets") if n == 0
                                 else tr("grimoire.spells.widgetl.page", "Update widgets") if updates or n < total
                                 else tr("grimoire.spells.widgetl.page", "Widgets up to date"))
        self.install_btn.setEnabled(n < total or bool(updates))
        for w in widgets.WIDGETS:
            card = self.cards[w.id]
            card.set_state(installed[w.id], counts[w.id] if counts is not None else None)
            card.add_btn.setEnabled(counts is not None)
        self._busy(False, keep_install=True)

    def _busy(self, on: bool, keep_install: bool = False):
        if not keep_install:
            self.install_btn.setEnabled(not on)
        for card in self.cards.values():
            if on:
                card.add_btn.setEnabled(False)

    def _load_previews(self):
        if self._previews_started:
            return
        self._previews_started = True
        POOL.start(Job(preview.ensure, lambda r: self.sig.done.emit(("preview", r[1], r[0]))))

    # ---- actions --------------------------------------------------------------------------------------------------

    def _start(self, what: str, fn):
        self._busy(True)
        self.note.setText(tr("grimoire.spells.widgetl.page", "Working…"))

        def guarded():
            try:
                return "", fn()
            except Exception as err:      # anything uncaught would leave the buttons off and "Working…" for good
                return str(err) or type(err).__name__, None
        POOL.start(Job(guarded, lambda r: self.sig.done.emit((what, r[0], r[1]))))

    def _install(self):
        self._start("install", widgets.install)

    def _add(self, wid: str):
        self._start("add", lambda: widgets.add(wid))

    def _finished(self, payload):
        what, error, result = payload
        if what == "read":
            self._show(result)
            return
        if what == "preview":
            for wid, path in result.items():
                self.cards[wid].set_preview(path)
            return
        if error:
            failed = {"install": tr("grimoire.spells.widgetl.page", "Couldn't install the widgets: {error}"),
                      "add": tr("grimoire.spells.widgetl.page", "Couldn't add the widget: {error}")}
            self.note.setText(failed.get(what, "{error}").format(error=error))
        elif what == "install":
            self.note.setText(tr("grimoire.spells.widgetl.page", "Widgets installed. Desktops already showing "
                                 "them pick up the new version when Plasma next restarts.") if result
                              else tr("grimoire.spells.widgetl.page", "Everything was already up to date."))
        elif what == "add":
            added = ADDED.get(result["widget"])
            self.note.setText(tr("grimoire.spells.widgetl.page", added) if added else "")
        self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        self._load_previews()
        self.refresh()
