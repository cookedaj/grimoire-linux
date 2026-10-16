# SPDX-License-Identifier: GPL-3.0-or-later
"""CloudL's backend (no Qt): rclone remotes, their mounts in ~/Cloud as per-user systemd services, space, sync state.

rclone keeps every account's keys in its own config file (rclone.conf). Grimoire never opens that file: it asks rclone
for the remotes' names and types only (`listremotes --json`), and adding an account runs rclone's own sign-in, which
talks to the browser and writes the file itself. Output from that sign-in is kept in memory and scrubbed of anything
that looks like a key before a line is shown.

A mount is `rclone mount <remote>: ~/Cloud/<remote> --vfs-cache-mode full` run by
~/.config/systemd/user/grimoire-cloudl-<remote>.service (Type=notify, logs to the journal), written and started only
when you press Mount. Its remote-control socket in $XDG_RUNTIME_DIR answers read-only questions (vfs/stats: what is
still uploading); rclone refuses its config/command calls there since no rc password is set.
"""
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path

from grimoire.i18n import ltr, tr
from grimoire.paths import HOME

CLOUD = HOME / "Cloud"
UNITS = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "systemd/user"
PREFIX = "grimoire-cloudl-"
MARK = "# written by Grimoire Linux (CloudL)"
# rclone's own rule for remote names (letters, digits, _ . + @ - and spaces, not starting with - or a space), minus
# a trailing space; it also keeps quotes, % and $ out of the unit file
NAME = re.compile(r"[\w.+@][\w.+@ -]*(?<! )")
# the services CloudL's Add page signs in to, in its order: (rclone type, shown name, suggested remote name)
SERVICES = [("drive", "Google Drive", "gdrive"), ("onedrive", "OneDrive", "onedrive"), ("dropbox", "Dropbox", "dropbox")]
TYPES = {"drive": "Google Drive", "onedrive": "OneDrive", "dropbox": "Dropbox", "box": "Box", "pcloud": "pCloud",
         "mega": "MEGA", "s3": "S3", "sftp": "SFTP", "webdav": "WebDAV", "ftp": "FTP", "smb": "SMB",
         "protondrive": "Proton Drive", "jottacloud": "Jottacloud", "koofr": "Koofr", "yandex": "Yandex Disk",
         "gphotos": "Google Photos", "local": "Local folder", "memory": "Memory", "crypt": "Encrypted (crypt)",
         "alias": "Alias", "union": "Union", "combine": "Combine", "b2": "Backblaze B2", "swift": "Swift",
         "azureblob": "Azure Blob", "azurefiles": "Azure Files", "sharefile": "ShareFile", "nextcloud": "Nextcloud"}
# what can never leave the sign-in's output: token blobs, client secrets, codes in URLs other than the local one
SECRET = re.compile(r"token|secret|refresh|access_|password|\{|\}|code=", re.I)
AUTH_URL = re.compile(r"http://127\.0\.0\.1:\d+/auth\?state=[\w-]+")


def _run(*args: str, timeout=20, check=False) -> subprocess.CompletedProcess:
    """rclone, systemctl… never with a terminal or stdin: a password-protected rclone.conf must fail, not wait."""
    return subprocess.run(list(args), capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
                          check=check)


RUN = _run                      # the stub point for tests


def rclone() -> str | None:
    return shutil.which("rclone")


def available() -> bool:
    return rclone() is not None


def fuse_ok() -> bool:
    return shutil.which("fusermount3") is not None or shutil.which("fusermount") is not None


def _err(r: subprocess.CompletedProcess) -> str:
    """rclone's last message, without its log prefix (and never a line that looks like a key)."""
    lines = [re.sub(r"^\d{4}/\d\d/\d\d \d\d:\d\d:\d\d (?:\w+\s*:)?\s*", "", ln).strip()
             for ln in (r.stderr or r.stdout or "").splitlines()]
    lines = [ln for ln in lines if ln and not SECRET.search(ln)]
    return lines[-1] if lines else f"exit code {r.returncode}"


# ---------------------------------------------------------------- remotes
def valid_name(name: str) -> bool:
    return bool(NAME.fullmatch(name or "")) and name not in (".", "..") and len(name) <= 64


def type_label(kind: str) -> str:
    if kind == "local":
        return tr("grimoire.spells.cloudl.rclone", "Local folder")
    if kind == "memory":
        return tr("grimoire.spells.cloudl.rclone", "In memory")
    return TYPES.get(kind, kind)


