# SPDX-License-Identifier: GPL-3.0-or-later
"""CleanupL's and UninstallerL's shared engine (no Qt).

What Grimoire replaces (REPLACED), what's installed of it, the settings and caches apps leave in your home
(leftovers), AppImages and hand-made installs (user_apps), and the list of what was removed (so Reinstall can put
it back). Removing packages goes through StoreL's engine: an `apt-get -s` preview, one password for the batch, and
StoreL's root helper, which refuses the desktop, its fonts and required system packages. Files in your home only
ever go to the Trash.
"""
import configparser
import json
import os
import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path

from grimoire.fsutil import human, trash
from grimoire.i18n import tr, tr_noop
from grimoire.paths import CACHE, DATA, HOME
from grimoire.spells.storel import sources

RESTORE = DATA / "cleanupl-removed.json"
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config")
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local/share")
CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME") or HOME / ".cache")
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME") or HOME / ".local/state")


@dataclass(frozen=True)
class Replaced:
    key: str
    title: str                       # the app's own name (not translated)
    spell: str                       # what does its job in Grimoire
    apt: tuple = ()                  # packages that are the app (never libraries others share)
    flatpak: tuple = ()              # Flatpak app ids
    leftovers: tuple = ()            # under ~/.config, ~/.local/share, ~/.local/state, ~/.cache ("config:dolphinrc")


def _r(key, title, spell, apt=(), flatpak=(), leftovers=()):
    return Replaced(key, title, spell, tuple(apt), tuple(flatpak), tuple(leftovers))


# Spectacle (ShotL captures through it), KDE Connect (PhoneL talks to its daemon), KDE Partition Manager (SystemL's
# Drives sends formatting there), ksystemstats (WidgetL's sensors) and the KDE modules SettingL opens stay: see KEPT.
REPLACED = (
    _r("dolphin", "Dolphin", "VaultL", ["dolphin", "dolphin-plugins"], ["org.kde.dolphin"],
       ["config:dolphinrc", "data:dolphin", "state:dolphinstaterc", "cache:dolphin"]),
    _r("ark", "Ark", "VaultL", ["ark"], ["org.kde.ark"], ["config:arkrc", "data:ark"]),
    _r("gwenview", "Gwenview", "ViewL", ["gwenview"], ["org.kde.gwenview"],
       ["config:gwenviewrc", "data:gwenview", "state:gwenviewstaterc", "cache:gwenview"]),
    _r("okular", "Okular", "ReadL", ["okular", "okular-extra-backends"], ["org.kde.okular"],
       ["config:okularrc", "config:okularpartrc", "data:okular", "state:okularstaterc"]),
    _r("konsole", "Konsole", "TerminalL", ["konsole"], ["org.kde.konsole"],
       ["config:konsolerc", "data:konsole", "state:konsolestaterc"]),
    _r("yakuake", "Yakuake", "TerminalL", ["yakuake"], ["org.kde.yakuake"], ["config:yakuakerc"]),
    _r("kate", "Kate", "NoteL", ["kate"], ["org.kde.kate"],
       ["config:katerc", "config:katevirc", "data:kate", "state:katestaterc"]),
    _r("kwrite", "KWrite", "NoteL", ["kwrite"], ["org.kde.kwrite"], ["config:kwriterc", "state:kwritestaterc"]),
    _r("haruna", "Haruna", "PlayL", ["haruna"], ["org.kde.haruna"], ["config:haruna", "data:haruna"]),
    _r("elisa", "Elisa", "PlayL", ["elisa"], ["org.kde.elisa"], ["config:elisarc", "data:elisa"]),
    _r("dragonplayer", "Dragon Player", "PlayL", ["dragonplayer"], ["org.kde.dragonplayer"],
       ["config:dragonplayerrc"]),
    _r("vlc", "VLC", "PlayL", ["vlc"], ["org.videolan.VLC"], ["config:vlc", "data:vlc"]),
    _r("kcharselect", "KCharSelect", "GlyphL", ["kcharselect"], ["org.kde.kcharselect"], ["config:kcharselectrc"]),
    _r("systemmonitor", "System Monitor", "SystemL", ["plasma-systemmonitor"], [],
       ["config:plasma-systemmonitorrc", "data:plasma-systemmonitor"]),
    _r("discover", "Discover", "StoreL + UpdateL",
       ["plasma-discover", "plasma-discover-backend-flatpak", "plasma-discover-backend-snap",
        "plasma-discover-backend-fwupd"], [], ["config:discoverrc", "cache:discover"]),
)
KEPT = (
    ("Spectacle", tr_noop("grimoire.spells.cleanupl.engine", "ShotL takes its screenshots through it")),
    ("KDE Connect", tr_noop("grimoire.spells.cleanupl.engine", "PhoneL talks to your phone through its service")),
    ("KDE Partition Manager", tr_noop("grimoire.spells.cleanupl.engine",
                                      "SystemL's Drives opens it to format and partition")),
    ("ksystemstats", tr_noop("grimoire.spells.cleanupl.engine", "WidgetL's system widget reads its sensors")),
    ("System Settings", tr_noop("grimoire.spells.cleanupl.engine", "SettingL opens KDE's own modules")),
)
USED_BY = {"kdeconnect": "PhoneL", "spectacle": "ShotL", "partitionmanager": "SystemL", "ksystemstats": "WidgetL",
           "systemsettings": "SettingL", "libmpv2": "PlayL", "rclone": "CloudL", "7zip": "VaultL"}
