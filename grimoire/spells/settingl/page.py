# SPDX-License-Identifier: GPL-3.0-or-later
"""SettingL: KDE's System Settings in black and white. A side menu of native pages (each built the first time it's
opened), a search over them and every KDE module (Ctrl+F), and a page listing all of KDE's modules.

Native pages write KDE's real settings through KDE's own tools (kde.py); anything they don't cover opens KDE's own
module. SettingL never makes itself the default settings app.
"""

from importlib import import_module

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from grimoire import i18n
from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.settingl import kcms
from grimoire.spells.settingl.common import label
from grimoire.widgets import plain_tip

CTX = "grimoire.spells.settingl.page"
# id, name, glyph, module, class, search words (translated, plus the English ones), KDE modules it covers
PAGES = [
    (
        tr_noop("grimoire.spells.settingl.page", "DEVICES"),
        [
            (
                "displays",
                tr_noop("grimoire.spells.settingl.page", "Displays"),
                "desktop",
                "displayview",
                "DisplaysPanel",
                tr_noop(
                    "grimoire.spells.settingl.page",
                    "screen monitor resolution refresh rate hz scale scaling zoom arrange primary rotate "
                    "orientation portrait night light blue light warm color temperature",
                ),
                ["kcm_kscreen", "kcm_nightlight"],
            ),
            (
                "sound",
                tr_noop("grimoire.spells.settingl.page", "Sound"),
                "audio",
                "linkview",
                "SoundPanel",
                tr_noop(
                    "grimoire.spells.settingl.page",
                    "audio volume speakers headphones microphone mic output input default device mute",
                ),
                ["kcm_pulseaudio"],
            ),
            (
                "network",
                tr_noop("grimoire.spells.settingl.page", "Network"),
                "wifi",
                "linkview",
                "NetworkPanel",
                tr_noop(
                    "grimoire.spells.settingl.page",
                    "wifi wi-fi wireless internet vpn airplane mode flight ethernet wired connection hotspot",
                ),
                ["kcm_networkmanagement"],
            ),
            (
                "bluetooth",
                tr_noop("grimoire.spells.settingl.page", "Bluetooth"),
                "bluetooth",
                "deviceview",
                "BluetoothPanel",
                tr_noop(
                    "grimoire.spells.settingl.page",
                    "bluetooth wireless headphones headset speaker pair connect devices",
                ),
                ["kcm_bluetooth"],
            ),
            (
                "mouse",
                tr_noop("grimoire.spells.settingl.page", "Mouse & touchpad"),
                "mouse",
                "deviceview",
                "PointerPanel",
                tr_noop(
                    "grimoire.spells.settingl.page",
                    "mouse touchpad trackpad pointer speed acceleration sensitivity natural scrolling left handed "
                    "tap to click scroll",
                ),
                ["kcm_mouse", "kcm_touchpad"],
            ),
            (
                "keyboard",
                tr_noop("grimoire.spells.settingl.page", "Keyboard"),
                "keyboard",
                "deviceview",
                "KeyboardPanel",
                tr_noop("grimoire.spells.settingl.page", "keyboard layout input language typing key repeat delay rate"),
                ["kcm_keyboard"],
            ),
            (
                "power",
                tr_noop("grimoire.spells.settingl.page", "Power"),
                "boot",
                "deviceview",
                "PowerPanel",
                tr_noop(
                    "grimoire.spells.settingl.page",
                    "power energy battery profile performance balanced power saver sleep suspend screen off "
                    "dim timeout idle",
                ),
                ["kcm_powerdevilprofilesconfig"],
            ),
        ],
    ),
    (
        tr_noop("grimoire.spells.settingl.page", "SYSTEM"),
        [
            (
                "datetime",
                tr_noop("grimoire.spells.settingl.page", "Date & time"),
                "clock",
                "systemview",
                "DateTimePanel",
                tr_noop(
                    "grimoire.spells.settingl.page", "date time clock time zone timezone ntp automatic internet time"
                ),
                ["kcm_clock"],
            ),
            (
                "region",
                tr_noop("grimoire.spells.settingl.page", "Language & region"),
                "globe",
                "systemview",
                "RegionPanel",
                tr_noop("grimoire.spells.settingl.page", "language region locale formats numbers currency translation"),
                ["kcm_regionandlang"],
            ),
            (
                "users",
                tr_noop("grimoire.spells.settingl.page", "Users"),
                "login",
                "systemview",
                "UsersPanel",
                tr_noop(
                    "grimoire.spells.settingl.page",
                    "users account accounts user name password picture avatar administrator",
                ),
                ["kcm_users"],
            ),
            (
                "defaults",
                tr_noop("grimoire.spells.settingl.page", "Default apps"),
                "grid",
                "systemview",
                "DefaultsPanel",
                tr_noop(
                    "grimoire.spells.settingl.page",
                    "default applications apps browser email mail file manager terminal text editor pictures "
                    "music video pdf open with",
                ),
                ["kcm_componentchooser"],
            ),
            (
                "notifications",
                tr_noop("grimoire.spells.settingl.page", "Notifications"),
                "bell",
                "systemview",
                "NotificationsPanel",
                tr_noop(
                    "grimoire.spells.settingl.page", "notifications do not disturb dnd popups history alerts quiet"
                ),
                ["kcm_notifications"],
            ),
            (
                "about",
                tr_noop("grimoire.spells.settingl.page", "About this PC"),
                "info",
                "systemview",
                "AboutPanel",
                tr_noop(
                    "grimoire.spells.settingl.page",
                    "about system information computer hardware processor cpu memory ram graphics gpu version "
                    "kernel plasma",
                ),
                [],
            ),
        ],
    ),
    (
        tr_noop("grimoire.spells.settingl.page", "GRIMOIRE"),
        [
            (
                "appearance",
                tr_noop("grimoire.spells.settingl.page", "Appearance"),
                "mural",
                "linkview",
                "AppearancePanel",
                tr_noop(
                    "grimoire.spells.settingl.page",
                    "appearance theme look wallpaper colors icons fonts cursor style panel taskbar splash lock "
                    "screen login",
                ),
                ["kcm_lookandfeel"],
            ),
            (
                "startup",
                tr_noop("grimoire.spells.settingl.page", "Startup apps"),
                "splash",
                "linkview",
                "StartupPanel",
                tr_noop("grimoire.spells.settingl.page", "startup autostart login apps services boot"),
                ["kcm_autostart"],
            ),
            (
                "updates",
                tr_noop("grimoire.spells.settingl.page", "Updates"),
                "updatel",
                "linkview",
                "UpdatesPanel",
                tr_noop("grimoire.spells.settingl.page", "updates upgrade software packages flatpak snap firmware"),
                ["kcm_updates"],
            ),
        ],
    ),
    (
        tr_noop("grimoire.spells.settingl.page", "KDE"),
        [
            (
                "kde",
                tr_noop("grimoire.spells.settingl.page", "All KDE settings"),
                "list",
                "linkview",
                "KdePanel",
                tr_noop("grimoire.spells.settingl.page", "kde system settings modules everything more advanced"),
                [],
            )
        ],
    ),
]
FLAT = [p for _, pages in PAGES for p in pages]


