# SPDX-License-Identifier: GPL-3.0-or-later
"""VaultL archives (no Qt): list, extract and make zip, tar (.gz/.xz/.bz2/.zst), single .gz/.xz/.bz2/.zst files,
7z and rar, so everyday archives need no Ark or PeaZip.

zip, tar and single compressed files use Python's own readers; 7z and rar go through the `7z` tool (rar needs its
codec, `7zip-rar`), else `bsdtar` turned into a tar stream that Python reads. Python writes every member itself:
names are cleaned (no absolute paths, no "..": those entries are skipped), only regular files and folders are
written, links are made last and only when they stay inside the extracted folder, devices and fifos never are,
sizes are counted as bytes come out (a bomb stops at the size it claimed, or before the disk fills). What `7z`
writes is scrubbed the same way afterwards. Everything lands in a hidden staging folder next to the destination
and moves into place under a free name (never over anything); a failure or a cancel removes only the staging.
Passwords reach `7z` on its stdin, never on the command line.
"""
import bz2
import gzip
import lzma
import os
import re
import secrets
import shutil
import stat
import subprocess
import tarfile
import threading
import time
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath

from grimoire.fsutil import free_name
from grimoire.i18n import tr

try:
    from compression import zstd
except ImportError:                                   # Python before 3.14
    zstd = None

ZIP, TAR, STREAM, SEVEN, RAR = "zip", "tar", "stream", "7z", "rar"
TAR_SUFFIXES = (".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".tbz", ".tar.zst", ".tzst",
                ".tar.zstd", ".tar")
SUFFIXES = TAR_SUFFIXES + (".zip", ".7z", ".rar", ".gz", ".xz", ".bz2", ".zst")
MAX_ENTRIES = 1_000_000
RESERVE = 512 * 1024 * 1024                           # always leave this much free on the destination drive
RATIO = 1000                                          # unknown sizes: more than 1000x the archive is a bomb
MIN_LIMIT = 1 << 30                                   # …but always allow at least this much
STAGING = ".grimoire-extract-"
CHUNK = 1 << 16
ENV = dict(os.environ, LC_ALL="C.UTF-8", LANG="C.UTF-8")


# ---------------------------------------------------------------- errors
class ArchiveError(RuntimeError):
    """Something the user should read (already translated)."""


class Missing(ArchiveError):
    """A tool isn't installed; `command` is the apt line that adds it."""

    def __init__(self, message: str, command: str):
        super().__init__(message)
        self.command = command


class NeedPassword(ArchiveError):
    def __init__(self, wrong=False):
        super().__init__(tr("grimoire.spells.vaultl.archive", "Wrong password.") if wrong
                         else tr("grimoire.spells.vaultl.archive", "This archive needs a password."))
        self.wrong = wrong


class UseSeven(Exception):
    """Python can't read this zip (AES, an unusual method): 7z can."""


class Cancelled(ArchiveError):
    def __init__(self):
        super().__init__(tr("grimoire.spells.vaultl.archive", "Cancelled."))


def _bomb() -> ArchiveError:
    return ArchiveError(tr("grimoire.spells.vaultl.archive",
                           "The archive holds more than it says it does (a zip bomb?). Stopped."))


def _damaged(e) -> ArchiveError:
    return ArchiveError(tr("grimoire.spells.vaultl.archive", "The archive is damaged: {error}").format(error=e))


def _no_room(need: int, free: int) -> ArchiveError:
    from grimoire.fsutil import human
    from grimoire.i18n import ltr
    return ArchiveError(tr("grimoire.spells.vaultl.archive", "Not enough space: needs {need}, {free} free.").format(
        need=ltr(human(need)), free=ltr(human(max(free - RESERVE, 0)))))


# ---------------------------------------------------------------- progress
class Progress:
    """Shared with the UI thread: `cancel()` from there, `report()`/`check()` from the worker."""

    def __init__(self, callback=None):
        self.callback = callback
        self.stop = threading.Event()
        self.done = self.total = 0
        self.label = ""
        self._last = 0.0

    def cancel(self):
        self.stop.set()

    def check(self):
        if self.stop.is_set():
            raise Cancelled()

    def report(self, done=None, total=None, label=None, force=False):
        if done is not None:
            self.done = done
        if total is not None:
            self.total = total
        if label is not None:
            self.label = label
        now = time.monotonic()
        if self.callback and (force or now - self._last > 0.1):
            self._last = now
            self.callback(self.done, self.total, self.label)


# ---------------------------------------------------------------- names and kinds
def clean_name(name: str) -> str | None:
    """A member name as a safe relative posix path, or None (absolute, "..", empty)."""
    name = name.replace("\x00", "")
    if name.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", name):
        return None
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def suffix(name: str) -> str:
    low = name.lower()
    return next((s for s in SUFFIXES if low.endswith(s) and len(low) > len(s)), "")


def is_archive(path: Path) -> bool:
    """By name only (cheap, for menus); `kind()` looks inside."""
    return bool(suffix(path.name))


def stem(path: Path) -> str:
    s = suffix(path.name)
    return path.name[:-len(s)] if s else path.stem


MAGIC = [(b"PK\x03\x04", ZIP), (b"PK\x05\x06", ZIP), (b"PK\x07\x08", ZIP), (b"7z\xbc\xaf\x27\x1c", SEVEN),
         (b"Rar!\x1a\x07", RAR), (b"\x1f\x8b", "gz"), (b"\xfd7zXZ\x00", "xz"), (b"BZh", "bz2"),
         (b"\x28\xb5\x2f\xfd", "zst")]


