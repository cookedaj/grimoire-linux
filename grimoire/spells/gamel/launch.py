# SPDX-License-Identifier: GPL-3.0-or-later
"""Starting games through their own launcher, and opening a game's folder in VaultL. No Qt.

    Steam      steam steam://rungameid/<appid>      (Flatpak: flatpak run com.valvesoftware.Steam …)
               non-Steam shortcuts: steam://rungameid/<appid << 32 | 0x02000000>
    Heroic     heroic --no-gui heroic://launch?appName=<app>&runner=<legendary|gog|nile|sideload>
    Lutris     lutris lutris:rungameid/<id>
    itch       itch itch://caves/<cave>/launch
    Bottles    bottles-cli run -b <bottle> -p <program>
    Roblox     Sober's / Vinegar's own menu entry (gio launch), else flatpak run <app>
    menu games gio launch <the .desktop file>: exactly what the app menu runs

Missing a launcher command, URL ones fall back to xdg-open. Starting a game changes nothing else on the system; the
one file written is GameL's own play history. RUN is the one place a process starts, so tests swap it for a stub
and never launch a real game.
"""
import errno
import os
import shutil
import subprocess
from urllib.parse import urlencode

from grimoire.paths import command
from grimoire.spells.gamel import library, others, overlay
from grimoire.spells.gamel.library import ID_RE, Game

FLATPAK = {"steam": "com.valvesoftware.Steam", "heroic": "com.heroicgameslauncher.hgl", "lutris": "net.lutris.Lutris",
           "itch": "io.itch.itch", "bottles": "com.usebottles.bottles"}
URL_SOURCES = ("steam", "heroic", "lutris", "itch")


def _run(argv: list[str], env: dict):
    subprocess.Popen(argv, env=dict(os.environ, **env), start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


RUN = _run


def url(g: Game) -> str:
    """ValueError for an id that can't be one (the library only lists valid ones; this is the last guard)."""
    if g.source not in URL_SOURCES or not g.id:
        raise ValueError(g.key)
    if g.source in ("steam", "lutris") and not ID_RE.match(g.id):
        raise ValueError(g.key)
    if g.source == "steam":
        return f"steam://rungameid/{library.shortcut_gameid(g.id) if g.extra.get('shortcut') else g.id}"
    if g.source == "heroic":
        return "heroic://launch?" + urlencode({"appName": g.id, "runner": g.store or "legendary"})
    if g.source == "itch":
        if not others.CAVE_RE.match(g.id):
            raise ValueError(g.key)
        return f"itch://caves/{g.id}/launch"
    return f"lutris:rungameid/{g.id}"


def _desktop(g: Game) -> str:
    d = str(g.extra.get("desktop") or "")
    return d if os.path.isabs(d) and d.endswith(".desktop") and os.path.isfile(d) else ""


def argv(g: Game) -> list[str]:
    if g.source in URL_SOURCES:
        u = url(g)
        exe = {"steam": "steam", "heroic": "heroic", "lutris": "lutris", "itch": "itch"}[g.source]
        extra = ["--no-gui"] if g.source == "heroic" else []
        if g.flatpak and shutil.which("flatpak"):
            return ["flatpak", "run", FLATPAK[g.source], *extra, u]
        if shutil.which(exe):
            return [exe, *extra, u]
        return ["xdg-open", u]
    if g.source == "bottles":
        bottle, prog = str(g.extra.get("bottle") or ""), str(g.extra.get("program") or "")
        if not bottle or not prog or bottle.startswith("-") or prog.startswith("-"):
            raise ValueError(g.key)
        run = ["run", "-b", bottle, "-p", prog]
        if g.flatpak:
            return ["flatpak", "run", "--command=bottles-cli", FLATPAK["bottles"], *run]
        return ["bottles-cli", *run]
    desk = _desktop(g)
    if desk:
        return ["gio", "launch", desk]
    if g.source == "roblox":
        app = others.SOBER if g.id == "sober" else others.VINEGAR
        return ["flatpak", "run", app] if g.flatpak else ["vinegar"]
    raise ValueError(g.key)


def game_env(g: Game) -> dict:
    """MANGOHUD=1 for games GameL starts itself while the overlay is on. Steam's URL goes to the Steam client already
    running, so an environment can't reach the game: Steam games need `mangohud %command%` in their launch options.
    Flatpak games run sandboxed, where MangoHud needs its own Flatpak extension; they're left alone."""
    return {} if g.source in ("steam", "flatpak", "roblox") else overlay.env()


def play(g: Game):
    """Raises OSError when the launcher can't be started, ValueError for an id that isn't one."""
    RUN(argv(g), game_env(g))
    try:
        library.mark_played(g.key)
    except OSError:
        pass                                               # the history is a nicety


def protontricks_argv(appid: str = "") -> list[str]:
    """Protontricks' window for one Steam game (winetricks on its Proton prefix), or its game picker without an
    appid. --no-term: it shows its errors in a dialog, as there's no terminal. [] when it isn't installed."""
    if appid and not ID_RE.match(appid):
        raise ValueError(appid)
    args = ["--no-term", appid, "--gui"] if appid else ["--no-term", "--gui"]
    kind = others.has_protontricks()
    if kind == "flatpak":
        return ["flatpak", "run", others.PROTONTRICKS, *args]
    if kind == "native":
        return ["protontricks", *args]
    return []


def protontricks(appid: str = ""):
    """Raises OSError when Protontricks isn't installed or can't start."""
    cmd = protontricks_argv(appid)
    if not cmd:
        raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), "protontricks")
    RUN(cmd, {})


def open_folder(path: str):
    """Only absolute paths: a relative one (or "tidy") would be read by grimoire-vaultl as something else."""
    if not os.path.isabs(path):
        raise OSError(errno.EINVAL, os.strerror(errno.EINVAL), path)
    RUN([str(command("grimoire-vaultl")), path], {})
