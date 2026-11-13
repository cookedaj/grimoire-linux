# SPDX-License-Identifier: GPL-3.0-or-later
"""Permissions: each installed Flatpak's sandbox as switches (Flatseal folded in). A switch shows what the app can
reach now; flipping it writes one of your overrides (`flatpak override --user`), marked "changed by you"; Reset
drops all of yours for that app. Reads and writes run on a worker thread."""
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from grimoire import i18n
from grimoire.i18n import tr
from grimoire.jobs import POOL, Job
from grimoire.spells.storel import perms
from grimoire.widgets import Switch, plain_tip


class _Signals(QObject):
    loaded = Signal(object)          # (app id, perms.read() or None, error)
    written = Signal(object)         # (app id, error)


def _label(text="", name="", wrap=False) -> QLabel:
    lab = QLabel(text)
    lab.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class PermRow(QFrame):
    def __init__(self, panel, pid: str):
        super().__init__()
        self.setObjectName("Row")
        self.pid = pid
        _id, _key, _value, _on, _off, label, about = perms.BY_ID[pid]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 14, 10)
        lay.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(_label(tr("grimoire.spells.storel.perms", label), "RowTitle"))
        self.sub = _label(tr("grimoire.spells.storel.perms", about), "Muted", wrap=True)
        col.addWidget(self.sub)
        lay.addLayout(col, 1)
        self.mark = _label("", "Badge")
        lay.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignVCenter)
        self.sw = Switch()
        self.sw.toggled.connect(lambda on: panel.flip(pid, on))
        lay.addWidget(self.sw, 0, Qt.AlignmentFlag.AlignVCenter)

    def show_state(self, on: bool, changed: bool):
        self.sw.blockSignals(True)
        self.sw.setChecked(on)
        self.sw.blockSignals(False)
        self.mark.setText(tr("grimoire.spells.storel.permview", "CHANGED BY YOU") if changed else "")
        self.mark.setVisible(changed)


