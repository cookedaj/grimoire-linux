# SPDX-License-Identifier: GPL-3.0-or-later
"""CloudL page: your rclone remotes (Google Drive, OneDrive, Dropbox…) as folders in ~/Cloud.

Drives: one row per remote with Mount/Unmount, Open in VaultL, space used/free and what is still uploading.
Add a drive: rclone's own browser sign-in, started only by the Sign in button. Activity: the mount's log.

Local state (remotes, mounts, services, the mounts' upload queues) is read every 3 s on a worker thread while the
page is on screen; space is asked of the service only on show and every few minutes, also off the UI thread.
"""
import os
import subprocess
import time

from PySide6.QtCore import QObject, QProcess, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QToolButton,
                               QVBoxLayout, QWidget)

from grimoire.fsutil import human
from grimoire.glyphs import glyph
from grimoire.i18n import isolate, ltr, rtl, tr, tr_noop
from grimoire.jobs import POOL, Job
from grimoire.paths import command
from grimoire.spells.cloudl import rclone

PANELS = [("drives", tr_noop("grimoire.spells.cloudl.page", "Drives"), "cloud"),
          ("add", tr_noop("grimoire.spells.cloudl.page", "Add a drive"), "plus"),
          ("activity", tr_noop("grimoire.spells.cloudl.page", "Activity"), "list")]
POLL_MS = 3000
ABOUT_EVERY = 300                 # seconds between asking a service for its space again
SIGN_IN_LIMIT = 10 * 60 * 1000    # a sign-in left open this long is stopped


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def _lead(text: str) -> str:
    """A line that may start with a name or a service in Latin letters still reads right to left in ar/ur."""
    return "\u200f" + text if text and rtl() else text


def _cloud_path(name: str) -> str:
    return ltr(f"~/Cloud/{name}")


class _Signals(QObject):
    polled = Signal(object)
    spaced = Signal(object)        # (name, {total, used, free} | error str)
    acted = Signal(object)         # (what, message, ok)
    logged = Signal(object)


class UsageBar(QWidget):
    """A thin outlined bar, filled white for the used part. Always fills left to right, like other meters."""

    def __init__(self):
        super().__init__()
        self.frac = None
        self.setFixedHeight(6)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_frac(self, frac):
        self.frac = frac
        self.setVisible(frac is not None)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QColor("#2a2a2a"))
        p.setBrush(QColor("#0b0b0b"))
        p.drawRoundedRect(r, 3, 3)
        if self.frac:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#e8e8e8"))
            p.drawRoundedRect(QRectF(r.x(), r.y(), max(r.height(), r.width() * min(1.0, self.frac)), r.height()), 3, 3)
        p.end()