_BASES = {"config": CONFIG_HOME, "data": DATA_HOME, "state": STATE_HOME, "cache": CACHE_HOME}


def leftover_path(spec: str) -> Path:
    base, _, rel = spec.partition(":")
    return _BASES[base] / rel


def du(path: Path, limit: int = 100_000) -> int:
    """Bytes under path (never following links), stopping after `limit` files."""
    try:
        st = path.lstat()
    except OSError:
        return 0
    if not path.is_dir() or path.is_symlink():
        return st.st_size
    total, n, stack = 0, 0, [str(path)]
    while stack and n < limit:
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    n += 1
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def existing(paths) -> list[tuple[Path, int]]:
    """[(path, bytes)] of those that exist."""
    return [(p, du(p)) for p in paths if p.exists() or p.is_symlink()]


# ---------------------------------------------------------------- what's on this PC
@dataclass
class Found:
    """One app that's here: how it's installed, what it takes, what it leaves."""
    key: str
    title: str
    source: str                         # "apt" | "flatpak" | "snap" | "appimage" | "user"
    names: list                         # packages, Flatpak refs, the snap, or the files of an AppImage/user install
    size: int | None = None
    scope: str = "system"               # Flatpak
    replaced_by: str = ""
    why_not: str = ""                   # set: it can't be removed here (the desktop or the system needs it)
    leftovers: list = field(default_factory=list)       # [(Path, bytes)]
    app_id: str = ""                    # Flatpak id, for ~/.var/app


def replaced(have: dict | None = None) -> list[Found]:
    """The REPLACED apps that are installed (APT and/or Flatpak), and those that only left files behind."""
    have = have if have is not None else sources.installed()
    apt, flat = have.get("apt", {}), have.get("flatpak", [])
    out = []
    for r in REPLACED:
        lefts = existing(leftover_path(s) for s in r.leftovers)
        pkgs = [p for p in r.apt if p in apt]
        if pkgs:
            why = next((w for w in (sources.removable(p, apt.get(p)) for p in pkgs) if w), "")
            out.append(Found(r.key, r.title, "apt", pkgs, sum(apt[p].get("size") or 0 for p in pkgs) or None,
                             replaced_by=r.spell, why_not=why, leftovers=lefts))
        for f in flat:
            if f["id"] in r.flatpak:
                out.append(Found(r.key, r.title, "flatpak", [f["ref"]], f.get("size"), scope=f["scope"],
                                 replaced_by=r.spell, leftovers=lefts + existing([HOME / ".var/app" / f["id"]]),
                                 app_id=f["id"]))
        if not pkgs and not any(f["id"] in r.flatpak for f in flat) and lefts:
            out.append(Found(r.key, r.title, "files", [], 0, replaced_by=r.spell, leftovers=lefts))
    return out


def _desktop(path: Path) -> dict:
    cp = configparser.RawConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
        return dict(cp["Desktop Entry"])
    except (configparser.Error, KeyError, UnicodeDecodeError, OSError):
        return {}


APPIMAGE_DIRS = ("Applications", "AppImages", ".local/bin", "Downloads", "Desktop", "bin", ".local/share/applications")


