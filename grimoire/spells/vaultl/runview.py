# SPDX-License-Identifier: GPL-3.0-or-later
"""The question VaultL asks before opening a program (launch.py sorts the files): Run / Open as text / Cancel for
programs and scripts, the command a .desktop launcher runs, and what to do with Windows or macOS programs. Nothing
starts without a click, and nothing goes through KIO (which refuses executables) or a shell."""
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from grimoire.fsutil import tilde
from grimoire.glyphs import glyph
from grimoire.i18n import isolate, ltr, tr, tr_noop
from grimoire.spells.vaultl import launch

LINUX_VERSION = tr_noop("grimoire.spells.vaultl.runview",
                        "Check whether the app has a Linux version (.deb, AppImage or Flatpak).")
ICONS = {launch.NATIVE: "terminal", launch.SCRIPT: "terminal", launch.DESKTOP: "launchl",
         launch.WINDOWS: "windows", launch.MAC: "desktop"}


class ProgramDialog(QDialog):
    """One question about one program; `choice` holds the clicked button's id (None = cancelled)."""

    def __init__(self, parent, p: Path, kind: str):
        super().__init__(parent)
        self.p, self.kind, self.choice = p, kind, None
        self.setObjectName("Page")
        self.setMinimumWidth(460)
        self.setMaximumWidth(640)
        self.setWindowTitle(p.name)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(12)
        self.lay = lay
        self.buttons: list[tuple[str, str, bool]] = []       # (id, text, primary)
        name = isolate(p.name)
        title, lines, code = "", [], None
        runnable = launch.executable(p)

        if kind in (launch.NATIVE, launch.SCRIPT):
            title = tr("grimoire.spells.vaultl.runview", "Run “{name}”?").format(name=name)
            lines.append(tr("grimoire.spells.vaultl.runview", "This is a program. It runs with your permissions and "
                            "can change or delete your files, so only run programs you trust.") if kind == launch.NATIVE
                         else tr("grimoire.spells.vaultl.runview", "This is a script. It runs with your permissions "
                                 "and can change or delete your files, so only run scripts you trust."))
            if not runnable:
                lines.append(tr("grimoire.spells.vaultl.runview", "It isn't marked as executable yet (usual for a "
                                "fresh download). Making it executable lets it run, for you only."))
            code = ltr(tilde(p))
            if kind == launch.SCRIPT:
                self.buttons.append(("text", tr("grimoire.spells.vaultl.runview", "Open as text"), False))
            self.buttons.append(("run", tr("grimoire.spells.vaultl.runview", "Run"), True) if runnable else
                                ("chmod_run", tr("grimoire.spells.vaultl.runview", "Make executable and run"), True))
        elif kind == launch.DESKTOP:
            entry = launch.desktop_entry(p)
            shown = isolate(entry.name if entry and entry.name else p.name)
            if entry and entry.type == "Link":
                title = tr("grimoire.spells.vaultl.runview", "Open “{name}”?").format(name=shown)
                lines.append(tr("grimoire.spells.vaultl.runview", "This launcher opens the address below."))
                code = ltr(entry.url)
                self.buttons.append(("text", tr("grimoire.spells.vaultl.runview", "Open as text"), False))
                if entry.url:
                    self.buttons.append(("link", tr("grimoire.spells.vaultl.runview", "Open link"), True))
            elif entry and entry.exec:
                title = tr("grimoire.spells.vaultl.runview", "Start “{name}”?").format(name=shown)
                lines.append(tr("grimoire.spells.vaultl.runview", "This launcher runs the command below. Only start "
                                "launchers you trust.") if runnable
                             else tr("grimoire.spells.vaultl.runview", "This launcher isn't marked as trusted. "
                                     "Launchers can run any command, so check the one below before you start it."))
                code = ltr(entry.exec)
                self.buttons.append(("text", tr("grimoire.spells.vaultl.runview", "Open as text"), False))
                self.buttons.append(("run", tr("grimoire.spells.vaultl.runview", "Start"), True) if runnable else
                                    ("chmod_run", tr("grimoire.spells.vaultl.runview", "Trust and start"), True))
            else:
                title = tr("grimoire.spells.vaultl.runview", "“{name}” can't be started").format(name=shown)
                lines.append(tr("grimoire.spells.vaultl.runview", "This launcher has no command to run."))
                self.buttons.append(("text", tr("grimoire.spells.vaultl.runview", "Open as text"), True))
        elif kind == launch.WINDOWS:
            title = tr("grimoire.spells.vaultl.runview", "“{name}” is a Windows program").format(name=name)
            lines.append(tr("grimoire.spells.vaultl.runview", "Linux can't run Windows programs directly."))
            runners = launch.runners()
            if runners:
                lines.append(tr("grimoire.spells.vaultl.runview", "A Windows compatibility tool is installed and may "
                                "run it, though not every program works. Only run programs you trust."))
                lines.append(tr("grimoire.spells.vaultl.runview", LINUX_VERSION))
                for i, r in enumerate(runners):
                    self.buttons.append((f"runner:{r.id}", tr("grimoire.spells.vaultl.runview",
                                                              "Open with {runner}").format(runner=r.name), i == 0))
            else:
                lines.append(tr("grimoire.spells.vaultl.runview", "No Windows compatibility tool (Wine, Bottles or "
                                "Protontricks) is installed."))
                lines.append(tr("grimoire.spells.vaultl.runview", LINUX_VERSION))
        else:                                                   # MAC
            title = tr("grimoire.spells.vaultl.runview", "“{name}” is for macOS").format(name=name)
            lines.append(tr("grimoire.spells.vaultl.runview", "macOS apps and installers can't run on Linux."))
            lines.append(tr("grimoire.spells.vaultl.runview", LINUX_VERSION))
            if p.is_dir():
                self.buttons.append(("browse", tr("grimoire.spells.vaultl.runview", "Show contents"), False))

        head = QHBoxLayout()
        head.setSpacing(12)
        icon = QLabel()
        icon.setPixmap(glyph(ICONS.get(kind, "document"), 28).pixmap(28, 28))
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        head.addWidget(icon)
        t = QLabel(title)
        t.setObjectName("RowTitle")
        t.setWordWrap(True)
        t.setTextFormat(Qt.TextFormat.PlainText)            # file and launcher names come from anyone
        head.addWidget(t, 1)
        lay.addLayout(head)
        for line in lines:
            lab = QLabel(line)
            lab.setObjectName("Muted")
            lab.setWordWrap(True)
            lab.setTextFormat(Qt.TextFormat.PlainText)
            lay.addWidget(lab)
        if code:
            box = QLabel(code)
            box.setObjectName("Mono")
            box.setWordWrap(True)
            box.setTextFormat(Qt.TextFormat.PlainText)
            box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(box)

        row = QHBoxLayout()
        row.addStretch(1)
        has_action = bool(self.buttons)
        cancel = QPushButton(tr("grimoire.spells.vaultl.runview", "Cancel") if has_action
                             else tr("grimoire.spells.vaultl.runview", "Close"))
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        for bid, text, primary in self.buttons:
            b = QPushButton(text)
            b.setProperty("choice", bid)
            if primary:
                b.setObjectName("Primary")
            b.setAutoDefault(False)
            b.clicked.connect(lambda _=False, bid=bid: self._pick(bid))
            row.addWidget(b)
        cancel.setDefault(True)                              # Enter never runs anything by accident
        cancel.setFocus()
        lay.addLayout(row)

    def _pick(self, bid: str):
        self.choice = bid
        self.accept()


