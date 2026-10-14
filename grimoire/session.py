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
import stat
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from grimoire import accounts, keystore, paths
from grimoire.github import Token
from grimoire.i18n import tr

KEYRING = keystore
CURRENT: "accounts.Session | None" = None          # this process's live session (tokens in memory)
_guest_lock = None                                  # held while this process uses the guest profile
_refreshing = threading.Lock()                      # one refresh at a time: refresh tokens are single-use
_keyring_behind = False                             # our last store failed: the keyring holds a spent token
SKIP = {"session.json", "profiles"}                 # never copied between profiles
HANDOFF = "GRIMOIRE_SESSION_FD"


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


def _guest_base() -> Path:
    """The guest profile's folder, made 0700 and checked: ours, a real folder (not a link), writable only by us.
    XDG_RUNTIME_DIR is normally /run/user/<uid>; if it points somewhere shared (say /tmp), another user could
    have planted "grimoire" there as a link to make the wipe below empty a folder of ours."""
    gdir = paths.guest_dir()
    base = gdir.parent
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    st = base.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o022:
        raise OSError(0, tr("grimoire.session", "{path} isn't a private folder of yours; not using it for the guest "
                                                "profile.").format(path=base))
    return gdir


def begin_guest() -> bool:
    """Start (or join) the guest profile. A new guest session empties the old one first."""
    global _guest_lock
    gdir = _guest_base()
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
    gdir = _guest_base()
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
    """A usable session for server calls (sync), refreshing it from the keyring after a remembered start.
    Refresh tokens are single-use (and reusing a spent one can sign the account out everywhere), so refreshes are
    serialized: across this process's threads by a lock, across Grimoire windows by a lock file, and a remembered
    session always refreshes with the keyring's token, the newest any window has stored."""
    global CURRENT, _keyring_behind
    backend = backend or accounts.BACKEND
    who = active()
    if who is None or who.guest:
        raise accounts.AccountError(tr("grimoire.session", "Sign in to use your account."))
    with _refreshing:
        if CURRENT is not None and CURRENT.user.id == who.profile and CURRENT.fresh():
            return CURRENT
        with _refresh_lock():
            mine = CURRENT.refresh if CURRENT is not None and CURRENT.user.id == who.profile else None
            remember = _read().get("remember") is True and last() is not None and last().profile == who.profile
            stored = None
            if (remember and not _keyring_behind) or mine is None:
                try:
                    stored = KEYRING.load(accounts.keyring_attrs(who.profile))
                except keystore.KeyringError as e:
                    if mine is None:
                        raise accounts.AccountError(str(e)) from None
            refresh = Token(stored) if stored else mine
            if refresh is None:
                raise accounts.AccountError(tr("grimoire.session",
                                               "Your sign-in expired. Sign out and sign in again."))
            s = backend.refresh(refresh, who.provider or "password")
            s.user.username = s.user.username or who.username
            CURRENT = s
            if remember:                                 # keep the new one for the next refresh (any window)
                try:
                    KEYRING.store(s.refresh.reveal(), accounts.keyring_attrs(s.user.id), "Grimoire Linux account")
                    _keyring_behind = False
                except keystore.KeyringError:
                    _keyring_behind = True
            return s


class _refresh_lock:
    """An flock on CACHE/session-refresh.lock (best effort: without it, only the in-process lock applies)."""

    def __enter__(self):
        try:
            paths.CACHE.mkdir(parents=True, exist_ok=True)
            self.f = open(paths.CACHE / "session-refresh.lock", "a")
            fcntl.flock(self.f, fcntl.LOCK_EX)
        except OSError:
            self.f = None
        return self

    def __exit__(self, *exc):
        if self.f is not None:
            self.f.close()


# ---------------------------------------------------------------- across a restart
def handoff():
    """Before exec'ing this program again: pass the live session (refresh token included) to the new process
    through an inherited pipe whose number goes in GRIMOIRE_SESSION_FD. Only the next process reads it (adopt()
    closes it and drops the variable), so nothing it starts later sees the token; it never touches a file."""
    s = CURRENT
    if s is None or os.environ.get("GRIMOIRE_PROFILE") != s.user.id:
        return
    data = json.dumps({"id": s.user.id, "username": s.user.username, "provider": s.user.provider,
                       "access": s.access.reveal(), "refresh": s.refresh.reveal(),
                       "expires_at": s.expires_at}).encode()
    if len(data) > 60000:                               # must fit the pipe's buffer: nobody reads it before exec
        return
    r, w = os.pipe()
    try:
        os.write(w, data)
    finally:
        os.close(w)
    os.set_inheritable(r, True)
    os.environ[HANDOFF] = str(r)


def adopt():
    """In the restarted process: take the session handed over by handoff(), if any (once, at import)."""
    global CURRENT
    fd = os.environ.pop(HANDOFF, "")
    if not fd.isdigit():
        return
    fd, chunks = int(fd), []
    try:
        if fd < 3 or not stat.S_ISFIFO(os.fstat(fd).st_mode):
            return                                      # not ours: leave that descriptor alone
    except OSError:
        return
    try:
        os.set_blocking(fd, False)
        while len(b"".join(chunks)) < 65536 and (chunk := os.read(fd, 65536)):
            chunks.append(chunk)
        d = json.loads(b"".join(chunks))
        uid = str(d["id"])
        if not paths.valid_profile(uid) or uid == paths.GUEST or os.environ.get("GRIMOIRE_PROFILE") != uid:
            return
        name = str(d.get("username", ""))[:32]
        CURRENT = accounts.Session(accounts.User(uid, name, str(d.get("provider", ""))[:10] or "password"),
                                   Token(str(d["access"])), Token(str(d["refresh"])), float(d["expires_at"]))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


adopt()


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
