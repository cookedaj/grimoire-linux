# SPDX-License-Identifier: GPL-3.0-or-later
"""GameL's library: the installed games of Steam, Heroic (Epic, GOG, Amazon, sideloaded) and Lutris, read from
the launchers' own files. Read-only: nothing here writes to a launcher's files (Lutris' database is opened in
read-only mode). No Qt, so the home page's status line can use it.

Home folders are read late (Path.home() at call time), so tests can point HOME at a sandbox.
"""
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.request import pathname2url

from grimoire.spells.gamel import vdf

SOURCES = {"steam": "Steam", "heroic": "Heroic", "lutris": "Lutris"}
STORES = {"legendary": "Epic", "gog": "GOG", "nile": "Amazon", "sideload": "Sideloaded"}

# Steam's own runtimes and compatibility tools also have app manifests; they aren't games
# (runtimes, Proton builds, anti-cheat runtimes); names and toolmanifest.vdf catch newer ones
STEAM_TOOLS = {228980, 1070560, 1391110, 1628350, 4183110, 1493710, 2180100, 1826330, 1161040}
STEAM_TOOL_NAMES = re.compile(r"^(Proton\b|Steam Linux Runtime|Steamworks Common)", re.I)


@dataclass
class Game:
    source: str                 # steam | heroic | lutris
    id: str                     # Steam appid, Heroic app name, Lutris game id
    name: str
    path: str = ""              # install folder ("" when the launcher doesn't say)
    size: int = 0               # bytes; 0 = not known yet
    last_played: float = 0      # epoch seconds; 0 = never / not known
    playtime: float | None = None   # minutes; None = not known
    cover: str = ""             # a local cover image, if the launcher keeps one
    store: str = ""             # Heroic: legendary | gog | nile | sideload; Lutris: its runner
    flatpak: bool = False       # the launcher is the Flatpak one
    note: str = ""              # e.g. Steam is still downloading it
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"

    @property
    def source_name(self) -> str:
        if self.source == "heroic" and self.store in STORES:
            return "Heroic · {store}".format(store=STORES[self.store])
        return SOURCES.get(self.source, self.source)


def _home() -> Path:
    return Path.home()


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def _int(v, default=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


_UNITS = {"b": 1, "kb": 1024, "kib": 1024, "mb": 1024 ** 2, "mib": 1024 ** 2, "gb": 1024 ** 3, "gib": 1024 ** 3,
          "tb": 1024 ** 4, "tib": 1024 ** 4}


def parse_size(v) -> int:
    """12345, "12345" or "12.3 GiB" -> bytes (0 if it can't tell)."""
    if isinstance(v, (int, float)):
        return max(0, int(v))
    m = re.match(r"^\s*([\d.]+)\s*([a-z]*)\s*$", str(v or ""), re.I)
    if not m:
        return 0
    try:
        return int(float(m.group(1)) * _UNITS.get(m.group(2).lower() or "b", 0))
    except ValueError:
        return 0


# ---------------------------------------------------------------- Steam
def steam_roots() -> list[tuple[Path, bool]]:
    """Steam installs found here, as (folder, is_flatpak), each once."""
    h = _home()
    cands = [(h / ".steam/steam", False), (h / ".steam/root", False), (h / ".local/share/Steam", False),
             (h / ".steam/debian-installation", False), (h / "snap/steam/common/.local/share/Steam", False),
             (h / ".var/app/com.valvesoftware.Steam/.local/share/Steam", True),
             (h / ".var/app/com.valvesoftware.Steam/data/Steam", True)]
    out, seen = [], set()
    for p, flat in cands:
        try:
            real = p.resolve()
        except OSError:
            continue
        if real not in seen and (real / "steamapps").is_dir():
            seen.add(real)
            out.append((real, flat))
    return out


def steam_libraries(root: Path) -> list[Path]:
    libs = [root]
    for f in (root / "steamapps/libraryfolders.vdf", root / "config/libraryfolders.vdf"):
        folders = vdf.find(vdf.load(f), "libraryfolders") or {}
        for v in folders.values():
            path = v.get("path") if isinstance(v, dict) else v if isinstance(v, str) and "/" in v else None
            if path:
                libs.append(Path(path))
    out, seen = [], set()
    for lib in libs:
        try:
            real = lib.resolve()
        except OSError:
            continue
        if real not in seen and (real / "steamapps").is_dir():
            seen.add(real)
            out.append(real)
    return out


def steam_playtimes(root: Path) -> dict[str, tuple[float, float]]:
    """appid -> (last played, minutes played), from every signed-in user's localconfig.vdf (latest/most wins)."""
    out: dict[str, tuple[float, float]] = {}
    try:
        users = [d for d in (root / "userdata").iterdir() if d.is_dir()]
    except OSError:
        return out
    for u in users:
        apps = vdf.find(vdf.load(u / "config/localconfig.vdf"), "UserLocalConfigStore", "Software", "Valve",
                        "Steam", "apps") or {}
        for appid, d in apps.items():
            if isinstance(d, dict):
                last, mins = _int(d.get("LastPlayed")), _int(d.get("Playtime"))
                old = out.get(appid, (0, 0))
                out[appid] = (max(old[0], last), max(old[1], mins))
    return out


def steam_cover(root: Path, appid: str) -> str:
    """The portrait cover from Steam's library cache, else its wide header; both layouts Steam has used."""
    cache = root / "appcache/librarycache"
    for name in ("library_600x900.jpg", "library_capsule.jpg", "library_header.jpg", "header.jpg"):
        for p in (cache / appid / name, cache / f"{appid}_{name}"):
            if p.is_file():
                return str(p)
        folder = cache / appid
        if folder.is_dir():                                # newer clients nest some images one folder down
            try:
                hit = next((s / name for s in folder.iterdir() if (s / name).is_file()), None)
            except OSError:
                hit = None
            if hit:
                return str(hit)
    return ""


def is_steam_tool(appid: str, name: str, folder: Path) -> bool:
    return _int(appid) in STEAM_TOOLS or bool(STEAM_TOOL_NAMES.match(name)) or (folder / "toolmanifest.vdf").is_file()


def scan_steam() -> list[Game]:
    games: dict[str, Game] = {}
    for root, flat in steam_roots():
        played = steam_playtimes(root)
        for lib in steam_libraries(root):
            for acf in sorted((lib / "steamapps").glob("appmanifest_*.acf")):
                st = vdf.find(vdf.load(acf), "AppState") or {}
                appid, name = str(st.get("appid") or ""), str(st.get("name") or "")
                if not appid.isdigit() or not name or appid in games:
                    continue
                folder = lib / "steamapps/common" / str(st.get("installdir") or name)
                if is_steam_tool(appid, name, folder):
                    continue
                last, mins = played.get(appid, (0, 0))
                flags = _int(st.get("StateFlags"))
                note = "" if flags & 4 else "Steam hasn't finished downloading or updating it."
                games[appid] = Game("steam", appid, name, str(folder), _int(st.get("SizeOnDisk")),
                                    max(last, _int(st.get("LastPlayed"))), mins,
                                    steam_cover(root, appid), flatpak=flat, note=note)
    return list(games.values())


# ---------------------------------------------------------------- Heroic
def heroic_roots() -> list[tuple[Path, bool]]:
    h = _home()
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or h / ".config")
    return [(p, flat) for p, flat in ((cfg / "heroic", False),
                                      (h / ".var/app/com.heroicgameslauncher.hgl/config/heroic", True))
            if p.is_dir()]


