# SPDX-License-Identifier: GPL-3.0-or-later
"""The rest of the library, beyond Steam, Heroic and Lutris: itch (butler.db), Bottles (bottle.yml programs),
Roblox (Sober to play, Vinegar for Studio, each its own tile) and every game in the app menu (desktop entries with
Categories=Game, native and Flatpak). Read-only like library.py, no Qt.

Menu entries that only start another launcher's game (Steam's "Play this game on Steam" shortcuts, Lutris' and
Heroic's menu entries) are dropped when that launcher's own library could be read, and launchers and tools
(Steam itself, ProtonUp-Qt, Protontricks…) aren't games. library.dedupe() does the rest.
System folders are module values so tests can point them at a sandbox.
"""
import os
import re
import shutil
import sqlite3
from pathlib import Path
from urllib.request import pathname2url

from grimoire.i18n import tr
from grimoire.spells.gamel.library import Game, _home, _int, _iso, steam_roots

FLATPAK_SYSTEM = Path("/var/lib/flatpak")
SNAP_APPS = Path("/var/lib/snapd/desktop/applications")
SOBER, VINEGAR = "org.vinegarhq.Sober", "org.vinegarhq.Vinegar"
PROTONTRICKS = "com.github.Matoking.protontricks"

# desktop ids (without .desktop) that are launchers or tools, not games; Roblox gets its own tiles
NOT_GAMES = {
    "steam", "steam-native", "steam-runtime", "com.valvesoftware.Steam", "valve-steam", "heroic",
    "com.heroicgameslauncher.hgl", "lutris", "net.lutris.Lutris", "itch", "io.itch.itch", "com.usebottles.bottles",
    "bottles", "net.davidotek.pupgui2", "protonup-qt", PROTONTRICKS, PROTONTRICKS + "-launch", "protontricks",
    "protontricks-launch", SOBER, VINEGAR, "vinegar", "org.vinegarhq.Vinegar.studio", "io.github.benjamimgois.goverlay",
    "goverlay", "minigalaxy", "io.github.sharkwouter.Minigalaxy", "gamehub", "com.github.tkashkin.gamehub",
}
# a game is never filed only under these as well
TOOL_CATEGORIES = {"Utility", "Settings", "PackageManager", "System", "Development"}
# Exec URLs of another launcher's games: (pattern, source); the launcher's own library lists them already
LAUNCHER_URLS = ((re.compile(r"steam://(?:rungameid|run)/(\d+)"), "steam"),
                 (re.compile(r"lutris:(?:rungameid/)?(\d+)"), "lutris"),
                 (re.compile(r"heroic://launch(?:/[a-z]+)?[/?](?:appName=)?([A-Za-z0-9_.-]+)"), "heroic"),
                 (re.compile(r"itch://caves/"), "itch"),
                 (re.compile(r"\bbottles-cli\b|com\.usebottles\.bottles"), "bottles"))
APP_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,254}$")
CAVE_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or _home() / ".local/share")


def flatpak_installs() -> list[Path]:
    """The user's and the system's Flatpak installations."""
    return [_data_home() / "flatpak", FLATPAK_SYSTEM]


def flatpak_installed(app: str) -> bool:
    return any((base / "app" / app / "current").exists() for base in flatpak_installs())


def has_protontricks() -> str:
    """'flatpak', 'native' or '' (not installed)."""
    if flatpak_installed(PROTONTRICKS):
        return "flatpak"
    return "native" if shutil.which("protontricks") else ""


# ---------------------------------------------------------------- desktop entries and icons
def app_dirs() -> list[Path]:
    """Where menu entries live, highest priority first (an id seen first hides later ones)."""
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    dirs = [_data_home() / "applications", *(i / "exports/share/applications" for i in flatpak_installs())]
    dirs += [Path(d) / "applications" for d in data_dirs.split(":") if d.startswith("/")]
    dirs.append(SNAP_APPS)
    out, seen = [], set()
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def icon_dirs() -> list[Path]:
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    bases = [_data_home(), *(i / "exports/share" for i in flatpak_installs())]
    bases += [Path(d) for d in data_dirs.split(":") if d.startswith("/")]
    return [_home() / ".icons", *(b / "icons" for b in bases)]


_SIZES = ("512x512", "256x256", "scalable", "192x192", "128x128", "96x96", "64x64", "48x48")


