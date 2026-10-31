# SPDX-License-Identifier: GPL-3.0-or-later
"""The only door SettingL has to the system: KDE's own tools and D-Bus (no Qt).

Every command, read or write, goes through RUN(args), the stub point for tests. Writes use the supported tools
(kwriteconfig6 --notify so the running KWin/Plasma reloads, busctl for D-Bus, the system's own *ctl tools, which
ask polkit), never edits of files Plasma rewrites. KDE config is *read* by parsing it here (fast: one page reads
dozens of keys), with the system-wide defaults in XDG_CONFIG_DIRS underneath, as KConfig cascades them.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from grimoire.i18n import tr


def _run(args: list[str], timeout: float = 20) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args, 127, "", tr("grimoire.spells.settingl.kde", "{tool} isn't installed").format(tool=args[0])
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args, 124, "", tr("grimoire.spells.settingl.kde", "{tool} didn't answer in time").format(tool=args[0])
        )


RUN = _run  # stub point: tests swap it so nothing on the real system changes


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def check(args: list[str], timeout: float = 30) -> str:
    """Run a command that changes something; raise its own message when it fails, return its output."""
    r = RUN(args, timeout)
    if r.returncode:
        msg = (r.stderr or r.stdout or "").strip().splitlines()
        if r.returncode == 126 or any("authoriz" in m.lower() or "not authorized" in m.lower() for m in msg[-1:]):
            raise RuntimeError(tr("grimoire.spells.settingl.kde", "cancelled"))
        raise RuntimeError(
            msg[-1]
            if msg
            else tr("grimoire.spells.settingl.kde", "{tool} failed ({code})").format(
                tool=Path(args[0]).name, code=r.returncode
            )
        )
    return r.stdout


# ---------------------------------------------------------------- KDE config files
def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _config_files(name: str) -> list[Path]:
    """name's files from the lowest priority (system defaults) to the user's own."""
    dirs = [d for d in os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg").split(":") if d]
    return [Path(d) / name for d in reversed(dirs)] + [config_home() / name]


def _unescape(v: str) -> str:
    out, i = [], 0
    while i < len(v):
        c = v[i]
        if c == "\\" and i + 1 < len(v):
            nxt = v[i + 1]
            out.append({"s": " ", "t": "\t", "n": "\n", "r": "\r", "\\": "\\"}.get(nxt, "\\" + nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _groups(header: str) -> tuple[str, ...]:
    """'[Applications][org.kde.dolphin]' -> ('Applications', 'org.kde.dolphin')"""
    parts, depth, cur = [], 0, ""
    for c in header:
        if c == "[" and depth == 0:
            depth, cur = 1, ""
        elif c == "]" and depth == 1:
            parts.append(cur)
            depth = 0
        elif depth:
            cur += c
    return tuple(parts)


def parse(name: str) -> dict[tuple[str, ...], dict[str, str]]:
    """A KDE config file as {(group, subgroup…): {key: value}}, merged over its system defaults."""
    out: dict[tuple[str, ...], dict[str, str]] = {}
    for path in _config_files(name):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        group: tuple[str, ...] = ()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("["):
                group = _groups(line)
                continue
            key, sep, value = line.partition("=")
            if not sep:
                continue
            key = key.strip()
            if key.endswith("[$e]") or key.endswith("[$i]"):
                key = key[:-4]
            out.setdefault(group, {})[key] = _unescape(value.strip())
    return out


def read(name: str, group, key: str, default: str = "") -> str:
    groups = (group,) if isinstance(group, str) else tuple(group)
    return parse(name).get(groups, {}).get(key, default)


def as_bool(v: str, default: bool = False) -> bool:
    v = (v or "").strip().lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off"):
        return False
    return default


def as_int(v: str, default: int) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def write(name: str, group, key: str, value, bool_=False, notify=True):
    """kwriteconfig6 one key (--notify: the running KWin/Plasma reloads it). value None deletes the key."""
    args = ["kwriteconfig6"] + (["--notify"] if notify else []) + ["--file", name]
    for g in (group,) if isinstance(group, str) else tuple(group):
        args += ["--group", g]
    args += ["--key", key]
    if value is None:
        args += ["--delete", "--", ""]
    else:
        if bool_ or isinstance(value, bool):
            args += ["--type", "bool"]
            value = "true" if value else "false"
        args += ["--", str(value)]  # "--": a value starting with "-" is the value, not an option
    check(args)


# ---------------------------------------------------------------- D-Bus (busctl)
def _bus(system: bool) -> list[str]:
    return ["busctl", "--system" if system else "--user", "--json=short"]


def _end_options(cmd: list[str], verb: str) -> list[str]:
    """busctl reads "-0.5" as an option: everything after the verb is arguments ("--" before the verb)."""
    i = cmd.index(verb)
    return cmd[:i] + ["--"] + cmd[i:]


def _plain(v):
    """busctl's JSON {"type": t, "data": d} (nested in variants) → plain Python values."""
    if isinstance(v, dict) and set(v) == {"type", "data"}:
        return _plain(v["data"])
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