class _Sig(QObject):
    acted = Signal(object)
    modules = Signal(object)


class SettingLPage(QWidget):
    modules_ready = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.modules: list[dict] | None = None
        self.sig = _Sig()
        self.sig.acted.connect(self._acted)
        self.sig.modules.connect(self._modules)
        POOL.start(Job(lambda: kcms.scan(), self.sig.modules.emit))

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        nav = QFrame()
        nav.setObjectName("SubNav")
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(12, 26, 12, 16)
        nl.setSpacing(2)
        nl.addWidget(label("SettingL", "Title"))
        nl.addSpacing(10)
        self.find = QLineEdit()
        self.find.setPlaceholderText(tr("grimoire.spells.settingl.page", "Search settings"))
        self.find.setClearButtonEnabled(True)
        self.find.addAction(glyph("search", 16), QLineEdit.ActionPosition.LeadingPosition)
        self.find.setToolTip(
            tr("grimoire.spells.settingl.page", "Searches these pages and every KDE settings module (Ctrl+F)")
        )
        self.find.textChanged.connect(self._search)
        self.find.returnPressed.connect(self._open_first)
        self.find.installEventFilter(self)
        nl.addWidget(self.find)
        nl.addSpacing(10)
        self.nav: dict[str, QPushButton] = {}
        for section, pages in PAGES:
            nl.addWidget(label(tr("grimoire.spells.settingl.page", section), "NavSection"))
            for pid, name, icon, *_ in pages:
                b = QPushButton(glyph(icon, 18), "  " + tr("grimoire.spells.settingl.page", name).replace("&", "&&"))
                b.setObjectName("SubNavItem")
                b.setCheckable(True)
                b.setIconSize(QSize(18, 18))
                b.clicked.connect(lambda _=False, p=pid: self.show_page(p))
                nl.addWidget(b)
                self.nav[pid] = b
            nl.addSpacing(8)
        nl.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(nav)
        scroll.setMinimumWidth(230)  # grows for longer names in other languages
        scroll.setMaximumWidth(300)
        root.addWidget(scroll)

        right = QVBoxLayout()
        right.setContentsMargins(32, 26, 32, 18)
        right.setSpacing(14)
        self.heading = label("", "PageHeading")
        right.addWidget(self.heading)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        self.results = QListWidget()
        self.results.setObjectName("Plain")
        self.results.itemActivated.connect(self._open_result)
        self.results.itemClicked.connect(self._open_result)
        self.stack.addWidget(self.results)
        self.toast = label("", "Toast", wrap=True, plain=True)
        self.toast.hide()
        right.addWidget(self.toast)
        self._toast_timer = QTimer(self, singleShot=True, interval=7000, timeout=self.toast.hide)
        root.addLayout(right, 1)

        self.built: dict[str, QWidget] = {}
        self.current = ""
        QShortcut(QKeySequence.StandardKey.Find, self, activated=self._focus_find)
        self.show_page("displays")

    # ------------------------------------------------------------ pages
    def show_page(self, pid: str):
        spec = next(p for p in FLAT if p[0] == pid)
        if pid not in self.built:
            cls = getattr(import_module(f"grimoire.spells.settingl.{spec[3]}"), spec[4])
            try:
                self.built[pid] = cls(self)
            except ImportError as e:  # a spell it borrows from is missing a module
                w = label(
                    tr("grimoire.spells.settingl.page", "This page can't open: {error}").format(error=e),
                    "Muted",
                    wrap=True,
                )
                w.setAlignment(Qt.AlignmentFlag.AlignTop)
                self.built[pid] = w
            self.stack.addWidget(self.built[pid])
        self.current = pid
        for p, b in self.nav.items():
            b.setChecked(p == pid)
        self.heading.setText(tr("grimoire.spells.settingl.page", spec[1]))
        if self.find.text():
            self.find.blockSignals(True)
            self.find.clear()
            self.find.blockSignals(False)
        self.stack.setCurrentWidget(self.built[pid])

    def _focus_find(self):
        self.find.setFocus()
        self.find.selectAll()

    # ------------------------------------------------------------ KDE's modules
    def _modules(self, mods):
        self.modules = mods or []
        self.modules_ready.emit()
        if self.find.text():
            self._search(self.find.text())

    def open_module(self, mid: str):
        m = next((x for x in self.modules or [] if x["id"] == mid), None) or mid
        name = m["name"] if isinstance(m, dict) else mid
        self.act(name, lambda: kcms.open_module(m) or tr("grimoire.spells.settingl.page", "opening in KDE's settings"))

    # ------------------------------------------------------------ search
    def search(self, text: str) -> list[tuple]:
        """[(kind, id, title, subtitle)] best first: native pages, then KDE's modules."""
        words = [w for w in text.casefold().split() if w]
        if not words:
            return []
        hits = []
        for pid, name, icon, _, _, keys, mods in FLAT:
            names = (tr("grimoire.spells.settingl.page", name).casefold(), name.casefold())
            hay = " ".join((tr("grimoire.spells.settingl.page", keys), keys)).casefold()
            score = 0
            for w in words:
                if any(n.startswith(w) for n in names):
                    score += 30
                elif any(w in n for n in names):
                    score += 20
                elif w in hay:
                    score += 22  # a feature of this page: before KDE's module names
                else:
                    score = 0
                    break
            if score:
                hits.append((score + 5, "page", pid, tr("grimoire.spells.settingl.page", name), icon))
        native = {m for p in FLAT if any(h[2] == p[0] for h in hits) for m in p[6]}
        for m in kcms.search(self.modules or [], text)[:40]:
            if m["id"] in native:
                continue  # its native page is already listed
            hits.append((kcms.score(m, words), "kcm", m["id"], m["name"], m.get("category_name") or m["description"]))
        hits.sort(key=lambda h: (-h[0], h[1] != "page"))
        return [h[1:] for h in hits]

    def _search(self, text: str):
        if not text.strip():
            self.stack.setCurrentWidget(self.built.get(self.current, self.results))
            spec = next(p for p in FLAT if p[0] == self.current)
            self.heading.setText(tr("grimoire.spells.settingl.page", spec[1]))
            for p, b in self.nav.items():
                b.setChecked(p == self.current)
            return
        for b in self.nav.values():
            b.setChecked(False)
        self.heading.setText(tr("grimoire.spells.settingl.page", "Search"))
        self.results.clear()
        hits = self.search(text)
        for kind, hid, title, extra in hits:
            if kind == "page":
                it = QListWidgetItem(glyph(extra, 20), "  " + title)
                it.setToolTip(tr("grimoire.spells.settingl.page", "A SettingL page"))
            else:
                it = QListWidgetItem(
                    glyph("forward", 20),
                    "  "
                    + (
                        tr("grimoire.spells.settingl.page", "{module} — in KDE's settings").format(
                            module=i18n.isolate(title)
                        )
                    ),
                )
                it.setToolTip(plain_tip(extra))
            it.setData(Qt.ItemDataRole.UserRole, (kind, hid))
            self.results.addItem(it)
        if not hits:
            it = QListWidgetItem(
                tr(
                    "grimoire.spells.settingl.page",
                    "Nothing matches. The list of all KDE settings is under KDE in the menu.",
                )
                if self.modules is not None
                else tr("grimoire.spells.settingl.page", "Reading KDE's modules…")
            )
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(it)
        else:
            self.results.setCurrentRow(0)
        self.stack.setCurrentWidget(self.results)

    def _open_result(self, it: QListWidgetItem):
        data = it.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, hid = data
        if kind == "page":
            self.show_page(hid)
        else:
            self.open_module(hid)

    def _open_first(self):
        it = self.results.currentItem() or self.results.item(0)
        if it and self.stack.currentWidget() is self.results:
            self._open_result(it)

    def eventFilter(self, obj, e):
        if obj is self.find and e.type() == e.Type.KeyPress and self.stack.currentWidget() is self.results:
            if e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = self.results.currentRow() + (1 if e.key() == Qt.Key.Key_Down else -1)
                self.results.setCurrentRow(max(0, min(self.results.count() - 1, row)))
                return True
            if e.key() == Qt.Key.Key_Escape:
                self.find.clear()
                return True
        return super().eventFilter(obj, e)

    # ------------------------------------------------------------ actions
    def act(self, what: str, fn, then=None, quiet=False, on_fail=None):
        """Run fn on the pool; say how it went in the toast (failures always), then call then() (on_fail() instead
        when it failed and one is given)."""

        def work():
            try:
                return (what, fn() or tr("grimoire.spells.settingl.page", "done"), True, then, quiet, on_fail)
            except Exception as err:  # shown, not a crash
                return (what, str(err), False, then, quiet, on_fail)

        POOL.start(Job(work, self.sig.acted.emit))

    def _acted(self, result):
        what, msg, ok, then, quiet, on_fail = result
        if not ok or not quiet:
            what, msg = i18n.isolate(str(what).lstrip("‏")), i18n.isolate(str(msg))
            self.say(
                tr("grimoire.spells.settingl.page", "{what}: {message}").format(what=what, message=msg)
                if ok
                else tr("grimoire.spells.settingl.page", "Couldn't change {what}: {message}").format(
                    what=what, message=msg
                )
            )
        if not ok and on_fail:
            on_fail()
        elif then:
            then()

    def say(self, text: str):
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start()


def status() -> str:
    """The home card's line (cheap: a few small files, no D-Bus)."""
    from datetime import datetime

    from grimoire.spells.settingl import kde, notify

    bits = []
    cfg = kde.parse("kwinrc").get(("NightColor",), {})
    bits.append(
        tr("grimoire.spells.settingl.page", "Night light on")
        if kde.as_bool(cfg.get("Active", ""))
        else tr("grimoire.spells.settingl.page", "Night light off")
    )
    try:
        until = notify._until(kde.parse(notify.FILE).get(("DoNotDisturb",), {}).get("Until", ""))
        if until and until > datetime.now():
            bits.append(tr("grimoire.spells.settingl.page", "Do Not Disturb on"))
    except (OSError, ValueError):
        pass
    n = len(kcms.scan())  # the same count as the All KDE settings page (≈0.1 s of reading metadata)
    bits.append(tr("grimoire.spells.settingl.page", "%n KDE module(s) one search away", n=n))
    return " · ".join(bits)
