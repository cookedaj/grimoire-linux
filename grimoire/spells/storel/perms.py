# SPDX-License-Identifier: GPL-3.0-or-later
"""Flatpak permissions (Flatseal's job, no Qt): what an app may reach, and your own overrides.

An app's sandbox is its metadata's [Context], then the system's overrides, then yours (`flatpak override --user`,
kept in ~/.local/share/flatpak/overrides/<app>); a "!" entry takes a permission away. StoreL only writes your
overrides, for the common switches in PERMS, and Reset drops all of yours for that app. Nothing needs root.
Every command goes through RUN (sources.RUN by default), the stub point for tests.
"""
import configparser
import re
from pathlib import Path

from grimoire.i18n import tr_noop
from grimoire.spells.storel import sources

APP_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+)+")
SYSTEM_OVERRIDES = Path("/var/lib/flatpak/overrides")
# (id, metadata key, value, flag on, flag off, label, what it means)
PERMS = [
    ("network", "shared", "network", "--share=network", "--unshare=network",
     tr_noop("grimoire.spells.storel.perms", "Network"),
     tr_noop("grimoire.spells.storel.perms", "Go online and reach other computers")),
    ("wayland", "sockets", "wayland", "--socket=wayland", "--nosocket=wayland",
     tr_noop("grimoire.spells.storel.perms", "Wayland windows"),
     tr_noop("grimoire.spells.storel.perms", "Show windows on the desktop")),
    ("x11", "sockets", "x11", "--socket=x11", "--nosocket=x11",
     tr_noop("grimoire.spells.storel.perms", "X11 windows"),
     tr_noop("grimoire.spells.storel.perms", "The older display system; it lets an app see other X11 windows")),
    ("fallback-x11", "sockets", "fallback-x11", "--socket=fallback-x11", "--nosocket=fallback-x11",
     tr_noop("grimoire.spells.storel.perms", "X11 as a fallback"),
     tr_noop("grimoire.spells.storel.perms", "X11 only when Wayland isn't there")),
    ("pulseaudio", "sockets", "pulseaudio", "--socket=pulseaudio", "--nosocket=pulseaudio",
     tr_noop("grimoire.spells.storel.perms", "Sound"),
     tr_noop("grimoire.spells.storel.perms", "Play sound and record from microphones")),
    ("cups", "sockets", "cups", "--socket=cups", "--nosocket=cups",
     tr_noop("grimoire.spells.storel.perms", "Printing"), tr_noop("grimoire.spells.storel.perms", "Talk to printers")),
    ("ssh-auth", "sockets", "ssh-auth", "--socket=ssh-auth", "--nosocket=ssh-auth",
     tr_noop("grimoire.spells.storel.perms", "SSH keys"),
     tr_noop("grimoire.spells.storel.perms", "Use your SSH agent's keys")),
    ("session-bus", "sockets", "session-bus", "--socket=session-bus", "--nosocket=session-bus",
     tr_noop("grimoire.spells.storel.perms", "Full session bus"),
     tr_noop("grimoire.spells.storel.perms", "Talk to any program in your session (a wide hole in the sandbox)")),
    ("system-bus", "sockets", "system-bus", "--socket=system-bus", "--nosocket=system-bus",
     tr_noop("grimoire.spells.storel.perms", "Full system bus"),
     tr_noop("grimoire.spells.storel.perms", "Talk to any system service")),
    ("dri", "devices", "dri", "--device=dri", "--nodevice=dri",
     tr_noop("grimoire.spells.storel.perms", "Graphics acceleration"),
     tr_noop("grimoire.spells.storel.perms", "Use the GPU")),
    ("devices", "devices", "all", "--device=all", "--nodevice=all",
     tr_noop("grimoire.spells.storel.perms", "All devices"),
     tr_noop("grimoire.spells.storel.perms", "Webcams, controllers, USB devices and the GPU")),
    ("home", "filesystems", "home", "--filesystem=home", "--nofilesystem=home",
     tr_noop("grimoire.spells.storel.perms", "Your home folder"),
     tr_noop("grimoire.spells.storel.perms", "Read and change every file in your home")),
    ("host", "filesystems", "host", "--filesystem=host", "--nofilesystem=host",
     tr_noop("grimoire.spells.storel.perms", "All files"),
     tr_noop("grimoire.spells.storel.perms", "Every file on the system, other drives included")),
    ("xdg-download", "filesystems", "xdg-download", "--filesystem=xdg-download", "--nofilesystem=xdg-download",
     tr_noop("grimoire.spells.storel.perms", "Downloads"),
     tr_noop("grimoire.spells.storel.perms", "Your Downloads folder")),
    ("xdg-documents", "filesystems", "xdg-documents", "--filesystem=xdg-documents", "--nofilesystem=xdg-documents",
     tr_noop("grimoire.spells.storel.perms", "Documents"),
     tr_noop("grimoire.spells.storel.perms", "Your Documents folder")),
    ("xdg-pictures", "filesystems", "xdg-pictures", "--filesystem=xdg-pictures", "--nofilesystem=xdg-pictures",
     tr_noop("grimoire.spells.storel.perms", "Pictures"),
     tr_noop("grimoire.spells.storel.perms", "Your Pictures folder")),
    ("xdg-music", "filesystems", "xdg-music", "--filesystem=xdg-music", "--nofilesystem=xdg-music",
     tr_noop("grimoire.spells.storel.perms", "Music"), tr_noop("grimoire.spells.storel.perms", "Your Music folder")),
    ("xdg-videos", "filesystems", "xdg-videos", "--filesystem=xdg-videos", "--nofilesystem=xdg-videos",
     tr_noop("grimoire.spells.storel.perms", "Videos"), tr_noop("grimoire.spells.storel.perms", "Your Videos folder")),
]
GROUPS = [("shared", tr_noop("grimoire.spells.storel.perms", "Internet")),
          ("sockets", tr_noop("grimoire.spells.storel.perms", "Desktop and services")),
          ("devices", tr_noop("grimoire.spells.storel.perms", "Devices")),
          ("filesystems", tr_noop("grimoire.spells.storel.perms", "Files"))]
