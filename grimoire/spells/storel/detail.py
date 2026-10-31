# SPDX-License-Identifier: GPL-3.0-or-later
"""An app's page: icon, name and summary, the source to get it from (when it's on Flathub and in Ubuntu, say),
Install / Open / Remove / Permissions, screenshots (the only colour in StoreL: they show the app as it is), the
description as plain text and the facts (version, sizes, license). Sizes and screenshots load on worker threads."""
from PySide6.QtCore import QObject, QSize, Qt, QUrl, Signal
from PySide6 import QtGui
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.fsutil import human
from grimoire.glyphs import glyph
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.storel import library, media, sources
from grimoire.spells.storel.apply import RUNNING
from grimoire.widgets import segments

SHOT_H = 230


class _Signals(QObject):
    details = Signal(object)         # (cache key, dict)
    shot = Signal(object)            # (generation, index, QImage or None)
    full = Signal(object)            # (QImage or None)


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)        # everything here comes from metadata: never rich text
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _start(lab: QLabel) -> QLabel:
    """Metadata is often English even in Arabic or Urdu: keep it on the reading side, not where its own letters
    would push it."""
    side = Qt.AlignmentFlag.AlignRight if i18n.rtl() else Qt.AlignmentFlag.AlignLeft
    lab.setAlignment(Qt.AlignmentFlag.AlignAbsolute | side | Qt.AlignmentFlag.AlignTop)
    return lab


def _details(offer: dict, scope: str) -> dict:
    """Worker side: version and sizes from the source (Flatpak and Snap ask online)."""
    try:
        if offer["src"] == "apt":
            return sources.apt_details([offer["pkg"]]).get(offer["pkg"], {})
        if offer["src"] == "flatpak":
            return sources.flatpak_details(offer, scope)
        if offer["src"] == "snap":
            return sources.snap_details(offer["name"])
    except Exception as e:                    # a slow or missing tool only leaves the facts blank
        return {"error": str(e)}
    return {}


def _shot(url: str) -> QImage | None:
    p = media.get(url)
    img = QImage(str(p)) if p else QImage()
    return None if img.isNull() else img.scaledToHeight(SHOT_H * 2, Qt.TransformationMode.SmoothTransformation)


class ShotLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class ShotDialog(QDialog):
    """One screenshot, big; its full-size file loads in the background."""

    def __init__(self, parent, thumb: QPixmap, url: str):
        super().__init__(parent)
        self.setWindowTitle(tr("grimoire.spells.storel.detail", "Screenshot"))
        self.setStyleSheet("QDialog { background: #000000; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.view)
        self.pm = thumb
        screen = parent.screen().availableGeometry() if parent and parent.screen() else None
        self.box = QSize(int(screen.width() * 0.85), int(screen.height() * 0.85)) if screen else QSize(1280, 800)
        self._show()
        self.sig = _Signals()
        self.sig.full.connect(self._full)

        def work():
            p = media.get(url)
            img = QImage(str(p)) if p else QImage()
            return None if img.isNull() else img
        POOL.start(Job(work, self.sig.full.emit))

    def _show(self):
        pm = self.pm.scaled(self.box, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        pm.setDevicePixelRatio(1)
        self.view.setPixmap(pm)
        self.resize(pm.size())

    def _full(self, img):
        if img is not None:
            self.pm = QPixmap.fromImage(img)
            self._show()

    def mousePressEvent(self, e):
        self.accept()


class DetailView(QScrollArea):
    back = Signal()

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.app: dict | None = None
        self.offer: dict | None = None
        self.scope = "user"
        self.facts: dict[str, dict] = {}
        self._gen = 0
        self.sig = _Signals()
        self.sig.details.connect(self._details)
        self.sig.shot.connect(self._shot)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 14, 24)
        col.setSpacing(14)

        back = QPushButton(glyph("back", 16), "  " + tr("grimoire.spells.storel.detail", "Back"))
        back.setObjectName("Link")
        back.setShortcut("Alt+Left")
        back.clicked.connect(self.back.emit)
        col.addWidget(back, 0, Qt.AlignmentFlag.AlignLeading)

        head = QHBoxLayout()
        head.setSpacing(18)
        self.icon = QLabel()
        self.icon.setFixedSize(96, 96)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        names = QVBoxLayout()
        names.setSpacing(4)
        self.name = _start(_label("", "PageHeading", wrap=True))
        names.addWidget(self.name)
        self.dev = _start(_label("", "Muted", wrap=True))
        names.addWidget(self.dev)
        self.summary = _start(_label("", "", wrap=True))
        names.addWidget(self.summary)
        names.addStretch(1)
        head.addLayout(names, 1)
        acts = QVBoxLayout()
        acts.setSpacing(8)
        self.install_btn = QPushButton(tr("grimoire.spells.storel.detail", "Install"))
        self.install_btn.setObjectName("Primary")
        self.install_btn.setMinimumWidth(150)
        self.install_btn.setMinimumHeight(38)
        self.install_btn.clicked.connect(self._install)
        self.open_btn = QPushButton(tr("grimoire.spells.storel.detail", "Open", "verb"))
        self.open_btn.setObjectName("Primary")
        self.open_btn.setMinimumHeight(38)
        self.open_btn.clicked.connect(self._open)
        self.remove_btn = QPushButton(tr("grimoire.spells.storel.detail", "Remove"))
        self.remove_btn.clicked.connect(self._remove)
        self.perm_btn = QPushButton(glyph("lock", 16), "  " + tr("grimoire.spells.storel.detail", "Permissions"))
        self.perm_btn.clicked.connect(self._perms)
        self.queued = _label("", "Muted", wrap=True)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        for w in (self.install_btn, self.open_btn, self.remove_btn, self.perm_btn, self.queued, self.bar):
            acts.addWidget(w)
        acts.addStretch(1)
        head.addLayout(acts)
        col.addLayout(head)

        # where from
        self.src_row = QHBoxLayout()
        self.src_row.setSpacing(0)
        self.src_title = _label(tr("grimoire.spells.storel.detail", "Get it from"), "Muted")
        self.src_box = QHBoxLayout()
        self.src_box.setSpacing(0)
        self.scope_title = _label(tr("grimoire.spells.storel.detail", "Install for"), "Muted")
        self.scope_btns = {}
        scope_box = QHBoxLayout()
        scope_box.setSpacing(0)
        self.scope_group = QButtonGroup(self)
        for sid, text in (("user", tr("grimoire.spells.storel.detail", "Just me")),
                          ("system", tr("grimoire.spells.storel.detail", "Everyone"))):
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, s=sid: self._set_scope(s))
            self.scope_group.addButton(b)
            scope_box.addWidget(b)
            self.scope_btns[sid] = b
        self.scope_btns["user"].setToolTip(tr("grimoire.spells.storel.detail", "Installed in your home: no password"))
        self.scope_btns["system"].setToolTip(tr("grimoire.spells.storel.detail", "For every account on this PC: asks "
                                                                                 "for your password"))
        segments(list(self.scope_btns.values()))
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        grid.addWidget(self.src_title, 0, 0)
        grid.addLayout(self.src_box, 0, 1, Qt.AlignmentFlag.AlignLeading)
        grid.addWidget(self.scope_title, 1, 0)
        grid.addLayout(scope_box, 1, 1, Qt.AlignmentFlag.AlignLeading)
        grid.setColumnStretch(2, 1)
        col.addLayout(grid)
        self.state = _start(_label("", "Muted", wrap=True))
        col.addWidget(self.state)

        # screenshots
        self.shots_area = QScrollArea()
        self.shots_area.setFixedHeight(SHOT_H + 18)
        self.shots_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.shots_area.setWidgetResizable(True)
        strip = QWidget()
        strip.setObjectName("Page")
        self.shots_lay = QHBoxLayout(strip)
        self.shots_lay.setContentsMargins(0, 0, 0, 0)
        self.shots_lay.setSpacing(12)
        self.shots_area.setWidget(strip)
        col.addWidget(self.shots_area)

        col.addWidget(_label(tr("grimoire.spells.storel.detail", "About"), "SectionTitle"))
        self.desc = _start(_label("", "", wrap=True))
        self.desc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.desc)

        col.addWidget(_label(tr("grimoire.spells.storel.detail", "Details"), "SectionTitle"))
        facts = QFrame()
        facts.setObjectName("Row")
        fl = QGridLayout(facts)
        fl.setContentsMargins(18, 14, 18, 14)
        fl.setHorizontalSpacing(18)
        fl.setVerticalSpacing(8)
        self.fact = {}
        for r, (key, name) in enumerate((("version", tr("grimoire.spells.storel.detail", "Version")),
                                         ("download", tr("grimoire.spells.storel.detail", "Download")),
                                         ("installed", tr("grimoire.spells.storel.detail", "Size on disk")),
                                         ("license", tr("grimoire.spells.storel.detail", "License")),
                                         ("dev", tr("grimoire.spells.storel.detail", "Developer")),
                                         ("id", tr("grimoire.spells.storel.detail", "Package")))):
            fl.addWidget(_label(name, "Muted"), r, 0, Qt.AlignmentFlag.AlignTop)
            v = _start(_label("", "", wrap=True))
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            fl.addWidget(v, r, 1)
            self.fact[key] = v
        self.home = QPushButton(tr("grimoire.spells.storel.detail", "Website"))
        self.home.setObjectName("Link")
        self.home.clicked.connect(self._website)
        fl.addWidget(self.home, len(self.fact), 0, 1, 2, Qt.AlignmentFlag.AlignLeading)
        fl.setColumnStretch(1, 1)
        col.addWidget(facts)
        col.addStretch(1)
        self.setWidget(inner)

    # ------------------------------------------------------------ showing an app
    def show_app(self, app: dict, offer_id: str = ""):
        self.app = app
        self._gen += 1
        self.verticalScrollBar().setValue(0)
        inst = self.page.inst
        mine = library.copies(app, inst)
        pick = next((o for o in app["offers"] if library.offer_id(o) == offer_id), None)
        if pick is None and mine:                        # an installed copy first
            pick = next(o for o in app["offers"] if library.offer_id(o) == mine[0]["offer"])
        self.offer = pick or self._preferred(app)
        self.name.setText(app["name"])
        self.dev.setText(app["dev"])
        self.dev.setVisible(bool(app["dev"]))
        self.summary.setText(app["summary"])
        pm = self.page.icons.get(app)
        self.icon.setPixmap((pm or self.page.icons.fallback).scaled(
            96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.desc.setText(app["desc"] or app["summary"] or tr("grimoire.spells.storel.detail",
                                                              "No description was published."))
        self.home.setVisible(app["home"].startswith(("https://", "http://")))
        self.home.setToolTip(QtGui.Qt.convertFromPlainText(app["home"]))
        self._sources()
        self._fill_shots()
        self.refresh()

    def _preferred(self, app: dict) -> dict:
        """Flathub first (sandboxed, newest), then APT, then Snap."""
        order = {"flatpak": 0, "apt": 1, "snap": 2}
        return sorted(app["offers"], key=lambda o: order.get(o["src"], 9))[0]

    def _sources(self):
        while self.src_box.count():
            w = self.src_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        btns = []
        group = QButtonGroup(self)
        for o in self.app["offers"]:
            text = library.offer_name(o)
            if o["src"] == "apt" and sum(x["src"] == "apt" for x in self.app["offers"]) > 1:
                text = f"APT · {o['pkg']}"
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setChecked(o is self.offer)
            b.clicked.connect(lambda _=False, o=o: self._pick(o))
            group.addButton(b)
            self.src_box.addWidget(b)
            btns.append(b)
        segments(btns)
        self._group = group

    def _pick(self, offer: dict):
        self.offer = offer
        self.refresh()

    def _set_scope(self, scope: str):
        self.scope = scope
        self.refresh()

    def _scopes(self) -> list[str]:
        o = self.offer
        if not o or o["src"] != "flatpak":
            return []
        conf = self.page.inst.get("remotes", {}).get(o.get("remote", ""))
        return [s for s in ("user", "system") if s in (conf or o.get("scopes") or ["user", "system"])]

    def refresh(self):
        """Buttons, state and facts for the chosen source (after a change in the queue or the installed list)."""
        if not self.app or not self.offer:
            return
        app, o = self.app, self.offer
        mine = [c for c in library.copies(app, self.page.inst) if c["offer"] == library.offer_id(o)]
        scopes = self._scopes()
        if mine and o["src"] == "flatpak":
            self.scope = mine[0]["scope"]
        elif scopes and self.scope not in scopes:
            self.scope = scopes[0]
        show_scope = o["src"] == "flatpak" and not mine and len(scopes) > 1
        self.scope_title.setVisible(show_scope)
        for s, b in self.scope_btns.items():
            b.setVisible(show_scope)
            b.setChecked(s == self.scope)
        task = self.page.queue.pending(app["key"])
        self.install_btn.setVisible(not mine and task is None)
        self.install_btn.setEnabled(bool(o["src"] != "flatpak" or scopes) and self.page.can(o["src"]))
        self.open_btn.setVisible(bool(mine) and task is None)
        self.open_btn.setEnabled(bool(mine) and bool(library.open_command(app, mine[0], self.page.inst)))
        self.remove_btn.setVisible(bool(mine) and task is None)
        keep = mine[0]["keep"] if mine else ""
        self.remove_btn.setEnabled(not keep)
        self.remove_btn.setToolTip(keep)
        self.perm_btn.setVisible(bool(mine) and o["src"] == "flatpak")
        self.queued.setVisible(task is not None)
        self.bar.setVisible(task is not None and task.state == RUNNING)
        if task is not None:
            self.queued.setText(tr("grimoire.spells.storel.detail", "Installing…") if task.action == "install" and
                                task.state == RUNNING else
                                tr("grimoire.spells.storel.detail", "Removing…") if task.state == RUNNING else
                                tr("grimoire.spells.storel.detail", "Waiting in the queue"))
            self.bar.setRange(0, 0 if task.progress < 0 else 100)
            self.bar.setValue(max(0, int(task.progress)))
        if mine:
            c = mine[0]
            where = (tr("grimoire.spells.storel.detail", "Installed {version} from {source}, just for you")
                     if c["scope"] == "user" and c["src"] == "flatpak" else
                     tr("grimoire.spells.storel.detail", "Installed {version} from {source}"))
            text = where.format(version=i18n.ltr(c["version"] or "?"), source=i18n.isolate(library.offer_name(o)))
            if keep:
                text += "  ·  " + keep
            self.state.setText(text)
        elif not self.page.can(o["src"]):
            self.state.setText(tr("grimoire.spells.storel.detail", "{tool} isn't installed on this PC.").format(
                tool=i18n.ltr({"flatpak": "flatpak", "apt": "apt-get", "snap": "snapd"}[o["src"]])))
        elif o["src"] == "flatpak" and not scopes:
            self.state.setText(tr("grimoire.spells.storel.detail", "The {remote} remote isn't set up; add it with: "
                                  "flatpak remote-add --user --if-not-exists flathub "
                                  "https://dl.flathub.org/repo/flathub.flatpakrepo").format(
                                      remote=i18n.ltr(o.get("remote", ""))))
        else:
            self.state.setText(tr("grimoire.spells.storel.detail", "Not installed"))
        self._facts()

    def _facts(self):
        o, app = self.offer, self.app
        key = f"{library.offer_id(o)}|{self.scope}"
        got = self.facts.get(key)
        if got is None:
            self.facts[key] = {}
            scope = self.scope if o["src"] == "flatpak" else ""
            POOL.start(Job(lambda: (key, _details(o, scope or "user")), self.sig.details.emit))
            got = {}
        mine = [c for c in library.copies(app, self.page.inst) if c["offer"] == library.offer_id(o)]
        version = got.get("version") or o.get("version") or (mine[0]["version"] if mine else "")
        dash = "–"
        self.fact["version"].setText(i18n.ltr(version) if version else dash)
        self.fact["download"].setText(i18n.ltr(human(got["download"])) if got.get("download") else dash)
        size = got.get("installed") or (mine[0]["size"] if mine else None)
        self.fact["installed"].setText(i18n.ltr(human(size)) if size else dash)
        self.fact["license"].setText(app["license"] or got.get("license") or dash)
        self.fact["dev"].setText(app["dev"] or got.get("publisher") or dash)
        self.fact["id"].setText(i18n.ltr(library.offer_id(o)))

    def _details(self, result):
        key, data = result
        self.facts[key] = data or {}
        if self.app and self.offer and key == f"{library.offer_id(self.offer)}|{self.scope}":
            self._facts()
            if self.offer["src"] == "snap" and data and not self.app["desc"]:
                self.desc.setText(data.get("desc") or data.get("summary") or self.desc.text())

    # ------------------------------------------------------------ screenshots
    def _fill_shots(self):
        while self.shots_lay.count():
            w = self.shots_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        shots = self.app["shots"]
        self.shots_area.setVisible(bool(shots))
        self.labels = []
        gen = self._gen
        for n, (thumb, full) in enumerate(shots):
            lab = ShotLabel()
            lab.setFixedSize(int(SHOT_H * 16 / 9), SHOT_H)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet("background: #101010; border: 1px solid #1f1f1f; border-radius: 8px; color: #4a4a4a;")
            lab.setText(tr("grimoire.spells.storel.detail", "Loading…"))
            lab.setCursor(Qt.CursorShape.PointingHandCursor)
            lab.clicked.connect(lambda n=n, full=full: self._enlarge(n, full))
            self.shots_lay.addWidget(lab)
            self.labels.append(lab)
            POOL.start(Job(lambda n=n, thumb=thumb: (gen, n, _shot(thumb)), self.sig.shot.emit))
        self.shots_lay.addStretch(1)

    def _shot(self, result):
        gen, n, img = result
        if gen != self._gen or n >= len(self.labels):
            return
        lab = self.labels[n]
        if img is None:
            lab.setText(tr("grimoire.spells.storel.detail", "Couldn't load this screenshot"))
            return
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(2)
        lab.setFixedWidth(min(int(pm.width() / 2), SHOT_H * 3))
        lab.setStyleSheet("border-radius: 8px;")
        lab.setPixmap(pm)

    def _enlarge(self, n: int, full: str):
        lab = self.labels[n] if n < len(self.labels) else None
        if lab is None or lab.pixmap() is None or lab.pixmap().isNull():
            return
        ShotDialog(self, lab.pixmap(), full).exec()

    # ------------------------------------------------------------ actions
    def _install(self):
        self.page.request_install(self.app, self.offer, self.scope)

    def _remove(self):
        mine = [c for c in library.copies(self.app, self.page.inst) if c["offer"] == library.offer_id(self.offer)]
        if mine:
            self.page.request_remove(self.app, mine[0])

    def _open(self):
        mine = [c for c in library.copies(self.app, self.page.inst) if c["offer"] == library.offer_id(self.offer)]
        if mine:
            self.page.open_app(self.app, mine[0])

    def _perms(self):
        self.page.show_permissions(self.offer["ref"].split("/")[1])

    def _website(self):
        url = QUrl(self.app["home"])
        if url.scheme() in ("https", "http"):
            QDesktopServices.openUrl(url)