def remotes() -> list[dict]:
    """[{name, type}] from rclone, in its order. Raises OSError with rclone's message."""
    exe = rclone()
    if not exe:
        raise OSError(tr("grimoire.spells.cloudl.rclone", "rclone isn't installed"))
    r = RUN(exe, "listremotes", "--json", "--ask-password=false")
    if r.returncode:
        raise OSError(_err(r))
    try:
        rows = json.loads(r.stdout or "[]") or []
    except ValueError as e:
        raise OSError(str(e)) from e
    return [{"name": str(x.get("name", "")).rstrip(":"), "type": str(x.get("type", ""))}
            for x in rows if isinstance(x, dict) and x.get("name")]


def config_file() -> str:
    """Where rclone keeps its config (only the path; the file itself is never read here)."""
    exe = rclone()
    r = RUN(exe, "config", "file") if exe else None
    lines = [ln.strip() for ln in (r.stdout if r else "").splitlines() if ln.strip()]
    return lines[-1] if lines and lines[-1].startswith("/") else str(HOME / ".config/rclone/rclone.conf")


def suggest_name(base: str, taken: set[str]) -> str:
    """gdrive, gdrive2, gdrive3… (rclone remotes and ~/Cloud folders both count as taken)."""
    n, name = 1, base
    while name in taken or (CLOUD / name).exists():
        n += 1
        name = f"{base}{n}"
    return name


def sign_in_command(name: str, kind: str) -> list[str]:
    """rclone's own sign-in: it opens the browser on the service's page and waits on 127.0.0.1 for the answer."""
    if not valid_name(name):
        raise ValueError(tr("grimoire.spells.cloudl.rclone", "Use letters, digits, spaces and . _ + @ - in the name"))
    return [rclone() or "rclone", "config", "create", name, kind, "--ask-password=false"]


def scrub(line: str) -> str:
    """A line of the sign-in's output that is safe to show ("" when it isn't)."""
    line = re.sub(r"^(?:\d{4}/\d\d/\d\d \d\d:\d\d:\d\d )?(?:NOTICE|INFO|DEBUG)\s*:\s*", "",
                  re.sub(r"^\d{4}/\d\d/\d\d \d\d:\d\d:\d\d ", "", line.strip()))
    if AUTH_URL.search(line):
        return AUTH_URL.search(line).group(0)
    return "" if SECRET.search(line) else line[:300]


def auth_url(line: str) -> str:
    m = AUTH_URL.search(line)
    return m.group(0) if m else ""


def delete_remote(name: str):
    """Forget the account in rclone.conf (its files online stay). Stops and removes its mount first."""
    if not valid_name(name):
        raise ValueError(name)
    forget_mount(name)
    r = RUN(rclone() or "rclone", "config", "delete", name, "--ask-password=false")
    if r.returncode:
        raise OSError(_err(r))


# ---------------------------------------------------------------- mounts
def mountpoint(name: str) -> Path:
    return CLOUD / name


def unit(name: str) -> str:
    """grimoire-cloudl-<name>.service, the name escaped the way systemd-escape does it (spaces → \\x20)."""
    out = []
    for i, ch in enumerate(name):
        if ch.isascii() and (ch.isalnum() or ch in "_:" or (ch in ".-" and i)):
            out.append(ch)
        else:
            out.extend(f"\\x{b:02x}" for b in ch.encode())
    return f"{PREFIX}{''.join(out)}.service"


def unit_path(name: str) -> Path:
    return UNITS / unit(name)


def _runtime() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")


def socket_path(name: str) -> Path:
    """The mount's rc socket: in the per-user runtime dir (0700), named by a hash so any remote name fits."""
    return _runtime() / f"grimoire-cloudl-{hashlib.sha1(name.encode()).hexdigest()[:12]}.sock"


def _home_rel(path: str) -> str:
    """%h/… for paths in the home folder, so units carry no home path."""
    home = str(HOME)
    return "%h" + path[len(home):] if path == home or path.startswith(home + "/") else path


def unit_text(name: str, exe: str, conf: str) -> str:
    if not valid_name(name):
        raise ValueError(name)
    if re.search(r'["\\%$\n]', conf) or re.search(r'["\\%$\n ]', exe):
        raise ValueError(tr("grimoire.spells.cloudl.rclone",
                            "rclone's config path has characters a service file can't hold: {path}").format(path=ltr(conf)))
    point = f"%h/Cloud/{name}"
    sock = f"%t/{socket_path(name).name}"
    fuser = shutil.which("fusermount3") or shutil.which("fusermount") or "/usr/bin/fusermount3"
    return f"""{MARK}: mounts the rclone remote "{name}" at ~/Cloud/{name}
# Remove it from CloudL (Forget mount) or with ./uninstall.sh; your files online are not touched.
[Unit]
Description=CloudL: {name} at ~/Cloud/{name}
Documentation=man:rclone(1)

[Service]
Type=notify
ExecStartPre=/usr/bin/mkdir -p "{point}"
ExecStart={exe} mount "{name}:" "{point}" --config "{_home_rel(conf)}" --vfs-cache-mode full --log-systemd --log-level INFO --rc --rc-addr "unix://{sock}"
ExecStop={fuser} -uz "{point}"
Restart=on-failure
RestartSec=15

[Install]
WantedBy=default.target
"""


