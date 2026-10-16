# SPDX-License-Identifier: GPL-3.0-or-later
"""ViewL from a terminal or a file manager's "Open with":

grimoire-viewl [picture | folder | file:// URL]     the window, on that picture or folder
grimoire-viewl status                                the home page's status line
"""

import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def main(argv: list[str]) -> int:
    if argv[:1] == ["status"]:
        from grimoire import i18n

        i18n.install_catalogs(["viewl"])
        from grimoire.spells.viewl import images

        print(images.status_line())
        return 0
    if argv[:1] in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMainWindow

    from grimoire.app import style_app
    from grimoire.standalone import app_icon

    app = QApplication(sys.argv[:1])
    app.setApplicationName("ViewL")
    app.setDesktopFileName("grimoire-viewl")
    style_app(app)
    app.setWindowIcon(QIcon(app_icon("viewl")))
    from grimoire.loginview import gate

    if not gate("ViewL", (1280, 820)):  # the account picks the settings folder before the page loads
        return 0
    from grimoire.spells.viewl.page import ViewLPage

    arg = argv[0] if argv else ""
    if arg.startswith("file://"):
        arg = unquote(urlparse(arg).path)
    start = Path(arg).expanduser().absolute() if arg else None

    class Win(QMainWindow):
        def closeEvent(self, e):
            e.accept() if page.can_close() else e.ignore()  # unsaved turns ask first

    win = Win()
    page = ViewLPage(start, standalone=True)
    page.title_changed.connect(lambda t: win.setWindowTitle(f"{t} — ViewL" if t else "ViewL"))
    win.setWindowTitle("ViewL")
    win.setCentralWidget(page)
    win.resize(1280, 820)
    win.setMinimumSize(760, 520)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
