# SPDX-License-Identifier: GPL-3.0-or-later
"""KDE Connect's daemon (kdeconnectd) over D-Bus: PhoneL is only a face on it, so pairing, the encryption and
the phone link itself stay KDE's. No Qt here; every call blocks, so the page runs them on its worker pool.

Talks through GLib's GDBus (python3-gi): its calls are thread-safe and it unpacks KDE Connect's structs (text
messages) that PySide6's QtDBus can't. Every call is sent with NO_AUTO_START, so reading never starts the daemon
behind your back; start() does that, only on a click.

Stub points for tests: ADDRESS (a private bus with scripts/fake_kdeconnect.py on it) and START.
"""
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

from grimoire.i18n import isolate, tr, tr_noop

SERVICE = "org.kde.kdeconnect"
ROOT = "/modules/kdeconnect"
DAEMON = "org.kde.kdeconnect.daemon"
DEVICE = "org.kde.kdeconnect.device"
PROPS = "org.freedesktop.DBus.Properties"
ADDRESS: str | None = None           # None = the session bus
TIMEOUT_MS = 5000
APT = "sudo apt install kdeconnect"
APT_GI = "sudo apt install python3-gi gir1.2-glib-2.0"
STORES = [("Google Play", "https://play.google.com/store/apps/details?id=org.kde.kdeconnect_tp"),
          ("F-Droid", "https://f-droid.org/packages/org.kde.kdeconnect_tp/"),
          ("App Store", "https://apps.apple.com/app/kde-connect/id1580245991")]
# KDE Connect's plugin ids, as shown in the Plugins list (unknown ones show their id)
PLUGINS = {
    "kdeconnect_battery": tr_noop("grimoire.spells.phonel.kdc", "Battery level"),
    "kdeconnect_clipboard": tr_noop("grimoire.spells.phonel.kdc", "Shared clipboard"),
    "kdeconnect_connectivity_report": tr_noop("grimoire.spells.phonel.kdc", "Mobile signal"),
    "kdeconnect_contacts": tr_noop("grimoire.spells.phonel.kdc", "Contacts"),
    "kdeconnect_findmyphone": tr_noop("grimoire.spells.phonel.kdc", "Ring my phone"),
    "kdeconnect_findthisdevice": tr_noop("grimoire.spells.phonel.kdc", "Ring this PC from the phone"),
    "kdeconnect_lockdevice": tr_noop("grimoire.spells.phonel.kdc", "Lock this PC from the phone"),
    "kdeconnect_mmtelephony": tr_noop("grimoire.spells.phonel.kdc", "Modem calls"),
    "kdeconnect_mousepad": tr_noop("grimoire.spells.phonel.kdc", "Use the phone as a touchpad"),
    "kdeconnect_mpriscontrol": tr_noop("grimoire.spells.phonel.kdc", "Control this PC's media from the phone"),
    "kdeconnect_mprisremote": tr_noop("grimoire.spells.phonel.kdc", "Control the phone's media"),
    "kdeconnect_notifications": tr_noop("grimoire.spells.phonel.kdc", "Phone notifications"),
    "kdeconnect_pausemusic": tr_noop("grimoire.spells.phonel.kdc", "Pause media during calls"),
    "kdeconnect_ping": tr_noop("grimoire.spells.phonel.kdc", "Ping"),
    "kdeconnect_presenter": tr_noop("grimoire.spells.phonel.kdc", "Presentation remote"),
    "kdeconnect_remotecommands": tr_noop("grimoire.spells.phonel.kdc", "Run the phone's commands"),
    "kdeconnect_remotecontrol": tr_noop("grimoire.spells.phonel.kdc", "Move the phone's pointer"),
    "kdeconnect_remotekeyboard": tr_noop("grimoire.spells.phonel.kdc", "Type on the phone"),
    "kdeconnect_remotesystemvolume": tr_noop("grimoire.spells.phonel.kdc", "The phone's volume"),
    "kdeconnect_runcommand": tr_noop("grimoire.spells.phonel.kdc", "Commands the phone can run here"),
    "kdeconnect_screensaver_inhibit": tr_noop("grimoire.spells.phonel.kdc", "Keep the screen on while connected"),
    "kdeconnect_sendnotifications": tr_noop("grimoire.spells.phonel.kdc", "Send this PC's notifications"),
    "kdeconnect_sftp": tr_noop("grimoire.spells.phonel.kdc", "Browse the phone's files"),
    "kdeconnect_share": tr_noop("grimoire.spells.phonel.kdc", "Send and receive files"),
    "kdeconnect_sms": tr_noop("grimoire.spells.phonel.kdc", "Text messages"),
    "kdeconnect_systemvolume": tr_noop("grimoire.spells.phonel.kdc", "This PC's volume from the phone"),
    "kdeconnect_telephony": tr_noop("grimoire.spells.phonel.kdc", "Calls"),
    "kdeconnect_virtualmonitor": tr_noop("grimoire.spells.phonel.kdc", "Use the device as a second screen"),
}
MEDIA_ACTIONS = ("Play", "Pause", "PlayPause", "Next", "Previous", "Stop")
KEYS = {"backspace": 1, "tab": 2, "left": 4, "up": 5, "right": 6, "down": 7, "home": 10, "end": 11, "enter": 12,
        "delete": 13, "escape": 14}          # KDE Connect's special key codes (remotekeyboard / mousepad)
