# SPDX-License-Identifier: GPL-3.0-or-later
"""PlayL's data (no Qt): what counts as media, turning files/folders/playlists/URLs into queue entries, settings
(playl.json), resume positions per file (playl-positions.json) and the hub's status line."""
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from grimoire import paths
from grimoire.i18n import tr

VIDEO = {".mp4", ".m4v", ".mkv", ".webm", ".avi", ".mov", ".wmv", ".flv", ".mpg", ".mpeg", ".m2ts", ".mts", ".ts",
         ".ogv", ".3gp", ".vob", ".divx", ".f4v", ".rmvb", ".asf"}
AUDIO = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".wma", ".alac", ".aiff", ".aif",
         ".ape", ".wv", ".mka", ".mpc", ".ac3", ".dts", ".amr", ".mid", ".midi", ".spx", ".tta", ".dsf", ".dff"}
PLAYLISTS = {".m3u", ".m3u8", ".pls"}
SUBTITLES = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".sup", ".idx", ".smi", ".lrc"}
SCHEMES = ("http", "https", "rtsp", "rtmp", "mms", "ftp", "smb", "sftp", "dvd", "bd", "cdda", "udp", "rtp", "srt")
MIME_TYPES = ["audio/aac", "audio/ac3", "audio/flac", "audio/x-flac", "audio/mp4", "audio/mpeg", "audio/x-mp3",
              "audio/ogg", "audio/vorbis", "audio/opus", "audio/x-opus+ogg", "audio/vnd.wave", "audio/x-wav",
              "audio/wav", "audio/webm", "audio/x-matroska", "audio/x-ms-wma", "audio/x-aiff", "audio/x-ape",
              "audio/x-wavpack", "audio/x-musepack", "audio/midi", "audio/x-m4a", "audio/mpegurl", "audio/x-mpegurl",
              "audio/x-scpls", "video/mp4", "video/x-matroska", "video/webm", "video/mpeg", "video/ogg",
              "video/quicktime", "video/vnd.avi", "video/x-msvideo", "video/x-ms-wmv", "video/x-flv", "video/mp2t",
              "video/3gpp", "video/x-m4v", "video/x-ogm+ogg", "video/x-theora+ogg", "application/vnd.apple.mpegurl"]
DEFAULTS = {"resume": True, "hwdec": True, "library": ["~/Music"], "queue_open": True, "repeat": "off",
            "shuffle": False, "last_folder": ""}
REPEATS = ("off", "all", "one")
MAX_POSITIONS = 500
RESUME_MIN_LENGTH = 60.0          # shorter files always start from the top
RESUME_EDGE = 10.0                # nothing to resume in the first/last 10 s
NOW: dict = {}                    # what the running player shows (title, playing), for the status line


# ---------------------------------------------------------------- kinds of things
def is_url(s: str) -> bool:
    return "://" in s and urlparse(s).scheme.lower() in SCHEMES


def kind(entry: str) -> str:
    """"video", "audio", "url" or "" for a queue entry."""
    if is_url(entry):
        return "url"
    ext = Path(entry).suffix.lower()
    return "video" if ext in VIDEO else "audio" if ext in AUDIO else ""


def is_media(path: Path) -> bool:
    return path.suffix.lower() in VIDEO | AUDIO


