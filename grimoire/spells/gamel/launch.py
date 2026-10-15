# SPDX-License-Identifier: GPL-3.0-or-later
"""Starting games through their own launcher, and opening a game's folder in VaultL. No Qt.

    Steam    steam steam://rungameid/<appid>          (Flatpak: flatpak run com.valvesoftware.Steam …)
    Heroic   heroic --no-gui heroic://launch?appName=<app>&runner=<legendary|gog|nile|sideload>
    Lutris   lutris lutris:rungameid/<id>

Missing a command, it falls back to xdg-open on the URL. Starting a game changes nothing else on the system.
RUN is the one place a process starts, so tests swap it for a stub and never launch a real game.
"""
import errno
import os
import shutil
import subprocess
from urllib.parse import urlencode

from grimoire.paths import command
from grimoire.spells.gamel import overlay
from grimoire.spells.gamel.library import ID_RE, Game

FLATPAK = {"steam": "com.valvesoftware.Steam", "heroic": "com.heroicgameslauncher.hgl", "lutris": "net.lutris.Lutris"}


def _run(argv: list[str], env: dict):
    subprocess.Popen(argv, env=dict(os.environ, **env), start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


RUN = _run


def url(g: Game) -> str:
    """ValueError for an id that can't be one (the library only lists valid ones; this is the last guard)."""
    if g.source not in FLATPAK or (g.source != "heroic" and not ID_RE.match(g.id)) or not g.id:
        raise ValueError(g.key)
    if g.source == "steam":
        return f"steam://rungameid/{g.id}"
    if g.source == "heroic":
        return "heroic://launch?" + urlencode({"appName": g.id, "runner": g.store or "legendary"})
    return f"lutris:rungameid/{g.id}"


def argv(g: Game) -> list[str]:
    u = url(g)
    if g.flatpak and shutil.which("flatpak"):
        extra = ["--no-gui"] if g.source == "heroic" else []
        return ["flatpak", "run", FLATPAK[g.source], *extra, u]
    exe = {"steam": "steam", "heroic": "heroic", "lutris": "lutris"}[g.source]
    if shutil.which(exe):
        return [exe, "--no-gui", u] if g.source == "heroic" else [exe, u]
    return ["xdg-open", u]


def game_env(g: Game) -> dict:
    """MANGOHUD=1 for Heroic and Lutris games while the overlay is on. Steam's URL goes to the Steam client already
    running, so an environment can't reach the game: Steam games need `mangohud %command%` in their launch options."""
    return {} if g.source == "steam" else overlay.env()


def play(g: Game):
    """Raises OSError when the launcher can't be started, ValueError for an id that isn't one."""
    RUN(argv(g), game_env(g))


def open_folder(path: str):
    """Only absolute paths: a relative one (or "tidy") would be read by grimoire-vaultl as something else."""
    if not os.path.isabs(path):
        raise OSError(errno.EINVAL, os.strerror(errno.EINVAL), path)
    RUN([str(command("grimoire-vaultl")), path], {})