class DriveRow(QFrame):
    """One remote: name, type and state, the space bar, the sync line, and its buttons."""

    def __init__(self, page, remote: dict):
        super().__init__()
        self.page, self.name, self.kind = page, remote["name"], remote["type"]
        self.mounted = False
        self.working = ""                  # "Mounting…"/"Unmounting…" while that runs
        self.setObjectName("Row")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 12, 12)
        lay.setSpacing(12)
        icon = QLabel()
        icon.setPixmap(glyph("cloud", 24).pixmap(24, 24))
        icon.setFixedWidth(28)
        lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(5)
        self.title = _label(_lead(self.name), "RowTitle")
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        text.addWidget(self.title)
        self.sub = _label("", "Muted")
        self.sub.setTextFormat(Qt.TextFormat.PlainText)
        self.sub.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text.addWidget(self.sub)
        self.bar = UsageBar()
        self.bar.set_frac(None)
        text.addWidget(self.bar)
        self.space = _label("", "Muted")
        self.space.setTextFormat(Qt.TextFormat.PlainText)
        self.space.hide()
        text.addWidget(self.space)
        self.sync = _label("", "Muted", wrap=True)
        self.sync.setTextFormat(Qt.TextFormat.PlainText)       # carries rclone's messages
        self.sync.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.sync.hide()
        text.addWidget(self.sync)
        lay.addLayout(text, 1)

        self.toggle = QPushButton()
        self.toggle.clicked.connect(lambda: page.toggle_mount(self))
        fm = self.toggle.fontMetrics()           # same width whatever it says, so the rows line up
        self.toggle.setMinimumWidth(36 + max(fm.horizontalAdvance(t) for t in (
            tr("grimoire.spells.cloudl.page", "Mount"), tr("grimoire.spells.cloudl.page", "Unmount"),
            tr("grimoire.spells.cloudl.page", "Mounting…"), tr("grimoire.spells.cloudl.page", "Unmounting…"))))
        self.open = QPushButton(glyph("vault", 16), " " + tr("grimoire.spells.cloudl.page", "Open"))
        self.open.setToolTip(tr("grimoire.spells.cloudl.page", "Open {path} in VaultL").format(
            path=_cloud_path(self.name)))
        self.open.clicked.connect(lambda: page.open_in_vaultl(self.name))
        more = QToolButton()
        more.setObjectName("Tool")
        more.setIcon(glyph("sliders", 18))
        more.setIconSize(QSize(18, 18))
        more.setToolTip(tr("grimoire.spells.cloudl.page", "More"))
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(more)
        self.at_login = menu.addAction(tr("grimoire.spells.cloudl.page", "Mount at login"))
        self.at_login.setCheckable(True)
        self.at_login.triggered.connect(lambda on: page.set_at_login(self, on))
        menu.addAction(tr("grimoire.spells.cloudl.page", "Check space again"),
                       lambda: page.ask_space(self.name, force=True))
        menu.addAction(tr("grimoire.spells.cloudl.page", "Show activity"), lambda: page.show_log(self.name))
        menu.addSeparator()
        self.forget = menu.addAction(tr("grimoire.spells.cloudl.page", "Forget mount"), lambda: page.forget(self))
        menu.addAction(tr("grimoire.spells.cloudl.page", "Remove from rclone…"), lambda: page.remove(self))
        more.setMenu(menu)
        for w in (self.toggle, self.open, more):
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignTop)

    def show_state(self, mounted: bool, state: dict, stats: dict | None):
        self.mounted = mounted
        self.toggle.setText(self.working or (tr("grimoire.spells.cloudl.page", "Unmount") if mounted else
                                             tr("grimoire.spells.cloudl.page", "Mount")))
        self.toggle.setEnabled(not self.working)
        self.toggle.setObjectName("" if mounted else "Primary")
        self.toggle.style().unpolish(self.toggle)
        self.toggle.style().polish(self.toggle)
        self.open.setEnabled(mounted)
        self.at_login.setEnabled(state["written"])
        self.at_login.setChecked(state["enabled"])
        self.forget.setEnabled(state["written"])
        bits = [rclone.type_label(self.kind)]
        if mounted:
            bits.append(tr("grimoire.spells.cloudl.page", "Mounted at {path}").format(path=_cloud_path(self.name)))
        elif state["active"] in ("activating", "reloading"):
            bits.append(tr("grimoire.spells.cloudl.page", "Mounting…"))
        elif state["active"] == "failed":
            bits.append(tr("grimoire.spells.cloudl.page", "Mount failed"))
        else:
            bits.append(tr("grimoire.spells.cloudl.page", "Not mounted"))
        if state["enabled"]:
            bits.append(tr("grimoire.spells.cloudl.page", "at login"))
        self.sub.setText(_lead(" · ".join(bits)))
        self.sync.setText(_lead(self.page.sync_text(self.name, mounted, state, stats)))
        self.sync.setVisible(bool(self.sync.text()))

    def show_space(self, space):
        if isinstance(space, str):
            self.bar.set_frac(None)
            self.space.setText(_lead(space))
            self.space.show()
            return
        total, used, free = space.get("total"), space.get("used"), space.get("free")
        if total:
            self.bar.set_frac((used if used is not None else total - (free or 0)) / total)
            self.space.setText(tr("grimoire.spells.cloudl.page", "{used} used of {total} · {free} free").format(
                used=ltr(human(used or 0)), total=ltr(human(total)), free=ltr(human(free or 0))))
        elif used is not None:
            self.bar.set_frac(None)
            self.space.setText(tr("grimoire.spells.cloudl.page", "{used} used").format(used=ltr(human(used))))
        else:
            self.bar.set_frac(None)
            self.space.setText("")
        self.space.setVisible(bool(self.space.text()))