def _systemctl(*args: str, check=True, timeout=60) -> subprocess.CompletedProcess:
    r = RUN("systemctl", "--user", *args, timeout=timeout)
    if check and r.returncode:
        raise OSError(_err(r))
    return r


def mounts() -> dict[str, str]:
    """{mount point: source} of every rclone FUSE mount (from /proc/self/mountinfo)."""
    found = {}
    try:
        text = Path("/proc/self/mountinfo").read_text()
    except OSError:
        return found
    unesc = lambda s: re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), s)      # noqa: E731
    for line in text.splitlines():
        left, _, right = line.partition(" - ")
        parts, rest = left.split(), right.split()
        if len(parts) > 4 and len(rest) > 1 and rest[0] == "fuse.rclone":
            found[unesc(parts[4])] = unesc(rest[1])
    return found


def is_mounted(name: str) -> bool:
    return str(mountpoint(name)) in mounts()


def service_state(name: str) -> dict:
    """{written, enabled, active} for the remote's unit ('active', 'failed', 'activating', 'inactive'…)."""
    path = unit_path(name)
    if not path.exists():
        return {"written": False, "enabled": False, "active": "inactive"}
    r = _systemctl("show", unit(name), "-p", "ActiveState", "-p", "UnitFileState", check=False, timeout=15)
    props = dict(ln.split("=", 1) for ln in r.stdout.splitlines() if "=" in ln)
    return {"written": True, "enabled": props.get("UnitFileState") == "enabled",
            "active": props.get("ActiveState", "inactive")}


def ours(name: str) -> bool:
    try:
        return unit_path(name).read_text().startswith(MARK)
    except OSError:
        return False


def mount(name: str, at_login: bool = True):
    """Write the service, start it (and enable it for later logins). Raises OSError/ValueError with what went wrong."""
    exe = rclone()
    if not exe:
        raise OSError(tr("grimoire.spells.cloudl.rclone", "rclone isn't installed"))
    if not valid_name(name):
        raise ValueError(name)
    point = mountpoint(name)
    if is_mounted(name):
        return
    if point.is_symlink() or (point.exists() and not point.is_dir()):
        raise OSError(tr("grimoire.spells.cloudl.rclone", "{path} is in the way: it isn't a folder").format(
            path=ltr(f"~/Cloud/{name}")))
    if point.is_dir() and any(point.iterdir()):
        raise OSError(tr("grimoire.spells.cloudl.rclone",
                         "{path} already has files in it. Move them somewhere else first; a mount would hide them")
                      .format(path=ltr(f"~/Cloud/{name}")))
    path = unit_path(name)
    if path.exists() and not ours(name):
        raise OSError(tr("grimoire.spells.cloudl.rclone", "{file} exists and wasn't written by CloudL").format(
            file=path.name))
    point.mkdir(parents=True, exist_ok=True)
    UNITS.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(unit_text(name, exe, config_file()))
    tmp.replace(path)
    _systemctl("daemon-reload")
    _systemctl("reset-failed", unit(name), check=False)
    _systemctl("enable" if at_login else "disable", unit(name), check=at_login)
    r = _systemctl("start", unit(name), check=False, timeout=120)
    if r.returncode:
        raise OSError(last_error(name) or _err(r))


def set_at_login(name: str, on: bool):
    if not ours(name):
        raise OSError(tr("grimoire.spells.cloudl.rclone", "Mount it once first"))
    _systemctl("enable" if on else "disable", unit(name))


def unmount(name: str):
    """Unmount now: fusermount3 -u first (it refuses while a program is using a file there), then stop the service.
    The mount stays set up: it comes back at the next login if that's on, or with Mount."""
    point = mountpoint(name)
    if is_mounted(name):
        fuser = shutil.which("fusermount3") or shutil.which("fusermount")
        if not fuser:
            raise OSError(tr("grimoire.spells.cloudl.rclone", "fusermount3 isn't installed: {command}").format(
                command=ltr("sudo apt install fuse3")))
        r = RUN(fuser, "-u", str(point), timeout=30)
        if r.returncode:
            msg = (r.stderr or "").strip()
            if "busy" in msg.lower():
                raise OSError(tr("grimoire.spells.cloudl.rclone",
                                 "A program is still using files in {path}. Close it, then unmount again").format(
                    path=ltr(f"~/Cloud/{name}")))
            raise OSError(msg or _err(r))
    if unit_path(name).exists():
        _systemctl("stop", unit(name), check=False, timeout=60)


