# SPDX-License-Identifier: GPL-3.0-or-later
"""Who is using Grimoire on this PC: the signed-in account, a guest, or nobody yet. No Qt.

CONFIG_ROOT/session.json (0600) remembers the account last signed in (id, username, how) and whether to stay
signed in. Each account's settings live in CONFIG_ROOT/profiles/<account id>/ (paths.py): the first account
signed in on this PC starts with a copy of the settings Grimoire had before accounts existed, later ones start
empty (or from their saved settings on the server). A guest gets a throwaway profile in the runtime dir, emptied
at the next guest start unless another guest window still uses it; "Create account to keep them" copies it into
the new account's profile.

The refresh token is the only secret, and it only goes to the system keyring (keystore.py), only when "Keep me
signed in" is ticked. KEYRING is swappable for tests.
"""
import fcntl
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from grimoire import accounts, keystore, paths
from grimoire.github import Token

KEYRING = keystore
CURRENT: "accounts.Session | None" = None          # this process's live session (tokens in memory)
_guest_lock = None                                  # held while this process uses the guest profile
SKIP = {"session.json", "profiles"}                 # never copied between profiles


@dataclass
class Who:
    profile: str                                    # account id, or paths.GUEST
    username: str = ""
    provider: str = ""

    @property
    def guest(self) -> bool:
        return self.profile == paths.GUEST