def find_icon(name: str) -> str:
    """An icon file for a desktop entry's Icon= (a path, or a name looked up in hicolor and pixmaps)."""
    if not name:
        return ""
    if os.path.isabs(name):
        return name if os.path.isfile(name) else ""
    if "/" in name:
        return ""
    for base in icon_dirs():
        for size in _SIZES:
            for ext in ("png", "svg"):
                p = base / "hicolor" / size / "apps" / f"{name}.{ext}"
                if p.is_file():
                    return str(p)
    for ext in ("png", "svg", "xpm"):
        p = Path("/usr/share/pixmaps") / f"{name}.{ext}"
        if p.is_file():
            return str(p)
    return ""


def read_desktop(path: Path) -> dict[str, str]:
    """The [Desktop Entry] group's plain keys (localized ones are skipped); {} when unreadable."""
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read(256 * 1024)
    except OSError:
        return out
    group = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            group = line
            continue
        if group == "[Desktop Entry]" and "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            if "[" not in k:
                out.setdefault(k, v.strip())
    return out


def _true(v: str) -> bool:
    return v.strip().lower() == "true"


def _try_exec(v: str) -> bool:
    if not v:
        return True
    return os.access(v, os.X_OK) if os.path.isabs(v) else shutil.which(v) is not None


def _readable(source: str) -> bool:
    """Whether a launcher's own library was found here, so its menu shortcuts are copies."""
    if source == "steam":
        return bool(steam_roots())
    from grimoire.spells.gamel import library
    if source == "heroic":
        return bool(library.heroic_roots())
    if source == "lutris":
        return bool(library.lutris_dirs())
    if source == "itch":
        return bool(itch_dbs())
    if source == "bottles":
        return bool(bottles_dirs())
    return False


def desktop_entries() -> list[tuple[str, Path, dict]]:
    """(desktop id, file, keys) for every visible game in the menu, each id once."""
    out, seen = [], set()
    for d in app_dirs():
        try:
            files = sorted(d.rglob("*.desktop"))
        except OSError:
            continue
        for f in files:
            try:
                did = str(f.relative_to(d))[:-len(".desktop")].replace("/", "-")
            except ValueError:
                continue
            if did in seen:
                continue
            seen.add(did)                                 # a hidden copy higher up hides this id everywhere
            e = read_desktop(f)
            cats = {c for c in e.get("Categories", "").split(";") if c}
            if (e.get("Type", "Application") != "Application" or _true(e.get("Hidden", ""))
                    or _true(e.get("NoDisplay", "")) or "Game" not in cats or not e.get("Name")
                    or not e.get("Exec") or did in NOT_GAMES or cats & TOOL_CATEGORIES
                    or not _try_exec(e.get("TryExec", ""))):
                continue
            out.append((did, f, e))
    return out


def scan_desktop() -> list[Game]:
    games, readable = [], {}
    for did, f, e in desktop_entries():
        dup = ""
        for rx, src in LAUNCHER_URLS:
            m = rx.search(e["Exec"])
            if m:
                if src not in readable:
                    readable[src] = _readable(src)
                dup = f"{src}:{m.group(1)}" if m.groups() else src
                break
        if dup and readable.get(dup.split(":")[0]):
            continue                                       # that launcher's tile is the real one
        app = e.get("X-Flatpak", "")
        flat = bool(app) or any(str(f).startswith(str(i / "exports")) for i in flatpak_installs())
        folder = ""
        if flat and APP_ID_RE.match(app or did) and (_home() / ".var/app" / (app or did)).is_dir():
            folder = str(_home() / ".var/app" / (app or did))
        elif os.path.isabs(e.get("Path", "")):
            folder = e["Path"]
        extra = {"desktop": str(f)}
        if dup:
            extra["dup"] = dup
        games.append(Game("flatpak" if flat else "native", did, e["Name"], folder, icon=find_icon(e.get("Icon", "")),
                          store="snap" if str(f).startswith(str(SNAP_APPS)) else "", flatpak=flat, extra=extra))
    return games


# ---------------------------------------------------------------- Roblox
def _desktop_of(app: str) -> str:
    for i in flatpak_installs():
        p = i / "exports/share/applications" / f"{app}.desktop"
        if p.is_file():
            return str(p)
    return ""


def scan_roblox() -> list[Game]:
    """Sober plays Roblox, Vinegar runs Roblox Studio: one tile each when installed (Flatpak, or a native vinegar)."""
    games = []
    for app, gid, name in ((SOBER, "sober", "Roblox"), (VINEGAR, "studio", "Roblox Studio")):
        flat = flatpak_installed(app)
        native = gid == "studio" and not flat and shutil.which("vinegar")
        if not (flat or native):
            continue
        data = _home() / ".var/app" / app
        desk = _desktop_of(app) if flat else ""
        games.append(Game("roblox", gid, name, str(data) if flat and data.is_dir() else "",
                          icon=find_icon(app if flat else "vinegar"), store=gid, flatpak=bool(flat),
                          extra={"desktop": desk, "app": app}))
    return games


# ---------------------------------------------------------------- itch
def itch_dbs() -> list[tuple[Path, bool]]:
    h = _home()
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or h / ".config")
    return [(p, flat) for p, flat in ((cfg / "itch/db/butler.db", False),
                                      (h / ".var/app/io.itch.itch/config/itch/db/butler.db", True)) if p.is_file()]