SMS_INBOX, SMS_SENT = 1, 2                    # Android's message types

_lock = threading.Lock()
_conn = None
_conn_address = None


class Error(Exception):
    """A failed call, with a message fit for the user."""


def _gio():
    try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
        return Gio, GLib
    except (ImportError, ValueError) as err:
        raise Error(tr("grimoire.spells.phonel.kdc", "PhoneL needs Python's GLib bindings: {command}").format(
            command=APT_GI)) from err


def has_gi() -> bool:
    try:
        _gio()
        return True
    except Error:
        return False


def connection():
    """The bus connection (shared, made once per ADDRESS)."""
    global _conn, _conn_address
    Gio, GLib = _gio()
    with _lock:
        if _conn is not None and _conn_address == ADDRESS and not _conn.is_closed():
            return _conn
        try:
            if ADDRESS:
                flags = (Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                         | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION)
                _conn = Gio.DBusConnection.new_for_address_sync(ADDRESS, flags, None, None)
            else:
                _conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as err:
            raise Error(tr("grimoire.spells.phonel.kdc", "Can't reach the session bus: {error}").format(
                error=err.message)) from err
        _conn_address = ADDRESS
        return _conn


def _message(err) -> str:
    """GDBus's error text without its "GDBus.Error:org.foo.Bar: " prefix."""
    text = getattr(err, "message", str(err)) or str(err)
    if text.startswith("GDBus.Error:") and ": " in text:
        text = text.split(": ", 1)[1]
    return text.strip()


def call(path: str, iface: str, method: str, sig: str = "", args=(), timeout: int = TIMEOUT_MS,
         service: str = SERVICE):
    """One method call; returns the unpacked reply (one value, a tuple for several, None for none)."""
    Gio, GLib = _gio()
    conn = connection()
    params = GLib.Variant(f"({sig})", tuple(args)) if sig else None
    try:
        reply = conn.call_sync(service, path, iface, method, params, None, Gio.DBusCallFlags.NO_AUTO_START,
                               timeout, None)
    except GLib.Error as err:
        if "ServiceUnknown" in str(err) or "NameHasNoOwner" in str(err):
            raise Error(tr("grimoire.spells.phonel.kdc", "KDE Connect isn't running")) from err
        raise Error(_message(err)) from err
    if reply is None:
        return None
    out = reply.unpack()
    return out[0] if len(out) == 1 else (out or None)


def props(path: str, iface: str) -> dict:
    return call(path, PROPS, "GetAll", "s", (iface,)) or {}


def set_prop(path: str, iface: str, name: str, sig: str, value):
    Gio, GLib = _gio()
    conn = connection()
    try:
        conn.call_sync(SERVICE, path, PROPS, "Set", GLib.Variant("(ssv)", (iface, name, GLib.Variant(sig, value))),
                       None, Gio.DBusCallFlags.NO_AUTO_START, TIMEOUT_MS, None)
    except GLib.Error as err:
        raise Error(_message(err)) from err


def dev_path(dev: str, plugin: str = "") -> str:
    return f"{ROOT}/devices/{dev}" + (f"/{plugin}" if plugin else "")


# ---------------------------------------------------------------- the daemon
def running() -> bool:
    return bool(call("/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner", "s", (SERVICE,),
                     service="org.freedesktop.DBus"))


