# SPDX-License-Identifier: GPL-3.0-or-later
"""MuraL: everything you look at, in one place. A side menu of sections, each opening a tab.

SCREENS  desktop, lock screen, splash, login, boot
SHELL    taskbar, style, windows, motion
LOOK     colors, icons, fonts, cursor, terminal
SAVED    looks (snapshots of all of the above)
Tabs are built the first time they're opened.
"""
from importlib import import_module

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop

SECTIONS = [
    (tr_noop("grimoire.spells.mural.page", "SCREENS"), [
        (tr_noop("grimoire.spells.mural.page", "Desktop"), "desktop", "desktop", "DesktopTab"),
        (tr_noop("grimoire.spells.mural.page", "Lock screen"), "lock", "lock", "LockTab"),
        (tr_noop("grimoire.spells.mural.page", "Splash"), "splash", "splash", "SplashTab"),
        (tr_noop("grimoire.spells.mural.page", "Login"), "login", "login", "LoginTab"),
        (tr_noop("grimoire.spells.mural.page", "Boot"), "boot", "boot", "BootTab"),
    ]),
    (tr_noop("grimoire.spells.mural.page", "SHELL"), [
        (tr_noop("grimoire.spells.mural.page", "Taskbar"), "taskbar", "taskbar", "TaskbarTab"),
        (tr_noop("grimoire.spells.mural.page", "Style"), "style", "style", "StyleTab"),
        (tr_noop("grimoire.spells.mural.page", "Windows"), "windows", "windows", "WindowsTab"),
        (tr_noop("grimoire.spells.mural.page", "Motion"), "motion", "motion", "MotionTab"),
    ]),
    (tr_noop("grimoire.spells.mural.page", "LOOK"), [
        (tr_noop("grimoire.spells.mural.page", "Colors"), "colors", "colors", "ColorsTab"),
        (tr_noop("grimoire.spells.mural.page", "Icons"), "icons", "icons", "IconsTab"),
        (tr_noop("grimoire.spells.mural.page", "Fonts"), "fonts", "fonts", "FontsTab"),
        (tr_noop("grimoire.spells.mural.page", "Cursor"), "cursor", "cursor", "CursorTab"),
        (tr_noop("grimoire.spells.mural.page", "Terminal"), "terminal", "terminal", "TerminalTab"),
    ]),
    (tr_noop("grimoire.spells.mural.page", "SAVED"), [
        (tr_noop("grimoire.spells.mural.page", "Looks"), "looks", "lookstab", "LooksTab"),
    ]),
]
TABS = [tab for _, tabs in SECTIONS for tab in tabs]


class MuralPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav = QFrame()
        nav.setObjectName("SubNav")
        nav.setFixedWidth(208)
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(14, 30, 14, 20)
        nl.setSpacing(2)
        title = QLabel("MuraL")
        title.setObjectName("Title")
        nl.addWidget(title)
        hint = QLabel(tr("grimoire.spells.mural.page", "Everything you look at"))
        hint.setObjectName("Muted")
        nl.addWidget(hint)
        nl.addSpacing(18)

        self.group = QButtonGroup(self)
        self.stack = QStackedWidget()
        self.built: dict[int, QWidget] = {}
        i = 0
        for section, tabs in SECTIONS:
            label = QLabel(tr("grimoire.spells.mural.page", section))
            label.setObjectName("NavSection")
            nl.addWidget(label)
            for name, icon, _, _ in tabs:
                b = QPushButton(tr("grimoire.spells.mural.page", name))
                b.setObjectName("SubNavItem")
                b.setIcon(glyph(icon))
                b.setIconSize(QSize(18, 18))
                b.setCheckable(True)
                b.clicked.connect(lambda _=False, i=i: self.open_tab(i))
                self.group.addButton(b, i)
                nl.addWidget(b)
                i += 1
            nl.addSpacing(12)
        nl.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedWidth(208)
        scroll.setWidget(nav)
        root.addWidget(scroll)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 22, 0, 0)
        bl.setSpacing(0)
        self.heading = QLabel()
        self.heading.setObjectName("PageHeading")
        self.heading.setContentsMargins(36, 0, 36, 0)      # both sides: right-to-left languages
        bl.addWidget(self.heading)
        bl.addWidget(self.stack, 1)
        root.addWidget(body, 1)
        self.open_tab(0)

    def open_tab(self, i: int):
        name, _, module, cls = TABS[i]
        if i not in self.built:
            self.built[i] = getattr(import_module(f"grimoire.spells.mural.{module}"), cls)()
            self.stack.addWidget(self.built[i])
            if hasattr(self.built[i], "restored"):
                self.built[i].restored.connect(lambda keep=self.built[i]: self._forget_others(keep))
        self.stack.setCurrentWidget(self.built[i])
        self.group.button(i).setChecked(True)
        self.heading.setText(tr("grimoire.spells.mural.page", name))

    def _forget_others(self, keep: QWidget):
        """A look was restored: drop the other built tabs so they're rebuilt showing what's in use now."""
        for i, w in list(self.built.items()):
            if w is not keep:
                self.stack.removeWidget(w)
                w.deleteLater()
                del self.built[i]
