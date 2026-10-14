# SPDX-License-Identifier: GPL-3.0-or-later
"""Share your setup: the whole Grimoire look as one .grimoire-setup file (or a short GS1- code), and importing one.

A setup is the look only: MuraL's applied designs + options and wallpaper playlist (optionally the wallpaper images),
community store items by store id (the importer downloads them on click; third-party files are never bundled), the
SightsL crosshair + profiles, TerminalL profiles, LaunchL's favorites order and the tray meter. Never anything
personal: no accounts, tokens or gist ids, no tidy rules, history, network or usage data, no TerminalL palette
commands (they run in a shell), and no paths: wallpapers travel by file name. export() refuses to write a setup whose
text still holds the home path, user name, host name or an email address (scrub()).

A shared setup is untrusted input, so inspect() checks it like backup.inspect(): a zip and nothing else, size and
count caps, allowlisted relative names, no links, every file in the manifest with its sha256, images that really are
images, and setup.json rebuilt field by field from a schema (unknown keys dropped, numbers clamped, text capped, ids
checked against what Grimoire knows). Nothing in it is executed and its text is only ever shown as plain text.
apply() saves a safety backup (backup.py) first, then writes atomically; the MuraL part becomes a saved look, so
changing the desktop stays a separate, optional step (apply_look()).

The module imports without Qt; the schema and MuraL steps load MuraL's modules (Qt) when they run.
"""
import base64
import getpass
import hashlib
import io
import json
import math
import os
import re
import socket
import stat
import time
import uuid
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from grimoire import __version__
from grimoire.i18n import tr, tr_noop
from grimoire.paths import CONFIG, DATA, HOME

FORMAT = "grimoire-setup"
FORMAT_VERSION = 1
SUFFIX = ".grimoire-setup"
CODE_PREFIX = "GS1-"
LIBRARY = DATA / "mural" / "library"           # MuraL's wallpaper library (library.LIBRARY, without importing Qt)
MURAL_STATE = CONFIG / "mural-screens.json"
MURAL_DESKTOP = CONFIG / "mural.json"
TRAY = CONFIG / "tray.json"

MAX_ARCHIVE = 200 << 20
MAX_FILES = 64
MAX_MANIFEST = 64 << 10
MAX_SETUP = 256 << 10
MAX_PREVIEW = 4 << 20
MAX_WALLPAPER = 40 << 20
MAX_WALLPAPERS = 150 << 20                     # everything a file may expand to
WALLPAPER_CAP = 100 << 20                      # what export() bundles at most
MAX_CODE = 2048                                # a share code longer than this is offered as a file only
TITLE_MAX, AUTHOR_MAX = 60, 40

IMAGE = r"\.(?:png|jpe?g|webp)"
MEDIA = r"\.(?:png|jpe?g|webp|bmp|avif|tiff?|gif|mp4|webm|mkv|mov|m4v)"
NAME = r"[A-Za-z0-9][A-Za-z0-9 ._()+,'&-]{0,119}"   # a library file name: no slashes, no leading dot
IMAGE_NAME = re.compile(NAME + IMAGE, re.I)
MEDIA_NAME = re.compile(NAME + MEDIA, re.I)
THEME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+ -]{0,79}")             # an icon/cursor theme or store ident
ITEM = re.compile(r"kde-\d{1,12}|wh-[a-z0-9]{1,16}")
FAVORITE = re.compile(r"(?:applications:)?[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.desktop"
                      r"|preferred://(?:browser|filemanager|mailer|terminal)")
MAGIC = {".png": (b"\x89PNG\r\n\x1a\n",), ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
         ".webp": (b"RIFF",)}
SPELLS = ["mural", "sightc", "terminall", "launchl", "tray"]
SPELL_NAMES = {"mural": "MuraL", "sightc": "SightsL", "terminall": "TerminalL", "launchl": "LaunchL",
               "tray": tr_noop("grimoire.sharesetup", "Tray")}      # shown with tr("grimoire.sharesetup", …)


class ShareError(ValueError):
    """Why a setup can't be exported, read or applied, worded for the UI."""


# ---------------------------------------------------------------- the schema
def _text(v, limit: int, default: str = "") -> str:
    """Plain one-line text: control and direction-override characters removed, capped, and < > turned into ‹ ›
    so no label anywhere (Qt and QML guess "rich text" from tags) can ever treat it as markup."""
    if not isinstance(v, str):
        return default
    v = "".join(c for c in v if c.isprintable() and not 0x202A <= ord(c) <= 0x202E and not 0x2066 <= ord(c) <= 0x2069)
    return v.replace("<", "‹").replace(">", "›").strip()[:limit]


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


class B:                                        # a tickbox
    def __init__(self, default: bool):
        self.default = default

    def clean(self, v):
        return v if isinstance(v, bool) else self.default


class I:                                        # a whole number in a range (sliders)
    def __init__(self, lo, hi, default, kind=int):
        self.lo, self.hi, self.default, self.kind = lo, hi, default, kind

    def clean(self, v):
        return self.kind(min(self.hi, max(self.lo, v))) if _num(v) else self.default


class C:                                        # one of a fixed list (combo boxes)
    def __init__(self, choices, default):
        self.choices, self.default = list(choices), default

    def clean(self, v):
        return v if isinstance(v, str) and v in self.choices else self.default


class T:                                        # free text
    def __init__(self, limit, default):
        self.limit, self.default = limit, default

    def clean(self, v):
        return _text(v, self.limit, self.default) or self.default


class Img:                                      # a library picture by file name (or "Plain black")
    def __init__(self, default, extra=()):
        self.default, self.extra = default, tuple(extra)

    def clean(self, v):
        return v if isinstance(v, str) and (v in self.extra or IMAGE_NAME.fullmatch(v)) else self.default


@dataclass
class Tab:
    designs: list                                # Grimoire's own design ids
    store: tuple = ()                            # store kinds whose items show up as "store:<kind>:<ident>"
    themes: str = ""                             # icons/cursor: any theme name; its store kind
    images: bool = False                         # lock: "img:<library picture>"
    options: dict = field(default_factory=dict)