# ---------------------------------------------------------------- drives
class DrivesPanel(QScrollArea):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 20)
        col.setSpacing(10)
        col.addWidget(_label(tr("grimoire.spells.cloudl.page",
                                "Each drive is a folder in {path} that every app can open. Files you open are "
                                "kept in a local cache, so they open fast; changes upload in the background.").format(
            path=ltr("~/Cloud")), "Muted", wrap=True))
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        col.addLayout(self.body)
        self.empty = QFrame()
        el = QVBoxLayout(self.empty)
        el.setContentsMargins(0, 18, 0, 0)
        el.setSpacing(12)
        el.addWidget(_label(tr("grimoire.spells.cloudl.page", "No cloud drives yet."), "SectionTitle"))
        el.addWidget(_label(tr("grimoire.spells.cloudl.page",
                               "Sign in to Google Drive, OneDrive or Dropbox and it shows up here."), "Muted",
                            wrap=True))
        add = QPushButton(glyph("plus", 16), " " + tr("grimoire.spells.cloudl.page", "Add a drive"))
        add.setObjectName("Primary")
        add.clicked.connect(lambda: page.show_panel("add"))
        el.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        self.empty.hide()
        col.addWidget(self.empty)
        col.addStretch(1)
        self.setWidget(inner)
        self.keys = None
        self.rows: dict[str, DriveRow] = {}

    def set_data(self, data: dict):
        keys = tuple((r["name"], r["type"]) for r in data["remotes"])
        if keys != self.keys:
            self.keys = keys
            while self.body.count():
                w = self.body.takeAt(0).widget()
                if w:
                    w.deleteLater()
            self.rows = {}
            for r in data["remotes"]:
                row = DriveRow(self.page, r)
                self.body.addWidget(row)
                self.rows[r["name"]] = row
                if r["name"] in self.page.space:
                    row.show_space(self.page.space[r["name"]][1])
        self.empty.setVisible(not data["remotes"])
        for name, row in self.rows.items():
            row.show_state(name in data["mounted"], data["states"][name], data["stats"].get(name))


