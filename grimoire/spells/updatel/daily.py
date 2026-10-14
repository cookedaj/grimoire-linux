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


def load() -> dict:
    s = _read(STATE, {})
    return s if isinstance(s, dict) and isinstance(s.get("items"), list) else {}


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
        return "never"
    s = max(0, (now or time.time()) - t)
    if s < 90:
        return "just now"
    if s < 3600:
        return "{n} min ago".format(n=round(s / 60))
    if s < 86400 * 2:
        return "{n} h ago".format(n=round(s / 3600))
    return "{n} days ago".format(n=round(s / 86400))


def status_line(now: float | None = None) -> str:
    """'N updates · checked 2 h ago' (cheap: reads the cache, runs nothing)."""
    s = load()
    restart = sources.REBOOT.exists()
    if not s:
        line = "Not checked yet"
    else:
        n = len(s["items"])
        when = ago(s.get("t"), now)
        if n == 0:
            line = "Up to date · checked {when}".format(when=when)
        elif n == 1:
            line = "1 update · checked {when}".format(when=when)
        else:
            line = "{n} updates · checked {when}".format(n=n, when=when)
    return line + (" · restart required" if restart else "")


def counts(items: list[dict]) -> dict[str, int]:
    out = {}
    for i in items:
        out[i["source"]] = out.get(i["source"], 0) + 1
    return out


# ---------------------------------------------------------------- notifications
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
    detail = ", ".join(f"{sources.NAMES[s]} {c[s]}" for s in sources.SOURCES if s in c)
    n = len(keys)
    title = "1 update is available" if n == 1 else "{n} updates are available".format(n=n)
    if send(title, "{detail}. Open UpdateL to see what's new and install them.".format(detail=detail)):
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