def open_program(parent, p: Path, say, browse=None) -> bool:
    """Ask about p and do what was picked; False when p isn't a program (the caller opens it normally).
    say(text) shows a status line; browse(path) opens a folder in VaultL (an .app bundle's contents)."""
    kind = launch.classify(p)
    if kind == launch.OTHER:
        return False
    dlg = ProgramDialog(parent, p, kind)
    dlg.exec()
    act(dlg.choice, p, say, browse)
    return True


def act(choice: str | None, p: Path, say, browse=None):
    name = isolate(p.name)
    if choice is None:
        return
    if choice == "browse":
        if browse:
            browse(p)
        return
    if choice == "link":
        entry = launch.desktop_entry(p)
        if entry and entry.url:
            QDesktopServices.openUrl(QUrl(entry.url))
        return
    if choice == "text":
        argv = launch.text_command(p)
        if not argv:
            say(tr("grimoire.spells.vaultl.runview", "No text editor is set up to open “{name}”.").format(name=name))
            return
    elif choice.startswith("runner:"):
        runner = next((r for r in launch.runners() if f"runner:{r.id}" == choice), None)
        if runner is None:
            return
        argv = runner.command + [str(p)]
    else:
        if choice == "chmod_run":
            try:
                launch.make_executable(p)
            except OSError as e:
                say(tr("grimoire.spells.vaultl.runview",
                       "Couldn't make “{name}” executable: {error}").format(name=name, error=e.strerror or e))
                return
        argv = launch.run_command(p)
    ok, error = launch.RUN(argv, p.parent)
    say(tr("grimoire.spells.vaultl.runview", "Started “{name}”.").format(name=name) if ok
        else tr("grimoire.spells.vaultl.runview", "Couldn't start “{name}”: {error}").format(name=name, error=error))