@lru_cache(maxsize=1)
def schema() -> dict:
    """Every MuraL tab a setup may carry, built from the tabs' own lists so it never drifts from them."""
    from grimoire.spells.mural import (boot, colors, cursor, fonts, lock, login, motion, splash, style, taskbar,
                                       terminal, windows)
    ids = lambda m: [d.id for d in m.DESIGNS]
    D = lambda m, k: m.DEFAULTS[k]
    return {
        "lock": Tab(ids(lock), images=True, options={
            "dim": I(0, 90, 20), "blur": I(0, 40, 0), "clock": B(True), "clock_idle": B(False), "media": B(False)}),
        "splash": Tab(ids(splash), ("splash",), options={
            "tagline": T(40, D(splash, "tagline")), "show_tagline": B(D(splash, "show_tagline")),
            "speed": C(splash.SPEEDS, D(splash, "speed"))}),
        "login": Tab(ids(login), ("sddm",), options={
            "background": Img(D(login, "background"), [login.NO_IMAGE]), "dim": I(0, 90, D(login, "dim")),
            "clock24": B(D(login, "clock24")), "power": B(D(login, "power"))}),
        "boot": Tab(ids(boot), ("plymouth",), options={
            "size": C(boot.SIZES, D(boot, "size")), "position": C(boot.POSITIONS, D(boot, "position")),
            "firmware_logo": B(D(boot, "firmware_logo"))}),
        "taskbar": Tab(ids(taskbar), options={
            "look": C(taskbar.LOOK_NAMES, D(taskbar, "look")), "height": I(28, 80, D(taskbar, "height")),
            "opacity": C(taskbar.OPACITY, D(taskbar, "opacity")), "floating": B(D(taskbar, "floating")),
            "autohide": B(D(taskbar, "autohide"))}),
        "style": Tab(ids(style), ("plasma",)),
        "windows": Tab(ids(windows), ("aurorae",), options={
            "size": C(windows.SIZES, D(windows, "size")), "align": C(windows.ALIGN, D(windows, "align")),
            "border": C(windows.BORDERS, D(windows, "border")), "outline": C(windows.OUTLINE, D(windows, "outline")),
            "borderless_max": B(D(windows, "borderless_max"))}),
        "motion": Tab(ids(motion), options={
            "blur": I(1, 15, D(motion, "blur")), "noise": I(0, 14, D(motion, "noise")),
            "wobbly": B(D(motion, "wobbly"))}),
        "colors": Tab(ids(colors), ("colors",), options={
            "titlebar": C(["Match", "Black"], D(colors, "titlebar")), "accent": C(colors.ACCENTS, D(colors, "accent"))}),
        "icons": Tab([], themes="icons"),
        "fonts": Tab(ids(fonts), options={
            "size": I(8, 14, D(fonts, "size")), "title_weight": C(["Bold", "Regular"], D(fonts, "title_weight")),
            "hinting": C(fonts.HINTING, D(fonts, "hinting")), "subpixel": C(["On", "Off"], D(fonts, "subpixel"))}),
        "cursor": Tab(ids(cursor), themes="cursor", options={"size": C(cursor.SIZES, D(cursor, "size"))}),
        "terminal": Tab(ids(terminal), ("konsole",), options={
            "font": C(terminal.FONTS, D(terminal, "font")), "size": I(8, 20, D(terminal, "size")),
            "transparency": I(0, 60, D(terminal, "transparency")), "blur": B(D(terminal, "blur")),
            "padding": I(0, 40, D(terminal, "padding")), "cursor": C(terminal.CURSORS, D(terminal, "cursor")),
            "prompt": C(terminal.PROMPTS, D(terminal, "prompt"))}),
    }


def _design_ok(tab: Tab, design) -> bool:
    if not isinstance(design, str) or len(design) > 120:
        return False
    if design in tab.designs:
        return True
    if tab.images and design.startswith("img:"):
        return bool(IMAGE_NAME.fullmatch(design[4:]))
    if tab.themes:
        return bool(THEME.fullmatch(design))
    kind, _, ident = design.removeprefix("store:").partition(":")
    return design.startswith("store:") and kind in tab.store and bool(THEME.fullmatch(ident))


def _clean_tab(tab: Tab, entry) -> dict | None:
    if not isinstance(entry, dict) or not _design_ok(tab, entry.get("design")):
        return None
    opts = entry.get("options") if isinstance(entry.get("options"), dict) else {}
    return {"design": entry["design"], "options": {k: spec.clean(opts.get(k, spec.default))
                                                   for k, spec in tab.options.items()}}


def _clean_desktop(d) -> dict | None:
    if not isinstance(d, dict) or not isinstance(d.get("items"), list):
        return None
    items = [n for n in d["items"][:200] if isinstance(n, str) and MEDIA_NAME.fullmatch(n)]
    if not items:
        return None
    return {"items": list(dict.fromkeys(items)), "interval_min": I(1, 1440, 5).clean(d.get("interval_min")),
            "fade_s": I(0, 10, 1.2, float).clean(d.get("fade_s")), "shuffle": B(False).clean(d.get("shuffle")),
            "fill": C(["Crop", "Fit", "Stretch"], "Crop").clean(d.get("fill")),
            "pause_fullscreen": B(True).clean(d.get("pause_fullscreen")), "muted": B(True).clean(d.get("muted"))}


def _clean_store(refs) -> list:
    from grimoire.spells.mural.store import CATEGORIES
    kinds = {c.kind for c in CATEGORIES.values()}
    out, seen = [], set()
    for r in refs[:40] if isinstance(refs, list) else []:
        if not isinstance(r, dict):
            continue
        kind, item, ident = r.get("kind"), r.get("item"), r.get("ident")
        if (kind not in kinds or not isinstance(item, str) or not ITEM.fullmatch(item) or not isinstance(ident, str)
                or not (THEME.fullmatch(ident) or MEDIA_NAME.fullmatch(ident)) or (kind, ident) in seen):
            continue
        seen.add((kind, ident))
        out.append({"kind": kind, "ident": ident, "item": item, "name": _text(r.get("name"), 80) or ident,
                    "author": _text(r.get("author"), 40)})
    return out


def _profile_name(k) -> str:
    return _text(k, 40)