BY_ID = {p[0]: p for p in PERMS}


def _run(cmd, timeout=30):
    return sources.RUN(cmd, timeout=timeout)


RUN = _run


def parse_context(text: str) -> dict[str, list[str]]:
    """A keyfile's [Context] group → {"shared": [...], "sockets": [...], "devices": [...], "filesystems": [...]}."""
    cp = configparser.RawConfigParser(strict=False, interpolation=None, delimiters=("=",))
    cp.optionxform = str
    try:
        cp.read_string(text or "")
    except configparser.Error:
        return {}
    if not cp.has_section("Context"):
        return {}
    return {k: [v for v in cp.get("Context", k).split(";") if v] for k in cp.options("Context")}


def _name(entry: str) -> str:
    """'home:ro' → 'home', '!host' → 'host'."""
    return entry.lstrip("!").split(":")[0]


def merge(*layers: dict[str, list[str]]) -> dict[str, list[str]]:
    """Later layers win: "x" grants, "!x" takes away."""
    out: dict[str, dict[str, str]] = {}
    for layer in layers:
        for key, entries in layer.items():
            cur = out.setdefault(key, {})
            for e in entries:
                cur[_name(e)] = e
    return {k: [e for e in v.values() if not e.startswith("!")] for k, v in out.items()}


def state(context: dict[str, list[str]], pid: str) -> bool:
    _id, key, value, *_rest = BY_ID[pid]
    return any(_name(e) == value for e in context.get(key, []))


def overridden(user: dict[str, list[str]], pid: str) -> bool:
    _id, key, value, *_rest = BY_ID[pid]
    return any(_name(e) == value for e in user.get(key, []))


def read(app: str) -> dict:
    """{"base": the app's own, "system": system overrides, "user": yours, "effective": all merged,
    "text": `flatpak info --show-permissions` as shown by flatpak}."""
    if not APP_ID.fullmatch(app or ""):
        raise ValueError(app)
    meta = RUN(["flatpak", "info", "--show-metadata", "--", app])
    base = parse_context(meta.stdout) if meta.returncode == 0 else {}
    try:
        system = parse_context((SYSTEM_OVERRIDES / app).read_text())
    except (OSError, UnicodeDecodeError):
        system = {}
    user_r = RUN(["flatpak", "override", "--user", "--show", "--", app])
    user = parse_context(user_r.stdout) if user_r.returncode == 0 else {}
    shown = RUN(["flatpak", "info", "--show-permissions", "--", app])
    return {"base": base, "system": system, "user": user, "effective": merge(base, system, user),
            "text": shown.stdout.strip() if shown.returncode == 0 else ""}


def set_perm(app: str, pid: str, on: bool) -> str:
    """Write one of your overrides; '' when it worked, else flatpak's message."""
    if not APP_ID.fullmatch(app or "") or pid not in BY_ID:
        raise ValueError(app)
    flag = BY_ID[pid][3] if on else BY_ID[pid][4]
    r = RUN(["flatpak", "override", "--user", flag, "--", app])
    return "" if r.returncode == 0 else (r.stderr or r.stdout).strip()


def reset(app: str) -> str:
    """Drop every override of yours for this app (the system's stay)."""
    if not APP_ID.fullmatch(app or ""):
        raise ValueError(app)
    r = RUN(["flatpak", "override", "--user", "--reset", "--", app])
    return "" if r.returncode == 0 else (r.stderr or r.stdout).strip()