def _iso(v) -> float:
    if isinstance(v, (int, float)):
        return v / 1000 if v > 1e11 else float(v)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0


def _titles(*files: Path) -> dict[str, str]:
    """app name -> title from Heroic's library caches (several shapes across versions)."""
    out: dict[str, str] = {}
    for f in files:
        d = _json(f)
        items = d if isinstance(d, list) else (d.get("library") or d.get("games") or []) if isinstance(d, dict) else []
        for g in items if isinstance(items, list) else []:
            if not isinstance(g, dict):
                continue
            key = g.get("app_name") or g.get("appName") or g.get("id")
            product = g.get("product") if isinstance(g.get("product"), dict) else {}
            title = g.get("title") or product.get("title")
            if key and title:
                out[str(key)] = str(title)
    return out


def scan_heroic() -> list[Game]:
    games: dict[str, Game] = {}
    for root, flat in heroic_roots():
        times = _json(root / "store/timestamp.json") or {}
        raw: list[tuple[str, str, str, str, int]] = []      # (store, app, title, path, size)

        legendary = _json(root / "legendaryConfig/legendary/installed.json") or {}
        titles = _titles(root / "store_cache/legendary_library.json", root / "lib-cache/library.json")
        for app, g in (legendary.items() if isinstance(legendary, dict) else []):
            if isinstance(g, dict) and not g.get("is_dlc"):
                raw.append(("legendary", app, g.get("title") or titles.get(app, app), g.get("install_path", ""),
                            parse_size(g.get("install_size"))))

        gog = _json(root / "gog_store/installed.json") or {}
        titles = _titles(root / "store_cache/gog_library.json", root / "gog_store/library.json")
        for g in (gog.get("installed") or [] if isinstance(gog, dict) else []):
            if isinstance(g, dict) and g.get("appName") and not g.get("is_dlc"):
                path = g.get("install_path", "")
                raw.append(("gog", str(g["appName"]), titles.get(str(g["appName"])) or Path(path).name or
                            str(g["appName"]), path, parse_size(g.get("install_size"))))

        nile = _json(root / "nile_config/nile/installed.json") or []
        titles = _titles(root / "store_cache/nile_library.json", root / "nile_config/nile/library.json")
        for g in nile if isinstance(nile, list) else []:
            if isinstance(g, dict) and g.get("id"):
                path = g.get("path", "")
                raw.append(("nile", str(g["id"]), titles.get(str(g["id"])) or Path(path).name or str(g["id"]), path,
                            parse_size(g.get("size"))))

        side = _json(root / "sideload_apps/library.json") or {}
        for g in (side.get("games") or [] if isinstance(side, dict) else []):
            if isinstance(g, dict) and g.get("app_name") and g.get("is_installed", True):
                inst = g.get("install") if isinstance(g.get("install"), dict) else {}
                exe = inst.get("executable") or ""
                path = g.get("folder_name") or (str(Path(exe).parent) if exe else "")
                raw.append(("sideload", str(g["app_name"]), g.get("title") or g["app_name"], path, 0))

        for store, app, title, path, size in raw:
            if app in games:
                continue
            t = times.get(app) if isinstance(times, dict) else None
            t = t if isinstance(t, dict) else {}
            games[app] = Game("heroic", app, str(title), str(path or ""), size, _iso(t.get("lastPlayed") or 0),
                              float(t["totalPlayed"]) if isinstance(t.get("totalPlayed"), (int, float)) else 0,
                              store=store, flatpak=flat)
    return list(games.values())


