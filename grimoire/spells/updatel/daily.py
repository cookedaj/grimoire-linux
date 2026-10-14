# SPDX-License-Identifier: GPL-3.0-or-later
"""UpdateL's last check (a cache file), its status line and the optional daily check (no Qt).

    grimoire-updatel check [--notify]|enable|disable|status

The daily check is a systemd user timer running `check --notify` as you: it reads what APT already knows (Ubuntu's
own apt-daily timer refreshes the lists), asks Flatpak, Snap and fwupd, saves the result for the page and the home
card, and sends one desktop notification when there are updates it hasn't told you about yet. It never installs.
"""
import json
import subprocess
import sys
import time
import traceback

from grimoire.i18n import tr
from grimoire.paths import CACHE, CONFIG, HOME, unit_command
from grimoire.spells.updatel import sources

STATE = CACHE / "updatel.json"
SETTINGS = CONFIG / "updatel.json"
LOG = CACHE / "updatel.log"
UNIT = "grimoire-updatel-check"
UNITS = HOME / ".config/systemd/user"
DEFAULTS = {"notify": True}

SERVICE = """[Unit]
Description=Grimoire UpdateL: look for system updates

[Service]
Type=oneshot
ExecStart={exe} check --notify
Nice=10
IOSchedulingClass=idle
"""
TIMER = """[Unit]
Description=Look for system updates once a day (Grimoire UpdateL)

[Timer]
OnCalendar=daily
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
"""


def _read(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


# what each item needs (by source) for the page and a plan; a cache from an older or broken run is cut to those
_NEEDS = {"apt": ("name",), "flatpak": ("name", "ref", "scope"), "snap": ("name",), "fwupd": ("name", "device")}


def _usable(i) -> bool:
    return (isinstance(i, dict) and i.get("source") in _NEEDS
            and all(isinstance(i.get(k), str) for k in ("key", "title", "current", "new", *_NEEDS[i["source"]])))


def load() -> dict:
    s = _read(STATE, {})
    if not (isinstance(s, dict) and isinstance(s.get("items"), list)):
        return {}
    s["items"] = [i for i in s["items"] if _usable(i)]
    return s


def settings() -> dict:
    s = _read(SETTINGS, {})
    out = dict(DEFAULTS)
    if isinstance(s, dict):
        out.update({k: v for k, v in s.items() if k in DEFAULTS and type(v) is type(DEFAULTS[k])})
    return out


def save_settings(s: dict):
    _write(SETTINGS, s)


def log(msg: str):
    try:
        if LOG.exists() and LOG.stat().st_size > 200_000:
            LOG.write_text(LOG.read_text()[-100_000:])
        with LOG.open("a") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg.rstrip() + "\n")
    except OSError:
        pass


def check(now: float | None = None) -> dict:
    """Look everywhere, save it (keeping what was last notified) and return it."""
    result = sources.check()
    result["t"] = now or time.time()
    result["notified"] = load().get("notified", [])
    _write(STATE, result)
    return result


def ago(t: float | None, now: float | None = None) -> str:
    if not t:
        return tr("grimoire.spells.updatel.daily", "never", "last check")
    s = max(0, (now or time.time()) - t)
    if s < 90:
        return tr("grimoire.spells.updatel.daily", "just now")
    if s < 3600:
        return tr("grimoire.spells.updatel.daily", "%n min ago", n=round(s / 60))
    if s < 86400 * 2:
        return tr("grimoire.spells.updatel.daily", "%n h ago", n=round(s / 3600))
    return tr("grimoire.spells.updatel.daily", "%n day(s) ago", n=round(s / 86400))


def status_line(now: float | None = None) -> str:
    """'N updates · checked 2 h ago' (cheap: reads the cache, runs nothing)."""
    s = load()
    restart = sources.REBOOT.exists()
    if not s:
        line = tr("grimoire.spells.updatel.daily", "Not checked yet")
    else:
        n = len(s["items"])
        when = ago(s.get("t"), now)
        if n == 0:
            line = tr("grimoire.spells.updatel.daily", "Up to date · checked {when}").format(when=when)
        else:
            line = tr("grimoire.spells.updatel.daily", "%n update(s) · checked {when}", n=n).format(when=when)
    return line + (" · " + tr("grimoire.spells.updatel.daily", "restart required") if restart else "")