def _opener(comp: str):
    if comp == "gz":
        return gzip.open
    if comp == "xz":
        return lzma.open
    if comp == "bz2":
        return bz2.open
    if comp == "zst" and zstd:
        return zstd.open
    return None


def kind(path: Path) -> tuple[str, str]:
    """(kind, compression) from the file's first bytes: ZIP, TAR, STREAM, SEVEN or RAR, plus gz/xz/bz2/zst for
    compressed tars and single files. Raises ArchiveError for anything else."""
    try:
        if not stat.S_ISREG(path.stat().st_mode):         # a fifo named .zip would block forever
            raise ArchiveError(tr("grimoire.spells.vaultl.archive", "Not a regular file."))
        with open(path, "rb") as f:
            head = f.read(512)
    except OSError as e:
        raise ArchiveError(e.strerror or str(e)) from None
    comp = next((k for m, k in MAGIC if head.startswith(m)), "")
    if comp in (ZIP, SEVEN, RAR):
        return comp, ""
    if comp:
        opener = _opener(comp)
        if opener is None:                                # zstd on an old Python: 7z/bsdtar may still do it
            return (TAR if ".tar" in path.name.lower() or path.name.lower().endswith(".tzst") else STREAM), comp
        try:
            with opener(path, "rb") as f:
                inner = f.read(512)
        except Exception:
            raise ArchiveError(tr("grimoire.spells.vaultl.archive",
                                  "The archive is damaged or not what its name says.")) from None
        return (TAR if inner[257:262] == b"ustar" or _tar_header(inner) else STREAM), comp
    if head[257:262] == b"ustar" or _tar_header(head):
        return TAR, ""
    raise ArchiveError(tr("grimoire.spells.vaultl.archive", "Not an archive VaultL can open."))


def _tar_header(block: bytes) -> bool:
    """An old (v7) tar header has no magic; its checksum still adds up."""
    if len(block) < 512:
        return False
    try:
        stored = int(block[148:156].replace(b"\x00", b" ").strip() or b"-1", 8)
    except ValueError:
        return False
    return stored == sum(block[:148]) + 256 + sum(block[156:512])


# ---------------------------------------------------------------- tools
_tools: dict | None = None


def tools() -> dict:
    """{'7z': path|None, 'bsdtar': path|None, 'rar': bool (7z has the rar codec)}; looked up once."""
    global _tools
    if _tools is None:
        seven = shutil.which("7z") or shutil.which("7zz")
        rar = False
        if seven:
            try:
                out = subprocess.run([seven, "i"], capture_output=True, text=True, timeout=10, env=ENV,
                                     stdin=subprocess.DEVNULL).stdout
                codecs = out.split("Codecs:", 1)[1] if "Codecs:" in out else ""
                rar = bool(re.search(r"\bRar\d?\b", codecs))
            except (OSError, subprocess.SubprocessError):
                pass
        _tools = {"7z": seven, "bsdtar": shutil.which("bsdtar"), "rar": rar}
    return _tools


def missing(k: str) -> Missing:
    t = tools()
    if k == RAR:
        cmd = "sudo apt install 7zip-rar" if t["7z"] else "sudo apt install 7zip 7zip-rar"
        return Missing(tr("grimoire.spells.vaultl.archive", "Opening .rar archives needs 7-Zip's rar codec."), cmd)
    return Missing(tr("grimoire.spells.vaultl.archive", "Opening this kind of archive needs 7-Zip."),
                   "sudo apt install 7zip")


# ---------------------------------------------------------------- listing
@dataclass
class Entry:
    name: str                                          # clean relative posix path, no trailing slash
    is_dir: bool = False
    size: int = 0                                      # -1: unknown
    packed: int = -1
    mtime: float | None = None
    link: bool = False                                 # symbolic link
    special: bool = False                              # device, fifo… (listed, never extracted)
    encrypted: bool = False
    raw: str = ""                                      # the name as the archive stores it


@dataclass
class Listing:
    entries: dict[str, Entry] = field(default_factory=dict)
    unsafe: int = 0                                    # entries skipped for absolute or ".." names
    encrypted: bool = False
    _kids: dict | None = None

    def add(self, e: Entry):
        old = self.entries.get(e.name)
        if old and old.is_dir and not e.is_dir:        # "a" as both: keep the folder
            return
        self.entries[e.name] = e
        parent = PurePosixPath(e.name).parent
        while str(parent) != ".":                      # folders only implied by their files
            if str(parent) in self.entries:
                break
            self.entries[str(parent)] = Entry(str(parent), is_dir=True)
            parent = parent.parent
        self.encrypted = self.encrypted or e.encrypted

    def children(self, folder: str) -> list[Entry]:
        if self._kids is None:                         # one pass, then every folder opens at once
            self._kids = {}
            for n, e in self.entries.items():
                self._kids.setdefault(n.rpartition("/")[0], []).append(e)
        return self._kids.get(folder, [])

    def under(self, names: list[str]) -> list[Entry]:
        """The entries named and everything inside the folders among them."""
        wanted = set(names)
        out = []
        for name, e in self.entries.items():
            parts = name.split("/")
            if any("/".join(parts[:i]) in wanted for i in range(1, len(parts) + 1)):
                out.append(e)
        return out

    def total(self) -> tuple[int, int]:
        files = [e for e in self.entries.values() if not e.is_dir]
        return len(files), sum(max(e.size, 0) for e in files)


