# SPDX-License-Identifier: GPL-3.0-or-later
"""The popup window around the picker: shows on the hotkey, hides on Escape, on the hotkey again, or after a copy
(when "Close after copying" is on)."""
import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from grimoire.spells.glyphl import popup as server
from grimoire.spells.glyphl.picker import SAVER, Picker


class Popup(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.setWindowTitle("GlyphL")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 10)
        self.picker = Picker(popup=True)
        self.picker.copied.connect(self._copied)
        self.picker.escape.connect(self.hide)
        lay.addWidget(self.picker)
        self.resize(760, 560)
        self.setMinimumSize(560, 420)
        self.idle = QTimer(self, singleShot=True, interval=server.IDLE_QUIT_MS, timeout=QApplication.quit)

    def command(self, cmd: str, token: str = ""):
        if token:
            os.environ["XDG_ACTIVATION_TOKEN"] = token     # Qt's Wayland plugin hands it to KWin on activation
        if cmd == "quit":
            QApplication.quit()
        elif cmd == "hide" or cmd == "toggle" and self.isVisible() and self.isActiveWindow():
            self.hide()
        elif cmd in ("show", "toggle"):
            self.present()

    def present(self):
        if not self.isVisible():
            self.picker.reset()
        self.idle.stop()
        self.show()
        self.raise_()
        self.activateWindow()
        self.picker.search.setFocus()

    def _copied(self, _text: str):
        if self.picker.s["close"]:
            QTimer.singleShot(60, self.hide)               # let the compositor take the clipboard offer first

    def closeEvent(self, e):
        e.ignore()                                         # the window's ✕ hides it; the process stays for next time
        self.hide()

    def hideEvent(self, e):
        self.idle.start()
        super().hideEvent(e)

    def finish(self):
        SAVER.waitForDone(2000)
