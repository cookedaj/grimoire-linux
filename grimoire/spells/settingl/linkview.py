# SPDX-License-Identifier: GPL-3.0-or-later
"""Pages that are another spell's work: Sound (AudioL's device panel, embedded), Network (NetL's Wi-Fi & VPN panel,
embedded), Appearance (MuraL's tabs), Startup apps (SystemL) and Updates (UpdateL); and the list of every KDE
settings module, so nothing System Settings has is out of reach."""

import os
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.settingl import kcms, kde
from grimoire.spells.settingl.common import OPEN_SPELL, FlowLinks, Panel, Row, label
from grimoire.widgets import plain_tip

CTX = "grimoire.spells.settingl.linkview"


def _open_button(text: str, fn) -> QPushButton:
    b = QPushButton(glyph("forward", 14), " " + text)
    b.clicked.connect(fn)
    return b


# ---------------------------------------------------------------- sound
class _SoundSig(QObject):
    sampled = Signal(object)


class SoundPanel(QWidget):
    """AudioL's outputs & inputs panel in SettingL; reads PipeWire every 1.5 s while it's on screen."""

    def __init__(self, host):
        super().__init__()
        from grimoire.spells.audiol import pw
        from grimoire.spells.audiol.page import DevicesPanel

        self.host = host
        self.pw = pw
        self.snap = None
        self.sig = _SoundSig()
        self.sig.sampled.connect(self._sampled)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(
            label(
                tr(
                    "grimoire.spells.settingl.linkview",
                    "Your speakers and microphones. Each app's volume, the equalizer and sound "
                    "card profiles are in AudioL.",
                ),
                "Muted",
                wrap=True,
            ),
            1,
        )
        top.addWidget(
            _open_button(tr("grimoire.spells.settingl.linkview", "Open AudioL"), lambda: OPEN_SPELL(self, "audiol"))
        )
        lay.addLayout(top)
        self.missing = label(
            tr(
                "grimoire.spells.settingl.linkview",
                "Sound settings need PipeWire's tools (pw-dump and wpctl). Install them "
                "with:\n\nsudo apt install pipewire-bin wireplumber",
            ),
            "Muted",
            wrap=True,
        )
        self.missing.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.missing.hide()
        lay.addWidget(self.missing)
        self.devices = DevicesPanel(self)
        lay.addWidget(self.devices, 1)
        lay.addWidget(label(tr("grimoire.spells.settingl.common", "MORE IN KDE'S SETTINGS"), "NavSection"))
        lay.addWidget(FlowLinks(["kcm_pulseaudio", "kcm_soundtheme", "kcm_audiocd"], host))
        self._poll = QTimer(self, interval=1500, timeout=self.refresh)
        self._sbusy = False

    # what DevicesPanel asks of its page
    def act(self, what, fn, then=None, quiet=False):
        self.host.act(what, fn, then=then, quiet=quiet)

    def refresh(self):
        if self._sbusy:
            return
        if not self.pw.available():
            self.missing.show()
            self.devices.hide()
            return
        self._sbusy = True
        snap = self.pw.snapshot

        def work():
            try:
                return {"snap": snap()}
            except Exception as e:
                return {"error": str(e)}

        POOL.start(Job(work, self.sig.sampled.emit))

    def _sampled(self, r):
        self._sbusy = False
        if "error" in r:
            return
        self.snap = r["snap"]
        self.devices.set_snap(self.snap)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()
        self._poll.start()
        self.devices._meters()

    def hideEvent(self, e):
        self._poll.stop()
        super().hideEvent(e)


# ---------------------------------------------------------------- network
class _NetSig(QObject):
    wifi = Signal(object)