def clean(raw) -> dict:
    """setup.json rebuilt from the schema: only known sections and keys, every value checked."""
    from grimoire.spells.sightc.config import Crosshair
    from grimoire.spells.terminall.config import clean_profile
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    m = raw.get("mural")
    if isinstance(m, dict):
        tabs = {}
        for key, tab in schema().items():
            entry = _clean_tab(tab, (m.get("tabs") or {}).get(key) if isinstance(m.get("tabs"), dict) else None)
            if entry:
                tabs[key] = entry
        desktop = _clean_desktop(m.get("desktop"))
        if tabs or desktop:
            out["mural"] = {"tabs": tabs, "desktop": desktop}
    store = _clean_store(raw.get("store"))
    if store:
        out["store"] = store
    s = raw.get("sightc")
    if isinstance(s, dict):
        sec = {}
        if isinstance(s.get("crosshair"), dict):
            sec["crosshair"] = Crosshair.from_dict(s["crosshair"]).look()
        if isinstance(s.get("profiles"), dict):
            sec["profiles"] = {n: Crosshair.from_dict(v).look() for k, v in list(s["profiles"].items())[:50]
                               if isinstance(v, dict) and (n := _profile_name(k))}
        if sec:
            out["sightc"] = sec
    t = raw.get("terminall")
    if isinstance(t, dict) and isinstance(t.get("profiles"), dict):       # profiles only: never "commands"
        profiles = {n: {**(c := clean_profile(v)), "font": _text(c["font"], 79) or "IBM Plex Mono"}
                    for k, v in list(t["profiles"].items())[:20] if isinstance(v, dict) and (n := _profile_name(k))}
        if profiles:
            cur = t.get("profile") if t.get("profile") in profiles else next(iter(profiles))
            out["terminall"] = {"profile": cur, "profiles": profiles}
    f = raw.get("launchl")
    if isinstance(f, dict) and isinstance(f.get("favorites"), list):
        favs = [x for x in f["favorites"][:50] if isinstance(x, str) and FAVORITE.fullmatch(x)]
        if favs:
            out["launchl"] = {"favorites": list(dict.fromkeys(favs))}
    tray = raw.get("tray")
    if isinstance(tray, dict) and isinstance(tray.get("meter"), bool):
        out["tray"] = {"meter": tray["meter"]}
    return out


# ---------------------------------------------------------------- what this PC has now
def _json(path: Path, default):
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def _registry() -> dict:
    from grimoire.spells.mural.store import registry
    reg = registry()
    return reg if isinstance(reg, dict) else {}


def _launchl_favorites() -> list:
    from grimoire.spells.launchl import panel
    rec = panel.load_state().get("replaced") or {}
    if not isinstance(rec, dict) or not rec.get("favorites_client"):
        return []
    return panel.favorites(rec["favorites_client"]) or list(rec.get("favorites") or [])


def current() -> dict:
    """This PC's look in the setup format (paths become library file names); also what previews compare against."""
    from grimoire.spells.sightc.config import Crosshair, load_profiles
    from grimoire.spells.terminall import config as term
    state, desk = _json(MURAL_STATE, {}), _json(MURAL_DESKTOP, {})
    tabs = {k: v for k, v in state.items() if k != "desktop" and isinstance(v, dict) and v.get("design")}
    items = desk.get("items") if isinstance(desk.get("items"), list) else []
    desktop = {**desk, "items": [Path(p).name for p in items if isinstance(p, str)]}
    cfg = term.load()
    raw = {"mural": {"tabs": tabs, "desktop": desktop},
           "sightc": {"crosshair": Crosshair.load().look(), "profiles": {k: c.look() for k, c in load_profiles().items()}},
           "terminall": {"profile": cfg["profile"], "profiles": cfg["profiles"]},
           "launchl": {"favorites": _launchl_favorites()},
           "tray": {"meter": bool(_json(TRAY, {}).get("meter", True))}}
    setup = clean(raw)
    setup["store"] = _store_refs(setup)
    if not setup["store"]:
        setup.pop("store")
    return setup


def _store_refs(setup: dict) -> list:
    """The community items this setup uses, by store id, so an importer can get them from the store."""
    reg, refs = _registry(), []
    by_key = {k: e for k, e in reg.items() if isinstance(e, dict)}
    wanted = []
    for key, entry in (setup.get("mural") or {}).get("tabs", {}).items():
        d, tab = entry["design"], schema()[key]
        if d.startswith("store:"):
            wanted.append(d[6:])
        elif tab.themes:
            wanted.append(f"{tab.themes}:{d}")
    for name in _pictures(setup):
        wanted.append(f"wallpaper:{name}")
    for k in dict.fromkeys(wanted):
        e = by_key.get(k)
        if e:
            refs.append({"kind": e.get("kind"), "ident": e.get("ident"), "item": e.get("item"), "name": e.get("name"),
                         "author": e.get("author", "")})
    return _clean_store(refs)


def _pictures(setup: dict) -> list:
    """Library file names a setup refers to: the playlist, the lock picture, the login background."""
    m = setup.get("mural") or {}
    names = list((m.get("desktop") or {}).get("items", []))
    lock = (m.get("tabs") or {}).get("lock", {}).get("design", "")
    if lock.startswith("img:"):
        names.append(lock[4:])
    bg = (m.get("tabs") or {}).get("login", {}).get("options", {}).get("background")
    if bg and IMAGE_NAME.fullmatch(bg):
        names.append(bg)
    return list(dict.fromkeys(names))


# ---------------------------------------------------------------- the scrub check
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _personal() -> list[tuple[str, re.Pattern]]:
    """What must never leave this PC in a shared setup, as (what it is, pattern)."""
    pats = [(tr("grimoire.sharesetup", "your home folder's path"), re.compile(re.escape(str(HOME)))),
            (tr("grimoire.sharesetup", "a path to someone's home folder"), re.compile(r"/home/|/root/|file:/", re.I)),
            (tr("grimoire.sharesetup", "an email address"), EMAIL)]
    user, pc = tr("grimoire.sharesetup", "your user name"), tr("grimoire.sharesetup", "this computer's name")
    words = [(user, getpass.getuser()), (user, HOME.name)]
    host = socket.gethostname()
    words += [(pc, host), (pc, host.split(".")[0])]
    for what, w in words:                       # as whole words; a two-letter name only in its own case
        if w and len(w) >= 2 and w.lower() not in ("root", "user", "home", "localhost"):
            pats.append((what, re.compile(rf"(?<![A-Za-z0-9]){re.escape(w)}(?![A-Za-z0-9])",
                                          re.I if len(w) > 2 else 0)))
    return pats


