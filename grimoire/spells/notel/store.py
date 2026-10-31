# SPDX-License-Identifier: GPL-3.0-or-later
"""NoteL's files: settings, the notes folder ("vault"), reading and saving text safely, and Markdown parsing. No Qt.

A vault is any folder of plain .md files (an Obsidian vault works as is: its .obsidian/ folder is skipped). Saving is
atomic (a temp file next to the note, fsync, rename) and checked: when the file changed on disk since it was read,
save() raises Conflict instead of writing, so nothing is ever overwritten silently. Removing goes to the Trash.
"""
import datetime
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from grimoire.fsutil import free_name, trash
from grimoire.i18n import tr
from grimoire.paths import CACHE, CONFIG

NOTE_EXT = (".md", ".markdown", ".txt")
MD_EXT = (".md", ".markdown")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
MAX_OPEN = 32 << 20                # bigger "text" files are refused (an editor can't help with a 1 GB log)
DEFAULTS = {"vault": "", "pinned": [], "mono": False, "line_numbers": True, "wrap": True, "view": "split",
            "autosave_files": False, "daily_folder": "Daily", "font_size": 14, "tabs": [], "current": "",
            "sidebar": "notes"}
VIEWS = ("edit", "split", "read")
BAD_NAME = re.compile(r'[/\\\x00-\x1f]')


class NotText(ValueError):
    """The file isn't something NoteL can edit (binary or too big); the message is worded for the UI."""


class Conflict(Exception):
    """The file changed (or vanished) on disk since NoteL read it. kind: "changed" | "deleted"."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


# ---------------------------------------------------------------- settings
def settings_file() -> Path:
    return CONFIG / "notel.json"


def load() -> dict:
    try:
        d = json.loads(settings_file().read_text())
    except (OSError, ValueError):
        d = {}
    out = dict(DEFAULTS)
    if isinstance(d, dict):
        for k, v in d.items():
            if k in DEFAULTS and type(v) is type(DEFAULTS[k]):
                out[k] = v
    out["pinned"] = [p for p in out["pinned"] if isinstance(p, str)][:200]
    out["tabs"] = [p for p in out["tabs"] if isinstance(p, str)][:50]
    if out["view"] not in VIEWS:
        out["view"] = DEFAULTS["view"]
    out["font_size"] = min(32, max(9, out["font_size"]))
    return out


def save_settings(d: dict):
    f = settings_file()
    data = json.dumps({k: d[k] for k in DEFAULTS if k in d}, indent=1).encode()
    write_atomic(f, data)


def update(**changes) -> dict:
    d = load() | changes
    save_settings(d)
    return d


def documents() -> Path:
    """XDG Documents folder (user-dirs.dirs), read late so a sandbox HOME works."""
    home = Path.home()
    conf = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "user-dirs.dirs"
    try:
        m = re.search(r'^XDG_DOCUMENTS_DIR="([^"]+)"', conf.read_text(), re.M)
        if m:
            return Path(m.group(1).replace("$HOME", str(home)))
    except OSError:
        pass
    return home / "Documents"


def default_vault() -> Path:
    return documents() / "Notes"


def vault(settings: dict | None = None) -> Path:
    chosen = (settings or load())["vault"]
    return Path(chosen).expanduser() if chosen else default_vault()


def ensure_vault(settings: dict | None = None) -> Path | None:
    """The vault folder, made when it's the default one; None when a chosen folder is missing (an unplugged drive
    stays missing instead of being recreated empty)."""
    v = vault(settings)
    if v.is_dir():
        return v
    if v == default_vault():
        try:
            v.mkdir(parents=True, exist_ok=True)
            return v
        except OSError:
            return None
    return None


def in_vault(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except OSError:
        return False


def is_note(path: Path) -> bool:
    return path.suffix.lower() in NOTE_EXT


def is_markdown(path: Path) -> bool:
    return path.suffix.lower() in MD_EXT


# ---------------------------------------------------------------- reading and writing
@dataclass
class Loaded:
    text: str                  # with "\n" line ends
    encoding: str              # "utf-8", "utf-8-sig" or "latin-1", written back the same way
    newline: str               # "\n" or "\r\n"
    digest: str                # sha1 of the bytes on disk
    sig: tuple                 # (mtime_ns, size, inode) when read
    mode: int


def digest(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _sig(st: os.stat_result) -> tuple:
    return st.st_mtime_ns, st.st_size, st.st_ino


def decode(data: bytes) -> tuple[str, str, str]:
    """(text, encoding, newline). Refuses binary files."""
    if b"\x00" in data[:65536]:
        raise NotText(tr("grimoire.spells.notel.store", "This looks like a binary file, not text."))
    if data.startswith(b"\xef\xbb\xbf"):
        text, enc = data.decode("utf-8-sig", errors="replace"), "utf-8-sig"
    else:
        try:
            text, enc = data.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            text, enc = data.decode("latin-1"), "latin-1"
    newline = "\r\n" if "\r\n" in text[:65536] else "\n"
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text, enc, newline


def encode(text: str, encoding: str, newline: str) -> tuple[bytes, str]:
    """(bytes, the encoding used): a latin-1 file that got characters latin-1 can't hold is written as UTF-8."""
    if newline != "\n":
        text = text.replace("\n", newline)
    try:
        return text.encode(encoding), encoding
    except UnicodeEncodeError:
        return text.encode("utf-8"), "utf-8"