def user_apps() -> list[Found]:
    """AppImages in the usual folders, and apps installed by hand into your home that a menu entry in
    ~/.local/share/applications starts (Exec inside ~, not a Flatpak, not Grimoire's own)."""
    out, seen = [], set()
    for d in APPIMAGE_DIRS:
        try:
            files = list((HOME / d).glob("*.[Aa]pp[Ii]mage"))
        except OSError:
            continue
        for f in sorted(files):
            if f.is_file() and f.resolve() not in seen:
                seen.add(f.resolve())
                title = re.sub(r"[-_.]?(x86_64|amd64|aarch64|linux)?$", "", f.stem, flags=re.I) or f.stem
                out.append(Found("appimage:" + f.name, title, "appimage", [f], du(f)))
    apps = DATA_HOME / "applications"
    try:
        entries = sorted(apps.glob("*.desktop"))
    except OSError:
        entries = []
    for entry in entries:
        e = _desktop(entry)
        if e.get("Type") != "Application" or entry.name.startswith("grimoire") or e.get("X-Grimoire-Edited") \
                or e.get("X-Flatpak") or "flatpak" in e.get("Exec", "") or e.get("NoDisplay", "").lower() == "true":
            continue
        try:
            argv = shlex.split(e.get("Exec", ""))
        except ValueError:
            continue
        if not argv:
            continue
        exe = Path(os.path.expanduser(argv[0]))
        if not exe.is_absolute() or not exe.is_relative_to(HOME) or not (exe.exists() or exe.is_symlink()):
            continue
        real = exe.resolve()
        if real in seen:                                      # an AppImage with a menu entry: one row, both files
            for f in out:
                if f.source == "appimage" and f.names[0].resolve() == real:
                    f.names.append(entry)
                    f.title = e.get("Name") or f.title
            continue
        seen.add(real)
        # an app in its own folder (~/.local/share/foo/bin/foo, ~/opt/foo/foo): the whole folder; else the file
        home_dir = next((p for p in real.parents if p.parent in (HOME, DATA_HOME, HOME / "opt", HOME / "Applications")
                         and p != HOME), None)
        files = [home_dir or real, entry]
        out.append(Found("user:" + entry.stem, e.get("Name") or entry.stem, "user", files, du(home_dir or real)))
    return out


def everything(have: dict | None = None) -> list[Found]:
    """Every app UninstallerL lists: system apps with menu entries (APT), Flatpaks, snaps and user installs."""
    have = have if have is not None else sources.installed()
    apt = have.get("apt", {})
    out, by_pkg = [], {}
    for d in have.get("desktop", []):
        pkg = d["pkg"]
        if pkg in by_pkg:                                     # one package, several menu entries: one row
            continue
        info = apt.get(pkg) or {}
        by_pkg[pkg] = f = Found("apt:" + pkg, d["name"], "apt", [pkg], info.get("size"),
                                why_not=sources.removable(pkg, info), app_id=d["id"])
        out.append(f)
    for fl in have.get("flatpak", []):
        out.append(Found("flatpak:" + fl["ref"] + ":" + fl["scope"], fl["name"], "flatpak", [fl["ref"]],
                         fl.get("size"), scope=fl["scope"], app_id=fl["id"]))
    for sn in have.get("snap", []):
        out.append(Found("snap:" + sn["name"], sn["name"], "snap", [sn["name"]], None))
    out += user_apps()
    for f in out:
        used = USED_BY.get(f.names[0]) if f.source == "apt" and f.names else None
        if used:                                              # Grimoire leans on it: say so, still the user's call
            f.replaced_by = tr("grimoire.spells.cleanupl.engine", "Used by {spell}").format(spell=used)
        if not f.replaced_by:
            f.replaced_by = next((r.spell for r in REPLACED if f.source == "apt" and f.names[0] in r.apt
                                  or f.source == "flatpak" and f.app_id in r.flatpak), "")
    return sorted(out, key=lambda f: f.title.lower())