def counts(items: list[dict]) -> dict[str, int]:
    out = {}
    for i in items:
        out[i["source"]] = out.get(i["source"], 0) + 1
    return out


# ---------------------------------------------------------------- notifications
_qt = []                                     # the timer's QCoreApplication and translators (kept alive)


def _language():
    """The timer runs without Grimoire's app, where tr() gives English: load UpdateL's catalog for the user's
    language into a bare QCoreApplication so the notification speaks it (no display needed)."""
    try:
        from PySide6.QtCore import QCoreApplication, QTranslator
        from grimoire import i18n
        app = QCoreApplication.instance() or QCoreApplication([])
        _qt.append(app)
        for qm in i18n.catalogs(i18n.current()):
            if qm.parent.name in ("updatel", "core"):
                t = QTranslator(app)
                if t.load(str(qm)) and app.installTranslator(t):
                    _qt.append(t)
    except Exception as e:                   # English, then; the check itself must not fail over this
        log(f"language not loaded: {e}")


def notify(title: str, body: str) -> bool:
    """One desktop notification from "UpdateL" over D-Bus; notify-send if dbus-python is missing."""
    from grimoire.spells.systeml.alerts import _icon
    icon = _icon()
    try:
        import dbus
        n = dbus.SessionBus().get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications")
        n.Notify("UpdateL", dbus.UInt32(0), icon, title, body, dbus.Array([], signature="s"),
                 {"desktop-entry": "grimoire", "urgency": dbus.Byte(1)}, -1,
                 dbus_interface="org.freedesktop.Notifications", timeout=5)
        return True
    except Exception as e:
        log(f"D-Bus notify failed ({e}); trying notify-send")
    try:
        return subprocess.run(["notify-send", "-a", "UpdateL", "-i", icon, "-h", "string:desktop-entry:grimoire",
                               title, body], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.TimeoutExpired) as e:
        log(f"notify-send failed: {e}")
        return False


def notify_new(result: dict, send=notify) -> bool:
    """Tell you about updates once: only when some aren't in the set last notified about."""
    keys = sorted(f"{i['key']}={i['new']}" for i in result["items"])
    if not keys or set(keys) <= set(result.get("notified", [])) or not settings()["notify"]:
        return False
    c = counts(result["items"])
    detail = ", ".join(f"{sources.name(s)} {c[s]}" for s in sources.SOURCES if s in c)
    title = tr("grimoire.spells.updatel.daily", "%n update(s) available", n=len(keys))
    if send(title, tr("grimoire.spells.updatel.daily", "{detail}. Open UpdateL to see what's new and install them.")
            .format(detail=detail)):
        result["notified"] = keys
        _write(STATE, result)
        return True
    return False


# ---------------------------------------------------------------- the timer
def _systemctl(*args: str, check=False) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=30, check=check)


def set_enabled(on: bool):
    if on:
        UNITS.mkdir(parents=True, exist_ok=True)
        (UNITS / f"{UNIT}.service").write_text(SERVICE.format(exe=unit_command("grimoire-updatel")))
        (UNITS / f"{UNIT}.timer").write_text(TIMER)
        _systemctl("daemon-reload", check=True)
        _systemctl("enable", "--now", f"{UNIT}.timer", check=True)
    else:
        _systemctl("disable", "--now", f"{UNIT}.timer")


def enabled() -> bool:
    try:
        return _systemctl("is-active", "--quiet", f"{UNIT}.timer").returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main(argv: list[str]):
    cmd = argv[0] if argv else "status"
    _language()                                  # the notification and the status line in your language
    if cmd == "check":
        try:
            r = check()
            log("checked: {n} update(s)".format(n=len(r["items"])))
            if "--notify" in argv:
                notify_new(r)
            print(status_line())
        except Exception:
            log("check crashed:\n" + traceback.format_exc())
            sys.exit(1)
    elif cmd in ("enable", "disable"):
        set_enabled(cmd == "enable")
        print("daily check on" if cmd == "enable" else "daily check off")
    elif cmd == "status":
        print(status_line())
        print("daily check on" if enabled() else "daily check off")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
