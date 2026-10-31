# SPDX-License-Identifier: GPL-3.0-or-later
"""The hotkey popup: one resident process per session, steered through a socket in $XDG_RUNTIME_DIR.

The first `grimoire-glyphl` starts it; later ones only send "toggle" (a plain Unix socket, no Qt, so the hotkey
answers at once). Staying resident keeps it instant and keeps the clipboard: on Wayland a copied text lives only as
long as the app that copied it. It quits by itself after a while hidden.

The launching command's XDG_ACTIVATION_TOKEN (KDE hands one to whatever a hotkey starts) travels with the request,
so KWin lets the popup take the focus instead of flashing it in the task bar.
"""
import fcntl
import json
import os
import socket
import time
from pathlib import Path

from grimoire.paths import CACHE

COMMANDS = ("toggle", "show", "hide", "quit")
IDLE_QUIT_MS = 30 * 60 * 1000                           # hidden this long: quit, the next press starts afresh


def socket_path() -> str:
    run = os.environ.get("XDG_RUNTIME_DIR")
    return str(Path(run) / "grimoire-glyphl.sock") if run and Path(run).is_dir() else str(CACHE / "glyphl.sock")


def send(cmd: str, timeout: float = 2.0) -> bool:
    """Hand cmd to the running popup; False when none is running."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(socket_path())
            s.sendall((json.dumps({"cmd": cmd, "token": os.environ.get("XDG_ACTIVATION_TOKEN", "")}) + "\n")
                      .encode())
            return s.recv(16).startswith(b"ok")
    except OSError:
        return False


def _lock():
    """The right to be the popup (two quick presses must not start two)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = open(CACHE / "glyphl.lock", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except OSError:
        f.close()
        return None


def run(cmd: str) -> int:
    """Send cmd to the running popup, or become it."""
    if send(cmd):
        return 0
    if cmd in ("hide", "quit"):
        return 0                                        # nothing running: nothing to hide
    lock = _lock()
    if lock is None:                                    # another one is starting (or quitting) right now
        for _ in range(50):
            time.sleep(0.1)
            if send(cmd, timeout=0.5):
                return 0
            lock = _lock()                              # the old one quit meanwhile: be the popup
            if lock is not None:
                break
        else:
            return 1
    return _serve(cmd, lock)


def _serve(cmd: str, lock) -> int:
    import signal
    import sys

    from PySide6.QtGui import QIcon
    from PySide6.QtNetwork import QLocalServer
    from PySide6.QtWidgets import QApplication

    from grimoire.app import style_app
    from grimoire.standalone import app_icon

    app = QApplication(sys.argv[:1])
    app.setApplicationName("GlyphL")
    app.setDesktopFileName("grimoire-glyphl")
    app.setQuitOnLastWindowClosed(False)
    style_app(app)
    app.setWindowIcon(QIcon(app_icon("glyphl")))
    from grimoire.loginview import gate
    if not gate("GlyphL", (760, 560)):                   # the account picks the settings folder
        return 0
    from grimoire.spells.glyphl.window import Popup
    popup = Popup()
    QLocalServer.removeServer(socket_path())            # a stale socket from a crash (we hold the lock)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(socket_path()):
        print(f"GlyphL: can't listen on {socket_path()}: {server.errorString()}")

    def connection():
        conn = server.nextPendingConnection()
        buf = bytearray()
        done = []

        def ready():
            if done:                                    # one command per connection: later bytes are ignored
                conn.readAll()
                return
            buf.extend(bytes(conn.readAll()))
            if b"\n" not in buf and len(buf) < 4096:
                return
            done.append(True)
            try:
                msg = json.loads(buf.split(b"\n")[0])
            except ValueError:
                msg = {}
            if not isinstance(msg, dict):               # valid JSON but not an object: would raise below
                msg = {}
            conn.write(b"ok\n")
            conn.flush()
            conn.disconnectFromServer()
            popup.command(str(msg.get("cmd", "")), str(msg.get("token", ""))[:512])

        conn.readyRead.connect(ready)
        conn.disconnected.connect(conn.deleteLater)

    server.newConnection.connect(connection)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, lambda *_: app.quit())
    from PySide6.QtCore import QTimer
    tick = QTimer(interval=1000, timeout=lambda: None)    # lets Python see those signals while Qt waits
    tick.start()
    popup.command(cmd, os.environ.pop("XDG_ACTIVATION_TOKEN", ""))
    code = app.exec()
    server.close()                                      # a press from now on starts a new popup, not waits on us
    popup.finish()
    lock.close()
    return code