class NetworkPanel(QWidget):
    """NetL's Wi-Fi & VPN panel in SettingL (it scrolls itself); reads NetworkManager every 15 s while shown."""

    def __init__(self, host):
        super().__init__()
        from grimoire.spells.netl.wifiview import WifiPanel

        self.host = host
        self.sig = _NetSig()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(
            label(
                tr(
                    "grimoire.spells.settingl.linkview",
                    "Wi-Fi, airplane mode and VPNs. Live traffic, per-app use and history are in NetL.",
                ),
                "Muted",
                wrap=True,
            ),
            1,
        )
        top.addWidget(
            _open_button(tr("grimoire.spells.settingl.linkview", "Open NetL"), lambda: OPEN_SPELL(self, "netl"))
        )
        top.addWidget(
            _open_button(
                tr("grimoire.spells.settingl.linkview", "Edit connections"),
                lambda: host.open_module("kcm_networkmanagement"),
            )
        )
        lay.addLayout(top)
        self.wifi = WifiPanel(self)
        lay.addWidget(self.wifi, 1)
        lay.addWidget(label(tr("grimoire.spells.settingl.common", "MORE IN KDE'S SETTINGS"), "NavSection"))
        lay.addWidget(
            FlowLinks(["kcm_networkmanagement", "kcm_proxy", "kcm_firewall", "kcm_netpref", "kcm_kaccounts"], host)
        )
        self._poll = QTimer(self, interval=15000, timeout=self.wifi.load)

    def act(self, what, fn, then=None, quiet=False):
        self.host.act(what, fn, then=then, quiet=quiet)

    def say(self, text):
        self.host.say(text)

    def showEvent(self, e):
        super().showEvent(e)
        self.wifi.load()
        self._poll.start()

    def hideEvent(self, e):
        self._poll.stop()
        super().hideEvent(e)


# ---------------------------------------------------------------- appearance, startup, updates
class AppearancePanel(Panel):
    def __init__(self, host):
        super().__init__(host)
        from grimoire.spells.mural.page import SECTIONS

        self.note(
            tr(
                "grimoire.spells.settingl.linkview",
                "MuraL changes everything you look at, in black and white or any way you like.",
            )
        )
        i = 0
        for section, tabs in SECTIONS:
            self.col.addWidget(label(tr("grimoire.spells.mural.page", section), "NavSection"))
            for name, icon, _, _ in tabs:
                b = _open_button(
                    tr("grimoire.spells.settingl.linkview", "Open"),
                    lambda _=False, n=i: OPEN_SPELL(self, "mural", lambda page, n=n: page.open_tab(n)),
                )
                self.col.addWidget(Row(tr("grimoire.spells.mural.page", name), "", b, glyph(icon, 24)))
                i += 1
        self.kde_links(
            [
                "kcm_lookandfeel",
                "kcm_colors",
                "kcm_desktoptheme",
                "kcm_style",
                "kcm_icons",
                "kcm_cursortheme",
                "kcm_fonts",
                "kcm_kwindecoration",
                "kcm_wallpaper",
                "kcm_splashscreen",
                "kcm_sddm",
                "kcm_plymouth",
                "kcm_animations",
                "kcm_kwin_effects",
                "kcm_workspace",
            ]
        )
        self.finish()


def _autostart_count() -> int:
    d = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart"
    return len(list(d.glob("*.desktop"))) if d.is_dir() else 0


class StartupPanel(Panel):
    def __init__(self, host):
        super().__init__(host)
        self.row = Row(
            tr("grimoire.spells.settingl.linkview", "Startup apps"),
            "",
            _open_button(
                tr("grimoire.spells.settingl.linkview", "Open in SystemL"),
                lambda: OPEN_SPELL(self, "systeml", lambda page: page.show_panel("startup")),
            ),
            glyph("splash", 24),
        )
        self.col.addWidget(self.row)
        self.col.addWidget(
            Row(
                tr("grimoire.spells.settingl.linkview", "Background services"),
                tr("grimoire.spells.settingl.linkview", "What runs at login without a window."),
                _open_button(
                    tr("grimoire.spells.settingl.linkview", "Open in SystemL"),
                    lambda: OPEN_SPELL(self, "systeml", lambda page: page.show_panel("services")),
                ),
                glyph("boot", 24),
            )
        )
        self.kde_links(["kcm_autostart", "kcm_smserver", "kcm_kded", "kcm_desktoppaths"])
        self.finish()

    def read(self):
        return _autostart_count()

    def fill(self, n):
        self.row.set_sub(
            tr(
                "grimoire.spells.settingl.linkview",
                "%n app(s) of yours start when you log in. Turn them on or off, or add one.",
                n=n,
            )
        )


