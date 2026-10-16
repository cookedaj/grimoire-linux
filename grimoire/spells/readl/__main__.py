# SPDX-License-Identifier: GPL-3.0-or-later
"""ReadL as its own window (what "Open with ReadL" runs):

    grimoire-readl [file or file:// URL]     open the reader (the library without a file)
    grimoire-readl status                    the home page's status line
"""
import os
import sys
from urllib.parse import unquote, urlparse


def main(argv: list[str]):
    if argv == ["status"]:
        from grimoire.spells.readl import library
        print(library.status_line())
        return 0

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMainWindow

    from grimoire.app import style_app
    from grimoire.standalone import app_icon

    app = QApplication(sys.argv[:1])
    app.setApplicationName("ReadL")
    app.setDesktopFileName("grimoire-readl")
    style_app(app)
    app.setWindowIcon(QIcon(app_icon("read")))
    from grimoire.loginview import gate
    if not gate("ReadL", (1280, 860)):            # the account picks the settings folder before the page loads
        sys.exit(0)
    from grimoire.spells.readl.page import ReadLPage
    arg = argv[0] if argv else ""
    if arg.startswith("file://"):
        arg = unquote(urlparse(arg).path)
    win = QMainWindow()
    win.setWindowTitle("ReadL")
    page = ReadLPage()
    page.titleChanged.connect(lambda t: win.setWindowTitle(f"{t} — ReadL" if t else "ReadL"))
    win.setCentralWidget(page)
    win.resize(1280, 860)
    win.setMinimumSize(720, 480)
    win.show()
    if arg:
        page.open_file(os.path.abspath(os.path.expanduser(arg)))
    sys.exit(app.exec())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
