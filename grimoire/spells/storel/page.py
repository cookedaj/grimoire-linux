# SPDX-License-Identifier: GPL-3.0-or-later
"""StoreL page: Home (picks and categories), search across Flathub, APT and Snap, an app's page, your installed
apps, Flatpak permissions and the install queue. Updates aren't here: they're UpdateL's job, linked from the side.

Opening the page reads the catalog cache and what's installed on a worker thread (no network); searching the catalog
is local; only an app's sizes, screenshots and Snap results go online. Installing or removing first shows a preview
(APT simulated with apt-get -s), then the task joins the queue.
"""
import os
import subprocess
import sys

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QStackedWidget, QToolButton, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from grimoire import i18n
from grimoire.fsutil import human
from grimoire.glyphs import glyph
from grimoire.i18n import tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.spells.storel import catalog, library, sources
from grimoire.spells.storel.apply import Task
from grimoire.spells.storel.detail import DetailView
from grimoire.spells.storel.grid import AppGrid, Icons
from grimoire.spells.storel.permview import PermissionsPanel
from grimoire.spells.storel.preview import PreviewDialog
from grimoire.spells.storel.queueview import Queue, QueuePanel
from grimoire.spells.systeml.page import NumItem, _tree
from grimoire.widgets import plain_tip, segments

CATS = {"AudioVideo": (tr_noop("grimoire.spells.storel.page", "Audio & Video"), "music"),
        "Development": (tr_noop("grimoire.spells.storel.page", "Development"), "terminal"),
        "Education": (tr_noop("grimoire.spells.storel.page", "Education"), "cap"),
        "Game": (tr_noop("grimoire.spells.storel.page", "Games"), "game"),
        "Graphics": (tr_noop("grimoire.spells.storel.page", "Graphics"), "mural"),
        "Network": (tr_noop("grimoire.spells.storel.page", "Internet"), "net"),
        "Office": (tr_noop("grimoire.spells.storel.page", "Office"), "document"),
        "Science": (tr_noop("grimoire.spells.storel.page", "Science"), "flask"),
        "System": (tr_noop("grimoire.spells.storel.page", "System"), "system"),
        "Utility": (tr_noop("grimoire.spells.storel.page", "Utilities"), "sliders")}
FILTERS = [("all", tr_noop("grimoire.spells.storel.page", "All")), ("flatpak", "Flathub"), ("apt", "APT"),
           ("snap", "Snap")]
TOOLS = {"flatpak": "flatpak", "apt": "apt-get", "snap": "snap"}


class _Signals(QObject):
    loaded = Signal(object)          # (catalog dict, installed dict)
    installed = Signal(object)       # installed dict
    planned = Signal(object)         # (task, plan, error)
    found = Signal(object)           # (query, [apps]) from Snap / flatpak search
    refreshed = Signal(object)       # (ok, message)


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)        # search words, app and package names: never rich text
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _cat(cid: str) -> str:
    return tr("grimoire.spells.storel.page", CATS[cid][0])


def _launch(module: str, *args: str):
    """Another Grimoire window (UpdateL) from this checkout or installed copy."""
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    env = dict(os.environ, PYTHONPATH=f"{repo}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"))
    subprocess.Popen([sys.executable, "-m", module, *args], env=env, start_new_session=True)