def bus_props(dest: str, path: str, iface: str, system=False) -> dict:
    """All of an object's properties on one interface ({} when the service isn't there)."""
    r = RUN(_bus(system) + ["call", dest, path, "org.freedesktop.DBus.Properties", "GetAll", "s", iface], 10)
    if r.returncode:
        return {}
    try:
        data = json.loads(r.stdout)["data"]
        return _plain(data[0]) if data else {}
    except (ValueError, KeyError, IndexError, TypeError):
        return {}


def bus_call(
    dest: str,
    path: str,
    iface: str,
    method: str,
    sig: str = "",
    *args,
    system=False,
    interactive=False,
    quiet=False,
    timeout=20,
):
    """Call a D-Bus method; returns its (plain) answer list. Raises with the service's message unless quiet."""
    cmd = (
        _bus(system)
        + (["--allow-interactive-authorization=yes"] if interactive else [])
        + ["call", dest, path, iface, method]
        + ([sig, *map(str, args)] if sig else [])
    )
    r = RUN(_end_options(cmd, "call"), timeout)
    if r.returncode:
        if quiet:
            return None
        msg = (r.stderr or r.stdout).strip().splitlines()
        text = msg[-1] if msg else method
        if "authoriz" in text.lower() or "dismissed" in text.lower():
            raise RuntimeError(tr("grimoire.spells.settingl.kde", "cancelled"))
        raise RuntimeError(text.removeprefix("Call failed: "))
    try:
        return _plain(json.loads(r.stdout)["data"]) if r.stdout.strip() else []
    except (ValueError, KeyError):
        return []


def bus_set(dest: str, path: str, iface: str, prop: str, sig: str, value, system=False):
    if isinstance(value, bool):
        value = "true" if value else "false"
    cmd = ["busctl", "--system" if system else "--user", "set-property", dest, path, iface, prop, sig, str(value)]
    r = RUN(_end_options(cmd, "set-property"), 15)
    if r.returncode:
        msg = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(
            msg[-1]
            if msg
            else tr("grimoire.spells.settingl.kde", "{tool} failed ({code})").format(tool="busctl", code=r.returncode)
        )


def kwin_reconfigure():
    bus_call("org.kde.KWin", "/KWin", "org.kde.KWin", "reconfigure", quiet=True)


# ---------------------------------------------------------------- KDE's own modules
def open_module(module: str):
    """Open one of KDE's settings modules in its own window (kcmshell6), else in System Settings."""
    if not re.fullmatch(r"[\w.-]+", module or ""):
        raise ValueError(module)
    for cmd in (["kcmshell6", module], ["systemsettings", module]):
        if have(cmd[0]):
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
    raise RuntimeError(tr("grimoire.spells.settingl.kde", "KDE's System Settings isn't installed"))


def launch(args: list[str]):
    """Start a program of the desktop's (an editor, kinfocenter, a wizard) without waiting for it."""
    if not have(args[0]):
        raise RuntimeError(tr("grimoire.spells.settingl.kde", "{tool} isn't installed").format(tool=args[0]))
    subprocess.Popen(
        args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
    )


OPEN = open_module  # stub points for tests: nothing opens
LAUNCH = launch