# ---------------------------------------------------------------- add a drive
class AddPanel(QScrollArea):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.kind = rclone.SERVICES[0][0]
        self.proc: QProcess | None = None
        self.before: set[str] = set()
        self.signing = ""
        self.cancelled = False
        self.url = ""
        self.output: list[str] = []
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 12, 20)
        col.setSpacing(12)
        col.addWidget(_label(tr("grimoire.spells.cloudl.page",
                                "Pick a service and press Sign in. Your browser opens the service's own sign-in "
                                "page; once you allow access, rclone receives the key and keeps it in its config "
                                "file. CloudL never reads that file or sees your password."), "Muted", wrap=True))
        row = QHBoxLayout()
        row.setSpacing(0)
        self.buttons = {}
        for kind, label, _ in rclone.SERVICES:
            b = QPushButton(label)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=kind: self.pick(k))
            row.addWidget(b)
            self.buttons[kind] = b
        from grimoire.widgets import segments
        segments(list(self.buttons.values()))
        row.addStretch(1)
        col.addLayout(row)
        nr = QHBoxLayout()
        nr.setSpacing(10)
        nr.addWidget(_label(tr("grimoire.spells.cloudl.page", "Name"), ""))
        self.name = QLineEdit()
        self.name.setMaxLength(64)
        self.name.setMaximumWidth(280)
        self.name.textChanged.connect(self._check)
        self.name.returnPressed.connect(self.start)
        nr.addWidget(self.name)
        self.where = _label("", "Muted")
        nr.addWidget(self.where, 1)
        col.addLayout(nr)
        self.problem = _label("", "Muted", wrap=True)
        col.addWidget(self.problem)
        br = QHBoxLayout()
        self.go = QPushButton(tr("grimoire.spells.cloudl.page", "Sign in"))
        self.go.setObjectName("Primary")
        self.go.clicked.connect(self.start)
        br.addWidget(self.go)
        self.again = QPushButton(tr("grimoire.spells.cloudl.page", "Open the sign-in page again"))
        self.again.clicked.connect(lambda: self.url and QDesktopServices.openUrl(QUrl(self.url)))
        self.again.hide()
        br.addWidget(self.again)
        self.cancel = QPushButton(tr("grimoire.spells.cloudl.page", "Cancel"))
        self.cancel.clicked.connect(self.stop)
        self.cancel.hide()
        br.addWidget(self.cancel)
        br.addStretch(1)
        col.addLayout(br)
        self.state = _label("", "Muted", wrap=True)
        self.state.setTextFormat(Qt.TextFormat.PlainText)
        col.addWidget(self.state)

        col.addSpacing(14)
        col.addWidget(_label(tr("grimoire.spells.cloudl.page", "OTHER SERVICES"), "NavSection"))
        col.addWidget(_label(tr("grimoire.spells.cloudl.page",
                                "rclone knows many more: pCloud, MEGA, Proton Drive, Nextcloud, SFTP, WebDAV and "
                                "others. Set one up with rclone's own questions in TerminalL; it shows up under "
                                "Drives when you're done."), "Muted", wrap=True))
        term = QPushButton(glyph("terminall", 16), " " + tr("grimoire.spells.cloudl.page",
                                                             "Open rclone config in TerminalL"))
        term.clicked.connect(page.rclone_config)
        col.addWidget(term, 0, Qt.AlignmentFlag.AlignLeft)
        col.addSpacing(8)
        col.addWidget(_label(tr("grimoire.spells.cloudl.page",
                                "Plasma's own Google Drive support (kio-gdrive: gdrive:/ in Dolphin, set up in "
                                "System Settings → Online Accounts) works too. CloudL uses rclone instead: a real "
                                "folder every app can use, and OneDrive and Dropbox as well."), "Muted", wrap=True))
        col.addStretch(1)
        self.setWidget(inner)
        self._limit = QTimer(self, singleShot=True, interval=SIGN_IN_LIMIT, timeout=self._timed_out)
        self.pick(self.kind)

    def taken(self) -> set[str]:
        if self.proc is not None:
            return self.before                 # rclone writes the new remote before the sign-in finishes
        return {r["name"] for r in (self.page.data or {}).get("remotes", [])}

    def pending(self) -> str:
        """The remote a running sign-in is making (hidden under Drives until it's done)."""
        return self.signing if self.proc is not None else ""

    def pick(self, kind: str):
        self.kind = kind
        for k, b in self.buttons.items():
            b.setChecked(k == kind)
        if self.proc is None:
            base = next(s for k, _, s in rclone.SERVICES if k == kind)
            self.name.setText(rclone.suggest_name(base, self.taken()))

    def _check(self) -> bool:
        name = self.name.text().strip()
        problem = ""
        if not name:
            problem = tr("grimoire.spells.cloudl.page", "Give the drive a name")
        elif not rclone.valid_name(name):
            problem = tr("grimoire.spells.cloudl.page", "Use letters, digits, spaces and . _ + @ - in the name")
        elif name in self.taken():
            problem = tr("grimoire.spells.cloudl.page", "rclone already has a drive called {name}").format(
                name=isolate(name))
        self.problem.setText(problem)
        self.problem.setVisible(bool(problem))
        self.where.setText(tr("grimoire.spells.cloudl.page", "mounts at {path}").format(path=_cloud_path(name))
                           if name and not problem else "")
        self.go.setEnabled(not problem and self.proc is None and rclone.available())
        return not problem

    def start(self):
        if self.proc is not None or not self._check():
            return
        name = self.name.text().strip()
        label = next(lab for k, lab, _ in rclone.SERVICES if k == self.kind)
        self.before = self.taken()
        self.signing, self.cancelled = name, False
        self.output, self.url = [], ""
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.setStandardInputFile(QProcess.nullDevice())
        self.proc.readyRead.connect(self._read)
        self.proc.finished.connect(lambda code, _s, n=name: self._done(n, code))
        self.proc.errorOccurred.connect(lambda _e, n=name: self.proc and self.proc.state() ==
                                        QProcess.ProcessState.NotRunning and self._done(n, -1))
        argv = rclone.sign_in_command(name, self.kind)
        self.proc.start(argv[0], argv[1:])
        self._limit.start()
        self._busy(True)
        self.state.setText(tr("grimoire.spells.cloudl.page",
                              "Your browser is opening {service}'s sign-in page. Sign in and allow access there; "
                              "this page carries on by itself.").format(service=label))

    def _busy(self, on: bool):
        self.cancel.setVisible(on)
        self.again.setVisible(on and bool(self.url))
        self.name.setEnabled(not on)
        for b in self.buttons.values():
            b.setEnabled(not on)
        self.go.setEnabled(not on and self._check())

    def _read(self):
        if not self.proc:
            return
        for line in bytes(self.proc.readAll()).decode(errors="replace").splitlines():
            url = rclone.auth_url(line)
            if url and not self.url:
                self.url = url
                self.again.show()
            safe = rclone.scrub(line)
            if safe:
                self.output.append(safe)
                self.output = self.output[-40:]

    def stop(self):
        if self.proc is not None:
            self.cancelled = True
            self.proc.kill()            # _done follows and removes a half-made remote

    def _timed_out(self):
        if self.proc is not None:
            self.output.append(tr("grimoire.spells.cloudl.page", "Stopped waiting after 10 minutes"))
            self.proc.kill()

    def _done(self, name: str, code: int):
        if self.proc is None:
            return
        self._read()
        proc, self.proc = self.proc, None
        proc.deleteLater()
        self._limit.stop()
        self._busy(False)
        ok = code == 0 and proc.exitStatus() == QProcess.ExitStatus.NormalExit
        if ok:
            self.state.setText("")
            self.page.added(name)
            return
        before = set(self.before)
        errors = [ln for ln in self.output if "error" in ln.lower() or "failed" in ln.lower()]
        why = errors[-1] if errors else (self.output[-1] if self.output else "")
        if self.cancelled:
            self.state.setText(tr("grimoire.spells.cloudl.page", "Sign-in cancelled."))
        elif why:
            self.state.setText(tr("grimoire.spells.cloudl.page", "Sign-in didn't finish. rclone said: {message}")
                               .format(message=isolate(why)))
        else:
            self.state.setText(tr("grimoire.spells.cloudl.page", "Sign-in didn't finish."))

        def tidy():                           # a remote this sign-in left half made goes again (config only)
            try:
                if name not in before and name in {r["name"] for r in rclone.remotes()}:
                    rclone.RUN(rclone.rclone() or "rclone", "config", "delete", name, "--ask-password=false")
            except (OSError, subprocess.SubprocessError):
                pass
            return None
        POOL.start(Job(tidy, lambda _r: None))
        self.page.refresh()