# ---------------------------------------------------------------- home
class HomePanel(QScrollArea):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 24)
        col.setSpacing(12)
        self.intro = _label("", "Muted", wrap=True)
        self.intro.setTextFormat(Qt.TextFormat.PlainText)
        col.addWidget(self.intro)
        col.addWidget(_label(tr("grimoire.spells.storel.page", "Categories"), "SectionTitle"))
        tiles = QGridLayout()
        tiles.setSpacing(10)
        self.tiles = {}
        for n, cid in enumerate(catalog.CATEGORIES):
            b = QPushButton(glyph(CATS[cid][1], 20), "  " + _cat(cid).replace("&", "&&"))
            b.setObjectName("CatTile")
            b.setIconSize(b.iconSize().expandedTo(b.iconSize()))
            b.setMinimumHeight(54)
            b.clicked.connect(lambda _=False, c=cid: page.show_category(c))
            tiles.addWidget(b, n // 5, n % 5)
            self.tiles[cid] = b
        col.addLayout(tiles)
        col.addSpacing(8)
        col.addWidget(_label(tr("grimoire.spells.storel.page", "Picks"), "SectionTitle"))
        col.addWidget(_label(tr("grimoire.spells.storel.page", "Well-made apps worth a look."), "Muted"))
        self.picks = AppGrid(page, page.icons, scroll=False)
        self.picks.opened.connect(page.show_app)
        col.addWidget(self.picks)
        col.addStretch(1)
        self.setWidget(inner)

    def fill(self, apps: list[dict], notes: list[str]):
        n_flat = sum(any(o["src"] == "flatpak" for o in a["offers"]) for a in apps)
        n_apt = sum(any(o["src"] == "apt" for o in a["offers"]) for a in apps)
        text = tr("grimoire.spells.storel.page", "{n} apps: {flat} on Flathub and {apt} from Ubuntu's archive. "
                  "Search with Ctrl+F; updates stay in UpdateL.").format(n=len(apps), flat=n_flat, apt=n_apt)
        if not n_flat and sources.have("flatpak"):
            text += "\n" + tr("grimoire.spells.storel.page", "Flathub's app list isn't downloaded yet: press the "
                               "refresh button next to the search field.")
        if not n_apt:
            text += "\n" + (tr("grimoire.spells.storel.page", "Ubuntu's apps need python3-yaml to be read: "
                                "sudo apt install python3-yaml") if "python3-yaml" in notes else
                             tr("grimoire.spells.storel.page", "Ubuntu's app list is missing: refresh the package "
                                "lists in UpdateL."))
        self.intro.setText(text)
        for cid, b in self.tiles.items():
            b.setToolTip(tr("grimoire.spells.storel.page", "%n app(s)", n=len(catalog.in_category(apps, cid))))
        self.picks.set_apps(catalog.picks(apps)[:18])


# ---------------------------------------------------------------- installed
class InstalledPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.rows: list[tuple[dict, dict]] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        bar = QFrame()
        bar.setObjectName("Row")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 10, 12, 10)
        bl.addWidget(_label(tr("grimoire.spells.storel.page", "Updates for these apps (and the rest of the system) "
                               "are in UpdateL."), "Muted", wrap=True), 1)
        up = QPushButton(glyph("updatel", 16), "  " + tr("grimoire.spells.storel.page", "Open UpdateL"))
        up.clicked.connect(page.open_updatel)
        bl.addWidget(up)
        lay.addWidget(bar)
        top = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("grimoire.spells.storel.page", "Filter your apps"))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(lambda _t: self.fill())
        top.addWidget(self.filter, 1)
        self.count = _label("", "Muted")
        top.addWidget(self.count)
        lay.addLayout(top)
        self.tree = _tree([tr("grimoire.spells.storel.page", "Name"), tr("grimoire.spells.storel.page", "Source"),
                           tr("grimoire.spells.storel.page", "Version"), tr("grimoire.spells.storel.page", "Size")])
        h = self.tree.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c, w in ((1, 150), (2, 200), (3, 100)):
            h.resizeSection(c, w)
        self.tree.setIconSize(self.tree.iconSize().expandedTo(self.tree.iconSize()))
        self.tree.itemActivated.connect(lambda *_: self._details())
        self.tree.currentItemChanged.connect(lambda *_: self._buttons())
        lay.addWidget(self.tree, 1)
        btns = QHBoxLayout()
        self.keep = _label("", "Muted", wrap=True)
        self.keep.setTextFormat(Qt.TextFormat.PlainText)
        btns.addWidget(self.keep, 1)
        self.details_btn = QPushButton(tr("grimoire.spells.storel.page", "Details"))
        self.details_btn.clicked.connect(self._details)
        self.open_btn = QPushButton(tr("grimoire.spells.storel.page", "Open", "verb"))
        self.open_btn.clicked.connect(self._open)
        self.remove_btn = QPushButton(tr("grimoire.spells.storel.page", "Remove"))
        self.remove_btn.clicked.connect(self._remove)
        for b in (self.details_btn, self.open_btn, self.remove_btn):
            btns.addWidget(b)
        lay.addLayout(btns)
        page.icons.ready.connect(self._icon_ready)

    def set_rows(self, rows):
        self.rows = rows
        self.fill()

    def fill(self):
        cur = self.tree.currentItem()
        keep = cur.data(0, Qt.ItemDataRole.UserRole + 1) if cur else None
        q = self.filter.text().strip().casefold()
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        self.items: dict[str, list[QTreeWidgetItem]] = {}
        shown = 0
        for n, (app, copy) in enumerate(self.rows):
            if q and q not in app["name"].casefold() and q not in copy["name"].casefold():
                continue
            shown += 1
            src = library.SOURCE_NAMES[copy["src"]]
            if copy["src"] == "flatpak":
                src = "{src} · {scope}".format(src=src, scope=tr("grimoire.spells.storel.page", "yours", "scope")
                                               if copy["scope"] == "user" else
                                               tr("grimoire.spells.storel.page", "system", "scope"))
            row = NumItem([app["name"], src, i18n.ltr(copy["version"] or "–"),
                           i18n.ltr(human(copy["size"])) if copy["size"] else "–"])
            for c, v in enumerate([app["name"].casefold(), src, copy["version"], copy["size"] or 0]):
                row.setData(c, Qt.ItemDataRole.UserRole, v)
            row.setData(0, Qt.ItemDataRole.UserRole + 1, n)
            row.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.setToolTip(0, plain_tip(copy["name"]))
            pm = self.page.icons.get(app)
            row.setIcon(0, pm or self.page.icons.fallback)
            if copy["keep"]:
                row.setForeground(0, self.palette().placeholderText())
            self.tree.addTopLevelItem(row)
            self.items.setdefault(app["key"], []).append(row)
        self.tree.setSortingEnabled(True)
        self.tree.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.count.setText(tr("grimoire.spells.storel.page", "%n app(s)", n=shown))
        hit = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())
               if self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole + 1) == keep]
        if hit:
            self.tree.setCurrentItem(hit[0])
        self._buttons()

    def _icon_ready(self, key):
        for row in getattr(self, "items", {}).get(key, []):
            app = self.rows[row.data(0, Qt.ItemDataRole.UserRole + 1)][0]
            pm = self.page.icons.get(app)
            if pm:
                row.setIcon(0, pm)

    def current(self):
        it = self.tree.currentItem()
        if not it:
            return None, None
        return self.rows[it.data(0, Qt.ItemDataRole.UserRole + 1)]

    def _buttons(self):
        app, copy = self.current()
        queued = bool(app and self.page.queue.pending(app["key"]))
        self.details_btn.setEnabled(app is not None)
        self.open_btn.setEnabled(bool(app and library.open_command(app, copy, self.page.inst)))
        self.remove_btn.setEnabled(bool(app) and not copy["keep"] and not queued)
        self.keep.setText(copy["keep"] if copy and copy["keep"] else
                          tr("grimoire.spells.storel.page", "In the queue.") if queued else "")

    def _details(self):
        app, copy = self.current()
        if app:
            self.page.show_app(app, copy["offer"])

    def _open(self):
        app, copy = self.current()
        if app:
            self.page.open_app(app, copy)

    def _remove(self):
        app, copy = self.current()
        if app and not copy["keep"]:
            self.page.request_remove(app, copy)