def _strings(obj, where=""):
    if isinstance(obj, str):
        yield where, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(str(k), f"{where}/{k}")
            yield from _strings(v, f"{where}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{where}/{i}")


def scrub(obj) -> list[str]:
    """Every place in obj (keys and values) that holds something personal, worded for the UI; [] when clean."""
    found, pats = [], _personal()
    for where, s in _strings(obj):
        for what, rx in pats:
            if rx.search(s):
                found.append(tr("grimoire.sharesetup", "{where} contains {what}").format(
                    where=where.strip('/') or tr("grimoire.sharesetup", "text"), what=what))
                break
    return found


# ---------------------------------------------------------------- export
@dataclass
class Draft:
    """What export() or share_code() would write; made by draft()."""
    setup: dict
    wallpapers: list = field(default_factory=list)        # [(name, Path, size)] to bundle
    left_out: list = field(default_factory=list)          # [(name, reason)]


def _library_file(name: str) -> Path | None:
    p = LIBRARY / name
    try:
        st = p.lstat()
    except OSError:
        return None
    return p if stat.S_ISREG(st.st_mode) else None


def draft(include_wallpapers=False, cap=WALLPAPER_CAP) -> Draft:
    d = Draft(current())
    if not include_wallpapers:
        return d
    total, store = 0, {r["ident"] for r in d.setup.get("store", []) if r["kind"] == "wallpaper"}
    for name in _pictures(d.setup):
        p = _library_file(name)
        if name in store:
            d.left_out.append((name, tr("grimoire.sharesetup", "from the community store")))
        elif p is None or not IMAGE_NAME.fullmatch(name):
            d.left_out.append((name, tr("grimoire.sharesetup", "not a picture in your library")))
        elif not _magic_ok(name, p.read_bytes()[:16]):
            d.left_out.append((name, tr("grimoire.sharesetup", "not a PNG, JPEG or WebP picture")))
        elif (size := p.stat().st_size) > MAX_WALLPAPER or total + size > cap:
            d.left_out.append((name, tr("grimoire.sharesetup", "too large")))
        else:
            total += size
            d.wallpapers.append((name, p, size))
    return d


def _meta(title: str, author: str) -> dict:
    title, author = _text(title, TITLE_MAX) or "Untitled setup", _text(author, AUTHOR_MAX)
    return {"format": FORMAT, "format_version": FORMAT_VERSION, "app_version": __version__,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "title": title, "author": author}


def _check_clean(meta: dict, setup: dict, names=()):
    problems = scrub({"title": meta["title"], "author": meta["author"], "setup": setup, "files": list(names)})
    if problems:
        raise ShareError(tr("grimoire.sharesetup", "Not shared: {problems}. Change it and try again.")
                         .format(problems="; ".join(problems[:3])))