# ---------------------------------------------------------------- writing members safely
class Sink:
    """Writes members under root (a fresh staging folder). Counts bytes against what the archive declared (or,
    when it can't say, a ratio of the archive's size) and keeps RESERVE free on the drive. Links come last."""

    def __init__(self, root: Path, progress: Progress, limit: int, private=False):
        self.root = root
        self.top = os.path.realpath(root)
        self.progress = progress
        self.limit = limit                             # bytes it may write in all
        self.written = 0
        self.skipped = 0                               # links leaving the folder, devices, fifos, bad names
        self.private = private                         # preview copies: owner-only, never executable
        self.links: list[tuple[str, str]] = []
        self.hardlinks: list[tuple[str, str]] = []
        self.dirs: list[tuple[str, int, float | None]] = []
        self._checked = 0

    def _parent(self, rel: str) -> Path | None:
        """root/rel's folder, made as real folders; None if something in the way isn't one."""
        cur = self.root
        for part in PurePosixPath(rel).parts[:-1]:
            cur = cur / part
            try:
                st = os.lstat(cur)
                if not stat.S_ISDIR(st.st_mode):
                    return None
            except FileNotFoundError:
                os.mkdir(cur, 0o700 if self.private else 0o755)
        return cur

    def _room(self):
        if self.written - self._checked > 64 * 1024 * 1024:
            self._checked = self.written
            if free_bytes(self.root) < RESERVE:
                raise _no_room(self.written, free_bytes(self.root))

    def file(self, rel: str, src, mode: int = 0o644, mtime: float | None = None, declared: int = -1):
        parent = self._parent(rel)
        if parent is None:
            self.skipped += 1
            return
        target = parent / PurePosixPath(rel).name
        try:
            if os.lstat(target) and not stat.S_ISDIR(os.lstat(target).st_mode):
                os.unlink(target)                      # the same name twice in one archive: the last one wins
            else:
                self.skipped += 1
                return
        except FileNotFoundError:
            pass
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        mine = 0
        with os.fdopen(fd, "wb") as out:
            while True:
                self.progress.check()
                chunk = src.read(CHUNK)
                if not chunk:
                    break
                mine += len(chunk)
                self.written += len(chunk)
                if (declared >= 0 and mine > declared) or self.written > self.limit:
                    raise _bomb()
                out.write(chunk)
                self._room()
                self.progress.report(self.written, label=rel)
        self._finish_file(target, mode, mtime)

    def _finish_file(self, target: Path, mode: int, mtime: float | None):
        mode = 0o600 if self.private else ((mode & 0o777) or 0o644) | 0o600     # no setuid/setgid/sticky
        os.chmod(target, mode, follow_symlinks=False)
        if mtime:
            try:
                os.utime(target, (mtime, mtime), follow_symlinks=False)
            except (OSError, OverflowError, ValueError):
                pass

    def folder(self, rel: str, mode: int = 0o755, mtime: float | None = None):
        if self._parent(rel + "/x") is None:
            self.skipped += 1
            return
        self.dirs.append((rel, mode, mtime))

    def link(self, rel: str, target: str):
        self.links.append((rel, target))

    def hardlink(self, rel: str, target: str):
        self.hardlinks.append((rel, target))

    def finish(self):
        """Hard links become copies of files already written; symbolic links are made only when they point
        inside, then checked again with everything in place; folders get their times and modes last."""
        for rel, target in self.hardlinks:
            src = self.root / target
            try:
                st = os.lstat(src)
            except OSError:
                self.skipped += 1
                continue
            if not stat.S_ISREG(st.st_mode) or not os.path.realpath(src).startswith(self.top + os.sep):
                self.skipped += 1
                continue
            with open(src, "rb") as f:
                self.file(rel, f, st.st_mode, st.st_mtime, declared=st.st_size)
        made = []
        for rel, target in self.links:
            if self.private or not _link_inside(rel, target):
                self.skipped += 1
                continue
            parent = self._parent(rel)
            if parent is None:
                self.skipped += 1
                continue
            try:
                os.symlink(target, parent / PurePosixPath(rel).name)
                made.append(parent / PurePosixPath(rel).name)
            except OSError:
                self.skipped += 1
        for p in made:                                 # links through links: check the real place once all exist
            real = os.path.realpath(p)
            if real != self.top and not real.startswith(self.top + os.sep):
                os.unlink(p)
                self.skipped += 1
        for rel, mode, mtime in sorted(self.dirs, key=lambda d: -d[0].count("/")):
            p = self.root / rel
            try:
                if stat.S_ISDIR(os.lstat(p).st_mode):
                    os.chmod(p, 0o700 if self.private else (mode & 0o777) | 0o700)
                    if mtime:
                        os.utime(p, (mtime, mtime))
            except (OSError, OverflowError, ValueError):
                pass


def _link_inside(rel: str, target: str) -> bool:
    if not target or target.startswith("/") or "\x00" in target:
        return False
    joined = os.path.normpath(os.path.join(os.path.dirname(rel), target))
    return not (joined == ".." or joined.startswith("../") or joined.startswith("/"))