def installed() -> bool:
    """kdeconnectd on PATH, or the bus knows how to start it."""
    if shutil.which("kdeconnectd") or Path("/usr/bin/kdeconnectd").exists():
        return True
    try:
        names = call("/org/freedesktop/DBus", "org.freedesktop.DBus", "ListActivatableNames",
                     service="org.freedesktop.DBus")
        return SERVICE in (names or [])
    except Error:
        return False


def _start():
    """Ask the bus to start kdeconnectd (its own service file), else run it detached."""
    try:
        call("/org/freedesktop/DBus", "org.freedesktop.DBus", "StartServiceByName", "su", (SERVICE, 0),
             timeout=20000, service="org.freedesktop.DBus")
        return
    except Error:
        exe = shutil.which("kdeconnectd") or "/usr/lib/x86_64-linux-gnu/libexec/kdeconnectd"
        if not os.path.exists(exe):
            raise
        subprocess.Popen([exe], start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)


START = _start


def start():
    START()


def state() -> str:
    """'nogi' (no GLib bindings), 'nobus', 'missing' (KDE Connect not installed), 'stopped' or 'running'."""
    if not has_gi():
        return "nogi"
    try:
        if running():
            return "running"
    except Error:
        return "nobus"
    return "stopped" if installed() else "missing"


def this_pc() -> str:
    return call(ROOT, DAEMON, "announcedName") or ""


def rename_pc(name: str):
    name = " ".join(name.split())[:32]
    if not name:
        raise Error(tr("grimoire.spells.phonel.kdc", "Type a name first"))
    call(ROOT, DAEMON, "setAnnouncedName", "s", (name,))


def refresh_network():
    """Look for devices again (KDE Connect re-announces this PC on every network)."""
    call(ROOT, DAEMON, "forceOnNetworkChange")


# ---------------------------------------------------------------- devices
def _plugin(p: dict, name: str) -> bool:
    return f"kdeconnect_{name}" in p.get("plugins", ())


def device(dev: str) -> dict:
    """One device as the page shows it."""
    path = dev_path(dev)
    p = props(path, DEVICE)
    # a nearby device picks its own name: one line, so it can't add lines of its own to the pairing prompt
    d = {"id": dev, "name": " ".join(str(p.get("name") or dev).split()) or dev, "type": str(p.get("type") or "phone"),
         "reachable": bool(p.get("isReachable")), "paired": bool(p.get("isPaired")),
         "requested": bool(p.get("isPairRequested")), "by_peer": bool(p.get("isPairRequestedByPeer")),
         "supported": sorted(p.get("supportedPlugins") or []), "plugins": [], "battery": None, "signal": None,
         "key": "", "mounted": False}
    if d["paired"] and d["reachable"]:
        try:
            d["plugins"] = sorted(call(path, DEVICE, "loadedPlugins") or [])
        except Error:
            pass
    if d["requested"] or d["by_peer"]:
        try:
            d["key"] = str(call(path, DEVICE, "verificationKey") or "")
        except Error:
            pass
    if _plugin(d, "battery"):
        try:
            b = props(dev_path(dev, "battery"), DEVICE + ".battery")
            if int(b.get("charge", -1)) >= 0:
                d["battery"] = {"charge": int(b["charge"]), "charging": bool(b.get("isCharging"))}
        except Error:
            pass
    if _plugin(d, "connectivity_report"):
        try:
            c = props(dev_path(dev, "connectivity_report"), DEVICE + ".connectivity_report")
            if int(c.get("cellularNetworkStrength", -1)) >= 0:
                d["signal"] = {"type": str(c.get("cellularNetworkType") or ""),
                               "strength": int(c["cellularNetworkStrength"])}
        except Error:
            pass
    if _plugin(d, "sftp"):
        try:
            d["mounted"] = bool(call(dev_path(dev, "sftp"), DEVICE + ".sftp", "isMounted"))
        except Error:
            pass
    return d


def snapshot() -> dict:
    """Everything the page's frame needs: state, this PC's name, the devices. Never raises."""
    s = state()
    snap = {"state": s, "name": "", "devices": [], "error": ""}
    if s != "running":
        return snap
    try:
        snap["name"] = this_pc()
        ids = call(ROOT, DAEMON, "devices", "bb", (False, False)) or []
        for dev in ids:
            try:
                snap["devices"].append(device(dev))
            except (Error, TypeError, ValueError):
                continue                      # it went away between the two calls, or answered oddly
    except Error as err:
        snap["error"] = str(err)
    # paired first (connected ones on top), then nearby devices, each by name
    snap["devices"].sort(key=lambda d: (not d["paired"], not d["reachable"], d["name"].lower()))
    return snap


