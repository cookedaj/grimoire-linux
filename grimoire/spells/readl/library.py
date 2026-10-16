# SPDX-License-Identifier: GPL-3.0-or-later
"""ReadL's memory: the recent list (where you left off in each file, its bookmarks and zoom) and the reader's
settings, in CONFIG/readl.json. No Qt.

Every change re-reads the file under an flock and changes only its own entry, so two ReadL windows don't undo each
other's progress. Files are only ever read: removing one from the list never touches the file itself.
"""
import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

from grimoire.i18n import tr
from grimoire.paths import CACHE, CONFIG

KINDS = {".pdf": "pdf", ".epub": "epub", ".md": "markdown", ".markdown": "markdown", ".mdown": "markdown",
         ".txt": "text", ".text": "text"}
MODES = ("day", "night", "paper")             # night = inverted, paper = soft gray page (no sepia: black & white)
LAYOUTS = ("single", "continuous", "two")
FITS = ("width", "page", "custom")
FONTS = ("sans", "serif")
DEFAULTS = {"mode": "day", "layout": "continuous", "sidebar": True, "tab": "contents", "font": "serif",
            "font_scale": 1.0, "measure": 720, "qtpdf_hint": True}
MAX_RECENT = 300
ZOOM_MIN, ZOOM_MAX = 0.1, 8.0


def store_file() -> Path:
    return CONFIG / "readl.json"


def covers_dir() -> Path:
    return CACHE / "readl" / "covers"


def kind_of(path) -> str:
    """'pdf', 'epub', 'markdown', 'text' or '' from the name; a file without a known ending is sniffed."""
    p = Path(path)
    k = KINDS.get(p.suffix.lower(), "")
    if k:
        return k
    try:
        with open(p, "rb") as f:
            head = f.read(64)
    except OSError:
        return ""
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"PK\x03\x04") and b"mimetypeapplication/epub+zip" in head:
        return "epub"
    return ""


def key(path) -> str:
    return os.path.realpath(os.path.expanduser(str(path)))


@contextmanager
def _locked():
    store_file().parent.mkdir(parents=True, exist_ok=True)
    lock_file = CACHE / "readl" / "readl.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
        except OSError:
            pass
        yield


def _read() -> dict:
    try:
        d = json.loads(store_file().read_text())
    except (OSError, ValueError):
        d = {}
    if not isinstance(d, dict):
        d = {}
    if not isinstance(d.get("recent"), dict):
        d["recent"] = {}
    if not isinstance(d.get("settings"), dict):
        d["settings"] = {}
    return d


def _write(d: dict):
    f = store_file()
    tmp = f.with_name(f".{f.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    os.chmod(tmp, 0o600)
    tmp.replace(f)


# ---------------------------------------------------------------- settings
def settings() -> dict:
    s = dict(DEFAULTS)
    for k, v in _read()["settings"].items():
        if k in DEFAULTS and type(v) is type(DEFAULTS[k]):
            s[k] = v
    if s["mode"] not in MODES:
        s["mode"] = DEFAULTS["mode"]
    if s["layout"] not in LAYOUTS:
        s["layout"] = DEFAULTS["layout"]
    if s["font"] not in FONTS:
        s["font"] = DEFAULTS["font"]
    s["font_scale"] = min(3.0, max(0.5, s["font_scale"]))
    s["measure"] = min(1600, max(360, s["measure"]))
    return s


def save_settings(**changes):
    with _locked():
        d = _read()
        d["settings"].update({k: v for k, v in changes.items() if k in DEFAULTS})
        _write(d)


# ---------------------------------------------------------------- the recent list
def _clean(e: dict) -> dict | None:
    if not isinstance(e, dict) or not isinstance(e.get("path"), str):
        return None
    out = {"path": e["path"], "title": str(e.get("title") or Path(e["path"]).stem)[:300],
           "author": str(e.get("author") or "")[:200], "kind": e.get("kind") if e.get("kind") in KINDS.values()
           else kind_of(e["path"]), "pos": e.get("pos") if isinstance(e.get("pos"), dict) else {},
           "progress": min(1.0, max(0.0, float(e.get("progress") or 0))) if isinstance(
               e.get("progress"), (int, float)) else 0.0,
           "pages": int(e["pages"]) if isinstance(e.get("pages"), int) else 0,
           "opened": float(e["opened"]) if isinstance(e.get("opened"), (int, float)) else 0.0,
           "fit": e.get("fit") if e.get("fit") in FITS else "width",
           "zoom": min(ZOOM_MAX, max(ZOOM_MIN, float(e["zoom"]))) if isinstance(e.get("zoom"), (int, float))
           else 1.0,
           "bookmarks": [b for b in (e.get("bookmarks") or []) if isinstance(b, dict) and isinstance(
               b.get("pos"), dict)][:500] if isinstance(e.get("bookmarks"), list) else []}
    return out


def recent() -> list[dict]:
    """Newest first."""
    items = [c for c in (_clean(e) for e in _read()["recent"].values()) if c]
    return sorted(items, key=lambda e: e["opened"], reverse=True)


def entry(path) -> dict:
    """What ReadL remembers about this file (a fresh entry when nothing)."""
    k = key(path)
    return _clean(_read()["recent"].get(k) or {"path": k}) or {"path": k}


def update(path, **fields) -> dict:
    """Merge fields into the file's entry (adds it to the list when new) and keep the list bounded."""
    k = key(path)
    with _locked():
        d = _read()
        cur = d["recent"].get(k) if isinstance(d["recent"].get(k), dict) else {"path": k}
        cur.update(fields)
        cur["path"] = k
        d["recent"][k] = cur
        if len(d["recent"]) > MAX_RECENT:
            keep = sorted(d["recent"].items(), key=lambda kv: (kv[1].get("opened") or 0) if isinstance(
                kv[1], dict) else 0, reverse=True)[:MAX_RECENT]
            d["recent"] = dict(keep)
        _write(d)
    return _clean(cur) or {}


def opened(path, **fields) -> dict:
    return update(path, opened=time.time(), **fields)


def forget(path):
    """Take a file off the list (the file itself stays where it is)."""
    k = key(path)
    with _locked():
        d = _read()
        if d["recent"].pop(k, None) is not None:
            _write(d)


def add_bookmark(path, pos: dict, label: str) -> list:
    marks = entry(path)["bookmarks"]
    if any(b["pos"] == pos for b in marks):
        return marks
    marks.append({"pos": pos, "label": label[:200], "made": time.time()})
    marks.sort(key=_order)
    update(path, bookmarks=marks)
    return marks


def remove_bookmark(path, pos: dict) -> list:
    marks = [b for b in entry(path)["bookmarks"] if b["pos"] != pos]
    update(path, bookmarks=marks)
    return marks


def rename_bookmark(path, pos: dict, label: str) -> list:
    marks = entry(path)["bookmarks"]
    for b in marks:
        if b["pos"] == pos:
            b["label"] = label.strip()[:200] or b["label"]
    update(path, bookmarks=marks)
    return marks


def _order(b: dict):
    p = b["pos"]
    return (int(p.get("page", p.get("chapter", 0)) or 0), float(p.get("y", 0) or 0))


def status_line() -> str:
    items = recent()
    if not items:
        return tr("grimoire.spells.readl.library", "Nothing read yet · PDF, EPUB and Markdown")
    last = items[0]
    from grimoire import i18n
    return tr("grimoire.spells.readl.library", "Last read {title} · {pct}%").format(
        title=i18n.isolate(last["title"]), pct=round(last["progress"] * 100))
