# SPDX-License-Identifier: GPL-3.0-or-later
"""Grimoire hub window: a slim icon rail on the left, a home page of spells, one page per spell."""
import sys
import threading
from datetime import datetime
from types import SimpleNamespace

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout,
                               QWidget)

from grimoire import NAME, i18n, standalone
from grimoire.glyphs import clover, glyph
from grimoire.i18n import tr
from grimoire.paths import ASSETS
from grimoire.settingsview import SettingsPage
from grimoire.spells import SPELLS
from grimoire.theme import FONT, QSS
from grimoire.updateview import Banner, Updater, VersionButton, WhatsNew


def spaced(text: str, size: int, spacing: float, weight=QFont.Weight.DemiBold) -> QLabel:
    label = QLabel(text)
    font = QFont(FONT, size, weight)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, i18n.spacing(text, spacing))
    label.setFont(font)
    return label


class InstallButton(QPushButton):
    """Top-right of a spell card: installs the spell as its own app in the menu; once installed it reads
    "Installed" and offers "Uninstall" on hover."""
    def __init__(self, spell):
        super().__init__()
        self.setObjectName("Pill")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.spell = spell
        self.clicked.connect(self._toggle)
        self._show(False)

    def _show(self, hover: bool):
        on = standalone.installed(self.spell.id)
        self.setProperty("on", on)
        self.setText((tr("grimoire.app", "Uninstall") if hover else tr("grimoire.app", "Installed")) if on
                     else tr("grimoire.app", "Install"))
        self.setToolTip((tr("grimoire.app", "Remove {name} as its own app in the app menu") if on
                         else tr("grimoire.app", "Add {name} as its own app in the app menu")).format(
                             name=self.spell.name))
        self.style().unpolish(self)
        self.style().polish(self)

    def enterEvent(self, e):
        self._show(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._show(False)
        super().leaveEvent(e)

    def _toggle(self):
        sid = self.spell.id
        try:
            if not standalone.installed(sid):
                standalone.install(sid)
            elif sid != "vaultl" or QMessageBox.question(
                    self, tr("grimoire.app", "Uninstall VaultL"),
                    tr("grimoire.app", "Remove VaultL from the app menu? If it's your default file manager, "
                       "folders will open in another one until you install it again.")) \
                    == QMessageBox.StandardButton.Yes:
                standalone.uninstall(sid)
        except (OSError, ValueError) as err:
            QMessageBox.warning(self, self.spell.name,
                                tr("grimoire.app", "Couldn't change the launcher: {err}").format(err=err))
        self._show(self.underMouse())


class SpellCard(QFrame):
    status_ready = Signal(str)

    def __init__(self, spell, on_open):
        super().__init__()
        self.setObjectName("Card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(360, 190)
        self._on_open = on_open
        self.spell = spell
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(6)
        top = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(glyph(spell.icon, 28).pixmap(28, 28, QIcon.Mode.Active))
        top.addWidget(icon)
        top.addSpacing(8)
        top.addWidget(spaced(spell.name.upper(), 14, 4))
        top.addStretch(1)
        if standalone.available(spell.id):
            top.addWidget(InstallButton(spell))
        lay.addLayout(top)
        tag = QLabel(tr("grimoire.spells", spell.tagline))
        tag.setObjectName("Muted")
        tag.setWordWrap(True)
        lay.addWidget(tag)
        lay.addStretch(1)
        self.status = QLabel()
        self.status.setObjectName("Status")
        self.status.setTextFormat(Qt.TextFormat.PlainText)   # Wi-Fi, phone, device and game names: never markup
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self._reading = False
        self.status_ready.connect(self._show_status)
        self.refresh()

    def refresh(self):
        """Reads the status line on a daemon thread: some ask Plasma, PipeWire or KDE Connect, and with every card
        read on the UI thread the hub froze for a second or more at start and on each visit home (a daemon, so a
        line that never answers can't hold up quitting either)."""
        if self._reading:
            return
        self._reading = True
        status, emit = self.spell.status, self.status_ready.emit

        def work():
            try:
                text = status()
            except Exception:      # a status line must never break the home page
                text = ""
            try:
                emit(text if isinstance(text, str) else "")
            except RuntimeError:   # the card is gone
                pass
        threading.Thread(target=work, name=f"status-{self.spell.id}", daemon=True).start()

    def _show_status(self, text: str):
        self._reading = False
        self.status.setText(text)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._on_open()


class TrayToggle(QCheckBox):
    """Opt-in: Grimoire's tray icon at login. Turning it on also starts the tray now."""
    def __init__(self):
        from grimoire import tray
        super().__init__(tr("grimoire.app", "Tray icon at login"))
        self.setToolTip(tr("grimoire.app", "Live CPU and RAM in the system tray, plus crosshair, tidy Downloads, "
                           "performance mode and every spell in its menu"))
        self.setChecked(tray.autostart_on())
        self.toggled.connect(self._set)

    def _set(self, on: bool):
        from grimoire import tray
        try:
            tray.set_autostart(on)
            if on and not tray.running():
                tray.launch("grimoire-tray")
        except OSError as err:
            QMessageBox.warning(self, tr("grimoire.app", "Tray icon"),
                                tr("grimoire.app", "Couldn't change it: {err}").format(err=err))


class Home(QWidget):
    def __init__(self, open_spell, banner: QWidget):
        super().__init__()
        self.setObjectName("Page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(56, 52, 56, 44)
        lay.setSpacing(4)
        lay.addWidget(banner)                    # hidden unless an update is waiting
        hour = datetime.now().hour
        greeting = tr("grimoire.app", "Good morning") if hour < 12 else tr("grimoire.app", "Good afternoon") \
            if hour < 18 else tr("grimoire.app", "Good evening")
        hello = QLabel(greeting)
        hello.setObjectName("Hero")
        lay.addWidget(hello)
        sub = QLabel(tr("grimoire.app", "Your spells. Personal tools for this machine, all in black and white."))
        sub.setObjectName("Muted")
        lay.addWidget(sub)
        lay.addSpacing(14)
        lay.addWidget(TrayToggle())
        lay.addSpacing(20)
        lay.addWidget(spaced(tr("grimoire.app", "SPELLS"), 10, 4))
        lay.addSpacing(10)

        self.grid = grid = QGridLayout()
        grid.setSpacing(16)
        self.cards = [SpellCard(s, lambda s=s: open_spell(s.id)) for s in SPELLS]
        self.soon = soon = QFrame()
        soon.setObjectName("CardSoon")
        soon.setMinimumSize(360, 190)
        sl = QVBoxLayout(soon)
        sl.setContentsMargins(24, 22, 24, 20)
        t = QLabel(tr("grimoire.app", "Next spell"))
        t.setObjectName("Muted")
        sl.addWidget(t)
        sl.addStretch(1)
        self.arrange(set())
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        from grimoire.aboutview import AboutSection
        lay.addWidget(AboutSection())            # About this PC, under the spells
        lay.addStretch(1)

    def arrange(self, hidden: set):
        """Lay out the cards of the spells not hidden in Settings (or the setup)."""
        shown = [c for c in self.cards if c.spell.id not in hidden] + [self.soon]
        for c in self.cards + [self.soon]:
            self.grid.removeWidget(c)
            c.setVisible(c in shown)
        for i, card in enumerate(shown):
            self.grid.addWidget(card, i // 2, i % 2)

    def showEvent(self, e):
        super().showEvent(e)
        for c in self.cards:
            if c.isVisible():
                c.refresh()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(NAME)
        self.resize(1440, 880)
        self.setMinimumSize(1100, 680)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        rail = QWidget()
        rail.setObjectName("Rail")
        rail.setFixedWidth(72)
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(0, 22, 0, 16)
        rl.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(clover(34))
        logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo.setToolTip(NAME)
        rl.addWidget(logo)
        rl.addSpacing(14)
        # home + one button per spell scroll (a thin bar when they don't fit, e.g. the minimum window height);
        # the account, Settings and the version stay pinned at the foot
        self.rail_scroll = scroll = QScrollArea()
        scroll.setObjectName("RailScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        spells = QWidget()
        spells.setObjectName("RailSpells")
        sl = QVBoxLayout(spells)
        sl.setContentsMargins(0, 8, 0, 8)
        sl.setSpacing(8)
        scroll.setWidget(spells)
        rl.addWidget(scroll, 1)

        self.updater = Updater(self)
        self._whatsnew = None
        self.stack = QStackedWidget()
        self.nav = QButtonGroup(self)
        self.pages: dict[str, tuple] = {}
        home = QScrollArea()                     # scrolls once there are more spell cards than fit
        home.setWidgetResizable(True)
        from grimoire.accountview import AutoSync, GuestBar
        top = QWidget()                          # the update banner and, for a guest, the guest bar
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(10)
        tl.addWidget(Banner(self.updater, self.whats_new))
        tl.addWidget(GuestBar())
        self.home = Home(self.open, top)
        home.setWidget(self.home)
        self._add_page("home", tr("grimoire.app", "Home"), "home", home, sl)
        for spell in SPELLS:
            self._add_page(spell.id, spell.name, spell.icon, None, sl, spell)
        sl.addStretch(1)
        rl.addSpacing(8)
        account = QPushButton()                  # your account: opens Settings → Account
        account.setObjectName("RailItem")
        account.setIcon(glyph("login", 22))
        account.setIconSize(QSize(22, 22))
        account.setFixedSize(48, 48)
        account.setToolTip(self._who())
        account.clicked.connect(lambda: (self.open("settings"), self.pages["settings"][1].show_section("profile")))
        rl.addWidget(account, 0, Qt.AlignmentFlag.AlignHCenter)
        self._add_page("settings", tr("grimoire.app", "Settings"), "gear", None, rl,
                       SimpleNamespace(page=lambda: SettingsPage(self.updater, self.whats_new)))
        rl.addWidget(VersionButton(self.updater, self.whats_new), 0, Qt.AlignmentFlag.AlignHCenter)

        root.addWidget(rail)
        root.addWidget(self.stack, 1)
        self.open("home")
        self.refresh_spells()
        self.updater.start()
        self.sync = AutoSync(self)

    @staticmethod
    def _who() -> str:
        from grimoire import session
        who = session.active()
        if who is None or who.guest:
            return tr("grimoire.app", "Guest: settings won't be kept")
        return tr("grimoire.app", "Signed in as {name}").format(name=who.username or tr("grimoire.app", "you"))

    def refresh_spells(self):
        """Show only the spells picked in setup/Settings, in the rail and on the home page."""
        from grimoire import prefs
        hidden = set(prefs.load()["hidden_spells"])
        for spell in SPELLS:
            self.pages[spell.id][0].setVisible(spell.id not in hidden)
        self.home.arrange(hidden)

    def whats_new(self):
        """The What's new panel (also 'Check for updates'); one per window, kept while it lives."""
        if self._whatsnew is None:
            self._whatsnew = WhatsNew(self.updater, self)
        self._whatsnew.show()
        self._whatsnew.raise_()
        self._whatsnew.activateWindow()

    def _add_page(self, pid, label, icon, widget, rail_layout, spell=None):
        btn = QPushButton()
        btn.setObjectName("RailItem")
        btn.setIcon(glyph(icon, 22))
        btn.setIconSize(QSize(22, 22))
        btn.setFixedSize(48, 48)
        btn.setToolTip(label)
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self.open(pid))
        self.nav.addButton(btn)
        rail_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self.pages[pid] = (btn, widget, spell)

    def open(self, pid: str):
        btn, widget, spell = self.pages[pid]
        if widget is None:                       # spells are built on first open
            widget = spell.page()
            self.pages[pid] = (btn, widget, spell)
        if self.stack.indexOf(widget) < 0:
            self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        btn.setChecked(True)
        if btn.parentWidget() is self.rail_scroll.widget():     # after the rail is laid out (open() may run first)
            QTimer.singleShot(0, lambda: self.rail_scroll.ensureWidgetVisible(btn, 0, 8))


def style_app(app: QApplication):
    """Grimoire's black & white look and the chosen language (also used by standalone spells, the tray and every
    other window that makes a QApplication)."""
    i18n.install(app)
    app.setWindowIcon(QIcon(str(ASSETS / "clover5.svg")))
    app.setStyle("Fusion")
    app.setFont(QFont(FONT, 10))
    pal = app.palette()                      # monochrome highlight (Qt's default is blue)
    for role, color in ((QPalette.ColorRole.Highlight, "#2a2a2a"), (QPalette.ColorRole.HighlightedText, "#ffffff"),
                        (QPalette.ColorRole.Window, "#0b0b0b"), (QPalette.ColorRole.Base, "#121212"),
                        (QPalette.ColorRole.Text, "#e8e8e8"), (QPalette.ColorRole.WindowText, "#e8e8e8"),
                        (QPalette.ColorRole.Button, "#121212"), (QPalette.ColorRole.ButtonText, "#e8e8e8")):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    app.setStyleSheet(i18n.qss(QSS) + (i18n.URDU_QSS if i18n.loaded() == "ur" else "")
                      + (i18n.RTL_QSS if i18n.rtl(i18n.loaded()) else ""))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(NAME)
    app.setDesktopFileName("grimoire")
    style_app(app)
    from grimoire.loginview import gate
    if not gate(wizard=True):                # signs in (or guest) before any spell reads its settings
        sys.exit(0)
    win = Window()
    start = sys.argv[1] if len(sys.argv) > 1 else "home"
    start = {"filel": "vaultl", "tidyl": "vaultl"}.get(start, start)     # old menu actions from before the merge
    win.open(start if start in win.pages else "home")
    win.show()
    sys.exit(app.exec())
