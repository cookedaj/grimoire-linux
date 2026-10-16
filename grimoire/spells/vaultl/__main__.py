# SPDX-License-Identifier: GPL-3.0-or-later
"""VaultL as its own window (this is what opens when you open a folder anywhere).

    python3 -m grimoire.spells.vaultl [folder or file or file:// URL]   (an archive opens inside)
    python3 -m grimoire.spells.vaultl tidy [run|preview|undo|enable|disable|status]
"""
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def main(argv: list[str]):
    if argv[:1] == ["--file-manager-service"]:              # D-Bus activation (org.freedesktop.FileManager1)
        from grimoire.spells.vaultl import fm1
        return fm1.main()
    if argv[:1] == ["--"]:                                    # a path that could look like an option
        argv = argv[1:]
    if argv[:1] == ["tidy"]:                                   # a folder called tidy: pass ./tidy
        from grimoire.spells.vaultl import cli
        return cli.main(argv[1:])

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMainWindow

    from grimoire.app import style_app
    from grimoire.standalone import app_icon

    app = QApplication(sys.argv[:1])
    app.setApplicationName("VaultL")
    app.setDesktopFileName("grimoire-vaultl")
    style_app(app)
    app.setWindowIcon(QIcon(app_icon("vault")))
    from grimoire.loginview import gate
    if not gate("VaultL", (1280, 800)):              # the account picks the settings folder before the page loads
        sys.exit(0)
    from grimoire.spells.vaultl.page import VaultLPage
    arg = argv[0] if argv else ""
    if arg.startswith("file://"):
        arg = unquote(urlparse(arg).path)
    start = Path(arg).expanduser() if arg else Path.home()
    select = None
    if start.exists() and not start.is_dir():
        start, select = start.parent, start
    win = QMainWindow()
    page = VaultLPage(start if start.is_dir() else Path.home(), standalone=True)
    win.setCentralWidget(page)
    win.resize(1280, 800)
    win.setMinimumSize(820, 520)
    win.show()
    if select:
        from grimoire.spells.vaultl import archive
        if archive.is_archive(select):                       # grimoire-vaultl notes.zip: browse inside it
            page.open_archive(select)
        else:
            page.reveal(select)
    sys.exit(app.exec())


if __name__ == "__main__":
    main(sys.argv[1:])
