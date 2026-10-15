# SPDX-License-Identifier: GPL-3.0-or-later
"""Taking another shot from any ShotL window: the New button (its main part repeats the last mode, its menu offers
every mode and the delay) and the round trip behind it, shared by the hub page and the editor window the hotkeys
open: hide ShotL, wait for the delay, grab, show it again."""
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QPushButton, QToolButton

from grimoire import i18n
from grimoire.i18n import tr, tr_noop
from grimoire.spells.shotl import capture, shots
from grimoire.spells.shotl.icons import solid

MODES = {"region": tr_noop("grimoire.spells.shotl.newshot", "Region"),           # tr() where shown
         "window": tr_noop("grimoire.spells.shotl.newshot", "Window"),
         "full": tr_noop("grimoire.spells.shotl.newshot", "All screens"),
         "screen": tr_noop("grimoire.spells.shotl.newshot", "Screen under the pointer")}
DELAYS = [0, 3, 5, 10]
HIDE_MS = 450                                  # time for our window to leave the screen before the grab


def mode_name(mode: str) -> str:
    return tr("grimoire.spells.shotl.newshot", MODES[mode])


def last_mode() -> str:
    mode = shots.load()["new_mode"]
    return mode if mode in MODES else "region"


def still(mode: str, pointer=False, screen=None):
    """One still as a QImage, or None when the region picker was cancelled. mode: region, window, full, screen, or
    monitor (the QScreen `screen`, cut from a full grab). Raises capture.CaptureError."""
    from grimoire.spells.shotl import region
    img = capture.take(capture.grab("full" if mode in ("region", "monitor") else mode,
                                    pointer=pointer and mode != "region"))
    if mode == "region":
        rect = region.pick(img)
        return img.copy(rect) if rect else None
    if mode == "monitor":
        return img.copy(capture.screen_rect(img, screen))
    return img


def run(win, mode: str, done, fail, screen=None):
    """Hide `win`, wait for it (and the delay) to clear the screen, grab, show `win` again, then done(QImage) — or
    fail(message). A cancelled region calls neither."""
    if not capture.backend():
        fail(tr("grimoire.spells.shotl.newshot", "No screenshot tool found: install Spectacle ({command})")
             .format(command="sudo apt install kde-spectacle"))
        return
    settings = shots.load()
    win.hide()

    def go():
        img = None
        try:
            img = still(mode, settings["pointer"], screen)
        except capture.CaptureError as e:
            fail(str(e))
        finally:                               # whatever happened, never leave ShotL hidden
            win.show()
            win.raise_()
            win.activateWindow()
        if img is not None and not img.isNull():
            done(img)

    QTimer.singleShot(HIDE_MS + int(settings["delay"]) * 1000, go)


class NewButton(QFrame):
    """A split button: "New" takes a shot in the last mode used; the arrow picks a mode (remembered) or the delay."""
    requested = Signal(str)                    # a mode from MODES
    delay_changed = Signal(int)

    def __init__(self, text: str, primary=False):
        super().__init__()
        self.setObjectName("NewShot")
        fg, bg, hover, line = (("#000000", "#f2f2f2", "#ffffff", "#9a9a9a") if primary
                               else ("#f2f2f2", "#0c0c0c", "#1a1a1a", "#3a3a3a"))
        edge = "right" if i18n.rtl() else "left"           # the divider sits between the two parts on screen
        self.setStyleSheet(
            f"QFrame#NewShot {{ background: {bg}; border: 1px solid {fg if not primary else bg}; "
            f"border-radius: 8px; }}"
            f"QFrame#NewShot QPushButton, QFrame#NewShot QToolButton {{ background: transparent; color: {fg}; "
            f"border: none; border-radius: 7px; font-weight: 600; padding: 6px 12px; }}"
            f"QFrame#NewShot QToolButton {{ padding: 6px 6px; border-radius: 0; border-{edge}: 1px solid {line}; }}"
            f"QFrame#NewShot QPushButton:hover, QFrame#NewShot QToolButton:hover {{ background: {hover}; }}"
            f"QFrame#NewShot QToolButton::menu-indicator {{ image: none; width: 0; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        lay.setSpacing(0)
        self.main = QPushButton(text)
        self.main.setIcon(solid("new", fg, 16))
        self.main.setIconSize(QSize(16, 16))
        self.main.setCursor(Qt.CursorShape.PointingHandCursor)
        self.main.clicked.connect(self.trigger)
        self.more = QToolButton()
        self.more.setIcon(solid("chevron", fg, 16))
        self.more.setIconSize(QSize(16, 16))
        self.more.setToolTip(tr("grimoire.spells.shotl.newshot", "Pick what to capture"))
        self.more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu = QMenu(self)
        self._sub = None
        self.menu.aboutToShow.connect(self._fill)
        self.more.setMenu(self.menu)
        lay.addWidget(self.main)
        lay.addWidget(self.more)
        self._tip()

    def _tip(self):
        self.main.setToolTip(tr("grimoire.spells.shotl.newshot", "New screenshot: {mode}  (Ctrl+N)")
                             .format(mode=mode_name(last_mode())))

    def showEvent(self, e):
        super().showEvent(e)
        self._tip()                            # another ShotL button may have changed the mode

    def trigger(self):
        self.requested.emit(last_mode())

    def _fill(self):
        m = self.menu
        m.clear()
        if self._sub is not None:              # clear() keeps submenus: drop the last one
            self._sub.deleteLater()
        current = last_mode()
        group = QActionGroup(m)
        for mode in MODES:
            a = m.addAction(mode_name(mode), lambda md=mode: self.pick(md))     # no icon: it would hide the check
            a.setCheckable(True)
            a.setChecked(mode == current)
            group.addAction(a)
        m.addSeparator()
        sub = QMenu(tr("grimoire.spells.shotl.newshot", "Delay"), m)   # parented: PySide drops addMenu(title)'s
        m.addMenu(sub)
        self._sub = sub
        delay = shots.load()["delay"]
        group = QActionGroup(sub)
        for d in DELAYS:
            a = sub.addAction(tr("grimoire.spells.shotl.newshot", "{n} s", "seconds").format(n=d) if d
                              else tr("grimoire.spells.shotl.newshot", "Off", "no delay"),
                              lambda v=d: self._delay(v))
            a.setCheckable(True)
            a.setChecked(d == delay)
            group.addAction(a)

    def pick(self, mode: str):
        shots.update(new_mode=mode)
        self._tip()
        self.requested.emit(mode)

    def _delay(self, d: int):
        shots.update(delay=d)
        self.delay_changed.emit(d)
