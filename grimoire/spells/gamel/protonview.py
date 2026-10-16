# SPDX-License-Identifier: GPL-3.0-or-later
"""GameL's Proton panel: GE-Proton builds (installed ones with the games Steam runs on them, the latest releases
from GitHub with Install), and Protontricks. Everything happens on a click; network and disk work run on workers.
"""
from PySide6.QtCore import QDateTime, QLocale, QObject, Qt, Signal
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                               QPushButton, QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.fsutil import human, tilde
from grimoire.glyphs import glyph
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.gamel import launch, others, proton

BAR_QSS = """
QProgressBar { background: #121212; border: 1px solid #262626; border-radius: 4px; max-height: 6px; }
QProgressBar::chunk { background: #f2f2f2; border-radius: 3px; }
"""


class _Signals(QObject):
    tools = Signal(object)        # (tools, mapping)
    releases = Signal(object)     # (releases, error)
    progress = Signal(object)     # (tag, done, total)
    installed = Signal(object)    # (tag, error, cancelled)
    removed = Signal(object)      # (display name, error)


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)        # names, paths and errors come from files and GitHub
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _row(title: str, sub: str, *controls, below: QWidget | None = None) -> QFrame:
    row = QFrame()
    row.setObjectName("Row")
    outer = QVBoxLayout(row)
    outer.setContentsMargins(18, 12, 16, 12)
    outer.setSpacing(8)
    lay = QHBoxLayout()
    lay.setSpacing(12)
    text = QVBoxLayout()
    text.setSpacing(3)
    text.addWidget(_label(title, "RowTitle", wrap=True))
    if sub:
        lab = _label(sub, "Muted", wrap=True)
        lab.setMinimumWidth(120)               # wraps instead of pushing under the buttons (long translations)
        lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        if QApplication.isRightToLeft():      # Qt can lay a mixed Arabic/Latin line out a little past its width
            lab.setContentsMargins(28, 0, 0, 0)
        text.addWidget(lab)
    lay.addLayout(text, 1)
    for c in controls:
        lay.addWidget(c, 0, Qt.AlignmentFlag.AlignVCenter)
    outer.addLayout(lay)
    if below:
        outer.addWidget(below)
    return row


def _clear(lay):
    while lay.count():
        w = lay.takeAt(0).widget()
        if w:
            w.deleteLater()


def _day(iso: str) -> str:
    d = QDateTime.fromString(iso, Qt.DateFormat.ISODate)
    if not d.isValid():
        return iso[:10]
    return QLocale().toString(d.toLocalTime().date(), QLocale.FormatType.ShortFormat)