def pair(dev: str):
    call(dev_path(dev), DEVICE, "requestPairing")


def accept(dev: str):
    call(dev_path(dev), DEVICE, "acceptPairing")


def cancel_pairing(dev: str):
    """Withdraws our request, or turns down the phone's."""
    call(dev_path(dev), DEVICE, "cancelPairing")


def unpair(dev: str):
    call(dev_path(dev), DEVICE, "unpair")


def plugins(dev: str, supported: list[str]) -> list[tuple[str, bool]]:
    """(plugin id, enabled) for each plugin both sides support."""
    out = []
    for pid in supported:
        try:
            out.append((pid, bool(call(dev_path(dev), DEVICE, "isPluginEnabled", "s", (pid,)))))
        except Error:
            continue
    return out


def set_plugin(dev: str, pid: str, on: bool):
    call(dev_path(dev), DEVICE, "setPluginEnabled", "sb", (pid, on))


def plugin_name(pid: str) -> str:
    return tr("grimoire.spells.phonel.kdc", PLUGINS[pid]) if pid in PLUGINS else \
        pid.removeprefix("kdeconnect_").replace("_", " ").capitalize()


# ---------------------------------------------------------------- one-shot actions
def ping(dev: str):
    call(dev_path(dev, "ping"), DEVICE + ".ping", "sendPing")


def ring(dev: str):
    call(dev_path(dev, "findmyphone"), DEVICE + ".findmyphone", "ring")


def send_files(dev: str, files: list[str]) -> int:
    """Sends local files (KDE Connect copies them in the background); returns how many."""
    urls = [Path(f).resolve().as_uri() for f in files if Path(f).is_file()]
    if not urls:
        raise Error(tr("grimoire.spells.phonel.kdc", "Only files can be sent, not folders"))
    call(dev_path(dev, "share"), DEVICE + ".share", "shareUrls", "as", (urls,))
    return len(urls)


def send_clipboard(dev: str):
    """Sends what's on this PC's clipboard now."""
    call(dev_path(dev, "clipboard"), DEVICE + ".clipboard", "sendClipboard")


# ---------------------------------------------------------------- the phone's files (sftp)
def mount(dev: str, wait: float = 15.0) -> str:
    """Mounts the phone's storage (sshfs through KDE Connect) and returns the folder to open."""
    import time
    path, iface = dev_path(dev, "sftp"), DEVICE + ".sftp"
    if not call(path, iface, "isMounted"):
        call(path, iface, "mount")
        end = time.monotonic() + wait
        while not call(path, iface, "isMounted"):
            err = str(call(path, iface, "getMountError") or "")
            if err:
                raise Error(err)
            if time.monotonic() > end:
                raise Error(tr("grimoire.spells.phonel.kdc", "The phone didn't answer. Unlock it and allow "
                                                             "file access in its KDE Connect app."))
            time.sleep(0.3)
    point = str(call(path, iface, "mountPoint") or "")
    dirs = call(path, iface, "getDirectories") or {}
    # the first storage the phone lists ("All files", the SD card…) is where people expect to land
    for d in dirs:
        if os.path.isdir(d):
            return d
    if not point:
        raise Error(tr("grimoire.spells.phonel.kdc", "KDE Connect didn't say where it mounted the phone"))
    return point


def unmount(dev: str):
    call(dev_path(dev, "sftp"), DEVICE + ".sftp", "unmount")


# ---------------------------------------------------------------- notifications
def notifications(dev: str) -> list[dict]:
    path, iface = dev_path(dev, "notifications"), DEVICE + ".notifications"
    out = []
    for pid in call(path, iface, "activeNotifications") or []:
        try:
            p = props(f"{path}/{pid}", iface + ".notification")
        except Error:
            continue
        out.append({"id": pid, "app": str(p.get("appName") or ""), "title": str(p.get("title") or ""),
                    "text": str(p.get("text") or ""), "ticker": str(p.get("ticker") or ""),
                    "dismissable": bool(p.get("dismissable")), "reply": str(p.get("replyId") or ""),
                    "silent": bool(p.get("silent"))})
    return out


def dismiss(dev: str, nid: str):
    call(f"{dev_path(dev, 'notifications')}/{nid}", DEVICE + ".notifications.notification", "dismiss")