# ---------------------------------------------------------------- activity
class ActivityPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        col.addWidget(_label(tr("grimoire.spells.cloudl.page",
                                "What each mount did lately: uploads, changes it noticed online, and errors. "
                                "Newest at the bottom."), "Muted", wrap=True))
        top = QHBoxLayout()
        self.pick = QComboBox()
        self.pick.setMinimumWidth(220)
        self.pick.currentIndexChanged.connect(lambda _i: self.load())
        top.addWidget(self.pick)
        self.summary = _label("", "Muted")
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        top.addWidget(self.summary, 1)
        col.addLayout(top)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLayoutDirection(Qt.LayoutDirection.LeftToRight)       # rclone's log is English, left to right
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log.setStyleSheet('font-family: "IBM Plex Mono"; font-size: 11px; background: #080808; '
                               'border: 1px solid #1c1c1c; border-radius: 6px;')
        col.addWidget(self.log, 1)
        self.timer = QTimer(self, interval=5000, timeout=self.load)
        self._busy = False

    def set_names(self, names: list[str]):
        if [self.pick.itemData(i) for i in range(self.pick.count())] == names:
            return
        cur = self.pick.currentData()
        self.pick.blockSignals(True)
        self.pick.clear()
        for n in names:
            self.pick.addItem(n, n)
        if cur in names:
            self.pick.setCurrentIndex(names.index(cur))
        self.pick.blockSignals(False)
        if self.isVisible():
            self.load()

    def select(self, name: str):
        i = self.pick.findData(name)
        if i >= 0:
            self.pick.setCurrentIndex(i)

    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start()
        self.load()

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def load(self):
        name = self.pick.currentData()
        if not name:
            self.log.setPlainText("")
            self.summary.setText(tr("grimoire.spells.cloudl.page", "No drives yet"))
            return
        if self._busy:
            return
        self._busy = True

        def work():
            try:
                return name, rclone.journal(name, 300) if rclone.unit_path(name).exists() else None
            except (OSError, subprocess.SubprocessError) as err:
                return name, str(err)
        POOL.start(Job(work, self.page.sig.logged.emit))

    def show_lines(self, result):
        self._busy = False
        name, lines = result
        if name != self.pick.currentData():
            return
        if lines is None:
            self.summary.setText(tr("grimoire.spells.cloudl.page", "Not mounted by CloudL yet"))
            self.log.setPlainText("")
            return
        if isinstance(lines, str):
            self.summary.setText(lines)
            return
        errors = sum(e["priority"] <= 3 for e in lines)
        self.summary.setText(tr("grimoire.spells.cloudl.page", "%n error(s) in the last lines", n=errors)
                             if errors else tr("grimoire.spells.cloudl.page", "No errors"))
        text = "\n".join(f"{time.strftime('%H:%M:%S', time.localtime(e['time'] / 1e6))}  "
                         f"{'ERROR  ' if e['priority'] <= 3 else ''}{e['message']}" for e in lines)
        bar = self.log.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        if text != self.log.toPlainText():
            keep = bar.value()
            self.log.setPlainText(text)
            bar.setValue(bar.maximum() if at_end else keep)