# ---------------------------------------------------------------- Lutris
def lutris_dirs() -> list[tuple[Path, bool]]:
    h = _home()
    data = Path(os.environ.get("XDG_DATA_HOME") or h / ".local/share")
    return [(p, flat) for p, flat in ((data / "lutris", False), (h / ".var/app/net.lutris.Lutris/data/lutris", True))
            if (p / "pga.db").is_file()]


def _lutris_rows(db: Path) -> list[dict]:
    """Installed games from pga.db, opened read-only (immutable as a fallback when Lutris holds a lock)."""
    for mode in ("mode=ro", "mode=ro&immutable=1"):
        try:
            con = sqlite3.connect(f"file:{pathname2url(str(db))}?{mode}", uri=True, timeout=1)
        except sqlite3.Error:
            continue
        try:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute("SELECT * FROM games WHERE installed = 1")]
        except sqlite3.Error:
            continue
        finally:
            con.close()
    return []


def lutris_cover(data: Path, slug: str) -> str:
    cache = Path(os.environ.get("XDG_CACHE_HOME") or _home() / ".cache") / "lutris"
    for base in (data, cache):
        for sub in ("coverart", "banners"):
            for ext in ("jpg", "png"):
                p = base / sub / f"{slug}.{ext}"
                if slug and p.is_file():
                    return str(p)
    return ""


def scan_lutris() -> list[Game]:
    games: dict[str, Game] = {}
    for data, flat in lutris_dirs():
        for r in _lutris_rows(data / "pga.db"):
            gid = str(r.get("id") or "")
            if not gid or gid in games or not r.get("name"):
                continue
            hours = r.get("playtime")
            games[gid] = Game("lutris", gid, str(r["name"]), str(r.get("directory") or ""), 0,
                              _int(r.get("lastplayed")),
                              float(hours) * 60 if isinstance(hours, (int, float)) else 0,
                              lutris_cover(data, str(r.get("slug") or "")), store=str(r.get("runner") or ""),
                              flatpak=flat, extra={"slug": r.get("slug") or ""})
    return list(games.values())


# ---------------------------------------------------------------- all of them
SCANNERS = {"steam": scan_steam, "heroic": scan_heroic, "lutris": scan_lutris}


def scan() -> tuple[list[Game], list[str]]:
    """Every installed game, plus a problem line for any launcher that couldn't be read."""
    games, problems = [], []
    for src, fn in SCANNERS.items():
        try:
            games += fn()
        except Exception as e:                       # one odd file shouldn't hide the other launchers
            problems.append("{source}: {error}".format(source=SOURCES[src], error=e))
    return games, problems


def sort_games(games: list[Game], by: str) -> list[Game]:
    name = lambda g: g.name.casefold()                       # noqa: E731
    if by == "last":
        return sorted(games, key=lambda g: (-g.last_played, name(g)))
    if by == "size":
        return sorted(games, key=lambda g: (-g.size, name(g)))
    if by == "playtime":
        return sorted(games, key=lambda g: (-(g.playtime or 0), name(g)))
    return sorted(games, key=name)


def folder_size(path: str, budget: float = 20.0) -> int:
    """Bytes under path (symlinks not followed), giving up after `budget` seconds with what it counted."""
    total, stack, end = 0, [path], time.monotonic() + budget
    while stack and time.monotonic() < end:
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            total += e.stat(follow_symlinks=False).st_blocks * 512
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def ago(ts: float, now: float | None = None) -> str:
    if not ts:
        return "Never"
    now = now or time.time()
    days = (datetime.fromtimestamp(now).date() - datetime.fromtimestamp(ts).date()).days
    if days <= 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    if days < 30:
        return "{n} days ago".format(n=days)
    return datetime.fromtimestamp(ts).strftime("%d %b %Y")


def hours(minutes: float | None) -> str:
    if minutes is None:
        return "Not known"
    if minutes <= 0:
        return "Not played yet"
    if minutes < 60:
        return "{n:.0f} min".format(n=minutes)
    return "{n:.1f} h".format(n=minutes / 60)


def status_line() -> str:
    games, _ = scan()
    if not games:
        return "No games found yet"
    last = max(games, key=lambda g: g.last_played)
    count = "1 game" if len(games) == 1 else "{n} games".format(n=len(games))
    if not last.last_played:
        return count
    return "{count} · last played {name}".format(count=count, name=last.name)