def reply_notification(dev: str, nid: str, text: str):
    call(f"{dev_path(dev, 'notifications')}/{nid}", DEVICE + ".notifications.notification", "sendReply", "s",
         (text,))


# ---------------------------------------------------------------- text messages
def parse_message(m) -> dict | None:
    """KDE Connect's ConversationMessage struct (isa(s)xiixixa(xsss)) → dict; None if it isn't one."""
    try:
        event, body, addresses, date, kind, read, thread = m[:7]
        return {"body": str(body), "addresses": [str(a[0]) if isinstance(a, (tuple, list)) else str(a)
                                                 for a in addresses],
                "date": int(date), "type": int(kind), "read": bool(read), "thread": int(thread),
                "uid": int(m[7]) if len(m) > 7 else 0, "event": int(event)}
    except (TypeError, ValueError, IndexError):
        return None


def conversations(dev: str) -> list[dict]:
    """The newest message of each conversation KDE Connect has (newest first)."""
    out = []
    for m in call(dev_path(dev), DEVICE + ".conversations", "activeConversations") or []:
        msg = parse_message(m)
        if msg:
            out.append(msg)
    return sorted(out, key=lambda m: -m["date"])


def request_threads(dev: str):
    """Asks the phone for its conversation list; they arrive as conversationCreated/Updated signals."""
    call(dev_path(dev), DEVICE + ".conversations", "requestAllConversationThreads")


def request_conversation(dev: str, thread: int, start: int = 0, end: int = 60):
    """Asks for one conversation's messages (newest `end`); they arrive as conversationUpdated signals."""
    call(dev_path(dev), DEVICE + ".conversations", "requestConversation", "xii", (thread, start, end))


def reply_sms(dev: str, thread: int, text: str):
    call(dev_path(dev), DEVICE + ".conversations", "replyToConversation", "xsav", (thread, text, []))


def send_sms(dev: str, numbers: list[str], text: str):
    _, GLib = _gio()
    addresses = [GLib.Variant("(s)", (n,)) for n in numbers]
    call(dev_path(dev), DEVICE + ".conversations", "sendWithoutConversation", "avsav", (addresses, text, []))


# ---------------------------------------------------------------- the phone's media
def media(dev: str) -> dict:
    p = props(dev_path(dev, "mprisremote"), DEVICE + ".mprisremote")
    return {"players": [str(x) for x in p.get("playerList") or []], "player": str(p.get("player") or ""),
            "playing": bool(p.get("isPlaying")), "volume": int(p.get("volume") or 0),
            "length": int(p.get("length") or 0), "position": int(p.get("position") or 0),
            "title": str(p.get("title") or ""), "artist": str(p.get("artist") or ""),
            "album": str(p.get("album") or ""), "can_seek": bool(p.get("canSeek"))}


def media_action(dev: str, action: str):
    if action not in MEDIA_ACTIONS:
        raise Error(action)
    call(dev_path(dev, "mprisremote"), DEVICE + ".mprisremote", "sendAction", "s", (action,))


def media_player(dev: str, player: str):
    set_prop(dev_path(dev, "mprisremote"), DEVICE + ".mprisremote", "player", "s", player)


def media_volume(dev: str, volume: int):
    set_prop(dev_path(dev, "mprisremote"), DEVICE + ".mprisremote", "volume", "i", max(0, min(100, int(volume))))


def media_refresh(dev: str):
    call(dev_path(dev, "mprisremote"), DEVICE + ".mprisremote", "requestPlayerList")


# ---------------------------------------------------------------- the phone's commands
def commands(dev: str) -> list[dict]:
    """The commands set up on the other device: [{key, name, command}] by name."""
    raw = props(dev_path(dev, "remotecommands"), DEVICE + ".remotecommands").get("commands") or b""
    if isinstance(raw, (list, tuple)):
        raw = bytes(raw)
    try:
        data = json.loads(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw) or "{}")
    except ValueError:
        return []
    if not isinstance(data, dict):
        return []
    out = [{"key": str(k), "name": str(v.get("name") or k), "command": str(v.get("command") or "")}
           for k, v in data.items() if isinstance(v, dict)]
    return sorted(out, key=lambda c: c["name"].lower())


def run_command(dev: str, key: str):
    call(dev_path(dev, "remotecommands"), DEVICE + ".remotecommands", "triggerCommand", "s", (key,))


# ---------------------------------------------------------------- remote input
def keyboard_active(dev: str) -> bool:
    try:
        return bool(props(dev_path(dev, "remotekeyboard"), DEVICE + ".remotekeyboard").get("remoteState"))
    except Error:
        return False