def read(path: Path) -> Loaded:
    """Read a text file for editing. Raises OSError or NotText."""
    real = Path(os.path.realpath(path))
    fd = os.open(real, os.O_RDONLY | os.O_NONBLOCK)      # a FIFO named note.md would block the worker forever
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode):
            raise NotText(tr("grimoire.spells.notel.store", "Only files can be opened."))
        if st.st_size > MAX_OPEN:
            raise NotText(tr("grimoire.spells.notel.store", "This file is too big to edit here."))
        data = f.read(MAX_OPEN + 1)
    text, enc, nl = decode(data)
    return Loaded(text, enc, nl, digest(data), _sig(st), st.st_mode & 0o7777)


def write_atomic(path: Path, data: bytes, mode: int | None = None):
    """Write data to path through a temp file in the same folder and a rename, so a crash never leaves a half file.
    A symlink keeps pointing where it did: its target is replaced."""
    real = Path(os.path.realpath(path))
    real.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        try:
            mode = os.stat(real).st_mode & 0o7777
        except OSError:
            mode = 0o644
    tmp = real.with_name(f".{real.name}.notel-{os.getpid()}-{os.urandom(3).hex()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fchmod(f.fileno(), mode)
            os.fsync(f.fileno())
        os.replace(tmp, real)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    try:
        d = os.open(real.parent, os.O_RDONLY)
        try:
            os.fsync(d)
        finally:
            os.close(d)
    except OSError:
        pass


def save(path: Path, text: str, loaded: Loaded | None, force: bool = False) -> Loaded:
    """Save text over path, unless the file changed on disk since `loaded` was read (raises Conflict) or force.
    loaded=None means a new file: an existing one is never replaced then. Returns the new Loaded state."""
    enc, nl = (loaded.encoding, loaded.newline) if loaded else ("utf-8", "\n")
    data, enc = encode(text, enc, nl)
    real = Path(os.path.realpath(path))
    try:
        st = os.stat(real)
    except FileNotFoundError:
        st = None
    if not force:
        if loaded is None and st is not None:
            raise Conflict("changed")
        if loaded is not None and st is None:
            raise Conflict("deleted")
        if loaded is not None and _sig(st) != loaded.sig:
            with open(real, "rb") as f:
                now = f.read(MAX_OPEN + 1)
            if digest(now) != loaded.digest:
                raise Conflict("changed")
    write_atomic(real, data, loaded.mode if loaded else None)
    st = os.stat(real)
    return Loaded(text, enc, nl, digest(data), _sig(st), st.st_mode & 0o7777)


def disk_state(path: Path) -> tuple[str, str] | None:
    """(digest, text) of the file as it is on disk now, or None when it's gone or unreadable."""
    try:
        fd = os.open(os.path.realpath(path), os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                return None
            data = f.read(MAX_OPEN + 1)
        return digest(data), decode(data)[0]
    except (OSError, NotText):
        return None


# ---------------------------------------------------------------- notes in the vault
def clean_name(name: str) -> str:
    """A file name typed by the user, checked: no folders, no hidden or empty names. Raises ValueError (UI text)."""
    name = name.strip()
    if not name or name in (".", "..") or name.startswith(".") or BAD_NAME.search(name) or len(name) > 200:
        raise ValueError(tr("grimoire.spells.notel.store", "Use a name without slashes that doesn't start with a dot."))
    return name


def note_name(name: str) -> str:
    """name with .md added unless it already ends in a note extension."""
    name = clean_name(name)
    return name if name.lower().endswith(NOTE_EXT) else name + ".md"


def create(path: Path, text: str = "") -> Path:
    """Make a new file at path, or at "name (2).md" when taken. Never replaces anything."""
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        target = free_name(path)
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            continue                                    # raced: another name
        with os.fdopen(fd, "wb") as f:
            f.write(text.encode())
        return target


def new_folder(parent: Path, name: str) -> Path:
    target = free_name(parent / clean_name(name))
    target.mkdir(parents=True)
    return target


def rename(path: Path, new_name: str) -> Path:
    """Rename a note or folder in place. Refuses (ValueError) a name that's already taken instead of replacing."""
    is_dir = path.is_dir()
    target = path.with_name(clean_name(new_name) if is_dir else note_name(new_name) if is_note(path)
                            else clean_name(new_name))
    if target == path:
        return path
    if target.exists() or target.is_symlink():
        if target.name.lower() != path.name.lower() or not os.path.samefile(target, path):
            raise ValueError(tr("grimoire.spells.notel.store", "Something called {name} is already there.")
                             .format(name=target.name))
    os.rename(path, target)
    return target


def remove(path: Path):
    """To the Trash, never deleted."""
    trash(path)


def daily_path(settings: dict, root: Path, day: datetime.date | None = None) -> Path:
    day = day or datetime.date.today()
    folder = settings.get("daily_folder", "").strip().strip("/")
    base = root / folder if folder and ".." not in Path(folder).parts else root
    return base / f"{day.isoformat()}.md"


def daily(settings: dict, root: Path) -> Path:
    """Today's note, made with a date heading when it doesn't exist yet."""
    p = daily_path(settings, root)
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return p
    with os.fdopen(fd, "wb") as f:
        f.write(f"# {p.stem}\n\n".encode())
    return p


# ---------------------------------------------------------------- Markdown bits
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"(`+)(?:.+?)\1")
TAG = re.compile(r"(?<![^\s(\[,;])#([\w/-]*[^\W\d][\w/-]*)")
WIKI = re.compile(r"(!?)\[\[([^\[\]|#^\n]*)(#[^\[\]|\n]*)?(?:\|([^\[\]\n]*))?\]\]")
MDLINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+\.(?:md|markdown))\)", re.I)
WORD = re.compile(r"\w+(?:['’-]\w+)*")