def _natural(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def local(arg: str) -> str:
    """A file:// URL as a path; ~ expanded; anything else as given."""
    if arg.startswith("file://"):
        return unquote(urlparse(arg).path)
    if arg.startswith("~"):
        return str(Path(arg).expanduser())
    return arg


def folder_media(folder: Path, limit: int = 5000) -> list[str]:
    """Media files under folder (subfolders too), in natural order, hidden ones skipped."""
    found = []
    for root, dirs, files in os.walk(folder, followlinks=False):
        dirs[:] = sorted((d for d in dirs if not d.startswith(".")), key=_natural)
        for f in sorted(files, key=_natural):
            if not f.startswith(".") and Path(f).suffix.lower() in VIDEO | AUDIO:
                found.append(os.path.join(root, f))
                if len(found) >= limit:
                    return found
    return found


def read_playlist(path: Path) -> list[str]:
    """Entries of an .m3u/.m3u8/.pls file: relative paths resolved against its folder, URLs kept."""
    out = []
    try:
        text = path.read_text(errors="replace")[:2_000_000]
    except OSError:
        return out
    pls = path.suffix.lower() == ".pls"
    for line in text.splitlines():
        line = line.strip().lstrip("﻿")
        if pls:
            m = re.match(r"File\d+=(.+)", line, re.I)
            if not m:
                continue
            line = m.group(1).strip()
        elif not line or line.startswith("#"):
            continue
        if is_url(line):
            out.append(line)
            continue
        p = Path(local(line))
        p = p if p.is_absolute() else path.parent / p
        out.append(str(p))
    return out


def gather(args: list[str]) -> list[str]:
    """Queue entries for what was opened: files, folders (their media), playlists (their entries), URLs."""
    out: list[str] = []
    for arg in args:
        arg = local(arg.strip())
        if not arg:
            continue
        if is_url(arg):
            out.append(arg)
            continue
        p = Path(arg)
        if p.is_dir():
            out += folder_media(p)
        elif p.suffix.lower() in PLAYLISTS and p.is_file():
            out += read_playlist(p)
        elif p.exists():
            out.append(str(p.resolve()))
    return out


def display_name(entry: str) -> str:
    """A file's name without extension, or a URL's last part."""
    if is_url(entry):
        u = urlparse(entry)
        last = unquote(u.path.rstrip("/").rsplit("/", 1)[-1])
        return last or u.netloc
    return Path(entry).stem


def clock(seconds: float | None) -> str:
    """1:05, 12:40 or 1:02:03."""
    if seconds is None or seconds != seconds or seconds < 0:
        return "–:––"
    s = int(seconds)
    h, m, s = s // 3600, s // 60 % 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------- settings
def _settings_file() -> Path:
    return paths.CONFIG / "playl.json"


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def load() -> dict:
    data = _read(_settings_file())
    out = dict(DEFAULTS)
    for k, v in data.items():
        if k in DEFAULTS and type(v) is type(DEFAULTS[k]):
            out[k] = v
    if out["repeat"] not in REPEATS:
        out["repeat"] = "off"
    out["library"] = [str(x) for x in out["library"] if isinstance(x, str) and x.strip()]
    return out


def save(**changes) -> dict:
    data = load() | {k: v for k, v in changes.items() if k in DEFAULTS}
    _write(_settings_file(), data)
    return data


def library_roots(settings: dict | None = None) -> list[Path]:
    return [Path(r).expanduser() for r in (settings or load())["library"]]


# ---------------------------------------------------------------- resume positions
def _positions_file() -> Path:
    return paths.CONFIG / "playl-positions.json"


def _key(entry: str) -> str:
    return hashlib.sha1(entry.encode("utf-8", "surrogateescape")).hexdigest()


class Positions:
    """Resume points, kept in memory and written back off the UI thread (save() is safe on any thread)."""

    def __init__(self, data: dict | None = None):
        self.data = data if data is not None else _read(_positions_file())

    def get(self, entry: str) -> float:
        """Where to start entry again (0 when there's nothing to resume)."""
        rec = self.data.get(_key(entry))
        try:
            return max(0.0, float(rec["pos"])) if isinstance(rec, dict) else 0.0
        except (KeyError, TypeError, ValueError):
            return 0.0

    def put(self, entry: str, pos: float | None, length: float | None) -> bool:
        """Keep pos for entry when it's worth resuming (a long file, not at its start or end), forget it
        otherwise; True when something changed."""
        if not entry:
            return False
        key = _key(entry)
        worth = (pos is not None and length is not None and length >= RESUME_MIN_LENGTH
                 and RESUME_EDGE <= pos <= length - RESUME_EDGE)
        if worth:
            self.data[key] = {"pos": round(pos, 1), "len": round(length, 1), "at": int(time.time())}
            if len(self.data) > MAX_POSITIONS:
                old = sorted(self.data, key=lambda k: self.data[k].get("at", 0) if isinstance(self.data[k], dict) else 0)
                for k in old[:len(self.data) - MAX_POSITIONS]:
                    self.data.pop(k, None)
            return True
        return self.data.pop(key, None) is not None

    def clear(self):
        self.data = {}

    def save(self):
        _write(_positions_file(), dict(self.data))


# ---------------------------------------------------------------- the hub's line
def status_line() -> str:
    if NOW.get("title"):
        if NOW.get("playing"):
            return tr("grimoire.spells.playl.media", "Playing {title}").format(title=NOW["title"])
        return tr("grimoire.spells.playl.media", "Paused: {title}").format(title=NOW["title"])
    try:
        from grimoire.spells.playl import library
        n = library.cached_count()
    except Exception:
        n = 0
    if n:
        return tr("grimoire.spells.playl.media", "%n song(s) in your library", n=n)
    return tr("grimoire.spells.playl.media", "Open a video or song, or point it at your music folder")
