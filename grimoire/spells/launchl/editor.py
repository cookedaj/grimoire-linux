# SPDX-License-Identifier: GPL-3.0-or-later
"""The "Edit…" dialog LaunchL's right-click menu opens (`grimoire-launchl edit <desktop id>`): an app's name, icon
and command, and whether the menu shows it. appedit.py does the work; files are read and written off the UI thread."""
import shlex
import sys

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QVBoxLayout)

from grimoire.fsutil import tilde
from grimoire.glyphs import glyph
from grimoire.i18n import isolate, ltr, tr
from grimoire.jobs import POOL, Job
from grimoire.spells.launchl import appedit
from grimoire.widgets import Switch

def app_icon(name: str) -> QIcon:
    """An app's icon from a theme name or a file path (null when there's neither)."""
    if not name:
        return QIcon()
    if name.startswith("/"):
        return QIcon(name)
    return QIcon.fromTheme(name)


def shown(args: list[str], app: appedit.App) -> str:
    """The command as it will run, field codes spelled out (%u → [link])."""
    codes = {"%u": tr("grimoire.spells.launchl.editor", "[link]"),
             "%U": tr("grimoire.spells.launchl.editor", "[links]"),
             "%f": tr("grimoire.spells.launchl.editor", "[file]"),
             "%F": tr("grimoire.spells.launchl.editor", "[files]"),
             "%d": "", "%D": "", "%n": "", "%N": "", "%v": "", "%m": "", "%k": str(app.user or app.system or ""),
             "%c": app.name}
    out = []
    for a in args:
        if a == "%i":
            if app.icon:
                out += ["--icon", shlex.quote(app.icon)]
            continue
        if a in codes:
            if codes[a]:
                out.append(codes[a] if a in ("%u", "%U", "%f", "%F") else shlex.quote(codes[a]))
            continue
        out.append(shlex.quote(a.replace("%%", "%")))
    return " ".join(out)


def _label(text="", name="", wrap=True) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    lab.setTextFormat(Qt.TextFormat.PlainText)          # names and commands come from anyone's desktop files
    return lab


class _Signals(QObject):
    done = Signal(object)          # (what, error text or "", result)