def scrub(root: Path, private=False) -> int:
    """After an outside tool wrote into root: drop links that leave root (or every link, for previews),
    devices, fifos and sockets; hard-linked files become private copies; no setuid bits. Returns how many
    entries were dropped."""
    top = os.path.realpath(root)
    dropped = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            p = os.path.join(dirpath, name)
            st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode):
                target = os.readlink(p)
                real = os.path.realpath(p)
                if private or target.startswith("/") or not (real == top or real.startswith(top + os.sep)):
                    os.unlink(p)
                    dropped += 1
            elif stat.S_ISREG(st.st_mode):
                if st.st_nlink > 1:                    # never keep a link to a file outside
                    tmp = p + ".grimoire-copy"
                    shutil.copyfile(p, tmp, follow_symlinks=False)
                    os.replace(tmp, p)
                os.chmod(p, 0o600 if private else (st.st_mode & 0o777) | 0o600)
            elif stat.S_ISDIR(st.st_mode):
                os.chmod(p, 0o700 if private else (st.st_mode & 0o777) | 0o700)
            else:
                os.unlink(p)
                dropped += 1
        dirnames[:] = [d for d in dirnames if os.path.isdir(os.path.join(dirpath, d))
                       and not os.path.islink(os.path.join(dirpath, d))]
    return dropped


def _confine(item: Path, around: Path) -> int:
    """Before item moves out of the staging folder on its own: drop the links in it that lead out of it (into
    the staging or the folder it lands in), and item itself when it is a link leading out of around. Our own
    fresh staging files only. Returns how many were dropped."""
    def leaves(p: str, top: str, strict: bool) -> bool:
        target = os.readlink(p)
        if target.startswith("/"):
            return True
        for where in (os.path.normpath(os.path.join(os.path.dirname(p), target)), os.path.realpath(p)):
            if not (where.startswith(top + os.sep) or (where == top and not strict)):
                return True
        return False

    item, top_around = str(item), os.path.realpath(around)
    if os.path.islink(item):
        if leaves(item, top_around, True):
            os.unlink(item)
            return 1
        return 0
    if not os.path.isdir(item):
        return 0
    top, dropped = os.path.realpath(item), 0
    for dirpath, dirnames, filenames in os.walk(item):
        for name in dirnames + filenames:
            p = os.path.join(dirpath, name)
            if os.path.islink(p) and leaves(p, top, False):
                os.unlink(p)
                dropped += 1
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
    return dropped


def free_bytes(path: Path) -> int:
    try:
        st = os.statvfs(path)
        return st.f_bavail * st.f_frsize
    except OSError:
        return 0


# ---------------------------------------------------------------- readers
class Reader:
    """One archive. `listing()` reads the table of contents; `extract(names, root, progress, limit)` writes the
    named entries (None = all) into the fresh folder root."""
    needs_tool = ""

    def __init__(self, path: Path, comp: str = "", password: str | None = None):
        self.path, self.comp, self.password = path, comp, password
        self._listing: Listing | None = None

    def listing(self, progress: Progress | None = None) -> Listing:
        if self._listing is None:
            self._listing = self._list(progress or Progress())
        return self._listing

    def extract(self, names, root: Path, progress: Progress, private=False) -> int:
        raise NotImplementedError

    def limit(self, entries: list[Entry]) -> int:
        """How many bytes extracting entries may write: what they declare, or RATIO x the archive if unknown."""
        if any(e.size < 0 for e in entries if not e.is_dir):
            return max(self.path.stat().st_size * RATIO, MIN_LIMIT)
        return sum(e.size for e in entries if not e.is_dir) + CHUNK


def _zip_time(info) -> float | None:
    try:
        return datetime(*info.date_time).timestamp()
    except (ValueError, OverflowError):
        return None


class ZipReader(Reader):
    def _list(self, progress) -> Listing:
        out = Listing()
        try:
            with zipfile.ZipFile(self.path) as z:
                infos = z.infolist()
        except (zipfile.BadZipFile, OSError, ValueError, EOFError) as e:
            raise _damaged(e) from None
        if len(infos) > MAX_ENTRIES:
            raise ArchiveError(tr("grimoire.spells.vaultl.archive", "The archive has too many entries."))
        for info in infos:
            name = clean_name(info.filename)
            if name is None:
                out.unsafe += 1
                continue
            mode = stat.S_IFMT(info.external_attr >> 16)
            special = bool(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode) or stat.S_ISLNK(mode))
            out.add(Entry(name, info.is_dir(), info.file_size, info.compress_size, _zip_time(info),
                          stat.S_ISLNK(mode), special, bool(info.flag_bits & 1), info.filename))
        return out

    def extract(self, names, root, progress, private=False) -> int:
        lst = self.listing()
        entries = lst.under(names) if names is not None else list(lst.entries.values())
        wanted = {e.raw for e in entries if e.raw}
        if any(e.encrypted for e in entries) and not self.password:
            raise NeedPassword()
        sink = Sink(root, progress, self.limit(entries), private)
        pwd = self.password.encode() if self.password else None
        progress.report(0, sum(e.size for e in entries if not e.is_dir), force=True)
        try:
            with zipfile.ZipFile(self.path) as z:
                for info in z.infolist():
                    if info.filename not in wanted:
                        continue
                    progress.check()
                    name = clean_name(info.filename)
                    mode = info.external_attr >> 16
                    if info.is_dir():
                        sink.folder(name, mode or 0o755, _zip_time(info))
                    elif stat.S_ISLNK(mode):
                        if info.file_size <= 4096:
                            sink.link(name, z.read(info, pwd).decode("utf-8", "replace"))
                        else:
                            sink.skipped += 1
                    elif stat.S_IFMT(mode) and not stat.S_ISREG(mode):
                        sink.skipped += 1
                    else:
                        with z.open(info, pwd=pwd) as src:
                            sink.file(name, src, mode or 0o644, _zip_time(info), info.file_size)
        except NotImplementedError:                    # AES or an unusual method: 7z reads those
            raise UseSeven() from None
        except RuntimeError as e:
            if isinstance(e, ArchiveError):
                raise
            if "password" in str(e).lower():
                raise NeedPassword(wrong=bool(pwd)) from None
            raise ArchiveError(str(e)) from None
        except (zipfile.BadZipFile, EOFError, zlib.error) as e:
            raise _damaged(e) from None
        sink.finish()
        return sink.skipped