def forget_mount(name: str):
    """Stop, disable and remove the service; remove ~/Cloud/<name> only when it is an empty folder."""
    if unit_path(name).exists():
        if not ours(name):
            raise OSError(tr("grimoire.spells.cloudl.rclone", "{file} exists and wasn't written by CloudL").format(
                file=unit(name)))
        unmount(name)
        _systemctl("disable", "--now", unit(name), check=False)
        unit_path(name).unlink()
        _systemctl("daemon-reload", check=False)
        _systemctl("reset-failed", unit(name), check=False)
    point = mountpoint(name)
    if point.is_dir() and not point.is_symlink() and not is_mounted(name):
        try:
            point.rmdir()                       # only succeeds when empty: never removes anything of yours
        except OSError:
            pass


# ---------------------------------------------------------------- space and sync
def about(name: str) -> dict:
    """{total, used, free, trashed} in bytes (any of them may be missing). Asks the service, so it can take a while."""
    r = RUN(rclone() or "rclone", "about", f"{name}:", "--json", "--ask-password=false", timeout=60)
    if r.returncode:
        msg = _err(r)
        if "doesn't support about" in msg:
            raise OSError(tr("grimoire.spells.cloudl.rclone", "This service doesn't report its space"))
        raise OSError(msg)
    data = json.loads(r.stdout or "{}")
    return {k: int(v) for k, v in data.items() if isinstance(v, (int, float))}


def vfs_stats(name: str) -> dict | None:
    """The running mount's cache state (uploads in progress and queued, files that failed), or None."""
    path = socket_path(name)
    if not path.exists():
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect(str(path))
            s.sendall(b"POST /vfs/stats HTTP/1.0\r\nHost: localhost\r\nContent-Type: application/json\r\n"
                      b"Content-Length: 2\r\n\r\n{}")
            data = b""
            while chunk := s.recv(65536):
                data += chunk
                if len(data) > 1 << 20:
                    break
        head, _, body = data.partition(b"\r\n\r\n")
        if b" 200 " not in head.split(b"\r\n", 1)[0]:
            return None
        cache = json.loads(body).get("diskCache") or {}
        return {"uploading": int(cache.get("uploadsInProgress", 0)), "queued": int(cache.get("uploadsQueued", 0)),
                "errored": int(cache.get("erroredFiles", 0)), "cached": int(cache.get("bytesUsed", 0))}
    except (OSError, ValueError, AttributeError):
        return None


def journal(name: str, lines: int = 200) -> list[dict]:
    """The mount's recent log: [{time (µs), priority, message}], oldest first."""
    r = RUN("journalctl", "--user", "-u", unit(name), "-n", str(lines), "-o", "json", "--no-pager",
            "--output-fields=MESSAGE,PRIORITY,__REALTIME_TIMESTAMP", timeout=20)
    out = []
    for ln in r.stdout.splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        msg = e.get("MESSAGE")
        if isinstance(msg, list):                        # journald sends non-UTF-8 messages as byte arrays
            msg = bytes(msg).decode(errors="replace")
        if not isinstance(msg, str) or SECRET.search(msg) and "token" in msg.lower():
            continue
        out.append({"time": int(e.get("__REALTIME_TIMESTAMP", 0) or 0), "priority": int(e.get("PRIORITY", 6) or 6),
                    "message": msg.strip()})
    return out


def last_error(name: str) -> str:
    errs = [e["message"] for e in journal(name, 60) if e["priority"] <= 3]
    return errs[-1] if errs else ""


def status_line() -> str:
    """The home card's line: how many remotes, how many mounted (no network)."""
    if not available():
        return tr("grimoire.spells.cloudl.rclone", "rclone isn't installed")
    try:
        names = [r["name"] for r in remotes()]
    except (OSError, subprocess.SubprocessError):
        return tr("grimoire.spells.cloudl.rclone", "rclone can't read its config")
    mounted = mounts()
    return status_line_from(len(names), sum(str(mountpoint(n)) in mounted for n in names))


def status_line_from(count: int, up: int) -> str:
    if not count:
        return tr("grimoire.spells.cloudl.rclone", "No cloud drives yet")
    return " · ".join([tr("grimoire.spells.cloudl.rclone", "%n cloud drive(s)", n=count),
                       tr("grimoire.spells.cloudl.rclone", "%n mounted in {path}", n=up).format(path=ltr("~/Cloud"))])
