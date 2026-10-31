# SPDX-License-Identifier: GPL-3.0-or-later
"""PlayL as its own window (what "Open with PlayL" runs).

    grimoire-playl [file|folder|playlist|URL ...]     play them (in the open PlayL window when there is one)
    grimoire-playl --enqueue file ...                 add them to the open window's queue instead

One window per session: a second start hands its files to the first over a local socket in $XDG_RUNTIME_DIR and
quits, the way video players usually behave when you open one file after another.
"""
import json
import os
import sys
from pathlib import Path

MAX_MESSAGE = 1 << 20


def socket_name() -> str:
    """In $XDG_RUNTIME_DIR (private to you): a bare name would land in /tmp, where another user could take it first
    and be handed the files you open."""
    run = os.environ.get("XDG_RUNTIME_DIR", "")
    base = Path(run) if run and Path(run).is_dir() else Path.home() / ".cache"
    return str(base / f"grimoire-playl-{os.getuid()}.sock")


def _absolute(args: list[str]) -> list[str]:
    """Paths made absolute here: the running window has another working folder."""
    from grimoire.spells.playl import media
    out = []
    for a in args:
        a = media.local(a)
        out.append(a if media.is_url(a) else str(Path(a).expanduser().absolute()))
    return out


def _hand_over(args: list[str], enqueue: bool) -> bool:
    """Send the files to a running PlayL; True when one took them."""
    from PySide6.QtNetwork import QLocalSocket
    s = QLocalSocket()
    s.connectToServer(socket_name())
    if not s.waitForConnected(400):
        return False
    s.write(json.dumps({"open": args, "enqueue": enqueue}).encode() + b"\n")
    s.flush()
    s.waitForBytesWritten(1000)
    s.disconnectFromServer()
    return True


def main(argv: list[str]):
    enqueue = "--enqueue" in argv
    args = [a for a in argv if a != "--enqueue"]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    args = _absolute(args)

    from PySide6.QtGui import QIcon
    from PySide6.QtNetwork import QLocalServer
    from PySide6.QtWidgets import QApplication, QMainWindow

    from grimoire.app import style_app
    from grimoire.standalone import app_icon

    app = QApplication(sys.argv[:1])
    app.setApplicationName("PlayL")
    app.setDesktopFileName("grimoire-playl")
    if _hand_over(args, enqueue):
        return 0
    style_app(app)
    app.setWindowIcon(QIcon(app_icon("playl")))
    from grimoire.loginview import gate
    if not gate("PlayL", (1280, 800)):              # the account picks the settings folder before the page loads
        return 0
    from grimoire.spells.playl.page import PlayLPage

    class Window(QMainWindow):
        def closeEvent(self, e):
            page.shutdown()
            super().closeEvent(e)

    win = Window()
    win.setWindowTitle("PlayL")
    page = PlayLPage(standalone=True)
    win.setCentralWidget(page)
    win.resize(1280, 800)
    win.setMinimumSize(900, 560)

    server = QLocalServer(win)
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    QLocalServer.removeServer(socket_name())          # a stale socket from a crashed run
    server.listen(socket_name())

    def incoming():
        conn = server.nextPendingConnection()

        def read():
            if conn.bytesAvailable() > MAX_MESSAGE and not conn.canReadLine():
                conn.abort()
                return
            while conn.canReadLine():
                try:
                    msg = json.loads(bytes(conn.readLine()).decode())
                except ValueError:
                    continue
                if not isinstance(msg, dict) or not isinstance(msg.get("open", []), list):
                    continue
                files = [f for f in msg.get("open", []) if isinstance(f, str)]
                if files:
                    page.open_paths(files, replace=not msg.get("enqueue"))
                win.show()
                win.raise_()
                win.activateWindow()
        conn.readyRead.connect(read)
        conn.disconnected.connect(conn.deleteLater)
    server.newConnection.connect(incoming)

    win.show()
    if args:
        page.open_paths(args, replace=True)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