class TarReader(Reader):
    """Python's tarfile, read as a stream (one pass, members in order). bsdtar feeds the same code through a
    pipe for formats Python can't read (7z, rar)."""

    def _open(self):
        """(tarfile, close function or None). Per call: a preview and an extraction can read at once."""
        if self.comp == "zst" and zstd is None:
            raise missing(SEVEN)
        return tarfile.open(self.path, "r|" + ({"gz": "gz", "xz": "xz", "bz2": "bz2", "zst": "zst"}
                                                .get(self.comp, ""))), None

    def _members(self, progress):
        t = close = None
        try:
            t, close = self._open()
            count = 0
            for m in t:
                progress.check()
                count += 1
                if count > MAX_ENTRIES:
                    raise ArchiveError(tr("grimoire.spells.vaultl.archive", "The archive has too many entries."))
                yield t, m
        except (tarfile.TarError, EOFError, OSError, lzma.LZMAError, ValueError) as e:
            raise _damaged(e) from None
        finally:
            if t is not None:
                t.close()
            if close is not None:
                close()

    def _list(self, progress) -> Listing:
        out = Listing()
        for _, m in self._members(progress):
            name = clean_name(m.name)
            if name is None:
                out.unsafe += 1
                continue
            size = m.size if m.isreg() else 0
            if m.islnk():                              # written as a copy of an earlier member: counts its bytes
                target = out.entries.get(clean_name(m.linkname) or "")
                size = target.size if target and not target.is_dir else 0
            out.add(Entry(name, m.isdir(), size, -1, m.mtime or None, m.issym(),
                          not (m.isreg() or m.isdir() or m.issym() or m.islnk()), False, m.name))
        return out

    def extract(self, names, root, progress, private=False) -> int:
        lst = self.listing()
        entries = lst.under(names) if names is not None else list(lst.entries.values())
        wanted = {e.raw for e in entries if e.raw}
        sink = Sink(root, progress, self.limit(entries), private)
        progress.report(0, sum(max(e.size, 0) for e in entries if not e.is_dir), force=True)
        for t, m in self._members(progress):
            if m.name not in wanted:
                continue
            name = clean_name(m.name)
            if m.isdir():
                sink.folder(name, m.mode, m.mtime)
            elif m.isreg():
                src = t.extractfile(m)
                sink.file(name, src, m.mode, m.mtime, m.size)
            elif m.issym():
                sink.link(name, m.linkname)
            elif m.islnk():
                target = clean_name(m.linkname)
                if target is None:
                    sink.skipped += 1
                else:
                    sink.hardlink(name, target)
            else:
                sink.skipped += 1
        sink.finish()
        return sink.skipped