class EditDialog(QDialog):
    def __init__(self, app_id: str, parent=None):
        super().__init__(parent)
        self.app_id, self.app = app_id, None
        self.sig = _Signals()
        self.sig.done.connect(self._finished)
        self.setObjectName("Page")
        self.setWindowTitle(tr("grimoire.spells.launchl.editor", "Edit app"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(14)
        self.preview = QLabel()
        self.preview.setFixedSize(48, 48)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = _label(tr("grimoire.spells.launchl.editor", "Loading…"), "RowTitle")
        self.subtitle = _label("", "Muted")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        head.addLayout(titles, 1)
        lay.addLayout(head)
        lay.addSpacing(6)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        self.name = QLineEdit()
        self.name.textChanged.connect(self._check)
        self.icon = QLineEdit()
        self.icon.setPlaceholderText(tr("grimoire.spells.launchl.editor",
                                        "An icon name from your theme, or an image file"))
        self.icon.textChanged.connect(self._show_icon)
        choose = QPushButton(tr("grimoire.spells.launchl.editor", "Choose…"))
        choose.clicked.connect(self._choose_icon)
        self.command = QLineEdit()
        self.command.setFont(self._mono())
        self.command.textChanged.connect(self._check)
        # commands, paths and icon names read left to right in every language
        for w in (self.icon, self.command):
            w.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        grid.addWidget(_label(tr("grimoire.spells.launchl.editor", "Name"), "", False), 0, 0)
        grid.addWidget(self.name, 0, 1, 1, 2)
        grid.addWidget(_label(tr("grimoire.spells.launchl.editor", "Icon"), "", False), 1, 0)
        grid.addWidget(self.icon, 1, 1)
        grid.addWidget(choose, 1, 2)
        grid.addWidget(_label(tr("grimoire.spells.launchl.editor", "Command"), "", False), 2, 0)
        grid.addWidget(self.command, 2, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)

        lay.addWidget(_label(tr("grimoire.spells.launchl.editor", "WILL RUN"), "Section"))
        self.runs = _label("", "Mono")
        self.runs.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.runs)
        self.warn = _label("", "Muted")
        self.warn.hide()
        lay.addWidget(self.warn)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.hidden = Switch()
        row.addWidget(self.hidden)
        hint = QVBoxLayout()
        hint.setSpacing(0)
        hint.addWidget(_label(tr("grimoire.spells.launchl.editor", "Hide from the menu"), "", False))
        hint.addWidget(_label(tr("grimoire.spells.launchl.editor",
                                 "It stays installed and still opens files; only the menus leave it out."),
                              "Muted"))
        row.addLayout(hint, 1)
        lay.addSpacing(4)
        lay.addLayout(row)

        lay.addSpacing(6)
        self.where = _label("", "Muted")
        lay.addWidget(self.where)
        self.status = _label("", "Muted")
        self.status.hide()
        lay.addWidget(self.status)

        buttons = QHBoxLayout()
        self.reset_btn = QPushButton(tr("grimoire.spells.launchl.editor", "Reset to default"))
        self.reset_btn.clicked.connect(self._reset)
        self.reset_btn.hide()
        buttons.addWidget(self.reset_btn)
        buttons.addStretch(1)
        cancel = QPushButton(tr("grimoire.spells.launchl.editor", "Cancel"))
        cancel.clicked.connect(self.reject)
        cancel.setAutoDefault(False)
        self.save_btn = QPushButton(tr("grimoire.spells.launchl.editor", "Save"))
        self.save_btn.setObjectName("Primary")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_btn)
        lay.addSpacing(6)
        lay.addLayout(buttons)

        self._enable(False)
        POOL.start(Job(self._load, lambda r: self.sig.done.emit(("load",) + r)))

    @staticmethod
    def _mono():
        from PySide6.QtGui import QFont
        f = QFont("IBM Plex Mono")
        f.setStyleHint(QFont.StyleHint.Monospace)
        return f

    def _load(self):
        try:
            return "", appedit.load(self.app_id)
        except (LookupError, OSError) as err:
            return str(err), None

    def _enable(self, on: bool):
        for w in (self.name, self.icon, self.command, self.hidden, self.save_btn, self.reset_btn):
            w.setEnabled(on)

    # ---- showing ------------------------------------------------------------------------------------------------

    def _fill(self, app: appedit.App):
        self.app = app
        self.title.setText(tr("grimoire.spells.launchl.editor", "Edit {app}").format(app=isolate(app.name or app.id)))
        self.subtitle.setText(ltr(app.id))
        self.name.setText(app.name)
        self.icon.setText(app.icon)
        self.command.setText(app.exec)
        self.hidden.setChecked(app.hidden)
        copy = ltr(tilde(app.user or appedit.user_dir() / app.id))
        if app.user and not app.system:
            self.where.setText(tr("grimoire.spells.launchl.editor",
                                  "This app's menu entry is your own file: {path}").format(path=copy))
        elif app.user:
            self.where.setText(tr("grimoire.spells.launchl.editor",
                                  "Your changes are in {path}. The system file ({system}) is never "
                                  "changed; Reset to default moves your copy to the Trash.").format(
                path=copy, system=ltr(tilde(app.system))))
        else:
            self.where.setText(tr("grimoire.spells.launchl.editor",
                                  "Saving makes your own copy in {path}. The system file ({system}) isn't "
                                  "changed.").format(path=copy, system=ltr(tilde(app.system))))
        self._enable(True)
        self.reset_btn.setVisible(app.resettable)
        self._check()
        self.name.setFocus()
        self.name.selectAll()

    def _show_icon(self):
        icon = app_icon(self.icon.text().strip())
        if icon.isNull() or icon.pixmap(QSize(48, 48)).isNull():
            icon = glyph("launchl", 40)                    # no such icon: LaunchL's own line glyph
        self.preview.setPixmap(icon.pixmap(QSize(48, 48)))
        self._check()

    def _fit(self):
        """Grow when a warning appears (wrapped labels don't push a dialog's minimum height by themselves)."""
        need = self.layout().totalHeightForWidth(self.width())
        if need > self.height():
            self.resize(self.width(), need)

    def _check(self) -> bool:
        """Show what the command runs and anything wrong with it; False when it can't be saved."""
        if self.app is None:
            return False
        cmd = self.command.text()
        check = appedit.check_exec(cmd)
        notes = list(check.warnings) if cmd.strip() != self.app.exec else []
        if check.error:
            self.runs.setText(check.error)
        else:
            self.runs.setText(shown(check.args, self.app))
        if cmd.strip() != self.app.exec and self.app.dbus:
            notes.append(tr("grimoire.spells.launchl.editor",
                            "This app normally starts through D-Bus. Saving a new command switches that "
                            "off, so your command is what runs."))
        icon = self.icon.text().strip()
        if icon and not icon.startswith("/") and not QIcon.hasThemeIcon(icon) and icon != self.app.icon:
            notes.append(tr("grimoire.spells.launchl.editor",
                            "Your icon theme has no icon called {icon}.").format(icon=ltr(icon)))
        self.warn.setText("\n".join(notes))
        self.warn.setVisible(bool(notes))
        QTimer.singleShot(0, self._fit)
        ok = not check.error and bool(self.name.text().strip())
        self.save_btn.setEnabled(ok)
        return ok

    def _choose_icon(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("grimoire.spells.launchl.editor", "Choose an icon"),
                                              "/usr/share/icons",
                                              tr("grimoire.spells.launchl.editor", "Images (*.png *.svg *.svgz *.xpm)"))
        if path:
            self.icon.setText(path)

    # ---- saving -------------------------------------------------------------------------------------------------

    def _run(self, what: str, fn):
        self._enable(False)
        self.status.show()
        self.status.setText(tr("grimoire.spells.launchl.editor", "Saving…") if what == "save"
                            else tr("grimoire.spells.launchl.editor", "Resetting…"))

        def guarded():
            try:
                result = fn()
            except (ValueError, LookupError, OSError) as err:
                return what, str(err), None
            appedit.rebuild()                              # the menus update once KDE's app cache does
            return what, "", result
        POOL.start(Job(guarded, self.sig.done.emit))

    def _save(self):
        if not self._check():
            return
        app, name, icon, cmd, hide = (self.app, self.name.text(), self.icon.text(), self.command.text(),
                                      self.hidden.isChecked())
        self._run("save", lambda: appedit.save(app, name=name, icon=icon, command=cmd, hidden=hide))

    def _reset(self):
        if QMessageBox.question(self, tr("grimoire.spells.launchl.editor", "Reset to default"),
                                tr("grimoire.spells.launchl.editor",
                                   "Put {app} back the way it was installed? Your copy of its menu entry goes "
                                        "to the Trash.").format(app=isolate(self.app.name or self.app.id))) \
                != QMessageBox.StandardButton.Yes:
            return
        app_id = self.app.id
        self._run("reset", lambda: appedit.reset(app_id))

    def _finished(self, payload):
        what, error, result = payload
        if what == "load":
            if error:
                self.title.setText(tr("grimoire.spells.launchl.editor", "Can't edit this app"))
                self.subtitle.setText(error)
                self.preview.setPixmap(glyph("launchl", 40).pixmap(QSize(48, 48)))
                return
            self._fill(result)
            return
        if error:
            self.status.setText(error)
            self._enable(True)
            self.reset_btn.setVisible(self.app.resettable)
            self._check()
            return
        self.accept()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.save_btn.isEnabled():
            self._save()
            return
        super().keyPressEvent(e)


def run(app_id: str) -> int:
    """The dialog in its own process (LaunchL's right-click menu starts it)."""
    from grimoire.app import style_app
    app = QApplication(sys.argv[:1])
    app.setApplicationName("LaunchL")
    app.setDesktopFileName("grimoire")
    style_app(app)
    dlg = EditDialog(app_id)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    app.exec()
    return 0 if dlg.result() == QDialog.DialogCode.Accepted else 1