def guess_leftovers(f: Found) -> list[tuple[Path, int]]:
    """Settings and caches an app probably left: its REPLACED list when it has one, else folders and rc files
    named like it (its package, its desktop id's last part, its name) under ~/.config, ~/.local/share, ~/.cache
    and ~/.local/state, plus ~/.var/app/<id> for a Flatpak. Only what exists; the user picks before anything goes."""
    known = next((r for r in REPLACED if f.key == r.key or f.source == "apt" and f.names and f.names[0] in r.apt
                  or f.app_id and f.app_id in r.flatpak), None)
    if known:
        paths = [leftover_path(s) for s in known.leftovers]
    else:
        stems = {f.title, f.title.lower(), f.title.replace(" ", ""), f.title.lower().replace(" ", "")}
        if f.source == "apt" and f.names:
            stems.add(f.names[0])
        if f.app_id:
            stems.add(f.app_id.split(".")[-1].lower())
        stems |= _own_names(f)
        stems = {s for s in stems if len(s) >= 3 and re.fullmatch(r"[\w.+-]+", s)
                 and s.lower() not in {"kde", "gnome", "org", "com", "app", "the", "settings", "linux"}}
        paths = []
        for base in (CONFIG_HOME, DATA_HOME, CACHE_HOME, STATE_HOME):
            for s in stems:
                paths += [base / s, base / f"{s}rc", base / f"{s}staterc"]
    if f.source == "flatpak" and f.app_id:
        paths.append(HOME / ".var/app" / f.app_id)
    paths += _traces(f)
    seen, out = set(), []
    for p, size in existing(paths):
        if p not in seen and _safe_leftover(p):
            seen.add(p)
            out.append((p, size))
    return out


def _own_names(f: Found) -> set[str]:
    """An AppImage's or hand-made install's own names: its menu entry's id and its program's file name."""
    if f.source not in ("appimage", "user"):
        return set()
    out = {f.key.split(":", 1)[1].removesuffix(".desktop").lower()}
    for n in f.names:
        if isinstance(n, Path) and n.suffix != ".desktop":
            out.add(n.name.lower())
            out.add(re.sub(r"[-_.]?(\d[\w.]*)?([-_.]?(x86_64|amd64|aarch64))?\.appimage$", "", n.name.lower()))
    return {o for o in out if o}


def _traces(f: Found) -> list[Path]:
    """What starts the app or points at it from your home: autostart entries, your own menu entries (copies or
    edits of its .desktop file) and systemd user units whose name or command names it."""
    words = {w.lower() for w in (f.app_id, f.app_id.split(".")[-1] if f.app_id else "",
                                 f.names[0] if f.source in ("apt", "snap") and f.names else "",
                                 f.title.replace(" ", ""), *_own_names(f)) if w and len(w) >= 3}
    if not words:
        return []
    hits = []
    for folder, pattern in ((CONFIG_HOME / "autostart", "*.desktop"), (DATA_HOME / "applications", "*.desktop"),
                            (CONFIG_HOME / "systemd/user", "*.service"), (CONFIG_HOME / "systemd/user", "*.timer")):
        try:
            files = list(folder.glob(pattern))
        except OSError:
            continue
        for path in files:
            if "grimoire" in path.name.lower() or not path.is_file():
                continue
            name = path.stem.lower()
            try:
                text = path.read_text(errors="replace")[:20000].lower()
            except OSError:
                continue
            execs = " ".join(line for line in text.splitlines() if line.startswith(("exec=", "execstart=")))
            if any(w == name or name.endswith("." + w) or re.search(rf"(^|[/\s=]){re.escape(w)}(\s|$|\.)", execs)
                   for w in words):
                hits.append(path)
    return hits


GROUPS = {"config": tr_noop("grimoire.spells.cleanupl.engine", "Settings"),
          "data": tr_noop("grimoire.spells.cleanupl.engine", "Data"),
          "cache": tr_noop("grimoire.spells.cleanupl.engine", "Cache"),
          "state": tr_noop("grimoire.spells.cleanupl.engine", "Window state"),
          "autostart": tr_noop("grimoire.spells.cleanupl.engine", "Starts at login"),
          "menu": tr_noop("grimoire.spells.cleanupl.engine", "Menu entries"),
          "units": tr_noop("grimoire.spells.cleanupl.engine", "Background services"),
          "flatpak": tr_noop("grimoire.spells.cleanupl.engine", "Flatpak data"),
          "app": tr_noop("grimoire.spells.cleanupl.engine", "Program files")}


def group_of(p: Path) -> str:
    """Which GROUPS heading a leftover goes under."""
    for key, base in (("autostart", CONFIG_HOME / "autostart"), ("menu", DATA_HOME / "applications"),
                      ("units", CONFIG_HOME / "systemd/user"), ("flatpak", HOME / ".var/app"),
                      ("cache", CACHE_HOME), ("state", STATE_HOME), ("data", DATA_HOME), ("config", CONFIG_HOME)):
        if p.is_relative_to(base):
            return key
    return "app"