def _read() -> dict:
    try:
        d = json.loads(paths.SESSION.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(d: dict):
    """Atomically, created 0600 (it names your username; no secrets)."""
    paths.SESSION.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.SESSION.with_name(f".session.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(d, f, indent=1)
        os.replace(tmp, paths.SESSION)
    finally:
        tmp.unlink(missing_ok=True)


def _who(entry) -> Who | None:
    if not isinstance(entry, dict):
        return None
    pid = str(entry.get("id", ""))
    name = str(entry.get("username", ""))[:32]
    if not paths.valid_profile(pid) or pid == paths.GUEST:
        return None
    return Who(pid, name, str(entry.get("provider", ""))[:10])


def last() -> Who | None:
    return _who(_read().get("last"))


def remembered() -> Who | None:
    """The account to open without asking, when "Keep me signed in" was ticked."""
    d = _read()
    return _who(d.get("last")) if d.get("remember") is True else None


def active() -> Who | None:
    """Who this process runs as (after the sign-in screen or a remembered session)."""
    p = os.environ.get("GRIMOIRE_PROFILE", "")
    if p == paths.GUEST:
        return Who(paths.GUEST)
    w = last()
    return w if w and w.profile == p else (Who(p) if paths.valid_profile(p) else None)


# ---------------------------------------------------------------- starting a session
def begin(s: "accounts.Session", remember: bool, from_guest: bool = False) -> bool:
    """Make s the signed-in account of this process. Returns paths.activate()'s answer (False = restart)."""
    global CURRENT
    uid = s.user.id
    fresh = not paths.profile_dir(uid).exists()
    if fresh:
        _seed(uid, from_guest)
    d = _read()
    d["last"] = {"id": uid, "username": s.user.username, "provider": s.user.provider,
                 "signed_in": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    d["remember"] = bool(remember)
    _write(d)
    if remember:
        try:
            KEYRING.store(s.refresh.reveal(), accounts.keyring_attrs(uid), "Grimoire Linux account")
        except keystore.KeyringError:
            d["remember"] = False                      # no keyring: stay signed in for this run only
            _write(d)
    else:
        _forget_token(uid)
    CURRENT = s
    return paths.activate(uid)


def begin_guest() -> bool:
    """Start (or join) the guest profile. A new guest session empties the old one first."""
    global _guest_lock
    gdir = paths.guest_dir()
    gdir.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = open(gdir.parent / "guest-profile.lock", "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _wipe_guest(gdir)                               # nobody else is using it
        fcntl.flock(lock, fcntl.LOCK_SH)
    except BlockingIOError:
        fcntl.flock(lock, fcntl.LOCK_SH)                # another guest window is open: share its profile
    _guest_lock = lock
    return paths.activate(paths.GUEST)


def join_guest() -> bool:
    """A window started by a guest session (GRIMOIRE_PROFILE=guest): share its profile, never empty it."""
    global _guest_lock
    gdir = paths.guest_dir()
    gdir.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _guest_lock = open(gdir.parent / "guest-profile.lock", "a")
    fcntl.flock(_guest_lock, fcntl.LOCK_SH)
    return paths.activate(paths.GUEST)


def _wipe_guest(gdir: Path):
    """The guest profile only ever holds Grimoire's own settings files, written by a guest session that was told
    they won't be kept; it lives in the runtime dir (memory) when there is one."""
    if gdir.is_symlink():
        gdir.unlink()
    elif gdir.is_dir() and gdir.name == "guest-profile":
        shutil.rmtree(gdir)
    gdir.mkdir(parents=True, exist_ok=True, mode=0o700)


def _copy_tree(src: Path, dest: Path):
    """Copy settings files from src into dest: regular files and folders only, never over an existing file."""
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    for p in sorted(src.iterdir()) if src.is_dir() else ():
        if p.name in SKIP or p.name.endswith((".tmp", ".lock")) or p.is_symlink():
            continue
        if p.is_dir():
            _copy_tree(p, dest / p.name)
        elif p.is_file() and not (dest / p.name).exists():
            shutil.copy2(p, dest / p.name)


def _seed(uid: str, from_guest: bool):
    """A new profile on this PC: the guest's settings when they made the account, else (first account only) the
    settings from before accounts existed. The originals stay where they are."""
    target = paths.profile_dir(uid)
    others = [p for p in paths.PROFILES.iterdir() if p.is_dir()] if paths.PROFILES.is_dir() else []
    if from_guest:
        _copy_tree(paths.guest_dir(), target)
    elif not others:
        _copy_tree(paths.CONFIG_ROOT, target)
    target.mkdir(parents=True, exist_ok=True, mode=0o700)


# ---------------------------------------------------------------- tokens
def _forget_token(uid: str):
    try:
        KEYRING.delete(accounts.keyring_attrs(uid))
    except keystore.KeyringError:
        pass


def live(backend=None) -> "accounts.Session":
    """A usable session for server calls (sync), refreshing it from the keyring after a remembered start."""
    global CURRENT
    backend = backend or accounts.BACKEND
    who = active()
    if who is None or who.guest:
        raise accounts.AccountError("Sign in to use your account.")
    if CURRENT is not None and CURRENT.user.id == who.profile and CURRENT.fresh():
        return CURRENT
    refresh = CURRENT.refresh if CURRENT is not None and CURRENT.user.id == who.profile else None
    if refresh is None:
        try:
            stored = KEYRING.load(accounts.keyring_attrs(who.profile))
        except keystore.KeyringError as e:
            raise accounts.AccountError(str(e)) from None
        if not stored:
            raise accounts.AccountError("Your sign-in expired. Sign out and sign in again.")
        refresh = Token(stored)
    s = backend.refresh(refresh, who.provider or "password")
    s.user.username = s.user.username or who.username
    CURRENT = s
    if _read().get("remember") is True:                 # refresh tokens are single-use: keep the new one
        try:
            KEYRING.store(s.refresh.reveal(), accounts.keyring_attrs(s.user.id), "Grimoire Linux account")
        except keystore.KeyringError:
            pass
    return s


def end(backend=None):
    """Sign out: tell the server (best effort), forget the token and stop remembering. Settings stay on disk."""
    global CURRENT
    who = active()
    if who and not who.guest:
        try:
            s = live(backend)
            (backend or accounts.BACKEND).sign_out(s)
        except accounts.AccountError:
            pass                                       # offline or already expired: signing out here still works
        _forget_token(who.profile)
    d = _read()
    d["remember"] = False
    _write(d)
    CURRENT = None