def split_frontmatter(text: str) -> tuple[str, str]:
    """(YAML front matter without its --- lines, the rest)."""
    if text.startswith("---\n"):
        end = text.find("\n---", 3)
        if end != -1 and text[end + 4:end + 5] in ("\n", ""):
            return text[4:end], text[end + 5:]
    return "", text


def prose(text: str) -> str:
    """text without front matter, fenced code blocks and inline code: where tags and links count."""
    _, body = split_frontmatter(text)
    out, fence = [], ""
    for line in body.split("\n"):
        m = FENCE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = ""
            continue
        if m:
            fence = m.group(1)
            continue
        out.append(INLINE_CODE.sub(" ", line) if "`" in line else line)
    return "\n".join(out)


def _front_tags(front: str) -> list[str]:
    tags, in_list = [], False
    for line in front.split("\n"):
        m = re.match(r"^(tags|tag)\s*:\s*(.*)$", line, re.I)
        if m:
            value = m.group(2).strip()
            in_list = not value
            tags += [t for t in re.split(r"[,\s\[\]\"']+", value) if t]
            continue
        if in_list:
            item = re.match(r"^\s*-\s*[\"']?([^\"'\s]+)", line)
            if item:
                tags.append(item.group(1))
            elif line.strip():
                in_list = False
    return [t.lstrip("#") for t in tags if t.lstrip("#")]


def parse(text: str) -> tuple[set[str], list[str]]:
    """(tags, link targets) of a note: #tags and front-matter tags (lowercased), [[wiki links]] and links to .md
    files (targets as written, without .md)."""
    front, _ = split_frontmatter(text)
    body = prose(text)
    tags = {t.lower().rstrip("/") for t in TAG.findall(body)} | {t.lower() for t in _front_tags(front)}
    links = [m.group(2).strip() for m in WIKI.finditer(body)
             if m.group(2).strip() and not (m.group(1) and m.group(2).strip().lower().endswith(IMAGE_EXT))]
    for m in MDLINK.finditer(body):
        target = m.group(1)
        if "://" not in target:
            from urllib.parse import unquote
            links.append(unquote(target))
    return tags, links


def words(text: str) -> int:
    return len(WORD.findall(text))


def link_key(target: str) -> str:
    """How a link target is looked up: lowercased, without a .md extension or leading ./"""
    t = target.strip().replace("\\", "/").removeprefix("./").lower()
    for ext in MD_EXT:
        if t.endswith(ext):
            t = t[: -len(ext)]
    return t


def safe_link_name(target: str) -> str:
    """A note name for an unresolved [[link]] (clicking it makes that note): the last part, cleaned."""
    name = re.sub(r'[\\:*?"<>|\x00-\x1f]', " ", target.strip().split("/")[-1]).strip(" .")
    return name or "Untitled"


# ---------------------------------------------------------------- the home page's line
STATUS = CACHE / "notel-status.json"


def remember_status(notes: int, last: str):
    try:
        write_atomic(STATUS, json.dumps({"notes": notes, "last": last}).encode())
    except OSError:
        pass


def status_line() -> str:
    try:
        d = json.loads(STATUS.read_text())
        n, last = int(d.get("notes", 0)), str(d.get("last", ""))
    except (OSError, ValueError, TypeError, AttributeError):
        return tr("grimoire.spells.notel.store", "Markdown notes and a text editor")
    if not n:
        return tr("grimoire.spells.notel.store", "No notes yet")
    if last:
        return tr("grimoire.spells.notel.store", "%n note(s) · last edited {name}", n=n).format(name=last)
    return tr("grimoire.spells.notel.store", "%n note(s)", n=n)
