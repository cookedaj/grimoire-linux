# SPDX-License-Identifier: GPL-3.0-or-later
"""org.freedesktop.FileManager1 for VaultL: what apps call to "show in folder" (browsers' downloads, portals,
"Open containing folder"). Dolphin used to answer it; without this, those buttons do nothing.

D-Bus starts it on demand (the .service file install.sh writes); it opens VaultL windows and quits when idle.
No Qt here: dbus-python + GLib only, so it starts in a blink.
"""
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

NAME = "org.freedesktop.FileManager1"
PATH = "/org/freedesktop/FileManager1"
IDLE_MS = 5 * 60 * 1000
VAULTL = Path(__file__).resolve().parents[3] / "bin" / "grimoire-vaultl"


def local_path(uri: str) -> Path | None:
    """file:// URI or plain path → an existing local path; anything else (http, smb…) is ignored."""
    if uri.startswith("file://"):
        uri = unquote(urlparse(uri).path)
    elif "://" in uri:
        return None
    p = Path(uri).expanduser()
    return p if p.is_absolute() and (p.exists() or p.is_symlink()) else None


def open_vaultl(target: Path):
    subprocess.Popen([str(VAULTL), "--", str(target)], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class FileManager(dbus.service.Object):
    def __init__(self, bus, loop):
        super().__init__(bus, PATH)
        self.loop = loop
        self.timer = None
        self._arm()

    def _arm(self):
        if self.timer:
            GLib.source_remove(self.timer)
        self.timer = GLib.timeout_add(IDLE_MS, self.loop.quit)

    def _open(self, uris, reveal: bool):
        self._arm()
        seen = set()
        for uri in list(uris)[:20]:                  # a caller can't make us open hundreds of windows
            p = local_path(str(uri))
            if p is None:
                continue
            folder = p.parent if reveal and not p.is_dir() else p
            if folder in seen:
                continue
            seen.add(folder)
            open_vaultl(p if reveal else folder)

    @dbus.service.method(NAME, in_signature="ass", out_signature="")
    def ShowFolders(self, uris, startup_id):
        self._open(uris, reveal=False)

    @dbus.service.method(NAME, in_signature="ass", out_signature="")
    def ShowItems(self, uris, startup_id):
        self._open(uris, reveal=True)

    @dbus.service.method(NAME, in_signature="ass", out_signature="")
    def ShowItemProperties(self, uris, startup_id):
        self._open(uris, reveal=True)               # VaultL's preview pane shows the item's details


def main():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = dbus.service.BusName(NAME, bus, do_not_queue=True)   # noqa: F841 (held while we run)
    loop = GLib.MainLoop()
    FileManager(bus, loop)
    loop.run()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONSAFEPATH", "1")
    sys.exit(main())