# ---------------------------------------------------------------- the page
class StoreLPage(QWidget):
    QSS = """
    QPushButton#CatTile { text-align: left; padding: 10px 14px; border: 1px solid #1f1f1f; border-radius: 10px;
                          background: #101010; color: #d0d0d0; }
    QPushButton#CatTile:hover { border-color: #6a6a6a; color: #ffffff; }
    QPlainTextEdit#Log { font-family: "IBM Plex Mono"; font-size: 11px; color: #bdbdbd; background: #080808;
                         border: 1px solid #1c1c1c; border-radius: 8px; padding: 6px; }
    QProgressBar { background: #121212; border: 1px solid #262626; border-radius: 4px; max-height: 6px; }
    QProgressBar::chunk { background: #f2f2f2; border-radius: 3px; }
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.setStyleSheet(self.QSS)
        self.sig = _Signals()
        self.icons = Icons()
        self.queue = Queue()
        self.apps: list[dict] = []
        self.inst: dict = {"flatpak": [], "apt": {}, "snap": [], "desktop": [], "remotes": {}}
        self.loaded = False
        self.view = "home"
        self.history: list[str] = []
        self.source = "all"
        self.extra: list[dict] = []                   # Snap / flatpak search results for the current query
        self._planning = False
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setMinimumWidth(214)
        nav_scroll.setMaximumWidth(300)
        nav = QFrame()
        nav.setObjectName("SubNav")
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(12, 26, 12, 16)
        nl.setSpacing(2)
        nl.addWidget(_label("StoreL", "Title"))
        nl.addSpacing(12)
        nl.addWidget(_label(tr("grimoire.spells.storel.page", "DISCOVER"), "NavSection"))
        self.nav: dict[str, QPushButton] = {}

        def item(pid, text, icon):
            b = QPushButton(glyph(icon, 18), "  " + text.replace("&", "&&"))
            b.setObjectName("SubNavItem")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, p=pid: self.go(p))
            nl.addWidget(b)
            self.nav[pid] = b
        item("home", tr("grimoire.spells.storel.page", "Home"), "home")
        for cid in catalog.CATEGORIES:
            item(f"cat:{cid}", _cat(cid), CATS[cid][1])
        nl.addSpacing(10)
        nl.addWidget(_label(tr("grimoire.spells.storel.page", "YOUR APPS"), "NavSection"))
        item("installed", tr("grimoire.spells.storel.page", "Installed"), "check")
        item("perms", tr("grimoire.spells.storel.page", "Permissions"), "lock")
        item("queue", tr("grimoire.spells.storel.page", "Queue"), "store")
        up = QPushButton(glyph("updatel", 18), "  " + tr("grimoire.spells.storel.page", "Updates in UpdateL"))
        up.setObjectName("SubNavItem")
        up.setToolTip(tr("grimoire.spells.storel.page", "StoreL installs and removes; UpdateL keeps everything "
                                                        "up to date"))
        up.clicked.connect(self.open_updatel)
        nl.addWidget(up)
        nl.addStretch(1)
        self.foot = _label("", "Tiny", wrap=True)
        self.foot.setTextFormat(Qt.TextFormat.PlainText)
        nl.addWidget(self.foot)
        nav_scroll.setWidget(nav)
        root.addWidget(nav_scroll)

        right = QVBoxLayout()
        right.setContentsMargins(28, 22, 28, 16)
        right.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("grimoire.spells.storel.page", "Search apps on Flathub, APT and Snap"))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(glyph("search", 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(lambda _t: self._search_timer.start())
        self.search.returnPressed.connect(self._search_now)
        top.addWidget(self.search, 1)
        self.refresh_btn = QToolButton()
        self.refresh_btn.setObjectName("Tool")
        self.refresh_btn.setIcon(glyph("update", 18))
        self.refresh_btn.setToolTip(tr("grimoire.spells.storel.page", "Download Flathub's app list again (no "
                                                                      "password; Ubuntu's comes with UpdateL's "
                                                                      "Refresh package lists)"))
        self.refresh_btn.clicked.connect(self.refresh_catalog)
        top.addWidget(self.refresh_btn)
        right.addLayout(top)
        head = QHBoxLayout()
        self.heading = _label("", "PageHeading")
        head.addWidget(self.heading, 1)
        self.filter_btns = {}
        fl = QHBoxLayout()
        fl.setSpacing(0)
        for fid, text in FILTERS:
            b = QPushButton(tr("grimoire.spells.storel.page", text) if fid == "all" else text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setChecked(fid == "all")
            b.clicked.connect(lambda _=False, f=fid: self._set_source(f))
            fl.addWidget(b)
            self.filter_btns[fid] = b
        segments(list(self.filter_btns.values()))
        head.addLayout(fl)
        right.addLayout(head)

        self.stack = QStackedWidget()
        self.home = HomePanel(self)
        self.results = AppGrid(self, self.icons)
        self.results.opened.connect(self.show_app)
        self.empty = _label("", "Muted", wrap=True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setTextFormat(Qt.TextFormat.PlainText)
        self.detail = DetailView(self)
        self.detail.back.connect(self.back)
        self.installed = InstalledPanel(self)
        self.perms = PermissionsPanel(self)
        self.queue_panel = QueuePanel(self.queue)
        for w in (self.home, self.results, self.empty, self.detail, self.installed, self.perms, self.queue_panel):
            self.stack.addWidget(w)
        right.addWidget(self.stack, 1)
        self.toast = _label("", "Toast", wrap=True)
        self.toast.setTextFormat(Qt.TextFormat.PlainText)
        self.toast.hide()
        right.addWidget(self.toast)
        self._toast_timer = QTimer(self, singleShot=True, interval=8000, timeout=self.toast.hide)
        root.addLayout(right, 1)

        self._search_timer = QTimer(self, singleShot=True, interval=250, timeout=self._search_now)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Find), self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+K"), self, self._focus_search)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._escape,
                  context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.sig.loaded.connect(self._loaded)
        self.sig.installed.connect(self._installed)
        self.sig.planned.connect(self._planned)
        self.sig.found.connect(self._found)
        self.sig.refreshed.connect(self._catalog_refreshed)
        self.queue.changed.connect(self._queue_changed)
        self.queue.finished.connect(self._batch_done)
        self.go("home")
        self._loading()
        self.load()

    # ------------------------------------------------------------ loading
    def _loading(self):
        self.empty.setText(tr("grimoire.spells.storel.page", "Reading the app catalog…"))
        self.stack.setCurrentWidget(self.empty)

    def load(self, force: bool = False):
        def work():
            inst = sources.installed()
            try:
                data = catalog.load(inst.get("remotes") or None, force=force)
            except Exception as e:                  # a broken cache or metadata file: shown, never a crash
                data = {"apps": [], "notes": [str(e)]}
            return data, inst
        POOL.start(Job(work, self.sig.loaded.emit))

    def _loaded(self, result):
        data, inst = result
        self.apps = data.get("apps", [])
        self.notes = data.get("notes", [])
        self.loaded = True
        self._installed(inst)
        self.home.fill(self.apps, self.notes)
        self.go(self.view, remember=False)

    def reload_installed(self):
        POOL.start(Job(sources.installed, self.sig.installed.emit))

    def _installed(self, inst: dict):
        self.inst = inst
        rows = []
        for app, cs in library.installed_apps(self.apps, inst):
            rows += [(app, c) for c in cs]
        self.installed.set_rows(rows)
        self.perms.set_apps([(c["name"].split("/")[1], app["name"]) for app, c in rows if c["src"] == "flatpak"])
        n_apps = len({app["key"] for app, _c in rows})
        library.save_status(n_apps, len(self.apps))
        self.foot.setText(library.status_line())
        self.results.model_.refresh_all()
        self.home.picks.model_.refresh_all()
        self.detail.refresh()

    def showEvent(self, e):
        if self.loaded:
            self.reload_installed()                 # something may have been installed elsewhere
        super().showEvent(e)

    # ------------------------------------------------------------ navigation
    def go(self, view: str, remember: bool = True):
        if remember and view != self.view and self.view != "detail":
            self.history.append(self.view)
        self.view = view
        self.heading.show()
        for p, b in self.nav.items():
            b.setChecked(p == view)
        browsing = view.startswith(("cat:", "search")) and self.loaded
        for b in self.filter_btns.values():
            b.setVisible(browsing)
        self.filter_btns["snap"].setVisible(browsing and sources.have("snap"))
        if view == "home":
            self.heading.setText(tr("grimoire.spells.storel.page", "Home"))
            self.stack.setCurrentWidget(self.home if self.loaded else self.empty)
        elif view.startswith("cat:"):
            self.heading.setText(_cat(view[4:]))
            self._show_results(catalog.in_category(self.apps, view[4:]))
        elif view == "search":
            self.heading.setText(tr("grimoire.spells.storel.page", "Search"))
            self._search_now()
        elif view == "installed":
            self.heading.setText(tr("grimoire.spells.storel.page", "Installed"))
            self.stack.setCurrentWidget(self.installed)
        elif view == "perms":
            self.heading.setText(tr("grimoire.spells.storel.page", "Permissions"))
            self.stack.setCurrentWidget(self.perms)
        elif view == "queue":
            self.heading.setText(tr("grimoire.spells.storel.page", "Queue"))
            self.stack.setCurrentWidget(self.queue_panel)
        if not self.loaded and view in ("home", "search") or (view.startswith("cat:") and not self.loaded):
            self._loading()

    def show_category(self, cid: str):
        self.go(f"cat:{cid}")

    def show_app(self, app: dict, offer_id: str = ""):
        if not app:
            return
        if self.view != "detail":
            self.history.append(self.view)
        self.view = "detail"
        for b in self.nav.values():
            b.setChecked(False)
        for b in self.filter_btns.values():
            b.setVisible(False)
        self.heading.hide()
        self.detail.show_app(app, offer_id)
        self.stack.setCurrentWidget(self.detail)
        self.detail.setFocus()

    def back(self):
        prev = self.history.pop() if self.history else "home"
        self.view = ""
        self.go(prev, remember=False)

    def show_permissions(self, app_id: str):
        self.go("perms")
        self.perms.select(app_id)

    def _escape(self):
        if self.view == "detail":
            self.back()
        elif self.search.hasFocus() and self.search.text():
            self.search.clear()

    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def say(self, text: str):
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start()

    def can(self, src: str) -> bool:
        return sources.have(TOOLS[src])

    def app_state(self, app: dict) -> str:
        if self.queue.pending(app["key"]):
            return "queued"
        return "installed" if library.copies(app, self.inst) else ""

    def open_updatel(self):
        win = self.window()
        if hasattr(win, "pages") and "updatel" in win.pages:
            win.open("updatel")
        else:
            _launch("grimoire.standalone", "updatel")

    # ------------------------------------------------------------ browsing
    def _set_source(self, src: str):
        self.source = src
        for f, b in self.filter_btns.items():
            b.setChecked(f == src)
        if self.view.startswith("cat:") or self.view == "search":
            self.go(self.view, remember=False)

    def _filtered(self, apps: list[dict]) -> list[dict]:
        if self.source == "all":
            return apps
        return [a for a in apps if any(o["src"] == self.source for o in a["offers"])]

    def _show_results(self, apps: list[dict], none: str = ""):
        apps = self._filtered(apps)
        self.results.set_apps(apps)
        if apps:
            self.stack.setCurrentWidget(self.results)
            self.results.scrollToTop()
        else:
            self.empty.setText(none or tr("grimoire.spells.storel.page", "No apps here from this source."))
            self.stack.setCurrentWidget(self.empty)

    def _search_now(self):
        self._search_timer.stop()
        q = self.search.text().strip()
        if not q:
            if self.view == "search":
                self.back()
            return
        if self.view != "search":
            if self.view != "detail":
                self.history.append(self.view)
            self.view = "search"
            self.heading.show()
            for b in self.nav.values():
                b.setChecked(False)
            self.heading.setText(tr("grimoire.spells.storel.page", "Search"))
            for b in self.filter_btns.values():
                b.setVisible(self.loaded)
            self.filter_btns["snap"].setVisible(self.loaded and sources.have("snap"))
        if not self.loaded:
            return
        self.heading.setText(tr("grimoire.spells.storel.page", "Results for “{query}”").format(
            query=i18n.isolate(q)))
        if getattr(self, "_query", None) != q:
            self._query = q
            self.extra = []
            no_flatpak = not any(o["src"] == "flatpak" for a in self.apps[:2000] for o in a["offers"])
            if sources.have("snap") or (no_flatpak and sources.have("flatpak")):
                def work(q=q, no_flatpak=no_flatpak):
                    found = [library.snap_app(r) for r in sources.snap_search(q)]
                    if no_flatpak:
                        found += [library.flatpak_search_app(r, catalog.arch()) for r in sources.flatpak_search(q)]
                    return q, found
                POOL.start(Job(work, self.sig.found.emit))
        self._show_results(catalog.search(self.apps, q) + self.extra,
                           tr("grimoire.spells.storel.page", "No app matches “{query}”.").format(
                               query=i18n.isolate(q)))

    def _found(self, result):
        q, apps = result
        if q != getattr(self, "_query", None):
            return
        self.extra = apps
        if self.view == "search":
            self._show_results(catalog.search(self.apps, q) + self.extra,
                               tr("grimoire.spells.storel.page", "No app matches “{query}”.").format(
                                   query=i18n.isolate(q)))

    def refresh_catalog(self):
        if not sources.have("flatpak"):
            self.load(force=True)
            return
        self.refresh_btn.setEnabled(False)
        self.say(tr("grimoire.spells.storel.page", "Downloading Flathub's app list…"))

        def work():
            try:
                r = sources.RUN(["flatpak", "update", "--appstream", "--user"], timeout=300)
                return r.returncode == 0, (r.stderr or r.stdout).strip()[-300:]
            except Exception as e:
                return False, str(e)
        POOL.start(Job(work, self.sig.refreshed.emit))

    def _catalog_refreshed(self, result):
        ok, msg = result
        self.refresh_btn.setEnabled(True)
        self.say(tr("grimoire.spells.storel.page", "App list updated.") if ok else
                 tr("grimoire.spells.storel.page", "Couldn't update the app list: {err}").format(err=i18n.isolate(msg)))
        self.load()

    # ------------------------------------------------------------ installing and removing
    def request_install(self, app: dict, offer: dict, scope: str):
        if self._planning or self.queue.pending(app["key"]):
            return
        if offer["src"] == "flatpak":
            task = Task("install", "flatpak", app["name"], app["key"], [offer["ref"]], scope=scope,
                        remote=offer.get("remote") or "flathub")
        elif offer["src"] == "apt":
            task = Task("install", "apt", app["name"], app["key"], [offer["pkg"]])
        else:
            task = Task("install", "snap", app["name"], app["key"], [offer["name"]])
        self._plan(task, offer)

    def request_remove(self, app: dict, copy: dict):
        if self._planning or self.queue.pending(app["key"]):
            return
        task = Task("remove", copy["src"], app["name"], app["key"], [copy["name"]], scope=copy["scope"])
        self._plan(task, None)

    def _plan(self, task: Task, offer: dict | None):
        self._planning = True
        self.say(tr("grimoire.spells.storel.page", "Working out what changes…"))

        def work():
            try:
                if task.source == "apt":
                    plan = sources.simulate(task.action, task.names)
                elif task.source == "flatpak" and task.action == "install":
                    plan = sources.flatpak_details(offer, task.scope) or {"error": tr(
                        "grimoire.spells.storel.page", "no answer")}
                    plan["runtime_installed"] = sources.runtime_installed(plan.get("runtime", ""))
                elif task.source == "snap" and task.action == "install":
                    plan = sources.snap_details(task.names[0])
                    task.classic = bool(plan.get("classic"))
                else:
                    plan = {}
                return task, plan, ""
            except Exception as e:                   # apt's own message, shown in the toast
                return task, None, str(e)
        POOL.start(Job(work, self.sig.planned.emit))

    def _planned(self, result):
        task, plan, err = result
        self._planning = False
        self.toast.hide()
        if err:
            self.say(tr("grimoire.spells.storel.page", "Couldn't plan this: {err}").format(err=i18n.isolate(err)))
            return
        dlg = PreviewDialog(self, task, plan)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        task.removals = dlg.confirmed_removals()
        if task.source == "apt" and task.action == "remove" and not task.removals:
            task.removals = list(plan.get("remove") or task.names)
        self.queue.add(task)
        self.say(tr("grimoire.spells.storel.page", "{name} is in the queue.").format(name=i18n.isolate(task.title)))

    def _queue_changed(self, _task):
        n = self.queue.active()
        name = tr("grimoire.spells.storel.page", "Queue")
        self.nav["queue"].setText("  " + (name if not n else "{name}  ·  {n}".format(name=name, n=n)))
        self.detail.refresh()
        self.installed._buttons()
        self.results.model_.refresh_all()

    def _batch_done(self, batch):
        self.reload_installed()
        ok = [t for t in batch if t.state == "done"]
        bad = [t for t in batch if t.state != "done"]
        if bad:
            self.say(tr("grimoire.spells.storel.page", "{name}: {why}").format(
                name=i18n.isolate(bad[0].title), why=bad[0].message or tr("grimoire.spells.storel.page", "failed")))
        elif ok:
            self.say(tr("grimoire.spells.storel.page", "%n change(s) done.", n=len(ok)))

    def open_app(self, app: dict, copy: dict):
        cmd = library.open_command(app, copy, self.inst)
        if not cmd:
            return
        try:
            library.LAUNCH(cmd)
        except OSError as e:
            self.say(tr("grimoire.spells.storel.page", "Couldn't open it: {err}").format(err=i18n.isolate(str(e))))