# ---------------------------------------------------------------- the page
class CloudLPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.sig = _Signals()
        self.data: dict | None = None
        self.space: dict[str, tuple[float, object]] = {}     # name → (when asked, result)
        self._asking: set[str] = set()
        self._busy = False

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        nav = QFrame()
        nav.setObjectName("SubNav")
        nav.setMinimumWidth(210)
        nav.setMaximumWidth(300)
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(12, 26, 12, 16)
        nl.setSpacing(2)
        nl.addWidget(_label("CloudL", "Title"))
        nl.addSpacing(12)
        nl.addWidget(_label(tr("grimoire.spells.cloudl.page", "CLOUD"), "NavSection"))
        self.nav = {}
        for pid, name, icon in PANELS:
            b = QPushButton(glyph(icon, 18), "  " + tr("grimoire.spells.cloudl.page", name))
            b.setObjectName("SubNavItem")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, p=pid: self.show_panel(p))
            nl.addWidget(b)
            self.nav[pid] = b
        nl.addStretch(1)
        self.foot = _label("", "Tiny", wrap=True)
        self.foot.setTextFormat(Qt.TextFormat.PlainText)
        nl.addWidget(self.foot)
        root.addWidget(nav)

        right = QVBoxLayout()
        right.setContentsMargins(32, 26, 32, 18)
        right.setSpacing(14)
        self.heading = _label("", "PageHeading")
        right.addWidget(self.heading)
        self.stack = QStackedWidget()
        self.panels = {"drives": DrivesPanel(self), "add": AddPanel(self), "activity": ActivityPanel(self)}
        for p in self.panels.values():
            self.stack.addWidget(p)
        self.missing = _label(tr("grimoire.spells.cloudl.page",
                                 "CloudL works through rclone, which isn't installed. Install it with:\n\n"
                                 "sudo apt install rclone fuse3"), "Muted", wrap=True)
        self.missing.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.missing.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.stack.addWidget(self.missing)
        right.addWidget(self.stack, 1)
        self.toast = _label("", "Toast", wrap=True)
        self.toast.setTextFormat(Qt.TextFormat.PlainText)
        self.toast.hide()
        right.addWidget(self.toast)
        self._toast_timer = QTimer(self, singleShot=True, interval=8000, timeout=self.toast.hide)
        root.addLayout(right, 1)

        self.sig.polled.connect(self._polled)
        self.sig.spaced.connect(self._spaced)
        self.sig.acted.connect(self._acted)
        self.sig.logged.connect(self.panels["activity"].show_lines)
        self.timer = QTimer(self, interval=POLL_MS, timeout=self.refresh)
        QShortcut(QKeySequence("F5"), self, self._refresh_all)
        QShortcut(QKeySequence("Ctrl+N"), self, lambda: self.show_panel("add"))
        self.show_panel("drives")

    # ------------------------------------------------------------ reading
    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start()
        self.refresh()

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def _refresh_all(self):
        self.space.clear()
        self.refresh()

    def refresh(self):
        if self._busy:
            return
        if not rclone.available():
            self.stack.setCurrentWidget(self.missing)
            self.foot.setText("")
            return
        if self.stack.currentWidget() is self.missing:
            self.show_panel("drives")
        self._busy = True

        def work():
            try:
                remotes = rclone.remotes()
                mounted = rclone.mounts()
                names = [r["name"] for r in remotes]
                up = {n for n in names if str(rclone.mountpoint(n)) in mounted}
                states = {n: rclone.service_state(n) for n in names}
                stats = {n: rclone.vfs_stats(n) for n in up}
                errors = {n: rclone.last_error(n) for n in names if states[n]["active"] == "failed"}
                return {"remotes": remotes, "mounted": up, "states": states, "stats": stats, "errors": errors}
            except (OSError, subprocess.SubprocessError, ValueError) as err:
                return {"error": str(err)}
        POOL.start(Job(work, self.sig.polled.emit))

    def _polled(self, data: dict):
        self._busy = False
        if "error" in data:
            self.foot.setText(tr("grimoire.spells.cloudl.page", "rclone didn't answer: {error}").format(
                error=data["error"]))
            data = {"remotes": [], "mounted": set(), "states": {}, "stats": {}, "errors": {}}
        else:
            self.foot.setText(_lead(rclone.status_line_from(len(data["remotes"]), len(data["mounted"]))))
        pending = self.panels["add"].pending()
        if pending:
            data["remotes"] = [r for r in data["remotes"] if r["name"] != pending]
            data["mounted"].discard(pending)
        self.data = data
        self.panels["drives"].set_data(data)
        self.panels["activity"].set_names([r["name"] for r in data["remotes"]])
        add = self.panels["add"]
        if add.proc is None and not add.name.text().strip():
            add.pick(add.kind)
        add._check()
        if self.isVisible():
            for r in data["remotes"]:
                self.ask_space(r["name"])

    def ask_space(self, name: str, force=False):
        when = self.space.get(name, (0, None))[0]
        if name in self._asking or (not force and time.monotonic() - when < ABOUT_EVERY):
            return
        self._asking.add(name)

        def work():
            try:
                return name, rclone.about(name)
            except (OSError, subprocess.SubprocessError, ValueError) as err:
                return name, tr("grimoire.spells.cloudl.page", "Space unknown: {reason}").format(reason=str(err))
        POOL.start(Job(work, self.sig.spaced.emit))

    def _spaced(self, result):
        name, space = result
        self._asking.discard(name)
        self.space[name] = (time.monotonic(), space)
        row = self.panels["drives"].rows.get(name)
        if row:
            row.show_space(space)

    def sync_text(self, name: str, mounted: bool, state: dict, stats: dict | None) -> str:
        if state["active"] == "failed":
            err = (self.data or {}).get("errors", {}).get(name, "")
            return tr("grimoire.spells.cloudl.page", "rclone stopped: {error}").format(error=err) if err else \
                tr("grimoire.spells.cloudl.page", "rclone stopped. See Activity for why")
        if not mounted or stats is None:
            return ""
        bits = []
        if stats["uploading"] or stats["queued"]:
            bits.append(tr("grimoire.spells.cloudl.page", "Uploading %n file(s)", n=stats["uploading"] +
                           stats["queued"]))
        if stats["errored"]:
            bits.append(tr("grimoire.spells.cloudl.page", "%n file(s) couldn't upload, see Activity",
                           n=stats["errored"]))
        if not bits:
            bits.append(tr("grimoire.spells.cloudl.page", "Up to date"))
        if stats["cached"]:
            bits.append(tr("grimoire.spells.cloudl.page", "{size} cached on this PC").format(
                size=ltr(human(stats["cached"]))))
        return " · ".join(bits)

    # ------------------------------------------------------------ navigation
    def show_panel(self, pid: str):
        for p, b in self.nav.items():
            b.setChecked(p == pid)
        self.heading.setText(tr("grimoire.spells.cloudl.page", next(n for p, n, _ in PANELS if p == pid)))
        self.stack.setCurrentWidget(self.panels[pid])
        if pid == "add":
            self.panels["add"].name.setFocus()

    def show_log(self, name: str):
        self.panels["activity"].select(name)
        self.show_panel("activity")

    # ------------------------------------------------------------ actions
    def act(self, what: str, fn, done_msg: str = ""):
        def work():
            try:
                fn()
                return what, done_msg, True
            except (OSError, ValueError, subprocess.SubprocessError) as err:
                return what, str(err), False
        POOL.start(Job(work, self.sig.acted.emit))

    def _acted(self, result):
        what, msg, ok = result
        row = self.panels["drives"].rows.get(what)
        if row:
            row.working = ""
        what = isolate(what)
        if ok:
            if msg:
                self.say(msg)
        else:
            self.say(tr("grimoire.spells.cloudl.page", "{what}: {message}").format(what=what, message=msg))
        self.refresh()

    def toggle_mount(self, row: DriveRow):
        name = row.name
        if row.mounted:
            stats = (self.data or {}).get("stats", {}).get(name) or {}
            waiting = stats.get("uploading", 0) + stats.get("queued", 0)
            if waiting and QMessageBox.question(
                    self, "CloudL", tr("grimoire.spells.cloudl.page",
                                       "%n file(s) haven't finished uploading. They stay in the cache and upload the "
                                       "next time this drive is mounted. Unmount now?", n=waiting)) \
                    != QMessageBox.StandardButton.Yes:
                return
            row.working = tr("grimoire.spells.cloudl.page", "Unmounting…")
            self.act(name, lambda: rclone.unmount(name),
                     tr("grimoire.spells.cloudl.page", "{name} unmounted").format(name=isolate(name)))
        else:
            if not rclone.fuse_ok():
                self.say(tr("grimoire.spells.cloudl.page", "Mounting needs FUSE: {command}").format(
                    command=ltr("sudo apt install fuse3")))
                return
            row.working = tr("grimoire.spells.cloudl.page", "Mounting…")
            self.act(name, lambda: rclone.mount(name),
                     tr("grimoire.spells.cloudl.page", "{name} is in {path}").format(name=isolate(name),
                                                                                     path=_cloud_path(name)))
        row.toggle.setText(row.working)
        row.toggle.setEnabled(False)

    def set_at_login(self, row: DriveRow, on: bool):
        msg = tr("grimoire.spells.cloudl.page", "{name} mounts at login") if on else \
            tr("grimoire.spells.cloudl.page", "{name} no longer mounts at login")
        self.act(row.name, lambda: rclone.set_at_login(row.name, on), msg.format(name=isolate(row.name)))

    def forget(self, row: DriveRow):
        if QMessageBox.question(self, "CloudL", tr("grimoire.spells.cloudl.page",
                                                   "Unmount {name} and remove its service? The account stays in "
                                                   "rclone and its files online aren't touched.").format(
                name=isolate(row.name))) != QMessageBox.StandardButton.Yes:
            return
        self.act(row.name, lambda: rclone.forget_mount(row.name),
                 tr("grimoire.spells.cloudl.page", "Mount removed"))

    def remove(self, row: DriveRow):
        if QMessageBox.question(self, "CloudL", tr("grimoire.spells.cloudl.page",
                                                   "Remove {name} from rclone? CloudL unmounts it and rclone forgets "
                                                   "the account and its key. Your files online stay where they are; "
                                                   "sign in again to get it back.").format(name=isolate(row.name))) \
                != QMessageBox.StandardButton.Yes:
            return
        self.space.pop(row.name, None)
        self.act(row.name, lambda: rclone.delete_remote(row.name),
                 tr("grimoire.spells.cloudl.page", "{name} removed").format(name=isolate(row.name)))

    def added(self, name: str):
        self.show_panel("drives")
        self.say(tr("grimoire.spells.cloudl.page", "Signed in. Press Mount to see {name} in {path}").format(
            name=isolate(name), path=_cloud_path(name)))
        self.panels["add"].name.clear()
        self.refresh()

    def open_in_vaultl(self, name: str):
        path = str(rclone.mountpoint(name))
        try:
            subprocess.Popen([str(command("grimoire-vaultl")), path], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as err:
            self.say(str(err))

    def rclone_config(self):
        try:
            subprocess.Popen([str(command("grimoire-terminall")), "-e", "rclone config", os.path.expanduser("~")],
                             start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError as err:
            self.say(str(err))

    def say(self, text: str):
        self.toast.setText(_lead(text))
        self.toast.show()
        self._toast_timer.start()