def _rows(db: Path, sql: str) -> list[dict]:
    for mode in ("mode=ro", "mode=ro&immutable=1"):
        try:
            con = sqlite3.connect(f"file:{pathname2url(str(db))}?{mode}", uri=True, timeout=1)
        except sqlite3.Error:
            continue
        try:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute(sql)]
        except sqlite3.Error:
            continue
        finally:
            con.close()
    return []


def scan_itch() -> list[Game]:
    games: dict[str, Game] = {}
    for db, flat in itch_dbs():
        rows = _rows(db, "SELECT c.id AS cave, c.install_folder_name AS folder, c.last_touched_at AS last, "
                         "c.seconds_run AS secs, c.installed_size AS size, g.title AS title, l.path AS base "
                         "FROM caves c LEFT JOIN games g ON g.id = c.game_id "
                         "LEFT JOIN install_locations l ON l.id = c.install_location_id")
        for r in rows:
            cave = str(r.get("cave") or "")
            if not CAVE_RE.match(cave) or cave in games or not r.get("title"):
                continue
            base, sub = r.get("base"), r.get("folder")          # any type: the database is just a file
            folder = os.path.join(base, sub) if isinstance(base, str) and isinstance(sub, str) and base and sub \
                else ""
            last = r.get("last")
            secs = r.get("secs")
            games[cave] = Game("itch", cave, str(r["title"]), folder if os.path.isabs(folder) else "",
                               _int(r.get("size")), _iso(last) if last else 0,
                               secs / 60 if isinstance(secs, (int, float)) else 0, flatpak=flat)
    return list(games.values())


# ---------------------------------------------------------------- Bottles
def bottles_dirs() -> list[tuple[Path, bool]]:
    h = _home()
    return [(p, flat) for p, flat in ((_data_home() / "bottles/bottles", False),
                                      (h / ".var/app/com.usebottles.bottles/data/bottles/bottles", True))
            if p.is_dir()]


def scan_bottles() -> list[Game]:
    """Programs added to a bottle (its bottle.yml's External_Programs), started with bottles-cli."""
    dirs = bottles_dirs()
    if not dirs:
        return []
    try:
        import yaml
    except ImportError:
        raise RuntimeError(tr("grimoire.spells.gamel.others", "reading Bottles needs python3-yaml "
                              "(sudo apt install python3-yaml)")) from None
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    games: dict[str, Game] = {}
    for base, flat in dirs:
        try:
            bottles = sorted(p for p in base.iterdir() if (p / "bottle.yml").is_file())
        except OSError:
            continue
        for b in bottles:
            try:
                with open(b / "bottle.yml", "rb") as f:
                    d = yaml.load(f.read(4 * 1024 * 1024), Loader=loader)
            except (OSError, yaml.YAMLError, RecursionError, ValueError, TypeError, OverflowError):
                continue                           # ValueError etc.: a date like 2020-99-99 fails while loading
            if not isinstance(d, dict):
                continue
            bottle = str(d.get("Name") or b.name)
            progs = d.get("External_Programs")
            for pid, p in (progs.items() if isinstance(progs, dict) else []):
                if not isinstance(p, dict) or p.get("removed") or not p.get("name"):
                    continue
                gid = str(p.get("id") or pid)
                if not CAVE_RE.match(gid) or gid in games or bottle.startswith("-") or str(p["name"]).startswith("-"):
                    continue
                exe = str(p.get("path") or "")
                folder = str(p.get("folder") or (os.path.dirname(exe) if exe else ""))
                games[gid] = Game("bottles", gid, str(p["name"]), folder if os.path.isabs(folder) else "",
                                  store=bottle, flatpak=flat, extra={"bottle": bottle, "program": str(p["name"])})
    return list(games.values())