class PermissionsPanel(QWidget):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.sig = _Signals()
        self.sig.loaded.connect(self._loaded)
        self.sig.written.connect(self._written)
        self.app = ""
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)
        self.list = QListWidget()
        self.list.setObjectName("Places")
        self.list.setMinimumWidth(220)
        self.list.setMaximumWidth(300)
        self.list.currentItemChanged.connect(lambda it, _p: self.load(it.data(Qt.ItemDataRole.UserRole) if it else ""))
        root.addWidget(self.list)

        right = QVBoxLayout()
        right.setSpacing(10)
        head = QHBoxLayout()
        self.title = _label("", "SectionTitle")
        head.addWidget(self.title, 1)
        self.reset_btn = QPushButton(tr("grimoire.spells.storel.permview", "Reset"))
        self.reset_btn.setToolTip(tr("grimoire.spells.storel.permview", "Drop every override you made for this app"))
        self.reset_btn.clicked.connect(self.reset)
        head.addWidget(self.reset_btn)
        right.addLayout(head)
        self.note = _label("", "Muted", wrap=True)
        right.addWidget(self.note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("Page")
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 10, 10)
        col.setSpacing(8)
        self.rows: dict[str, PermRow] = {}
        for key, name in perms.GROUPS:
            col.addSpacing(6)
            col.addWidget(_label(tr("grimoire.spells.storel.perms", name), "NavSection"))
            for p in perms.PERMS:
                if p[1] == key:
                    self.rows[p[0]] = PermRow(self, p[0])
                    col.addWidget(self.rows[p[0]])
        col.addSpacing(6)
        col.addWidget(_label(tr("grimoire.spells.storel.permview", "Everything it may reach, as Flatpak lists it"),
                             "NavSection"))
        self.raw = QPlainTextEdit()
        self.raw.setObjectName("Log")
        self.raw.setReadOnly(True)
        self.raw.setMinimumHeight(180)
        self.raw.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        col.addWidget(self.raw)
        col.addStretch(1)
        scroll.setWidget(inner)
        right.addWidget(scroll, 1)
        self.body = scroll
        root.addLayout(right, 1)
        self.set_apps([])

    # ------------------------------------------------------------ the app list
    def set_apps(self, apps: list[tuple[str, str]]):
        """(flatpak app id, name) of every installed Flatpak app."""
        keep = self.app
        self.list.blockSignals(True)
        self.list.clear()
        for app_id, name in sorted(set(apps), key=lambda t: t[1].casefold()):
            it = QListWidgetItem(name)
            it.setData(Qt.ItemDataRole.UserRole, app_id)
            it.setToolTip(plain_tip(app_id))
            self.list.addItem(it)
        self.list.blockSignals(False)
        if not apps:
            self.app = ""
            self.title.setText(tr("grimoire.spells.storel.permview", "No Flatpak apps installed"))
            self.note.setText(tr("grimoire.spells.storel.permview", "Install an app from Flathub and its sandbox "
                                 "shows here."))
            self.body.setVisible(False)
            self.reset_btn.setEnabled(False)
            return
        self.body.setVisible(True)
        ids = [a for a, _n in sorted(set(apps), key=lambda t: t[1].casefold())]
        self.select(keep if keep in ids else ids[0])

    def select(self, app_id: str):
        for n in range(self.list.count()):
            if self.list.item(n).data(Qt.ItemDataRole.UserRole) == app_id:
                self.list.setCurrentRow(n)
                if self.app != app_id:
                    self.load(app_id)
                return

    # ------------------------------------------------------------ one app
    def load(self, app_id: str):
        if not app_id:
            return
        self.app = app_id
        it = self.list.currentItem()
        self.title.setText(it.text() if it else app_id)
        self.note.setText(tr("grimoire.spells.storel.permview", "Reading its permissions…"))
        self.body.setEnabled(False)
        self.reset_btn.setEnabled(False)

        def work():
            try:
                return app_id, perms.read(app_id), ""
            except Exception as e:              # flatpak missing or odd output: shown, not a crash
                return app_id, None, str(e)
        POOL.start(Job(work, self.sig.loaded.emit))

    def _loaded(self, result):
        app_id, data, err = result
        if app_id != self.app:
            return
        self.body.setVisible(True)
        if data is None:
            self.note.setText(tr("grimoire.spells.storel.permview", "Couldn't read its permissions: {err}").format(
                err=i18n.isolate(err)))
            return
        self.data = data
        eff, user = data["effective"], data["user"]
        for pid, row in self.rows.items():
            row.show_state(perms.state(eff, pid), perms.overridden(user, pid))
        self.raw.setPlainText(data["text"])
        mine = any(user.values())
        self.note.setText(tr("grimoire.spells.storel.permview", "{app} · switches marked CHANGED BY YOU differ from "
                             "what the app asked for. Changes apply the next time it starts.").format(
                                 app=i18n.ltr(app_id)) if mine else
                          tr("grimoire.spells.storel.permview", "{app} · what the app asked for. Changes apply the "
                             "next time it starts.").format(app=i18n.ltr(app_id)))
        self.body.setEnabled(True)
        self.reset_btn.setEnabled(mine)

    def flip(self, pid: str, on: bool):
        app_id = self.app
        self.body.setEnabled(False)

        def work():
            try:
                return app_id, perms.set_perm(app_id, pid, on)
            except Exception as e:
                return app_id, str(e)
        POOL.start(Job(work, self.sig.written.emit))

    def reset(self):
        it = self.list.currentItem()
        box = QMessageBox(QMessageBox.Icon.NoIcon, tr("grimoire.spells.storel.permview", "Reset"),
                          tr("grimoire.spells.storel.permview", "Drop every permission override you made for {app}? "
                             "It gets back what it asked for when installed.").format(
                              app=i18n.isolate(it.text() if it else self.app)),
                          QMessageBox.StandardButton.Cancel, self)
        box.setTextFormat(Qt.TextFormat.PlainText)
        ok = box.addButton(tr("grimoire.spells.storel.permview", "Reset"), QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        if box.clickedButton() is not ok:
            return
        app_id = self.app
        self.body.setEnabled(False)

        def work():
            try:
                return app_id, perms.reset(app_id)
            except Exception as e:
                return app_id, str(e)
        POOL.start(Job(work, self.sig.written.emit))

    def _written(self, result):
        app_id, err = result
        if err:
            self.page.say(tr("grimoire.spells.storel.permview", "Flatpak refused the change: {err}").format(
                err=i18n.isolate(err)))
        if app_id == self.app:
            self.load(app_id)
