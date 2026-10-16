# SPDX-License-Identifier: GPL-3.0-or-later
"""GlyphL's page in the hub: the same picker as the popup, plus where its hotkey stands."""
from PySide6.QtCore import QObject, QProcess, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from grimoire import hotkeys, i18n, paths
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.glyphl import store
from grimoire.spells.glyphl.picker import Picker


def bound_keys() -> tuple[int, ...] | None:
    """The keys KDE has for GlyphL's hotkey command; None when KDE's shortcut service can't be asked."""
    h = next((h for h in hotkeys.catalog() if h.component == f"grimoire-hotkey-{store.HOTKEY_ID}.desktop"), None)
    if h is None:
        return ()
    try:
        got = (hotkeys.BUS.call(hotkeys.ROOT, hotkeys.IFACE, "shortcut", "as", len(h.id), *h.id) or [[]])[0]
    except hotkeys.HotkeyError:
        return None
    return tuple(k for k in got if k)


def suggested() -> int:
    return next((c[3] for c in hotkeys.COMMANDS if c[0] == store.HOTKEY_ID and len(c) > 3), 0)


class _Signals(QObject):
    keys = Signal(object)


class GlyphLPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.sig = _Signals()
        self.sig.keys.connect(self._keys)
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 22)
        root.setSpacing(16)
        head = QHBoxLayout()
        head.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("GlyphL")
        title.setObjectName("Title")
        titles.addWidget(title)
        intro = QLabel(tr("grimoire.spells.glyphl.page", "Emoji, symbols and every Unicode character, a key away. "
                                                         "Search in your language or by Unicode name, then click to "
                                                         "copy."))
        intro.setObjectName("Subtitle")
        intro.setWordWrap(True)
        titles.addWidget(intro)
        self.hotkey = QLabel()
        self.hotkey.setObjectName("Muted")
        self.hotkey.setWordWrap(True)
        titles.addWidget(self.hotkey)
        head.addLayout(titles, 1)
        self.open_btn = QPushButton(tr("grimoire.spells.glyphl.page", "Open the popup"))
        self.open_btn.setObjectName("Primary")
        self.open_btn.setMinimumHeight(38)
        self.open_btn.setToolTip(tr("grimoire.spells.glyphl.page", "The small picker window your hotkey opens"))
        self.open_btn.clicked.connect(self._open_popup)
        head.addWidget(self.open_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)
        self.picker = Picker(popup=False)
        root.addWidget(self.picker, 1)
        self._set_hotkey_text(())
        POOL.start(Job(bound_keys, self.sig.keys.emit))

    def _set_hotkey_text(self, keys):
        key = suggested()
        if keys:
            self.hotkey.setText(tr("grimoire.spells.glyphl.page", "Press {key} anywhere to open the picker.").format(
                key=i18n.ltr(hotkeys.text(keys[0]))))
        elif key:
            self.hotkey.setText(tr("grimoire.spells.glyphl.page", "No hotkey yet: pick one in Settings → Hotkeys "
                                                                  "({key} is suggested).").format(
                key=i18n.ltr(hotkeys.text(key))))
        else:
            self.hotkey.setText(tr("grimoire.spells.glyphl.page", "No hotkey yet: pick one in Settings → "
                                                                  "Hotkeys."))

    def _keys(self, keys):
        self._set_hotkey_text(keys or ())

    def _open_popup(self):
        QProcess.startDetached(str(paths.command("grimoire-glyphl")), ["show"])