class BsdtarReader(TarReader):
    """Any format libarchive reads, converted to a pax tar stream by `bsdtar -cf - @archive`."""
    needs_tool = "bsdtar"

    def _open(self):
        proc = subprocess.Popen([tools()["bsdtar"], "-cf", "-", "--format", "pax", "@" + str(self.path)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=ENV)
        try:
            return tarfile.open(fileobj=proc.stdout, mode="r|"), lambda: self._close(proc)
        except BaseException:
            self._close(proc)                          # bsdtar's own message says more than "empty file"
            raise

    @staticmethod
    def _close(proc):
        if proc.poll() is None:
            proc.kill()
        err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        proc.wait()
        if proc.returncode not in (0, -9) and err:
            if "passphrase" in err.lower() or "encrypt" in err.lower():
                raise NeedPassword()
            raise ArchiveError(err.strip().splitlines()[-1][:300])


class StreamReader(Reader):
    """A single compressed file (notes.txt.gz): one entry, its size unknown until it's out."""

    def _list(self, progress) -> Listing:
        out = Listing()
        name = clean_name(stem(self.path) or "file") or "file"
        out.add(Entry(name, size=-1, packed=self.path.stat().st_size, mtime=self.path.stat().st_mtime))
        return out

    def extract(self, names, root, progress, private=False) -> int:
        e = next(iter(self.listing().entries.values()))
        opener = _opener(self.comp)
        if opener is None:
            raise missing(SEVEN)
        sink = Sink(root, progress, self.limit([e]), private)
        progress.report(0, 0, force=True)
        try:
            with opener(self.path, "rb") as src:
                sink.file(e.name, src, 0o644, e.mtime)
        except (OSError, EOFError, lzma.LZMAError, ValueError) as err:
            if isinstance(err, OSError) and err.errno:     # the disk, not the archive
                raise ArchiveError(err.strerror or str(err)) from None
            raise _damaged(err) from None
        sink.finish()
        return sink.skipped


def _seven_time(s: str) -> float | None:
    try:
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").timestamp()
    except ValueError:
        return None


class SevenReader(Reader):
    """7z, rar and anything Python can't read, through the `7z` tool. The password goes to its stdin."""
    needs_tool = "7z"

    def _run(self, args, progress: Progress | None = None, watch: Path | None = None, limit=0, cwd=None):
        """Run 7z; returns (returncode, output). Cancel kills it; while extracting, watch's drive must keep
        RESERVE free and the folder may not outgrow limit."""
        cmd = [tools()["7z"]] + args
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=ENV, cwd=cwd)
        out = bytearray()

        def feed():
            try:
                if self.password:
                    proc.stdin.write(self.password.encode() + b"\n")
                proc.stdin.close()                     # no password: 7z gives up instead of waiting
            except OSError:
                pass

        def read():
            while chunk := proc.stdout.read1(4096):
                out.extend(chunk)
                if progress is not None:
                    pct = re.findall(rb"(\d+)%", bytes(chunk))
                    if pct and progress.total:
                        progress.report(progress.total * min(int(pct[-1]), 100) // 100)

        threading.Thread(target=feed, daemon=True).start()
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        next_check = 0.0
        try:
            while proc.poll() is None:
                if progress is not None and progress.stop.is_set():
                    raise Cancelled()
                if watch is not None and time.monotonic() > next_check:
                    next_check = time.monotonic() + 0.5
                    if free_bytes(watch) < RESERVE:
                        raise _no_room(limit, free_bytes(watch))
                    if limit and _du(watch, limit) > limit:
                        raise _bomb()
                time.sleep(0.05)
            if watch is not None and limit and _du(watch, limit) > limit:
                raise _bomb()                          # a fast 7z can finish between two checks
        except BaseException:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            raise
        reader.join(5)
        return proc.returncode, out.decode("utf-8", "replace")

    def _check_password(self, rc: int, text: str):
        low = text.lower()
        if rc not in (0, 1) and ("wrong password" in low or "enter password" in low
                                 or "can not open encrypted" in low):
            raise NeedPassword(wrong=bool(self.password))

    def _list(self, progress) -> Listing:
        rc, text = self._run(["l", "-slt", "-ba", "-sccUTF-8", "--", str(self.path)], progress)
        self._check_password(rc, text)
        if rc not in (0, 1):
            raise ArchiveError(_seven_error(text))
        out = Listing()
        for block in re.split(r"\n\s*\n", text):
            f = {}
            for line in block.splitlines():
                k, sep, v = line.partition(" = ")
                if sep:
                    f[k.strip()] = v
            if "Path" not in f:
                continue
            name = clean_name(f["Path"])
            if name is None:
                out.unsafe += 1
                continue
            if len(out.entries) > MAX_ENTRIES:
                raise ArchiveError(tr("grimoire.spells.vaultl.archive", "The archive has too many entries."))
            attrs = f.get("Attributes", "")
            unix = attrs.split(" ")[-1] if " " in attrs else ""
            is_dir = f.get("Folder") == "+" or attrs.startswith("D") or unix.startswith("d")
            out.add(Entry(name, is_dir, _int(f.get("Size")), _int(f.get("Packed Size"), -1),
                          _seven_time(f.get("Modified", "")), unix.startswith("l"),
                          bool(unix) and unix[0] in "cbps", f.get("Encrypted") == "+", f["Path"]))
        return out

    def extract(self, names, root, progress, private=False) -> int:
        lst = self.listing()
        entries = lst.under(names) if names is not None else list(lst.entries.values())
        if lst.encrypted and not self.password and any(e.encrypted for e in entries):
            raise NeedPassword()
        total = sum(max(e.size, 0) for e in entries if not e.is_dir)
        progress.report(0, total, force=True)
        args = ["x", "-y", "-bso0", "-bse1", "-bsp1", "-spd", "-sccUTF-8", "-o" + str(root), "--", str(self.path)]
        if names is not None:                          # folders bring what's inside them
            args += sorted({(lst.entries[n].raw or n) for n in names if n in lst.entries})
        rc, text = self._run(args, progress, watch=root, limit=self.limit(entries))
        self._check_password(rc, text)
        errors = [l for l in text.splitlines() if l.startswith("ERROR")]
        if rc not in (0, 1) and not all("Dangerous link" in l for l in errors):
            raise ArchiveError(_seven_error(text))
        progress.report(total, force=True)
        return scrub(root, private) + sum("Dangerous link" in l for l in errors)


def _int(s, default=0) -> int:
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def _du(root: Path, stop: int) -> int:
    total = 0
    for dirpath, _, files in os.walk(root):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
            if total > stop:
                return total
    return total


def _seven_error(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for l in lines:
        if "Unsupported Method" in l:
            return tr("grimoire.spells.vaultl.archive",
                      "7-Zip can't unpack this (a codec is missing, e.g. 7zip-rar for rar).")
    err = [l for l in lines if l.startswith(("ERROR", "E_", "Can not", "Cannot")) or "rror" in l]
    return (err[-1] if err else (lines[-1] if lines else "7z failed"))[:300]


def reader(path: Path, password: str | None = None) -> Reader:
    """The reader for path. Raises ArchiveError (not an archive) or Missing (needs a tool)."""
    k, comp = kind(path)
    t = tools()
    if k == ZIP:
        return ZipReader(path, password=password)
    if k == TAR:
        if comp == "zst" and zstd is None:             # Python before 3.14
            if t["bsdtar"]:
                return BsdtarReader(path)
            raise Missing(tr("grimoire.spells.vaultl.archive", "Opening .tar.zst needs bsdtar."),
                          "sudo apt install libarchive-tools")
        return TarReader(path, comp)
    if k == STREAM:
        return StreamReader(path, comp)
    if k == RAR and not t["rar"]:
        if t["bsdtar"]:
            return BsdtarReader(path)
        raise missing(RAR)
    if t["7z"]:
        return SevenReader(path, password=password)
    if t["bsdtar"]:
        return BsdtarReader(path)
    raise missing(k)


def needs_7z_for_password(r: Reader) -> bool:
    """Encrypted zips: Python reads the old ZipCrypto only; 7z reads AES too, so it does them when it's here."""
    return isinstance(r, ZipReader) and bool(tools()["7z"])


# ---------------------------------------------------------------- extract into place
@dataclass
class Result:
    placed: list[Path] = field(default_factory=list)
    skipped: int = 0
    unsafe: int = 0


def _staging(dest: Path) -> Path:
    p = dest / (STAGING + secrets.token_hex(4))
    os.mkdir(p, 0o700)
    return p


def remove_staging(p: Path):
    """Our own half-written staging folder (never user files): it goes for good."""
    if p.name.startswith(STAGING) or p.parent.name == "vaultl-archive":
        shutil.rmtree(p, ignore_errors=True)


def extract(r: Reader, dest: Path, names: list[str] | None = None, base: str = "", progress: Progress | None = None,
            smart=True, private=False) -> Result:
    """Extract names (None = everything) into dest. With names, what's inside `base` (the folder being browsed)
    lands directly in dest; everything at once lands as one item: the archive's single top folder or file, else
    a new folder named after the archive. Never over an existing name."""
    progress = progress or Progress()
    if r.password and isinstance(r, ZipReader) and needs_7z_for_password(r):
        r = SevenReader(r.path, password=r.password)
    try:
        return _extract(r, dest, names, base, progress, smart, private)
    except UseSeven:
        if not tools()["7z"]:
            raise missing(SEVEN) from None
        return _extract(SevenReader(r.path, password=r.password), dest, names, base, progress, smart, private)


def _extract(r, dest, names, base, progress, smart, private) -> Result:
    lst = r.listing(progress)
    entries = lst.under(names) if names is not None else list(lst.entries.values())
    need = sum(max(e.size, 0) for e in entries if not e.is_dir)
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ArchiveError(e.strerror or str(e)) from None
    free = free_bytes(dest)
    if need + RESERVE > free:
        raise _no_room(need, free)
    try:
        stage = _staging(dest)
    except OSError as e:
        raise ArchiveError(tr("grimoire.spells.vaultl.archive", "Can't write in {folder}: {error}").format(
            folder=dest, error=e.strerror or e)) from None
    result = Result(unsafe=lst.unsafe)
    try:
        result.skipped = r.extract(names, stage, progress, private)
        progress.check()
        if names is not None:
            src = stage / base if base else stage
            tops = sorted(src.iterdir()) if src.is_dir() else []
            result.skipped += sum(_confine(item, src) for item in tops)
            tops = [t for t in tops if t.is_symlink() or t.exists()]
            for item in tops:
                target = free_name(dest / item.name)
                os.rename(item, target)
                result.placed.append(target)
        else:
            tops = list(stage.iterdir())
            single = smart and len(tops) == 1
            result.skipped += _confine(tops[0] if single else stage, stage)
            tops = [t for t in tops if t.is_symlink() or t.exists()]
            if single and tops:
                target = free_name(dest / tops[0].name)
                os.rename(tops[0], target)
            else:
                target = free_name(dest / (stem(r.path) or "archive"))
                os.chmod(stage, 0o755)
                os.rename(stage, target)
            result.placed.append(target)
    except OSError as e:
        raise ArchiveError(e.strerror or str(e)) from None
    finally:
        if stage.exists():
            remove_staging(stage)
    return result


# ---------------------------------------------------------------- compress
ZIPF, TARZST, SEVENF, TARGZ = "zip", "tar.zst", "7z", "tar.gz"
FORMATS = {ZIPF: ".zip", TARZST: ".tar.zst", TARGZ: ".tar.gz", SEVENF: ".7z"}
LEVELS = {ZIPF: (0, 1, 6, 9), TARZST: (1, 3, 9, 19), TARGZ: (0, 1, 6, 9), SEVENF: (0, 1, 5, 9)}


def formats() -> list[str]:
    out = [ZIPF]
    if zstd is not None:
        out.append(TARZST)
    out.append(TARGZ)
    if tools()["7z"]:
        out.append(SEVENF)
    return out


def can_encrypt(fmt: str) -> bool:
    """zip and 7z can carry a password, both through 7z (AES-256): Python can't write encrypted zips."""
    return fmt in (ZIPF, SEVENF) and bool(tools()["7z"])


def password_problem(fmt: str, password: str) -> str:
    """Why this password can't protect an archive of this format ("" when it can)."""
    if not password:
        return ""
    if not can_encrypt(fmt):
        return tr("grimoire.spells.vaultl.archive", "This format can't carry a password.")
    if "\n" in password or "\r" in password:
        return tr("grimoire.spells.vaultl.archive", "Passwords can't contain line breaks.")
    if fmt == ZIPF and not password.isascii():           # 7z stops with E_INVALIDARG
        return tr("grimoire.spells.vaultl.archive",
                  "zip passwords can only use English letters, digits and symbols. Pick 7z to use this one.")
    return ""


def default_name(sources: list[Path], fmt: str) -> str:
    if len(sources) == 1:
        s = sources[0]
        base = s.name if s.is_dir() else (stem(s) if is_archive(s) else s.stem) or s.name
    else:
        base = sources[0].parent.name or "Archive"
    return base + FORMATS[fmt]


def _walk(sources: list[Path]):
    """(path, arcname, lstat) for every item, folders before what's in them; links are not followed."""
    for s in sources:
        try:
            st = os.lstat(s)
        except OSError:
            continue
        yield s, s.name, st
        if stat.S_ISDIR(st.st_mode):
            for dirpath, dirnames, filenames in os.walk(s):
                dirnames.sort()
                for name in dirnames + sorted(filenames):
                    p = Path(dirpath) / name
                    try:
                        yield p, str(p.relative_to(s.parent)), os.lstat(p)
                    except OSError:
                        continue


class _Counted:
    def __init__(self, f, progress: Progress, start: int):
        self.f, self.progress, self.n = f, progress, start

    def read(self, size=-1):
        self.progress.check()
        data = self.f.read(CHUNK if size < 0 else min(size, CHUNK))
        self.n += len(data)
        self.progress.report(self.n)
        return data


def compress(sources: list[Path], out: Path, fmt: str, level: int = 2, password: str = "",
             progress: Progress | None = None) -> Path:
    """Pack sources (all in one folder) into out, or a free name next to it. level indexes LEVELS (0 store …
    3 max). Writes to a hidden file first and only takes the final name if it's still free."""
    progress = progress or Progress()
    problem = password_problem(fmt, password)
    if problem:
        raise ArchiveError(problem)
    items = list(_walk(sources))
    total = sum(st.st_size for _, _, st in items if stat.S_ISREG(st.st_mode))
    progress.report(0, total, sources[0].name if sources else "", force=True)
    out = free_name(out)
    tmp = out.parent / f".{secrets.token_hex(4)}-{out.name}"
    try:
        if fmt == SEVENF or (fmt == ZIPF and password):
            _compress_7z(sources, tmp, fmt, LEVELS[fmt][level], password, progress)
        elif fmt == ZIPF:
            _compress_zip(items, tmp, LEVELS[fmt][level], progress)
        else:
            _compress_tar(items, tmp, fmt, LEVELS[fmt][level], progress)
        progress.check()
        progress.report(total, force=True)
        final = free_name(out)
        try:
            os.link(tmp, final)                        # fails rather than replace anything
            os.unlink(tmp)
        except OSError:                                # drives without hard links: rename if still free
            if final.exists() or final.is_symlink():
                final = free_name(final)
            os.rename(tmp, final)
        return final
    except OSError as e:
        raise ArchiveError(e.strerror or str(e)) from None
    finally:
        if tmp.exists():
            tmp.unlink()                               # our own half-written file


def _compress_zip(items, tmp: Path, level: int, progress: Progress):
    method = zipfile.ZIP_STORED if level == 0 else zipfile.ZIP_DEFLATED
    done = 0
    with zipfile.ZipFile(tmp, "w", method, compresslevel=None if level == 0 else level) as z:
        for p, arc, st in items:
            progress.check()
            if stat.S_ISDIR(st.st_mode):
                z.write(p, arc)
            elif stat.S_ISLNK(st.st_mode):
                info = zipfile.ZipInfo(arc, time.localtime(st.st_mtime)[:6])
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                info.create_system = 3
                z.writestr(info, os.readlink(p))
            elif stat.S_ISREG(st.st_mode):
                info = zipfile.ZipInfo.from_file(p, arc)
                info.compress_type = method
                if level:
                    info.compress_level = level
                progress.report(label=arc)
                with open(p, "rb") as src, z.open(info, "w") as dst:
                    reader = _Counted(src, progress, done)
                    while chunk := reader.read():
                        dst.write(chunk)
                done += st.st_size


def _compress_tar(items, tmp: Path, fmt: str, level: int, progress: Progress):
    mode, kw = ("w:zst", {"level": level}) if fmt == TARZST else ("w:gz", {"compresslevel": level})
    done = 0
    with tarfile.open(tmp, mode, **kw) as t:
        for p, arc, st in items:
            progress.check()
            if not (stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode) or stat.S_ISREG(st.st_mode)):
                continue
            info = t.gettarinfo(str(p), arc)
            info.uid = info.gid = 0                    # no user or group names in an archive you share
            info.uname = info.gname = ""
            if info.isreg():
                progress.report(label=arc)
                with open(p, "rb") as src:
                    t.addfile(info, _Counted(src, progress, done))
                done += st.st_size
            else:
                t.addfile(info)


def _compress_7z(sources: list[Path], tmp: Path, fmt: str, level: int, password: str, progress: Progress):
    if not tools()["7z"]:
        raise missing(SEVEN)
    args = ["a", "-t7z" if fmt == SEVENF else "-tzip", f"-mx={level}", "-snl", "-spd", "-bso0", "-bse1",
            "-bsp1", "-sccUTF-8"]
    if password:
        args += ["-p", "-mhe=on"] if fmt == SEVENF else ["-p", "-mem=AES256"]
    parent = sources[0].parent
    args += ["--", os.path.abspath(tmp)] + [s.name for s in sources]
    r = SevenReader(tmp, password=password or None)
    rc, text = r._run(args, progress, cwd=parent)      # names relative to the folder they're in
    if rc not in (0, 1):
        raise ArchiveError(_seven_error(text))