def type_text(dev: str, text: str):
    """Types text on the phone (its KDE Connect keyboard must be the active one)."""
    if text:
        call(dev_path(dev, "remotekeyboard"), DEVICE + ".remotekeyboard", "sendKeyPress", "sibbbb",
             (text, 0, False, False, False, False))


def press(dev: str, key: str):
    call(dev_path(dev, "remotekeyboard"), DEVICE + ".remotekeyboard", "sendKeyPress", "sibbbb",
         ("", KEYS[key], False, False, False, False))


def move_pointer(dev: str, dx: int, dy: int):
    call(dev_path(dev, "remotecontrol"), DEVICE + ".remotecontrol", "moveCursor", "(ii)", ((int(dx), int(dy)),))


def click(dev: str, kind: str = "singleclick"):
    """kind: singleclick, rightclick, middleclick, doubleclick."""
    _, GLib = _gio()
    call(dev_path(dev, "remotecontrol"), DEVICE + ".remotecontrol", "sendCommand", "a{sv}",
         ({kind: GLib.Variant("b", True)},))


def scroll(dev: str, dy: int):
    _, GLib = _gio()
    call(dev_path(dev, "remotecontrol"), DEVICE + ".remotecontrol", "sendCommand", "a{sv}",
         ({"scroll": GLib.Variant("b", True), "dx": GLib.Variant("d", 0.0), "dy": GLib.Variant("d", float(dy))},))


# ---------------------------------------------------------------- status line
def status_line() -> str:
    """For the home card: quick, never raises."""
    try:
        s = state()
        if s == "missing":
            return tr("grimoire.spells.phonel.kdc", "KDE Connect isn't installed")
        if s != "running":
            return tr("grimoire.spells.phonel.kdc", "KDE Connect is off")
        quick = 800                        # the home page asks on the UI thread: never hang it on a busy daemon
        ids = call(ROOT, DAEMON, "devices", "bb", (True, True), timeout=quick) or []
        if not ids:
            paired = call(ROOT, DAEMON, "devices", "bb", (False, True), timeout=quick) or []
            return tr("grimoire.spells.phonel.kdc", "No phone paired yet") if not paired else \
                tr("grimoire.spells.phonel.kdc", "%n paired device(s), none connected", n=len(paired))
        name = call(dev_path(ids[0]), PROPS, "Get", "ss", (DEVICE, "name"), timeout=quick) or ids[0]
        bits = [tr("grimoire.spells.phonel.kdc", "{name} connected").format(name=isolate(name))]
        try:
            charge = call(dev_path(ids[0], "battery"), PROPS, "Get", "ss", (DEVICE + ".battery", "charge"),
                          timeout=quick)
            if isinstance(charge, int) and charge >= 0:
                bits.append(tr("grimoire.spells.phonel.kdc", "Battery {n}%").format(n=charge))
        except Error:
            pass
        if len(ids) > 1:
            bits.append(tr("grimoire.spells.phonel.kdc", "%n more", n=len(ids) - 1))
        return " · ".join(bits)
    except Exception:
        return tr("grimoire.spells.phonel.kdc", "KDE Connect isn't answering")


# ---------------------------------------------------------------- contact names
def _digits(number: str) -> str:
    d = "".join(c for c in number if c.isdigit())
    return d[-9:]                         # national and international forms of one number match


def contacts(dev: str) -> dict:
    """Phone number (last 9 digits) → name, from the vCards KDE Connect's contacts plugin keeps for the device
    (~/.local/share/kpeoplevcard/kdeconnect-<id>/). Read only; {} when it isn't syncing."""
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "kpeoplevcard" / f"kdeconnect-{dev}"
    names = {}
    try:
        files = sorted(base.glob("*.vcf"))[:5000]
    except OSError:
        return names
    for f in files:
        try:
            text = f.read_text(errors="replace")[:65536]
        except OSError:
            continue
        name, numbers = "", []
        for line in text.replace("\r\n ", "").splitlines():
            key, _, value = line.partition(":")
            key = key.split(";")[0].upper()
            if key == "FN":
                name = value.strip()
            elif key == "TEL":
                numbers.append(value)
        for n in numbers:
            if name and _digits(n):
                names.setdefault(_digits(n), name)
    return names


def contact_name(names: dict, address: str) -> str:
    return names.get(_digits(address), "") if _digits(address) else ""