class UpdatesPanel(Panel):
    def __init__(self, host):
        super().__init__(host)
        self.row = Row(
            tr("grimoire.spells.settingl.linkview", "System updates"),
            "",
            _open_button(tr("grimoire.spells.settingl.linkview", "Open UpdateL"), lambda: OPEN_SPELL(self, "updatel")),
            glyph("updatel", 24),
        )
        self.col.addWidget(self.row)
        self.note(
            tr(
                "grimoire.spells.settingl.linkview",
                "UpdateL shows every update (packages, Flatpaks, snaps and firmware) with changelogs and "
                "a preview of anything that would be removed.",
            )
        )
        self.kde_links(["kcm_updates"])
        self.finish()

    def read(self):
        from grimoire.spells.updatel.daily import status_line

        return status_line()

    def fill(self, text):
        self.row.set_sub(text)


# ---------------------------------------------------------------- every KDE module
OTHER = tr_noop("grimoire.spells.settingl.linkview", "Other")


class KdePanel(QWidget):
    """Every installed KDE settings module, grouped like System Settings; Enter or a double click opens one."""

    def __init__(self, host):
        super().__init__()
        self.host = host
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        top = QHBoxLayout()
        self.count = label("", "Muted", wrap=True)
        top.addWidget(self.count, 1)
        self.open_btn = QPushButton(tr("grimoire.spells.settingl.linkview", "Open"))
        self.open_btn.setObjectName("Primary")
        self.open_btn.clicked.connect(self._open)
        top.addWidget(self.open_btn)
        allb = QPushButton(tr("grimoire.spells.settingl.linkview", "Open System Settings"))
        allb.clicked.connect(
            lambda: host.act("System Settings", lambda: kde.LAUNCH(["systemsettings"]) or "", quiet=True)
        )
        allb.setVisible(kde.have("systemsettings"))
        top.addWidget(allb)
        lay.addLayout(top)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(
            [tr("grimoire.spells.settingl.linkview", "Module"), tr("grimoire.spells.settingl.linkview", "What it does")]
        )
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        h.resizeSection(0, 300)
        h.setStretchLastSection(True)
        self.tree.itemActivated.connect(lambda *_: self._open())
        self.tree.itemSelectionChanged.connect(lambda: self.open_btn.setEnabled(self._current() is not None))
        lay.addWidget(self.tree, 1)
        if host.modules is None:
            host.modules_ready.connect(self._fill)
        else:
            self._fill()

    def _fill(self):
        mods = self.host.modules or []
        cats = kcms.categories()
        self.count.setText(
            tr(
                "grimoire.spells.settingl.linkview",
                "%n settings module(s) of KDE's are installed. Each opens in KDE's own window.",
                n=len(mods),
            )
        )
        groups: dict[str, list] = {}
        for m in mods:
            groups.setdefault(m["category"] if m["category"] in cats else "", []).append(m)

        def top(cid):  # System Settings nests one level: a sidebar category and the groups inside it
            parent = cats[cid]["parent"] if cid in cats else ""
            return parent if parent in cats else cid

        def order(cid):
            if cid not in cats:
                return (1, 999, "", 0, 0)
            t = top(cid)
            return (0, cats[t]["weight"], cats[t]["name"].casefold(), cid != t, cats[cid]["weight"])

        def heading(text, depth):
            head = QTreeWidgetItem(["    " * depth + text, ""])
            head.setFlags(Qt.ItemFlag.ItemIsEnabled)
            f = head.font(0)
            f.setBold(True)
            head.setFont(0, f)
            self.tree.addTopLevelItem(head)

        self.tree.clear()
        shown_tops = set()
        for cid in sorted(groups, key=order):
            if cid not in cats:
                heading(tr("grimoire.spells.settingl.linkview", OTHER), 0)
                depth = 1
            else:
                t = top(cid)
                if t not in shown_tops:
                    shown_tops.add(t)
                    heading(cats[t]["name"], 0)
                depth = 1
                if cid != t:
                    heading(cats[cid]["name"], 1)
                    depth = 2
            for m in sorted(groups[cid], key=lambda m: (m["weight"], m["name"].casefold())):
                it = QTreeWidgetItem(["    " * depth + m["name"], m["description"]])
                it.setData(0, Qt.ItemDataRole.UserRole, m["id"])
                it.setToolTip(1, plain_tip(m["description"]))
                self.tree.addTopLevelItem(it)
        self.open_btn.setEnabled(False)

    def _current(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.ItemDataRole.UserRole) if it else None

    def _open(self):
        mid = self._current()
        if mid:
            self.host.open_module(mid)