class ProtonPanel(QScrollArea):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.sig = _Signals()
        self.tools: list[proton.Tool] = []
        self.mapping: dict = {}
        self.rels: list[proton.Release] = []
        self.rel_error = ""
        self.busy = ""                       # the tag being installed
        self._cancel = False
        self._fetching = False
        self._rows: dict[str, tuple] = {}   # tag -> (button, bar, cancel)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        inner.setStyleSheet(BAR_QSS)
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 20)
        col.setSpacing(8)
        intro = tr("grimoire.spells.gamel.protonview", "GE-Proton is a community build of Proton with extra fixes and "
                   "video codecs. Install a build here, restart Steam, then pick it for a game in Steam: right-click "
                   "the game, Properties, Compatibility. GameL never changes a game's settings.")
        col.addWidget(_label(intro, "Subtitle", wrap=True))

        self.target = QComboBox()
        self.target.setMinimumWidth(190)
        self.target_row = _row(tr("grimoire.spells.gamel.protonview", "Install into"),
                               tr("grimoire.spells.gamel.protonview", "Which Steam gets new builds"), self.target)
        col.addWidget(self.target_row)
        self.no_steam = _row(tr("grimoire.spells.gamel.protonview", "Steam isn't installed"),
                             tr("grimoire.spells.gamel.protonview", "GE-Proton builds go into Steam's "
                                "compatibilitytools.d folder; GameL found no Steam here."))
        col.addWidget(self.no_steam)

        col.addSpacing(8)
        col.addWidget(_label(tr("grimoire.spells.gamel.protonview", "Installed"), "SectionTitle"))
        self.inst_box = QVBoxLayout()
        self.inst_box.setSpacing(8)
        col.addLayout(self.inst_box)

        col.addSpacing(8)
        head = QHBoxLayout()
        head.addWidget(_label(tr("grimoire.spells.gamel.protonview", "GE-Proton releases"), "SectionTitle"), 1)
        self.refresh = QToolButton()
        self.refresh.setObjectName("Tool")
        self.refresh.setIcon(glyph("update", 18))
        self.refresh.setToolTip(tr("grimoire.spells.gamel.protonview", "Check GitHub again"))
        self.refresh.clicked.connect(lambda: self.fetch(force=True))
        head.addWidget(self.refresh)
        col.addLayout(head)
        self.rel_state = _label("", "Muted", wrap=True)
        col.addWidget(self.rel_state)
        self.rel_box = QVBoxLayout()
        self.rel_box.setSpacing(8)
        col.addLayout(self.rel_box)

        col.addSpacing(8)
        col.addWidget(_label("Protontricks", "SectionTitle"))
        self.pt_btn = QPushButton(tr("grimoire.spells.gamel.protonview", "Open Protontricks"))
        self.pt_btn.clicked.connect(self.open_protontricks)
        self.pt_row = _row("Protontricks", tr("grimoire.spells.gamel.protonview", "Runs Winetricks in a Steam game's "
                                              "Proton prefix, to add the DLLs, fonts or runtimes a game asks for. "
                                              "Opens its game picker; a game's own button is in the library."),
                           self.pt_btn)
        col.addWidget(self.pt_row)
        self.pt_missing = _row(tr("grimoire.spells.gamel.protonview", "Protontricks isn't installed"),
                               tr("grimoire.spells.gamel.protonview", "Install it from Flathub, then come back here:"),
                               below=_label("flatpak install flathub com.github.Matoking.protontricks", "Mono"))
        col.addWidget(self.pt_missing)
        col.addStretch(1)
        self.setWidget(inner)

        self.sig.tools.connect(self._tools)
        self.sig.releases.connect(self._releases)
        self.sig.progress.connect(self._progress)
        self.sig.installed.connect(self._installed)
        self.sig.removed.connect(self._removed)

    # ------------------------------------------------------------ loading
    def load(self):
        targets = proton.targets()
        keep = self.target.currentData()
        self.target.blockSignals(True)
        self.target.clear()
        for path, flat in targets:
            self.target.addItem(tr("grimoire.spells.gamel.protonview", "Steam (Flatpak)") if flat else "Steam",
                                str(path))
            self.target.setItemData(self.target.count() - 1, tilde(path), Qt.ItemDataRole.ToolTipRole)
        if keep:
            i = self.target.findData(keep)
            self.target.setCurrentIndex(max(0, i))
        self.target.blockSignals(False)
        self.target_row.setVisible(len(targets) > 1)
        self.no_steam.setVisible(not targets)
        pt = bool(others.has_protontricks())
        self.pt_row.setVisible(pt)
        self.pt_missing.setVisible(not pt)
        self.reload_tools()
        self.fetch()

    def reload_tools(self):
        POOL.start(Job(lambda: (proton.installed(), proton.mapping()), self.sig.tools.emit))

    def fetch(self, force=False):
        if self._fetching:
            return
        self._fetching = True
        self.refresh.setEnabled(False)
        if not self.rels:
            self.rel_state.setText(tr("grimoire.spells.gamel.protonview", "Looking at GitHub…"))

        def work():
            try:
                return proton.releases(force), ""
            except proton.ProtonError as e:
                return None, str(e)
        POOL.start(Job(work, self.sig.releases.emit))

    def _tools(self, result):
        self.tools, self.mapping = result
        _clear(self.inst_box)
        for t in self.tools:
            default, games = proton.used_by(t, self.page.games, self.mapping)
            bits = []
            if t.steam:
                bits.append(tr("grimoire.spells.gamel.protonview", "Installed and updated by Steam"))
            else:
                bits.append(i18n.ltr(tilde(t.path)))
            if default:
                bits.append(tr("grimoire.spells.gamel.protonview", "Steam's default for every game"))
            if games:
                bits.append(tr("grimoire.spells.gamel.protonview", "Used by: {games}").format(
                    games=", ".join(i18n.isolate(g) for g in games)))
            elif not default:
                bits.append(tr("grimoire.spells.gamel.protonview", "No game is set to it"))
            controls = []
            if not t.steam:
                rm = QPushButton(tr("grimoire.spells.gamel.protonview", "Remove"))
                rm.clicked.connect(lambda _=False, tool=t: self.remove(tool))
                rm.setEnabled(not self.busy)
                controls.append(rm)
            self.inst_box.addWidget(_row(t.display, " · ".join(bits), *controls))
        if not self.tools:
            self.inst_box.addWidget(_label(tr("grimoire.spells.gamel.protonview", "No Proton builds yet."), "Muted"))
        self._fill_releases()

    def _releases(self, result):
        self._fetching = False
        self.refresh.setEnabled(True)
        rels, err = result
        if rels is not None:
            self.rels = rels
        self.rel_error = err
        self._fill_releases()

    def _have(self, tag: str) -> bool:
        return any(not t.steam and (t.name == tag or t.display == tag or t.path.rstrip("/").endswith("/" + tag))
                   for t in self.tools)

    def _fill_releases(self):
        _clear(self.rel_box)
        self._rows = {}
        if self.rel_error:
            self.rel_state.setText(self.rel_error)
        elif not self.rels and not self._fetching:
            self.rel_state.setText(tr("grimoire.spells.gamel.protonview", "GitHub listed no releases."))
        else:
            self.rel_state.setText("")
        self.rel_state.setVisible(bool(self.rel_state.text()))
        for i, r in enumerate(self.rels):
            sub = tr("grimoire.spells.gamel.protonview", "Released {date} · {size}").format(
                date=_day(r.date), size=i18n.ltr(human(r.size)) if r.size else "–")
            if i == 0:
                sub += " · " + tr("grimoire.spells.gamel.protonview", "Latest")
            btn = QPushButton()
            if r.tag == self.busy:
                btn.setText(tr("grimoire.spells.gamel.protonview", "Installing…"))
                btn.setEnabled(False)
            elif self._have(r.tag):
                btn.setText(tr("grimoire.spells.gamel.protonview", "Installed"))
                btn.setEnabled(False)
            else:
                btn.setText(tr("grimoire.spells.gamel.protonview", "Install"))
                btn.setEnabled(not self.busy and self.target.count() > 0)
                btn.clicked.connect(lambda _=False, rel=r: self.install(rel))
            if i == 0 and btn.isEnabled():
                btn.setObjectName("Primary")
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setRange(0, 1000)
            bar.setVisible(r.tag == self.busy)
            stop = QPushButton(tr("grimoire.spells.gamel.protonview", "Cancel"))
            stop.setVisible(r.tag == self.busy)
            stop.clicked.connect(self.cancel)
            holder = QWidget()
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.addWidget(bar, 1)
            hl.addWidget(stop)
            holder.setVisible(r.tag == self.busy)
            self._rows[r.tag] = (btn, bar, holder)
            self.rel_box.addWidget(_row(r.tag, sub, btn, below=holder))

    # ------------------------------------------------------------ install / remove
    def install(self, rel: proton.Release):
        if self.busy or not self.target.count():
            return
        from pathlib import Path
        target = Path(self.target.currentData())
        self.busy, self._cancel = rel.tag, False
        self._fill_releases()
        self.page.say(tr("grimoire.spells.gamel.protonview", "Downloading {name}…").format(name=i18n.ltr(rel.tag)))
        emit = self.sig.progress.emit

        def work():
            try:
                proton.install(rel, target, lambda d, t: emit((rel.tag, d, t)), lambda: self._cancel)
                return rel.tag, "", False
            except proton.Cancelled:
                return rel.tag, "", True
            except (proton.ProtonError, OSError) as e:
                return rel.tag, str(e), False
        POOL.start(Job(work, self.sig.installed.emit))

    def cancel(self):
        self._cancel = True

    def _progress(self, result):
        tag, done, total = result
        row = self._rows.get(tag)
        if row:
            btn, bar, _ = row
            bar.setValue(int(done * 1000 / total) if total else 0)
            btn.setText(tr("grimoire.spells.gamel.protonview", "{done} of {total}").format(
                done=i18n.ltr(human(done)), total=i18n.ltr(human(total))) if total else human(done))

    def _installed(self, result):
        tag, err, cancelled = result
        self.busy = ""
        if cancelled:
            self.page.say(tr("grimoire.spells.gamel.protonview", "Stopped installing {name}.").format(
                name=i18n.ltr(tag)))
        elif err:
            self.page.say(tr("grimoire.spells.gamel.protonview", "Couldn't install {name}: {error}").format(
                name=i18n.ltr(tag), error=err))
        else:
            self.page.say(tr("grimoire.spells.gamel.protonview", "{name} is installed. Restart Steam, then pick it in "
                             "a game's Properties, Compatibility.").format(name=i18n.ltr(tag)))
        self.reload_tools()

    def remove(self, tool: proton.Tool):
        default, games = proton.used_by(tool, self.page.games, self.mapping)
        text = tr("grimoire.spells.gamel.protonview", "Move {name} to the Trash?").format(name=i18n.ltr(tool.display))
        if games or default:
            text += "\n\n" + tr("grimoire.spells.gamel.protonview", "Steam is set to run some games with it; they "
                                "need another tool picked afterwards.")
        if QMessageBox.question(self, tr("grimoire.spells.gamel.protonview", "Remove"), text) != \
                QMessageBox.StandardButton.Yes:
            return

        def work():
            try:
                proton.remove(tool)
                return tool.display, ""
            except proton.ProtonError as e:
                return tool.display, str(e)
        POOL.start(Job(work, self.sig.removed.emit))

    def _removed(self, result):
        name, err = result
        if err:
            self.page.say(tr("grimoire.spells.gamel.protonview", "Couldn't remove {name}: {error}").format(
                name=i18n.ltr(name), error=err))
        else:
            self.page.say(tr("grimoire.spells.gamel.protonview", "{name} is in the Trash.").format(name=i18n.ltr(name)))
        self.reload_tools()

    def open_protontricks(self):
        try:
            launch.protontricks()
        except (OSError, ValueError) as e:
            self.page.say(tr("grimoire.spells.gamel.protonview", "Couldn't open Protontricks: {error}").format(error=e))
            return
        self.page.say(tr("grimoire.spells.gamel.protonview", "Opening Protontricks…"))
