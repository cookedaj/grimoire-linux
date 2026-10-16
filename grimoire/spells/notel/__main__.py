# SPDX-License-Identifier: GPL-3.0-or-later
"""NoteL as its own window (what "Open with NoteL" runs):

    grimoire-notel [file …]        open the window, with these files in tabs
    grimoire-notel --daily         open today's note
    grimoire-notel status          the home page's status line

When a NoteL window is already open, the files open as tabs there instead of in a second window: the first window
listens on a socket in $XDG_RUNTIME_DIR (private to you) and only ever takes a list of files to open.
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

MAX_MESSAGE = 1 << 20


def socket_name() -> str:
    run = os.environ.get("XDG_RUNTIME_DIR", "")
    base = Path(run) if run and Path(run).is_dir() else Path.home() / ".cache"
    return str(base / f"grimoire-notel-{os.getuid()}.sock")


def _paths(args: list[str]) -> list[str]:
    out = []
    for a in args:
        if a.startswith("file://"):
            a = unquote(urlparse(a).path)
        elif "://" in a:
            continue                                  # only local files
        out.append(str(Path(a).expanduser().absolute()))
    return out


def _forward(message: dict) -> bool:
    """Hand the files to a running NoteL; False when there's none."""
    from PySide6.QtNetwork import QLocalSocket
    s = QLocalSocket()
    s.connectToServer(socket_name())
    if not s.waitForConnected(400):
        return False
    s.write(json.dumps(message).encode() + b"\n")
    s.flush()
    s.waitForBytesWritten(1000)
    s.disconnectFromServer()
    return True


def _listen(page, win):
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer(win)
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    name = socket_name()
    QLocalServer.removeServer(name)                   # a stale socket from a crash (no one answered above)
    if not server.listen(name):
        return None

    def incoming():
        conn = server.nextPendingConnection()
        buf = bytearray()

        def read():
            buf.extend(bytes(conn.readAll()))
            if len(buf) > MAX_MESSAGE:
                conn.abort()
                return
            if b"\n" not in buf:
                return
            try:
                msg = json.loads(bytes(buf).split(b"\n", 1)[0])
            except ValueError:
                msg = {}
            conn.disconnectFromServer()
            files = [f for f in msg.get("open", []) if isinstance(f, str) and os.path.isabs(f)][:50] \
                if isinstance(msg, dict) else []
            page.open_paths(files)
            if isinstance(msg, dict) and msg.get("daily"):
                page.daily()
            win.showNormal() if win.isMinimized() else win.show()
            win.raise_()
            win.activateWindow()
        conn.readyRead.connect(read)
    server.newConnection.connect(incoming)
    return server


def main(argv: list[str]) -> int:
    if argv[:1] == ["status"]:
        from grimoire import i18n
        i18n.install_catalogs(["notel"])
        from grimoire.spells.notel import store
        print(store.status_line())
        return 0
    if argv[:1] in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    daily = "--daily" in argv
    files = _paths([a for a in argv if a != "--daily"])

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMainWindow

    from grimoire.app import style_app
    from grimoire.standalone import app_icon

    app = QApplication(sys.argv[:1])
    app.setApplicationName("NoteL")
    app.setDesktopFileName("grimoire-notel")
    if _forward({"open": files, "daily": daily}):
        return 0
    style_app(app)
    app.setWindowIcon(QIcon(app_icon("notel")))
    from grimoire.loginview import gate
    if not gate("NoteL", (1280, 820)):              # the account picks the settings folder before the page loads
        return 0
    from grimoire.spells.notel.page import NoteLPage
    win = QMainWindow()
    win.setWindowTitle("NoteL")
    page = NoteLPage(standalone=True)
    win.setCentralWidget(page)
    win.resize(1280, 820)
    win.setMinimumSize(820, 520)
    server = _listen(page, win)
    win.show()
    page.open_paths(files)
    if daily:
        page.daily()
    code = app.exec()
    if server is not None:
        server.close()
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
