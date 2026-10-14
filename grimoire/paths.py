# SPDX-License-Identifier: GPL-3.0-or-later
"""Where Grimoire keeps its files (XDG locations).

CONFIG is the active profile's settings folder. Accounts (accounts.py, session.py) give each signed-in account its
own folder, CONFIG_ROOT/profiles/<account id>/, and a guest session a throwaway one in the runtime dir. Every module
reads CONFIG once, at import, so the profile is chosen here first: GRIMOIRE_PROFILE (set by the hub or a standalone
window after sign-in, and inherited by what they start), else the account last signed in on this PC (so timers, the
tray and hotkeys follow it), else CONFIG_ROOT itself (installs from before accounts). DATA and CACHE are shared:
they hold machine state (OptimizeL's originals, history) that belongs to the PC, not to a profile.
"""
import json
import os
import re
import sys
from pathlib import Path

HOME = Path.home()
DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "grimoire"
CONFIG_ROOT = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "grimoire"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "grimoire"
ASSETS = Path(__file__).resolve().parent / "assets"
ROOT = Path(__file__).resolve().parent.parent      # this copy: a checkout, ~/.local/share/grimoire/app or a package's
SYSTEM_BIN = Path("/usr/bin")

PROFILES = CONFIG_ROOT / "profiles"
SESSION = CONFIG_ROOT / "session.json"         # who signed in last and whether to stay signed in (session.py)
GUEST = "guest"
_PROFILE_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")   # an account's uuid


def valid_profile(profile: str) -> bool:
    return profile == GUEST or bool(_PROFILE_ID.fullmatch(profile or ""))


def guest_dir() -> Path:
    """The guest profile: in the runtime dir (memory, gone at logout) when there is one, else the cache."""
    run = os.environ.get("XDG_RUNTIME_DIR", "")
    base = Path(run) / "grimoire" if run and Path(run).is_dir() else CACHE
    return base / "guest-profile"


def profile_dir(profile: str) -> Path:
    if profile == GUEST:
        return guest_dir()
    return PROFILES / profile if valid_profile(profile) else CONFIG_ROOT


def _initial_profile() -> str:
    env = os.environ.get("GRIMOIRE_PROFILE", "")
    if valid_profile(env):
        return env
    try:
        last = json.loads(SESSION.read_text()).get("last") or {}
        pid = last.get("id", "") if isinstance(last, dict) else ""
    except (OSError, ValueError, AttributeError):
        pid = ""
    return pid if valid_profile(pid) and pid != GUEST else ""


for _d in (DATA, CONFIG_ROOT, CACHE):
    _d.mkdir(parents=True, exist_ok=True)
PROFILE = _initial_profile()
CONFIG = profile_dir(PROFILE)
CONFIG.mkdir(parents=True, exist_ok=True, mode=0o700)


def activate(profile: str) -> bool:
    """Make profile the active one for this process and everything it starts. Call before any spell module is
    imported; returns False when a loaded module already holds the old CONFIG (the caller restarts the process)."""
    global CONFIG, PROFILE
    new = profile_dir(profile)
    new.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.environ["GRIMOIRE_PROFILE"] = profile if valid_profile(profile) else ""
    if new == CONFIG:
        PROFILE = profile
        return True
    old, me = CONFIG, sys.modules[__name__]
    stale = [n for n, m in list(sys.modules.items())
             if n.startswith("grimoire") and m is not me and getattr(m, "CONFIG", None) == old]
    CONFIG, PROFILE = new, profile
    return not stale


def packaged() -> str:
    """'deb', 'arch'… when a distro package installed this copy system-wide (it leaves a PACKAGED file in ROOT), else
    "". A packaged copy is updated by the package manager, never by Grimoire's own updater."""
    try:
        return (ROOT / "PACKAGED").read_text().strip()[:20] or "package"
    except OSError:
        return ""


def command(name: str) -> Path:
    """What autostart entries, hotkeys and launches run: the ~/.local/bin link of a per-user install, else a system
    package's /usr/bin command, else this copy's own bin/."""
    link = HOME / ".local/bin" / name
    if link.exists():
        return link
    if packaged() and (SYSTEM_BIN / name).exists():
        return SYSTEM_BIN / name
    return ROOT / "bin" / name


def unit_command(name: str) -> str:
    """command() for a systemd user unit's ExecStart (%h keeps per-user units free of the home path)."""
    cmd = command(name)
    return f"%h/.local/bin/{name}" if cmd == HOME / ".local/bin" / name or not packaged() else str(cmd)