def export(dest: Path, d: Draft, title: str, author: str = "", preview_png: bytes = b"") -> dict:
    """Write a .grimoire-setup to dest atomically (dest's folder must exist). Returns its manifest."""
    meta = _meta(title, author)
    if preview_png and (len(preview_png) > MAX_PREVIEW or not _magic_ok("preview.png", preview_png)):
        preview_png = b""
    _check_clean(meta, d.setup, [n for n, _, _ in d.wallpapers])
    blobs = [("setup.json", json.dumps(d.setup, indent=1, ensure_ascii=False).encode())]
    if preview_png:
        blobs.append(("preview.png", preview_png))
    tmp = dest.with_name(f".{dest.name}.tmp")
    files = []
    try:
        with open(tmp, "wb") as f, zipfile.ZipFile(f, "w") as z:
            stamp = time.localtime()[:6]
            for name, data in blobs:
                files.append({"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
                z.writestr(zipfile.ZipInfo(name, stamp), data, zipfile.ZIP_DEFLATED)
            for name, path, _ in d.wallpapers:
                data = path.read_bytes()
                files.append({"path": f"wallpapers/{name}", "size": len(data),
                              "sha256": hashlib.sha256(data).hexdigest()})
                z.writestr(zipfile.ZipInfo(f"wallpapers/{name}", stamp), data, zipfile.ZIP_STORED)
            meta["files"] = files
            z.writestr(zipfile.ZipInfo("manifest.json", stamp), json.dumps(meta, indent=1, ensure_ascii=False),
                       zipfile.ZIP_DEFLATED)
        with open(tmp, "rb+") as f:
            os.fsync(f.fileno())
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)                   # our own temp file, only left over on failure
    return meta


def share_code(d: Draft, title: str, author: str = "") -> str | None:
    """A GS1- text code of the setup (no pictures), or None when it would be longer than MAX_CODE."""
    meta = _meta(title, author)
    _check_clean(meta, d.setup)
    raw = json.dumps({"v": FORMAT_VERSION, "t": meta["title"], "a": meta["author"], "s": d.setup},
                     separators=(",", ":"), ensure_ascii=False).encode()
    code = CODE_PREFIX + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode().rstrip("=")
    return code if len(code) <= MAX_CODE else None


def default_name(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()[:40] or "setup"
    return f"{slug}{SUFFIX}"


# ---------------------------------------------------------------- import
@dataclass
class Shared:
    """A checked setup, made by inspect() or from_code()."""
    title: str
    author: str
    setup: dict
    created: str = ""
    app_version: str = ""
    preview: bytes = b""
    wallpapers: dict = field(default_factory=dict)      # name -> (size, sha256), all verified
    ignored: list = field(default_factory=list)          # archive names Grimoire doesn't know; never read
    source: object = None                               # Path or bytes, re-read by apply()
    digest: str = ""


def _magic_ok(name: str, head: bytes) -> bool:
    ext = os.path.splitext(name.lower())[1]
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return any(head.startswith(m) for m in MAGIC.get(ext, ()))


def _loads(data: bytes):
    def bad(_):
        raise ValueError("not a number")
    return json.loads(data.decode(), parse_constant=bad)


def _open(source) -> zipfile.ZipFile:
    if isinstance(source, (bytes, bytearray)):
        if len(source) > MAX_ARCHIVE:
            raise ShareError(tr("grimoire.sharesetup", "The setup is larger than the safety limit."))
        if not zipfile.is_zipfile(io.BytesIO(source)):
            raise ShareError(tr("grimoire.sharesetup", "That isn't a Grimoire setup (not a zip file)."))
        return zipfile.ZipFile(io.BytesIO(source))
    path = Path(source)
    try:
        st = path.stat()
    except OSError as e:
        raise ShareError(tr("grimoire.sharesetup", "Couldn't open the setup: {error}")
                         .format(error=e.strerror or e)) from None
    if not stat.S_ISREG(st.st_mode):
        raise ShareError(tr("grimoire.sharesetup", "That isn't a file."))
    if st.st_size > MAX_ARCHIVE:
        raise ShareError(tr("grimoire.sharesetup", "The setup is larger than the safety limit."))
    if not zipfile.is_zipfile(path):
        raise ShareError(tr("grimoire.sharesetup", "That isn't a Grimoire setup (not a zip file)."))
    return zipfile.ZipFile(path)


def _digest(source) -> str:
    if isinstance(source, (bytes, bytearray)):
        return hashlib.sha256(source).hexdigest()
    h = hashlib.sha256()
    with open(source, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _read(z: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int, sink=None) -> tuple[str, int]:
    """Stream one member (sha256, size), never past limit bytes."""
    h, n = hashlib.sha256(), 0
    with z.open(info) as f:
        while chunk := f.read(1 << 20):
            n += len(chunk)
            if n > limit:
                raise ShareError(tr("grimoire.sharesetup", "{name} is larger than it says (or than the limit).")
                                 .format(name=info.filename[:80]))
            h.update(chunk)
            if sink:
                sink(chunk)
    return h.hexdigest(), n


def _check_member(info: zipfile.ZipInfo):
    name, mode = info.filename, info.external_attr >> 16
    if info.flag_bits & 0x1:
        raise ShareError(tr("grimoire.sharesetup", "The setup is encrypted; Grimoire doesn't read those."))
    if stat.S_ISLNK(mode):
        raise ShareError(tr("grimoire.sharesetup", "The setup contains a link; not importing it."))
    if mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise ShareError(tr("grimoire.sharesetup", "The setup contains a special file; not importing it."))
    parts = name.rstrip("/").split("/")
    if (name.startswith("/") or "\\" in name or re.match(r"[A-Za-z]:", name) or len(name) > 300
            or any(not c.isprintable() for c in name) or any(s in ("", ".", "..") for s in parts)):
        raise ShareError(tr("grimoire.sharesetup", "The setup contains an unsafe file name; not importing it."))


def _kind(name: str) -> str | None:
    if name in ("setup.json", "preview.png"):
        return name
    if name.startswith("wallpapers/") and IMAGE_NAME.fullmatch(name[11:]):
        return "wallpaper"
    return None


LIMIT = {"setup.json": MAX_SETUP, "preview.png": MAX_PREVIEW, "wallpaper": MAX_WALLPAPER}


def _manifest(z: zipfile.ZipFile) -> dict:
    try:
        info = z.getinfo("manifest.json")
    except KeyError:
        raise ShareError(tr("grimoire.sharesetup", "That isn't a Grimoire setup (no manifest.json).")) from None
    raw = io.BytesIO()
    _read(z, info, MAX_MANIFEST, raw.write)
    try:
        meta = _loads(raw.getvalue())
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ShareError(tr("grimoire.sharesetup", "The setup's manifest isn't valid JSON.")) from None
    if not isinstance(meta, dict) or meta.get("format") != FORMAT:
        raise ShareError(tr("grimoire.sharesetup", "That isn't a Grimoire setup."))
    v = meta.get("format_version")
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        raise ShareError(tr("grimoire.sharesetup", "The setup's manifest is damaged."))
    if v > FORMAT_VERSION:
        raise ShareError(tr("grimoire.sharesetup", "This setup was made by a newer Grimoire; update Grimoire first."))
    files = meta.get("files")
    if not isinstance(files, list) or len(files) > MAX_FILES:
        raise ShareError(tr("grimoire.sharesetup", "The setup's manifest is damaged."))
    listed = {}
    for f in files:
        ok = (isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("size"), int)
              and not isinstance(f.get("size"), bool) and f["size"] >= 0 and isinstance(f.get("sha256"), str)
              and re.fullmatch(r"[0-9a-f]{64}", f["sha256"]))
        if not ok or f["path"] in listed:
            raise ShareError(tr("grimoire.sharesetup", "The setup's manifest is damaged."))
        listed[f["path"]] = f
    meta["files"] = listed
    return meta


def inspect(source) -> Shared:
    """Validate a setup file (a path or bytes) completely. Raises ShareError; nothing is written."""
    try:
        with _open(source) as z:
            digest = _digest(source)
            infos = z.infolist()
            if len(infos) > MAX_FILES:
                raise ShareError(tr("grimoire.sharesetup", "The setup holds more files than the safety limit."))
            names = [i.filename for i in infos]
            if len(set(names)) != len(names):
                raise ShareError(tr("grimoire.sharesetup", "The setup lists a file twice; not importing it."))
            for info in infos:
                _check_member(info)
            meta = _manifest(z)
            listed, total, raw, shared = meta["files"], 0, None, None
            preview, wallpapers, ignored = b"", {}, []
            for info in infos:
                name = info.filename
                if info.is_dir() or name == "manifest.json":
                    continue
                kind = _kind(name)
                if kind is None:
                    ignored.append(name[:120])
                    continue
                m = listed.pop(name, None)
                if m is None:
                    raise ShareError(tr(
                        "grimoire.sharesetup", "{name} isn't in the setup's manifest; not importing it.")
                        .format(name=name[:80]))
                if info.file_size != m["size"] or m["size"] > LIMIT[kind]:
                    raise ShareError(tr("grimoire.sharesetup", "{name} is larger than it says (or than the limit).")
                                     .format(name=name[:80]))
                total += m["size"]
                if total > MAX_WALLPAPERS + MAX_SETUP + MAX_PREVIEW:
                    raise ShareError(tr("grimoire.sharesetup", "The setup expands larger than the safety limit."))
                buf = io.BytesIO()
                keep = kind != "wallpaper"
                head = bytearray()

                def sink(chunk, buf=buf, keep=keep, head=head):
                    if keep:
                        buf.write(chunk)
                    elif len(head) < 16:
                        head.extend(chunk[:16])
                sha, size = _read(z, info, m["size"], sink)
                if sha != m["sha256"] or size != m["size"]:
                    raise ShareError(tr(
                        "grimoire.sharesetup", "{name} doesn't match the setup's manifest (damaged or altered).")
                        .format(name=name[:80]))
                if kind == "setup.json":
                    try:
                        raw = _loads(buf.getvalue())
                    except (ValueError, UnicodeDecodeError, RecursionError):
                        raise ShareError(tr("grimoire.sharesetup",
                                            "The setup's settings aren't valid JSON; not importing it.")) from None
                elif kind == "preview.png":
                    preview = buf.getvalue() if _magic_ok(name, buf.getvalue()[:16]) else b""
                else:
                    if not _magic_ok(name, bytes(head)):
                        raise ShareError(tr(
                            "grimoire.sharesetup", "{name} isn't the picture it says it is; not importing it.")
                            .format(name=name[:80]))
                    wallpapers[name[11:]] = (size, sha)
            if raw is None:
                raise ShareError(tr("grimoire.sharesetup", "That isn't a Grimoire setup (no setup.json)."))
            missing = [p for p in listed if _kind(p)]
            if missing:
                raise ShareError(tr("grimoire.sharesetup", "The setup is missing {name}, which its manifest lists.")
                                 .format(name=missing[0][:80]))
            shared = Shared(title=_text(meta.get("title"), TITLE_MAX) or tr("grimoire.sharesetup", "Untitled setup"),
                            author=_text(meta.get("author"), AUTHOR_MAX), setup=clean(raw),
                            created=_text(meta.get("created"), 40), app_version=_text(meta.get("app_version"), 20),
                            preview=preview, wallpapers=wallpapers, ignored=ignored, source=source, digest=digest)
    except zipfile.BadZipFile as e:
        raise ShareError(tr("grimoire.sharesetup", "The setup is damaged: {error}").format(error=e)) from None
    except (zipfile.LargeZipFile, NotImplementedError, EOFError, RuntimeError) as e:
        raise ShareError(tr("grimoire.sharesetup", "The setup can't be read: {error}").format(error=e)) from None
    except OSError as e:
        raise ShareError(tr("grimoire.sharesetup", "Couldn't read the setup: {error}")
                         .format(error=e.strerror or e)) from None
    if not shared.setup:
        raise ShareError(tr("grimoire.sharesetup", "This setup has nothing Grimoire can use."))
    return shared


def from_code(text: str) -> Shared:
    """A pasted GS1- code, checked like a file."""
    text = "".join(str(text).split())
    if not text.startswith(CODE_PREFIX) or len(text) > MAX_CODE * 2:
        raise ShareError(tr("grimoire.sharesetup", "That isn't a Grimoire setup code (they start with {prefix}).")
                         .format(prefix=CODE_PREFIX))
    body = text[len(CODE_PREFIX):]
    try:
        packed = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        z = zlib.decompressobj()
        raw = z.decompress(packed, MAX_SETUP)
        if z.unconsumed_tail or not z.eof:
            raise ValueError("too large or cut short")
        data = _loads(raw)
    except (ValueError, TypeError, zlib.error, UnicodeDecodeError, RecursionError):
        raise ShareError(tr("grimoire.sharesetup", "That setup code is damaged; copy it again.")) from None
    if not isinstance(data, dict) or data.get("v") != FORMAT_VERSION:
        raise ShareError(tr("grimoire.sharesetup", "That setup code is from a different Grimoire version."))
    shared = Shared(title=_text(data.get("t"), TITLE_MAX) or tr("grimoire.sharesetup", "Untitled setup"),
                    author=_text(data.get("a"), AUTHOR_MAX),
                    setup=clean(data.get("s")))
    if not shared.setup:
        raise ShareError(tr("grimoire.sharesetup", "This setup has nothing Grimoire can use."))
    return shared


# ---------------------------------------------------------------- preview: what would change
@dataclass
class Change:
    label: str
    now: str
    new: str

    @property
    def same(self) -> bool:
        return self.now == self.new


def _design_name(key: str, design: str | None) -> str:
    if not design:
        return "—"
    try:
        from grimoire.spells.mural.looks import design_label
        return design_label(key, design)
    except Exception:                               # a broken store registry must not stop the preview
        return design.split(":")[-1]


def _on(v) -> str:
    return tr("grimoire.sharesetup", "on") if v else tr("grimoire.sharesetup", "off")


def _opts_text(opts: dict) -> str:
    return ", ".join(f"{k.replace('_', ' ')} {_on(v) if isinstance(v, bool) else v}"
                     for k, v in opts.items())


def _crosshair_text(c: dict) -> str:
    return tr("grimoire.sharesetup", "{style}, {color}, size {size}").format(style=c.get("style"), color=c.get("color"),
                                                                              size=c.get("size"))


def _profiles_change(mine: dict, theirs: dict) -> Change:
    _, names = _merge_named(mine, theirs)
    added = [names[k] for k in theirs if names[k] not in mine]
    return Change(tr("grimoire.sharesetup", "Profiles"), ", ".join(mine) or "—",
                  tr("grimoire.sharesetup", "adds {names}").format(names=", ".join(added)) if added
                  else ", ".join(mine))


def changes(shared: Shared) -> dict:
    """{spell: [Change]} for each spell the setup touches: what this PC has now → what the setup has."""
    from grimoire.spells.mural.looks import LABELS
    label = lambda key: tr("grimoire.spells.mural.looks", LABELS[key]) if key in LABELS else key
    now, new, out = current(), shared.setup, {}
    if "mural" in new:
        rows, ntabs = [], (now.get("mural") or {}).get("tabs", {})
        for key, entry in new["mural"]["tabs"].items():
            cur = ntabs.get(key) or {}
            rows.append(Change(label(key), _design_name(key, cur.get("design")),
                               _design_name(key, entry["design"])))
            if cur.get("options") != entry["options"] and entry["options"]:
                rows.append(Change(tr("grimoire.sharesetup", "{tab} options").format(tab=label(key)),
                                   _opts_text(cur.get("options") or {}) or "—", _opts_text(entry["options"])))
        desk = new["mural"].get("desktop")
        if desk:
            cur = (now.get("mural") or {}).get("desktop") or {}
            fmt = lambda n, m: tr("grimoire.sharesetup", "%n wallpaper(s), every {m} min", n=n).format(m=m)
            rows.insert(0, Change(tr("grimoire.sharesetup", "Wallpaper playlist"),
                                  fmt(len(cur.get("items", [])), cur.get("interval_min", 5)) if cur else "—",
                                  fmt(len(desk["items"]), desk["interval_min"])))
        out["mural"] = rows
    if "sightc" in new:
        rows, cur = [], now.get("sightc") or {}
        if "crosshair" in new["sightc"]:
            rows.append(Change(tr("grimoire.sharesetup", "Crosshair"), _crosshair_text(cur.get("crosshair") or {}),
                               _crosshair_text(new["sightc"]["crosshair"])))
        if new["sightc"].get("profiles"):
            rows.append(_profiles_change(cur.get("profiles", {}), new["sightc"]["profiles"]))
        out["sightc"] = rows
    if "terminall" in new:
        cur = now.get("terminall") or {}
        _, names = _merge_named(cur.get("profiles", {}), new["terminall"]["profiles"])
        out["terminall"] = [_profiles_change(cur.get("profiles", {}), new["terminall"]["profiles"]),
                            Change(tr("grimoire.sharesetup", "Profile in use"), cur.get("profile", "—"),
                                   names[new["terminall"]["profile"]])]
    if "launchl" in new:
        cur = (now.get("launchl") or {}).get("favorites", [])
        out["launchl"] = [Change(tr("grimoire.sharesetup", "Favorites order"),
                                 tr("grimoire.sharesetup", "%n favorite(s)", n=len(cur)),
                                 tr("grimoire.sharesetup", "%n favorite(s)", n=len(new["launchl"]["favorites"])))]
    if "tray" in new:
        out["tray"] = [Change(tr("grimoire.sharesetup", "CPU and RAM meter"),
                              _on((now.get("tray") or {}).get("meter", True)), _on(new["tray"]["meter"]))]
    return out


def missing_store(shared: Shared) -> list:
    """Store items the setup uses that this PC hasn't installed (yet)."""
    reg = _registry()
    return [r for r in shared.setup.get("store", []) if f"{r['kind']}:{r['ident']}" not in reg]


def missing_pictures(shared: Shared) -> list:
    """Wallpapers the setup names that are neither inside it nor in this PC's library (nor coming from the store)."""
    store = {r["ident"] for r in shared.setup.get("store", []) if r["kind"] == "wallpaper"}
    return [n for n in _pictures(shared.setup) if n not in shared.wallpapers and n not in store and not _match(n)]


def get_from_store(ref: dict) -> str:
    """Download and install one referenced store item (on the user's click only). Returns its name."""
    from grimoire.spells.mural import store
    cat = (store.CATEGORIES["wallhaven-bw"] if ref["item"].startswith("wh-") else
           next(c for c in store.CATEGORIES.values() if c.kind == ref["kind"] and not c.wallhaven))
    store.install(cat, store.fetch(ref["item"]))
    return ref["name"]


# ---------------------------------------------------------------- apply
@dataclass
class Result:
    safety: Path | None
    look_id: str = ""
    favorites: list = field(default_factory=list)
    written: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def _atomic(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ShareError(tr("grimoire.sharesetup", "{name} is a link on this PC; not replacing it.")
                         .format(name=path.name))
    tmp = path.with_name(f".{path.name}.share-tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)                   # our own temp file, only left over on failure


def _write_json(path: Path, data):
    _atomic(path, json.dumps(data, indent=2, ensure_ascii=False).encode())


def _match(name: str) -> str | None:
    """The library file for a shared name: the same name, else the same name with another picture type
    (store wallpapers converted to black & white become .png)."""
    if _library_file(name):
        return name
    stem = os.path.splitext(name)[0]
    for p in sorted(LIBRARY.glob("*")) if LIBRARY.is_dir() else []:
        if os.path.splitext(p.name)[0] == stem and _library_file(p.name):
            return p.name
    return None


def _free(name: str, taken) -> str:
    stem, ext = os.path.splitext(name)
    n = 2
    while (cand := f"{stem} ({n}){ext}") in taken or (LIBRARY / cand).exists() or (LIBRARY / cand).is_symlink():
        n += 1
    return cand


def _sha_file(p: Path) -> str:
    return _digest(p)


def _copy_wallpapers(shared: Shared, result: Result) -> dict:
    """Put the setup's pictures into MuraL's library; never overwrites. Returns {shared name: library name}."""
    renamed = {}
    if not shared.wallpapers:
        return renamed
    LIBRARY.mkdir(parents=True, exist_ok=True)
    with _open(shared.source) as z:
        for name, (size, sha) in shared.wallpapers.items():
            dest = LIBRARY / name
            if dest.exists() or dest.is_symlink():
                if not dest.is_symlink() and dest.is_file() and _sha_file(dest) == sha:
                    continue                                     # already here
                new = _free(name, renamed.values())
                renamed[name], dest = new, LIBRARY / new
            tmp = dest.with_name(f".{dest.name}.share-tmp")
            try:
                with open(tmp, "wb") as f:
                    got, _ = _read(z, z.getinfo(f"wallpapers/{name}"), size, f.write)
                    f.flush()
                    os.fsync(f.fileno())
                if got != sha:
                    raise ShareError(tr("grimoire.sharesetup", "{name} changed while importing; stopped.")
                                     .format(name=name))
                if dest.exists() or dest.is_symlink():
                    raise ShareError(tr("grimoire.sharesetup", "{name} appeared in your library meanwhile; stopped.")
                                     .format(name=dest.name))
                tmp.replace(dest)
            finally:
                tmp.unlink(missing_ok=True)
            result.written.append(f"wallpapers/{dest.name}")
    return renamed


def _rename_pictures(mural: dict, renamed: dict) -> dict:
    tabs = {k: {**v, "options": dict(v["options"])} for k, v in mural.get("tabs", {}).items()}
    lock = tabs.get("lock")
    if lock and lock["design"].startswith("img:") and lock["design"][4:] in renamed:
        lock["design"] = "img:" + renamed[lock["design"][4:]]
    login = tabs.get("login")
    if login and login["options"].get("background") in renamed:
        login["options"]["background"] = renamed[login["options"]["background"]]
    desk = mural.get("desktop")
    if desk:
        desk = {**desk, "items": [renamed.get(n, n) for n in desk["items"]]}
    return {"tabs": tabs, "desktop": desk}


def _save_look(title: str, mural: dict, preview: bytes) -> str:
    """The MuraL part as a saved look (MuraL → Looks), so applying it to the desktop stays a separate choice."""
    from grimoire.spells.mural import looks
    tabs = {k: {**v, "label": _design_name(k, v["design"])} for k, v in mural["tabs"].items()}
    desk = mural.get("desktop")
    look = {"id": uuid.uuid4().hex[:12], "name": title, "created": datetime.now().isoformat(timespec="seconds"),
            "tabs": tabs, "desktop": None, "shared": {"desktop": desk}}
    if desk:
        look["desktop"] = {**desk, "items": [str(LIBRARY / n) for n in desk["items"]]}
    if preview:
        looks.THUMBS.mkdir(parents=True, exist_ok=True)
        _atomic(looks.thumb_path(look["id"]), preview)
    looks._change(lambda d: d.setdefault("looks", []).append(look))
    return look["id"]


def _merge_named(mine: dict, theirs: dict) -> tuple[dict, dict]:
    """Add their profiles to mine; one I already have (same settings) isn't added twice, and a name already taken
    gets " (2)", " (3)"… Returns (merged, their name → name here)."""
    merged, names = dict(mine), {}
    for k, v in theirs.items():
        same = k if merged.get(k) == v else next((n for n, m in merged.items() if m == v), None)
        if same is not None:
            names[k] = same
            continue
        new, n = k, 2
        while new in merged:
            new, n = f"{k} ({n})", n + 1
        merged[new], names[k] = v, new
    return merged, names


def apply(shared: Shared, parts=frozenset(SPELLS), progress=lambda text: None) -> Result:
    """Write the chosen parts of a checked setup. A safety backup of the current settings is saved first."""
    from grimoire import backup
    if shared.source is not None and _digest(shared.source) != shared.digest:
        raise ShareError(tr("grimoire.sharesetup", "The setup file changed since it was checked; open it again."))
    new = shared.setup
    progress(tr("grimoire.sharesetup", "Saving a safety backup…"))
    result = Result(backup.safety_backup())
    try:
        if "mural" in parts and "mural" in new:
            progress(tr("grimoire.sharesetup", "Adding the wallpapers…"))
            renamed = _copy_wallpapers(shared, result)
            mural = _rename_pictures(new["mural"], renamed)
            result.look_id = _save_look(shared.title, mural, shared.preview)
            result.written.append("mural-looks.json")
        if "sightc" in parts and "sightc" in new:
            from grimoire.spells.sightc import config as sc
            if "crosshair" in new["sightc"]:
                screen = sc.Crosshair.load().screen                  # which monitor stays this PC's choice
                _write_json(sc.FILE, {**sc.Crosshair.from_dict(new["sightc"]["crosshair"]).look(), "screen": screen})
                result.written.append(sc.FILE.name)
            if new["sightc"].get("profiles"):
                mine = {k: c.look() for k, c in sc.load_profiles().items()}
                merged, _ = _merge_named(mine, new["sightc"]["profiles"])
                _write_json(sc.PROFILES_FILE, merged)
                result.written.append(sc.PROFILES_FILE.name)
        if "terminall" in parts and "terminall" in new:
            from grimoire.spells.terminall import config as tc
            cfg = tc.load()                                         # keeps this PC's own palette commands
            merged, names = _merge_named(cfg["profiles"], new["terminall"]["profiles"])
            cfg["profiles"], cfg["profile"] = merged, names[new["terminall"]["profile"]]
            _write_json(tc.FILE, cfg)
            result.written.append(tc.FILE.name)
        if "launchl" in parts and "launchl" in new:
            result.favorites = list(new["launchl"]["favorites"])     # applied with the look: it's in Plasma's files
        if "tray" in parts and "tray" in new:
            _write_json(TRAY, {**_json(TRAY, {}), "meter": new["tray"]["meter"]})
            result.written.append(TRAY.name)
    except (OSError, ShareError, zipfile.BadZipFile) as err:
        msg = err.strerror if isinstance(err, OSError) and err.strerror else str(err)
        raise ShareError(tr("grimoire.sharesetup", "{error} Your settings from before are saved in {safety}.").format(
            error=msg, safety=result.safety.name)) from None
    return result


def apply_look(result: Result, include_root=frozenset(), progress=None) -> list:
    """Put the imported look on the desktop now (MuraL's own restore, then LaunchL's favorites order).
    Changes the live desktop: only on the user's click. Returns [(part, ok, message)]."""
    out = []
    if result.look_id:
        from grimoire.spells.mural import looks
        _resolve(result.look_id)
        out += [(tr("grimoire.spells.mural.looks", looks.LABELS[k]) if k in looks.LABELS else
                 tr("grimoire.sharesetup", "Wallpaper") if k == "desktop" else k, ok, msg)
                for k, ok, msg in looks.restore(result.look_id, include_root, progress)]
    if result.favorites:
        from grimoire.spells.launchl import panel
        rec = panel.load_state().get("replaced") or {}
        if rec.get("favorites_client"):
            panel.write_order(rec["favorites_client"], result.favorites)
            out.append(("LaunchL", True, tr("grimoire.sharesetup",
                                            "Favorites reordered; LaunchL shows it next time Plasma starts.")))
        else:
            out.append(("LaunchL", True, tr("grimoire.sharesetup", "Skipped (LaunchL isn't in your panel).")))
    return out


def _resolve(look_id: str):
    """Point the saved look at the library files as they are now (store wallpapers may have arrived since)."""
    from grimoire.spells.mural import looks

    def fn(d):
        for look in d.get("looks", []):
            if look.get("id") != look_id:
                continue
            desk = (look.get("shared") or {}).get("desktop")
            if desk:
                items = [m for n in desk["items"] if (m := _match(n))]
                look["desktop"] = {**desk, "items": [str(LIBRARY / n) for n in items]} if items else None
            lock = look.get("tabs", {}).get("lock")
            if lock and lock["design"].startswith("img:") and (m := _match(lock["design"][4:])):
                lock["design"] = "img:" + m
            login = look.get("tabs", {}).get("login")
            if login and IMAGE_NAME.fullmatch(login["options"].get("background", "")):
                login["options"]["background"] = _match(login["options"]["background"]) or \
                    login["options"]["background"]
    looks._change(fn)