def owner_of(desktop_id: str, found: list[Found]) -> Found | None:
    """The app a window belongs to, from its desktop file name (KWin's queryWindowInfo "desktopFile")."""
    d = desktop_id.removesuffix(".desktop").lower()
    if not d:
        return None
    for f in found:
        ids = {f.app_id.lower(), *(n.lower() for n in f.names if isinstance(n, str))}
        if f.source == "user":
            ids.add(f.key.split(":", 1)[1].lower())
        if d in ids or any(d == i.split("/")[1].lower() for i in ids if i.startswith("app/") and "/" in i[4:]):
            return f
    return None


def _safe_leftover(p: Path) -> bool:
    """Never a base folder itself or anything of Grimoire's."""
    if p in (HOME, CONFIG_HOME, DATA_HOME, CACHE_HOME, STATE_HOME, HOME / ".var/app", CONFIG_HOME / "autostart",
             DATA_HOME / "applications", CONFIG_HOME / "systemd", CONFIG_HOME / "systemd/user") \
            or "grimoire" in p.name.lower():
        return False
    return any(p.is_relative_to(b) for b in (*_BASES.values(), HOME / ".var/app"))


# ---------------------------------------------------------------- removing files, and remembering
def trash_files(paths: list[Path]) -> list[str]:
    """Leftovers, AppImages and hand-made installs go to the Trash (Restore puts them back); errors per item."""
    errors = []
    for p in paths:
        if not (p.exists() or p.is_symlink()):
            continue
        try:
            trash(p)
        except OSError as e:
            errors.append(f"{p.name}: {e}")
    return errors


def removed() -> list[dict]:
    try:
        data = json.loads(RESTORE.read_text())
    except (OSError, ValueError):
        return []
    return [d for d in data if isinstance(d, dict) and d.get("source") in ("apt", "flatpak", "snap")
            and isinstance(d.get("names"), list)] if isinstance(data, list) else []


def remember(found: Found):
    """Add a removed package app to the restore list (files in the Trash restore from the Trash instead)."""
    if found.source not in ("apt", "flatpak", "snap"):
        return
    data = [d for d in removed() if not (d["source"] == found.source and d["names"] == found.names)]
    data.append({"title": found.title, "source": found.source, "names": list(found.names), "scope": found.scope,
                 "when": int(time.time())})
    _write(data[-200:])


def forget(entry: dict):
    _write([d for d in removed() if d != entry])


def _write(data: list):
    RESTORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = RESTORE.with_name(f".{RESTORE.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=1))
    os.replace(tmp, RESTORE)


def total(found: list[Found], with_leftovers: bool = True) -> int:
    return sum((f.size or 0) + (sum(s for _p, s in f.leftovers) if with_leftovers else 0) for f in found)


STATUS = CACHE / "cleanupl-status.json"


def remember_status(mode: str, found: list[Found]):
    """What the last scan saw, for the home page's status lines (they never scan themselves)."""
    try:
        data = json.loads(STATUS.read_text())
        data = data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        data = {}
    apps = [f for f in found if f.source != "files"]
    data[mode] = {"apps": len(apps), "bytes": total(found), "files": len(found) - len(apps)}
    try:
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        STATUS.write_text(json.dumps(data))
    except OSError:
        pass


def status_line(mode: str) -> str:
    try:
        d = json.loads(STATUS.read_text())[mode]
        apps, size = int(d["apps"]), int(d["bytes"])
    except (OSError, ValueError, KeyError, TypeError):
        return tr("grimoire.spells.cleanupl.engine", "Not scanned yet")
    if mode == "cleanup":
        if not apps and not d.get("files"):
            return tr("grimoire.spells.cleanupl.engine", "Nothing left to clean up")
        return tr("grimoire.spells.cleanupl.engine", "%n replaceable app(s)", n=apps) + " · " + \
            tr("grimoire.spells.cleanupl.engine", "{size} to free").format(size=human(size))
    return tr("grimoire.spells.cleanupl.engine", "%n app(s) installed", n=apps)


def describe_source(f: Found) -> str:
    return {"apt": tr("grimoire.spells.cleanupl.engine", "System package"),
            "flatpak": tr("grimoire.spells.cleanupl.engine", "Flatpak (just you)") if f.scope == "user"
            else tr("grimoire.spells.cleanupl.engine", "Flatpak"),
            "snap": tr("grimoire.spells.cleanupl.engine", "Snap"),
            "appimage": tr("grimoire.spells.cleanupl.engine", "AppImage"),
            "user": tr("grimoire.spells.cleanupl.engine", "Installed in your home"),
            "files": tr("grimoire.spells.cleanupl.engine", "Already removed: settings left")}.get(f.source, f.source)
